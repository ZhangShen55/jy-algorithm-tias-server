# 同接口并发业务一致性工具与执行出口

状态：工具代码完成，4项无模型回归检查通过；尚未执行真实GPU并发审计，不写为并发一致性已通过。当前正式服务仍为b15dd39，未拉取本工具或插入额外GPU任务。

## 执行方法

新增 `scripts/benchmark/audit.py`，由 `instances.py --audit-reference` 选择。未传该选项时仍使用原load.py容量路径；新模式独立采集完整业务响应，不把额外结果保存/比较开销混入容量成绩。

在正式PyTorch→TensorRT串行容量流程结束、确认GPU空闲后，分别对三个接口、两个后端执行；采用各后端已实测零失败的实例/并发/服务配置，每接口全量请求池跑1遍，固定seed=20261118。PyTorch引用torch-corrected-baseline-20261118，TensorRT引用trt-corrected-baseline-20261118，验证同后端并发对顺序结果；后端间差异继续使用已有全量比较，不能把两种检查混为一谈。只测同接口，不据此覆盖混合接口共享predictor竞态。

启动模型之前先核对请求池覆盖、完整请求参数及Base64图片SHA与该接口基线一致。顺序采集基线不改写；响应另存新目录。每次保存序号、图像路径/SHA、实例、完整响应及业务对照，不能只检查HTTP200。

对照保留忽略TimeStamp/UseTimeMs/FreeCapacity及列表顺序的严格相等、逐类数量变化、业务框IoU≥0.5匹配/未匹配及坐标差。没有预设可接受检测差异门槛，所有数值变化保存供复核，不自行认定准确性通过。未捕获原始模型框，因此此项只证明/描述最终业务响应的并发一致性。

发生HTTP、业务或传输错误时停止派发新样本，排空已发请求；记录未执行样本并返回非零，实例管理器保留日志并清理本轮进程。不能将只完成部分输入写为全量通过。数值变化但业务有效时保留完整差异，不作为生产精度自动验收。

## 启动示例（GPU空闲后，当前不可与正式容量重叠）

```sh
/home/zhangs/.conda/envs/vbas/bin/python scripts/benchmark/instances.py \
  --backend pytorch --endpoint /AE/SyncTasks2 \
  --instances 8 --concurrency 8 --max-batches 1 --warmup-seconds 30 \
  --payload /home/zhangs/workspace/vbas-benchmarks/full-performance-payloads-20261118/sync \
  --audit-reference /home/zhangs/workspace/vbas-benchmarks/torch-corrected-baseline-20261118/predictions.jsonl \
  --audit-repetitions 1 --seed 20261118 \
  --output /home/zhangs/workspace/vbas-benchmarks/torch-concurrent-sync-20261118
```

该模式按完整样本次数结束，非固定seconds容量窗口；不接受非零rate。师生配置取各自候选，不能直接套用此示例；TensorRT另需vbas-trt解释器、backend=tensorrt和正式FP16 engine-root。所有推理仍只用指定GPU1，默认配置与生产接口不改。

## 已完成的工具检查

`python3 -m unittest discover -s tests/benchmark -p test_audit.py`：4项通过。覆盖时间差可忽略但计数/坐标变化必须保留、图片字节/覆盖不符拒绝、两个并发worker完整保存全部图片及重复、HTTP错误停止新派发并保留未执行状态。测试不加载模型、不访问网络，仅验证采集和对照逻辑；不替代真实CUDA/HTTP验证。audit.py与instances.py编译、git diff检查通过。

真实GPU审计、差异归因、产物哈希/备份与最终出口仍待执行。后续在任务05和完成出口07按实际证据更新。
