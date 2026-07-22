"""Generate class_metrics.json once for every Ultralytics best.pt missing it."""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime

import yaml
from ultralytics import YOLO


def read_yaml(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            value = yaml.safe_load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def already_generated(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            value = json.load(file)
        rows = value.get('class_metrics', []) if isinstance(value, dict) else value
        return isinstance(rows, list) and bool(rows)
    except (OSError, ValueError):
        return False


def normalize_summary(metrics):
    if hasattr(metrics, 'summary'):
        raw_rows = metrics.summary()
        if raw_rows:
            return [{
                'class': row.get('Class', row.get('class', '')),
                'images': row.get('Images', row.get('images')),
                'instances': row.get('Instances', row.get('instances', 0)),
                'ap50': row.get('mAP50', row.get('ap50')),
                'ap5095': row.get('mAP50-95', row.get('ap5095')),
                'precision': row.get('Box-P', row.get('precision')),
                'recall': row.get('Box-R', row.get('recall')),
                'f1': row.get('Box-F1', row.get('f1'))
            } for row in raw_rows]
    box = metrics.box
    indices = list(getattr(box, 'ap_class_index', []))
    names = getattr(metrics, 'names', {})
    images = getattr(metrics, 'nt_per_image', [])
    instances = getattr(metrics, 'nt_per_class', [])
    rows = []
    for offset, class_id in enumerate(indices):
        precision, recall, ap50, ap5095 = box.class_result(offset)
        denominator = precision + recall
        rows.append({
            'class': names.get(int(class_id), str(class_id)) if isinstance(names, dict) else names[int(class_id)],
            'images': int(images[int(class_id)]) if len(images) > int(class_id) else None,
            'instances': int(instances[int(class_id)]) if len(instances) > int(class_id) else 0,
            'ap50': float(ap50), 'ap5095': float(ap5095),
            'precision': float(precision), 'recall': float(recall),
            'f1': float(2 * precision * recall / denominator) if denominator else 0.0
        })
    return rows


def generate(model_path, override_data='', device='auto'):
    experiment = model_path.parent.parent
    output = experiment / 'class_metrics.json'
    if already_generated(output):
        return 'skipped', str(output)
    arguments = read_yaml(experiment / 'args.yaml')
    dataset = override_data or str(arguments.get('data', '')).strip()
    if not dataset or not Path(dataset).is_file():
        raise RuntimeError('找不到验证数据集：{}'.format(dataset or 'args.yaml 未配置 data'))
    image_size = arguments.get('imgsz', 640)
    if isinstance(image_size, list):
        image_size = max(image_size)
    cpu_mode = str(device).lower() == 'cpu'
    metrics = YOLO(str(model_path)).val(
        data=dataset, split='val', imgsz=int(image_size), batch=1 if cpu_mode else 8,
        device=device, workers=2 if cpu_mode else 4, plots=False, save_json=False,
        project=str(experiment), name='geoview_class_validation', exist_ok=True,
        verbose=True
    )
    rows = normalize_summary(metrics)
    if not rows:
        raise RuntimeError('验证完成，但没有生成逐类别指标')
    payload = {'model_path': str(model_path), 'dataset_path': dataset, 'class_metrics': rows}
    temporary = output.with_suffix('.json.part')
    with open(temporary, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2,
                  default=lambda value: value.item() if hasattr(value, 'item') else str(value))
    os.replace(temporary, output)
    return 'generated', str(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', default='/root/autodl-tmp/output')
    parser.add_argument('--data', default='', help='覆盖所有模型 args.yaml 记录的数据集')
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model', default='', help='仅验证指定 best.pt')
    options = parser.parse_args()
    if options.device == 'auto':
        import torch
        options.device = '0' if torch.cuda.is_available() else 'cpu'
    models = [Path(options.model)] if options.model else sorted(Path(options.output_root).glob('*/weights/best.pt'))
    status_path = Path(options.output_root) / 'class_metrics_generation_status.json'
    status = {'total': len(models), 'completed': 0, 'failed': [], 'models': [],
              'finished': False, 'device': options.device,
              'started_at': datetime.now().isoformat(timespec='seconds')}
    with open(status_path, 'w', encoding='utf-8') as file:
        json.dump(status, file, ensure_ascii=False, indent=2)
    for model_path in models:
        try:
            state, output = generate(model_path, options.data, options.device)
            status['models'].append({'model': str(model_path), 'status': state, 'output': output})
        except Exception as error:
            status['failed'].append({'model': str(model_path), 'error': str(error)})
        status['completed'] += 1
        with open(status_path, 'w', encoding='utf-8') as file:
            json.dump(status, file, ensure_ascii=False, indent=2)
    status['finished'] = True
    status['finished_at'] = datetime.now().isoformat(timespec='seconds')
    with open(status_path, 'w', encoding='utf-8') as file:
        json.dump(status, file, ensure_ascii=False, indent=2)
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
