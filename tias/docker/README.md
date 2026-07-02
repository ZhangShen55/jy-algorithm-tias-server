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

构建 Cython 保护镜像：

```bash
docker build -f tias/docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t tias:6.0-protected .
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

GPU 单实例：

```bash
docker run -d \
  --name tias-gpu-8981 \
  --gpus all \
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

GPU compose 示例：

```bash
docker compose -f tias/docker/docker-compose.gpu.yml config
docker compose -f tias/docker/docker-compose.gpu.yml up --build
```

GPU 宿主机前置条件：

- NVIDIA 驱动可用。
- Docker 可用。
- 已安装 NVIDIA Container Toolkit。

模型加密模式：

```bash
mkdir -p tias/docker/secrets
python scripts/protect_tias_models.py \
  --source-dir tias/models \
  --target-dir tias/models-encrypted \
  --key-file tias/docker/secrets/tias_model_key \
  --generate-key
```

容器挂载：

```bash
-v "$PWD/tias/models-encrypted:/workspace/tias/models-encrypted:ro"
-v "$PWD/tias/docker/secrets/tias_model_key:/run/secrets/tias_model_key:ro"
```

`config.toml`：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/tias/models-encrypted"
DecryptedTempRoot = "/dev/shm/tias-models"
KeyFile = "/run/secrets/tias_model_key"
CleanupAfterLoad = true
```

说明：模型加密保护的是静态文件，不承诺防止高权限运行时逆向。删除宿主机模型文件后，运行中进程可能暂时继续工作，但重启、懒加载或再次读取模型会失败。

多 TIAS 实例必须保证：

- `[TIAS].InstanceId` 唯一
- `[TIAS].BaseUrl` 是 ai_quality-worker 可访问地址
- `[TIAS].MaxConcurrentBatches` 和 `[TIAS].MaxQueueSize` 与机器算力匹配
- `[TIAS].AiQualityBaseUrl` 指向 ai_quality API 地址
