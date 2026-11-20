# TensorRT三接口并发与实例/worker拐点评估

状态：方案草拟及工具/资源只读调查中，尚未启动GPU测试。用户确认三个接口各9轮，共27轮；worker计数含义、服务准入上限两项仍待答复。此次任务独立于已完成的TensorRT迁移，不重新打开原37项任务，不开展C++改造或部署。

## 目标与范围

仅RTX3090，逐个接口独立测试：`/AE/SyncTasks2`、`/ImageDetect/student/v1.0.0`、`/ImageDetect/teacher/v1.0.0`。每接口测试三种实例/worker拓扑与总客户端并发50/100/200的九种组合，各组合一次，合计27个正式测量窗口；一次只运行一个组合/接口。启动就绪及预热属于该轮准备，不另算容量成绩。

报告成功图片吞吐、成功请求P50/P95/P99/均值、429/503/传输/业务失败、CPU/RSS/GPU、实际进程覆盖及负载分配，探索指定网格内的饱和/收益拐点。没有生产SLO，不据此宣称生产峰值或准确率通过。数据仅每组一次，不提供重复实验置信区间。

## 已确定与待确认

已确定：27轮；仅3090；当前TensorRT FP16四Engine；总客户端并发50/100/200；接口独立；沿用完整冻结图池且一请求一图；保留原始记录和有限失败。

待确认A：每实例worker为1/2/4（总进程1/4/16），或实例合计worker为1/2/4（每实例1）。不能替用户选择。

待确认B：建议沿用迁移验证的每worker `MaxConcurrentBatches=1`、`MaxQueueSize=0`；用户如需调整须明确数值。高客户端并发不自动授权增大服务b/队列。两项答复前暂停依赖的GPU启动、正式配置冻结和成绩判断；可继续只读调查和文档草拟。

资源现状：最近一次成功查询指定GPU3MiB/0%，总24576MiB；后续SSH连接超时，实时主机内存/进程仍需恢复后复核，不据旧记录启动。历史单worker显存约1567～1611MiB仅作预算参考，不把线性估算当已测16worker。

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
