# 学生人数 NMS 口径修正

状态：独立重采、对照、重复性检查与本机校验备份已完成，容量调度已恢复。日期：2026-11-18（北京时间）。

## 发现与决策

Ultralytics 8.3.156 的 Model.predict 会把本次 kwargs 合并到已存在 predictor.args。人数接口显式传 True，学生接口过去省略 agnostic_nms：独立学生首次调用为 False，同进程先调用人数再调用学生则继承 True。服务器无模型 dummy predictor 调查重现了 False→True→True 的顺序，且 _reset_ckpt_args 不保留该项。旧 baseline.py 按人数、学生、教师顺序采集，故旧学生记录并非独立默认。

用户选择“保留学生独立默认：不跨类别去重，并重新采集学生基线”。学生 process_person_detection 显式传 False；人数保持 True。采集器增加 --endpoint，在不同进程独立采集学生两后端。接口结构与其它检测阈值不变。共享 predictor 的混合接口并发竞态不在这项修正验证结论内。

## 保留与恢复

旧 torch-fp16-baseline-20261118、trt-fp16-baseline-20261118 原样保留。仅学生部分被后续独立版本取代；旧全量比较包含学生的汇总相应标为历史口径。人数与教师结果可继续复用，组合时逐段追溯。

容量父进程4182465暂收 SIGSTOP，当前 instances/load 子进程继续完整收尾；不杀正在测量的工作。GPU空闲且 cleanup_complete 后才拉取修正并顺序重采。新目录为 torch-student-independent-nms-false-20261118 和 trt-student-independent-nms-false-20261118。完成后核对2162条、业务成功、FP16、参数False、生成哈希与备份，再 SIGCONT 原父进程，沿原 journal 继续。不重复启动 capacity.py。

## 待补证据

已补齐的采集、对照、恢复及校验证据见 [修正版报告](../20261118-precision-comparison-corrected/report.md)；并发一致性仍待验证。本次修正不能写为真实准确率或生产验收通过。

## 实施检查点

- 提交 `b15dd396172e5532661a88e547cb70e92a9f5147` 已推送 perf，服务器已 fast-forward，跟踪文件干净。
- 本地对实际生产函数做隔离调用核验：人数 predict 必须收到 False，FP16 设置及空检测结果保持；编译检查与 diff 检查通过。
- 当前 sync I8/C8/b1 首轮确认正常结束，300秒3926次成功、0失败，13.06图/s，P95 660.40ms；尚未完成三轮复测，不是最终推荐。
- 调度暂停时 GPU 仅3MiB，无 instances/load 运行；2026-11-18 20:18后启动独占GPU的修正协调器 PID30437。已采集的首批记录核对 HTTP200、业务成功、三模型 FP16、人数参数False。
- 协调器：`/home/zhangs/workspace/vbas-benchmarks/environment-20261118/student-nms-correction.py`。状态与日志：`student-nms-correction-20261118/{state.json,coordinator.log,torch-collect.log,trt-collect.log}`。
- 成功后自动组合原人数/教师与新学生为 `torch-corrected-baseline-20261118`、`trt-corrected-baseline-20261118`，另存新对照、3张学生重复采集、校验清单与打包，再恢复原调度。任何阶段失败保持暂停，先检查，不自动覆盖或重跑。
- 打包完成后仍需取回本机并校验，以及按新结果更新差异案例图与最终报告；本检查点不表示重采完成。

## 完成证据

两后端各2162张学生记录全部有效、三模型均FP16且人数False。学生PyTorch3张独立重复得到275框完全一致。组合全量各5901条，127778框匹配、47参考独有、43候选新增；学生人数31张计数不同，单图最大差1，净+1，尚待用户复核采用。新统计取代旧学生口径，不修改旧文件。

2026-11-18 20:28:31（北京时间）协调器完成并自动SIGCONT原容量调度4182465。已核对下一轮sync I6/C6/b1确认测试运行；没有重复GPU任务。

备份已取回本机并核验：`/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/student-nms-correction-20261118/corrected-baselines.tar.gz`；SHA256 `53f09d1cb6c9b289ab1c33ab0cbf312a3f61a385b64c8b66b0bb500d40cf7895`。解包后checksums.json的19项均匹配。后续继续执行正式容量、并发与兼容回退测试。
