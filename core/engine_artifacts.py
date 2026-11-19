"""TensorRT asset contract. Static validation requires only the standard library."""
import hashlib
import json
from pathlib import Path
import re
import shutil

MODEL_SPECS = {
    'person_count': {'shape': [1, 3, 1088, 1920], 'names': ['Head', 'Top_Head', 'Hat', 'Headphones', 'Shoulder', 'Other']},
    'face_count': {'shape': [1, 3, 1088, 1920], 'names': ['face']},
    'student': {'shape': [1, 3, 1088, 1920], 'names': ['Using_phone', 'Hand_raising', 'Sleep', 'standing', 'Read_W']},
    'teacher_behavior': {'shape': [1, 3, 384, 640], 'names': ['sit', 'stand', 'bbwriting', 'teach']},
}
ENVIRONMENT_FIELDS = ('os', 'machine', 'tensorrt', 'cuda', 'driver', 'torch', 'ultralytics',
                      'gpu_name', 'compute_capability', 'gpu_uuid', 'code_commit')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_engine_metadata(path):
    """Read Ultralytics' little-endian JSON length header, without importing CUDA."""
    path = Path(path)
    with path.open('rb') as stream:
        prefix = stream.read(4)
        size = int.from_bytes(prefix, 'little')
        if len(prefix) != 4 or not 0 < size <= 1 << 20 or path.stat().st_size <= size + 4:
            raise ValueError(f'{path.name}: invalid Engine metadata header or empty plan')
        try:
            metadata = json.loads(stream.read(size).decode('utf-8'))
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f'{path.name}: invalid Engine metadata JSON') from exc
    if not isinstance(metadata, dict):
        raise ValueError(f'{path.name}: metadata must be an object')
    return metadata


def ordered_names(names):
    if isinstance(names, list) and all(isinstance(x, str) for x in names):
        return names
    if isinstance(names, dict) and set(names) == {str(i) for i in range(len(names))}:
        result = [names[str(i)] for i in range(len(names))]
        if all(isinstance(x, str) for x in result):
            return result
    raise ValueError('Invalid class name mapping')


def validate_bundle(root, prepared_paths=None):
    """Validate a complete plaintext release; this does not prove GPU compatibility."""
    root = Path(root).resolve()
    try:
        manifest = json.loads((root / 'manifest.json').read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f'{root}: missing or invalid manifest.json') from exc
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or not manifest.get('release_id'):
        raise ValueError('Unsupported manifest schema_version or missing release_id')
    env = manifest.get('environment', {})
    if not isinstance(env, dict) or any(not env.get(k) for k in ENVIRONMENT_FIELDS):
        raise ValueError('Missing build environment information')
    models = manifest.get('models')
    if not isinstance(models, dict) or set(models) != set(MODEL_SPECS):
        raise ValueError('Manifest requires exactly four models')
    for name, spec in MODEL_SPECS.items():
        row = models[name]
        if not isinstance(row, dict) or row.get('file') != f'{name}.engine':
            raise ValueError(f'{name}: invalid Engine filename')
        path = Path(prepared_paths[name]) if prepared_paths is not None else root / row['file']
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'{name}: missing Engine or symbolic link')
        for field in ('engine_sha256', 'source_sha256', 'onnx_sha256'):
            if not isinstance(row.get(field), str) or not re.fullmatch('[0-9a-f]{64}', row[field]):
                raise ValueError(f'{name}: invalid {field}')
        if sha256(path) != row['engine_sha256']:
            raise ValueError(f'{name}: Engine SHA mismatch')
        if row.get('shape') != spec['shape'] or row.get('names') != spec['names']:
            raise ValueError(f'{name}: shape or class names mismatch')
        if row.get('precision') != 'fp16' or row.get('tf32_enabled') is not False:
            raise ValueError(f'{name}: requires FP16, TF32 disabled')
        metadata = read_engine_metadata(path)
        if metadata.get('task') != 'detect' or ordered_names(metadata.get('names')) != spec['names']:
            raise ValueError(f'{name}: Engine class metadata mismatch')
        tensors = row.get('io_tensors', [])
        if (not isinstance(tensors, list) or len(tensors) < 2
                or any(not isinstance(t, dict) or t.get('dtype') != 'float16'
                       or not isinstance(t.get('shape'), list) or not t['shape']
                       or any(type(v) is not int or v <= 0 for v in t['shape'])
                       or not t.get('name') or t.get('mode') not in ('INPUT', 'OUTPUT') for t in tensors)):
            raise ValueError(f'{name}: invalid FP16 I/O declaration')
        inputs = [t for t in tensors if t['mode'] == 'INPUT']
        outputs = [t for t in tensors if t['mode'] == 'OUTPUT']
        if (len(inputs) != 1 or inputs[0]['shape'] != spec['shape'] or not outputs
                or len({t['name'] for t in tensors}) != len(tensors)):
            raise ValueError(f'{name}: inconsistent I/O declaration')
    return manifest


def copy_bundle(source, output):
    """Copy a validated immutable bundle; never overwrite an existing destination."""
    source, output = Path(source).resolve(), Path(output).absolute()
    manifest = validate_bundle(source)
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name in MODEL_SPECS:
            shutil.copy2(source / manifest['models'][name]['file'], output / manifest['models'][name]['file'])
        shutil.copy2(source / 'manifest.json', output / 'manifest.json')
        validate_bundle(output)
    except BaseException:
        # Only the destination we just created is ours to remove.
        shutil.rmtree(output)
        raise
    return manifest


def prepare_legacy_bundle(legacy_root, source_root, output, environment):
    """Upgrade verified benchmark assets without rebuilding or rewriting any Engine."""
    legacy_root, source_root, output = Path(legacy_root), Path(source_root), Path(output)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    manifest = {'schema_version': 1, 'release_id': output.name, 'environment': environment,
                'environment_attestation': 'verified target environment at reuse; original build records preserved per model',
                'models': {}}
    paths = {}
    for name, spec in MODEL_SPECS.items():
        child = legacy_root / name
        old = json.loads((child / 'build-manifest.json').read_text())
        engine, onnx, source = child / f'{name}.engine', child / f'{name}.onnx', source_root / f'{name}.pt'
        if sha256(source) != old.get('source_sha256') or sha256(engine) != old.get('engine_sha256'):
            raise ValueError(f'{name}: original source or Engine SHA mismatch')
        if old.get('precision_requested') != 'fp16' or old.get('tf32_enabled') is not False or old.get('shape') != spec['shape']:
            raise ValueError(f'{name}: original precision or shape mismatch')
        for key in ('torch', 'tensorrt'):
            if key in old and old[key] != environment.get(key):
                raise ValueError(f'{name}: original {key} version differs from target')
        io = []
        for tensor in old.get('io_tensors', []):
            if tensor.get('dtype') != 'DataType.HALF':
                raise ValueError(f'{name}: original I/O is not HALF')
            io.append({'name': tensor['name'], 'dtype': 'float16', 'shape': tensor['shape'],
                       'mode': 'INPUT' if tensor['name'] == 'images' else 'OUTPUT'})
        manifest['models'][name] = {'file': f'{name}.engine', 'engine_sha256': sha256(engine),
            'source_sha256': sha256(source), 'onnx_sha256': sha256(onnx), 'shape': spec['shape'],
            'names': ordered_names(read_engine_metadata(engine).get('names')), 'precision': 'fp16',
            'tf32_enabled': False, 'io_tensors': io, 'original_build_manifest': old}
        paths[name] = engine
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name, source in paths.items(): shutil.copy2(source, output / f'{name}.engine')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        validate_bundle(output)
    except BaseException:
        shutil.rmtree(output)
        raise
    return manifest
