## Why

已有同配置实验表明 TensorRT 相对 PyTorch 的端到端吞吐提升约50%～77%，但项目仍默认读取 models/*.pt，Engine 加载和导出依赖实验目录。需要将这条已验证路线整理为项目自身的默认运行能力，在服务器跑通并验证，再讨论部署。

依据：`docs/20261119-tensorrt-project-migration/README.md` 及01～07；本 change 是其执行契约，不替代八份计划或历史实验报告。

## What Changes

- 将人数、人脸、学生、教师四模型的 FP16 Engine 和 manifest 放入项目根 `model/`，提供离线构建/复用及校验工具；保留源权重、历史引擎和回退资产，二进制不入 Git。
- **BREAKING**：新服务默认且仅允许 TensorRT FP16 模型推理，移除运行时对 `.pt` 权重的依赖；旧 pytorch/CPU/half=False 配置明确失败，不静默降级。torch/torchvision 继续作为 Ultralytics 调用层依赖；PyTorch 对照在独立工具/旧环境运行。
- 明确设备绑定、固定shape、四模型warmup和就绪门槛，保持业务阈值、NMS、ROI、坐标和公开HTTP契约；隔离共享predictor参数。
- 每模型固定100张PT FP16/TRT模型输出对比，保留逐框、类别、置信度、计数差异及私有差异图；报告完成与用户接受差异分开。
- 完成三接口业务/并发、有限性能和稳定性验证，以及保护机制回归、独立端口启动/重启和旧版本恢复；证据完整备份。
- 仅改项目代码和服务端验证，不构建/发布镜像，不改Docker/compose或线上服务，不实施C++，不重建已删除定时任务。

## Capabilities

### New Capabilities

- `tensorrt-model-artifacts`：四模型Engine目录、构建/复用、manifest完整性和版本关联。
- `tensorrt-inference-runtime`：TRT-only加载、设备/FP16/shape检查、就绪、接口语义及保护回归。
- `tensorrt-migration-validation`：每模型100张一致性、服务端回归、有限稳定性、回退与证据出口。

### Modified Capabilities

无。当前 `openspec/specs/` 无已建立的主规范，本次新增迁移能力；不改写归档中含历史接口/头姿语义的规范，也不改其他活动change。

## Impact

- 代码：core/settings.py、新core/inference_runtime.py、必要的四类业务predict调用、core/model_protection.py。
- 工具：离线Engine构建/校验、100张模型对照与报告、scripts/protect_vbas_models.py；历史benchmark工具原件保持可复现。
- 项目：model/说明、配置示例、README/RUNNING及忽略规则；不覆盖私有config.toml或用户AGENTS.md。
- 环境：仅ssh zhangs12上的用户vbas-trt环境及指定RTX3090 GPU1；保留jy-tias/vbas/旧权重。已有活动GPU任务结束且cleanup前不得同步/启动新任务。
- API：不新增或变更公共请求/响应结构、路由默认开关、业务错误和准入语义；模型后端和默认路径改变属于配置兼容性变化。
- 状态：仅制定change；未实施、未验证或部署。真实准确率、生产SLO与采用决定不由本change自动认定。
