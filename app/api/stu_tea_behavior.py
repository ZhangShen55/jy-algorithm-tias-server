# app/api/stu_tea_behavior.py
from fastapi import APIRouter, HTTPException
from ..schemas.stu_tea_behavior import Stu_Tea_BehaviorRequest, Stu_Tea_BehaviorResponse
from ..services.student_behavior_service import analyze_student_behavior
from ..services.teacher_behavior_service import analyze_teacher_behavior
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ImageDetect/student/v1.0.0", response_model=Stu_Tea_BehaviorResponse)
async def student_behavior_analysis(request: Stu_Tea_BehaviorRequest):
    """
    学生行为分析接口
    集成人数统计、抬头检测和学生行为识别
    """
    try:
        logger.info(f"Received student behavior analysis request for {len(request.ImageList)} images")
        result = await analyze_student_behavior(request)
        return result
    except Exception as e:
        logger.error(f"Student behavior analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

@router.post("/ImageDetect/teacher/v1.0.0", response_model=Stu_Tea_BehaviorResponse)
async def teacher_behavior_analysis(request: Stu_Tea_BehaviorRequest):
    """
    老师行为分析接口
    包含：讲台是否有人(100)、走动(101)、站立(102)、坐着(103)、板书(104)
    """
    try:
        logger.info(f"Received teacher behavior analysis request for {len(request.ImageList)} images")
        result = await analyze_teacher_behavior(request)
        return result
    except Exception as e:
        logger.error(f"Teacher behavior analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")