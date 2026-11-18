# 环境准备执行记录

状态：执行中，不能据此认定 A 阶段验收通过。

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
