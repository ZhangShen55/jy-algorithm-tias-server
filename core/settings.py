# core/settings.py
import os
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Any, Dict, Union, Literal
from .config_loader import load_config
from .inference_runtime import configure_device, load_models, resolve_engine_root
from .model_protection import ModelPathResolver, ModelProtectionConfig

CONFIG_PATH = os.getenv("CONFIG_PATH",os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.toml")))
_cfg = load_config(CONFIG_PATH)

class Settings(BaseSettings):
    IMAGE_ROOT: str = "/mnt/ias-images"
    RESULT_IMAGE_ROOT: str = "/data/result_images"
    SAVE_RESULT_IMAGE: int = 0
    InferenceHalf: bool = True
    InferenceBackend: Literal["pytorch", "tensorrt"] = "tensorrt"
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

configure_device(settings.GPU_ID)
# GPU libraries are imported only after preserving the external visibility mapping.
import torch
if not torch.cuda.is_available():
    raise RuntimeError("TensorRT requires an available CUDA device")
device = torch.device("cuda:0")
use_half = settings.InferenceHalf

APP_VER = "V4.1_20251222"
ADP_VER = "V4.1_20251222"
ALG_VER = "person_count_20251222_1920p/face_count(20251212)/student(20250819)"
#已经处理任务总数
Total_HaveProcess_Tasks = {"val": 0}

_engine_root = resolve_engine_root(settings.EngineRoot)
PERSON_MODEL_PATH = str(_engine_root / 'person_count.engine')
FACE_MODEL_PATH = str(_engine_root / 'face_count.engine')
STUDENT_MODEL_PATH = str(_engine_root / 'student.engine')
TEACHER_BEHAVIOR_MODEL_PATH = str(_engine_root / 'teacher_behavior.engine')

model_protection_config = ModelProtectionConfig.from_mapping(getattr(settings, "ModelProtection", {}))
model_path_resolver = ModelPathResolver(model_protection_config)
try:
    _models = load_models(settings, model_path_resolver)
    yolo_person_model = _models['person_count']
    yolo_face_model = _models['face_count']
    yolo_student_model = _models['student']
    yolo_teacher_behavior_model = _models['teacher_behavior']
finally:
    if model_protection_config.cleanup_after_load:
        model_path_resolver.cleanup()
