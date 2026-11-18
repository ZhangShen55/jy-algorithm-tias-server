"""在独立环境/指定 GPU 构建本测试集实际 shape 的 FP16 引擎，不覆盖源模型。"""
import argparse
import ast
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
    # ONNX 是中间图；正式推理精度由后续 engine 的 I/O 和构建设置明确约束。
    onnx_path = YOLO(str(target)).export(format='onnx', imgsz=shape, batch=1, half=False,
                                        device=0, dynamic=False, simplify=False, opset=17)
    graph = onnx.load(str(onnx_path))
    metadata = {}
    for item in graph.metadata_props:
        try:
            metadata[item.key] = ast.literal_eval(item.value)
        except (ValueError, SyntaxError):
            metadata[item.key] = item.value
    logger = tensorrt.Logger(tensorrt.Logger.INFO)
    builder = tensorrt.Builder(logger)
    network = builder.create_network(1 << int(tensorrt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser_onnx = tensorrt.OnnxParser(network, logger)
    if not parser_onnx.parse(Path(onnx_path).read_bytes()):
        raise RuntimeError('\n'.join(str(parser_onnx.get_error(i)) for i in range(parser_onnx.num_errors)))
    if not builder.platform_has_fast_fp16:
        raise RuntimeError('Fast FP16 unavailable')
    for i in range(network.num_inputs):
        network.get_input(i).dtype = tensorrt.float16
    for i in range(network.num_outputs):
        network.get_output(i).dtype = tensorrt.float16
    config = builder.create_builder_config()
    config.set_flag(tensorrt.BuilderFlag.FP16)
    config.clear_flag(tensorrt.BuilderFlag.TF32)
    config.set_memory_pool_limit(tensorrt.MemoryPoolType.WORKSPACE, 4 << 30)
    config.profiling_verbosity = tensorrt.ProfilingVerbosity.DETAILED
    cache_path = args.output.parent/'timing-cache.bin'
    cache_bytes = cache_path.read_bytes() if cache_path.exists() else b''
    config.set_timing_cache(config.create_timing_cache(cache_bytes), False)
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError('TensorRT engine build failed')
    cache_path.write_bytes(bytes(config.get_timing_cache().serialize()))
    engine = target.with_suffix('.engine')
    header = json.dumps(metadata).encode()
    engine.write_bytes(len(header).to_bytes(4, 'little')+header+bytes(serialized))
    runtime = tensorrt.Runtime(logger)
    loaded = runtime.deserialize_cuda_engine(serialized)
    if loaded is None:
        raise RuntimeError('Engine deserialization failed')
    tensors = []
    for i in range(loaded.num_io_tensors):
        name = loaded.get_tensor_name(i)
        dtype = loaded.get_tensor_dtype(name)
        if dtype != tensorrt.float16:
            raise RuntimeError(f'Non-FP16 I/O: {name} {dtype}')
        tensors.append({'name': name, 'dtype': str(dtype), 'shape': list(loaded.get_tensor_shape(name))})
    inspector = loaded.create_engine_inspector()
    (args.output/'layers.json').write_text(inspector.get_engine_information(tensorrt.LayerInformationFormat.JSON))
    manifest = {'model': args.model, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'engine_sha256': hashlib.sha256(Path(engine).read_bytes()).hexdigest(),
                'shape': [1, 3, *shape], 'precision_requested': 'fp16', 'dynamic': False,
                'torch': torch.__version__, 'tensorrt': tensorrt.__version__, 'onnx': onnx.__version__,
                'gpu_uuid': gpu, 'exporter': 'legacy_torch_onnx_dynamo_false',
                'io_tensors': tensors, 'tf32_enabled': False,
                'timing_cache_input_sha256': hashlib.sha256(cache_bytes).hexdigest(),
                'timing_cache_output_sha256': hashlib.sha256(cache_path.read_bytes()).hexdigest(),
                'scope': 'dataset_shapes_only_not_general_deployment_acceptance'}
    (args.output/'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
