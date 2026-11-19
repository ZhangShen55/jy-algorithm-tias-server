# 同Engine业务全量回归

采集版本8234554，原参考e90b31f；指定RTX3090 GPU1、FP16、trace off、HTTP60秒、无重试。新路径使用项目model四Engine；旧TRT corrected参考SHA为0a8b40f11a64031e88dc2656519f7af19804625ab75bc7822f939b0b49eb5c4b。未改变阈值、队列或准入。

| 场景 | 人数 | 学生 | 教师 |
|---|---:|---:|---:|
| 顺序I1/C1/b1 | 2162 | 2162 | 1577 |
| 同接口并发 | 2162 | 2162 | 1577 |

并发分别I8/C16/b2、I2/C8/b4、I8/C16/b2。六组11802次均HTTP/业务成功，与各自旧TRT参考规范化严格相等，计数变化0。逐请求ID/SHA/序号、重算比较、双摘要及cleanup复核通过。21实际实例运行OpenAPI公开7路径和完整schema相等，也与原TRT契约相等。无trace文件，所有实例已回收。

本项是最终业务响应一致性审计，不作为容量成绩，不覆盖模型原始框或真实准确率。PT/TRT已有差异仍以100张对照及历史报告为准。

私有run_id：trt-migration-20261119-business-r1、trt-migration-20261119-business-analysis-r1。完整包trt-migration-20261119-business-checkpoint-r1/evidence.tar.gz，140文件、16350948字节、SHA256 e7507f5296574f17d86164735f41b183414b15b2048c0adc9d717b27ce96ccea。打包前后源未变，本机整包、全部成员及解包文件核验通过；本机位置在用户.codex/backups/vbas-benchmark-20261118/同名目录，完整配置/响应/日志不入Git。
