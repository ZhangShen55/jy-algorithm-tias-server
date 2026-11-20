## Context

当前core/settings.py已有实验TRT分支，默认仍为pytorch/half=False；从models/*.pt的stem推导嵌套Engine路径。scripts/benchmark/export_engine.py可生成带Ultralytics元数据头的FP16 Engine，但硬编码本次3090设备。保护工具默认PT且跳过缺件，多个worker解密使用同名临时路径。项目需要将这些实验能力整理成可直接启动的服务能力。

方案依据：docs/20261119-tensorrt-project-migration/README.md及01～07。文档含方法/证据/出口，change的spec定义实现契约，tasks管理实施；执行中每个子任务开始、实质检查点、完成或阻塞时同步源05的状态、数量、北京时间和证据/run_id，聚合任务全件完成才勾选；README更新当前阶段、07按实际证据更新出口。变更范围或方法时同步两处，不让原实验任务被本迁移状态覆盖。当前主spec目录无正式规范，不将归档中旧头姿和接口格式带回现代码。

## Goals / Non-Goals

**Goals:**
- 项目model/内四个FP16 Engine可直接服务，来源、环境、输入输出可核验。
- 保持现有HTTP契约、NMS、坐标和业务语义，提供每模型100张PT/TRT对比及可复核结果。
- 在指定服务器独立端口完成直接启动、重启、并发、稳定性及旧版本恢复，证据完整留存。

**Non-Goals:**
- 不部署、不合并上线、不改Dockerfile/compose/线上配置，不做C++、动态profile、新batch、INT8或NMS插件优化。
- 不移除Ultralytics所需torch/torchvision，不把无标注的一致性报告称真实准确率或mAP。
- 不扩大GPU使用范围，不重新启动旧实验、增大C256或重建定时器；不把旧任务未完部分记为完成。

## Decisions

### 1. Engine作为明确运行资产

model/person_count.engine、face_count.engine、student.engine、teacher_behavior.engine及manifest.json组成一套原子发布资产。EngineRoot默认锚定项目根并解析绝对路径，不依赖cwd；旧models/*.pt仅供离线构建、PT对照和旧版本恢复，新服务不依赖它们。

优先核验并复制已有engines-fp16-io-20261118资产至新私有release目录，检查通过后放入项目model/；不覆盖历史资产。目标已存在且不一致则失败，不默默混装。需重建时使用scripts/export_tensorrt_models.py离线转换，source-root/output/device显式传入，输出必须不存在，四模型全部验证完成后才写完成清单。旧benchmark导出脚本不改写，保留历史复现。

manifest包含schema_version、release_id，以及每模型源PT/ONNX/Engine SHA、类别映射、NCHW形状、I/O名称/dtype、FP16/TF32设置、GPU型号/compute capability/构建UUID、OS/CPU架构、TensorRT/CUDA/driver/torch/Ultralytics和构建代码版本。密文另有SHA、不存密钥。Engine文件SHA包含Ultralytics头；反序列化前正确分离长度头和JSON元数据，不能将完整封装文件当裸plan。清单完整性不能替代可信来源，仅接收本项目受审资产。

scripts/verify_tensorrt_models.py提供CPU静态校验和显式GPU加载诊断，后者核对实际后端、I/O和warmup。构建UUID是溯源信息；兼容性按已验证目标GPU型号/计算能力、平台和运行库组合判断，不将同型号新卡的UUID不同误作Engine文件损坏。本轮执行设备仍严格限定授权UUID。

### 2. TRT-only服务与必要依赖分开

core/inference_runtime.py承载四模型映射、manifest/设备检查、YOLO Engine加载和warmup；settings保留配置解析及现有模型对象引用。默认InferenceBackend=tensorrt、InferenceHalf=true；旧pytorch、cpu或half=False配置明确报迁移错误。对照工具独立加载PT，旧版本/环境整体回退，不在新服务中保留隐式切换。

保持YOLO(engine, task=detect)和现有预处理/NMS，而不直接重写TensorRT API，以缩小一致性风险。固定batch1；前三模型[1,3,1088,1920]，教师[1,3,384,640]，I/O HALF，FP16构建、TF32关闭。FP16不表示所有后处理算子都为HALF。启动导出或网络下载均禁用。

四模型全部warmup成功才允许服务就绪或注册，失败终止当前测试实例。设备可见性在导入GPU运行库前建立；继承外层UUID绑定时不把物理序号再次映射成另一GPU，应用内部逻辑cuda:0。GPU不可用不退CPU。

### 3. 保持接口行为并审查共享predictor

审查student_behavior_service、teacher_behavior_service、task_service和task_service_base64的predict参数；保持旧人数agnostic_nms=True、学生人数False。确认现有锁是否涵盖参数更新与实际预测，若不足以隔离，则以每模型锁包住完整调用；同时报告吞吐代价。混合调用交替/并发验证不可由历史单接口审计替代。

静态shape与不同分辨率/ROI及教师ImageSize覆盖可能影响letterbox。分别做同形状模型对照和原业务语义对照；发现不能保持既有语义时保存差异并暂停该实现出口，向用户说明选项，不偷偷忽略配置或新增拒绝行为。

### 4. 保护和文件管理保持兼容

Engine加密工具采用明确四件清单，先全件预检再输出，缺件退出非零；现有加密格式不变。解密目录使用每worker独立0700子目录，加载成功/异常均只清理自己的临时明文；不删其他进程目录、源文件或持久密钥。验证双worker同时加载，复用现有密钥引导机制，不改生产挂载。

.gitignore/.dockerignore排除新model/二进制、密文及中间文件；只跟踪目录说明、脚本和脱敏规范，实际manifest随私有资产保存。修改.dockerignore仅为避免资产意外进入后续构建上下文，不做镜像工作。提供config.toml.example与README/RUNNING直接启动说明，不覆盖完整私有config.toml。

### 5. 每模型100张是独立一致性出口

冻结人数、人脸、学生各自100张学生池样本和教师100张教师池样本；内容SHA去重，按image_id/SHA排序后固定seed20261119，各80张随机+20张历史差异（排重，不足按同随机序列补齐）。实现时记录抽样算法/工具版本和每模型随机序列，清单冻结在新推理之前。跨模型可同图，随机层/富集层分开统计，类别无正例明确限制。

PT权重SHA须等于Engine源SHA，FP16、解码/预处理/shape/conf/IoU/max_det/NMS一致。保存NMS后、业务聚合前xyxy/conf/class；四模型400个图片-模型配对。人数同100张额外True/False两种NMS，共每后端500次正式单模型调用，额外接口调用分开计数。

使用compare.py同类别IoU>=0.5降序贪心一对一匹配；这是匹配规则而非精度合格线。输出每模型/类框数、匹配/缺失/新增、IoU均值/中位/P5/最小、置信度绝对差均值/P95/最大、坐标最大绝对差、计数差异图片数及最大差。未匹配/无框不丢弃。对未匹配/计数差异全量出图；仅浮点差异每模型至少最大10张（不足全出），全量逐框记录保留。

对比完成要求样本/输出完整、零运行失败、数值合法、差异分类和备份齐备。用户接受差异决定采用，不能据此自动勾选精度验收；此复核不阻止无破坏的后续功能测量，但未复核时不得宣称采用。旧TRT→新路径相同Engine业务响应仍按原规范严格一致。

## Risks / Trade-offs

- [Engine环境绑定] → 复用前核对完整环境/实加载；不兼容时独立重建，不在线降级。
- [旧Docker CUDA11.8未配套] → 明确留后续部署处理，本轮既不改镜像也不称容器可用。
- [静态shape影响输入语义] → 补几何/ROI/ImageSize对照，不以1920×1080数据外推任意输入。
- [共享predictor参数串扰或加锁影响性能] → 混合接口验证与独立旧/新TRT有限配对，记录实际资源代价。
- [FP16阈值边缘差异/100张覆盖有限] → 保留未匹配/计数差异与私有图、正例覆盖，用户复核，无事后容差。
- [并行旧实验和资源竞争] → 实施前实时进程/事件核查，等cleanup和GPU空闲才同步；不按旧PID发信号。
- [注册或测试干扰其他系统] → 独立测试端口并关闭外部注册，使用受控loopback输入，不修改线上启动方式。

## Migration Plan

1. 只读核对旧任务真实状态和全部资产/备份；冻结旧版本恢复单元（commit、环境、配置、源权重），所有GPU验证串行。
2. 完成产物工具、TRT-only加载及CPU反例测试，再检查四Engine实际FP16运行；新旧代码路径使用独立checkout/工作区或逐轮受控切换，禁止污染冻结旧参考。
3. 执行100张对照并保存差异，三接口全量5901（2162/2162/1577）与相同Engine旧TRT响应比较。保留旧入口开关默认行为。
4. 按源02执行输入/几何、同接口并发（TRT人数I8/C16/b2、学生I2/C8/b4、教师I8/C16/b2）、混合接口同worker各64图交替并总C3重复3轮；保护与双worker回归。
5. 各接口I1/C1/b1、seed20261118，warm30秒/正式300秒/HTTP60秒，人数/学生按旧→新、新→旧、旧→新三对，教师一对（用户2026-11-20缩减重复）；trace off，无重试。各接口新路径闭环30分钟零失败；报告窗口、资源、延迟及内存时间序列，不用缺乏定义的“明显增长”自动判通过。
6. 在vbas-trt环境独立端口验证不同cwd启动/重启、Health/WorkerStatus/Drain；旧版本恢复后各接口快速64图验证。无线上切换，无容器操作。
7. 新run_id保存报告/原始证据，整包前后源指纹相同、本机整包/每文件核验；更新源05/07，清理仅本任务进程。GPU仅物理1 UUID GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49；每轮主机预算8+I×1.5GiB，不放宽队列/b/超时。

回退为恢复旧commit+旧环境+旧配置+旧models权重的完整单元，新服务不承担PT兼容开关。代码迁移完成、服务器验证完成、用户采用、生产部署四种状态分别记录；此change只包含前两者及采用所需报告。

## Open Questions

无阻塞本change文档生成的问题。目录/不部署/100张要求已经确认。教师ImageSize已由用户确认为仅640，其它值加载前报错，原图分辨率可变。生产SLO、其他GPU适配和彻底去除torch均不在本轮范围。模型对照容差尚无业务定义，因此维持“完整报告后用户复核”，不擅设精度合格率。现有GPU工作是否结束、实际资产SHA/运行环境、ImageSize语义兼容性属于实施前预检和验证事项，不能由本次只写change推定通过。

## 用户确认的尺寸约束（2026-11-19）

Teacher_Behavior_Thresd.ImageSize仅支持640（数值等价的配置解析为640），非640/无效值在CUDA初始化和解密前报错。原图仍支持不同分辨率。默认640执行几何/ROI兼容检查；其他值验证明确启动拒绝，替代原先需讨论额外尺寸Engine的开放问题，不扩大profile或C++范围。

用户范围更新：2026-11-20用户明确不需要很多组重复对比：保留已完成的人数/学生各三对、教师一对（14轮），取消其余教师重复配对；缩减时正在执行的teacher-r2-new自然收尾，单列非配对观察，不进入逐对比值。三接口各30分钟稳定性保留。原21轮计划和全部记录原样留存，取消不伪记为完成。
