# app/services/teacher_behavior_service.py
import os
import cv2
import base64
import time
import numpy as np
import math
from typing import List, Tuple, Dict
from ..schemas.stu_tea_behavior import (
    Stu_Tea_BehaviorRequest,
    Stu_Tea_BehaviorResponse,
    ImageResult,
    ResultItem,
    ObjectPosition
)
from ..core.settings import yolo_teacher_model, settings, use_half
from ..schemas.geometry import Point
import logging

logger = logging.getLogger(__name__)
verbose=True
# 老师的后面可以调成一个模型，不用人数的模型
# 老师行为目标类别码定义
TEACHER_OBJECT_TYPES = {
    'platform_person': 100,  # 讲台是否有人
    'standing': 201,  # 站立
    'sitting': 202,  # 坐着
    'writing': 203,  # 板书
    'calling': 204,  # 打电话
}

# 姿态关键点名称
POSE_KPT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]
"""
0鼻子, 1左眼, 2右眼, 3左耳, 4右耳, 5左肩, 6右肩, 7左肘, 8右肘, 9左腕
10右手腕, 11左髋关节, 12右髋关节, 13左膝, 14右膝盖, 15左脚踝, 16右脚踝
"""

# 髋部以下关键点索引
LOWER_BODY_KPTS = [11, 12, 13, 14, 15, 16]

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


def process_platform_person_detection(img: np.ndarray, offset: Tuple[int, int], img_size: Tuple[int, int]) -> List[ObjectPosition]:
    """
    讲台人员检测
    """
    logger.debug("[讲台检测] 开始讲台人员检测")
    start_time = time.time()
    ox, oy = offset
    height, width = img_size

    pred = yolo_teacher_model.predict(img, imgsz=(height, width),half=use_half,verbose=verbose)[0]
    dets = pred.boxes.data.tolist()
    inference_time = time.time() - start_time
    logger.debug(f"[讲台检测] 模型推理耗时: {inference_time * 1000:.1f}ms, 检测到 {len(dets)} 个目标")

    positions = []
    for *xyxy, conf, cls in dets:

        x1, y1, x2, y2 = map(int, xyxy)
        positions.append(ObjectPosition(
            LeftTopX=x1 + ox,
            LeftTopY=y1 + oy,
            RightBtmX=x2 + ox,
            RightBtmY=y2 + oy
        ))
    logger.debug(f"[讲台检测] 讲台人员检测完成，符合阈值的有效检测: {len(positions)} 个")
    return positions


def is_sitting(keypoints_xy):
    """判断是否坐着：如果髋部以下关键点大多数缺失"""
    # logger.info("[坐姿检测] 开始坐姿检测...")
    visible_count = 0
    for idx in LOWER_BODY_KPTS:
        x, y = keypoints_xy[idx]
        if x > 0 and y > 0:
            visible_count += 1
    return visible_count <= 1  # 阈值你可以根据实际调整，比如 <=2 表示关键点几乎看不到


def calculate_angle(point1, point2, point3):
    """
    计算三点形成的角度
    point1, point2, point3 为 (x, y) 坐标
    """
    # 计算向量
    vector1 = [point2[0] - point1[0], point2[1] - point1[1]]
    vector2 = [point3[0] - point2[0], point3[1] - point2[1]]

    # 计算点积和模长
    dot_product = vector1[0] * vector2[0] + vector1[1] * vector2[1]
    magnitude1 = math.sqrt(vector1[0] ** 2 + vector1[1] ** 2)
    magnitude2 = math.sqrt(vector2[0] ** 2 + vector2[1] ** 2)

    # 计算角度
    cos_angle = dot_product / (magnitude1 * magnitude2)
    angle = math.acos(cos_angle)
    angle = math.degrees(angle)  # 转为度数
    return angle


def check_shoulder_lean(left_shoulder, right_shoulder, bbox, lean_threshold=15):
    """
    检查肩部是否前倾
    计算肩部偏离水平线的角度
    """
    # 检查肩部关键点有效性
    if (left_shoulder[0] <= 0 or left_shoulder[1] <= 0 or
            right_shoulder[0] <= 0 or right_shoulder[1] <= 0):
        return False

    # 计算肩部倾斜角度而不仅仅是Y坐标差
    shoulder_angle = math.atan2(
        right_shoulder[1] - left_shoulder[1],
        right_shoulder[0] - left_shoulder[0]
    )
    shoulder_angle_degrees = math.degrees(shoulder_angle)

    # 计算偏离水平线的角度（0度为水平）
    # 将角度标准化到 [-180, 180] 范围
    if shoulder_angle_degrees > 180:
        shoulder_angle_degrees -= 360
    elif shoulder_angle_degrees < -180:
        shoulder_angle_degrees += 360

    # 计算偏离水平的绝对角度
    deviation_from_horizontal = abs(shoulder_angle_degrees)

    # 如果角度接近180度，说明是水平的（正常状态）
    if deviation_from_horizontal > 90:
        deviation_from_horizontal = 180 - deviation_from_horizontal

    logger.debug(
        f"肩部原始角度: {math.degrees(shoulder_angle):.1f}度, 偏离水平角度: {deviation_from_horizontal:.1f}度, 阈值: {lean_threshold}度")

    # 判断是否超过阈值（偏离水平线太多表示前倾）
    return deviation_from_horizontal > lean_threshold


def is_writing(keypoints_xy, bbox):
    """
    判断是否在板书：
    - 手臂和手腕的高举姿势
    - 手腕与肘部的相对角度（是否弯曲）
    - 肩部是否前倾（作为补充条件）
    """
    logger.info("[板书检测] 开始板书检测...")
    logger.debug("[板书检测] 当前关键点坐标：")
    for idx, (x, y) in enumerate(keypoints_xy):
        logger.debug(f"  {idx} ({POSE_KPT_NAMES[idx] if idx < len(POSE_KPT_NAMES) else idx}): ({x:.1f}, {y:.1f})")

    left_wrist = keypoints_xy[9]  # 左手腕
    right_wrist = keypoints_xy[10]  # 右手腕
    left_elbow = keypoints_xy[7]  # 左肘部
    right_elbow = keypoints_xy[8]  # 右肘部
    left_shoulder = keypoints_xy[5]  # 左肩部
    right_shoulder = keypoints_xy[6]  # 右肩部
    # 检查肩部关键点（必须至少有一个肩部可见）
    left_shoulder_valid = left_shoulder[0] > 0 and left_shoulder[1] > 0
    right_shoulder_valid = right_shoulder[0] > 0 and right_shoulder[1] > 0

    if not (left_shoulder_valid or right_shoulder_valid):
        logger.info("[板书检测] 肩部关键点缺失，无法进行板书检测")
        return False
    # 检查左手臂完整性
    left_arm_valid = (left_shoulder_valid and
                      left_elbow[0] > 0 and left_elbow[1] > 0 and
                      left_wrist[0] > 0 and left_wrist[1] > 0)

    # 检查右手臂完整性
    right_arm_valid = (right_shoulder_valid and
                       right_elbow[0] > 0 and right_elbow[1] > 0 and
                       right_wrist[0] > 0 and right_wrist[1] > 0)
    logger.debug(f"[板书检测] 手臂有效性: 左臂={left_arm_valid}, 右臂={right_arm_valid}")
    # 至少需要一只完整的手臂才能进行板书检测
    if not (left_arm_valid or right_arm_valid):
        logger.info("[板书检测] 没有完整的手臂关键点，无法进行板书检测")
        return False

    # 获取人物框信息
    x1, y1, x2, y2 = bbox
    bbox_height = y2 - y1
    bbox_width = x2 - x1
    center_y = (y1 + y2) / 2

    # 4. 动态调整各种阈值
    is_sitting_posture = is_sitting(keypoints_xy)

    # 手腕高举阈值（根据坐立状态调整）
    if is_sitting_posture:
        threshold_ratio = 0.25  # 坐姿时更严格
        angle_threshold = 130  # 坐姿时肘部角度更严格
        logger.debug("[板书检测] 检测到坐姿，使用严格阈值")
    else:
        threshold_ratio = 0.15  # 站立时相对宽松
        angle_threshold = 140  # 站立时肘部角度稍宽松
        logger.debug("[板书检测] 检测到站姿，使用标准阈值")

    # 动态肩部前倾阈值（基于人物大小）
    shoulder_lean_threshold = max(10, min(20, bbox_height * 0.02))  # 10-20度范围

    logger.debug(
        f"[板书检测] 阈值设置: threshold_ratio={threshold_ratio}, angle_threshold={angle_threshold}, shoulder_diff_threshold={shoulder_lean_threshold:.1f}")
    # 5. 改进的手腕高举判断
    wrist_threshold = center_y - bbox_height * threshold_ratio
    logger.debug(f"[板书检测] 手腕阈值计算: center_y={center_y:.1f}, bbox_height={bbox_height:.1f}, wrist_threshold={wrist_threshold:.1f}")

    wrist_high = False
    left_wrist_valid = left_wrist[0] > 0 and left_wrist[1] > 0
    right_wrist_valid = right_wrist[0] > 0 and right_wrist[1] > 0

    if left_wrist_valid and left_wrist[1] < wrist_threshold:
        wrist_high = True
        logger.debug(f"[板书检测] 左手腕高举: {left_wrist[1]:.1f} < {wrist_threshold:.1f}")
    elif right_wrist_valid and right_wrist[1] < wrist_threshold:
        wrist_high = True
        logger.debug(f"[板书检测] 右手腕高举: {right_wrist[1]:.1f} < {wrist_threshold:.1f}")
    else:
        logger.debug("[板书检测] 手腕未高举")

    # 肘部角度判断（是否弯曲）
    elbow_bent = False
    try:
        # 检查左肘部角度
        if left_arm_valid:
            left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
            logger.debug(f"[板书检测] 左肘部角度: {left_elbow_angle:.1f}°, 阈值={angle_threshold}°")
            if left_elbow_angle < angle_threshold:
                elbow_bent = True
                logger.info("[板书检测] 检测到左肘部弯曲")

        # 检查右肘部角度
        if right_arm_valid:
            right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
            logger.debug(f"[板书检测] 右肘部角度: {right_elbow_angle:.1f}°, 阈值={angle_threshold}°")
            if right_elbow_angle < angle_threshold:
                elbow_bent = True
                logger.info("[板书检测] 检测到右肘部弯曲")

    except Exception as e:
        logger.debug(f"[板书检测] 肘部角度计算失败: {e}")
        elbow_bent = False

    # 7. 板书动作判断（手腕高举 + 肘部弯曲）
    writing_motion = False
    if wrist_high and elbow_bent:
        writing_motion = True
        logger.debug("[板书检测] 检测到板书动作（手腕高举+肘部弯曲）")
        # 补充条件：肩部前倾可以增强判定的置信度
        if left_shoulder_valid and right_shoulder_valid:
            shoulder_lean = check_shoulder_lean(left_shoulder, right_shoulder, bbox, shoulder_lean_threshold)
            if shoulder_lean:
                logger.debug("[板书检测] 肩部前倾进一步确认板书动作")
            else:
                logger.debug("[板书检测] 肩部未前倾，但基于手腕和肘部仍判定为板书")
    else:
        # 如果主要条件不满足，即使肩部前倾也不判定为板书
        if left_shoulder_valid and right_shoulder_valid:
            shoulder_lean = check_shoulder_lean(left_shoulder, right_shoulder, bbox, shoulder_lean_threshold)
            if shoulder_lean:
                logger.debug("[板书检测] 检测到肩部前倾，但手腕未高举或肘部未弯曲，不判定为板书")
            else:
                logger.debug("[板书检测] 肩部未前倾，且手腕未高举或肘部未弯曲，不判定为板书")
        else:
            logger.debug("[板书检测] 肩部关键点不完整，无法检测肩部前倾")
        logger.debug("[板书检测] 主要条件不满足（手腕高举+肘部弯曲），不判定为板书")

    logger.info(f"[板书检测] 板书检测结果: {writing_motion}")

    return writing_motion


def calculate_distance(point1, point2):
    """
    计算两点之间的欧几里得距离
    point1, point2 为 (x, y) 坐标
    """
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def is_calling(keypoints_xy, bbox):
    """
    判断是否在打电话：
    - 手腕与耳朵的距离很近
    - 左右手任一手腕与对应侧耳朵距离小于阈值
    """
    logger.info("[打电话检测] 检测打电话行为...")

    # 关键点索引
    left_ear = keypoints_xy[3]  # 左耳
    right_ear = keypoints_xy[4]  # 右耳
    left_wrist = keypoints_xy[9]  # 左手腕
    right_wrist = keypoints_xy[10]  # 右手腕

    # 检查关键点有效性
    needed_kpts = [3, 4, 9, 10]  # 左耳、右耳、左手腕、右手腕
    missing = []
    for idx in needed_kpts:
        x, y = keypoints_xy[idx]
        if x == 0 or y == 0:
            logger.debug(f"[打电话检测] 关键点{idx}缺失: ({x}, {y})")
            missing.append(idx)

    # 如果关键点缺失过多，无法判断
    if len(missing) >= 3:
        logger.info("[打电话检测] 关键点缺失过多，无法判断打电话行为")
        return False

    # 获取人物框信息，用于动态调整距离阈值
    x1, y1, x2, y2 = bbox
    bbox_height = y2 - y1
    bbox_width = x2 - x1

    # 动态距离阈值：基于人物框大小
    distance_threshold = min(bbox_height, bbox_width) * 0.15  # 人物框较小边的15%
    logger.debug(f"[打电话检测] 距离阈值: {distance_threshold:.1f}")
    calling_detected = False
    # 检查左手腕与左耳距离
    if left_ear[0] > 0 and left_ear[1] > 0 and left_wrist[0] > 0 and left_wrist[1] > 0:
        left_distance = calculate_distance(left_wrist, left_ear)
        logger.debug(f"[打电话检测] 左手腕与左耳距离: {left_distance:.1f}")
        if left_distance < distance_threshold:
            calling_detected = True
            logger.debug("[打电话检测] 检测到左手打电话")
    # 检查右手腕与右耳距离
    if right_ear[0] > 0 and right_ear[1] > 0 and right_wrist[0] > 0 and right_wrist[1] > 0:
        right_distance = calculate_distance(right_wrist, right_ear)
        logger.debug(f"[打电话检测] 右手腕与右耳距离: {right_distance:.1f}")
        if right_distance < distance_threshold:
            calling_detected = True
            logger.debug("[打电话检测] 检测到右手打电话")
    logger.info(f"[打电话检测] 打电话检测结果: {calling_detected}")
    return calling_detected


def detect_pose_behaviors(keypoints_xy, bbox):
    logger.info("========== 开始姿态行为检测 ==========")
    behaviors = {}

    # 判断基本姿态
    if is_sitting(keypoints_xy):
        behaviors['sitting'] = True
        behaviors['standing'] = False
        logger.info("[姿态检测] 基本姿态判定: 坐姿")
    else:
        behaviors['sitting'] = False
        behaviors['standing'] = True
        logger.info("[姿态检测] 基本姿态判定: 站姿")

    # 板书检测（独立于坐立状态，但通常在站立时发生）
    writing_detected = is_writing(keypoints_xy, bbox)
    # 打电话检测（站着或坐着都可以）
    calling_detected = is_calling(keypoints_xy, bbox)

    # 互斥逻辑：板书和打电话不能同时进行
    if writing_detected and calling_detected:
        # 如果同时检测到，优先选择板书（根据业务逻辑调整）
        logger.debug("[姿态检测] 同时检测到板书和打电话，优先选择板书")
        behaviors['writing'] = True
        behaviors['calling'] = False
    elif writing_detected:
        behaviors['writing'] = True
        behaviors['calling'] = False
    elif calling_detected:
        behaviors['writing'] = False
        behaviors['calling'] = True
    else:
        behaviors['writing'] = False
        behaviors['calling'] = False
    return behaviors


def process_teacher_pose_detection(img: np.ndarray, offset: Tuple[int, int], img_size: Tuple[int, int]) -> Dict[str, List[ObjectPosition]]:
    """
    老师姿态检测+ 讲台人员检测
    返回站立、坐着、板书,打电话的检测结果
    """
    logger.info("========== 开始老师姿态检测 ==========")
    ox, oy = offset
    height, width = img_size
    logger.info(f"图像信息: 尺寸=({width}x{height}), 偏移=({ox}, {oy})")
    # 使用姿态检测模型
    results = yolo_teacher_model.predict(img, imgsz=(height, width),half=use_half,verbose=True)

    behavior_results = {
        'platform_person': [],  # 新增
        'standing': [],
        'sitting': [],
        'writing': [],
        'calling': []
    }

    if not results or len(results) == 0:
        return behavior_results

    result = results[0]
    boxes = result.boxes.xyxy if result.boxes is not None else []
    # 先保存讲台人员位置
    for bbox in boxes:
        x1, y1, x2, y2 = map(int, bbox.tolist())
        position = ObjectPosition(
            LeftTopX=x1 + ox,
            LeftTopY=y1 + oy,
            RightBtmX=x2 + ox,
            RightBtmY=y2 + oy
        )
        behavior_results['platform_person'].append(position)
    logger.info(f"[姿态检测] 检测结果: 检测到 {len(behavior_results['platform_person'])} 个讲台人员")
    # logger.info(f"[姿态检测] 检测结果: 检测到 {len(result.boxes) if result.boxes else 0} 个目标")

    # 检查是否有关键点检测结果
    if hasattr(result, 'keypoints') and result.keypoints is not None and len(result.keypoints.xy) > 0:
        # 姿态检测模式
        # logger.debug(f"[姿态检测] 关键点检测: 检测到 {len(result.keypoints.xy)} 个人物的关键点")
        # boxes = result.boxes.xyxy if result.boxes is not None else []

        for i, keypoints_xy in enumerate(result.keypoints.xy):
            logger.info(f"========== 处理第 {i + 1} 个人物 ==========")
            if i < len(boxes):
                bbox = boxes[i].tolist()
                x1, y1, x2, y2 = map(int, bbox)
                logger.debug(f"[姿态检测] 人物边界框: ({x1}, {y1}) -> ({x2}, {y2}), 尺寸: {x2 - x1}x{y2 - y1}")
                # 检测姿态行为
                behaviors = detect_pose_behaviors(keypoints_xy, bbox)
                position = ObjectPosition(
                    LeftTopX=x1 + ox,
                    LeftTopY=y1 + oy,
                    RightBtmX=x2 + ox,
                    RightBtmY=y2 + oy
                )

                # 根据检测结果分类 - 修正版（板书和坐着不能同时满足）
                # 板书检测独立进行
                if behaviors.get('writing', False):
                    behavior_results['writing'].append(position)
                    # 如果检测到板书，强制设置为站立状态
                    behavior_results['standing'].append(position)
                    # 确保不在坐着列表中
                    if position in behavior_results['sitting']:
                        behavior_results['sitting'].remove(position)
                else:
                    # 没有板书时，按原逻辑判断坐立
                    if behaviors.get('sitting', False):
                        behavior_results['sitting'].append(position)
                    else:
                        if behaviors.get('standing', False):
                            behavior_results['standing'].append(position)
                # 打电话检测独立进行
                if behaviors.get('calling', False):
                    behavior_results['calling'].append(position)
        logger.info("========== 老师姿态检测完成 ==========")
    return behavior_results


async def analyze_teacher_behavior(request: Stu_Tea_BehaviorRequest) -> Stu_Tea_BehaviorResponse:
    """
    老师行为分析主函数
    """
    start_time = time.time()
    timestamp = int(time.time())
    logger.info(f"========== 开始老师行为分析 ========== 图片数量: {len(request.ImageList)}")
    # 增加处理计数
    from .capacity_service import increment_connection, increment_processed_images
    increment_connection()
    increment_processed_images(len(request.ImageList))

    processed_image_ids = []
    data_list = []
    # 添加统计变量
    total_stats = {
        'platform_person': 0,
        'standing': 0,
        'sitting': 0,
        'writing': 0,
        'calling': 0
    }
    for image_item in request.ImageList:
        image_start_time = time.time()
        try:
            logger.debug(f"[图片处理] 开始处理图片 {image_item.ImageId}")
            # 解码图片（与学生行为服务相同的逻辑）
            if image_item.StoragePath.startswith('data:') or len(image_item.StoragePath) > 1000:
                # Base64格式
                logger.debug(f"[图片处理] 使用Base64格式解码图片 {image_item.ImageId}")
                if image_item.StoragePath.startswith('data:'):
                    base64_data = image_item.StoragePath.split(',')[1]
                else:
                    base64_data = image_item.StoragePath

                img_data = base64.b64decode(base64_data)
                img_array = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            elif image_item.StoragePath.startswith('http://') or image_item.StoragePath.startswith('https://'):
                # 网络流图片
                logger.debug(f"[图片处理] 从网络URL加载图片 {image_item.ImageId}: {image_item.StoragePath}")
                import requests
                resp = requests.get(image_item.StoragePath, timeout=5)
                img_array = np.frombuffer(resp.content, np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            else:
                # 文件路径
                logger.debug(f"[图片处理] 从本地路径加载图片 {image_item.ImageId}: {image_item.StoragePath}")
                if os.path.isabs(image_item.StoragePath):
                    img_path = image_item.StoragePath
                else:
                    img_path = os.path.join(settings.IMAGE_ROOT, image_item.StoragePath.lstrip('/'))
                img = cv2.imread(img_path)

            if img is None:
                logger.error(f"[图片处理] 图片解码失败: {image_item.ImageId}")
                raise ValueError(f"无法读取图片: {image_item.ImageId}")

            logger.debug(f"[图片处理] 图片解码成功 {image_item.ImageId}, 尺寸: {img.shape[:2]}")
            # 获取原始图像尺寸
            original_height, original_width = img.shape[:2]
            img_size = (original_height, original_width)

            # 处理检测区域
            if image_item.Points:
                logger.debug(f"[图片处理] 应用多边形遮罩，区域点数: {len(image_item.Points)}")
                processed_img, offset = mask_polygon(img, image_item.Points)
            else:
                logger.debug("[图片处理] 使用完整图像，无遮罩区域")
                processed_img, offset = img, (0, 0)

            # 1. 讲台人员检测
            # logger.info("[步骤1] 开始讲台人员检测")
            # platform_positions = process_platform_person_detection(processed_img, offset, img_size)
            # # 2. 姿态行为检测
            # logger.info("[步骤2] 开始老师姿态行为检测（坐着/站着、板书、打电话）")
            # pose_results = process_teacher_pose_detection(processed_img, offset, img_size)

            logger.info("[步骤1+2] 开始讲台 + 姿态行为检测")
            pose_results = process_teacher_pose_detection(processed_img, offset, img_size)

            # 构建结果列表
            result_list = []

            # 讲台是否有人（100）
            # platform_count = len(platform_positions)
            platform_count = len(pose_results['platform_person'])
            result_list.append(ResultItem(
                ObjectType=TEACHER_OBJECT_TYPES['platform_person'],
                ObjectCount=platform_count,
                ObjectPostList=pose_results['platform_person'] if platform_count > 0 else None
            ))

            # result_list.append(ResultItem(
            #     ObjectType=TEACHER_OBJECT_TYPES['platform_person'],
            #     ObjectCount=len(platform_positions),
            #     ObjectPostList=platform_positions if platform_positions else None
            # ))
            total_stats['platform_person'] += platform_count

            # 站立（201）
            standing_count = len(pose_results['standing'])
            result_list.append(ResultItem(
                ObjectType=TEACHER_OBJECT_TYPES['standing'],
                ObjectCount=len(pose_results['standing']),
                ObjectPostList=pose_results['standing'] if pose_results['standing'] else None
            ))
            total_stats['standing'] += standing_count

            # 坐着（202）
            sitting_count = len(pose_results['sitting'])
            result_list.append(ResultItem(
                ObjectType=TEACHER_OBJECT_TYPES['sitting'],
                ObjectCount=len(pose_results['sitting']),
                ObjectPostList=pose_results['sitting'] if pose_results['sitting'] else None
            ))
            total_stats['sitting'] += sitting_count

            # 板书（203）
            writing_count = len(pose_results['writing'])
            result_list.append(ResultItem(
                ObjectType=TEACHER_OBJECT_TYPES['writing'],
                ObjectCount=len(pose_results['writing']),
                ObjectPostList=pose_results['writing'] if pose_results['writing'] else None
            ))
            total_stats['writing'] += writing_count

            # 打电话（204）
            calling_count = len(pose_results['calling'])
            result_list.append(ResultItem(
                ObjectType=TEACHER_OBJECT_TYPES['calling'],
                ObjectCount=len(pose_results['calling']),
                ObjectPostList=pose_results['calling'] if pose_results['calling'] else None
            ))
            total_stats['calling'] += calling_count

            # 计算单张图片耗时
            image_use_time_ms = int((time.time() - image_start_time) * 1000)
            # 构建单张图片结果
            image_result = ImageResult(
                StatusObject={
                    "StatusString": "success",
                    "ImageId": image_item.ImageId,
                    "TimeStamp": timestamp,
                    "UseTimeMs": image_use_time_ms,
                    "StatusCode": 0
                },
                ResultList=result_list
            )

            data_list.append(image_result)
            processed_image_ids.append(image_item.ImageId)

            logger.info(f"Successfully processed teacher image {image_item.ImageId}")

        except Exception as e:
            logger.error(f"[老师行为分析] 处理图片失败 {image_item.ImageId}: {str(e)}", exc_info=True)
            # 添加失败结果
            image_result = ImageResult(
                StatusObject={"StatusString": "failed", "StatusCode": 500},
                ResultList=[]
            )
            data_list.append(image_result)
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
    # 添加最终统计日志
    logger.info(
        f"[最终统计] 讲台:{total_stats['platform_person']} 站立:{total_stats['standing']} 坐着:{total_stats['sitting']} 板书:{total_stats['writing']} 打电话:{total_stats['calling']} | 耗时:{use_time_ms}ms 图片:{len(processed_image_ids)}张")

    return response