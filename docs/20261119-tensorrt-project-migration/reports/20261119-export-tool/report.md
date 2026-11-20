# 离线四Engine构建工具验证

实现及测量代码f5a7f3ae7baf36cc6ca615e06d03acd01ecb49c5，指定GPU1 RTX3090、vbas-trt环境。显式source-root、全新output和GPU UUID；模型源SHA与受审原件一致，未修改旧benchmark导出脚本或原权重。沿用静态batch1、FP16构建、TF32关闭、HALF I/O、Ultralytics长度头+JSON元数据封装。

r1因用户暂停在两件Engine产出后停止，无完成manifest，原目录/日志/user-pause.json保留。恢复后以独立trt-migration-20261119-export-check-r2完整构建四件，耗时1058.654秒（含工具进程和后续验证，不是服务启动时延）；导出与独立GPU校验均返回0。实际反序列化、四模型HALF输入输出、类别/shape及warmup全部通过，只有整套完成后才生成有效manifest。

新构建仅验证离线工具，fresh_release_adopted=false。项目model/仍使用已完成100张对照的原受审发布，四Engine/manifest/目录说明在工具前后SHA全部相同。没有把本次fresh构建当成已完成精度或业务全量对比的发布；若采用它需另行重复相应模型/业务验证。

完整包trt-migration-20261119-export-checkpoint-r1/evidence.tar.gz含r1暂停和r2完整构建、PT/ONNX/Engine/层信息/构建记录/manifest、控制脚本及日志，共44文件，2346343050字节，SHA256 f86ac31678760364f7e1dc191be557cf297b74a55f556cb30137b1b0a4db004b。源前后不变，2026-11-20完成本机整包、44成员和全部解包文件核验。

首次SFTP同步文件长度长时间停在1821834240字节，未据此启动性能测试。已终止该传输，保留.partial-transfer-r1及分类记录，经SSH字节流续传后对完整原包重新核对SHA及全部成员；未重建或更改证据包。传输停滞的底层网络原因未证明，不归因为GPU或模型失败。

后续有限性能使用原受审Engine，独立日期20261120新run_id；不重新搜索原容量、不部署或合并。
