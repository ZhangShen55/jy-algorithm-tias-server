"""Validate a private four-Engine release. GPU execution requires explicit --gpu."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from core.engine_artifacts import MODEL_SPECS, validate_bundle


def verify_gpu_bundle(root, device_uuid):
    if not device_uuid.startswith('GPU-'):
        raise ValueError('GPU diagnostic requires an explicit GPU UUID')
    manifest = validate_bundle(root)
    # No CUDA library is imported before binding the diagnostic process.
    os.environ['CUDA_VISIBLE_DEVICES'] = device_uuid
    import gc
    import numpy as np
    import tensorrt as trt
    import torch
    import ultralytics
    from ultralytics import YOLO
    if not torch.cuda.is_available():
        raise ValueError('CUDA unavailable; no CPU fallback')
    actual = {'os': platform.system(), 'machine': platform.machine(),
              'tensorrt': trt.__version__, 'torch': torch.__version__,
              'ultralytics': ultralytics.__version__, 'cuda': torch.version.cuda,
              'gpu_name': torch.cuda.get_device_name(0),
              'compute_capability': list(torch.cuda.get_device_capability(0))}
    for field, value in actual.items():
        if manifest['environment'][field] != value:
            raise ValueError(f'Incompatible {field}: expected {manifest["environment"][field]!r}, actual {value!r}')
    diagnostics = {}
    logger = trt.Logger(trt.Logger.ERROR)
    for name, spec in MODEL_SPECS.items():
        path = Path(root) / f'{name}.engine'
        with path.open('rb') as stream:
            size = int.from_bytes(stream.read(4), 'little')
            stream.seek(4 + size)
            plan = stream.read()
        with trt.Runtime(logger) as runtime:
            engine = runtime.deserialize_cuda_engine(plan)
            if engine is None:
                raise ValueError(f'{name}: Engine deserialization failed')
            tensors = []
            for i in range(engine.num_io_tensors):
                tensor_name = engine.get_tensor_name(i)
                if engine.get_tensor_dtype(tensor_name) != trt.float16:
                    raise ValueError(f'{name}: actual I/O must be HALF')
                tensors.append({'name': tensor_name, 'dtype': 'float16',
                                'shape': list(engine.get_tensor_shape(tensor_name)),
                                'mode': 'INPUT' if engine.get_tensor_mode(tensor_name) == trt.TensorIOMode.INPUT else 'OUTPUT'})
            if tensors != manifest['models'][name]['io_tensors']:
                raise ValueError(f'{name}: actual I/O differs from manifest')
            del engine
        model = YOLO(str(path), task='detect')
        height, width = spec['shape'][2:]
        model.predict(np.zeros((height, width, 3), dtype=np.uint8), imgsz=(height, width),
                      half=True, device=0, verbose=False)
        backend = model.predictor.model
        if not backend.engine or not backend.fp16:
            raise ValueError(f'{name}: warmup did not use TensorRT FP16')
        diagnostics[name] = {'backend': 'tensorrt', 'fp16': True, 'io_tensors': tensors, 'warmup': 'passed'}
        del backend, model, plan
        gc.collect()
    return {'actual_environment': actual, 'device_uuid': device_uuid, 'models': diagnostics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT / 'model')
    parser.add_argument('--gpu', action='store_true', help='Explicitly run real CUDA/Engine warmups')
    parser.add_argument('--device', help='Required GPU UUID for --gpu')
    args = parser.parse_args()
    try:
        manifest = validate_bundle(args.root)
        result = {'static_validation': 'passed', 'release_id': manifest['release_id'], 'gpu_validation': 'not_run'}
        if args.gpu:
            if not args.device:
                parser.error('--gpu requires --device GPU-UUID')
            result['gpu_validation'] = verify_gpu_bundle(args.root, args.device)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        print(f'Engine validation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
