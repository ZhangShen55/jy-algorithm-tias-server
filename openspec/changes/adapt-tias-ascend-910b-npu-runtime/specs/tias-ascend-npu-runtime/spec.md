## ADDED Requirements

### Requirement: TIAS 必须支持 Ascend NPU 设备配置

TIAS MUST 支持通过配置选择 Ascend NPU 设备，并在 NPU 模式下显式加载 `torch_npu`，不得把 NPU 配置当作 CUDA 配置处理。

#### Scenario: 使用 NPU 3 启动主模型

- **WHEN** `tias/config.toml` 设置 `GPU_ID = "npu:3"` 并在 `tias-910b` 环境启动 TIAS
- **THEN** TIAS MUST 将 `person_count.pt`、`face_count.pt`、`student.pt`、`teacher_behavior.pt` 加载到 `npu:3`

#### Scenario: NPU 依赖缺失时失败可诊断

- **WHEN** `GPU_ID` 设置为 `npu:3` 但当前 Python 环境无法导入 `torch_npu`
- **THEN** TIAS MUST 启动失败并输出明确说明 `torch_npu` 或 NPU 环境缺失的错误

#### Scenario: CPU 和 CUDA 配置保持兼容

- **WHEN** `GPU_ID` 设置为 `cpu` 或现有 CUDA 编号配置
- **THEN** TIAS MUST 保持既有 CPU 或 NVIDIA CUDA 设备选择行为

### Requirement: TIAS 主推理接口必须可在 NPU 3 上处理测试图片

TIAS MUST 在 NPU 3 号卡和端口 `8882` 上完成学生和教师主推理接口的 HTTP 冒烟验证，响应结构必须与现有 API 契约兼容。

#### Scenario: 学生行为接口处理 test 图片

- **WHEN** TIAS 使用 `GPU_ID = "npu:3"` 并监听端口 `8882` 启动，并用 `test/` 目录中的 jpg 图片调用学生行为推理接口
- **THEN** 响应 MUST 返回成功状态、逐图结果列表和 ai_quality 所需的人数、人脸、睡觉、手机、阅读计数字段

#### Scenario: 教师行为接口处理 test 图片

- **WHEN** TIAS 使用 `GPU_ID = "npu:3"` 并监听端口 `8882` 启动，并用 `test/` 目录中的 jpg 图片调用教师行为推理接口
- **THEN** 响应 MUST 返回成功状态、逐图结果列表和教师行为结果字段

### Requirement: DirectMHP 教师头姿必须支持 NPU 设备解析

当教师头姿开启时，TIAS MUST 支持通过 `Teacher_Head_Pose.Device = "npu:3"` 将 DirectMHP 模型加载到 Ascend NPU 设备。

#### Scenario: 教师头姿启用 NPU 3

- **WHEN** `Teacher_Head_Pose.Enabled = true` 且 `Teacher_Head_Pose.Device = "npu:3"`
- **THEN** DirectMHP MUST 使用 `torch.device("npu:3")` 加载模型并完成一次教师头姿推理流程或返回可诊断的业务失败状态

#### Scenario: 教师头姿关闭不影响主链路

- **WHEN** `Teacher_Head_Pose.Enabled = false`
- **THEN** TIAS MUST 不加载 DirectMHP 模型，学生行为和教师行为主接口 MUST 仍可在 NPU 3 上运行

### Requirement: ai_quality 必须通过远程 TIAS 调度 NPU 推理

ai_quality MUST 保持 `TiasInferenceMode=remote` 生产链路，通过 HTTP 调度已注册的 NPU TIAS 实例，不得在生产模式中直接加载 TIAS 模型。

#### Scenario: NPU TIAS 注册到 ai_quality

- **WHEN** ai_quality HTTP 服务启动且 TIAS 使用 NPU 3 和端口 `8882` 成功启动
- **THEN** TIAS MUST 向 ai_quality 注册并在心跳中上报实例状态、能力和队列容量

#### Scenario: ai_quality Worker 调度 NPU TIAS

- **WHEN** ai_quality Worker 消费或运行测试课堂任务，并从注册表选择 NPU TIAS 实例
- **THEN** ai_quality MUST 通过 TIAS HTTP 接口完成帧分析，并保持既有结果聚合和入库语义

### Requirement: NPU Docker 部署必须独立于 NVIDIA Docker 部署

TIAS MUST 提供 Ascend NPU 专用 Docker 构建和运行说明，不得破坏现有 NVIDIA CUDA Dockerfile、compose 和 secure runtime 路径，并且不得停止、重启、删除或改动本机已有 Docker 容器。

#### Scenario: 构建 NPU 镜像

- **WHEN** 执行 NPU 专用 Dockerfile 构建
- **THEN** 镜像 MUST 包含 TIAS 运行依赖、`torch_npu` 依赖说明或安装步骤，并设置 CANN/NPU 运行所需环境变量

#### Scenario: 容器使用 NPU 3 启动 TIAS

- **WHEN** 使用 NPU compose 或运行命令启动新增容器，并配置 `GPU_ID = "npu:3"` 和端口 `8882`
- **THEN** 容器内 TIAS MUST 能导入 `torch_npu`、识别 NPU 设备并完成健康检查和至少一次测试图片推理

#### Scenario: Docker 验证不影响已有容器

- **WHEN** 执行 NPU Docker 构建、启动和验证
- **THEN** 实施过程 MUST NOT 对本机已有容器执行停止、重启、删除或 compose down 操作

### Requirement: NPU 验证必须记录环境和结果

本变更 MUST 产出 NPU 验证记录，覆盖源码环境和 Docker 环境，并明确记录测试使用 NPU 3 号卡和端口 `8882`。

#### Scenario: 记录源码环境验证

- **WHEN** 使用 `tias-910b` conda 环境完成验证
- **THEN** 验证记录 MUST 包含 Python、torch、torch-npu、ultralytics、CANN、driver、`npu-smi` 和测试命令结果

#### Scenario: 记录 Docker 环境验证

- **WHEN** 完成 NPU Docker 启动和推理验证
- **THEN** 验证记录 MUST 包含镜像构建命令、新增容器启动命令、容器内 NPU 可见性、TIAS 端口 `8882` 健康检查和测试图片推理结果
