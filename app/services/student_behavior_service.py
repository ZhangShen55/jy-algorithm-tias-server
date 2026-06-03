# app/services/student_behavior_service.py
import os
import cv2
import base64
import time
import numpy as np
from typing import List, Tuple
from ..schemas.stu_tea_behavior import (
    Stu_Tea_BehaviorRequest,
    Stu_Tea_BehaviorResponse,
    ImageResult,
    ResultItem,
    ObjectPosition
)
from ..core.settings import yolo_person_model, yolo_face_model, yolo_student_model, settings,use_half
from ..schemas.geometry import Point
import logging


logger = logging.getLogger(__name__)
verbose=True
# 目标类别码定义
OBJECT_TYPES = {
    'person_count': 100,
    'face': 101,
    'Using_phone': 201,
    'Sleep': 202,
    'Hand_raising': 203,
    'standing': 204,
    'Read_W': 205
}
# 学生行为模型类别映射
STUDENT_BEHAVIOR_CLASSES = {
    0: 'Using_phone',  # 使用手机
    1: 'Hand_raising',  # 举手
    2: 'Sleep',  # 睡觉
    3: 'standing',  # 站立
    4: 'Read_W'  # 阅读
}

def mask_polygon(img: np.ndarray, points: List[Point]) -> Tuple[np.ndarray, Tuple[int, int]]:
    """
    使用多边形区域对图像进行遮罩，仅保留多边形内区域
    """
    if not points:
        return img, (0, 0)

    pts = np.array([[p.X, p.Y] for p in points], dtype=np.int32)
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    masked_img = cv2.bitwise_and(img, img, mask=mask)

    x, y, w, h = cv2.boundingRect(pts)
    subimg = masked_img[y:y + h, x:x + w]
    return subimg, (x, y)


def process_person_detection(img: np.ndarray, offset: Tuple[int, int], img_size: Tuple[int, int]) -> List[ObjectPosition]:
    """
    # todo 人数检测
    """
    start_time = time.time()
    ox, oy = offset
    height, width = img_size
    # logger.info(f"[人数检测] 开始检测，图像尺寸: {width}x{height}, 偏移: ({ox}, {oy})")
    pred = yolo_person_model.predict(img, conf=0.1, imgsz=(height, width),half=use_half,verbose=verbose)[0]
    dets = pred.boxes.data.tolist()
    inference_time = time.time() - start_time
    logger.info(f"[人数检测] 模型推理耗时: {inference_time * 1000:.1f}ms, 检测到 {len(dets)} 个目标")

    cls_names = ["Head", "Top_Head", "Hat", "Headphones", "Shoulder"]
    positions = []

    for *xyxy, conf, cls in dets:
        cls = int(cls)
        if cls < 0 or cls >= len(cls_names):
            continue
        if conf < settings.Person_Thresd[cls_names[cls]]:
            logger.debug(
                f"[人数检测] 过滤低置信度目标: {cls_names[cls]} conf={conf:.3f} < {settings.Person_Thresd[cls_names[cls]]}")
            continue

        x1, y1, x2, y2 = map(int, xyxy)
        positions.append(ObjectPosition(
            LeftTopX=x1 + ox,
            LeftTopY=y1 + oy,
            RightBtmX=x2 + ox,
            RightBtmY=y2 + oy
        ))
        # logger.debug(f"[人数检测] 检测到 {cls_names[cls]}: conf={conf:.3f}, bbox=({x1 + ox},{y1 + oy},{x2 + ox},{y2 + oy})")
    logger.info(f"[人数检测] 完成，符合config.toml中的阈值的有效目标: {len(positions)}个")
    return positions


def process_face_detection(img: np.ndarray, offset: Tuple[int, int], img_size: Tuple[int, int]) -> List[ObjectPosition]:
    """
    # todo 抬头检测（人脸检测）
    """
    start_time = time.time()
    ox, oy = offset
    height, width = img_size
    pred = yolo_face_model.predict(img, conf=0.1,imgsz=(height, width),half=use_half,verbose=verbose)[0]
    dets = pred.boxes.data.tolist()
    inference_time = time.time() - start_time
    logger.info(f"[抬头检测] 模型推理耗时: {inference_time * 1000:.1f}ms, 检测到 {len(dets)} 个目标")
    positions = []
    for *xyxy, conf, cls in dets:
        if conf < settings.Face_Thresd["face"]:
            logger.debug(f"[抬头检测] 过滤低置信度目标: conf={conf:.3f} < {settings.Face_Thresd['face']}")
            continue

        x1, y1, x2, y2 = map(int, xyxy)
        positions.append(ObjectPosition(
            LeftTopX=x1 + ox,
            LeftTopY=y1 + oy,
            RightBtmX=x2 + ox,
            RightBtmY=y2 + oy
        ))
    logger.info(f"[抬头检测] 完成，符合config.toml中的阈值的有效目标: {len(positions)}个")
    return positions


def process_student_behavior(img: np.ndarray, offset: Tuple[int, int],img_size: Tuple[int, int]) -> dict:
    """
    # todo 学生行为检测
    返回各种行为的检测结果
    """
    start_time = time.time()
    ox, oy = offset
    height, width = img_size
    pred = yolo_student_model.predict(img, conf=0.1, imgsz=(height, width),half=use_half,verbose=verbose)[0]  # 可调整置信度阈值
    dets = pred.boxes.data.tolist()
    inference_time = time.time() - start_time
    logger.info(f"[学生行为检测] 模型推理耗时: {inference_time * 1000:.1f}ms, 检测到 {len(dets)} 个目标")
    # 按行为类别分组
    behavior_results = {behavior: [] for behavior in STUDENT_BEHAVIOR_CLASSES.values()}

    for *xyxy, conf, cls in dets:
        cls = int(cls)
        if cls not in STUDENT_BEHAVIOR_CLASSES:
            logger.debug(f"[学生行为检测] 未知类别: {cls}")
            continue

        behavior_name = STUDENT_BEHAVIOR_CLASSES[cls]
        # 第二步：使用配置文件中的阈值进行筛选
        threshold = settings.Student_Thresd.get(behavior_name, 0.15)
        if conf < threshold:
            logger.debug(f"[学生行为检测] 过滤低置信度目标: {behavior_name} conf={conf:.3f} < {threshold}")
            continue
        x1, y1, x2, y2 = map(int, xyxy)
        behavior_results[behavior_name].append(ObjectPosition(
            LeftTopX=x1 + ox,
            LeftTopY=y1 + oy,
            RightBtmX=x2 + ox,
            RightBtmY=y2 + oy
        ))
    # 统计各行为检测结果
    behavior_stats = {name: len(positions) for name, positions in behavior_results.items() if positions}
    logger.info(f"[学生行为检测] 完成，符合config.toml中的阈值的检测结果: {behavior_stats}")
    return behavior_results


async def analyze_student_behavior(request: Stu_Tea_BehaviorRequest) -> Stu_Tea_BehaviorResponse:
    """
    学生行为分析主函数
    """
    start_time = time.time()
    timestamp = int(time.time())
    logger.info(f"[学生行为分析] 开始处理 {len(request.ImageList)} 张图片")
    # 增加处理计数
    from .capacity_service import increment_connection, increment_processed_images
    increment_connection()
    increment_processed_images(len(request.ImageList))

    processed_image_ids = []
    data_list = []

    # for image_item in request.ImageList:
    for idx, image_item in enumerate(request.ImageList, 1):
        image_start_time = time.time()  # 添加单张图片开始时间
        logger.info(f"[学生行为分析] 处理第 {idx}/{len(request.ImageList)} 张图片: {image_item.ImageId}")

        try:
            # 解码base64图片
            decode_start = time.time()
            if image_item.StoragePath.startswith('data:') or len(image_item.StoragePath) > 1000:
                # Base64格式
                if image_item.StoragePath.startswith('data:'):
                    base64_data = image_item.StoragePath.split(',')[1]
                else:
                    base64_data = image_item.StoragePath

                img_data = base64.b64decode(base64_data)
                img_array = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img is None:
                    raise RuntimeError("base64图片解码失败")
                logger.info(f"[学生行为分析] Base64图片解码耗时: {(time.time() - decode_start) * 1000:.1f}ms")
            elif image_item.StoragePath.startswith('http://') or image_item.StoragePath.startswith('https://'):
                # 网络流图片
                logger.debug(f"[图片处理] 从网络URL加载图片 ID={image_item.ImageId}: Url={image_item.StoragePath}")
                import requests
                t0 = time.time()
                resp = requests.get(image_item.StoragePath, timeout=5)
                t1 = time.time()
                img_array = np.frombuffer(resp.content, np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                t2 = time.time()

                logger.info(f"[学生行为分析] download-time: {(t1-t0)*1000:.1f} ms, 网络流图片解码耗时_decode-time: {(t2-t1)*1000:.1f} ms")

                # logger.info(f"[学生行为分析] 网络流图片解码耗时: {(time.time() - decode_start) * 1000:.1f}ms")
            else:
                # 文件路径
                if os.path.isabs(image_item.StoragePath):
                    img_path = image_item.StoragePath
                else:
                    img_path = os.path.join(settings.IMAGE_ROOT, image_item.StoragePath.lstrip('/'))
                img = cv2.imread(img_path)
                logger.info(f"[学生行为分析] 本地图片读取耗时: {(time.time() - decode_start) * 1000:.1f}ms")
            if img is None:
                raise ValueError(f"无法读取图片: {image_item.ImageId}")

            # 获取原始图像尺寸
            original_height, original_width = img.shape[:2]
            img_size = (original_height, original_width)
            logger.info(f"[学生行为分析] 图片尺寸: {original_width}x{original_height}")
            # 处理检测区域
            if image_item.Points:
                processed_img, offset = mask_polygon(img, image_item.Points)
            else:
                processed_img, offset = img, (0, 0)

            # 执行三种检测
            detection_start = time.time()
            person_positions = process_person_detection(processed_img, offset, img_size)
            face_positions = process_face_detection(processed_img, offset, img_size)
            behavior_results = process_student_behavior(processed_img, offset, img_size)
            detection_time = time.time() - detection_start
            logger.info(f"[学生行为分析] 三种检测总耗时: {detection_time * 1000:.1f}ms")

            # 构建结果列表
            result_list = []
            # 人数统计结果
            result_list.append(ResultItem(
                ObjectType=OBJECT_TYPES['person_count'],
                ObjectCount=len(person_positions),
                ObjectPostList=person_positions if person_positions else None
            ))

            # 抬头人数结果
            result_list.append(ResultItem(
                ObjectType=OBJECT_TYPES['face'],
                ObjectCount=len(face_positions),
                ObjectPostList=face_positions if face_positions else None
            ))

            # 学生行为结果
            for behavior_name, positions in behavior_results.items():
                if behavior_name in OBJECT_TYPES:
                    result_list.append(ResultItem(
                        ObjectType=OBJECT_TYPES[behavior_name],
                        ObjectCount=len(positions),
                        ObjectPostList=positions if positions else None
                    ))

            # 计算单张图片耗时
            image_use_time_ms = int((time.time() - image_start_time) * 1000)
            # 构建单张图片结果
            image_result = ImageResult(
                StatusObject={
                    "StatusString": "success",
                    "ImageId": image_item.ImageId,
                    "TimeStamp": timestamp,
                    "UseTimeMs": image_use_time_ms,  # 或者单张图片的处理时间
                    "StatusCode": 0
                },
                ResultList=result_list
            )

            data_list.append(image_result)
            processed_image_ids.append(image_item.ImageId)

            # 统计结果
            total_detections = len(person_positions) + len(face_positions) + sum(
                len(pos) for pos in behavior_results.values())
            logger.info(
                f"[学生行为分析] 图片 {image_item.ImageId} 处理完成: 人数={len(person_positions)}, 抬头={len(face_positions)}, 行为检测={sum(len(pos) for pos in behavior_results.values())}, 总检测数={total_detections}, 耗时={image_use_time_ms}ms")
        except Exception as e:
            logger.error(f"[学生行为分析] 图片 {image_item.ImageId} 处理失败: {str(e)}")
            # 添加失败结果
            image_result = ImageResult(
                StatusObject={"StatusString": "failed", "StatusCode": 500},
                ResultList=[]
            )
            data_list.append(image_result)
            # 抛出HTTP异常，FastAPI会自动返回500错误
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))

    # 计算总耗时
    use_time_ms = int((time.time() - start_time) * 1000)

    # 构建最终响应
    response = Stu_Tea_BehaviorResponse(
        StatusObject={
            "StatusString": "success" if processed_image_ids else "failed",
            "ImageIdList": processed_image_ids,
            "TimeStamp": timestamp,
            "UseTimeMs": use_time_ms,
            "StatusCode": 0 if processed_image_ids else 500
        },
        DataList=data_list
    )
    logger.info(
        f"[学生行为分析] 全部完成: 成功处理 {len(processed_image_ids)}/{len(request.ImageList)} 张图片, 总耗时: {use_time_ms}ms")
    return response
