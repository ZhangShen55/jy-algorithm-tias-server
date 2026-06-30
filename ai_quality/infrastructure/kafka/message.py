from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse


class InvalidTaskMessage(ValueError):
    """Kafka 任务消息缺少关键字段或字段不可用。"""


def _first_present(payload: Mapping[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return None


def _require_http_url(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidTaskMessage(f"{field_name} must be a string URL")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidTaskMessage(f"{field_name} must be a complete HTTP URL")
    return value


@dataclass(frozen=True)
class VisualTaskMessage:
    task_id: str
    teacher_video_url: str
    student_video_url: str
    slides_video_url: Optional[str]
    course_id: Optional[str]
    student_count: int
    raw_payload: Dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "VisualTaskMessage":
        task_id = _first_present(payload, "task_id", "taskId", "taskID")
        if not isinstance(task_id, str) or not task_id.strip():
            raise InvalidTaskMessage("task_id is required")

        teacher_url = _first_present(
            payload,
            "teacher_video_path",
            "teacher_video_url",
            "teacherVideoPath",
            "teacherVideoUrl",
        )
        student_url = _first_present(
            payload,
            "student_video_path",
            "student_video_url",
            "studentVideoPath",
            "studentVideoUrl",
        )
        slides_url = _first_present(
            payload,
            "slides_video_path",
            "slides_video_url",
            "slidesVideoPath",
            "slidesVideoUrl",
        )

        if teacher_url is None:
            raise InvalidTaskMessage("teacher_video is required")
        if student_url is None:
            raise InvalidTaskMessage("student_video is required")

        parsed_slides_url = None
        if slides_url is not None:
            parsed_slides_url = _require_http_url(slides_url, "slides_video")

        raw_student_count = _first_present(payload, "student_count", "studentCount")
        try:
            student_count = int(raw_student_count) if raw_student_count is not None else 50
        except (TypeError, ValueError):
            student_count = 50

        return cls(
            task_id=task_id.strip(),
            teacher_video_url=_require_http_url(teacher_url, "teacher_video"),
            student_video_url=_require_http_url(student_url, "student_video"),
            slides_video_url=parsed_slides_url,
            course_id=_first_present(payload, "course_id", "courseId"),
            student_count=student_count,
            raw_payload=dict(payload),
        )

