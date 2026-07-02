# ai_quality Docker 部署说明

`ai_quality/docker/` 存放 ai_quality API 和 Worker 的部署示例。

第一版推荐：

- `ai_quality-api` 默认单实例，`uvicorn workers=1`
- `ai_quality-worker` 按 Kafka partition、TIAS 容量和课程并发独立扩容
- Redis 保存 Worker 控制状态、Worker 注册表和 TIAS 注册表
- Nginx 只在部署 2 个 API 实例做高可用时使用

本地示例：

```bash
cp ai_quality/config.toml.example ai_quality/config.toml
docker compose -f ai_quality/docker/docker-compose.yml up --build
```

API 启动命令：

```bash
python -m ai_quality.app --config /workspace/ai_quality/config.toml serve
```

Worker 启动命令：

```bash
python -m ai_quality.app --config /workspace/ai_quality/config.toml worker
```

控制接口示例：

```bash
curl -X POST http://127.0.0.1:9000/api/worker-control/resume \
  -H 'X-AI-QUALITY-KEY: change-me' \
  -H 'Content-Type: application/json' \
  -d '{"updated_by":"operator","reason":"manual resume"}'
```
