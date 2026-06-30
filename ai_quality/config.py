import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from app.core.config_loader import load_config


class DependencyCheckError(RuntimeError):
    """运行 Worker 所需依赖缺失。"""


def _get_value(config: Mapping[str, object], key: str, default):
    return config.get(key, default)


@dataclass(frozen=True)
class AiQualityConfig:
    kafka_bootstrap_servers: str = "10.67.65.8:9092"
    kafka_topic: str = "classroom_asr_task"
    kafka_group_id: str = "cv-analysis-service"
    db_host: str = "10.67.65.8"
    db_port: int = 23308
    db_user: str = "root"
    db_password: str = "123456"
    db_name: str = "ai_quality"
    snapshot_mount_root: Path = Path("/mnt")
    snapshot_relative_prefix: str = "cv"
    snapshot_scale: float = 0.25
    snapshot_max_total: int = 30
    snapshot_head_up_top_k: int = 3
    snapshot_head_up_min_rate: float = 0.70
    snapshot_read_top_k: int = 3
    snapshot_read_min_rate: float = 0.30
    snapshot_sleep_min_count: int = 2
    snapshot_sleep_min_rate: float = 0.05
    snapshot_phone_min_count: int = 2
    snapshot_phone_min_rate: float = 0.05
    snapshot_teacher_alert_consecutive_frames: int = 3
    snapshot_same_type_min_interval_seconds: int = 90
    behavior_stat_start_minute: int = 3
    behavior_stat_peak_max_segments: int = 5
    temp_root: Path = Path("/tmp/ai-quality")
    frame_interval_seconds: int = 30
    max_task_retries: int = 3
    worker_concurrency: int = 1
    default_student_count: int = 50
    max_frames_per_video: int | None = None

    def check_required_modules(self, module_names: Iterable[str] = ()) -> None:
        missing = [
            module_name
            for module_name in module_names
            if importlib.util.find_spec(module_name) is None
        ]
        if missing:
            raise DependencyCheckError("缺少运行依赖: " + ", ".join(missing))

    def ensure_runtime_dependencies(self) -> None:
        self.check_required_modules(["cv2", "requests", "pymysql", "kafka"])


def load_ai_quality_config(config_path: str) -> AiQualityConfig:
    raw_config = load_config(config_path)
    section = raw_config.get("AI_Quality", {})
    if not isinstance(section, Mapping):
        section = {}

    return AiQualityConfig(
        kafka_bootstrap_servers=str(_get_value(section, "KafkaBootstrapServers", AiQualityConfig.kafka_bootstrap_servers)),
        kafka_topic=str(_get_value(section, "KafkaTopic", AiQualityConfig.kafka_topic)),
        kafka_group_id=str(_get_value(section, "KafkaGroupId", AiQualityConfig.kafka_group_id)),
        db_host=str(_get_value(section, "DBHost", AiQualityConfig.db_host)),
        db_port=int(_get_value(section, "DBPort", AiQualityConfig.db_port)),
        db_user=str(_get_value(section, "DBUser", AiQualityConfig.db_user)),
        db_password=str(_get_value(section, "DBPassword", AiQualityConfig.db_password)),
        db_name=str(_get_value(section, "DBName", AiQualityConfig.db_name)),
        snapshot_mount_root=Path(str(_get_value(section, "SnapshotMountRoot", AiQualityConfig.snapshot_mount_root))),
        snapshot_relative_prefix=str(_get_value(section, "SnapshotRelativePrefix", AiQualityConfig.snapshot_relative_prefix)),
        snapshot_scale=float(_get_value(section, "SnapshotScale", AiQualityConfig.snapshot_scale)),
        snapshot_max_total=int(_get_value(section, "SnapshotMaxTotal", AiQualityConfig.snapshot_max_total)),
        snapshot_head_up_top_k=int(_get_value(section, "SnapshotHeadUpTopK", AiQualityConfig.snapshot_head_up_top_k)),
        snapshot_head_up_min_rate=float(_get_value(section, "SnapshotHeadUpMinRate", AiQualityConfig.snapshot_head_up_min_rate)),
        snapshot_read_top_k=int(_get_value(section, "SnapshotReadTopK", AiQualityConfig.snapshot_read_top_k)),
        snapshot_read_min_rate=float(_get_value(section, "SnapshotReadMinRate", AiQualityConfig.snapshot_read_min_rate)),
        snapshot_sleep_min_count=int(_get_value(section, "SnapshotSleepMinCount", AiQualityConfig.snapshot_sleep_min_count)),
        snapshot_sleep_min_rate=float(_get_value(section, "SnapshotSleepMinRate", AiQualityConfig.snapshot_sleep_min_rate)),
        snapshot_phone_min_count=int(_get_value(section, "SnapshotPhoneMinCount", AiQualityConfig.snapshot_phone_min_count)),
        snapshot_phone_min_rate=float(_get_value(section, "SnapshotPhoneMinRate", AiQualityConfig.snapshot_phone_min_rate)),
        snapshot_teacher_alert_consecutive_frames=int(_get_value(
            section,
            "SnapshotTeacherAlertConsecutiveFrames",
            AiQualityConfig.snapshot_teacher_alert_consecutive_frames,
        )),
        snapshot_same_type_min_interval_seconds=int(_get_value(
            section,
            "SnapshotSameTypeMinIntervalSeconds",
            AiQualityConfig.snapshot_same_type_min_interval_seconds,
        )),
        behavior_stat_start_minute=int(_get_value(
            section,
            "BehaviorStatStartMinute",
            AiQualityConfig.behavior_stat_start_minute,
        )),
        behavior_stat_peak_max_segments=int(_get_value(
            section,
            "BehaviorStatPeakMaxSegments",
            AiQualityConfig.behavior_stat_peak_max_segments,
        )),
        temp_root=Path(str(_get_value(section, "TempRoot", AiQualityConfig.temp_root))),
        frame_interval_seconds=int(_get_value(section, "FrameIntervalSeconds", AiQualityConfig.frame_interval_seconds)),
        max_task_retries=int(_get_value(section, "MaxTaskRetries", AiQualityConfig.max_task_retries)),
        worker_concurrency=int(_get_value(section, "WorkerConcurrency", AiQualityConfig.worker_concurrency)),
        default_student_count=int(_get_value(section, "DefaultStudentCount", AiQualityConfig.default_student_count)),
        max_frames_per_video=(
            int(section["MaxFramesPerVideo"])
            if section.get("MaxFramesPerVideo") not in (None, "", 0, "0")
            else None
        ),
    )
