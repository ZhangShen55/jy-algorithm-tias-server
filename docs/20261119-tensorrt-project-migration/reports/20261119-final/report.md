# TensorRT项目迁移完成交接

状态：2026-11-20，用户缩减重复配对后的约定实施、验证、报告与完整备份已齐备。工作完成与用户精度采用/部署分开；RSS增长及覆盖限制如实列示。

## 交付行为

四模型统一从项目根model/读取：person_count.engine、face_count.engine、student.engine、teacher_behavior.engine及manifest.json。默认TensorRT FP16、batch1；前三输入1088×1920，教师384×640。教师配置ImageSize仅640，其他值在导入GPU库/解密前明确报错；原图分辨率可变。

模型源、构建与实际I/O/类别/环境和SHA均有清单。项目采用trt-migration-20261119-model-release-r1，四Engine与原受审资产逐字节相同，新增离线导出工具验证产物不替换它。运行实现冻结f5a7f3ae7baf36cc6ca615e06d03acd01ecb49c5，旧参考冻结e90b31f943f9ec59942297214b0397913f07e08c；后续文档提交与测量代码分开。

服务不加载PT源权重、不自动退CPU/PT、不在启动时导出或下载；torch/torchvision仍为Ultralytics预处理和NMS依赖。每模型锁覆盖完整predict调用，旧人数True、学生人数False的NMS口径保留。HTTP路由、schema、阈值及正常准入策略保持，混合诊断b3仅用于共享状态检查，不是容量推荐配置。

## 已完成证据

| 验证 | 有限结论 | 详细报告 |
|---|---|---|
| 资产/实际后端 | 四Engine来源SHA、真实HALF I/O、类别/shape及warmup通过 | [预检](../20261119-preflight/report.md) |
| 各模型100张 | 两端各500正式调用、数值合法；6254匹配、5PT独有/2新增（人数NMS复用同100张） | [模型对照](../20261119-model-comparison/report.md) |
| 三接口全量 | 顺序及同接口并发11802次均成功，与旧TRT参考严格一致 | [业务回归](../20261119-business-regression/report.md) |
| 几何/输入/混合 | 42同Engine专项一致，交替/576混合对独立参考一致；原PT8项计数变化独立保留 | [专项](../20261119-functional-regression/report.md) |
| 直接启动/恢复 | 不同cwd、重启、Health/WorkerStatus/Drain通过，旧PT单元各64图恢复一致 | [专项](../20261119-functional-regression/report.md) |
| 保护/双worker | 四Engine真实加密、4加载负例无明文残留、两种清理模式24调用一致 | [保护](../20261119-protection/report.md) |
| 代码审查 | 无已确认Critical/Important；1项报告SHA占位符已纠正 | [审查](../20261119-code-review/report.md) |
| 离线导出工具 | 独立r2四模型构建/实加载返回0，未替换受审发布；44文件完整备份本机核验 | [构建报告](../20261119-export-tool/report.md) |
| 输入/阶段备份 | 3739照片逐SHA核对及双端完整包验证，其他阶段各包整包/成员核验 | [证据索引](../20261119-evidence-index/report.md) |

模型一致性是相对PT的输出比较，不是人工标注准确率/mAP。每模型80随机+20历史差异富集，无偏精度估计不成立。47张私有叠框图和逐图逐框差异保留；Other没有模型输出覆盖，举手/站立最终业务正例不足。用户差异接受/采用尚待复核。

## 有限性能及最终验证

用户缩减后14配对+3稳定性必需轮共208050次正常请求成功、零失败；另13562次已开始的教师未配对观察独立保留。三30分钟窗口人数26383、学生23357、教师82579次成功，服务端RSS有小幅增长、GPU显存稳定，未作无泄漏/长期稳定性或生产验收结论。详细分位数、CPU/RSS趋势、窗口和收益限制见[性能报告](../20261120-performance/report.md)。当前迁移前后TRT吞吐人数三对中位+0.54%、学生+2.94%、教师单对+3.86%，不把历史后端收益重新归因于目录迁移。

最终直接main:app从/tmp、项目model/、I1/C1/b1、queue0、独立18983端口完成三接口各64图共192次，全部与独立TRT参考一致；Health/WorkerStatus/Drain通过，测试服务已退出。完整handoff包25文件含四Engine、manifest、代码bundle、配置/日志/响应和环境记录，本机整包及全文件核验通过。两用户环境freeze与起点相同，既有pip check声明冲突仍存在，没有安装升级；不称依赖声明无冲突。

## 启动及整版恢复边界

新服务直接启动准备、GPU UUID映射、项目路径解析、静态/实际GPU检查和保护配置见[RUNNING](../../../../RUNNING.md)。独立测试必须关闭VisionOrchestratorBaseUrl，使用空闲loopback端口，不切换线上服务。缺文件、错SHA、版本/设备/半精度不符明确失败。

旧PT恢复单元保留在服务器私有trt-migration-reference-code-20261119，配合vbas环境、旧配置和四源PT作为整体。实际恢复测试从/tmp启动独立18979端口，完整命令/环境及配置SHA在functional-r2/old-pytorch-recovery/launch.json和同目录私有配置，三接口各64图响应与独立PT参考一致。恢复不要求新TRT-only服务支持PT，未停止/切换任何线上服务。

加密双worker使用/dev/shm之外受控持久KeyFile；源密钥保留。旧secure entrypoint的共享一次性副本引导未在本轮修改/验证，不能把双worker功能结果当成该容器流程已通过。

## 未授权及未验证范围

没有部署、合并、镜像构建或C++改造；旧Docker CUDA11.8与本次CUDA13/TensorRT环境差异须在后续部署前单独解决。只验证指定物理GPU1 RTX3090 UUID GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49，不承诺其他平台或版本兼容。无生产SLO，不据有限测试宣称生产容量验收。用户精度差异接受、采用及部署决定均另行进行。

原优化任务与本迁移独立：旧42轮已自然结束，但其未完成的总归集/部分补证仍不能由本迁移结项代替。已删除vbas定时器，不重建、不自动归档聊天。所有旧环境、原始资产和已核验备份保留。

已完成效率结果见[独立检查点](../20261120-efficiency-checkpoint/report.md)，配对按用户要求缩减，稳定性继续；不增加对比组。

## 可复核启动与恢复命令

下面是已验证的私有配置（注册关闭、Sync开关为验证打开、b1/queue0）；不会自动启动常驻服务。需要使用时在授权服务器执行：

```bash
CONFIG_PATH=/home/zhangs/workspace/vbas-benchmarks/trt-migration-20261119-handoff-r1/direct-server-config.json CUDA_VISIBLE_DEVICES=GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49 /home/zhangs/.conda/envs/vbas-trt/bin/python -m uvicorn main:app --app-dir /home/zhangs/workspace/vbas --host 127.0.0.1 --port 18983 --workers 1
```

旧PT整版恢复的独立验证配置和代码单元仍保留：

```bash
CONFIG_PATH=/home/zhangs/workspace/vbas-benchmarks/trt-migration-20261119-functional-r2/old-pytorch-recovery/config.toml CUDA_VISIBLE_DEVICES=GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49 /home/zhangs/.conda/envs/vbas/bin/python -m uvicorn main:app --app-dir /home/zhangs/workspace/vbas-benchmarks/trt-migration-reference-code-20261119 --host 127.0.0.1 --port 18979 --workers 1
```

原恢复采集使用委托main:app的私有probe wrapper以采PID；上述main入口与原工作区/配置/环境相同，不对新TRT服务提供PT开关。照片相对路径根需按实际场景配置；Base64验证不依赖生产图片路径。启动前核对空闲端口/GPU及可信模型清单，不切换线上实例。

## 完整性与退出

完整十个证据包及SHA见[证据索引](../20261119-evidence-index/report.md)，包含模型100张/47私有图、所有阶段失败分类与恢复、全量图片/payload、请求/响应/资源/OpenAPI、源PT/Engine/ONNX、配置和测量代码bundle。现有原始报告与旧备份保留。

最终核对指定GPU3MiB/0%、无本任务服务/发生器进程、驱动580.126.09未变；受保护Docker/启动脚本/main_910b_npu无差异，旧环境保留，没有停止/部署其他服务。该核对不是全机其他服务业务验收。代码及脱敏文档提交perf；最终提交由Git记录与交接状态关联，测量实现f5a7f3a，后续仅文档及配置示例注释变化。用户AGENTS.md保留且仅本机忽略，模型/私有资料按既定忽略规则保留；不使用git clean删除用户文件，不重建定时器或归档聊天。
