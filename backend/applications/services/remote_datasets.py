import os
import posixpath
import shlex
import stat

import yaml

from applications.services.remote_models import ssh_connection


IMAGE_EXTENSIONS = {'.tif', '.tiff', '.png', '.jpg', '.jpeg'}


def validated_dataset_path(server, dataset_path):
    normalized = posixpath.normpath(str(dataset_path or ''))
    if (not normalized.startswith(server['root'] + '/') or
            posixpath.basename(normalized) not in {'dataset.yaml', 'dataset.yml'}):
        return None
    return normalized


def _read_yaml(sftp, path):
    with sftp.open(path, 'rb') as remote_file:
        value = yaml.safe_load(remote_file.read().decode('utf-8', errors='replace'))
    if not isinstance(value, dict):
        raise ValueError('dataset.yaml 内容不正确')
    return value


def _class_names(config):
    raw = config.get('names', [])
    if isinstance(raw, dict):
        def order(item):
            try:
                return 0, int(item[0])
            except (TypeError, ValueError):
                return 1, str(item[0])
        return [str(value).strip() for _, value in sorted(raw.items(), key=order)]
    return [str(value).strip() for value in raw] if isinstance(raw, list) else []


def _dataset_root(dataset_path, config):
    root = str(config.get('path', '')).strip() or posixpath.dirname(dataset_path)
    if not root.startswith('/'):
        root = posixpath.join(posixpath.dirname(dataset_path), root)
    return posixpath.normpath(root)


def _split_roots(dataset_path, config):
    root = _dataset_root(dataset_path, config)
    values = []
    for split_name in ('train', 'val', 'test'):
        entries = config.get(split_name, [])
        if isinstance(entries, str):
            entries = [entries]
        for entry in entries if isinstance(entries, list) else []:
            path = str(entry).strip()
            if not path:
                continue
            if not path.startswith('/'):
                path = posixpath.join(root, path)
            values.append((split_name, posixpath.normpath(path)))
    return root, values


def _walk_images(sftp, root):
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sftp.listdir_attr(directory)
        except OSError:
            continue
        for entry in entries:
            path = posixpath.join(directory, entry.filename)
            if stat.S_ISDIR(entry.st_mode):
                pending.append(path)
            elif posixpath.splitext(entry.filename)[1].lower() in IMAGE_EXTENSIONS:
                yield path, entry.st_size


def _label_path(dataset_root, image_root, image_path):
    relative = posixpath.relpath(image_path, image_root)
    stem = posixpath.splitext(relative)[0] + '.txt'
    if '/images/' in image_path:
        return posixpath.splitext(image_path.replace('/images/', '/labels/', 1))[0] + '.txt'
    return posixpath.join(dataset_root, 'labels', stem)


def _fast_counts(client, dataset_root, split_roots):
    roots = ' '.join(shlex.quote(path) for _, path in split_roots)
    if not roots:
        return 0, 0, 0
    image_expression = ' -o '.join("-iname '*{}'".format(extension) for extension in sorted(IMAGE_EXTENSIONS))
    label_root = posixpath.join(dataset_root, 'labels')
    command = (
        "find {roots} -type f \\( {images} \\) -printf '%s\\n' 2>/dev/null | "
        "awk '{{count++; bytes+=$1}} END {{printf \"%d %d\\n\", count, bytes}}'; "
        "find {labels} -type f -name '*.txt' -printf '%s\\n' 2>/dev/null | "
        "awk '{{count++; bytes+=$1}} END {{printf \"%d %d\\n\", count, bytes}}'"
    ).format(roots=roots, images=image_expression, labels=shlex.quote(label_root))
    _, stdout, _ = client.exec_command(command, timeout=30)
    values = stdout.read().decode('utf-8', errors='replace').split()
    if len(values) < 4:
        return 0, 0, 0
    return int(values[0]), int(values[2]), int(values[1]) + int(values[3])


def inspect_dataset(sftp, server, dataset_path, include_files=False, client=None):
    dataset_path = validated_dataset_path(server, dataset_path)
    if not dataset_path:
        raise ValueError('远程数据集路径不合法')
    config = _read_yaml(sftp, dataset_path)
    dataset_root, split_roots = _split_roots(dataset_path, config)
    if (not dataset_root.startswith(server['root'] + '/') or
            any(not path.startswith(server['root'] + '/') for _, path in split_roots)):
        raise ValueError('dataset.yaml 引用了允许目录之外的路径')
    files = []
    if not include_files and client:
        image_count, label_count, total_size = _fast_counts(client, dataset_root, split_roots)
    else:
        image_count = 0
        label_count = 0
        total_size = 0
        for split_name, image_root in split_roots:
            for image_path, size in _walk_images(sftp, image_root):
                label_path = _label_path(dataset_root, image_root, image_path)
                try:
                    label_size = sftp.stat(label_path).st_size
                    has_label = True
                except OSError:
                    label_size = 0
                    has_label = False
                image_count += 1
                label_count += int(has_label)
                total_size += size + label_size
                if include_files:
                    files.append({'split': split_name, 'image_path': image_path,
                                  'label_path': label_path if has_label else '', 'size': size})
    names = _class_names(config)
    return {
        'dataset_path': dataset_path, 'dataset_root': dataset_root,
        'name': posixpath.basename(dataset_root), 'class_names': names,
        'class_count': len(names), 'image_count': image_count,
        'label_count': label_count, 'total_size': total_size, 'files': files
    }


def scan_server_datasets(server):
    command = "find {} -maxdepth 4 -type f \\( -name dataset.yaml -o -name dataset.yml \\) -print".format(
        shlex.quote(server['root']))
    with ssh_connection(server) as client:
        _, stdout, stderr = client.exec_command(command, timeout=20)
        paths = stdout.read().decode('utf-8', errors='replace').splitlines()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        if stdout.channel.recv_exit_status():
            raise RuntimeError(error or '远程数据集扫描失败')
        sftp = client.open_sftp()
        try:
            datasets = []
            for path in paths:
                try:
                    datasets.append(inspect_dataset(sftp, server, path, client=client))
                except (OSError, UnicodeError, ValueError, yaml.YAMLError):
                    continue
            return sorted(datasets, key=lambda item: item['name'].lower())
        finally:
            sftp.close()


def download_dataset(server, dataset_path, destination, on_file):
    with ssh_connection(server) as client:
        sftp = client.open_sftp()
        try:
            dataset = inspect_dataset(sftp, server, dataset_path, include_files=True)
            total = len(dataset['files'])
            for index, item in enumerate(dataset['files'], start=1):
                on_file(sftp, item, destination, index, total)
            return dataset
        finally:
            sftp.close()
