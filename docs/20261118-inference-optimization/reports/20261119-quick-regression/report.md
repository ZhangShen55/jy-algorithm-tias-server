# 固定快速回归输入与历史采集格式兼容

状态：两后端共同的三接口各64张已冻结，192个逻辑图片/接口样本；CPU输入预检通过，未启动新GPU任务。用于后续诊断，不作无偏准确率评估。

## 选择与请求

regression.py读取两份corrected-baseline，确认接口/图片ID/SHA集合一致，固定seed=20261118。保留所有后端业务计数差异图片、每个非空输出类别的首个代表、显式慢请求image1/0078.jpg及0079.jpg，再从剩余图片按种子补足每接口64张。若强制留存已超过目标，工具显式扩大而不删差异。本批恰好各64。

选择发生在HTTP统计开销测试之前。该集合有意富集差异/慢请求，不能用它估计全数据精度或正常吞吐。学生举手/站立没有非空最终输出，不能声称这些类别得到有效正样本覆盖。

| 接口 | 图片数 | 包含业务计数差异的图片数 | 非空输出类别数 |
|---|---:|---:|---:|
| /AE/SyncTasks2 | 64 | 9 | 2 |
| /ImageDetect/student/v1.0.0 | 64 | 39 | 5 |
| /ImageDetect/teacher/v1.0.0 | 64 | 1 | 5 |

两后端使用完全相同的192个图片ID/SHA，各自保存原始顺序输出为torch-reference.jsonl和trt-reference.jsonl；没有重新采集/修改检测值。payloads.py从Torch子集和原tests图片重建Base64请求，逐图SHA校验；完整请求参数、ROI与阈值沿用原冻结基线及配置，不为对照改阈值。

## CPU预检与历史格式

首次预检发现89da431/6ffb689采集器将整个ImageList从request元数据省略。通过Git原始源码确认旧逐图项只含ImageID或ImageId及图像字节；审计比较时从已有image_id恢复ID，字节仍按image_sha256核对，并拒绝任何额外逐图选项。原始基线不补写、不覆盖。

第二次预检发现旧PyTorch记录没有runtime_fp16字段，但保留weight_dtype=torch.float16和predict_args.half=True。审计允许这组历史证据；明确的runtime_fp16=False仍拒绝，不能被旧权重标记覆盖。TensorRT仍要求实际runtime_fp16=True；学生人数必须是新NMS=False元数据，旧继承True基线拒绝。两个失败的CPU预检记录和候选源码保留，未启动模型/GPU任务，随后从有效请求池恢复，没有重生成覆盖输入。

修正后R3预检对两后端×三接口的快速池及完整池均通过：快速各64，完整人数/学生各2162、教师1577；图片字节SHA、接口覆盖、请求参数及已有精度/学生NMS元数据均核对。此项只验证输入和基线关联，不等于真实GPU并发一致性或精度通过。

## 产物与校验

服务器 `/home/zhangs/workspace/vbas-benchmarks/quick-regression-20261119/`：selection.json、两个reference.jsonl、payloads及清单、preflight-r1/r2/r3.json、checksums.json。selection保留原始两份全量JSONL SHA及选择脚本SHA；R3保留实际预检候选代码SHA。完整路径和复现脚本均可追溯。

压缩包 `/home/zhangs/workspace/vbas-benchmarks/quick-regression-20261119.tar.gz` 已取回本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/quick-regression-20261119.tar.gz`，SHA256 `bcc16106b1564ba4c8757a9e6d5592cf74128e31e7d4c5fe5d60441566d4b444`；解包后201项逐一校验通过。图片/Base64、原始预测与私有配置不推Git，只提交工具和摘要报告。
