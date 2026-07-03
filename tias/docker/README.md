# TIAS Docker 部署说明

`tias/docker/` 存放 TIAS 推理服务的 Docker 构建、compose 和配置示例。当前分三类部署路径：

| 路径 | 文件 | 用途 |
| --- | --- | --- |
| 开发/联调 | `Dockerfile`、`docker-compose.yml` | 可挂载明文模型，便于本地排查 |
| 普通 GPU | `Dockerfile`、`docker-compose.gpu.yml` | Cython 保护镜像，可用于可信内网测试 |
| 生产 secure GPU | `Dockerfile.runtime`、`docker-compose.gpu.secure.yml` | 最小运行镜像、加密模型、密钥启动引导 |

旧根目录文件 `tias/Dockerfile`、`tias/Dockerfile_cuda113` 仍保留兼容，新部署优先使用 `tias/docker/`。

## 开发镜像

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

本地 compose：

```bash
docker compose -f tias/docker/docker-compose.yml up --build
```

## 普通 Cython 保护镜像

该镜像会编译 TIAS 自研模块，但仍是开发兼容镜像，不等同于生产最小 runtime 镜像。

```bash
docker build -f tias/docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t tias:6.0-protected .
```

GPU compose：

```bash
docker compose -f tias/docker/docker-compose.gpu.yml config
docker compose -f tias/docker/docker-compose.gpu.yml up --build
```

GPU 宿主机前置条件：

- NVIDIA 驱动可用。
- Docker 可用。
- 已安装 NVIDIA Container Toolkit。

## 生产 secure runtime 镜像

secure runtime 镜像使用多阶段构建，最终镜像只保留运行入口、必要 `__init__.py`、Cython `.so` 编译产物、DirectMHP vendor 和 secure entrypoint，不整包复制 `tias` 项目。

构建：

```bash
docker build -f tias/docker/Dockerfile.runtime -t tias:6.0-secure .
```

镜像内容检查：

```bash
python scripts/check_tias_runtime_image.py --image tias:6.0-secure
```

检查会拒绝明文模型、密钥、Docker/文档/测试目录、非运行文件和核心明文源码。该检查可在 Mac 上执行，不依赖 NVIDIA GPU。

## 加密模型准备

生成密钥并加密模型：

```bash
mkdir -p tias/docker/secrets
python scripts/protect_tias_models.py \
  --source-dir tias/models \
  --target-dir tias/models-encrypted \
  --key-file tias/docker/secrets/tias_model_key \
  --generate-key
chmod 0400 tias/docker/secrets/tias_model_key
```

生产 secure compose 不挂载整个 `tias/models` 明文目录，只挂载：

- `tias/models-encrypted` 到 `/workspace/tias/models-encrypted:ro`
- `tias/models/cmu_panoptic_coco.yaml` 到 `/workspace/tias/model-assets/cmu_panoptic_coco.yaml:ro`
- `tias/docker/secrets/tias_model_key` 到 `/run/bootstrap-secrets/tias_model_key:ro`

secure entrypoint 启动时会把 `/run/bootstrap-secrets/tias_model_key` 复制到 `/dev/shm/tias_model_key`，应用读取后删除 `/dev/shm` 副本。

secure 配置示例：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/tias/models-encrypted"
DecryptedTempRoot = "/dev/shm/tias-models"
KeyFile = "/dev/shm/tias_model_key"
CleanupAfterLoad = true
```

## Docker 网络

TIAS、ai_quality API、ai_quality Worker 和 Redis 必须在同一 Docker 网络内，才能通过容器名互相访问。

```bash
docker network create ai-quality-net || true
docker network connect ai-quality-net ai-quality-redis || true
docker network connect ai-quality-net ai-quality-api || true
```

如果 ai_quality Worker 是独立容器，也需要加入该网络。`docker-compose.gpu.secure.yml` 使用外部网络 `ai-quality-net`，不会自动创建网络。

## 生产 secure GPU compose

启动前确认：

- `ai-quality-net` 已存在。
- `ai-quality-api`、Redis、ai_quality Worker 已在同一网络。
- `tias/docker/secrets/tias_model_key` 存在且非空。
- `tias/models-encrypted/*.enc` 已生成。
- `tias/models/cmu_panoptic_coco.yaml` 存在。

静态检查：

```bash
docker compose -f tias/docker/docker-compose.gpu.secure.yml config
```

启动：

```bash
docker compose -f tias/docker/docker-compose.gpu.secure.yml up -d --build
```

查看日志：

```bash
docker logs -f tias-gpu-8981
docker logs -f tias-gpu-8982
```

关键日志：

```text
运行期模型密钥副本已生成
运行期模型密钥副本已清理
TIAS 启动 instance_id=<实例ID> base_url=<地址> max_concurrent_batches=<并发> max_queue_size=<队列>
```

## restart 语义

为了支持 `docker restart`、容器重建、宿主机重启和故障恢复，宿主机源密钥文件必须保留在受控路径，例如 `tias/docker/secrets/tias_model_key`。

只要源密钥文件仍存在且挂载关系未变，`docker restart tias-gpu-8981` 会重新执行 entrypoint，重新复制 `/dev/shm/tias_model_key` 并允许服务解密模型启动。

如果部署后删除宿主机源密钥文件，当前运行中的进程可能暂时继续工作，但后续 `docker restart`、容器重建或宿主机重启会因为无法读取 `/run/bootstrap-secrets/tias_model_key` 而启动失败。生产不得把“部署后删除源密钥”作为稳定保护方案。

## 安全边界

本阶段不接 KMS/Vault/HSM。当前方案降低的是镜像、明文模型目录和长期密钥文件暴露面，但不承诺防止以下权限读取数据：

- 宿主机 root。
- Docker socket 持有者。
- 容器 root 或具备调试能力的高权限用户。
- 能读取进程内存、挂载源或运行时临时文件的人员。

生产环境仍需要结合私有镜像仓库、宿主机权限控制、只读挂载、最小权限账号、审计和网络隔离。

## 常见问题

### TIAS 容器解析不到 ai-quality-api

检查 TIAS 和 ai_quality API 是否在同一网络：

```bash
docker network inspect ai-quality-net
```

必要时执行：

```bash
docker network connect ai-quality-net ai-quality-api
```

### secure 容器启动后提示密钥源文件不存在

检查宿主机文件：

```bash
ls -l tias/docker/secrets/tias_model_key
```

检查 compose 挂载路径是否是：

```text
./secrets/tias_model_key:/run/bootstrap-secrets/tias_model_key:ro
```

### 模型加载失败

检查顺序：

1. `tias/models-encrypted/` 下是否存在全部 `*.pt.enc`。
2. 密钥是否和加密模型匹配。
3. `/dev/shm` 是否足够，默认 secure compose 配置为 `2g`。
4. `Teacher_Head_Pose.DirectMHPData` 是否指向 `/workspace/tias/model-assets/cmu_panoptic_coco.yaml`。
5. GPU 环境中 `GPU_ID` 和 `Teacher_Head_Pose.Device` 是否为可用设备编号，例如 `"0"`。

### 128 GPU 服务器验证清单

用户在 128 服务器验证时建议按以下顺序执行：

1. `docker network create ai-quality-net || true`
2. 启动 Redis、ai_quality API、ai_quality Worker 并加入 `ai-quality-net`。
3. `docker compose -f tias/docker/docker-compose.gpu.secure.yml up -d --build`
4. 查看 TIAS 日志确认加密模型加载和注册心跳正常。
5. 调用 `/AE/Health`、`/AE/WorkerStatus` 和推理接口。
6. 源密钥文件保留时执行 `docker restart tias-gpu-8981`，确认可恢复。
7. 仅在验证环境模拟删除源密钥后 restart 失败，确认失败原因符合文档说明；生产不要执行该步骤。
