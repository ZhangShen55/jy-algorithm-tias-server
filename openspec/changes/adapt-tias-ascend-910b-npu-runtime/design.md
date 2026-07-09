## Context

TIAS 当前在启动时由 `tias/core/settings.py` 全局加载四个 Ultralytics YOLO 模型，设备选择逻辑只有 `cpu` 和 CUDA 两种路径：非 `cpu` 时设置 `CUDA_VISIBLE_DEVICES` 并使用 `torch.cuda.is_available()` 判断设备。这个逻辑在 Ascend 910B 上不可用，因为 NPU 需要先加载 `torch_npu`，并通过 `torch.device("npu:<index>")` 或 `torch.npu` API 访问。

`ai_quality` 生产链路默认使用 `TiasInferenceMode=remote`，只通过 HTTP 调度 TIAS，不直接加载模型。因此本次适配重点是 TIAS 运行时、TIAS Docker 部署和验证流程；`ai_quality` 只需要保留远程调度验证。

当前服务器事实：

- 架构为 `aarch64`。
- `npu-smi` 可见 8 张 `910B3`。
- CANN 指向 `8.1.RC1`，driver 为 `25.0.rc1.1`。
- 现有 conda 环境 `tias-910b` 已安装 `torch==2.4.0`、`torch-npu==2.4.0`、`torchvision==0.19.0`、`ultralytics==8.3.156`。
- 已用 NPU 实测 `YOLO(...).to(torch.device("npu:0")).predict(...)` 可运行。
- 已绕过 DirectMHP vendor `select_device()` 实测 `attempt_load(..., map_location=torch.device("npu:0"))` 可运行。

验证阶段必须优先使用 NPU 3 号卡，因为用户说明当前只有该卡还有可用显存。TIAS 服务端口固定使用 `8882`，避免占用既有 `8881` 或其它正在使用的端口。

本机已有 Docker 容器属于现场运行环境，本变更实施和验证期间禁止停止、重启、删除或改动任何已有容器；Docker 验证只能新增本次 NPU 适配相关镜像和容器，并使用唯一名称避免冲突。

## Goals / Non-Goals

**Goals:**

- 在新分支 `dev_6.0_ai_quality_910b_npu` 上完成 910B NPU 适配，不影响原 `dev_6.0_ai_quality` 分支。
- 让 TIAS 支持 `GPU_ID = "npu:3"` 并把主 YOLO 模型加载到 NPU 3 号卡。
- 让可选 DirectMHP 教师头姿支持 `Teacher_Head_Pose.Device = "npu:3"`。
- 优先复用 `tias-910b` conda 环境完成源码运行验证。
- 新增 Ascend NPU Docker 适配文件和部署文档，用于后续容器化运行。
- 使用 `test/` 目录图片完成单服务推理、远程 ai_quality 调度和 Docker 启动验证。
- 源码和 Docker 验证统一使用端口 `8882`。
- Docker 验证不影响本机已有运行容器。
- 保持 CPU 和 NVIDIA CUDA 既有配置方式可用。

**Non-Goals:**

- 不重训、不转换模型，不引入 ONNX、OM、TensorRT 或 ATC 模型格式转换。
- 不改动 HTTP API 请求/响应格式。
- 不把 `ai_quality` 生产模式改成本地模型推理。
- 不调整 Kafka、Redis、数据库业务语义。
- 不在本变更中优化模型精度或重新标定阈值。

## Decisions

### 1. 新增统一设备解析 helper

新增 `tias/core/device.py` 或等价模块，提供一个小型函数，例如 `resolve_torch_device(raw_device, prefer_accelerator=True)`，集中处理：

- `cpu` -> `torch.device("cpu")`
- `npu` -> `torch.device("npu:0")`
- `npu:3` -> `torch.device("npu:3")`
- `cuda:0` -> `torch.device("cuda:0")`
- `"0"` -> 为保持兼容，默认继续按 CUDA 编号解释

理由：当前主 YOLO 和 DirectMHP 有两套设备逻辑，若只在 `settings.py` 中临时加分支，DirectMHP 仍会继续走 CUDA-only vendor `select_device()`。抽 helper 可以让两个模型路径共用判断，并避免后续再复制 `torch_npu` 导入逻辑。

备选方案：升级 Ultralytics 到支持 NPU 的新版本。暂不采用，因为当前环境已验证 `ultralytics==8.3.156` 可通过 `.to(torch.device("npu:3"))` 运行，升级会扩大依赖风险，可能影响模型加载和结果稳定性。

### 2. NPU 模式显式 import `torch_npu`

当解析到 `npu` 设备时，运行时必须显式 `import torch_npu`，再检查 `torch.npu.is_available()` 和设备数量。

理由：PyTorch 只有在加载 `torch_npu` 扩展后才注册 NPU backend。缺失 `torch_npu` 时要尽早报出可诊断错误，而不是静默回退 CPU。

备选方案：在模块顶部无条件 import `torch_npu`。暂不采用，因为 CPU/NVIDIA 环境不应强依赖 NPU 包。

### 3. NPU 模式不设置 `CUDA_VISIBLE_DEVICES`

`GPU_ID = "npu:3"` 时不设置 `CUDA_VISIBLE_DEVICES`。如果需要限制 NPU 可见卡，优先在 Docker/启动脚本层使用 Ascend 运行时约定；应用层只根据配置选择 `torch.device("npu:3")`。

理由：`CUDA_VISIBLE_DEVICES` 是 NVIDIA 语义，在 Ascend 环境中没有意义，反而会混淆日志和诊断。

### 4. DirectMHP 绕开 vendor CUDA-only `select_device()`

`teacher_head_pose_service.py` 在加载 DirectMHP 时不再依赖 `tias/vendor/DirectMHP/utils/torch_utils.py::select_device()` 解析 NPU。它应使用项目统一 helper 得到 `torch.device`，然后传给 `attempt_load(..., map_location=device)`。

理由：vendor `select_device()` 会对非 CPU 设备强制检查 `torch.cuda.is_available()`，在 910B 上必然失败。直接传 NPU device 已经通过手工验证。

备选方案：修改 vendor `select_device()` 支持 NPU。暂不优先采用，因为 vendor 目录来自 DirectMHP，局部绕开更小、更容易回滚；只有当其它 DirectMHP 路径也必须调用该函数时再补丁 vendor。

### 5. Docker 采用新增 Ascend 专用文件且不影响已有容器

新增类似 `tias/docker/Dockerfile.npu`、`tias/docker/docker-compose.npu.yml` 和示例配置，不覆盖现有 `Dockerfile`、`Dockerfile.cuda113`、`Dockerfile.runtime`、`docker-compose.gpu*.yml`。

理由：NVIDIA Docker 与 Ascend Docker 的 runtime、设备挂载、CANN 环境变量和基础镜像不同。新增文件可以保留现有交付路径，降低回归风险。

Docker 操作边界：

- 允许 `docker ps`、`docker images`、`docker compose config` 等只读检查。
- 允许构建本次 NPU 镜像。
- 允许启动本次 NPU 验证容器，容器名需带 `tias-npu-8882` 或等价唯一前缀。
- 禁止对已有容器执行 `docker stop`、`docker restart`、`docker rm`、`docker compose down` 或等价操作。
- 如果端口、容器名、网络或设备资源冲突，必须调整本次新增容器配置，不得处理已有容器。

Docker 适配优先级：

1. 先在宿主机 `tias-910b` conda 环境跑通源码。
2. 再根据现有部署 Dockerfile 改造 Ascend NPU 镜像。
3. 最后验证容器可见 NPU 3 号卡、CANN 环境、`torch_npu` 和 TIAS `8882` HTTP 推理。

### 6. 验证固定使用 NPU 3 和端口 8882

所有 NPU 验证配置使用：

```toml
GPU_ID = "npu:3"
Port = 8882

[Teacher_Head_Pose]
Device = "npu:3"
```

理由：当前 NPU 3 号卡显存可用，其它卡已有进程占用；`8882` 是本次用户指定端口。验证报告中必须记录 `npu-smi info` 片段、TIAS 日志中的 device 和实际监听端口。

## Risks / Trade-offs

- `ultralytics==8.3.156` 官方 `select_device()` 不认识 NPU -> 通过显式 `.to(torch.device("npu:3"))` 绕开；验证必须覆盖 `.predict()`。
- `torch_npu` 算子覆盖可能和 CUDA 不完全一致 -> 保持 FP32，使用 `test/` 图片做行为接口冒烟和输出结构校验，不把数值完全等同作为硬性条件。
- DirectMHP 可能在真实图片上触发未覆盖算子 -> 将教师头姿作为单独验证项；如失败，可保持 `Teacher_Head_Pose.Enabled=false` 作为主链路兜底，并记录风险。
- Docker 基础镜像和 CANN 版本可能与宿主机不匹配 -> Docker 阶段必须先输出 CANN/driver/torch_npu 版本，再启动 TIAS。
- Docker 验证误影响已有容器 -> 只允许新增本次容器；发现冲突时调整本次配置，不对已有容器执行停止、重启或删除。
- `8882` 端口可能被占用 -> 验证前只读检查端口占用；如被占用，暂停并向用户确认，不自动停止占用进程或容器。
- NPU 3 显存仍可能被其它进程占用 -> 验证前后执行 `npu-smi info`，任务中保留显存不足时的诊断步骤。
- 多 worker 启动会重复加载模型占用显存 -> NPU 验证默认 `WORKERS_PER_INSTANCE=1`、`MaxConcurrentBatches=1`，扩容另行评估。

## Migration Plan

1. 在 `dev_6.0_ai_quality_910b_npu` 分支实施 NPU 设备解析和文档变更。
2. 在宿主机激活 `tias-910b`，补齐 `tias/requirements.txt` 中缺失依赖。
3. 使用 `GPU_ID = "npu:3"` 和端口 `8882` 启动 TIAS，验证健康检查和 `test/` 图片推理。
4. 启动 ai_quality HTTP/Worker 所需依赖，验证 ai_quality 仍通过远程 TIAS 调度。
5. 构建并运行 Ascend NPU Docker 镜像，使用新增容器验证容器内 `torch_npu`、NPU 3 和 TIAS `8882` HTTP 推理，不操作已有容器。
6. 回滚策略：保留原 CUDA/CPU 配置不变，生产若 NPU 路径不可用，可切回 `GPU_ID = "cpu"` 或回退到原 NVIDIA 部署分支/镜像。

## Open Questions

- 用户已有的部署 Dockerfile 是否在仓库外，还是指当前 `tias/docker/*` 文件；实施前需要对实际部署文件做一次读取确认。
- Docker 运行时是否已有 Ascend Docker Runtime / device plugin 约定；如果宿主机只能用直接挂载 `/usr/local/Ascend` 和 `/dev/davinci*`，compose 需要按现场方式落地。
- 如果 `8882` 已被占用，需要用户确认替代端口；在确认前不得停止占用端口的进程或容器。
- DirectMHP 教师头姿在生产是否必须启用；如果非必须，主验证可先以 `Enabled=false` 跑通，再单独打开验证。
