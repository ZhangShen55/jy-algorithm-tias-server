# 环境与约束

执行仓库：本机 `/Users/zhangshen/Documents/workspace/vbas` 分支perf，准备起点a3ecbd0；服务器ssh zhangs12、`/home/zhangs/workspace/vbas`，最近成功查询3f77bfd且Git干净。正式前核对代码差异及同源运行实现，CPU检查后仅空闲时同步所需工具；测量期间冻结实际提交，不拉取后续文档。AGENTS.md为用户文件，不提交覆盖。

唯一设备为物理GPU1 RTX3090 UUID `GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49`、24576MiB。启动前使用UUID限制可见设备并实际核对名称/计算能力/UUID，内部cuda:0。保留jy-tias/vbas/vbas-trt，不升级驱动/库、不动其他服务、main_910b_npu或部署脚本。TensorRT10.13.3.9、Ultralytics8.3.156、Torch2.12.1+cu130/CUDA13.0为既有受测版本，正式前保存本次实际清单而不是假定。

沿用项目model/同SHA四FP16 Engine及manifest，batch1、人数/人脸/学生1088×1920，教师384×640且ImageSize640。源权重不变，不在线导出或下载、不回退CPU/PT。普通模式、不启用trace、不修改阈值/NMS/接口schema。测试仅loopback空闲端口，关闭外部注册，按原验证开关暴露SyncTasks2。

每轮资源检查：指定GPU无任务遗留且空闲；主机可用内存至少 `8 + 1.5 × 实际模型worker总数` GiB，父管理进程不冒充模型worker。GPU预算参考既有每worker1567～1611MiB并保留余量，实际装载与预热逐步观察，未知错误/资源不足停下留证，不强行16worker、不换其他卡、不删除其他服务进程。只读估算不是实际GPU装载上限。

现有instances.py固定--workers1，只采父PID；每实例多worker路线需要补足子进程/PID覆盖、就绪和进程组清理，CPU验证后才可GPU。SSH恢复、worker语义和准入上限确认均是正式启动依赖。
