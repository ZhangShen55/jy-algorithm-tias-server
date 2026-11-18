"""验证四个 engine 的加密加载、推理和成功/失败时明文清理，不输出密钥。"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from core.model_protection import generate_key, encrypt_model_file, AESGCM
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    secret_file = args.output/'temporary-test.key'
    secret = generate_key()
    fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(secret)
    encrypted = args.output/'encrypted'
    encrypted.mkdir(mode=0o700)
    summary = {'cipher': 'AESGCM' if AESGCM is not None else 'existing_fallback', 'checks': []}
    try:
        for model in ['person_count', 'face_count', 'student', 'teacher_behavior']:
            encrypt_model_file(args.engine_root/model/f'{model}.engine', encrypted/f'{model}.engine.enc', secret)
        for tampered in [False, True]:
            if tampered:
                path = encrypted/'teacher_behavior.engine.enc'
                data = bytearray(path.read_bytes())
                data[-1] ^= 1
                path.write_bytes(data)
            with tempfile.TemporaryDirectory(prefix='vbas-engine-check-', dir='/dev/shm') as folder:
                text = (root/'config.toml').read_text()
                gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
                text = re.sub(r'^GPU_ID\s*=.*$', f'GPU_ID = "{gpu}"\nInferenceHalf = true', text, flags=re.M)
                text = 'InferenceBackend = "tensorrt"\nEngineRoot = '+json.dumps(str(args.engine_root.resolve()))+'\n'+text
                prefix, protection = text.split('[ModelProtection]', 1)
                for key, value in {'Enabled': True, 'EncryptedModelRoot': str(encrypted),
                                   'DecryptedTempRoot': folder, 'KeyFile': str(secret_file),
                                   'CleanupAfterLoad': True}.items():
                    protection = re.sub(rf'^{key}\s*=.*$', f'{key} = {json.dumps(value)}', protection, flags=re.M)
                config = args.output/f'config-{tampered}.toml'
                config.write_text(prefix+'[ModelProtection]'+protection)
                command = "from core import settings as s; import cv2,pathlib; p=next(pathlib.Path('tests/teacher_test_img').rglob('*.jpg')); r=s.yolo_teacher_behavior_model.predict(cv2.imread(str(p)),verbose=False); assert r and r[0].boxes is not None; assert s.yolo_teacher_behavior_model.predictor.model.fp16; print('protected engine inference passed')"
                with (args.output/f'child-{tampered}.log').open('w') as log:
                    code = subprocess.run([sys.executable, '-c', command], cwd=root,
                                          env={**os.environ, 'CONFIG_PATH': str(config), 'CUDA_VISIBLE_DEVICES': gpu},
                                          stdout=log, stderr=subprocess.STDOUT).returncode
                leftovers = [p.name for p in Path(folder).rglob('*') if p.is_file()]
                log = (args.output/f'child-{tampered}.log').read_text(errors='replace')
                expected = code != 0 and '解密' in log if tampered else code == 0
                passed = expected and not leftovers
                summary['checks'].append({'tampered': tampered, 'returncode': code,
                                          'plaintext_leftovers': leftovers, 'passed': passed})
                if not passed:
                    raise RuntimeError('Protected engine lifecycle check failed; inspect child log')
    finally:
        secret_file.unlink(missing_ok=True)
        (args.output/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
