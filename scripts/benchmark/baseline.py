"""隔离配置下逐接口采集 FP16 检测基线；默认只做一张图冒烟验证。"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--backend', choices=['pytorch', 'tensorrt'], default='pytorch')
    parser.add_argument('--engine-root', default='')
    parser.add_argument('--endpoint', choices=['/AE/SyncTasks2', '/ImageDetect/student/v1.0.0', '/ImageDetect/teacher/v1.0.0'], help='仅采集指定接口，独立进程隔离 predictor 状态')
    parser.add_argument('--limit', type=int, default=1, help='每接口图片数，0 为全部')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    args.output.mkdir(parents=True, exist_ok=False)
    gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    import re
    config = (root / 'config.toml').read_text()
    config = re.sub(r'^GPU_ID\s*=.*$', f'GPU_ID = "{gpu}"\nInferenceHalf = true', config, flags=re.M)
    config = 'InferenceBackend = '+json.dumps(args.backend)+'\nEngineRoot = '+json.dumps(args.engine_root)+'\n'+config
    config = config.replace('VbasExposeLegacySyncTasks = false', 'VbasExposeLegacySyncTasks = true')
    config = re.sub(r'^VisionOrchestratorBaseUrl\s*=.*$', 'VisionOrchestratorBaseUrl = ""', config, flags=re.M)
    config_path = args.output / 'config.toml'
    config_path.write_text(config)
    os.environ['CONFIG_PATH'] = str(config_path)

    import cv2
    import torch
    from fastapi.testclient import TestClient
    from core import settings as cfg
    from main import app
    assert torch.cuda.is_available() and cfg.use_half
    assert '3090' in torch.cuda.get_device_name(0)
    models = {name: getattr(cfg, name) for name in [
        'yolo_person_model', 'yolo_face_model', 'yolo_student_model', 'yolo_teacher_behavior_model']}
    captured = []
    # Ultralytics 同一模型内部已串行化；本采集器顺序调用接口，记录返回预测而非修改预测。
    for name, model in models.items():
        original = model.predict
        def wrap(*a, _name=name, _model=model, _predict=original, **kw):
            results = _predict(*a, **kw)
            for result in results:
                captured.append({
                    'model': _name, 'names': result.names,
                    'boxes_xyxy_conf_cls': result.boxes.data.cpu().tolist(),
                    'coordinate_space': 'input_image_pixels_after_nms_before_business_filter',
                    'original_shape': result.orig_shape, 'speed_ms': result.speed,
                    'predict_args': {k: v for k, v in kw.items() if k != 'source'},
                    'weight_dtype': str(next(_model.model.parameters()).dtype) if args.backend == 'pytorch' else 'not_applicable_engine',
                    'runtime_fp16': bool(_model.predictor.model.fp16),
                })
            return results
        model.predict = wrap
    import importlib.metadata as metadata
    manifest = {
        'mode': 'sequential_in_process_api_baseline_not_http_load_test',
        'source_git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_git_tracked_changes': subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root, text=True).splitlines(),
        'backend': args.backend, 'engine_root': args.engine_root, 'endpoint_filter': args.endpoint,
        'gpu_uuid': gpu, 'device': torch.cuda.get_device_name(0),
        'torch_cuda_runtime': torch.version.cuda,
        'versions': {p: metadata.version(p) for p in ['torch', 'torchvision', 'ultralytics']},
        'model_sha256': {p.name: digest(p) for p in (root / 'models').glob('*.pt')},
        'config_sha256': digest(config_path),
    }
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    endpoints = [('/AE/SyncTasks2', 'student_test_img'),
                 ('/ImageDetect/student/v1.0.0', 'student_test_img'),
                 ('/ImageDetect/teacher/v1.0.0', 'teacher_test_img')]
    failures = 0
    with TestClient(app) as client, (args.output / 'predictions.jsonl').open('w') as out:
        for endpoint, folder in endpoints:
            if args.endpoint and endpoint != args.endpoint:
                continue
            files = sorted((root / 'tests' / folder).rglob('*.jpg'))
            if args.limit:
                files = files[:args.limit]
            if not files:
                raise RuntimeError(f'No images: {folder}')
            for image in files:
                captured.clear()
                raw = image.read_bytes()
                decoded = cv2.imdecode(__import__('numpy').frombuffer(raw, dtype='uint8'), cv2.IMREAD_COLOR)
                if decoded is None:
                    raise RuntimeError(f'Invalid image: {image}')
                h, w = decoded.shape[:2]
                image_id = image.relative_to(root / 'tests').as_posix()
                data = base64.b64encode(raw).decode()
                payload = {'ImageList': [{'StoragePath': data, 'ImageId': image_id}]}
                if endpoint == '/AE/SyncTasks2':
                    payload = {'TaskID': image_id, 'ImageList': [{'ImageID': image_id, 'Data': data}],
                               'AnalysisRule': {'AlgParams': {'ImageFormat': 1,
                                'ImageResolution': {'ImageWidth': w, 'ImageHeight': h},
                                'PolygonList': [{'Enable': True, 'Label': 'full_image', 'Points': [
                                    {'X': 0, 'Y': 0}, {'X': w-1, 'Y': 0},
                                    {'X': w-1, 'Y': h-1}, {'X': 0, 'Y': h-1}]}]}}}
                started = time.perf_counter()
                response = client.post(endpoint, json=payload)
                record = {'endpoint': endpoint, 'image_id': image_id,
                          'image_sha256': hashlib.sha256(raw).hexdigest(), 'shape': [h, w],
                          'request': {**{k: v for k, v in payload.items() if k != 'ImageList'},
                                      'ImageList': [{k: v for k, v in item.items() if k not in {'StoragePath', 'Data'}} for item in payload['ImageList']]},
                          'status': response.status_code, 'elapsed_ms': (time.perf_counter()-started)*1000,
                          'predictions': list(captured), 'response': response.json()}
                body = record['response']
                if endpoint.startswith('/ImageDetect/'):
                    record['valid_business'] = len(body.get('DataList', [])) == 1 and body['DataList'][0].get('StatusObject', {}).get('StatusCode') == 0
                else:
                    record['valid_business'] = body.get('Response', {}).get('ErrCode') == 0 and len(body.get('TaskResult', [])) == 1
                out.write(json.dumps(record, ensure_ascii=False) + '\n')
                out.flush()
                if response.status_code != 200 or not captured or not record['valid_business']:
                    failures += 1
                if any(not p['runtime_fp16'] for p in captured):
                    raise RuntimeError('FP16 verification failed')
    print(json.dumps({'output': str(args.output), 'failed_requests': failures}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
