from ai_quality.application.worker import VisualAnalysisWorker
from ai_quality.config import load_ai_quality_config
from ai_quality.infrastructure.db.connection import create_mysql_connection
from ai_quality.infrastructure.db.repositories import AiQualityRepository
from ai_quality.infrastructure.media.snapshot_storage import SnapshotStorage


def build_worker(config_path: str) -> VisualAnalysisWorker:
    config = load_ai_quality_config(config_path)
    config.ensure_runtime_dependencies()
    storage = SnapshotStorage(config.snapshot_mount_root, config.snapshot_relative_prefix, config.snapshot_scale)
    storage.ensure_writable()
    connection = create_mysql_connection(config)
    repository = AiQualityRepository(connection)
    return VisualAnalysisWorker(config=config, repository=repository, snapshot_storage=storage)
