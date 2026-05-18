# app/schemas/capacity.py

from pydantic import BaseModel
from .response import Response

class Capacity(BaseModel):
    AppID: str
    TaskNumTotal: int
    TaskNumUsed: int
    FtrNumTotal: int
    FtrNumUsed: int

class CapacityResponse(BaseModel):
    Response: Response
    Capacity: Capacity


# 新增 Capacity_v2 相关模型
class CapacityV2(BaseModel):
    AppID: str
    TaskNumTotal: int  # 总路数
    TaskNumUsed: int   # 已用路数
    FtrNumTotal: int   # 总容量
    FtrNumUsed: int    # 已用容量
    ConnectionCount: int  # 连接数
    ProcessedImages: int  # 处理的图片数量
    RegisterTime: str     # 注册时间
    RunningTime: str      # 运行时间（从注册到现在的时间）

class CapacityV2Response(BaseModel):
    Response: Response
    Capacity: CapacityV2