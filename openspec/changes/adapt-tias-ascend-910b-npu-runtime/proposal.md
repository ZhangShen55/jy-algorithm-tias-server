## Why

当前 TIAS 推理服务按 NVIDIA CUDA 环境设计，`GPU_ID` 只支持 `cpu` 或 CUDA 编号；在华为 Ascend 910B3 服务器上即使已安装 CANN、`torch_npu` 和 NPU 运行环境，服务仍会把非 CPU 配置当作 CUDA 处理，导致模型无法按 NPU 方式稳定启动。

本变更目标是在不影响现有 `dev_6.0_ai_quality` 分支和 NVIDIA/CPU 部署路径的前提下，新增 910B NPU 运行路径，使 TIAS 可在 `tias-910b` conda 环境和后续 NPU Docker 镜像中使用 3 号 NPU 卡完成模型加载、HTTP 推理、ai_quality 远程调度和部署验证。

## What Changes

- 新增 TIAS 运行时设备解析能力，支持 `GPU_ID = "npu:3"`、`GPU_ID = "npu"`、`GPU_ID = "cpu"`、CUDA 编号等配置形式，并在 NPU 模式下显式加载 `torch_npu`。
- 调整主 YOLO 模型加载路径，使 `person_count.pt`、`face_count.pt`、`student.pt`、`teacher_behavior.pt` 可以被加载到 Ascend NPU 设备。
- 调整可选教师头姿 DirectMHP 加载路径，避免继续依赖 vendor 中只支持 CUDA 的 `select_device()`，使 `Teacher_Head_Pose.Device = "npu:3"` 可用。
- 新增或更新 NPU 专用依赖和运行文档，优先复用服务器现有 `tias-910b` conda 环境，并记录 CANN、driver、torch、torch-npu、ultralytics 的已验证版本组合。
- 新增 NPU Docker 适配方案和部署文件，替换现有 NVIDIA runtime / `--gpus all` 语义，面向 Ascend/CANN 宿主机运行。
- 使用 `test/` 目录中的测试图片建立验证流程，固定验证时使用 NPU 3 号卡和服务端口 `8882`，覆盖单模型加载、HTTP 推理、ai_quality 远程调度和 Docker 启动。
- Docker 验证只能新增、构建、启动本次 NPU 适配相关容器，禁止停止、重启、删除或改动本机已有运行容器。
- 保持 `ai_quality` 默认 `TiasInferenceMode=remote` 架构不变；除非显式进入本地开发模式，`ai_quality` 不直接加载 NPU 模型。

## Capabilities

### New Capabilities

- `tias-ascend-npu-runtime`: 描述 TIAS 在 Ascend 910B NPU 环境中的设备配置、模型加载、运行验证和 Docker 部署要求。

### Modified Capabilities

- 无。现有 HTTP API、ai_quality 调度语义、模型保护语义和 NVIDIA/CPU 部署能力不改变。

## Impact

- 代码影响：
  - `tias/core/settings.py`：设备解析、`torch_npu` 加载、YOLO 模型加载设备。
  - `tias/services/teacher_head_pose_service.py`：DirectMHP 设备解析与 `attempt_load` 的 NPU 支持。
  - 可能新增 `tias/core/device.py` 或等价小型 helper，以避免设备解析逻辑散落。
- 配置影响：
  - `tias/config.toml.example` 和 Docker 示例配置需要记录 `GPU_ID = "npu:3"`、`Teacher_Head_Pose.Device = "npu:3"`、端口 `8882` 的用法。
  - 文档需明确本次验证固定使用 NPU 3 号卡和 `8882` 端口。
- 依赖影响：
  - 新增 NPU 依赖说明或 `requirements_npu.txt`，记录 `torch==2.4.0`、`torch-npu==2.4.0`、`torchvision==0.19.0`、`ultralytics==8.3.156`、CANN `8.1.RC1`、driver `25.0.rc1.1` 的已验证组合。
  - `tias-910b` conda 环境需补齐 TIAS requirements 中缺失依赖，例如 `tomli`。
- 部署影响：
  - 新增或调整 Ascend NPU Dockerfile / compose / 运行文档。
  - NVIDIA Dockerfile 和 compose 保持现有行为。
  - 不允许停止、重启、删除或改动本机已有 Docker 容器。
- 验证影响：
  - 需要在 910B 服务器上用 `npu-smi` 确认 NPU 3 可用。
  - 需要使用 `test/` 图片完成 TIAS 单服务和 ai_quality 远程调度验证。
