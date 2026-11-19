"""TensorRT-only runtime; CUDA binding is established before GPU imports."""
import os
from pathlib import Path
from threading import RLock
from .engine_artifacts import MODEL_SPECS, validate_bundle

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_engine_root(value):
    path = Path(value).expanduser() if value else PROJECT_ROOT / 'model'
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def configure_device(gpu_id, environ=None):
    environ = os.environ if environ is None else environ
    configured = str(gpu_id)
    if configured.lower() == 'cpu':
        raise ValueError('TensorRT requires CUDA; CPU fallback is disabled')
    if 'CUDA_VISIBLE_DEVICES' in environ:
        visible = environ['CUDA_VISIBLE_DEVICES']
        if not visible or visible == '-1' or ',' in visible:
            raise ValueError('TensorRT requires exactly one visible CUDA device')
        if configured.startswith('GPU-') and configured != visible:
            raise ValueError('GPU_ID conflicts with CUDA_VISIBLE_DEVICES')
    else:
        environ['CUDA_VISIBLE_DEVICES'] = configured


def isolate_predictions(model, shape):
    """Protect YOLO's mutable predictor args across interfaces and warmup."""
    original = model.predict
    lock = RLock()

    def predict(*args, **kwargs):
        if kwargs.get('stream'):
            raise ValueError('Streaming prediction is unsupported by the synchronous service')
        kwargs.setdefault('agnostic_nms', False)
        kwargs['imgsz'] = tuple(shape[2:])
        kwargs['half'] = True
        with lock:
            return original(*args, **kwargs)

    model.predict = predict
    return model


def load_models(settings, resolver):
    try:
        return _load_models(settings, resolver)
    except BaseException:
        # Keeping plaintext after a successful load must never keep a failed release.
        resolver.cleanup()
        raise


def _load_models(settings, resolver):
    if settings.InferenceBackend != 'tensorrt' or not settings.InferenceHalf:
        raise ValueError('This service requires InferenceBackend=tensorrt and InferenceHalf=true; use the old release for PyTorch')
    root = resolve_engine_root(settings.EngineRoot)
    paths = {name: resolver.prepare_model_path(root / f'{name}.engine') for name in MODEL_SPECS}
    manifest = validate_bundle(root, prepared_paths=paths)
    import platform
    import numpy as np
    import tensorrt as trt
    import torch
    import ultralytics
    from ultralytics import YOLO
    if not torch.cuda.is_available():
        raise ValueError('TensorRT requires available CUDA; no CPU fallback')
    actual = {'os': platform.system(), 'machine': platform.machine(), 'tensorrt': trt.__version__,
        'torch': torch.__version__, 'ultralytics': ultralytics.__version__, 'cuda': torch.version.cuda,
        'gpu_name': torch.cuda.get_device_name(0), 'compute_capability': list(torch.cuda.get_device_capability(0))}
    for key, value in actual.items():
        if manifest['environment'][key] != value:
            raise ValueError(f'Incompatible runtime {key}: {value!r}; rebuild or validate the target environment')
    models = {}
    for name, spec in MODEL_SPECS.items():
        model = isolate_predictions(YOLO(str(paths[name]), task='detect'), spec['shape'])
        height, width = spec['shape'][2:]
        model.predict(np.zeros((height, width, 3), dtype=np.uint8), device=0, verbose=False)
        backend = model.predictor.model
        if not backend.engine or not backend.fp16:
            raise ValueError(f'{name}: actual TensorRT FP16 backend required')
        engine = backend.model
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
        models[name] = model
    return models
