# app/schemas/student_behavior.py
from pydantic import BaseModel
from typing import List, Optional
from .geometry import Point
from .error_codes import AppErrCode

class ImageItem(BaseModel):
    StoragePath: str
    ImageId: str
    Points: Optional[List[Point]] = None

class Stu_Tea_BehaviorRequest(BaseModel):
    ImageList: List[ImageItem]

class ObjectPosition(BaseModel):
    LeftTopX: int
    LeftTopY: int
    RightBtmX: int
    RightBtmY: int

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