# core/settings.py
import os
from ultralytics import YOLO
import torch
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Any, Dict, Union, Literal
from .config_loader import load_config
from .model_protection import ModelPathResolver, ModelProtectionConfig

CONFIG_PATH = os.getenv("CONFIG_PATH",os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.toml")))
_cfg = load_config(CONFIG_PATH)

class Settings(BaseSettings):
    IMAGE_ROOT: str = "/mnt/ias-images"
    RESULT_IMAGE_ROOT: str = "/data/result_images"
    SAVE_RESULT_IMAGE: int = 0
    InferenceHalf: bool = False
    InferenceBackend: Literal["pytorch", "tensorrt"] = "pytorch"
    EngineRoot: str = ""
    Port: int = 8881
    GPU_ID: Union[int, str]
    Person_Thresd: Dict[str, float]
    Face_Thresd: Dict[str, float]
    Student_Thresd: Dict[str, float]  # 新增学生行为阈值
    Teacher_Behavior_Thresd: Dict[str, Any] = Field(default_factory=lambda: {
        "MergeIoU": 0.8,
        "ImageSize": 640,
        "sit": 0.4,
        "stand": 0.4,
        "bbwriting": 0.25,
        "teach": 0.25,
        "KeepOnlyMainSubject": True,
        "MainSubjectStrategy": "posture_confidence",
        "SubjectClusterIoU": 0.45,
        "PostureConflictRatio": 0.10,
        "PostureConflictDefault": "stand",
        "ForcePostureWhenMissing": True
    })
    INSTANCE_COUNT: int = 1  # nginx实例个数
    WORKERS_PER_INSTANCE: int = 1 # 每实例workers数量，默认1
    VBAS: Dict[str, Any] = Field(default_factory=dict)
    VbasExposeLegacySyncTasks: bool = False
    InstanceId: str = "vbas-8981"
    BaseUrl: str = "http://127.0.0.1:8981"
    VisionOrchestratorBaseUrl: str = "http://127.0.0.1:9000"
    MaxConcurrentBatches: int = 1
    MaxQueueSize: int = 0
    HeartbeatIntervalSeconds: int = 5
    HeartbeatTimeoutSeconds: int = 15
    RegisterRetryIntervalSeconds: int = 5
    ModelProtection: Dict[str, Any] = Field(default_factory=lambda: {
        "Enabled": False,
        "EncryptedModelRoot": "models-encrypted",
        "DecryptedTempRoot": "/dev/shm/vbas-models",
        "KeyFile": "/dev/shm/vbas_model_key",
        "CleanupAfterLoad": True
    })

    model_config = {"env_file": None, "extra": "ignore"}

_vbas_config = _cfg.get("VBAS", {})
if not isinstance(_vbas_config, dict):
    _vbas_config = {}
_cfg = {
    **_cfg,
    "VbasExposeLegacySyncTasks": bool(_vbas_config.get("VbasExposeLegacySyncTasks", False)),
    "InstanceId": str(_vbas_config.get("InstanceId", "vbas-8981")),
    "BaseUrl": str(_vbas_config.get("BaseUrl", "http://127.0.0.1:8981")),
    "VisionOrchestratorBaseUrl": str(
        _vbas_config.get("VisionOrchestratorBaseUrl", "http://127.0.0.1:9000")
    ),
    "MaxConcurrentBatches": int(_vbas_config.get("MaxConcurrentBatches", 1)),
    "MaxQueueSize": int(_vbas_config.get("MaxQueueSize", 0)),
    "HeartbeatIntervalSeconds": int(_vbas_config.get("HeartbeatIntervalSeconds", 5)),
    "HeartbeatTimeoutSeconds": int(_vbas_config.get("HeartbeatTimeoutSeconds", 15)),
    "RegisterRetryIntervalSeconds": int(_vbas_config.get("RegisterRetryIntervalSeconds", 5)),
}
settings = Settings(**_cfg)

if str(settings.GPU_ID).lower() == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    device = torch.device("cpu")
else:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(settings.GPU_ID)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # if device.type == "cuda":
    #     torch.backends.cudnn.benchmark = True
    #     torch.backends.cudnn.deterministic = False
# use_half = device.type == "cuda"  # 仅在 CUDA 场景启用 FP16
use_half = settings.InferenceHalf
if use_half and device.type != "cuda":
    raise RuntimeError("InferenceHalf requires an available CUDA device")

APP_VER = "V4.1_20251222"
ADP_VER = "V4.1_20251222"
ALG_VER = "person_count_20251222_1920p/face_count(20251212)/student(20250819)"
#已经处理任务总数
Total_HaveProcess_Tasks = {"val": 0}

PERSON_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'person_count.pt')
FACE_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'face_count.pt')
STUDENT_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'student.pt')
TEACHER_BEHAVIOR_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'teacher_behavior.pt')

model_protection_config = ModelProtectionConfig.from_mapping(getattr(settings, "ModelProtection", {}))
model_path_resolver = ModelPathResolver(model_protection_config)

def load_inference_model(pt_path):
    if settings.InferenceBackend == "pytorch":
        return YOLO(str(model_path_resolver.prepare_model_path(pt_path))).to(device)
    if device.type != "cuda" or not use_half or not settings.EngineRoot:
        raise RuntimeError("TensorRT requires CUDA, InferenceHalf=true and EngineRoot")
    from pathlib import Path
    import numpy as np
    name = Path(pt_path).stem
    engine_path = Path(settings.EngineRoot) / name / f"{name}.engine"
    path = model_path_resolver.prepare_model_path(engine_path)
    model = YOLO(str(path), task="detect")
    # 当前实验引擎固定实际输入尺寸，不能沿用 PyTorch 的自动矩形补边。
    shape = (384, 640) if name == "teacher_behavior" else (1088, 1920)
    original = model.predict
    def predict(*args, **kwargs):
        kwargs["imgsz"] = shape
        kwargs["half"] = True
        return original(*args, **kwargs)
    model.predict = predict
    # 在清理解密临时文件前实例化运行时，避免延迟加载访问已删除文件。
    model.predict(np.zeros((*shape, 3), dtype=np.uint8), device=0, verbose=False)
    if not model.predictor.model.fp16:
        raise RuntimeError(f"Engine is not FP16: {name}")
    return model


yolo_person_model = load_inference_model(PERSON_MODEL_PATH)
yolo_face_model = load_inference_model(FACE_MODEL_PATH)
yolo_student_model = load_inference_model(STUDENT_MODEL_PATH)
yolo_teacher_behavior_model = load_inference_model(TEACHER_BEHAVIOR_MODEL_PATH)
if model_protection_config.cleanup_after_load:
    model_path_resolver.cleanup()
