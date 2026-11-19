# 实施预检

检查时间：2026-11-19T16:52:17+08:00。基于d79d6eb开始实施，用户显式调用openspec-apply-change；范围保持项目model/、仅服务器验证、不部署、每模型100张。

OpenSpec日期名称限制通过临时符号链接别名读取CLI指令，实际changeRoot仍为日期前缀目录；别名在读取后删除，不改CLI或正式名称。schema为spec-driven，共37项，初始0完成。

只读SSH核查：旧教师补证42/42个case-result，controller-error不存在，未见instances/load/coordinated或旧控制父进程；指定3090 UUID匹配，3MiB/0%，服务器HEAD为e90b31f，tracked diff为空。没有发信号或启动GPU任务，没有pull。私有库存清单在本机trt-migration-20261119-preflight-r1/inventory.json，含资产SHA/原构建manifest/环境freeze及配置SHA；完整回退单元与备份仍在准备，尚未标记1.3/1.4完成。

本机已有benchmark基线32项CPU测试通过（11.025秒）。不据此声称TRT运行时GPU验证通过。

## 资产冻结与当前实现检查点（2026-11-19T17:04:05+08:00）

旧42轮所有events最终均为cleanup_complete。旧参考代码工作区为服务器私有trt-migration-reference-code-20261119，HEAD e90b31f；现有models目录含受跟踪说明，首次整体链接被FileExistsError保护拒绝，随后仅为未跟踪权重及图片子目录建立引用，未改源文件。每轮仍须核对源哈希；不可变备份是恢复的最终依据。

trt-migration-20261119-reference-r1/evidence.tar.gz：1593570673字节，SHA2dc960f08af14ff468017f51a09877c9972de774999a8869e4a4724fdcaa07c3，26个源文件打包前后不变；本机整包、31个成员及解包后逐文件校验完成，local-verification.json留存。含四源PT、四Engine/ONNX/构建记录、配置、两环境freeze/pip-check及reference.bundle。完整配置不入Git。

当前环境采集于target-environment.json，原始build-manifest完整嵌入新manifest，未将新采集的环境信息伪称为历史完整构建记录。源PT与原manifest一致；四Engine静态复用完成，已放入本机项目model/，新私有发布包run_id为trt-migration-20261119-model-release-r1。实际GPU校验/服务器项目放置尚待执行，不因此标记模型产物最终通过。

core/engine_artifacts.py、inference_runtime.py及离线构建/校验命令已写；settings默认TRT FP16、保留UUID映射、逐模型预测锁/NMS默认隔离已实现。保护工具全件检查、独立临时目录已写，尚待GPU/完整失败矩阵验证。15项新增CPU测试通过（均先验证缺失能力或旧错误路径再实现），原32项benchmark回归亦通过；不将CPU测试冒称真实Engine验证。
