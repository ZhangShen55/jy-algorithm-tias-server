# app/core/settings.py
import os
from ultralytics import YOLO
import torch
import time
from pydantic_settings import BaseSettings
from typing import Dict, Union
from .config_loader import load_config

CONFIG_PATH = os.getenv("CONFIG_PATH",os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.toml")))
_cfg = load_config(CONFIG_PATH)

class Settings(BaseSettings):
    IMAGE_ROOT: str = "/mnt/ias-images"
    RESULT_IMAGE_ROOT: str = "/data/result_images"
    SAVE_RESULT_IMAGE: int = 0
    Port: int = 8881
    GPU_ID: Union[int, str]
    Person_Thresd: Dict[str, float]
    Face_Thresd: Dict[str, float]
    Student_Thresd: Dict[str, float]  # 新增学生行为阈值
    INSTANCE_COUNT: int = 1  # nginx实例个数
    WORKERS_PER_INSTANCE: int = 1 # 每实例workers数量，默认1

    model_config = {"env_file": None, "extra": "ignore"}

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
STUDENT_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'student_20250819.pt')
TEACHER_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'teacher-pose.pt')

'''
person_count.pt	
    0: Head
    1: Top_Head
    2: Hat
    3: Headphones
    4: Shoulder
    5: Other（移除）
face_count.pt
    0: face
student.pt	
    0: Using_phone
    1: Hand_raising
    2: Sleep
    3: standing
    4: Read_W
teacher-pose.pt	
    0: person
'''

yolo_person_model = YOLO(PERSON_MODEL_PATH).to(device)
yolo_face_model = YOLO(FACE_MODEL_PATH).to(device)
yolo_student_model = YOLO(STUDENT_MODEL_PATH).to(device)
yolo_teacher_model = YOLO(TEACHER_MODEL_PATH).to(device)
