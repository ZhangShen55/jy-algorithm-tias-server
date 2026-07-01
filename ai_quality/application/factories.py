from ai_quality.application.worker import VisualAnalysisWorker
from ai_quality.config import load_ai_quality_config
from ai_quality.infrastructure.db.connection import create_mysql_connection
from ai_quality.infrastructure.db.repositories import AiQualityRepository
from ai_quality.infrastructure.media.snapshot_storage import SnapshotStorage
from ai_quality.infrastructure.tias.registry import InMemoryTiasRegistry, RedisTiasRegistry, TiasInstanceStatus
from ai_quality.infrastructure.tias.scheduler import TiasScheduler
from ai_quality.infrastructure.vision.frame_analyzer import FrameAnalyzer
from ai_quality.infrastructure.vision.remote_frame_analyzer import RemoteFrameAnalyzer


def build_worker(config_path: str) -> VisualAnalysisWorker:
    config = load_ai_quality_config(config_path)
    config.ensure_runtime_dependencies()
    storage = SnapshotStorage(config.snapshot_mount_root, config.snapshot_relative_prefix, config.snapshot_scale)
    storage.ensure_writable()
    connection = create_mysql_connection(config)
    repository = AiQualityRepository(connection)
    return VisualAnalysisWorker(
        config=config,
        repository=repository,
        snapshot_storage=storage,
        frame_analyzer=build_frame_analyzer(config),
    )


def build_frame_analyzer(config):
    if config.tias_inference_mode != "remote":
        return FrameAnalyzer()
    try:
        registry = RedisTiasRegistry(
            redis_url=config.redis_url,
            key_prefix=config.redis_key_prefix,
            default_ttl_seconds=config.tias_heartbeat_timeout_seconds,
        )
    except RuntimeError:
        if not config.tias_fallback_instances:
            raise
        registry = InMemoryTiasRegistry(
            key_prefix=config.redis_key_prefix,
            default_ttl_seconds=config.tias_heartbeat_timeout_seconds,
        )
        for index, base_url in enumerate(config.tias_fallback_instances, start=1):
            registry.upsert(TiasInstanceStatus(
                instance_id=f"fallback-tias-{index}",
                base_url=base_url,
                capabilities=["student_behavior", "teacher_behavior", "teacher_head_pose"],
                max_concurrent_batches=1,
                running_batches=0,
                queued_batches=0,
                max_queue_size=0,
                status="UP",
            ))
    scheduler = TiasScheduler(
        registry,
        circuit_breaker_failure_threshold=config.tias_circuit_breaker_failure_threshold,
        circuit_breaker_cooldown_seconds=config.tias_circuit_breaker_cooldown_seconds,
    )
    return RemoteFrameAnalyzer(config, scheduler)
