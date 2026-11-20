# 基线与结果留存

直接基线为已完成的Python TensorRT项目版本及同SHA Engine，不重新比较Torch，也不改C++。参照 `../20261119-tensorrt-project-migration/reports/20261120-performance/report.md`：单worker I1/C1/b1有限稳定性sync14.65667、student12.97556、teacher45.87667图/s，对应GPU显存1567/1611/1571MiB。旧值只作历史参照；新高并发、不同worker拓扑不能直接拼接成同窗配对或复用零失败结论。

本次使用原全量Base64请求池full-performance-payloads-20261118，sync/student2162、teacher1577；逐图ID/SHA和请求字节哈希、池aggregate SHA在服务器CPU预检核对，旧池不修改。三接口独立使用对应池，固定时间不保证请求次数/图片覆盖相同，逐轮覆盖和频次另报；不做人工标注准确率或误检/漏检结论。

私有服务器产物统一 `/home/zhangs/workspace/vbas-benchmarks/trt-concurrency-knee-20261120-r1/`，如目录已存在则新run_id；每轮独立子目录。备份位于本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/` 的同名checkpoint。未开始的目录/计划不得当执行完成证明。

保存运行代码/工具SHA、环境清单、模型/manifest/配置哈希、plan、启动/就绪/预热/正式/cleanup事件、原始请求/错误体、PID树、OpenAPI、每worker日志与资源。整包前后源指纹不变，整包和逐文件清单本机核验解包；旧包和失败记录不覆盖。Git仅提交脱敏报告、计划、必要工具和聚合指标，不推照片、完整私有配置、日志或Engine。


最终27唯一组合由r1三轮+r2三轮+r3二十一轮构成，完整原始包、图包、模型交接包及SHA见最终报告。所有失败与旧阶段包保留；本机summary/CSV原件重算与服务器逐字节一致。管理脚本自身资源未采项作为待确认限制，服务worker与发生器采样范围明确。
