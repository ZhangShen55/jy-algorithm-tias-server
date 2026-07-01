import logging
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException

from ai_quality.config import AiQualityConfig
from ai_quality.infrastructure.tias.registry import (
    RedisTiasRegistry,
    TiasInstanceStatus,
    TiasRegistry,
)


logger = logging.getLogger(__name__)


class TiasInstanceApi:
    def __init__(self, registry: TiasRegistry, heartbeat_interval_seconds: int = 5, default_ttl_seconds: int = 15):
        self.registry = registry
        self.heartbeat_interval_seconds = int(heartbeat_interval_seconds)
        self.default_ttl_seconds = int(default_ttl_seconds)

    def register(self, payload: Mapping[str, Any]) -> dict:
        instance = self._instance_from_payload(payload)
        ttl_seconds = int(payload.get("heartbeat_timeout_seconds") or self.default_ttl_seconds)
        self.registry.upsert(instance, ttl_seconds=ttl_seconds)
        logger.info(
            "TIAS 注册 instance_id=%s base_url=%s max_concurrent_batches=%s max_queue_size=%s",
            instance.instance_id,
            instance.base_url,
            instance.max_concurrent_batches,
            instance.max_queue_size,
        )
        return {
            "status": "ok",
            "instance_id": instance.instance_id,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
        }

    def heartbeat(self, payload: Mapping[str, Any]) -> dict:
        instance = self._instance_from_payload(payload)
        ttl_seconds = int(payload.get("heartbeat_timeout_seconds") or self.default_ttl_seconds)
        self.registry.upsert(instance, ttl_seconds=ttl_seconds)
        logger.info(
            "TIAS 心跳 instance_id=%s status=%s running_batches=%s queued_batches=%s",
            instance.instance_id,
            instance.status,
            instance.running_batches,
            instance.queued_batches,
        )
        return {
            "status": "ok",
            "instance_id": instance.instance_id,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
        }

    def unregister(self, payload: Mapping[str, Any]) -> dict:
        instance_id = str(payload.get("instance_id") or "").strip()
        if not instance_id:
            raise ValueError("instance_id is required")
        self.registry.unregister(instance_id)
        logger.info("TIAS 注销 instance_id=%s", instance_id)
        return {
            "status": "ok",
            "instance_id": instance_id,
        }

    def _instance_from_payload(self, payload: Mapping[str, Any]) -> TiasInstanceStatus:
        required_fields = ["instance_id", "base_url", "max_concurrent_batches", "max_queue_size"]
        missing = [field for field in required_fields if payload.get(field) in (None, "")]
        if missing:
            raise ValueError("缺少 TIAS 注册字段: " + ",".join(missing))
        return TiasInstanceStatus.from_payload(dict(payload), default_ttl_seconds=self.default_ttl_seconds)


def create_app(registry: TiasRegistry, config: AiQualityConfig | None = None) -> FastAPI:
    app = FastAPI(title="AI课堂质量调度服务", version="6.0")
    heartbeat_interval = 5
    heartbeat_timeout = 15
    if config is not None:
        heartbeat_timeout = config.tias_heartbeat_timeout_seconds
    api = TiasInstanceApi(
        registry,
        heartbeat_interval_seconds=heartbeat_interval,
        default_ttl_seconds=heartbeat_timeout,
    )

    @app.post("/api/tias/instances/register")
    async def register(payload: dict):
        try:
            return api.register(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/tias/instances/heartbeat")
    async def heartbeat(payload: dict):
        try:
            return api.heartbeat(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/tias/instances/unregister")
    async def unregister(payload: dict):
        try:
            return api.unregister(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app


def create_app_from_config(config: AiQualityConfig) -> FastAPI:
    registry = RedisTiasRegistry(
        redis_url=config.redis_url,
        key_prefix=config.redis_key_prefix,
        default_ttl_seconds=config.tias_heartbeat_timeout_seconds,
    )
    return create_app(registry, config)
