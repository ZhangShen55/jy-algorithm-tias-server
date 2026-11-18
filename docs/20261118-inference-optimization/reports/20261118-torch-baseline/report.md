# PyTorch FP16 全量基线采集

状态：全量采集与小样本重复性检查完成；尚未完成高并发一致性、业务结果自动比较及容量实验验收。

## 环境与输入

指定物理 GPU 1 RTX 3090，驱动 580.126.09，PyTorch CUDA runtime 13.0。基线采集运行代码为 89da431；主机环境与模型 SHA256 见产物 manifest.json。

3739 张图片均为 1920×1080，可解码；91 条记录与其他图片内容完全重复。全量保留并通过哈希关联，不将相似/重复帧当作独立场景覆盖的证明。

采用配置文件默认阈值、单请求单图、顺序调用；人数接口配置全图 ROI，学生/教师接口不裁剪 ROI。原始图片与请求标识关联，图片内容未嵌入 Git 文档。

## 采集结果

| 接口 | 记录数 | HTTP/初步业务状态错误 |
|---|---:|---:|
| /AE/SyncTasks2 | 2162 | 0 |
| /ImageDetect/student/v1.0.0 | 2162 | 0 |
| /ImageDetect/teacher/v1.0.0 | 1577 | 0 |
| 合计 | 5901 | 0 |

12387 份模型预测记录的权重类型均为 torch.float16。保留 NMS 后、业务过滤前浮点框/置信度、模型阶段统计及完整业务响应。采集器为进程内 TestClient，所记耗时含采集开销及冷启动，不作为真实网络容量数据。

六次调用的小样本重复性检查：同类框按 IoU≥0.5 一对一匹配，358 框匹配、0 缺失、0 新增。此结果不等于全量逐位确定性或真实准确率；坐标和置信度差值保存在 differences.jsonl，尚待汇总。业务响应比较尚未自动完成。

## 产物与备份

- 全量：`/home/zhangs/workspace/vbas-benchmarks/torch-fp16-baseline-20261118/`。
- 数据清单：`/home/zhangs/workspace/vbas-benchmarks/dataset-20261118/`。
- 重复性对照：`/home/zhangs/workspace/vbas-benchmarks/torch-repeat-comparison-20261118/`。
- 服务器打包：`/home/zhangs/workspace/vbas-benchmarks/torch-fp16-baseline-20261118.tar.gz`。
- 本机额外备份：`/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/torch-fp16-baseline-20261118.tar.gz`。
- 备份 SHA256：`8a79b1c56c3817c8282f361178c502fb767b78ddbc1ecb3d4a5109df486092ba`。

## 小规模工具验证

学生接口 I=1/C=1、5 秒试运行：35 请求、35 成功、0 失败。窗口内 6.8 图/s，成功图片客户端延迟 P50 140.14ms、P95 153.94ms、均值 142.05ms。该轮仅验证 HTTP 工具与清理流程，时间太短且可能与全量采集尾部相邻，不作为正式性能基线或峰值结论。

## 下一步

三个接口分别探索实例×并发曲线，任何失败检查原因；推荐配置要求测试窗口内零失败。TensorRT 仅在独立环境准备依赖，尚未构建引擎。真实准确率缺少标注，按用户要求先做一致性对照。
