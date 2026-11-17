# VBAS Docker 部署说明

`docker/` 存放 VBAS 推理服务的 Docker 构建、compose 和配置示例。当前分三类部署路径：

| 路径 | 文件 | 用途 |
| --- | --- | --- |
| 开发/联调 | `Dockerfile`、`docker-compose.yml` | 可挂载明文模型，便于本地排查 |
| 普通 GPU | `Dockerfile`、`docker-compose.gpu.yml` | Cython 保护镜像，可用于可信内网测试 |
| 生产 secure GPU | `Dockerfile.runtime`、`docker-compose.gpu.secure.yml` | 最小运行镜像、加密模型、密钥启动引导 |
| Ascend NPU | `Dockerfile.npu`、`docker-compose.npu.yml` | 华为 910B / CANN 环境，使用 `torch_npu` |

旧根目录 Dockerfile 已删除，所有新部署统一使用 `docker/` 下的构建入口。

## 开发镜像

构建默认镜像：

```bash
docker build -f docker/Dockerfile -t vbas:6.0 .
```

启动单实例：

```bash
docker run -d \
  --name vbas-8981 \
  -p 8981:8881 \
  -e CONFIG_PATH=/workspace/vbas/config.toml \
  -v "$PWD/config.toml:/workspace/vbas/config.toml:ro" \
  -v "$PWD/models:/workspace/vbas/models:ro" \
  vbas:6.0
```

本地 compose：

```bash
docker compose -f docker/docker-compose.yml up --build
```

## 普通 Cython 保护镜像

该镜像会编译 VBAS 自研模块，但仍是开发兼容镜像，不等同于生产最小 runtime 镜像。

```bash
docker build -f docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t vbas:6.0-protected .
```

GPU compose：

```bash
docker compose -f docker/docker-compose.gpu.yml config
docker compose -f docker/docker-compose.gpu.yml up --build
```

GPU 宿主机前置条件：

- NVIDIA 驱动可用。
- Docker 可用。
- 已安装 NVIDIA Container Toolkit。

## 生产 secure runtime 镜像

secure runtime 镜像使用多阶段构建，最终镜像只保留运行入口、必要 `__init__.py`、Cython `.so` 编译产物和 secure entrypoint，不整包复制 `vbas` 项目。

构建：

```bash
docker build -f docker/Dockerfile.runtime -t vbas:6.0-secure .
```

镜像内容检查：

```bash
python scripts/check_vbas_runtime_image.py --image vbas:6.0-secure
```

检查会拒绝明文模型、密钥、Docker/文档/测试目录、非运行文件和核心明文源码。该检查可在 Mac 上执行，不依赖 NVIDIA GPU。

## 加密模型准备

生成密钥并加密模型：

```bash
mkdir -p docker/secrets
python scripts/protect_vbas_models.py \
  --source-dir models \
  --target-dir models-encrypted \
  --key-file docker/secrets/vbas_model_key \
  --generate-key
chmod 0400 docker/secrets/vbas_model_key
```

生产 secure compose 不挂载整个 `models` 明文目录，只挂载：

- `models-encrypted` 到 `/workspace/vbas/models-encrypted:ro`
- `docker/secrets/vbas_model_key` 到 `/run/bootstrap-secrets/vbas_model_key:ro`

secure entrypoint 启动时会把 `/run/bootstrap-secrets/vbas_model_key` 复制到 `/dev/shm/vbas_model_key`，应用读取后删除 `/dev/shm` 副本。

secure 配置示例：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/vbas/models-encrypted"
DecryptedTempRoot = "/dev/shm/vbas-models"
KeyFile = "/dev/shm/vbas_model_key"
CleanupAfterLoad = true
```

## Docker 网络

同一宿主机上使用容器名互相访问时，VBAS、vision_orchestrator API、vision_orchestrator Worker 和 Redis 必须加入同一 Docker 网络。

## Ascend NPU Docker 部署

NPU 部署使用新增容器，不得停止、重启、删除或改动本机已有运行容器。允许执行 `docker ps`、`docker images`、`docker compose config` 等只读检查；如端口、容器名、网络或设备资源冲突，调整本次新增容器配置，不处理已有容器。

宿主机现有路径保持不变：`/root/config/tias_deploy/`、`/home/xjtu/model_zoo/tias/` 和 `/tmp/shm/tias_model_key` 仍作为挂载源。部署新版时，将 `examples/vbas-npu-<端口>.secure.toml` 内容更新到既有挂载配置文件（原文件名 `tias-npu-<端口>.secure.toml`）；配置节已统一为 `[VBAS]`。镜像内包路径和启动入口使用 `vbas`。CANN、驱动、torch/torch-npu 版本、NPU 编号、端口及设备映射保持原有设置。

910B 验证默认使用：

- NPU 设备：`npu:3`
- 对外端口：`8882`
- 容器名：`vbas-npu-8882`

启动前只读检查：

```bash
npu-smi info
ss -ltnp | grep ':8882' || true
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

如果 8882 已被占用，暂停并确认替代端口，不停止占用端口的进程或容器。

构建和启动 NPU 镜像：

```bash
docker build -f docker/Dockerfile.npu -t vbas:6.0-npu .
docker compose -f docker/docker-compose.npu.yml config
docker compose -f docker/docker-compose.npu.yml up -d --build
```
构建镜像 西交大-910b-npu
```bash
docker build -f docker/Dockerfile.npu \
  --build-arg BUILD_HTTP_PROXY=http://127.0.0.1:18080 \
  --build-arg BUILD_HTTPS_PROXY=http://127.0.0.1:18080 \
  --build-arg PROTECT_SOURCE=1 \
  --network=host \
  -t vbas_910b_npu:v6.0_260709 \
  .
```
拉起 西交大-910b-npu
```bash
docker compose -f docker/docker-compose.npu.yml up -d --force-recreate
```

验证：

```bash
docker exec vbas-npu-8882 python -c "import torch, torch_npu; print(torch.npu.is_available(), torch.npu.device_count())"
curl http://127.0.0.1:8882/AE/Health
```

同一宿主机上使用容器名互相访问时，VBAS、vision_orchestrator API、vision_orchestrator Worker 和 Redis 必须加入同一 Docker 网络：

```bash
docker network create vision-orchestrator-net || true
docker network connect vision-orchestrator-net vision-orchestrator-redis || true
docker network connect vision-orchestrator-net vision-orchestrator-api || true
```

如果 vision_orchestrator Worker 是独立容器，也需要加入该网络。`docker-compose.gpu.secure.yml` 使用外部网络 `vision-orchestrator-net`，不会自动创建网络。

跨服务器部署时不使用 Docker 网络互通。此时 `[VBAS].VisionOrchestratorBaseUrl` 和 `[VBAS].BaseUrl` 必须配置为对端服务器可访问的真实地址，并放通对应端口。

## 生产 secure GPU compose

启动前确认：

- `vision-orchestrator-net` 已存在。
- `vision-orchestrator-api`、Redis、vision_orchestrator Worker 已在同一网络。
- `docker/secrets/vbas_model_key` 存在且非空。
- `models-encrypted/*.enc` 已生成。

静态检查：

```bash
docker compose -f docker/docker-compose.gpu.secure.yml config
```

启动：

```bash
docker compose -f docker/docker-compose.gpu.secure.yml up -d --build
```

查看日志：

```bash
docker logs -f vbas-gpu-8981
docker logs -f vbas-gpu-8982
```

关键日志：

```text
运行期模型密钥副本已生成
运行期模型密钥副本已清理
VBAS 启动 instance_id=<实例ID> base_url=<地址> max_concurrent_batches=<并发> max_queue_size=<队列>
```

## restart 语义

为了支持 `docker restart`、容器重建、宿主机重启和故障恢复，宿主机源密钥文件必须保留在受控路径，例如 `docker/secrets/vbas_model_key`。

只要源密钥文件仍存在且挂载关系未变，`docker restart vbas-gpu-8981` 会重新执行 entrypoint，重新复制 `/dev/shm/vbas_model_key` 并允许服务解密模型启动。

如果部署后删除宿主机源密钥文件，当前运行中的进程可能暂时继续工作，但后续 `docker restart`、容器重建或宿主机重启会因为无法读取 `/run/bootstrap-secrets/vbas_model_key` 而启动失败。生产不得把“部署后删除源密钥”作为稳定保护方案。

## 安全边界

本阶段不接 KMS/Vault/HSM。当前方案降低的是镜像、明文模型目录和长期密钥文件暴露面，但不承诺防止以下权限读取数据：

- 宿主机 root。
- Docker socket 持有者。
- 容器 root 或具备调试能力的高权限用户。
- 能读取进程内存、挂载源或运行时临时文件的人员。

生产环境仍需要结合私有镜像仓库、宿主机权限控制、只读挂载、最小权限账号、审计和网络隔离。

## 常见问题

### VBAS 容器解析不到 vision-orchestrator-api

检查 VBAS 和 vision_orchestrator API 是否在同一网络：

```bash
docker network inspect vision-orchestrator-net
```

必要时执行：

```bash
docker network connect vision-orchestrator-net vision-orchestrator-api
```

### secure 容器启动后提示密钥源文件不存在

检查宿主机文件：

```bash
ls -l docker/secrets/vbas_model_key
```

检查 compose 挂载路径是否是：

```text
./secrets/vbas_model_key:/run/bootstrap-secrets/vbas_model_key:ro
```

### 模型加载失败

检查顺序：

1. `models-encrypted/` 下是否存在全部 `*.pt.enc`。
2. 密钥是否和加密模型匹配。
3. `/dev/shm` 是否足够，默认 secure compose 配置为 `2g`。
4. GPU 环境中 `GPU_ID` 是否为可用设备编号，例如 `"0"`。

### 128 GPU 服务器验证清单

用户在 128 服务器验证时建议按以下顺序执行：

1. `docker network create vision-orchestrator-net || true`
2. 启动 Redis、vision_orchestrator API、vision_orchestrator Worker 并加入 `vision-orchestrator-net`。
3. `docker compose -f docker/docker-compose.gpu.secure.yml up -d --build`
4. 查看 VBAS 日志确认加密模型加载和注册心跳正常。
5. 调用 `/AE/Health`、`/AE/WorkerStatus` 和推理接口。
6. 源密钥文件保留时执行 `docker restart vbas-gpu-8981`，确认可恢复。
7. 仅在验证环境模拟删除源密钥后 restart 失败，确认失败原因符合文档说明；生产不要执行该步骤。
