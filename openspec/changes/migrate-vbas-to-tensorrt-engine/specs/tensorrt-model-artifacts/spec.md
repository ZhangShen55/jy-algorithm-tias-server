## ADDED Requirements

### Requirement: 项目模型目录完整且独立于cwd
系统 MUST 将四Engine和manifest作为一套资产，默认从项目根model/解析，运行不依赖models/*.pt。

#### Scenario: 从其他工作目录启动
- **WHEN** 以不同cwd启动项目且未指定EngineRoot
- **THEN** 仍定位项目model/person_count.engine、face_count.engine、student.engine、teacher_behavior.engine和manifest.json

#### Scenario: 缺少或混用产物
- **WHEN** 任一必需文件缺失、清单缺模型或文件SHA与清单不符
- **THEN** 校验失败并指出对应模型，不加载部分资产提供服务

### Requirement: 构建与复用可追溯
工具 MUST 核验已有受审Engine后复用，需重建时离线导出到不存在的新目录，不覆盖历史源权重/ONNX/Engine或启动时导出。

#### Scenario: 复用原Engine
- **WHEN** 来源清单和当前环境检查通过
- **THEN** 复制至新资产集并校验新旧文件SHA一致，保留原件

#### Scenario: 已有输出或构建失败
- **WHEN** 导出目标已存在或任一模型构建/加载检查失败
- **THEN** 非零退出，不覆盖原目录、不生成表示四模型全件可用的完成清单

#### Scenario: 离线导出参数
- **WHEN** 在指定设备执行离线导出
- **THEN** 显式使用source-root/output/device参数，保留源PT/ONNX/Engine及构建代码哈希和构建日志

### Requirement: 清单包含实际模型和环境元数据
manifest MUST 记录四模型类别顺序、NCHW/I/O、精度选项、各资产SHA和构建平台/库/GPU信息；校验工具 MUST 区分元数据封装文件与裸plan。

#### Scenario: 验证FP16资产
- **WHEN** 检查本轮四个Engine
- **THEN** 前三模型shape为[1,3,1088,1920]，教师为[1,3,384,640]，batch1、I/O HALF、FP16构建且TF32关闭；清单与实际加载一致

#### Scenario: 验证文件来源
- **WHEN** 读取含Ultralytics元数据头的Engine
- **THEN** 以完整文件计算SHA，正确解析封装再检查实际plan，保留source_pt/ONNX/engine SHA、类别、版本和构建设备信息

#### Scenario: 跨环境检查
- **WHEN** 运行GPU/平台/库组合不在受审兼容目标内
- **THEN** 明确阻塞加载或复用并提示重建/验证，不声称Engine通用或自动换后端

### Requirement: 模型资产不进入版本库
项目 MUST 只跟踪说明、工具和脱敏文档，模型/密文/中间产物/密钥及私有数据不得入Git。

#### Scenario: 新增model资产
- **WHEN** 将Engine及实际私有manifest放入项目model/
- **THEN** 忽略规则阻止二进制/私有清单被常规添加，可信资产与逐文件清单保存在私有存储，不覆盖既有备份
