# TIAS 运行文档

## 服务定位

`tias` 是视觉推理服务，只负责模型加载、学生/教师帧推理、本地准入控制、实例状态和向 `ai_quality` 注册心跳。

`ai_quality` 负责 Kafka 消费、课程任务编排、TIAS 调度、指标聚合和入库。TIAS 不消费 Kafka，也不写课堂质量结果表。

## 运行前准备

从仓库根目录执行：

```bash
conda activate jy-tias
pip install -r tias/requirements.txt
```

Mac 本地 CPU 环境可按需使用：

```bash
pip install -r tias/requirements_mac.txt
```

准备配置文件：

```bash
cp tias/config.toml.example tias/config.toml
```

确认模型文件在 `tias/models/` 下：

| 文件 | 说明 |
| --- | --- |
| `person_count.pt` | 人数检测 |
| `face_count.pt` | 人脸/抬头检测 |
| `student.pt` | 学生行为 |
| `teacher_behavior.pt` | 教师行为 |
| `cmu_m_1280_e200_t40_lw010_best.pt` | 教师头姿，可选 |
| `cmu_panoptic_coco.yaml` | 教师头姿数据配置，可选 |

## 配置说明

TIAS 通过环境变量 `CONFIG_PATH` 读取配置。未设置时默认读取 `tias/config.toml`。

核心配置：

| 配置 | 说明 |
| --- | --- |
| `GPU_ID` | `cpu` 表示 CPU；NVIDIA GPU 环境可配置为 `"0"`；Ascend 910B NPU 环境可配置为 `"npu:3"` |
| `IMAGE_ROOT` | 相对路径图片读取根目录 |
| `INSTANCE_COUNT` | `tias/start.sh` 多实例数量 |
| `WORKERS_PER_INSTANCE` | 每个 Uvicorn 实例 worker 数 |
| `[TIAS].InstanceId` | 当前 TIAS 实例 ID，必须唯一 |
| `[TIAS].BaseUrl` | 当前 TIAS 实例对 ai_quality 可访问的 HTTP 根地址 |
| `[TIAS].AiQualityBaseUrl` | ai_quality HTTP 注册服务地址 |
| `[TIAS].TiasExposeLegacySyncTasks` | 是否暴露旧 `/AE/SyncTasks` 和 `/AE/SyncTasks2` |
| `[TIAS].MaxConcurrentBatches` | 当前实例最大并发批次数 |
| `[TIAS].MaxQueueSize` | 本地等待队列长度；`0` 表示不排队，满载直接拒绝 |
| `[TIAS].HeartbeatIntervalSeconds` | 向 ai_quality 上报心跳间隔 |
| `[TIAS].HeartbeatTimeoutSeconds` | ai_quality 侧心跳租约超时时间 |
| `[TIAS].RegisterRetryIntervalSeconds` | 注册失败后的重试间隔 |

## Ascend 910B NPU 启动

当前 910B 验证优先使用宿主机 conda 环境 `tias-910b`，已验证组合：

| 组件 | 版本 |
| --- | --- |
| CANN | `8.1.RC1` |
| Driver | `25.0.rc1.1` |
| Python | `3.10` |
| torch | `2.4.0` |
| torch-npu | `2.4.0` |
| torchvision | `0.19.0` |
| ultralytics | `8.3.156` |

准备依赖：

```bash
conda activate tias-910b
python -m pip install -r tias/requirements_npu.txt
```

验证前只读检查 NPU 3 和端口 8882：

```bash
npu-smi info
ss -ltnp | grep ':8882' || true
```

如果 8882 已被占用，不要停止占用进程或容器，先调整本次新增配置或向负责人确认。

NPU 单实例配置建议：

```toml
GPU_ID = "npu:3"

[TIAS]
InstanceId = "tias-npu-8882"
BaseUrl = "http://127.0.0.1:8882"
Host = "0.0.0.0"
Port = 8882
MaxConcurrentBatches = 1
MaxQueueSize = 0

[Teacher_Head_Pose]
Enabled = false
Device = "npu:3"
```

启动：

```bash
export CONFIG_PATH="$PWD/tias/config.toml"
python -m uvicorn tias.main:app --host 0.0.0.0 --port 8882
```

健康检查：

```bash
curl http://127.0.0.1:8882/AE/Health
```

`ai_quality` 生产模式保持 `TiasInferenceMode=remote`。910B NPU 模型只在 TIAS 进程中加载，ai_quality Worker 通过 HTTP 调度 TIAS，不直接 import TIAS 模型服务。

单实例配置示例：

```toml
[TIAS]
InstanceId = "tias-8981"
BaseUrl = "http://127.0.0.1:8981"
AiQualityBaseUrl = "http://127.0.0.1:9000"
TiasExposeLegacySyncTasks = false
MaxConcurrentBatches = 1
MaxQueueSize = 0
HeartbeatIntervalSeconds = 5
HeartbeatTimeoutSeconds = 15
RegisterRetryIntervalSeconds = 5
Host = "0.0.0.0"
Port = 8981
```

## 启动前依赖

如果需要让 TIAS 被 `ai_quality` 调度，先启动：

1. Redis。
2. `ai_quality` HTTP 注册服务。

示例：

```bash
docker run -d --name ai-quality-redis -p 6379:6379 redis:7-alpine
python -m ai_quality.app --config ai_quality/config.toml serve
```

TIAS 启动后会读取 `AiQualityBaseUrl` 并自动调用：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tias/instances/register` | 启动注册 |
| POST | `/api/tias/instances/heartbeat` | 周期心跳 |
| POST | `/api/tias/instances/unregister` | 关闭注销 |

如果只想单独调试 TIAS 推理接口，可以不启动 ai_quality；此时注册和心跳会失败重试，但本地推理接口仍可用于调试。

## 本地单实例启动

从仓库根目录执行：

```bash
export CONFIG_PATH="$PWD/tias/config.toml"
uvicorn tias.main:app --host 0.0.0.0 --port 8981 --reload
```

不使用 reload：

```bash
export CONFIG_PATH="$PWD/tias/config.toml"
python -m uvicorn tias.main:app --host 0.0.0.0 --port 8981
```

健康检查：

```bash
curl http://127.0.0.1:8981/AE/Health
```

期望返回：

```json
{"status":"ok","instance_id":"tias-8981","model_ready":true}
```

查看 worker 状态：

```bash
curl http://127.0.0.1:8981/AE/WorkerStatus
```

## 本地启动 4 个 TIAS 实例

联调时可使用 4 份配置分别启动：

```bash
cp tias/config.toml.example /tmp/tias-8981.toml
cp tias/config.toml.example /tmp/tias-8982.toml
cp tias/config.toml.example /tmp/tias-8983.toml
cp tias/config.toml.example /tmp/tias-8984.toml
```

分别修改：

| 配置文件 | InstanceId | BaseUrl | 启动端口 |
| --- | --- | --- | ---: |
| `/tmp/tias-8981.toml` | `tias-8981` | `http://127.0.0.1:8981` | 8981 |
| `/tmp/tias-8982.toml` | `tias-8982` | `http://127.0.0.1:8982` | 8982 |
| `/tmp/tias-8983.toml` | `tias-8983` | `http://127.0.0.1:8983` | 8983 |
| `/tmp/tias-8984.toml` | `tias-8984` | `http://127.0.0.1:8984` | 8984 |

启动：

```bash
CONFIG_PATH=/tmp/tias-8981.toml python -m uvicorn tias.main:app --host 127.0.0.1 --port 8981
CONFIG_PATH=/tmp/tias-8982.toml python -m uvicorn tias.main:app --host 127.0.0.1 --port 8982
CONFIG_PATH=/tmp/tias-8983.toml python -m uvicorn tias.main:app --host 127.0.0.1 --port 8983
CONFIG_PATH=/tmp/tias-8984.toml python -m uvicorn tias.main:app --host 127.0.0.1 --port 8984
```

检查端口：

```bash
for port in 8981 8982 8983 8984; do
  curl "http://127.0.0.1:${port}/AE/Health"
  echo
done
```

## 使用 start.sh 启动

`tias/start.sh` 面向容器或 Linux 部署使用，读取 `CONFIG_PATH`。

单实例：

```bash
export CONFIG_PATH="/workspace/tias/config.toml"
bash tias/start.sh
```

多实例：

```toml
INSTANCE_COUNT = 4
WORKERS_PER_INSTANCE = 1
```

多实例模式下，脚本会：

1. 从 8981 开始启动多个 Uvicorn 后端。
2. 生成 Nginx upstream。
3. 通过 8881 暴露统一入口。

说明：`start.sh` 中单实例默认监听 8881；手动 `uvicorn` 启动时以命令行端口为准。

## Docker 启动

部署资产集中在：

```text
tias/docker/
├── Dockerfile
├── Dockerfile.cuda113
├── Dockerfile.runtime
├── docker-compose.yml
├── docker-compose.gpu.secure.yml
├── env.example
└── README.md
```

构建镜像：

```bash
docker build -f tias/docker/Dockerfile -t tias:6.0 .
```

启动容器：

```bash
docker run -d \
  --name tias-8981 \
  -p 8981:8881 \
  -e CONFIG_PATH=/workspace/tias/config.toml \
  -v "$PWD/tias/config.toml:/workspace/tias/config.toml:ro" \
  -v "$PWD/tias/models:/workspace/tias/models:ro" \
  tias:6.0
```

如果使用 GPU，需要按部署环境补充 Docker GPU 参数，例如 NVIDIA runtime 的 `--gpus all`，并把 `GPU_ID` 改为对应设备编号。

GPU compose 示例：

```bash
docker compose -f tias/docker/docker-compose.gpu.yml config
docker compose -f tias/docker/docker-compose.gpu.yml up --build
```

宿主机需要提前安装 NVIDIA 驱动、Docker 和 NVIDIA Container Toolkit。

构建 Cython 保护镜像：

```bash
docker build -f tias/docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t tias:6.0-protected .
```

生产 secure runtime 镜像：

```bash
docker build -f tias/docker/Dockerfile.runtime -t tias:6.0-secure .
python scripts/check_tias_runtime_image.py --image tias:6.0-secure
```

secure runtime 镜像只保留运行入口、必要 `__init__.py`、Cython `.so` 编译产物、DirectMHP vendor 和 secure entrypoint，不整包复制 TIAS 项目，不包含明文模型、密钥、Docker 文件、部署文档、测试目录和核心明文源码。

## 模型保护部署

默认明文模型模式：

```toml
[ModelProtection]
Enabled = false
```

该模式适合开发或可信内网环境，模型目录建议只读挂载：

```bash
-v "$PWD/tias/models:/workspace/tias/models:ro"
```

生产可启用静态加密模型模式。先生成密钥并加密模型：

```bash
mkdir -p tias/docker/secrets
python scripts/protect_tias_models.py \
  --source-dir tias/models \
  --target-dir tias/models-encrypted \
  --key-file tias/docker/secrets/tias_model_key \
  --generate-key
```

配置：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/tias/models-encrypted"
DecryptedTempRoot = "/dev/shm/tias-models"
KeyFile = "/dev/shm/tias_model_key"
CleanupAfterLoad = true
```

容器挂载：

```bash
-v "$PWD/tias/models-encrypted:/workspace/tias/models-encrypted:ro"
-v "$PWD/tias/docker/secrets/tias_model_key:/run/bootstrap-secrets/tias_model_key:ro"
```

模型加密只保护静态文件，降低镜像或模型目录被直接复制后的离线使用风险。TIAS 运行时仍需要把模型解密并加载到内存，具备宿主机 root、容器调试或进程内存读取权限的人仍可能逆向。生产还需要结合私有镜像仓库、宿主机权限控制、只读挂载、密钥管理和最小权限运行。

如果宿主机删除了被挂载的模型文件，已经加载到内存的运行中进程可能暂时继续工作，但服务重启、懒加载或再次读取模型时会失败。生产不得把“删除后当前进程仍可运行”作为保障。

## 生产 secure runtime 部署

secure runtime 部署使用加密模型和启动期密钥引导，不再挂载整个明文 `tias/models` 目录。准备密钥和加密模型：

```bash
mkdir -p tias/docker/secrets
python scripts/protect_tias_models.py \
  --source-dir tias/models \
  --target-dir tias/models-encrypted \
  --key-file tias/docker/secrets/tias_model_key \
  --generate-key
chmod 0400 tias/docker/secrets/tias_model_key
```

模型保护配置使用运行期密钥副本：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/tias/models-encrypted"
DecryptedTempRoot = "/dev/shm/tias-models"
KeyFile = "/dev/shm/tias_model_key"
CleanupAfterLoad = true
```

secure entrypoint 启动时读取 `/run/bootstrap-secrets/tias_model_key`，复制到 `/dev/shm/tias_model_key`。应用第一次读取密钥后会删除 `/dev/shm` 副本，并继续使用内存中的密钥完成后续模型解密。

secure GPU compose 使用外部网络 `ai-quality-net`：

```bash
docker network create ai-quality-net || true
docker network connect ai-quality-net ai-quality-redis || true
docker network connect ai-quality-net ai-quality-api || true
docker compose -f tias/docker/docker-compose.gpu.secure.yml config
docker compose -f tias/docker/docker-compose.gpu.secure.yml up -d --build
```

compose 挂载策略：

```text
tias/models-encrypted -> /workspace/tias/models-encrypted:ro
tias/models/cmu_panoptic_coco.yaml -> /workspace/tias/model-assets/cmu_panoptic_coco.yaml:ro
tias/docker/secrets/tias_model_key -> /run/bootstrap-secrets/tias_model_key:ro
```

为了支持 `docker restart`、容器重建、宿主机重启和故障恢复，宿主机源密钥文件必须保留在受控路径。删除源密钥后，当前进程可能暂时继续运行，但下一次 restart/recreate 会失败。生产不得把删除源密钥作为稳定保护手段。

本阶段不接 KMS/Vault，不承诺防止宿主机 root、Docker socket 持有者、容器 root 或具备调试能力的高权限用户读取挂载源、内存或运行时文件。

Mac 本地只验证 build、compose config、镜像内容检查和单元测试；GPU 加密模型启动、注册心跳和推理接口需要在 128 GPU 服务器验证。

旧根目录 Dockerfile 已删除，部署统一使用 `tias/docker/` 下的文件。

## 对外接口

默认保留：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/ImageDetect/student/v1.0.0` | 学生人数、人脸、睡觉、玩手机、阅读等推理 |
| POST | `/ImageDetect/teacher/v1.0.0` | 教师行为和可选头姿推理 |
| GET | `/AE/WorkerStatus` | 实例状态、并发、队列、耗时和失败指标 |
| GET | `/AE/Health` | 健康检查 |
| PUT | `/AE/Drain` | 进入排空状态 |

默认不暴露：

| 路径 | 说明 |
| --- | --- |
| `/AE/SyncTasks` | 旧 IAS 同步任务，`TiasExposeLegacySyncTasks=true` 时启用 |
| `/AE/SyncTasks2` | 旧 IAS base64 同步任务，`TiasExposeLegacySyncTasks=true` 时启用 |

6.0 默认移除：

```text
/AE/Capacity
/AE/Capacity_v2
/AE/Version
/AE/LogLevel
/ImageDetect/student/v1.0.1
```

OpenAPI：

```text
http://127.0.0.1:8981/docs
```

## 推理接口冒烟检查

健康检查：

```bash
curl http://127.0.0.1:8981/AE/Health
```

Worker 状态：

```bash
curl http://127.0.0.1:8981/AE/WorkerStatus
```

排空：

```bash
curl -X PUT http://127.0.0.1:8981/AE/Drain
```

进入排空后，该实例不再接收新批次。重新接收任务需要重启实例。

## 日志关注点

启动时应看到：

```text
TIAS 启动 instance_id=<实例ID> base_url=<地址> max_concurrent_batches=<并发> max_queue_size=<队列>
```

被 ai_quality 调用时应看到：

```text
收到推理批次
批次完成
```

如果实例满载且 `MaxQueueSize=0`，推理接口会返回可重试 busy，ai_quality 会换实例或按配置重试。

## 常见问题

### TIAS 没有注册到 ai_quality

检查顺序：

1. `AiQualityBaseUrl` 是否正确。
2. ai_quality HTTP 服务是否启动。
3. Redis 是否可用。
4. TIAS 日志中是否有注册失败或心跳失败。

### ai_quality 不能访问 TIAS

检查顺序：

1. `BaseUrl` 是否是 ai_quality 所在机器可访问的地址。
2. 端口是否监听。
3. 防火墙或容器网络是否放通。
4. `/AE/Health` 是否返回 `ok`。

### 模型加载失败

检查顺序：

1. `tias/models/` 下模型文件是否存在。
2. `GPU_ID` 是否与运行环境匹配。
3. CPU 环境是否设置 `GPU_ID = "cpu"`。
4. CUDA 环境的 PyTorch、驱动和容器基础镜像是否匹配。

### 接口返回 busy

说明当前实例已达到 `MaxConcurrentBatches`。处理方式：

1. 增加 TIAS 实例数量。
2. 适当提高 `MaxConcurrentBatches`。
3. 开启小队列，设置 `MaxQueueSize > 0`。
4. 降低 ai_quality 的并发或批大小。
