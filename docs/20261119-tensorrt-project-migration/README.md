# 项目统一 TensorRT Engine 迁移方案

状态：约定工作完成（37/37，2026-11-20）。用户缩减重复配对后14配对+三稳定性全部完成；最终main192调用一致，十个证据包全部本机核验。服务RSS增长、PT/TRT差异及类别覆盖如实保留，用户采用/部署仍待定，未部署。任务目录创建日期保留2026-11-19。

最终入口：[完成交接](reports/20261119-final/report.md)、[效率检查点](reports/20261120-efficiency-checkpoint/report.md)、[有限性能/资源](reports/20261120-performance/report.md)、[完整备份索引](reports/20261119-evidence-index/report.md)。

## 目标和边界

按用户要求，将人数、人脸、学生行为、教师行为四模型统一为 TensorRT Engine 推理，交付到统一模型目录；保留 Python/FastAPI、现有接口和业务语义，C++ 后续另议。以现有 perf 分支实现及已验证引擎为起点，完成项目默认运行与服务器直接启动验证，不重复从零实现后端。

“整个项目是 TensorRT”在本方案中指正式服务只加载四个 Engine，不通过 .pt 执行模型、不静默退回 PyTorch/CPU；Ultralytics 预处理、Tensor/NMS 等仍使用 torch/torchvision 库。彻底移除这些依赖是另一条重写路线，不混入本轮。保留旧版本和旧环境供人工整版回退，正式配置不提供隐式降级。

本轮已授权按change实施，仅项目改造与服务器验证，不部署。后续代码、模型转换和部署分别记录，不把方案写完当实施完成。已有优化任务未结项；定时任务 vbas 已按用户要求删除，不重新创建。服务器已有测试是否结束须实施前只读确认，不凭历史 PID 操作，不在活动测量期间同步新代码。

## 评审建议

推荐沿用 Ultralytics TensorRT 路径并整理加载、校验与交付层：复用验证资产，业务改动最少。仅修改 InferenceBackend 默认值无法解决模型目录、加密工具、Docker 依赖和混合接口共享状态问题；直接 TensorRT Python API 重写预处理/NMS 会扩大一致性验证范围；完整 C++ 重写留待后续。因此选择第一条完整交付路线。

## 已确认的目录与执行范围

用户已确认：项目根目录 `model/`（服务器为 `/home/zhangs/workspace/vbas/model/`），放四个 TensorRT Engine 和 manifest，先在服务器直接启动项目并验证。不是宿主机根目录 `/model`，本轮不引入容器路径。部署必须等服务稳定后另行讨论，不构建或切换 Docker/compose，不改线上启动方式。

普通运行直接读取项目 `model/*.engine`。既有 secure 能力不得被破坏，CPU层加密/解密和失败清理作为回归检查；secure镜像交付、生产挂载、多容器重启验收均留到部署阶段，不算本轮完成条件。

## 文档导航

| 文件 | 职责 |
|---|---|
| [01-environment.md](01-environment.md) | 环境、设备、版本和保护范围 |
| [02-validation-protocol.md](02-validation-protocol.md) | 冻结测试、对照与失败条件 |
| [03-baseline-and-results.md](03-baseline-and-results.md) | 现有证据、基线和产物关联 |
| [04-implementation-plan.md](04-implementation-plan.md) | 模型布局、加载、构建和交付方案 |
| [05-tasks.md](05-tasks.md) | 有依赖的执行清单 |
| [06-report-template.md](06-report-template.md) | 报告字段和校验规则 |
| [07-completion-and-exit.md](07-completion-and-exit.md) | 完成、停止、回退与交接 |

## 模型一致性完成要求

用户补充要求：四模型各100张PT FP16与项目model/实际Engine对比，固定80张随机+20张历史差异（不足补随机）、seed20261119、内容去重，详见02。人数同100张分别检查旧人数True/学生False NMS。保存检测框、类别、置信度、匹配/新增/缺失和计数差异及私有图；对比完成和用户接受差异分开，不计算无标注的真实准确率。该项已执行并完整备份，见[100张对比报告](reports/20261119-model-comparison/report.md)；存在框/计数差异，用户采用复核待定。

## 尚未确定

目录、不部署范围及方案实施已确认。用户已确认教师ImageSize仅支持640，其他值启动时报错；原图分辨率仍可变化。几何和启动失败验证按此冻结范围执行。目标仅覆盖已授权 3090 环境；其他部署硬件和生产延迟 SLO 未指定，不承诺跨机可用或生产验收。真实准确率仍无人工标注；已存在的 PT/TRT 差异必须在采用复核中保留。

## 对应 OpenSpec change

已根据本索引及01～07生成 `20261119-migrate-vbas-to-tensorrt-engine`，当前约定工作完成，真实状态以本索引和05最终记录为准。

- [proposal：动机与范围](../../openspec/changes/20261119-migrate-vbas-to-tensorrt-engine/proposal.md)
- [design：技术设计与取舍](../../openspec/changes/20261119-migrate-vbas-to-tensorrt-engine/design.md)
- [tasks：实施与验证清单](../../openspec/changes/20261119-migrate-vbas-to-tensorrt-engine/tasks.md)
- 三项能力规范位于该change的specs/：模型产物、推理运行时、迁移验证。

OpenSpec的planning complete只表示文档齐备，不表示05/07实施或完成出口通过；修改范围或协议时两处同步。

执行期间按[05任务清单](05-tasks.md)的映射表同步标注每个子任务的状态、完成数量和证据；开始、实质检查点、完成或阻塞均更新，不等结项统一回填。

命名说明：按用户要求，change使用日期前缀 `20261119-migrate-vbas-to-tensorrt-engine`。当前安装的OpenSpec `status`命令要求名称以字母开头，因此无法通过该命令查看此名称的状态；文档保留，不能将该命名限制当成实施已完成或规范内容不合格。`validate`须独立核验。

2026-11-19用户确认：Teacher_Behavior_Thresd.ImageSize固定640，其他值必须在加载前明确报错，不静默覆盖；原图分辨率不限制为640。

专项执行检查点：全量业务与功能共享状态已完成，见[业务回归](reports/20261119-business-regression/report.md)和[专项回归](reports/20261119-functional-regression/report.md)。保护/多worker结果见下方新检查点；性能稳定性尚未齐备，用户采用待复核。

保护与直接启动出口已验证，见[保护报告](reports/20261119-protection/report.md)；离线导出工具实际GPU验证中，性能与稳定性未完成。

暂停检查点（2026-11-19T18:41:23+08:00）：已停止离线转换控制器及其实际子进程，GPU回到3MiB/0%，无本迁移进程遗留。独立新构建目录仅完成人数/人脸两件Engine、无manifest完成标记，不能作为完整发布；项目model/原受审四Engine未替换。18性能配对及3稳定性尚未启动。等待用户明确恢复，不自动续跑。

2026-11-19T18:44:50+08:00 | 用户明确恢复并要求完成后工作区干净 | 核对GPU3MiB/0%、无遗留任务进程、代码仍f5a7f3a；r1暂停原件保留，以trt-migration-20261119-export-check-r2新目录完整验证离线导出；性能尚未启动。完成后提交任务改动，不提交/删除用户AGENTS.md，保留私有model资产。

离线导出工具GPU完整验证已完成（r2四模型构建+实加载），项目受审Engine未替换；构建证据封存后接续有限性能阶段。

2026-11-20恢复检查点：构建包整包/44文件本机核验已完成，见[构建工具报告](reports/20261119-export-tool/report.md)。性能与稳定性独立run_id trt-migration-20261120-performance-r1已启动；整体仍30/37，未部署。

用户2026-11-20范围更新：2026-11-20用户明确不需要很多组重复对比：保留已完成的人数/学生各三对、教师一对（14轮），取消其余教师重复配对；缩减时正在执行的teacher-r2-new自然收尾，单列非配对观察，不进入逐对比值。三接口各30分钟稳定性保留。原21轮计划和全部记录原样留存，取消不伪记为完成。 当前完成31/37；稳定性及最终交接未完成。

2026-11-20最终检查点：37/37约定工作完成，详见顶部交接入口；以下前序检查点是执行历史，不作为当前状态。工作完成不等于采用/部署，未自动归档。
