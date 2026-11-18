"""在独立环境/指定 GPU 构建本测试集实际 shape 的 FP16 引擎，不覆盖源模型。"""
import argparse
import functools
import hashlib
import json
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['person_count', 'face_count', 'student', 'teacher_behavior'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    import torch
    import tensorrt
    import onnx
    from ultralytics import YOLO
    if not torch.cuda.is_available() or '3090' not in torch.cuda.get_device_name(0):
        raise RuntimeError('Required RTX 3090 unavailable')
    # 固定旧版 Ultralytics 预期的 legacy 导出路径；仅影响本构建子进程。
    torch.onnx.export = functools.partial(torch.onnx.export, dynamo=False)
    root = Path(__file__).resolve().parents[2]
    args.output.mkdir(parents=True, exist_ok=False)
    source = root/'models'/f'{args.model}.pt'
    target = args.output/source.name
    shutil.copy2(source, target)
    shape = (384, 640) if args.model == 'teacher_behavior' else (1088, 1920)
    engine = YOLO(str(target)).export(format='engine', imgsz=shape, batch=1, half=True,
                                     device=0, dynamic=False, simplify=False, opset=17, workspace=4)
    manifest = {'model': args.model, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'engine_sha256': hashlib.sha256(Path(engine).read_bytes()).hexdigest(),
                'shape': [1, 3, *shape], 'precision_requested': 'fp16', 'dynamic': False,
                'torch': torch.__version__, 'tensorrt': tensorrt.__version__, 'onnx': onnx.__version__,
                'gpu_uuid': gpu, 'exporter': 'legacy_torch_onnx_dynamo_false',
                'scope': 'dataset_shapes_only_not_general_deployment_acceptance'}
    (args.output/'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
