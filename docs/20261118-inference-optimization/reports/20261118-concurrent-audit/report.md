# 同接口并发业务一致性工具与执行出口

状态：六组全量真实GPU并发业务审计完成，11802次均成功，规范化最终业务响应全部与各自后端corrected顺序基线严格相等。原始/派生197文件已本机整包及逐成员核验；只验证同接口业务响应，不评价真实准确率或混合接口竞态。当前结果见文末，原工具准备记录保留。

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

以上为工具准备时的检查范围；真实GPU执行与备份结果见下节。

2026-11-19更新：新增HTTP接收时延、Unicode关联头、历史ImageList/FP16元数据保护兼容；六组全量及快速池CPU预检通过。--trace-http只允许和audit-reference共同诊断，方法及真实GPU待验状态见 ../20261119-http-timing/report.md，输入冻结见 ../20261119-quick-regression/report.md。

## 2026-11-19 全量GPU阶段启动

18组普通配对结束并确认指定GPU空闲后，服务器FF同步e90b31f，两环境各32项CPU回归通过。六组完整池再次在服务器CPU预检通过，引用torch/trt-corrected-baseline-20261118原件，SHA分别ccfdde4bec50200f8d62ca05dfd6de861e393c968f1002502e157a08e8b52b59和0a8b40f11a64031e88dc2656519f7af19804625ab75bc7822f939b0b49eb5c4b。

run_id为concurrent-business-audit-20261119，控制父551538，脚本/日志environment-20261118/concurrent-business-audit-20261119.py/.log，驱动SHA38899c1c3b2d97c042474c27474b996b270dad116bba1a5f6080dae779c13c29。三接口按人数/学生/教师顺序PT→TRT，各完整池一次，总11802次正式调用；PT I/C/b分别8/8/1、4/8/2、12/24/2；TRT分别8/16/2、2/8/4、8/16/2。人数b仍无准入作用。seed20261118、预热30秒、客户端60秒超时，trace关闭。保存逐图完整响应/同后端顺序差异、每端口实际OpenAPI、资源与原始日志，不计容量；每轮新目录和原GPU/主机预算保护，失败保留停止。真实GPU完成与差异/备份尚待实时记录，不将控制启动当执行完成。新阶段冻结e90b31f，后续文档提交不在此阶段中途拉取。

## 2026-11-19 全量执行与独立复核结果

六组均按完整池各一次完成，序号恰为0..N-1、图片ID无重复/缺失、SHA与同后端基线一致；逐行重新计算业务差异与保存comparison相同，两份summary相同，最后事件均为cleanup_complete。原控制551538已自然退出，指定GPU恢复3MiB/0%。Traceback、CUDA out of memory、CUDA error、NMS time limit扫描均0，所有最终响应浮点数有限。

| 接口 | 后端 | I/C/b | 完成/独立图片 | 规范化严格相等 | 计数变化 | HTTP/业务失败 |
|---|---|---|---:|---:|---:|---:|
| sync | pytorch | 8/8/1 | 2162 | 2162 | 0 | 0 |
| sync | tensorrt | 8/16/2 | 2162 | 2162 | 0 | 0 |
| student | pytorch | 4/8/2 | 2162 | 2162 | 0 | 0 |
| student | tensorrt | 2/8/4 | 2162 | 2162 | 0 | 0 |
| teacher | pytorch | 12/24/2 | 1577 | 1577 | 0 | 0 |
| teacher | tensorrt | 8/16/2 | 1577 | 1577 | 0 | 0 |

“严格相等”沿用已冻结canonical定义：忽略TimeStamp、UseTimeMs、FreeCapacity和列表顺序；没有放宽浮点坐标、计数或置信度来取得一致。各实例均实际收到正式请求，分布见summary.per_instance。结果表示这批输入/候选配置下并发相对各自顺序业务输出一致，不表示两后端彼此无差异；原127778框匹配、47参考独有/43新增及学生人数差异等后端对照结论继续保留。原始模型检测框未在此模式重采，混合接口共享predictor竞态和未覆盖正类别仍不在本项结论内。

42个实际实例均捕获完整运行OpenAPI，公开7路径及完整schema结构相同，且与原contracts-tensorrt-runtime-20261119/openapi.json结构相同。JSON文件排版不用于判断契约变化。所有组默认trace关闭，未生成timing-*.jsonl；后续开启/关闭诊断单独执行，不把本次额外保存和比较开销混入容量。

## 本阶段完整证据与备份

- 原始run_id：concurrent-business-audit-20261119，代码e90b31f943f9ec59942297214b0397913f07e08c；计划SHA2f427174f56a84712edb852e41b2ab6fb7178e478bab9322310626e574668501。
- 独立复核目录concurrent-business-analysis-20261119，summary SHAaa1fcbbbc77ad6ae00cab05e724c0fb2a1b08749e0afaf3cda507e5112c79d2d；保存逐组响应/摘要SHA、每端口分布、OpenAPI成员清单及default-off-contract-check.json。
- concurrent-business-checkpoint-20261119/evidence.tar.gz：197源文件、6526744字节、SHA0d01a2ee4a8ee8668f1eb4e9c50ae68184fe169c98132f3f455aafc7b8183f1b。含完整响应、比较、实例日志/配置/资源/事件、42份OpenAPI、驱动/日志、分析及两环境各32项CPU回归证据。源文件打包前后不变。
- 本机/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/concurrent-business-checkpoint-20261119/已核对整包及197成员、解包，local-verification.json保存结果。完整配置/照片/逐图响应均不推Git。

本项实验完成；真实GPU统计开关/开销、教师单双发生器、显式PyTorch回退、读取/下载成本与最终完整性/图表/交接继续。结果不构成部署或精度采用授权。
