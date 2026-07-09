## 1. 环境与基线确认

- [x] 1.1 确认当前工作分支为 `dev_6.0_ai_quality_910b_npu`，并确认不修改 `dev_6.0_ai_quality` 分支。
- [x] 1.2 记录宿主机 `npu-smi info` 输出，确认 NPU 3 号卡可用于本次验证。
- [x] 1.3 只读检查端口 `8882` 是否可用；如已占用，暂停并向用户确认，不停止占用端口的进程或容器。
- [x] 1.4 记录 CANN、driver、Python、torch、torch-npu、torchvision、ultralytics 版本。
- [x] 1.5 激活 `tias-910b` conda 环境，补齐 `tias/requirements.txt` 中缺失依赖，例如 `tomli`。
- [x] 1.6 用 NPU 3 执行最小 PyTorch 张量测试，确认 `import torch_npu`、`torch.npu.is_available()`、`torch.device("npu:3")` 可用。
- [x] 1.7 用 `teacher_behavior.pt` 在 NPU 3 上执行一次 Ultralytics YOLO 空图或 `test/` 图片推理冒烟。
- [x] 1.8 用 DirectMHP 权重在 NPU 3 上执行一次最小加载和推理冒烟，记录是否可启用教师头姿。

## 2. TIAS NPU 设备解析实现

- [x] 2.1 新增或调整 TIAS 设备解析 helper，支持 `cpu`、`npu`、`npu:3`、`cuda:0` 和既有 CUDA 编号。
- [x] 2.2 在 NPU 模式下懒加载 `torch_npu`，检查 NPU 可用性和设备编号范围，并输出可诊断错误。
- [x] 2.3 调整 `tias/core/settings.py`，使用统一 helper 解析 `GPU_ID` 并加载四个主 YOLO 模型。
- [x] 2.4 确保 NPU 模式不设置 `CUDA_VISIBLE_DEVICES`，CPU 和 CUDA 模式保持既有行为。
- [x] 2.5 保持 `use_half = False`，不在本变更中启用 FP16。

## 3. DirectMHP 教师头姿 NPU 适配

- [x] 3.1 调整 `tias/services/teacher_head_pose_service.py`，使用统一设备解析 helper 解析 `Teacher_Head_Pose.Device`。
- [x] 3.2 在 DirectMHP 加载时绕开 vendor CUDA-only `select_device()`，将解析后的 `torch.device` 传给 `attempt_load(..., map_location=device)`。
- [x] 3.3 验证 `Teacher_Head_Pose.Enabled = false` 时不会加载 DirectMHP，主链路可正常运行。
- [x] 3.4 验证 `Teacher_Head_Pose.Enabled = true` 且 `Device = "npu:3"` 时，DirectMHP 可完成加载和至少一次测试图片推理或返回可诊断业务失败。

## 4. 配置、依赖与文档

- [x] 4.1 新增 `tias/requirements_npu.txt` 或等价文档，记录 910B 已验证依赖版本和安装顺序。
- [x] 4.2 更新 `tias/config.toml.example`，补充 `GPU_ID = "npu:3"`、端口 `8882` 和 `Teacher_Head_Pose.Device = "npu:3"` 注释。
- [x] 4.3 更新 `tias/RUNNING.md` 或新增 NPU 运行文档，说明 `tias-910b` conda 环境启动方式。
- [x] 4.4 文档中明确本次验证默认使用 NPU 3 号卡和端口 `8882`，启动前后需检查 `npu-smi info`。
- [x] 4.5 文档中说明 `ai_quality` 生产模式保持 `TiasInferenceMode=remote`，不直接加载 NPU 模型。
- [x] 4.6 文档中明确禁止停止、重启、删除或改动本机已有 Docker 容器。

## 5. Ascend NPU Docker 适配

- [x] 5.1 读取用户实际部署 Dockerfile 和当前 `tias/docker/*`，确认需要适配的 Docker 入口。
- [x] 5.2 新增 Ascend NPU 专用 Dockerfile，避免覆盖现有 NVIDIA Dockerfile。
- [x] 5.3 新增 Ascend NPU compose 或运行命令示例，包含 CANN 环境变量、NPU 设备挂载、`GPU_ID = "npu:3"` 和端口 `8882` 配置。
- [ ] 5.4 确认容器内可执行 `import torch_npu`、`torch.npu.is_available()` 和 NPU 3 设备探测。
- [ ] 5.5 构建 NPU 镜像并启动 TIAS，完成容器内健康检查和测试图片推理。
- [x] 5.6 保留现有 NVIDIA GPU compose、secure runtime 和 CPU 路径不变。
- [x] 5.7 Docker 验证只新增本次 NPU 相关容器，容器名使用唯一前缀；不得停止、重启、删除或改动本机已有容器。

## 6. TIAS 源码环境验证

- [x] 6.1 使用 `tias-910b` conda 环境、`GPU_ID = "npu:3"` 和端口 `8882` 启动 TIAS 单实例。
- [x] 6.2 调用 `http://127.0.0.1:8882/AE/Health` 或现有健康检查接口，确认 `model_ready=true`。
- [x] 6.3 使用 `test/` 目录 jpg 图片调用学生行为推理接口，验证响应结构和计数字段。
- [x] 6.4 使用 `test/` 目录 jpg 图片调用教师行为推理接口，验证响应结构和行为字段。
- [x] 6.5 记录推理前后 `npu-smi info`，确认进程使用 NPU 3。
- [x] 6.6 若教师头姿启用，使用 `test/` 图片验证 `HeadPoseResult` 返回结构。

## 7. ai_quality 远程调度验证

- [x] 7.1 启动 Redis 和 ai_quality HTTP 服务，确认 TIAS 可注册和发送心跳。
- [x] 7.2 确认 ai_quality 注册表中 NPU TIAS 实例状态为可调度。
- [x] 7.3 使用现有测试消息或 `test/` 图片构造任务，验证 ai_quality Worker 通过远程 TIAS 完成帧分析。
- [x] 7.4 确认 ai_quality 保持 `TiasInferenceMode=remote`，不直接 import TIAS 模型服务。
- [x] 7.5 记录调度日志中的 TIAS instance_id、batch_id、耗时和失败重试信息。

## 8. 回归与报告

- [x] 8.1 运行可用的 TIAS 单元测试或接口测试，确认 CPU/CUDA 设备解析兼容性未破坏。
- [x] 8.2 运行可用的 ai_quality 单元测试或冒烟测试，确认远程调度行为未破坏。
- [x] 8.3 新增 NPU 验证报告，记录 conda 源码验证命令、Docker 验证命令、端口 `8882`、关键日志和结论。
- [x] 8.4 在验证报告中明确记录未停止、未重启、未删除、未改动本机已有 Docker 容器。
- [x] 8.5 在报告中记录未解决风险，例如 DirectMHP 是否启用、Docker runtime 现场依赖、NPU 显存占用。
- [x] 8.6 执行 `openspec status --change adapt-tias-ascend-910b-npu-runtime`，确认任务和规格状态可追踪。
