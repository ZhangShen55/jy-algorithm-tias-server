from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ai_quality.domain.metrics import StudentFrameMetric, TeacherFrameMetric
from app.services import student_behavior_service as student_service
from app.services import teacher_behavior_service as teacher_service


@dataclass(frozen=True)
class StudentFrameAnalysis:
    metric: StudentFrameMetric


@dataclass(frozen=True)
class TeacherFrameAnalysis:
    metric: TeacherFrameMetric


class FrameAnalyzer:
    def analyze_student_frame(self, minute_no: int, image: np.ndarray) -> StudentFrameMetric:
        img_size: Tuple[int, int] = image.shape[:2]
        offset = (0, 0)
        person_positions = student_service.process_person_detection(image, offset, img_size)
        face_positions = student_service.process_face_detection(image, offset, img_size)
        behavior_results = student_service.process_student_behavior(image, offset, img_size)
        return StudentFrameMetric(
            minute_no=minute_no,
            present_count=len(person_positions),
            face_count=len(face_positions),
            sleep_count=len(behavior_results.get("Sleep", [])),
            phone_count=len(behavior_results.get("Using_phone", [])),
            read_count=len(behavior_results.get("Read_W", [])),
        )

    def analyze_teacher_frame(self, minute_no: int, image: np.ndarray) -> TeacherFrameMetric:
        img_size: Tuple[int, int] = image.shape[:2]
        offset = (0, 0)
        _, behavior_details = teacher_service.process_teacher_behavior_model_detection_with_details(
            image,
            offset,
            img_size,
        )
        if not behavior_details:
            return TeacherFrameMetric(minute_no=minute_no, valid_head_pose=False)

        teacher_position = behavior_details[0]["position"]
        try:
            head_pose = teacher_service.analyze_teacher_head_pose(image, teacher_position)
        except Exception:
            return TeacherFrameMetric(minute_no=minute_no, valid_head_pose=False)

        return self._metric_from_head_pose(minute_no, head_pose)

    @staticmethod
    def _metric_from_head_pose(minute_no: int, head_pose: Optional[object]) -> TeacherFrameMetric:
        if head_pose is None:
            return TeacherFrameMetric(minute_no=minute_no, valid_head_pose=False)
        status = getattr(head_pose, "Status", None)
        if status != "success":
            return TeacherFrameMetric(minute_no=minute_no, valid_head_pose=False)
        return TeacherFrameMetric(
            minute_no=minute_no,
            valid_head_pose=True,
            face_direction=getattr(head_pose, "FaceDirection", "unknown"),
            is_looking_down=bool(getattr(head_pose, "IsLookingDown", False)),
        )
