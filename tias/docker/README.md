# TIAS Docker 部署说明

`tias/docker/` 存放 TIAS 推理服务部署示例。

当前保留根目录旧文件：

- `tias/Dockerfile`
- `tias/Dockerfile_cuda113`

新部署优先使用：

- `tias/docker/Dockerfile`
- `tias/docker/Dockerfile.cuda113`

构建默认镜像：

```bash
docker build -f tias/docker/Dockerfile -t tias:6.0 .
```

启动单实例：

```bash
docker run -d \
  --name tias-8981 \
  -p 8981:8881 \
  -e CONFIG_PATH=/workspace/tias/config.toml \
  -v "$PWD/tias/config.toml:/workspace/tias/config.toml:ro" \
  -v "$PWD/tias/models:/workspace/tias/models:ro" \
  tias:6.0
```

本地 compose 示例：

```bash
docker compose -f tias/docker/docker-compose.yml up --build
```

多 TIAS 实例必须保证：

- `[TIAS].InstanceId` 唯一
- `[TIAS].BaseUrl` 是 ai_quality-worker 可访问地址
- `[TIAS].MaxConcurrentBatches` 和 `[TIAS].MaxQueueSize` 与机器算力匹配
- `[TIAS].AiQualityBaseUrl` 指向 ai_quality API 地址
