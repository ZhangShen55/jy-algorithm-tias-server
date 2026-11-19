#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.model_protection import encrypt_model_file, generate_key


DEFAULT_MODEL_NAMES = [
    "person_count.engine",
    "face_count.engine",
    "student.engine",
    "teacher_behavior.engine",
]


def protect_models(source_dir: Path, target_dir: Path, key: str, model_names=None) -> list[Path]:
    model_names = model_names or DEFAULT_MODEL_NAMES
    for model_name in model_names:
        if Path(model_name).name != model_name:
            raise ValueError(f"模型名称必须是文件名: {model_name}")
        if not (source_dir / model_name).is_file():
            raise FileNotFoundError(f"模型缺失: {source_dir / model_name}")
        if (target_dir / f"{model_name}.enc").exists():
            raise FileExistsError(f"加密输出已存在: {model_name}.enc")
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for model_name in model_names:
        source_path = source_dir / model_name
        target_path = target_dir / f"{model_name}.enc"
        encrypt_model_file(source_path, target_path, key)
        outputs.append(target_path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="将 VBAS 明文模型加密为 .enc 文件。")
    parser.add_argument("--source-dir", default="model", help="明文 Engine 目录")
    parser.add_argument("--target-dir", default="models-encrypted", help="加密模型输出目录")
    parser.add_argument("--key-file", required=True, help="模型密钥文件；不存在时可配合 --generate-key 生成")
    parser.add_argument("--generate-key", action="store_true", help="如果密钥文件不存在则生成新密钥")
    parser.add_argument("--model", action="append", help="指定模型文件名，可重复；默认处理内置模型清单")
    args = parser.parse_args()

    key_path = Path(args.key_file)
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
    elif args.generate_key:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = generate_key()
        key_path.write_text(key + "\n", encoding="utf-8")
        key_path.chmod(0o600)
        print(f"模型密钥已生成: {key_path}")
    else:
        raise FileNotFoundError(f"模型密钥文件不存在: {key_path}")

    outputs = protect_models(
        source_dir=Path(args.source_dir),
        target_dir=Path(args.target_dir),
        key=key,
        model_names=args.model,
    )
    for output in outputs:
        print(f"已生成加密模型: {output}")
    if not outputs:
        print("未找到可加密模型，请检查 --source-dir 或 --model 参数")


if __name__ == "__main__":
    main()
