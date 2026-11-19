# 基线与结果留存

## 可复用证据

既有任务 docs/20261118-inference-optimization/ 独立保留。18组同配置配对共107942次零失败，TRT/PT吞吐比三轮中位：人数1.50174、学生1.77366、教师1.54984，见该任务 reports/20261119-backend-paired/report.md。全量同接口审计11802次与各自顺序基线规范化一致，不能外推混合接口竞态。

修正版 PT/TRT 每端5901条，原始框127778匹配、47参考独有、43新增；学生人数31张计数不同，最多1。没有标注，不能当真实准确率；差异报告需用户复核。人数NMS=True、学生人数NMS=False必须保持，旧学生True记录不作为新参考。

迁移参考分两层：①同一 SHA Engine、同形状和业务配置的现有 TRT 路径，验证打包和加载变化；②既有 PT FP16 和修正版差异，说明后端本身变化。Engine重新构建后需独立全量比较，不默认与旧 Engine 数值相等。

## 本轮新增模型对照证据

按02固定四模型各100张PT FP16/TRT对照；人数同100张额外验证True/False两种NMS口径。保存抽样清单SHA、两后端逐图模型输出、逐框匹配/未匹配、模型及类别汇总、全部计数差异和私有叠框图。历史全量报告是参考，不能代替项目model/内本轮实际Engine的100张验证。抽样层和历史差异富集层分别统计，不声称真实准确率；报告完成与用户接受差异分别记录。

## 版本和存储

运行标识采用 trt-migration-YYYYMMDD-阶段-rN。服务器独立目录 /home/zhangs/workspace/vbas-benchmarks/<run_id>/；本机 /Users/zhangshen/.codex/backups/vbas-benchmark-20261118/<run_id>/。Git 仅保存脱敏报告、必要聚合结果和复现脚本；引擎与权重即使位于仓库 model/ 也不提交。

每组关联代码 commit/dirty diff、dataset清单SHA、配置SHA、模型及Engine SHA、manifest SHA、环境锁定清单（本轮不构建镜像）。保存每请求ID/图像SHA/序号/完整响应与比较、OpenAPI、资源、日志、错误、启动/清理记录。整包之前和之后计算源文件指纹，源发生变化则该包不作完整封存；整包SHA/大小和逐文件清单在本机核验解包。旧完整备份不删除、不覆盖。

manifest.json 对每模型记录源PT SHA、ONNX SHA、含Ultralytics元数据头的engine文件SHA、FP16构建选项、实际I/O名称/dtype/shape、类别名称/顺序、GPU型号/compute capability、构建UUID、OS/CPU架构、TensorRT/CUDA/driver/torch/Ultralytics版本、构建代码SHA。普通/secure产物分别记录明文SHA/密文SHA，清单不含密钥。SHA只能证明完整性，不能代替可信发布来源；只加载本项目受审构建产物。

## 本轮已封存阶段索引

- [预检与旧资产](reports/20261119-preflight/report.md)：原权重/Engine/环境及回退单元冻结。
- [四模型100张](reports/20261119-model-comparison/report.md)：同shape输出差异、私有图及完整备份；用户采用待复核。
- [业务全量](reports/20261119-business-regression/report.md)：新TRT顺序/同接口并发11802次与旧参考一致。
- [专项输入/几何/混合/旧PT恢复](reports/20261119-functional-regression/report.md)：同Engine42项一致，原PT几何8项计数变化独立记录。
- [保护/双worker](reports/20261119-protection/report.md)：四Engine密文、4加载负例和双worker两模式。

各报告包含独立run_id、整包SHA和本机逐文件核验位置；性能稳定性和最终全件证据尚未完成，不能以阶段包冒充最终交接。
