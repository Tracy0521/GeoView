import json
import os
import posixpath
import shlex
from contextlib import contextmanager

import paramiko
import yaml


def configured_servers():
    """Read SSH targets from environment without ever returning credentials."""
    servers = []
    for index in range(1, 11):
        prefix = 'REMOTE_MODEL_SERVER_{}'.format(index)
        host = os.getenv('{}_HOST'.format(prefix), '').strip()
        if not host:
            continue
        try:
            port = int(os.getenv('{}_PORT'.format(prefix), '22'))
        except ValueError:
            port = 22
        servers.append({
            'id': str(index),
            'name': os.getenv('{}_NAME'.format(prefix), '远程服务器 {}'.format(index)).strip(),
            'host': host,
            'port': port,
            'username': os.getenv('{}_USERNAME'.format(prefix), 'root').strip() or 'root',
            'password': os.getenv('{}_PASSWORD'.format(prefix), ''),
            'key_filename': os.getenv('{}_KEY_FILE'.format(prefix), '').strip() or None,
            'root': os.getenv('{}_ROOT'.format(prefix), '/root/autodl-tmp').rstrip('/'),
            'python': os.getenv('{}_PYTHON'.format(prefix), '/root/miniconda3/bin/python').strip(),
            'yolo_root': os.getenv('{}_YOLO_ROOT'.format(prefix), '/root/ultralytics-YOLO26').strip()
        })
    return servers


def public_server(server):
    return {key: server[key] for key in ('id', 'name', 'host', 'port')}


def get_server(server_id):
    return next((server for server in configured_servers() if server['id'] == str(server_id)), None)


@contextmanager
def ssh_connection(server):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=server['host'], port=server['port'], username=server['username'],
        password=server['password'] or None, key_filename=server['key_filename'],
        timeout=6, banner_timeout=6, auth_timeout=6, look_for_keys=False,
        allow_agent=False
    )
    try:
        yield client
    finally:
        client.close()


def scan_server(server):
    output_root = posixpath.join(server['root'], 'output')
    command = "find {} -mindepth 3 -maxdepth 3 -type f -path '*/weights/best.pt' -printf '%s\\t%T@\\t%p\\n'".format(
        shlex.quote(output_root)
    )
    with ssh_connection(server) as client:
        _, stdout, stderr = client.exec_command(command, timeout=15)
        rows = stdout.read().decode('utf-8', errors='replace').splitlines()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        status = stdout.channel.recv_exit_status()
        if status:
            raise RuntimeError(error or '远程目录扫描失败')
        sftp = client.open_sftp()
        try:
            candidates = []
            for row in rows:
                parts = row.split('\t', 2)
                if len(parts) != 3:
                    continue
                size, modified_at, remote_path = parts
                experiment_dir = posixpath.dirname(posixpath.dirname(remote_path))
                results_path = posixpath.join(experiment_dir, 'results.csv')
                try:
                    results_size = sftp.stat(results_path).st_size
                    has_results = True
                except OSError:
                    results_size = 0
                    has_results = False
                category_info = read_category_info(sftp, server, experiment_dir)
                class_info = read_class_metrics(sftp, experiment_dir)
                candidates.append({
                    'server_id': server['id'],
                    'server_name': server['name'],
                    'name': posixpath.basename(experiment_dir),
                    'remote_path': remote_path,
                    'size': int(size),
                    'modified_at': float(modified_at),
                    'results_path': results_path if has_results else '',
                    'results_size': results_size,
                    'has_results': has_results,
                    **category_info,
                    **{key: value for key, value in class_info.items() if key != 'class_metrics'}
                })
            return sorted(candidates, key=lambda item: item['modified_at'], reverse=True)
        finally:
            sftp.close()


def validated_model_path(server, remote_path):
    normalized = posixpath.normpath(str(remote_path or ''))
    output_root = posixpath.join(server['root'], 'output') + '/'
    if not normalized.startswith(output_root):
        return None
    relative = normalized[len(output_root):]
    parts = relative.split('/')
    if len(parts) != 3 or parts[1:] != ['weights', 'best.pt'] or not parts[0]:
        return None
    return normalized


def validated_dataset_path(server, dataset_path):
    if not dataset_path:
        return ''
    normalized = posixpath.normpath(str(dataset_path))
    if (not normalized.startswith(server['root'] + '/') or
            posixpath.splitext(normalized)[1].lower() not in {'.yaml', '.yml'}):
        return None
    return normalized


def _yaml_from_sftp(sftp, path):
    try:
        stat = sftp.stat(path)
        if stat.st_size > 1024 * 1024:
            return {}
        with sftp.open(path, 'rb') as remote_file:
            value = yaml.safe_load(remote_file.read().decode('utf-8', errors='replace'))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}


def read_category_info(sftp, server, experiment_dir):
    args = _yaml_from_sftp(sftp, posixpath.join(experiment_dir, 'args.yaml'))
    dataset_path = str(args.get('data', '')).strip()
    if not dataset_path:
        return {'dataset_path': '', 'class_names': [], 'class_count': 0}
    if not dataset_path.startswith('/'):
        dataset_path = posixpath.join(server['root'], dataset_path)
    dataset_path = posixpath.normpath(dataset_path)
    allowed_root = server['root'] + '/'
    if (not dataset_path.startswith(allowed_root) or
            posixpath.splitext(dataset_path)[1].lower() not in {'.yaml', '.yml'}):
        return {'dataset_path': '', 'class_names': [], 'class_count': 0}
    dataset = _yaml_from_sftp(sftp, dataset_path)
    raw_names = dataset.get('names', [])
    if isinstance(raw_names, dict):
        def order(item):
            try:
                return 0, int(item[0])
            except (TypeError, ValueError):
                return 1, str(item[0])
        names = [str(value).strip() for _, value in sorted(raw_names.items(), key=order)]
    elif isinstance(raw_names, list):
        names = [str(value).strip() for value in raw_names]
    else:
        names = []
    names = [name[:80] for name in names if name][:1000]
    return {'dataset_path': dataset_path, 'class_names': names, 'class_count': len(names)}


def read_class_metrics(sftp, experiment_dir):
    metrics_path = posixpath.join(experiment_dir, 'class_metrics.json')
    try:
        stat = sftp.stat(metrics_path)
        if stat.st_size > 5 * 1024 * 1024:
            raise ValueError
        with sftp.open(metrics_path, 'rb') as remote_file:
            value = json.loads(remote_file.read().decode('utf-8-sig'))
        rows = value.get('class_metrics', []) if isinstance(value, dict) else value
        rows = [row for row in rows if isinstance(row, dict)][:1000] if isinstance(rows, list) else []
        return {'class_metrics_path': metrics_path, 'class_metrics_size': stat.st_size,
                'class_metrics_count': len(rows), 'has_class_metrics': bool(rows),
                'class_metrics': rows}
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {'class_metrics_path': '', 'class_metrics_size': 0,
                'class_metrics_count': 0, 'has_class_metrics': False,
                'class_metrics': []}


def download_candidate(server, remote_path, local_path):
    remote_path = validated_model_path(server, remote_path)
    if not remote_path:
        raise ValueError('远程模型路径不在允许的 best.pt 目录中')
    results_path = posixpath.join(posixpath.dirname(posixpath.dirname(remote_path)), 'results.csv')
    with ssh_connection(server) as client:
        sftp = client.open_sftp()
        try:
            model_stat = sftp.stat(remote_path)
            sftp.get(remote_path, local_path)
            results = None
            try:
                with sftp.open(results_path, 'rb') as remote_file:
                    results = remote_file.read()
            except OSError:
                pass
            experiment_dir = posixpath.dirname(posixpath.dirname(remote_path))
            return {
                'size': model_stat.st_size, 'results': results,
                'results_path': results_path if results else '',
                **read_category_info(sftp, server, experiment_dir),
                **read_class_metrics(sftp, experiment_dir)
            }
        finally:
            sftp.close()


def launch_class_metrics_generation(server, dataset_path=''):
    dataset_path = validated_dataset_path(server, dataset_path)
    if dataset_path is None:
        raise ValueError('验证数据集必须是远程数据目录中的 YAML 文件')
    local_script = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'scripts', 'generate_remote_class_metrics.py'))
    remote_script = '/tmp/geoview_generate_remote_class_metrics.py'
    output_root = posixpath.join(server['root'], 'output')
    log_path = posixpath.join(output_root, 'class_metrics_generation.log')
    pid_path = posixpath.join(output_root, 'class_metrics_generation.pid')
    with ssh_connection(server) as client:
        sftp = client.open_sftp()
        try:
            sftp.put(local_script, remote_script)
        finally:
            sftp.close()
        arguments = [server['python'], remote_script, '--output-root', output_root]
        if dataset_path:
            arguments.extend(['--data', dataset_path])
        run_command = 'exec env PYTHONPATH={} {}'.format(
            shlex.quote(server['yolo_root']), ' '.join(shlex.quote(value) for value in arguments))
        wrapper = 'echo $$ > {}; {}'.format(shlex.quote(pid_path), run_command)
        command = 'cd {} && rm -f {}; nohup sh -c {} > {} 2>&1 < /dev/null & '
        command += 'for i in 1 2 3 4 5; do test -s {} && break; sleep 1; done; cat {}'
        command = command.format(
            shlex.quote(server['yolo_root']), shlex.quote(pid_path), shlex.quote(wrapper),
            shlex.quote(log_path), shlex.quote(pid_path), shlex.quote(pid_path))
        _, stdout, stderr = client.exec_command(command, timeout=10)
        pid = stdout.read().decode('utf-8', errors='replace').strip()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        if not pid.isdigit():
            raise RuntimeError(error or '无法启动远程验证任务')
        return {'pid': int(pid), 'log_path': log_path, 'dataset_path': dataset_path}


def class_metrics_generation_status(server):
    output_root = posixpath.join(server['root'], 'output')
    status_path = posixpath.join(output_root, 'class_metrics_generation_status.json')
    log_path = posixpath.join(output_root, 'class_metrics_generation.log')
    pid_path = posixpath.join(output_root, 'class_metrics_generation.pid')
    command = "pid=$(cat {} 2>/dev/null || true); state=$(ps -p \"$pid\" -o stat= 2>/dev/null || true); if [ -n \"$state\" ] && ! echo \"$state\" | grep -q Z; then echo running:$pid; else echo stopped:$pid; fi".format(
        shlex.quote(pid_path))
    with ssh_connection(server) as client:
        _, stdout, _ = client.exec_command(command, timeout=8)
        state = stdout.read().decode('utf-8', errors='replace').strip()
        sftp = client.open_sftp()
        try:
            status = {}
            try:
                with sftp.open(status_path, 'rb') as remote_file:
                    status = json.loads(remote_file.read().decode('utf-8-sig'))
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
            log_tail = ''
            try:
                stat = sftp.stat(log_path)
                with sftp.open(log_path, 'rb') as remote_file:
                    remote_file.seek(max(0, stat.st_size - 6000))
                    log_tail = remote_file.read().decode('utf-8', errors='replace')[-6000:]
            except OSError:
                pass
        finally:
            sftp.close()
    running = state.startswith('running:')
    interrupted = bool(status.get('total')) and not running and not status.get('finished', False)
    return {'running': running, 'interrupted': interrupted, 'pid': state.partition(':')[2],
            'status': status, 'log_tail': log_tail}
