import logging
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from ..core.settings import settings
from .student_behavior_service import process_face_detection, process_person_detection, process_student_behavior
from .teacher_behavior_service import process_teacher_behavior_model_detection
from .teacher_head_pose_service import get_directmhp_backend, get_teacher_head_pose_bool_config


logger = logging.getLogger(__name__)


def run_model_inference_warmup() -> None:
    warmup_config = getattr(settings, "Warmup", {})
    if not _get_bool(warmup_config, "Enabled", True):
        logger.info("模型推理预热已关闭")
        return

    fail_on_error = _get_bool(warmup_config, "FailOnError", True)
    runs = max(1, _get_int(warmup_config, "Runs", 1))
    image_width = max(32, _align32(_get_int(warmup_config, "ImageWidth", 640)))
    image_height = max(32, _align32(_get_int(warmup_config, "ImageHeight", 640)))
    include_head_pose = _get_bool(warmup_config, "IncludeTeacherHeadPose", True)

    try:
        _run_warmup(runs, image_width, image_height, include_head_pose)
    except Exception:
        logger.exception("模型推理预热失败")
        if fail_on_error:
            raise


def _run_warmup(runs: int, image_width: int, image_height: int, include_head_pose: bool) -> None:
    logger.info(
        "开始模型推理预热 runs=%s image_size=%sx%s include_head_pose=%s",
        runs,
        image_width,
        image_height,
        include_head_pose,
    )
    image = np.zeros((image_height, image_width, 3), dtype=np.uint8)
    image_size = (image_height, image_width)
    offset = (0, 0)

    for index in range(runs):
        run_no = index + 1
        _timed_warmup("person_count", lambda: process_person_detection(image, offset, image_size))
        _timed_warmup("face_count", lambda: process_face_detection(image, offset, image_size))
        _timed_warmup("student_behavior", lambda: process_student_behavior(image, offset, image_size))
        _timed_warmup("teacher_behavior", lambda: process_teacher_behavior_model_detection(image, offset, image_size))
        if include_head_pose and get_teacher_head_pose_bool_config("Enabled", False):
            _warmup_teacher_head_pose(image)
        logger.info("模型推理预热轮次完成 run=%s/%s", run_no, runs)

    logger.info("全部模型推理预热完成")


def _timed_warmup(model_name: str, callback) -> None:
    start_time = time.time()
    callback()
    logger.info("模型推理预热完成 model=%s elapsed_ms=%.1f", model_name, (time.time() - start_time) * 1000)


def _warmup_teacher_head_pose(image: np.ndarray) -> None:
    start_time = time.time()
    backend = get_directmhp_backend()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as temp_file:
        cv2.imwrite(temp_file.name, image)
        backend.predict_file(Path(temp_file.name))
    logger.info("模型推理预热完成 model=teacher_head_pose elapsed_ms=%.1f", (time.time() - start_time) * 1000)


def _get_bool(config: Any, key: str, default: bool) -> bool:
    if not isinstance(config, dict):
        return default
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _get_int(config: Any, key: str, default: int) -> int:
    if not isinstance(config, dict):
        return default
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _align32(value: int) -> int:
    return ((value + 31) // 32) * 32
