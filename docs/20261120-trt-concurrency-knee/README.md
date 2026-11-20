# TensorRT三接口并发与实例/worker拐点评估

状态：参数已冻结，服务器CPU输入/配置预检及32项回归、执行器6项本机检查通过，正式27轮启动中。用户确认三个接口各9轮，共27轮；worker含义及准入已确认：I1/2/4、每实例W1、每worker b512、queue0。此次任务独立于已完成的TensorRT迁移，不重新打开原37项任务，不开展C++改造或部署。

## 目标与范围

仅RTX3090，逐个接口独立测试：`/AE/SyncTasks2`、`/ImageDetect/student/v1.0.0`、`/ImageDetect/teacher/v1.0.0`。每接口测试三种实例/worker拓扑与总客户端并发50/100/200的九种组合，各组合一次，合计27个正式测量窗口；一次只运行一个组合/接口。启动就绪及预热属于该轮准备，不另算容量成绩。

报告成功图片吞吐、成功请求P50/P95/P99/均值、429/503/传输/业务失败、CPU/RSS/GPU、实际进程覆盖及负载分配，探索指定网格内的饱和/收益拐点。没有生产SLO，不据此宣称生产峰值或准确率通过。数据仅每组一次，不提供重复实验置信区间。

## 已确定参数

已确定：27轮；仅3090；当前TensorRT FP16四Engine；总客户端并发50/100/200；接口独立；沿用完整冻结图池且一请求一图；保留原始记录和有限失败。

已确认A：所有实例合计worker为1/2/4，每实例1个worker，即I1/W1、I2/W1、I4/W1；不执行16模型进程。

已确认B：用户明确本轮每worker `MaxConcurrentBatches=512`，`MaxQueueSize=0`保持。此次放开准入是用户授权的新对照条件，不改写旧b1基线。三档C50/100/200均小于单worker b512；实际仍可能在线程池、模型锁和HTTP处理中等待，不把queue0解释为没有内部等待。

资源现状：SSH已恢复，实时指定GPU3MiB/0%、总24576MiB，主机可用约37GiB；每轮重新核对，不据旧记录启动。历史单worker显存约1567～1611MiB仅作预算参考，不把线性估算当已测16worker。

## 文档导航

| 文件 | 职责 |
|---|---|
| [01-environment.md](01-environment.md) | 代码/硬件/依赖、资源与保护 |
| [02-performance-protocol.md](02-performance-protocol.md) | 矩阵、测量口径及失败处理 |
| [03-baseline-and-results.md](03-baseline-and-results.md) | 既有基线、证据和存储 |
| [04-implementation-plan.md](04-implementation-plan.md) | 工具适配、执行、归集方案 |
| [05-tasks.md](05-tasks.md) | 依赖任务与实际进度 |
| [06-report-template.md](06-report-template.md) | 报告与原始证据字段 |
| [07-completion-and-exit.md](07-completion-and-exit.md) | 27轮完成条件、停止/清理/交接 |


路由语义补充：SyncTasks2现有实现不走BatchAdmissionController，b512对师生接口生效，对旧人数路由不形成准入限制；本轮保留实现测量，不新增准入逻辑。见02，不能把客户端并发当作单worker GPU并发。
