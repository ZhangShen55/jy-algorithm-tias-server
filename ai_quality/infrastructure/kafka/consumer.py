import json
import logging
from typing import Callable, Optional

from ai_quality.config import AiQualityConfig
from ai_quality.infrastructure.kafka.message import InvalidTaskMessage, VisualTaskMessage


logger = logging.getLogger(__name__)


class AiQualityKafkaConsumer:
    def __init__(self, consumer, max_retries: int = 3):
        self.consumer = consumer
        self.max_retries = max(1, int(max_retries))

    def consume(
            self,
            handler: Callable[[VisualTaskMessage], None],
            invalid_message_handler: Optional[Callable[[object, Exception], None]] = None,
            limit: Optional[int] = None) -> None:
        processed = 0
        for raw_message in self.consumer:
            try:
                task_message = self._parse_message(raw_message)
            except InvalidTaskMessage as exc:
                logger.error("Kafka 消息不可处理，提交 offset: %s", exc)
                if invalid_message_handler is not None:
                    invalid_message_handler(self._raw_value(raw_message), exc)
                self.consumer.commit()
                processed += 1
                if limit is not None and processed >= limit:
                    break
                continue

            for attempt in range(1, self.max_retries + 1):
                try:
                    handler(task_message)
                    break
                except Exception as exc:
                    logger.warning(
                        "视觉分析任务失败 task_id=%s attempt=%s/%s: %s",
                        task_message.task_id,
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    if attempt >= self.max_retries:
                        break
            self.consumer.commit()
            processed += 1
            if limit is not None and processed >= limit:
                break

    @staticmethod
    def _parse_message(raw_message) -> VisualTaskMessage:
        value = AiQualityKafkaConsumer._raw_value(raw_message)
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise InvalidTaskMessage("Kafka message value must be a JSON object")
        return VisualTaskMessage.from_payload(value)

    @staticmethod
    def _raw_value(raw_message):
        value = raw_message.value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value


def create_kafka_consumer(config: AiQualityConfig):
    try:
        from kafka import KafkaConsumer
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少 kafka-python 依赖，请安装 app/requirements.txt") from exc

    return KafkaConsumer(
        config.kafka_topic,
        bootstrap_servers=config.kafka_bootstrap_servers,
        group_id=config.kafka_group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
