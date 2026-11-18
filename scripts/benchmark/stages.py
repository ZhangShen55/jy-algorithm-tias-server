"""单进程诊断分段；强制同步仅用于诊断，不与 HTTP 容量数据混用。"""
import argparse
import base64
import collections
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time


def summarize(values):
    ordered = sorted(values)
    def q(f):
        x = (len(ordered)-1)*f
        i = int(x)
        return ordered[i]+(ordered[min(i+1, len(ordered)-1)]-ordered[i])*(x-i)
    return {'mean': statistics.mean(values), 'p50': q(.5), 'p95': q(.95), 'p99': q(.99)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--backend', choices=['pytorch', 'tensorrt'], required=True)
    parser.add_argument('--engine-root', default='')
    parser.add_argument('--runs', type=int, default=200)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('runs must be positive')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    config = (root/'config.toml').read_text()
    config = re.sub(r'^GPU_ID\s*=.*$', f'GPU_ID = "{gpu}"\nInferenceHalf = true', config, flags=re.M)
    config = 'InferenceBackend = '+json.dumps(args.backend)+'\nEngineRoot = '+json.dumps(args.engine_root)+'\n'+config
    config_path = args.output/'config.toml'
    config_path.write_text(config)
    os.environ['CONFIG_PATH'] = str(config_path)
    import cv2
    import numpy as np
    import torch
    from core import settings as cfg
    from services.student_behavior_service import get_student_behavior_predict_conf
    from services.teacher_behavior_service import get_teacher_behavior_predict_conf
    from services.task_service_base64 import mask_polygon
    from schemas.geometry import Point
    assert cfg.device.type == 'cuda' and cfg.use_half
    configurations = [('yolo_person_model', 'student', (1088, 1920), .1),
                      ('yolo_face_model', 'student', (1088, 1920), .1),
                      ('yolo_student_model', 'student', (1088, 1920), get_student_behavior_predict_conf()),
                      ('yolo_teacher_behavior_model', 'teacher', (384, 640), get_teacher_behavior_predict_conf())]
    prepared = []
    for name, group, shape, conf in configurations:
        path = sorted((root/'tests'/f'{group}_test_img').rglob('*.jpg'))[0]
        raw = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        model = getattr(cfg, name)
        model.predict(image, imgsz=shape, conf=conf, half=True, verbose=False)
        assert model.predictor.model.fp16
        prepared.append((name, model.predictor, image, raw))
    start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    def cpu(fn):
        before = time.perf_counter_ns()
        value = fn()
        return value, (time.perf_counter_ns()-before)/1e6
    def device(fn):
        torch.cuda.synchronize()
        before = time.perf_counter_ns()
        start.record()
        value = fn()
        end.record()
        end.synchronize()
        return value, (time.perf_counter_ns()-before)/1e6, start.elapsed_time(end)
    summary = {'backend': args.backend, 'runs': args.runs, 'models': {},
               'scope': 'isolated_synchronized_diagnostic_not_http_or_concurrent_capacity',
               'device_time': 'CUDA event span includes host launch gaps; not summed kernel time',
               'h2d': 'pageable_uint8_as_current_preprocess', 'all_models_warmed_in_one_process': True}
    with torch.inference_mode(), (args.output/'samples.jsonl').open('w') as stream:
        for name, predictor, image, raw in prepared:
            encoded = base64.b64encode(raw).decode()
            h, w = image.shape[:2]
            polygon = [Point(X=0,Y=0), Point(X=w-1,Y=0), Point(X=w-1,Y=h-1), Point(X=0,Y=h-1)]
            stages = collections.defaultdict(list)
            for iteration in range(args.runs):
                row = {'model': name, 'iteration': iteration}
                _, row['base64_decode_cpu_ms'] = cpu(lambda: base64.b64decode(encoded))
                _, row['jpeg_decode_cpu_ms'] = cpu(lambda: cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR))
                _, row['full_frame_roi_cpu_ms'] = cpu(lambda: mask_polygon(image, polygon))
                transformed, row['resize_letterbox_cpu_ms'] = cpu(lambda: predictor.pre_transform([image]))
                array, row['rgb_chw_contiguous_cpu_ms'] = cpu(lambda: np.ascontiguousarray(np.stack(transformed)[..., ::-1].transpose((0,3,1,2))))
                host = torch.from_numpy(array)
                tensor, row['h2d_wall_ms'], row['h2d_device_span_ms'] = device(lambda: host.to(cfg.device))
                tensor, row['normalize_wall_ms'], row['normalize_device_span_ms'] = device(lambda: tensor.half().div_(255))
                if iteration == 0:
                    assert torch.equal(tensor, predictor.preprocess([image])), 'Instrumented preprocessing differs'
                    row['actual_input_shape'] = list(tensor.shape)
                    row['actual_input_dtype'] = str(tensor.dtype)
                prediction, row['forward_wall_ms'], row['forward_device_span_ms'] = device(lambda: predictor.inference(tensor))
                results, row['nms_scale_wrap_wall_ms'], row['nms_scale_wrap_device_span_ms'] = device(lambda: predictor.postprocess(prediction, tensor, [image]))
                boxes, row['d2h_wall_ms'], row['d2h_device_span_ms'] = device(lambda: results[0].boxes.data.cpu())
                _, row['tolist_cpu_ms'] = cpu(boxes.tolist)
                for key, value in row.items():
                    if key.endswith('_ms'):
                        stages[key].append(value)
                stream.write(json.dumps(row)+'\n')
                del prediction, results, tensor, boxes
            summary['models'][name] = {key: summarize(values) for key, values in stages.items()}
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
