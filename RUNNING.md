# VBAS 运行文档

## 服务定位

`vbas` 是视觉推理服务，只负责模型加载、学生/教师帧推理、本地准入控制、实例状态和向 `vision_orchestrator` 注册心跳。

`vision_orchestrator` 负责 Kafka 消费、课程任务编排、VBAS 调度、指标聚合和入库。VBAS 不消费 Kafka，也不写课堂质量结果表。

## TensorRT 服务端运行前准备

本分支正式模型只运行TensorRT FP16，保留torch/torchvision供Ultralytics预处理和NMS。Mac可做CPU工具测试，不能启动GPU推理服务。本轮不部署；下方历史Docker章节仅供后续部署评审，现有CUDA11.8镜像尚未针对本Engine验证，不能直接使用。

在指定服务器使用已核验的用户环境 `/home/zhangs/.conda/envs/vbas-trt`，不要在jy-tias/vbas基线环境升级依赖。完整依赖以私有发布清单和验证记录为准，单独 `pip install -r requirements.txt` 不足以建立已验证的TensorRT环境。

项目根 `model/` 必须有person_count.engine、face_count.engine、student.engine、teacher_behavior.engine和manifest.json，来自可信私有发布包；源PT仅用于离线构建/对照和旧版本恢复，不是新服务必需文件。

先执行静态校验，显式GPU检查另开：

```bash
/home/zhangs/.conda/envs/vbas-trt/bin/python scripts/verify_tensorrt_models.py --root model
/home/zhangs/.conda/envs/vbas-trt/bin/python scripts/verify_tensorrt_models.py --root model --gpu --device GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49
```

复制配置示例到一个新的私有文件（不要覆盖现有config.toml），修改IMAGE_ROOT等本机值；保持InferenceBackend=tensorrt、InferenceHalf=true，EngineRoot默认指向项目model/。独立测试设置 `[VBAS].VisionOrchestratorBaseUrl=""`，关闭外部注册；旧接口测试可仅在该私有配置中打开VbasExposeLegacySyncTasks。

```bash
CONFIG_PATH=/绝对路径/私有测试配置.toml CUDA_VISIBLE_DEVICES=GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49 /home/zhangs/.conda/envs/vbas-trt/bin/python -m uvicorn main:app --host 127.0.0.1 --port 18981
```

使用未占用的独立测试端口。所有Engine加载并warmup后才接收服务；缺件/校验不符/无CUDA/不兼容后端明确启动失败，不退PT或CPU，不在线导出/下载。模型固定batch1不限制HTTP请求图片数量，既有逐图和批次准入语义保留。

## 配置说明

VBAS 通过环境变量 `CONFIG_PATH` 读取配置。未设置时默认读取 `config.toml`。

核心配置：

| 配置 | 说明 |
| --- | --- |
| `GPU_ID` | CUDA GPU序号或UUID，推荐UUID；不支持CPU |
| `IMAGE_ROOT` | 相对路径图片读取根目录 |
| `INSTANCE_COUNT` | `start.sh` 多实例数量 |
| `WORKERS_PER_INSTANCE` | 每个 Uvicorn 实例 worker 数 |
| `[VBAS].InstanceId` | 当前 VBAS 实例 ID，必须唯一 |
| `[VBAS].BaseUrl` | 当前 VBAS 实例对 vision_orchestrator 可访问的 HTTP 根地址 |
| `[VBAS].VisionOrchestratorBaseUrl` | vision_orchestrator HTTP 注册服务地址 |
| `[VBAS].VbasExposeLegacySyncTasks` | 是否暴露旧 `/AE/SyncTasks` 和 `/AE/SyncTasks2` |
| `[VBAS].MaxConcurrentBatches` | 当前实例最大并发批次数 |
| `[VBAS].MaxQueueSize` | 本地等待队列长度；`0` 表示不排队，满载直接拒绝 |
| `[VBAS].HeartbeatIntervalSeconds` | 向 vision_orchestrator 上报心跳间隔 |
| `[VBAS].HeartbeatTimeoutSeconds` | vision_orchestrator 侧心跳租约超时时间 |
| `[VBAS].RegisterRetryIntervalSeconds` | 注册失败后的重试间隔 |

单实例配置示例：

```toml
[VBAS]
InstanceId = "vbas-8981"
BaseUrl = "http://127.0.0.1:8981"
VisionOrchestratorBaseUrl = "http://127.0.0.1:9000"
VbasExposeLegacySyncTasks = false
MaxConcurrentBatches = 1
MaxQueueSize = 0
HeartbeatIntervalSeconds = 5
HeartbeatTimeoutSeconds = 15
RegisterRetryIntervalSeconds = 5
Host = "0.0.0.0"
Port = 8981
```

## 启动前依赖

如果需要让 VBAS 被 `vision_orchestrator` 调度，先启动：

1. Redis。
2. `vision_orchestrator` HTTP 注册服务。

示例：

```bash
docker run -d --name vision-orchestrator-redis -p 6379:6379 redis:7-alpine
cd /path/to/jy-vision-orchestrator-server
python -m app.main --config app/config.toml serve
```

VBAS 启动后会读取 `VisionOrchestratorBaseUrl` 并自动调用：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/instances/register` | 启动注册 |
| POST | `/api/instances/heartbeat` | 周期心跳 |
| POST | `/api/instances/unregister` | 关闭注销 |

独立验证必须设置VisionOrchestratorBaseUrl为空字符串，明确关闭注册，而非依赖连接失败重试。

## 本地单实例启动

从仓库根目录执行：

```bash
export CONFIG_PATH="$PWD/config.toml"
uvicorn main:app --host 0.0.0.0 --port 8981 --reload
```

不使用 reload：

```bash
export CONFIG_PATH="$PWD/config.toml"
python -m uvicorn main:app --host 0.0.0.0 --port 8981
```

健康检查：

```bash
curl http://127.0.0.1:8981/AE/Health
```

期望返回：

```json
{"status":"ok","instance_id":"vbas-8981","model_ready":true}
```

查看 worker 状态：

```bash
curl http://127.0.0.1:8981/AE/WorkerStatus
```

## 本地启动 4 个 VBAS 实例

联调时可使用 4 份配置分别启动：

```bash
cp config.toml.example /tmp/vbas-8981.toml
cp config.toml.example /tmp/vbas-8982.toml
cp config.toml.example /tmp/vbas-8983.toml
cp config.toml.example /tmp/vbas-8984.toml
```

分别修改：

| 配置文件 | InstanceId | BaseUrl | 启动端口 |
| --- | --- | --- | ---: |
| `/tmp/vbas-8981.toml` | `vbas-8981` | `http://127.0.0.1:8981` | 8981 |
| `/tmp/vbas-8982.toml` | `vbas-8982` | `http://127.0.0.1:8982` | 8982 |
| `/tmp/vbas-8983.toml` | `vbas-8983` | `http://127.0.0.1:8983` | 8983 |
| `/tmp/vbas-8984.toml` | `vbas-8984` | `http://127.0.0.1:8984` | 8984 |

启动：

```bash
CONFIG_PATH=/tmp/vbas-8981.toml python -m uvicorn main:app --host 127.0.0.1 --port 8981
CONFIG_PATH=/tmp/vbas-8982.toml python -m uvicorn main:app --host 127.0.0.1 --port 8982
CONFIG_PATH=/tmp/vbas-8983.toml python -m uvicorn main:app --host 127.0.0.1 --port 8983
CONFIG_PATH=/tmp/vbas-8984.toml python -m uvicorn main:app --host 127.0.0.1 --port 8984
```

检查端口：

```bash
for port in 8981 8982 8983 8984; do
  curl "http://127.0.0.1:${port}/AE/Health"
  echo
done
```

## 使用 start.sh 启动

`start.sh` 面向容器或 Linux 部署使用，读取 `CONFIG_PATH`。

单实例：

```bash
export CONFIG_PATH="/workspace/vbas/config.toml"
bash start.sh
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
docker/
├── Dockerfile
├── Dockerfile.runtime
├── docker-compose.yml
├── docker-compose.gpu.secure.yml
├── env.example
└── README.md
```

构建镜像：

```bash
docker build -f docker/Dockerfile -t vbas:6.0 .
```

启动容器：

```bash
docker run -d \
  --name vbas-8981 \
  -p 8981:8881 \
  -e CONFIG_PATH=/workspace/vbas/config.toml \
  -v "$PWD/config.toml:/workspace/vbas/config.toml:ro" \
  -v "$PWD/models:/workspace/vbas/models:ro" \
  vbas:6.0
```

如果使用 GPU，需要按部署环境补充 Docker GPU 参数，例如 NVIDIA runtime 的 `--gpus all`，并把 `GPU_ID` 改为对应设备编号。

GPU compose 示例：

```bash
docker compose -f docker/docker-compose.gpu.yml config
docker compose -f docker/docker-compose.gpu.yml up --build
```

宿主机需要提前安装 NVIDIA 驱动、Docker 和 NVIDIA Container Toolkit。

构建 Cython 保护镜像：

```bash
docker build -f docker/Dockerfile \
  --build-arg PROTECT_SOURCE=1 \
  -t vbas:6.0-protected .
```

生产 secure runtime 镜像：

```bash
docker build -f docker/Dockerfile.runtime -t vbas:6.0-secure .
python scripts/check_vbas_runtime_image.py --image vbas:6.0-secure
```

secure runtime 镜像只保留运行入口、必要 `__init__.py`、Cython `.so` 编译产物和 secure entrypoint，不整包复制 VBAS 项目，不包含明文模型、密钥、Docker 文件、部署文档、测试目录和核心明文源码。

## 模型保护部署

默认明文模型模式：

```toml
[ModelProtection]
Enabled = false
```

该模式适合开发或可信内网环境，模型目录建议只读挂载：

```bash
-v "$PWD/models:/workspace/vbas/models:ro"
```

生产可启用静态加密模型模式。先生成密钥并加密模型：

```bash
mkdir -p docker/secrets
python scripts/protect_vbas_models.py \
  --source-dir models \
  --target-dir models-encrypted \
  --key-file docker/secrets/vbas_model_key \
  --generate-key
```

配置：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/vbas/models-encrypted"
DecryptedTempRoot = "/dev/shm/vbas-models"
KeyFile = "/dev/shm/vbas_model_key"
CleanupAfterLoad = true
```

容器挂载：

```bash
-v "$PWD/models-encrypted:/workspace/vbas/models-encrypted:ro"
-v "$PWD/docker/secrets/vbas_model_key:/run/bootstrap-secrets/vbas_model_key:ro"
```

模型加密只保护静态文件，降低镜像或模型目录被直接复制后的离线使用风险。VBAS 运行时仍需要把模型解密并加载到内存，具备宿主机 root、容器调试或进程内存读取权限的人仍可能逆向。生产还需要结合私有镜像仓库、宿主机权限控制、只读挂载、密钥管理和最小权限运行。

如果宿主机删除了被挂载的模型文件，已经加载到内存的运行中进程可能暂时继续工作，但服务重启、懒加载或再次读取模型时会失败。生产不得把“删除后当前进程仍可运行”作为保障。

## 生产 secure runtime 部署

secure runtime 部署使用加密模型和启动期密钥引导，不再挂载整个明文 `models` 目录。准备密钥和加密模型：

```bash
mkdir -p docker/secrets
python scripts/protect_vbas_models.py \
  --source-dir models \
  --target-dir models-encrypted \
  --key-file docker/secrets/vbas_model_key \
  --generate-key
chmod 0400 docker/secrets/vbas_model_key
```

模型保护配置使用运行期密钥副本：

```toml
[ModelProtection]
Enabled = true
EncryptedModelRoot = "/workspace/vbas/models-encrypted"
DecryptedTempRoot = "/dev/shm/vbas-models"
KeyFile = "/dev/shm/vbas_model_key"
CleanupAfterLoad = true
```

secure entrypoint 启动时读取 `/run/bootstrap-secrets/vbas_model_key`，复制到 `/dev/shm/vbas_model_key`。应用第一次读取密钥后会删除 `/dev/shm` 副本，并继续使用内存中的密钥完成后续模型解密。

secure GPU compose 使用外部网络 `vision-orchestrator-net`：

```bash
docker network create vision-orchestrator-net || true
docker network connect vision-orchestrator-net vision-orchestrator-redis || true
docker network connect vision-orchestrator-net vision-orchestrator-api || true
docker compose -f docker/docker-compose.gpu.secure.yml config
docker compose -f docker/docker-compose.gpu.secure.yml up -d --build
```

compose 挂载策略：

```text
models-encrypted -> /workspace/vbas/models-encrypted:ro
docker/secrets/vbas_model_key -> /run/bootstrap-secrets/vbas_model_key:ro
```

为了支持 `docker restart`、容器重建、宿主机重启和故障恢复，宿主机源密钥文件必须保留在受控路径。删除源密钥后，当前进程可能暂时继续运行，但下一次 restart/recreate 会失败。生产不得把删除源密钥作为稳定保护手段。

本阶段不接 KMS/Vault，不承诺防止宿主机 root、Docker socket 持有者、容器 root 或具备调试能力的高权限用户读取挂载源、内存或运行时文件。

Mac 本地只验证 build、compose config、镜像内容检查和单元测试；GPU 加密模型启动、注册心跳和推理接口需要在 128 GPU 服务器验证。

旧根目录 Dockerfile 已删除，部署统一使用 `docker/` 下的文件。

## 对外接口

默认保留：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/ImageDetect/student/v1.0.0` | 学生人数、人脸、睡觉、玩手机、阅读等推理 |
| POST | `/ImageDetect/teacher/v1.0.0` | 教师主体、站立、坐着、板书和讲授推理 |
| GET | `/AE/WorkerStatus` | 实例状态、并发、队列、耗时和失败指标 |
| GET | `/AE/Health` | 健康检查 |
| PUT | `/AE/Drain` | 进入排空状态 |

默认不暴露：

| 路径 | 说明 |
| --- | --- |
| `/AE/SyncTasks` | 旧 IAS 同步任务，`VbasExposeLegacySyncTasks=true` 时启用 |
| `/AE/SyncTasks2` | 旧 IAS base64 同步任务，`VbasExposeLegacySyncTasks=true` 时启用 |

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
VBAS 启动 instance_id=<实例ID> base_url=<地址> max_concurrent_batches=<并发> max_queue_size=<队列>
```

被 vision_orchestrator 调用时应看到：

```text
收到推理批次
批次完成
```

如果实例满载且 `MaxQueueSize=0`，推理接口会返回可重试 busy，vision_orchestrator 会换实例或按配置重试。

## 常见问题

### VBAS 没有注册到 vision_orchestrator

检查顺序：

1. `VisionOrchestratorBaseUrl` 是否正确。
2. vision_orchestrator HTTP 服务是否启动。
3. Redis 是否可用。
4. VBAS 日志中是否有注册失败或心跳失败。

### vision_orchestrator 不能访问 VBAS

检查顺序：

1. `BaseUrl` 是否是 vision_orchestrator 所在机器可访问的地址。
2. 端口是否监听。
3. 防火墙或容器网络是否放通。
4. `/AE/Health` 是否返回 `ok`。

### 模型加载失败

检查顺序：

1. `models/` 下模型文件是否存在。
2. `GPU_ID` 是否与运行环境匹配。
3. CPU 环境是否设置 `GPU_ID = "cpu"`。
4. CUDA 环境的 PyTorch、驱动和容器基础镜像是否匹配。

### 接口返回 busy

说明当前实例已达到 `MaxConcurrentBatches`。处理方式：

1. 增加 VBAS 实例数量。
2. 适当提高 `MaxConcurrentBatches`。
3. 开启小队列，设置 `MaxQueueSize > 0`。
4. 降低 vision_orchestrator 的并发或批大小。
