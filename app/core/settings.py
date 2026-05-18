# app/core/settings.py
import os, json
from ultralytics import YOLO
import torch
import time
from pydantic_settings import BaseSettings
from typing import Dict, Optional, Union
from ..schemas.aem import MetaData_schemas, AEMSettings

CONFIG_PATH = os.getenv("CONFIG_PATH",os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config.json")))
with open(CONFIG_PATH, "r") as f:
    _cfg = json.load(f)

class Settings(BaseSettings):
    AEM: Optional[AEMSettings] = None
    IMAGE_ROOT: str = "/mnt/ias-images"
    RESULT_IMAGE_ROOT: str = "/data/result_images"
    SAVE_RESULT_IMAGE: int = 0
    SERVER: Optional[str] = "http://172.17.0.1:10004"
    Port: int = 8881
    GPU_ID: Union[int, str]
    Person_Thresd: Dict[str, float]
    Face_Thresd: Dict[str, float]
    Student_Thresd: Dict[str, float]  # 新增学生行为阈值
    INSTANCE_COUNT: int = 1  # nginx实例个数
    WORKERS_PER_INSTANCE: int = 1 # 每实例workers数量，默认1

    model_config = {"env_file": None}

if "AEM" in _cfg:
    aem_config = _cfg.pop("AEM")
    if "MetaData" in aem_config:
        aem_config["MetaData"] = MetaData_schemas(**aem_config["MetaData"])
    _cfg["AEM"] = AEMSettings(**aem_config)

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
use_half = False  # 优先精准度，所以开启 fp32。20251205

APP_VER = "V4.1_20251222"
ADP_VER = "V4.1_20251222"
ALG_VER = "person_count_20251222_1920p/face_count(20251212)/student(20250819)"
#已经处理任务总数
Total_HaveProcess_Tasks = {"val": 0} 

PERSON_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'person_count_20251222_1920p.pt')
FACE_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'face_count_20251212.pt')
STUDENT_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'student_20250819).pt')
TEACHER_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'teacher-pose.pt')

yolo_person_model = YOLO(PERSON_MODEL_PATH).to(device)
yolo_face_model = YOLO(FACE_MODEL_PATH).to(device)
yolo_student_model = YOLO(STUDENT_MODEL_PATH).to(device)
yolo_teacher_model = YOLO(TEACHER_MODEL_PATH).to(device)
