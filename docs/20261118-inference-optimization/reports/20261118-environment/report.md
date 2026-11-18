# 环境准备执行记录

状态：环境准备及三接口 FP16 冒烟通过，全量基线采集中；尚未执行容量压测。

## 已执行

- 本地 perf 分支方案提交 e60763f 已推送并同步服务器。
- 服务器仓库 Git 身份已设置为 zhangshen55 / 865325136@qq.com。
- 原环境 Conda 显式包清单及 pip freeze 已导出，位于 `/home/zhangs/workspace/vbas-benchmarks/environment-20261118/`。
- 正在克隆 `/root/anaconda3/envs/jy-tias` 至 `/home/zhangs/.conda/envs/vbas`，原环境未改动。
- 已添加 FP16 显式配置 InferenceHalf，默认 false，测试配置 true；非 CUDA 环境拒绝 FP16 而非静默回退。
- 已修复旧接口启用和执行时的扁平目录相对导入问题；实际人数接口为 `/AE/SyncTasks2`，不新增 `/SyncTasks2` 路由。
- 已提供独立图片清单工具与三接口顺序基线采集器，后者使用进程内 TestClient，不代表 HTTP 压测结果。
- 用户确认暂无人工标注，先进行后端一致性评价。

## 待验证

环境克隆完成、CUDA runtime、四模型实际 FP16 推理、三接口响应与结果有效性、数据清单生成及重复性检查。尚未执行容量压测或 TensorRT 导出。

## 代码验证

新增采集工具、设置及入口已通过 Python 语法编译，差异格式检查通过。GPU 运行和接口验证结果待补，不以语法检查替代实际推理。

## 实际验证结果

- 克隆完成，新环境 Python 路径为 `/home/zhangs/.conda/envs/vbas/bin/python`。测试依赖增加 httpx 0.28.1、httpcore 1.0.9，原环境未变；前后 pip freeze 已保留。
- 指定设备 NVIDIA GeForce RTX 3090，UUID 与约定一致，PyTorch CUDA runtime 13.0。
- 三接口各一图均 HTTP 200 且检测结果非空；四模型权重均为 torch.float16。首次调用含初始化，不用作容量结论。
- 冒烟产物：`/home/zhangs/workspace/vbas-benchmarks/smoke-fp16-20261118-r2/`；首次缺 httpx 的失败日志也保留。
- 图片清单：`/home/zhangs/workspace/vbas-benchmarks/dataset-20261118/`，3739 张全部可解码，91 张为完全重复记录。清单 SHA256 为 `559803834483b28769272b4a70b0f79fce324e3f4ea8124daf73380cf9559b78`。
- 全量采集已启动：`/home/zhangs/workspace/vbas-benchmarks/torch-fp16-baseline-20261118/`，预计 5901 次接口调用。尚未完成，不标记基线冻结。
