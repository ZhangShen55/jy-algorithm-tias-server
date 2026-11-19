## ADDED Requirements

### Requirement: 正式模型推理仅使用TensorRT FP16
新服务 MUST 默认并仅接受TensorRT FP16模型执行，保留Ultralytics所需torch依赖；PT对照或恢复 MUST 在独立工具/旧版本进行。

#### Scenario: 默认启动
- **WHEN** 正确配置CUDA并提供全件Engine
- **THEN** 四模型均使用实际TensorRT后端及FP16运行，不读取.pt作为在线模型

#### Scenario: 不支持的后端配置
- **WHEN** 配置pytorch、cpu、half=False或缺少TensorRT/CUDA
- **THEN** 明确启动失败且不静默改配置、落CPU或读取PT权重

#### Scenario: 可见设备映射
- **WHEN** 外层已绑定授权GPU UUID
- **THEN** 在GPU运行库初始化前保留正确可见性映射，仅使用对应逻辑cuda:0，不因GPU_ID二次重写选错卡

### Requirement: 完整模型就绪门槛
运行时 MUST 校验实际shape/类别/I/O/版本及四模型warmup，全部成功前不得注册或报告可服务。

#### Scenario: 任一模型失败
- **WHEN** 反序列化、实际FP16/shape检查或warmup失败
- **THEN** 记录具体模型及原因，终止新实例并清理私有临时文件，不半就绪接请求

#### Scenario: 全部warmup成功
- **WHEN** 四模型均通过检查
- **THEN** 才允许现有健康/服务生命周期进入就绪，不新增公共响应字段

### Requirement: 保持HTTP与业务推理语义
迁移 MUST 保持路由默认开关、请求响应schema、错误、ROI/坐标/类别/阈值和准入语义，人数NMS=True、学生人数NMS=False。

#### Scenario: 混合接口共享模型
- **WHEN** 同worker交替及并发调用旧人数与学生接口
- **THEN** 预测全过程的参数相互隔离，结果与各自独立TRT参考一致，不能继承另一接口的NMS

#### Scenario: 不同尺寸与ROI
- **WHEN** 处理横竖图、非原分辨率、多/空ROI或教师ImageSize配置覆盖
- **THEN** 保持既有语义并留存对照，发现不兼容则阻塞并提出方案，不默默忽略参数或改API错误行为

#### Scenario: 多图请求
- **WHEN** 一个HTTP请求含多张图且Engine为batch1
- **THEN** 保留既有逐图业务与批次准入，不能将Engine batch1误作仅支持单张请求

### Requirement: Engine保护具备完整性和进程隔离
保护工具 MUST 全件预检且缺件非零退出；加载器 MUST 使用每worker独立0700临时目录，保持现有加密格式和密钥引导。

#### Scenario: 双worker解密
- **WHEN** 两个测试worker同时加载同名Engine
- **THEN** 临时路径独立，不覆盖或串删，完成后继续可推理

#### Scenario: 错误密钥或篡改
- **WHEN** 缺密文、错误密钥、篡改或加载失败
- **THEN** 明确失败并清理当前进程明文，不泄漏密钥、不删除其他worker或源文件

#### Scenario: 保护关闭
- **WHEN** 关闭ModelProtection并正常启动
- **THEN** 直接读取项目明文Engine，不退回.pt，不要求生产密钥挂载

### Requirement: 教师配置仅支持明确的固定推理尺寸
运行时 MUST 按用户确认仅支持Teacher_Behavior_Thresd.ImageSize=640，非640或无效值在CUDA初始化和模型解密前明确启动失败；不得静默覆盖。该约束不限制原图分辨率。

#### Scenario: 不支持的教师推理尺寸
- **WHEN** 配置ImageSize为1280、320、非整数640.5、空值或无效字符串
- **THEN** 明确报告ImageSize必须为640，不初始化CUDA或解密/加载模型，不退回其他后端

#### Scenario: 支持不同原图分辨率
- **WHEN** ImageSize配置为640而输入横图、竖图或其他分辨率
- **THEN** 仍按固定384×640Engine预处理并正确还原坐标，保持HTTP业务语义，通过几何对照证明兼容性
