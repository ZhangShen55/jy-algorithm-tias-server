# 业务响应 JSON 编码成本诊断

状态：CPU离线重放完成，六组35406次编码校验通过；不包含真实HTTP或GPU推理，不替代尚待执行的并发业务审计及完整请求分段统计。

## 范围与环境

服务器zhangs12，Intel Xeon Silver 4210 @2.20GHz、40个逻辑CPU；vbas Python3.11.15、Starlette0.46.2。独立脚本 `scripts/benchmark/serialization.py` 读取修正版PyTorch/TensorRT各5901条成功响应，每条重放3次；每个接口先16次预热。CUDA_VISIBLE_DEVICES为空，不导入模型或启动服务，当前正式GPU流程未改动。

计时范围为Starlette JSONResponse的构造、render及响应头初始化，包含标准JSON转UTF-8 body。每次计时外将编码body解码并与原业务字典核对，全部保留值。这里输入是已经保存的普通字典，**不包含Pydantic响应校验/dump、业务对象构造、请求解析或网络发送**；不能称完整响应耗时。

本轮与GPU容量流程同时运行在同主机，CPU未独占或固定频率；两份结果顺序重放，因此不能将微秒级差异归因为后端性能收益。只用于补齐编码组件量级证据，不改变容量成绩或API，不据此制定生产SLO。

## 观测结果

| 结果来源 | 接口 | 图片/采样数 | P50 ms | P95 ms | P99 ms | 均值ms | 平均body字节 |
|---|---|---|---:|---:|---:|---:|---:|
| PyTorch | 人数 | 2162/6486 | 0.08802 | 0.22784 | 0.30996 | 0.09709 | 3072.2 |
| PyTorch | 学生 | 2162/6486 | 0.07555 | 0.15979 | 0.20547 | 0.07905 | 4460.2 |
| PyTorch | 教师 | 1577/4731 | 0.02692 | 0.03219 | 0.03597 | 0.02758 | 876.7 |
| TensorRT | 人数 | 2162/6486 | 0.08793 | 0.20470 | 0.25871 | 0.09345 | 3071.8 |
| TensorRT | 学生 | 2162/6486 | 0.07621 | 0.15801 | 0.19917 | 0.07909 | 4458.1 |
| TensorRT | 教师 | 1577/4731 | 0.02790 | 0.03309 | 0.03692 | 0.02858 | 876.6 |

这批响应的JSON编码均值约0.03～0.10ms，不能单凭这项证明完整响应链路开销很小。Pydantic校验/序列化、业务聚合、进程调度、排队和网络仍需结合实际HTTP及分段诊断解释；各组件也不能在模型并行时直接相加成总耗时。

## 证据与复现

服务器 `/home/zhangs/workspace/vbas-benchmarks/response-serialization-20261118/` 保存逐图samples.jsonl、summary.json及checksums.json。私有执行脚本在environment-20261118/serialization.py，依赖当前b15dd39的load.percentile和compare.valid_business；summary保留脚本SHA、输入两份JSONL SHA、解释器和库版本。用--reference传入两份corrected-baseline的predictions.jsonl、--repeats 3，并为--output指定不存在的新目录可重放，不覆盖旧结果。

全部产物已取回 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/response-serialization-20261118/` 并与服务器SHA核对：

- summary.json：`16e1d85794228058c75cd111d0f3ecaa5224a050c55e1295ff8a0bfb88ba16a1`。
- samples.jsonl：`2fc6fdc43fad4ea28b28e9eaed68d5a1fb343775368bb08fd038d86f3fb9d58c`。
