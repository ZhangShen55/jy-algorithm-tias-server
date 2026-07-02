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
mkdir -p mnt
docker compose -f ai_quality/docker/docker-compose.yml up --build
```

容器内配置要求：

```toml
SnapshotMountRoot = "/mnt"
RedisUrl = "redis://redis:6379/0"
```

如果不用 compose，而是手动 `docker run`，需要先把 Redis、API 和 Worker 放到同一个 Docker 网络。此时 `config.toml` 中 Redis 地址要使用 Redis 容器名：

```toml
RedisUrl = "redis://ai-quality-redis:6379/0"
```

启动 Redis 容器：

```bash
docker network create ai-quality-net || true
docker run -d \
  --name ai-quality-redis \
  --network ai-quality-net \
  -p 6379:6379 \
  redis:7-alpine
```chrom

如果 Redis 容器已经启动，但还没有加入网络，执行：

```bash
docker network connect ai-quality-net ai-quality-redis || true
```

如果宿主机使用 NFS，先挂载到项目 `mnt`：

```bash
mkdir -p "$PWD/mnt"
mount -t nfs -o nolock,vers=3,tcp 10.80.5.131:/image "$PWD/mnt"
```

构建 Cython 保护镜像：

```bash
docker build -f ai_quality/docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t ai-quality:6.0-protected .
```

API 启动命令：

```bash
python -m ai_quality.app --config /workspace/ai_quality/config.toml serve
```

Worker 启动命令：

```bash
python -m ai_quality.app --config /workspace/ai_quality/config.toml worker
```

Docker run 示例：

```bash
docker run -d \
  --name ai-quality-api \
  --network ai-quality-net \
  -p 9000:9000 \
  -e CONFIG_PATH=/workspace/ai_quality/config.toml \
  -v "$PWD/ai_quality/config.toml:/workspace/ai_quality/config.toml:ro" \
  -v "$PWD/mnt:/mnt" \
  ai-quality:6.0 \
  python -m ai_quality.app --config /workspace/ai_quality/config.toml serve

docker run -d \
  --name ai-quality-worker-1 \
  --network ai-quality-net \
  -e CONFIG_PATH=/workspace/ai_quality/config.toml \
  -e AI_QUALITY_WORKER_ID=worker-1 \
  -v "$PWD/ai_quality/config.toml:/workspace/ai_quality/config.toml:ro" \
  -v "$PWD/mnt:/mnt" \
  ai-quality:6.0 \
  python -m ai_quality.app --config /workspace/ai_quality/config.toml worker
```

2 个 API 实例高可用时，参考 `nginx.conf.example`。Nginx 只代理 API 控制面，不代理 Worker，不提升 Kafka 消费并发。

控制接口示例：

```bash
curl -X POST http://127.0.0.1:9000/api/worker-control/resume \
  -H 'X-AI-QUALITY-KEY: change-me' \
  -H 'Content-Type: application/json' \
  -d '{"updated_by":"operator","reason":"manual resume"}'
```
