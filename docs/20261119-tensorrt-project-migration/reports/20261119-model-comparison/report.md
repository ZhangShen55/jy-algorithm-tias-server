# 四模型各100张PT FP16 / TensorRT Engine对比

状态：采集、逐框比较、47张私有对照图及完整备份/本机逐文件校验完成。用户差异复核/采用尚待决定；不是人工标注准确率或mAP验收。

## 方法与关联

项目model/内四个Engine与既有受审FP16 I/O Engine文件SHA相同，源PT SHA已逐模型核对。采集代码8b09a01，分析代码8234554；单模型输出在业务聚合前、NMS后保存，PT和TRT使用同固定shape、rect=False、FP16、conf/IoU/max_det和NMS。没有使用新服务的TRT-only开关加载PT；PT由独立采集工具显式加载。

每模型100个不同内容SHA，80随机+20历史差异，不足补随机；seed20261119。四模型共400个模型-图片配对，人数同100张另测True/False两种NMS，故每后端500次正式单模型调用。各端500次全部成功、零失败，另外的每模型一张零图warmup不计正式调用。由于三个人数/人脸/学生池可共用图片，本次实际封存206张不同源图。样本是富集检查集，不能作为无偏精度估计。

冻结清单SHA：6de7bbc7757a0391cb67d6b4fd9a16e6a92066e3d3ecbad1d1ce1d705ca19577。PT结果SHA822b6da2c2d583517bfb710511b7425305936558ebc98daeaf2271cc37523665；TRT结果SHA7868962e04f15f34340c65e8e472958a26122e8c41e7793cf672991a91c8ba76。

按同类别IoU>=0.5降序贪心一对一匹配，0.5只是匹配口径，不作精度合格线。无框和未匹配框完整计入；所有数值/类别/置信度/几何检查通过。

## 总体结果

| 模型/口径 | 图片 | PT框 | TRT框 | 匹配 | PT独有 | TRT新增 | 平均IoU | 最大坐标差px | 计数不同图片 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| face_count/default_false | 100 | 414 | 414 | 414 | 0 | 0 | 0.99715634 | 2.0 | 0 |
| person_count/legacy_true | 100 | 2594 | 2594 | 2594 | 0 | 0 | 0.99748159 | 2.0 | 0 |
| person_count/student_false | 100 | 2639 | 2635 | 2635 | 4 | 0 | 0.99750552 | 2.0 | 4 |
| student/default_false | 100 | 410 | 410 | 409 | 1 | 1 | 0.99853475 | 2.0 | 2 |
| teacher_behavior/default_false | 100 | 202 | 203 | 202 | 0 | 1 | 0.99602913 | 3.0 | 1 |

IoU是匹配框重叠指标，不是准确率。全部500次输出中，6254框匹配、5框PT独有、2框TRT新增；人数两种NMS重复使用同100张，这些总数不当成独立500张统计。框差异不能无标注地称误检/漏检。

## 各模型置信度、覆盖与参数

- face_count/default_false：匹配框置信度绝对差均值0.00090757、P95 0.00268555、最大0.00476074；最小IoU 0.93028190。
- person_count/legacy_true：匹配框置信度绝对差均值0.00060840、P95 0.00195312、最大0.01635742；最小IoU 0.89950624。
- person_count/student_false：匹配框置信度绝对差均值0.00066939、P95 0.00244141、最大0.01635742；最小IoU 0.89950624。
- student/default_false：匹配框置信度绝对差均值0.00098373、P95 0.00292969、最大0.00390625；最小IoU 0.96428571。
- teacher_behavior/default_false：匹配框置信度绝对差均值0.00051729、P95 0.00244141、最大0.00488281；最小IoU 0.96312972。
- person_count：分层{'random': 80, 'historical_difference': 20, 'random_fill': 0}；参数{"conf": 0.1, "iou": 0.7, "max_det": 300, "rect": false, "half": true, "verbose": false, "imgsz": [1088, 1920], "agnostic_nms": false}。
- face_count：分层{'random': 80, 'historical_difference': 20, 'random_fill': 0}；参数{"conf": 0.1, "iou": 0.7, "max_det": 300, "rect": false, "half": true, "verbose": false, "imgsz": [1088, 1920], "agnostic_nms": false}。
- student：分层{'random': 80, 'historical_difference': 20, 'random_fill': 0}；参数{"conf": 0.5, "iou": 0.7, "max_det": 300, "rect": false, "half": true, "verbose": false, "imgsz": [1088, 1920], "agnostic_nms": false}。
- teacher_behavior：分层{'random': 80, 'historical_difference': 20, 'random_fill': 0}；参数{"conf": 0.25, "iou": 0.7, "max_det": 300, "rect": false, "half": true, "verbose": false, "imgsz": [384, 640], "agnostic_nms": false}。

类别覆盖、逐类误差及随机/富集层完整指标见同目录summary.json。person_count的Other类在这100张中两端均无输出；其余各类有模型输出覆盖。有输出不意味着人工确认的正例，不能据此宣称这些类别真实准确率已验证；原任务中学生举手/站立最终业务正例覆盖不足的限制不因原始模型输出非空而消失。

## 私有差异图与备份

全部未匹配框/计数差异图已保存，其余仅坐标/置信度差异按每模型最大10张保存，共47张；全量逐图逐框数据未截断。已抽查并列图左右PT/TRT标识和框/置信度呈现；未对47张人工做准确率标注。

本机证据目录：/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/trt-migration-20261119-model-checkpoint-r1/；解包后evidence/vbas-benchmarks/trt-migration-20261119-model-analysis-r1/含summary、differences及visual-index/visuals，源图按清单封存。完整照片、响应和配置不入Git。

完整包evidence.tar.gz：279文件（含206张源图），259295746字节，SHA{pkg["package"]["sha256"]}。源前后不变，本机整包/279成员及解包后全部文件核验通过，local-verification.json留存。

## 结论与下一步

本轮100张对比已完成，存在上述可复核差异，采用状态待用户决定。不修改阈值、不删异常样本，也不把数值或框数量差异自动认定为不合格或合格。接续同Engine新旧TRT接口、并发、几何/输入、直接启动和有限稳定性验证；此处不能代替那些完成出口。
