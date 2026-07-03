#!/usr/bin/env python3
import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable


FORBIDDEN_MODEL_EXTENSIONS = {".pt", ".pth", ".onnx", ".engine"}
FORBIDDEN_KEY_EXTENSIONS = {".key", ".pem", ".crt"}
FORBIDDEN_DIRECTORIES = (
    "/workspace/tias/docker",
    "/workspace/tias/tests",
    "/workspace/tias/tests2",
    "/workspace/tias/docs",
    "/workspace/tias/openspec",
    "/workspace/tias/tmp",
    "/workspace/tias/mnt",
    "/workspace/tias/models",
    "/workspace/docs",
    "/workspace/openspec",
    "/workspace/tests",
    "/workspace/tests2",
)
FORBIDDEN_FILE_PATTERNS = (
    "Dockerfile*",
    "RUNNING.md",
    "requirements*.txt",
    "config.toml.example",
)
PROTECTED_PACKAGE_PREFIXES = (
    "/workspace/tias/api/",
    "/workspace/tias/core/",
    "/workspace/tias/services/",
    "/workspace/tias/schemas/",
)
ALLOWED_PYTHON_FILES = {
    "/workspace/tias/__init__.py",
    "/workspace/tias/main.py",
    "/workspace/tias/api/__init__.py",
    "/workspace/tias/core/__init__.py",
    "/workspace/tias/services/__init__.py",
    "/workspace/tias/schemas/__init__.py",
}
REQUIRED_FILES = {
    "/workspace/tias/main.py",
    "/usr/local/bin/tias-secure-entrypoint",
}


@dataclass(frozen=True)
class ImageCheckResult:
    ok: bool
    failures: list[str]
    extension_count: int
    checked_rule_count: int


def evaluate_runtime_files(files: Iterable[str]) -> ImageCheckResult:
    normalized_files = sorted({_normalize_path(item) for item in files if str(item).strip()})
    failures: list[str] = []
    extension_count = 0

    for file_path in normalized_files:
        path = PurePosixPath(file_path)
        suffix = path.suffix
        name = path.name

        if suffix in FORBIDDEN_MODEL_EXTENSIONS:
            failures.append(f"发现明文模型文件: {file_path}")
        if suffix in FORBIDDEN_KEY_EXTENSIONS or name == "tias_model_key":
            failures.append(f"发现密钥文件: {file_path}")
        if _is_under_forbidden_directory(file_path):
            failures.append(f"发现非运行目录内容: {file_path}")
        if any(fnmatch.fnmatch(name, pattern) for pattern in FORBIDDEN_FILE_PATTERNS):
            failures.append(f"发现非运行文件: {file_path}")
        if _is_protected_plain_source(file_path):
            failures.append(f"发现核心明文源码: {file_path}")
        if suffix == ".so" and any(file_path.startswith(prefix) for prefix in PROTECTED_PACKAGE_PREFIXES):
            extension_count += 1

    missing_required = sorted(REQUIRED_FILES.difference(normalized_files))
    for file_path in missing_required:
        failures.append(f"缺少运行必需文件: {file_path}")
    if extension_count == 0:
        failures.append("未发现 Cython .so 编译产物")

    return ImageCheckResult(
        ok=not failures,
        failures=failures,
        extension_count=extension_count,
        checked_rule_count=6,
    )


def list_image_files(image: str) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "sh",
        image,
        "-c",
        "find /workspace/tias -type f -print 2>/dev/null; "
        "if [ -f /usr/local/bin/tias-secure-entrypoint ]; then "
        "printf '%s\\n' /usr/local/bin/tias-secure-entrypoint; "
        "fi",
    ]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "镜像文件列表读取失败: "
            f"exit={completed.returncode} stderr={completed.stderr.strip()}"
        )
    return completed.stdout.splitlines()


def _normalize_path(value: str) -> str:
    text = str(value).strip()
    if not text.startswith("/"):
        text = f"/{text}"
    return text


def _is_under_forbidden_directory(file_path: str) -> bool:
    return any(file_path == directory or file_path.startswith(f"{directory}/")
               for directory in FORBIDDEN_DIRECTORIES)


def _is_protected_plain_source(file_path: str) -> bool:
    if file_path in ALLOWED_PYTHON_FILES:
        return False
    if not file_path.endswith(".py"):
        return False
    return any(file_path.startswith(prefix) for prefix in PROTECTED_PACKAGE_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 TIAS secure runtime 镜像内容。")
    parser.add_argument("--image", required=True, help="需要检查的镜像名，例如 tias:6.0-secure")
    args = parser.parse_args()

    try:
        files = list_image_files(args.image)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = evaluate_runtime_files(files)
    if result.ok:
        print("TIAS secure runtime 镜像检查通过")
        print(f".so 编译产物数量: {result.extension_count}")
        print(f"检查规则数量: {result.checked_rule_count}")
        return 0

    print("TIAS secure runtime 镜像检查失败", file=sys.stderr)
    for failure in result.failures:
        print(f"- {failure}", file=sys.stderr)
    print(f".so 编译产物数量: {result.extension_count}", file=sys.stderr)
    print(f"检查规则数量: {result.checked_rule_count}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
