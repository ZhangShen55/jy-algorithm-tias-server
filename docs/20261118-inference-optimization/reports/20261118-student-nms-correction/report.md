# 学生人数 NMS 口径修正

状态：用户已确认，代码已修正，待服务器验证与独立重采。日期：2026-11-18（北京时间）。

## 发现与决策

Ultralytics 8.3.156 的 Model.predict 会把本次 kwargs 合并到已存在 predictor.args。人数接口显式传 True，学生接口过去省略 agnostic_nms：独立学生首次调用为 False，同进程先调用人数再调用学生则继承 True。服务器无模型 dummy predictor 调查重现了 False→True→True 的顺序，且 _reset_ckpt_args 不保留该项。旧 baseline.py 按人数、学生、教师顺序采集，故旧学生记录并非独立默认。

用户选择“保留学生独立默认：不跨类别去重，并重新采集学生基线”。学生 process_person_detection 显式传 False；人数保持 True。采集器增加 --endpoint，在不同进程独立采集学生两后端。接口结构与其它检测阈值不变。共享 predictor 的混合接口并发竞态不在这项修正验证结论内。

## 保留与恢复

旧 torch-fp16-baseline-20261118、trt-fp16-baseline-20261118 原样保留。仅学生部分被后续独立版本取代；旧全量比较包含学生的汇总相应标为历史口径。人数与教师结果可继续复用，组合时逐段追溯。

容量父进程4182465暂收 SIGSTOP，当前 instances/load 子进程继续完整收尾；不杀正在测量的工作。GPU空闲且 cleanup_complete 后才拉取修正并顺序重采。新目录为 torch-student-independent-nms-false-20261118 和 trt-student-independent-nms-false-20261118。完成后核对2162条、业务成功、FP16、参数False、生成哈希与备份，再 SIGCONT 原父进程，沿原 journal 继续。不重复启动 capacity.py。

## 待补证据

服务器提交、运行起止、逐图采集完整性、差异统计、校验清单和恢复时间：待实测填写。本次修正不能写为真实准确率或生产验收通过。
