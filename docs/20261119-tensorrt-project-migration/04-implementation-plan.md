# 实施与对照方案

## 推荐结构

目录已确认：项目根目录 model/，服务器绝对路径 /home/zhangs/workspace/vbas/model/。EngineRoot 默认锚定项目根、解析为绝对路径，不依赖启动 cwd；本轮不涉及容器挂载。

```text
model/                      # 每个发布包只含一套受审目标环境资产
  person_count.engine
  face_count.engine
  student.engine
  teacher_behavior.engine
  manifest.json
```

既有加密机制保留兼容：保护回归使用私有目录中的 person_count.engine.enc 等文件，密文交付形式留待后续部署阶段。源 models/*.pt、中间ONNX、层检查记录留在私有构建/回退区，不随正式推理发布包交付。外层按 release_id 存多个不可变发布目录，启动只指向一个已核验目录，整包切换避免跨版本四模型混搭。

## 代码与职责

1. 新增 core/inference_runtime.py，负责显式四模型映射、manifest验证、设备/FP16/shape校验、加载和warmup。core/settings.py保留配置和对外模型引用，移除由.pt stem推导运行Engine路径的关系，正式默认tensorrt/FP16；配置pytorch、cpu、half=False均给明确迁移错误，不悄悄改成其他后端。旧PT完整发布另存回退，不把训练权重留在新服务必需文件中。
2. 使用现有 YOLO(engine, task=detect) 路径和元数据封装格式，不能把带4字节长度/JSON头文件当裸TensorRT plan交给deserialize。Engine形状固定：person_count/face_count/student为1×3×1088×1920，teacher_behavior为1×3×384×640，batch1、HALF I/O、FP16构建、TF32关闭。继承已验证预处理/NMS/类别/业务逻辑，不引入NMS插件、动态profile、INT8或新batch优化。
3. 运行加载全部四模型成功并warmup才允许注册/健康就绪。与现有启动生命周期衔接，不改外部响应schema；失败日志说明模型、预期/实际环境和修复方式，无静默PT/CPU或启动时自动导出。trace默认off。
4. services/student_behavior_service.py、task_service.py、task_service_base64.py、teacher_behavior_service.py审查每个predict参数及共享状态。保持学生人数False/旧人数True，特别验证交替和并发是否串改Ultralytics predictor参数。若现有锁已覆盖调用全过程则复用；否则将参数更新和预测纳入每模型锁并评估吞吐影响，不直接删除旧接口或修改阈值。静态shape可能改变任意尺寸/ROI的letterbox和教师ImageSize语义，必须有专门对照结果，不能用原1920×1080数据证明全输入兼容。

## 转换与发布

已有四Engine通过清单/反序列化核对后，优先复制到新独立发布包，不覆盖原构建；无需为了路径搬迁重新转换。若依赖/目标环境不匹配，新增 scripts/export_tensorrt_models.py，由显式 source-root、output、deviceUUID执行四模型离线构建，输出目录必须不存在；方法继承 scripts/benchmark/export_engine.py。该旧脚本保留历史复现，不改写其硬编码实验参数。正式导出工具不硬编码服务器路径，不启动时下载模型，构建失败不产生可发布完成标记，四模型+清单核验后才封包。

新增 scripts/verify_tensorrt_models.py，在启动前检查清单完整性并支持真实GPU加载诊断。新Engine放model/同时更新.gitignore/.dockerignore，排除明文/密文模型和中间产物；清单模板/说明可显式跟踪，实际私有发布清单随私有包留存。

## 模型保护

scripts/protect_vbas_models.py增加显式Engine四文件清单，先检查全件存在再加密，缺件非零退出；不沿用现有“缺件continue、部分输出也成功”的行为。core/model_protection.py为每worker创建权限0700的唯一临时子目录，防止共用/dev/shm/vbas-models/<basename>相互覆盖/删除；成功加载及异常退出均清理各自明文，源Engine与持久密钥不删除。该加固只服务本轮Engine交付，不改算法或加密格式。

## 服务器运行与项目文件

以现有 vbas-trt 环境为运行基础，核对实际软件版本及CUDA设备，保存可复现依赖清单和已知冲突，不在基线环境升级。保留torch和torchvision供Ultralytics，ONNX/export工具只在离线转换时使用。

更新config.toml.example、README、RUNNING以及model/说明，明确默认Engine路径、FP16、设备、独立测试端口、关闭注册方法和启动前检查。当前config.toml可能含私有信息，不覆盖或提交完整配置。原benchmark代码和旧结果保留，运行验证全部另建run_id。

本轮不修改docker/Dockerfile、Dockerfile.runtime、compose、线上配置或部署脚本，不构建/发布镜像。现有镜像基于CUDA11.8且未配套本Engine环境，列为后续部署前必须解决的事项；服务端验证通过不能称镜像或部署就绪。

## 顺序与回退

先确认方案/目录，再核验活动任务和冻结输入；离线产物及加载→CPU回归→四模型GPU→各模型100张PT/TRT一致性报告与差异复核→三接口全量/几何/混合并发→有限性能与稳定性→项目直接启动/保护回归/旧版本恢复→交接。全过程不与原42轮重叠、不改其他服务。

人工回退按旧commit+旧依赖环境/镜像+旧models权重+旧配置作为一个发布单元，停止新服务自有进程，切换回退单元，再做三接口各64图冒烟。回退不要求新TRT-only服务重新支持PT。实施前记录实际旧环境清单和配置备份路径；不删除旧环境，不自动上线或合并。旧优化任务剩余项继续列未完成，迁移不替代其结项。

## 2026-11-19尺寸范围确认

用户选择本轮教师ImageSize固定640，其他值启动时明确报错；原图分辨率可变化，内部仍letterbox到384×640。运行选项检查放在CUDA初始化/模型解密之前，并由加载工具入口复查。默认640业务对照和不同原图几何检查继续；不实现动态shape或额外尺寸Engine。

## 2026-11-20范围更新

2026-11-20用户明确不需要很多组重复对比：保留已完成的人数/学生各三对、教师一对（14轮），取消其余教师重复配对；缩减时正在执行的teacher-r2-new自然收尾，单列非配对观察，不进入逐对比值。三接口各30分钟稳定性保留。原21轮计划和全部记录原样留存，取消不伪记为完成。
