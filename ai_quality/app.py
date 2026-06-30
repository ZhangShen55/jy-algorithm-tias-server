import argparse
import json
import logging
import os
from pathlib import Path

from ai_quality.application.factories import build_worker
from ai_quality.application.worker import VisualAnalysisWorker
from ai_quality.config import load_ai_quality_config
from ai_quality.infrastructure.kafka.consumer import AiQualityKafkaConsumer, create_kafka_consumer
from ai_quality.infrastructure.kafka.message import VisualTaskMessage


logger = logging.getLogger(__name__)


def load_message_from_json_arg(value: str) -> VisualTaskMessage:
    candidate_path = Path(value)
    if candidate_path.exists():
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(value)
    return VisualTaskMessage.from_payload(payload)


def run_single_json(config_path: str, message_json: str) -> None:
    worker = build_worker(config_path)
    message = load_message_from_json_arg(message_json)
    worker.process_task(message)


def consume(config_path: str) -> None:
    config = load_ai_quality_config(config_path)
    config.ensure_runtime_dependencies()
    worker = build_worker(config_path)
    kafka_consumer = AiQualityKafkaConsumer(
        create_kafka_consumer(config),
        max_retries=config.max_task_retries,
    )
    kafka_consumer.consume(
        worker.process_task,
        invalid_message_handler=lambda payload, error: handle_invalid_message(worker, payload, error),
    )


def handle_invalid_message(worker: VisualAnalysisWorker, payload, error: Exception) -> None:
    if not isinstance(payload, dict):
        return
    task_id = payload.get("task_id") or payload.get("taskId") or payload.get("taskID")
    if not task_id:
        return
    error_msg = str(error)
    worker.repository.mark_workflow_failed(str(task_id), error_msg)
    worker.repository.mark_job_failed(str(task_id), error_msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 课堂质量视觉分析 Worker")
    parser.add_argument(
        "--config",
        default=os.getenv("CONFIG_PATH", "app/config.toml"),
        help="配置文件路径，默认读取 CONFIG_PATH 或 app/config.toml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    consume_parser = subparsers.add_parser("consume", help="从 Kafka 消费视觉分析任务")
    consume_parser.set_defaults(func=lambda args: consume(args.config))

    run_json_parser = subparsers.add_parser("run-json", help="使用 JSON 字符串或 JSON 文件模拟一条 Kafka 消息")
    run_json_parser.add_argument("message_json", help="JSON 字符串或 JSON 文件路径")
    run_json_parser.set_defaults(func=lambda args: run_single_json(args.config, args.message_json))

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
