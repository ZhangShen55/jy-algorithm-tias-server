import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ai_quality.config_loader import load_config


class DependencyCheckError(RuntimeError):
    """运行 Worker 所需依赖缺失。"""


def _get_value(config: Mapping[str, object], key: str, default):
    return config.get(key, default)


@dataclass(frozen=True)
class AiQualityConfig:
    kafka_bootstrap_servers: str = "10.67.65.8:9092"
    kafka_topic: str = "classroom_cv_task"
    kafka_group_id: str = "cv-analysis-service"
    kafka_auto_offset_reset: str = "earliest"
    kafka_max_poll_interval_ms: int = 7200000
    kafka_max_poll_records: int = 1
    http_host: str = "0.0.0.0"
    http_port: int = 9000
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "ai_quality:tias"
    health_check_redis: bool = False
    worker_control_enabled: bool = True
    worker_control_key: str = "change-me"
    worker_control_header_name: str = "X-AI-QUALITY-KEY"
    worker_control_state_key: str = "ai_quality:worker_control:state"
    worker_registry_key_prefix: str = "ai_quality"
    worker_id: str = ""
    worker_controlled_by_redis: bool = True
    worker_default_desired_state: str = "PAUSED"
    worker_heartbeat_interval_seconds: int = 5
    worker_heartbeat_timeout_seconds: int = 30
    worker_poll_when_paused_seconds: int = 5
    worker_stop_exits: bool = False
    tias_inference_mode: str = "remote"
    tias_batch_size: int = 8
    tias_request_timeout_seconds: int = 60
    tias_max_retry_per_batch: int = 3
    tias_busy_retry_delay_seconds: int = 5
    tias_circuit_breaker_failure_threshold: int = 3
    tias_circuit_breaker_cooldown_seconds: int = 30
    tias_heartbeat_timeout_seconds: int = 15
    tias_fallback_instances: tuple[str, ...] = ()
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
    local_video_base_root: Path | None = None
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
        modules = ["cv2", "requests", "pymysql", "kafka"]
        if self.tias_inference_mode == "remote" and not self.tias_fallback_instances:
            modules.append("redis")
        self.check_required_modules(modules)


def load_ai_quality_config(config_path: str) -> AiQualityConfig:
    raw_config = load_config(config_path)
    section = raw_config.get("AI_Quality", {})
    if not isinstance(section, Mapping):
        section = {}

    fallback_instances = _get_value(section, "TiasFallbackInstances", AiQualityConfig.tias_fallback_instances)
    if isinstance(fallback_instances, str):
        fallback_instances = tuple(
            item.strip()
            for item in fallback_instances.split(",")
            if item.strip()
        )
    else:
        fallback_instances = tuple(str(item).strip() for item in fallback_instances if str(item).strip())

    return AiQualityConfig(
        kafka_bootstrap_servers=str(_get_value(section, "KafkaBootstrapServers", AiQualityConfig.kafka_bootstrap_servers)),
        kafka_topic=str(_get_value(section, "KafkaTopic", AiQualityConfig.kafka_topic)),
        kafka_group_id=str(_get_value(section, "KafkaGroupId", AiQualityConfig.kafka_group_id)),
        kafka_auto_offset_reset=str(_get_value(
            section,
            "KafkaAutoOffsetReset",
            AiQualityConfig.kafka_auto_offset_reset,
        )),
        kafka_max_poll_interval_ms=int(_get_value(
            section,
            "KafkaMaxPollIntervalMs",
            AiQualityConfig.kafka_max_poll_interval_ms,
        )),
        kafka_max_poll_records=int(_get_value(
            section,
            "KafkaMaxPollRecords",
            AiQualityConfig.kafka_max_poll_records,
        )),
        http_host=str(_get_value(section, "HttpHost", AiQualityConfig.http_host)),
        http_port=int(_get_value(section, "HttpPort", AiQualityConfig.http_port)),
        redis_url=str(_get_value(section, "RedisUrl", AiQualityConfig.redis_url)),
        redis_key_prefix=str(_get_value(section, "RedisKeyPrefix", AiQualityConfig.redis_key_prefix)),
        health_check_redis=_to_bool(_get_value(section, "HealthCheckRedis", AiQualityConfig.health_check_redis)),
        worker_control_enabled=_to_bool(_get_value(
            section,
            "WorkerControlEnabled",
            AiQualityConfig.worker_control_enabled,
        )),
        worker_control_key=str(_get_value(section, "WorkerControlKey", AiQualityConfig.worker_control_key)),
        worker_control_header_name=str(_get_value(
            section,
            "WorkerControlHeaderName",
            AiQualityConfig.worker_control_header_name,
        )),
        worker_control_state_key=str(_get_value(
            section,
            "WorkerControlStateKey",
            AiQualityConfig.worker_control_state_key,
        )),
        worker_registry_key_prefix=str(_get_value(
            section,
            "WorkerRegistryKeyPrefix",
            AiQualityConfig.worker_registry_key_prefix,
        )),
        worker_id=str(_get_value(section, "WorkerId", AiQualityConfig.worker_id)),
        worker_controlled_by_redis=_to_bool(_get_value(
            section,
            "WorkerControlledByRedis",
            AiQualityConfig.worker_controlled_by_redis,
        )),
        worker_default_desired_state=str(_get_value(
            section,
            "WorkerDefaultDesiredState",
            AiQualityConfig.worker_default_desired_state,
        )),
        worker_heartbeat_interval_seconds=int(_get_value(
            section,
            "WorkerHeartbeatIntervalSeconds",
            AiQualityConfig.worker_heartbeat_interval_seconds,
        )),
        worker_heartbeat_timeout_seconds=int(_get_value(
            section,
            "WorkerHeartbeatTimeoutSeconds",
            AiQualityConfig.worker_heartbeat_timeout_seconds,
        )),
        worker_poll_when_paused_seconds=int(_get_value(
            section,
            "WorkerPollWhenPausedSeconds",
            AiQualityConfig.worker_poll_when_paused_seconds,
        )),
        worker_stop_exits=_to_bool(_get_value(section, "WorkerStopExits", AiQualityConfig.worker_stop_exits)),
        tias_inference_mode=str(_get_value(section, "TiasInferenceMode", AiQualityConfig.tias_inference_mode)),
        tias_batch_size=int(_get_value(section, "TiasBatchSize", AiQualityConfig.tias_batch_size)),
        tias_request_timeout_seconds=int(_get_value(
            section,
            "TiasRequestTimeoutSeconds",
            AiQualityConfig.tias_request_timeout_seconds,
        )),
        tias_max_retry_per_batch=int(_get_value(section, "TiasMaxRetryPerBatch", AiQualityConfig.tias_max_retry_per_batch)),
        tias_busy_retry_delay_seconds=int(_get_value(
            section,
            "TiasBusyRetryDelaySeconds",
            AiQualityConfig.tias_busy_retry_delay_seconds,
        )),
        tias_circuit_breaker_failure_threshold=int(_get_value(
            section,
            "TiasCircuitBreakerFailureThreshold",
            AiQualityConfig.tias_circuit_breaker_failure_threshold,
        )),
        tias_circuit_breaker_cooldown_seconds=int(_get_value(
            section,
            "TiasCircuitBreakerCooldownSeconds",
            AiQualityConfig.tias_circuit_breaker_cooldown_seconds,
        )),
        tias_heartbeat_timeout_seconds=int(_get_value(
            section,
            "TiasHeartbeatTimeoutSeconds",
            AiQualityConfig.tias_heartbeat_timeout_seconds,
        )),
        tias_fallback_instances=fallback_instances,
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
        local_video_base_root=_optional_path(_get_value(
            section,
            "LocalVideoBaseRoot",
            AiQualityConfig.local_video_base_root,
        )),
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


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _optional_path(value) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text)
