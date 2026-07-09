# 910B NPU 适配验证记录

## 环境

- 分支：`dev_6.0_ai_quality_910b_npu`
- NPU：使用 `npu:3`
- TIAS 验证端口：`8882`
- CANN：`8.1.RC1`
- Driver：`25.0.rc1.1`
- Python：`3.10.19`
- torch：`2.4.0`
- torch-npu：`2.4.0`
- torchvision：`0.19.0`
- ultralytics：`8.3.156`

## 基线检查

- `npu-smi info` 可见 8 张 `910B3`。
- 验证前 `8882` 未被监听占用。
- `tias-910b` 环境已补齐 `tias/requirements.txt` 依赖。
- NPU 张量测试通过：
  - `torch.npu.is_available() == True`
  - `torch.npu.device_count() == 8`
  - `torch.ones(3, device="npu:3").sum() == 3.0`

## 模型冒烟

- Ultralytics `teacher_behavior.pt` 在 `npu:3` 加载和 `test/00000001-ddna.jpg` 推理通过。
- 推理期间出现警告：`torchvision::nms` 不支持 NPU backend，回退 CPU。功能通过，性能影响需后续评估。
- DirectMHP `cmu_m_1280_e200_t40_lw010_best.pt` 在 `npu:3` 加载和最小推理通过。

## TIAS 源码服务验证

临时配置：

- `GPU_ID = "npu:3"`
- `[TIAS].InstanceId = "tias-npu-8882"`
- `[TIAS].BaseUrl = "http://127.0.0.1:8882"`
- Uvicorn 监听端口：`8882`
- `[Teacher_Head_Pose].Device = "npu:3"`

结果：

- `GET http://127.0.0.1:8882/AE/Health` 返回 `model_ready=true`。
- `POST /ImageDetect/student/v1.0.0` 使用 `test/00000001-ddna.jpg` 返回 200，`StatusString=success`，包含人数、人脸、睡觉、手机、阅读等计数字段。
- `POST /ImageDetect/teacher/v1.0.0` 使用 `test/00000001-ddna.jpg` 返回 200，`StatusString=success`，包含教师行为字段。
- 并发调用时曾因 `MaxConcurrentBatches=1` 返回 429 `TIAS 当前满载`，符合准入控制预期；串行重试成功。
- `GET /AE/WorkerStatus` 显示 `success_count=2`、`failure_count=0`。
- 推理后 `npu-smi info` 显示 TIAS 进程使用 NPU 3。

## 教师头姿 HTTP 验证

临时开启：

- `[Teacher_Head_Pose].Enabled = true`
- `[Teacher_Head_Pose].Device = "npu:3"`

结果：

- `POST /ImageDetect/teacher/v1.0.0` 使用 `ReturnHeadPose=true` 返回 200。
- `HeadPoseResult.Status = "success"`。
- 返回 `FaceDirection`、`Yaw`、`Pitch`、`Roll`、`TeacherSubjectBox`、`HeadBox` 等字段。

## ai_quality 远程调度验证

由于本机没有 `redis-server` 命令，且本变更不允许启动或改动已有 Docker 容器，本次使用 ai_quality 内存注册表启动临时 HTTP API 验证注册和远程调度链路。

结果：

- TIAS 启动后成功注册到 ai_quality 临时 API。
- `GET /api/tias/instances` 返回 `tias-npu-8882`，状态 `UP`，能力包含 `student_behavior`、`teacher_behavior`、`teacher_head_pose`。
- 使用 `TiasScheduler` 从注册表选择 `tias-npu-8882`。
- 使用 `TiasHttpClient.infer_student()` 远程调用 TIAS，返回 `StatusString=success`，`DataList` 数量为 1。
- ai_quality 保持远程 TIAS 调度路径，未直接加载 TIAS 模型。

## Docker 验证

已新增：

- `tias/docker/Dockerfile.npu`
- `tias/docker/docker-compose.npu.yml`
- `tias/docker/examples/tias-npu-8882.toml`

静态验证：

- `docker compose -f tias/docker/docker-compose.npu.yml config` 通过。
- Compose 使用唯一容器名 `tias-npu-8882` 和端口 `8882:8882`。
- 现有 NVIDIA Dockerfile、compose、secure runtime 文件无 diff。

构建验证：

- 第一次构建卡在默认 Debian apt 源访问。
- 改为清华 Debian 源后仍无法访问 apt 源。
- 改为最小 Python 镜像、跳过 apt 阶段后，构建容器内 pip 访问 `mirrors.aliyun.com` 出现 DNS 解析失败：`Temporary failure in name resolution`。
- 因构建容器网络/DNS 不可用，NPU Docker 镜像构建和容器内 `torch_npu` 探测未完成。

Docker 操作边界：

- 未停止本机已有 Docker 容器。
- 未重启本机已有 Docker 容器。
- 未删除本机已有 Docker 容器。
- 未改动本机已有 Docker 容器。
- 未创建 `tias-npu-8882` 容器。

## 回归

- `conda run -n tias-910b python -m compileall -q tias ai_quality` 通过。
- 未发现仓库内 Python 测试文件。

## 风险和后续

- `torchvision::nms` 在 NPU 上回退 CPU，后续需要评估性能影响。
- NPU Docker 构建依赖 Docker build 容器网络/DNS；需要现场修复 Docker daemon DNS 或提供可访问的 wheel/apt 内网源后重试。
- 当前 Dockerfile.npu 为最小镜像，未通过 apt 安装 OpenCV 常见系统库；如果后续容器启动时 `cv2` 缺少系统库，需要在可用 apt 源下补齐。
- 本次 ai_quality 使用内存注册表验证远程调度路径；生产 Redis 注册表仍需在完整部署环境中回归。
