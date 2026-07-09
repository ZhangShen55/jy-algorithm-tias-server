import os
from typing import Any

import torch


def resolve_torch_device(raw_device: Any) -> torch.device:
    value = str(raw_device).strip().lower()
    if value in {"", "none"}:
        value = "cpu"

    if value == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return torch.device("cpu")

    if value == "npu":
        return _resolve_npu_device(0)
    if value.startswith("npu:"):
        return _resolve_npu_device(_parse_device_index(value, "npu"))

    if value == "cuda":
        return _resolve_cuda_device("0")
    if value.startswith("cuda:"):
        return _resolve_cuda_device(str(_parse_device_index(value, "cuda")))

    if value.isdigit():
        return _resolve_cuda_device(value)

    raise RuntimeError(
        f"不支持的 TIAS 设备配置: {raw_device!r}。可用示例: 'cpu', '0', 'cuda:0', 'npu:3'。"
    )


def _parse_device_index(value: str, prefix: str) -> int:
    suffix = value.split(":", 1)[1].strip()
    if not suffix.isdigit():
        raise RuntimeError(f"无效的 {prefix.upper()} 设备配置: {value!r}")
    return int(suffix)


def _resolve_npu_device(index: int) -> torch.device:
    try:
        import torch_npu  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("当前环境无法导入 torch_npu，不能使用 Ascend NPU 设备。") from exc

    if not hasattr(torch, "npu") or not torch.npu.is_available():
        raise RuntimeError("torch_npu 已导入，但 torch.npu 不可用，请检查 CANN、驱动和环境变量。")

    count = torch.npu.device_count()
    if index < 0 or index >= count:
        raise RuntimeError(f"请求的 NPU 设备 npu:{index} 不可用，当前可见 NPU 数量: {count}")

    torch.npu.set_device(index)
    return torch.device(f"npu:{index}")


def _resolve_cuda_device(index: str) -> torch.device:
    os.environ["CUDA_VISIBLE_DEVICES"] = index
    if not torch.cuda.is_available():
        return torch.device("cpu")
    return torch.device("cuda:0")
