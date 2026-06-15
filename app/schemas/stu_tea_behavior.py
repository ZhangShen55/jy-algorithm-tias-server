# app/schemas/student_behavior.py
from pydantic import BaseModel
from typing import List, Optional
from .geometry import Point
from .error_codes import AppErrCode

class ImageItem(BaseModel):
    StoragePath: str
    ImageId: str
    Points: Optional[List[Point]] = None

class TeacherBehaviorThresholds(BaseModel):
    sit: Optional[float] = None
    stand: Optional[float] = None
    bbwriting: Optional[float] = None
    teach: Optional[float] = None

class Stu_Tea_BehaviorRequest(BaseModel):
    ImageList: List[ImageItem]
    Teacher_Behavior_Thresd: Optional[TeacherBehaviorThresholds] = None

class ObjectPosition(BaseModel):
    LeftTopX: int
    LeftTopY: int
    RightBtmX: int
    RightBtmY: int
    Confidence: Optional[float] = None
    SuspectedSitting: Optional[bool] = None # 疑似坐
    PostureFallback: Optional[bool] = None #坐站都低于阈值，使用主体位置作为站

class ResultItem(BaseModel):
    ObjectType: int
    ObjectCount: int
    ObjectPostList: Optional[List[ObjectPosition]] = None

class ImageResult(BaseModel):
    StatusObject: dict
    ResultList: List[ResultItem]

class Stu_Tea_BehaviorResponse(BaseModel):
    StatusObject: dict
    DataList: List[ImageResult]
