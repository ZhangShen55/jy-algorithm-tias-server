import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(monkeypatch, name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def npu_device(monkeypatch):
    selected = []
    npu = types.SimpleNamespace(
        is_available=lambda: True,
        device_count=lambda: 8,
        set_device=selected.append,
    )
    torch = types.SimpleNamespace(device=lambda value: value, npu=npu)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "torch_npu", types.ModuleType("torch_npu"))
    module = load_module(monkeypatch, "core._device_test", "core/device.py")
    return module, npu, selected


@pytest.mark.parametrize("value,index", [("npu", 0), ("npu:3", 3), ("npu:7", 7)])
def test_npu_selection_keeps_requested_device(npu_device, value, index):
    module, _, selected = npu_device
    assert module.resolve_torch_device(value) == f"npu:{index}"
    assert selected == [index]


def test_npu_out_of_range_fails_without_cpu_fallback(npu_device):
    module, _, selected = npu_device
    with pytest.raises(RuntimeError, match="不可用"):
        module.resolve_torch_device("npu:8")
    assert selected == []


def test_npu_unavailable_fails_without_cpu_fallback(npu_device):
    module, npu, selected = npu_device
    npu.is_available = lambda: False
    with pytest.raises(RuntimeError, match="CANN"):
        module.resolve_torch_device("npu:3")
    assert selected == []


def test_missing_torch_npu_fails_without_cpu_fallback(npu_device, monkeypatch):
    module, _, selected = npu_device
    monkeypatch.setitem(sys.modules, "torch_npu", None)
    with pytest.raises(RuntimeError, match="无法导入 torch_npu"):
        module.resolve_torch_device("npu:3")
    assert selected == []


@pytest.fixture
def warmup(monkeypatch):
    settings = types.SimpleNamespace(Warmup={"Enabled": True, "Runs": 2, "ImageWidth": 641, "ImageHeight": 479})
    calls = []

    def callback(name):
        def infer(image, offset, size):
            calls.append((name, image.shape, offset, size))
        return infer

    monkeypatch.setitem(sys.modules, "core.settings", types.SimpleNamespace(settings=settings))
    monkeypatch.setitem(sys.modules, "services.student_behavior_service", types.SimpleNamespace(
        process_person_detection=callback("person"),
        process_face_detection=callback("face"),
        process_student_behavior=callback("student"),
    ))
    monkeypatch.setitem(sys.modules, "services.teacher_behavior_service", types.SimpleNamespace(
        process_teacher_behavior_model_detection=callback("teacher"),
    ))
    # A removed module must not be needed to import or execute startup warmup.
    monkeypatch.setitem(sys.modules, "services.teacher_head_pose_service", None)
    module = load_module(monkeypatch, "services._warmup_test", "services/model_warmup.py")
    return module, settings, calls


def test_startup_warms_all_four_models_without_head_pose(warmup):
    module, _, calls = warmup
    module.run_model_inference_warmup()
    assert [name for name, *_ in calls] == ["person", "face", "student", "teacher"] * 2
    assert all((shape, offset, size) == ((480, 672, 3), (0, 0), (480, 672)) for _, shape, offset, size in calls)


def test_disabled_warmup_does_not_run_models(warmup):
    module, settings, calls = warmup
    settings.Warmup["Enabled"] = False
    module.run_model_inference_warmup()
    assert calls == []


@pytest.mark.parametrize("fail_on_error", [True, False])
def test_warmup_preserves_failure_policy(warmup, fail_on_error):
    module, settings, _ = warmup
    settings.Warmup["FailOnError"] = fail_on_error

    def fail(*args):
        raise RuntimeError("NPU warmup failed")

    module.process_person_detection = fail
    if fail_on_error:
        with pytest.raises(RuntimeError, match="NPU warmup failed"):
            module.run_model_inference_warmup()
    else:
        module.run_model_inference_warmup()
