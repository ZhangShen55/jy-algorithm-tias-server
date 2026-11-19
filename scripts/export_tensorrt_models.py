"""Offline four-model FP16 export, or copy an already validated release. Never run at service startup."""
import argparse
import ast
import functools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from core.engine_artifacts import MODEL_SPECS, copy_bundle, sha256, validate_bundle


def export_models(source_root, output, device_uuid):
    source_root, output = Path(source_root).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    for name in MODEL_SPECS:
        if not (source_root / f'{name}.pt').is_file():
            raise ValueError(f'{name}: source PT file missing')
    if not device_uuid.startswith('GPU-'):
        raise ValueError('An explicit GPU UUID is required')
    os.environ['CUDA_VISIBLE_DEVICES'] = device_uuid
    import onnx
    import tensorrt as trt
    import torch
    import ultralytics
    from ultralytics import YOLO
    if not torch.cuda.is_available():
        raise ValueError('CUDA unavailable; no CPU export fallback')
    output.mkdir(parents=True, exist_ok=False)
    torch.onnx.export = functools.partial(torch.onnx.export, dynamo=False)
    environment = {'os': platform.system(), 'machine': platform.machine(),
        'torch': torch.__version__, 'tensorrt': trt.__version__, 'onnx': onnx.__version__,
        'ultralytics': ultralytics.__version__, 'cuda': torch.version.cuda,
        'gpu_name': torch.cuda.get_device_name(0), 'compute_capability': list(torch.cuda.get_device_capability(0)),
        'gpu_uuid': device_uuid, 'code_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT_ROOT,text=True).strip(),
        'driver': subprocess.check_output(['nvidia-smi','-i',device_uuid,'--query-gpu=driver_version','--format=csv,noheader'],text=True).strip(),
        'tracked_diff': subprocess.check_output(['git','diff','HEAD'],cwd=PROJECT_ROOT,text=True)}
    manifest = {'schema_version': 1, 'release_id': output.name, 'environment': environment, 'models': {}}
    logger = trt.Logger(trt.Logger.INFO)
    for name, spec in MODEL_SPECS.items():
        work = output / 'build' / name
        work.mkdir(parents=True)
        source = source_root / f'{name}.pt'
        pt = work / source.name
        shutil.copy2(source, pt)
        onnx_path = Path(YOLO(str(pt)).export(format='onnx', imgsz=spec['shape'][2:], batch=1,
            half=False, device=0, dynamic=False, simplify=False, opset=17))
        graph = onnx.load(str(onnx_path))
        metadata = {}
        for item in graph.metadata_props:
            try:
                metadata[item.key] = ast.literal_eval(item.value)
            except (ValueError, SyntaxError):
                metadata[item.key] = item.value
        builder = trt.Builder(logger)
        network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
        parser = trt.OnnxParser(network, logger)
        if not parser.parse(onnx_path.read_bytes()):
            raise ValueError(f'{name}: ONNX parse failure: '+str([str(parser.get_error(i)) for i in range(parser.num_errors)]))
        if not builder.platform_has_fast_fp16:
            raise ValueError('Fast FP16 is unavailable')
        for i in range(network.num_inputs): network.get_input(i).dtype = trt.float16
        for i in range(network.num_outputs): network.get_output(i).dtype = trt.float16
        config = builder.create_builder_config()
        config.set_flag(trt.BuilderFlag.FP16)
        config.clear_flag(trt.BuilderFlag.TF32)
        config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 4 << 30)
        config.profiling_verbosity = trt.ProfilingVerbosity.DETAILED
        serialized = builder.build_serialized_network(network, config)
        if serialized is None:
            raise ValueError(f'{name}: Engine build failed')
        engine_path = output / f'{name}.engine'
        header = json.dumps(metadata).encode()
        engine_path.write_bytes(len(header).to_bytes(4, 'little') + header + bytes(serialized))
        runtime = trt.Runtime(logger)
        engine = runtime.deserialize_cuda_engine(serialized)
        if engine is None: raise ValueError(f'{name}: Engine verification failed')
        tensors = []
        for i in range(engine.num_io_tensors):
            tensor_name = engine.get_tensor_name(i)
            if engine.get_tensor_dtype(tensor_name) != trt.float16:
                raise ValueError(f'{name}: Non-HALF actual I/O')
            tensors.append({'name': tensor_name, 'dtype': 'float16',
                'shape': list(engine.get_tensor_shape(tensor_name)),
                'mode': 'INPUT' if engine.get_tensor_mode(tensor_name) == trt.TensorIOMode.INPUT else 'OUTPUT'})
        inspector = engine.create_engine_inspector()
        (work / 'layers.json').write_text(inspector.get_engine_information(trt.LayerInformationFormat.JSON))
        manifest['models'][name] = {'file': engine_path.name, 'engine_sha256': sha256(engine_path),
            'source_sha256': sha256(source), 'onnx_sha256': sha256(onnx_path),
            'shape': spec['shape'], 'names': spec['names'], 'precision': 'fp16',
            'tf32_enabled': False, 'io_tensors': tensors}
        (work / 'build-record.json').write_text(json.dumps(manifest['models'][name],indent=2))
        del inspector, engine, runtime, serialized, config, parser, network, builder
    # Only a complete validated release receives manifest.json.
    staging = output / 'manifest.pending'
    staging.write_text(json.dumps(manifest, indent=2))
    staging.rename(output / 'manifest.json')
    try:
        validate_bundle(output)
    except BaseException:
        (output / 'manifest.json').rename(output / 'manifest.failed')
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--source-root', type=Path)
    source.add_argument('--reuse-root', type=Path, help='Copy a release already using manifest schema 1')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--device', help='GPU UUID, required for offline construction')
    args = parser.parse_args()
    try:
        if args.reuse_root:
            manifest = copy_bundle(args.reuse_root, args.output)
        else:
            if not args.device: parser.error('--source-root requires --device GPU-UUID')
            manifest = export_models(args.source_root, args.output, args.device)
        print(json.dumps({'release_id': manifest['release_id'], 'models': list(manifest['models']), 'output': str(args.output)}))
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        print(f'Engine export failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
