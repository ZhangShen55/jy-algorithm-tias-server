## ADDED Requirements

### Requirement: Kafka 视频字段支持 URL 或本地文件路径

ai_quality SHALL 接受 `teacher_video_path`、`student_video_path`、`slides_video_path` 及其兼容别名中的视频输入值为 HTTP/HTTPS URL 或本地文件路径字符串。

#### Scenario: 接收 HTTP URL

- **WHEN** Kafka 任务中的 `teacher_video_path` 和 `student_video_path` 是完整 HTTP/HTTPS URL
- **THEN** ai_quality SHALL 接受该消息并按 URL 下载流程准备视频

#### Scenario: 接收本地绝对路径

- **WHEN** Kafka 任务中的 `teacher_video_path` 和 `student_video_path` 是当前 ai_quality worker 可访问的本地绝对文件路径
- **THEN** ai_quality SHALL 接受该消息并直接使用本地文件抽帧

#### Scenario: 接收本地相对路径

- **WHEN** Kafka 任务中的视频 path 是本地相对路径
- **THEN** ai_quality SHALL 按配置的本地视频基准目录或进程当前工作目录解析为本地文件路径

#### Scenario: 拒绝不支持的 scheme

- **WHEN** Kafka 任务中的视频 path 使用 `ftp://`、`s3://`、`file://` 或其他非 HTTP/HTTPS scheme
- **THEN** ai_quality MUST 拒绝该消息并给出不支持的视频 path 类型错误

### Requirement: URL 视频保持下载和临时清理语义

ai_quality SHALL 保持 HTTP/HTTPS 视频输入的现有行为：抽帧前先将视频下载到任务临时目录，并在任务完成或失败后删除任务临时目录。

#### Scenario: URL 下载成功

- **WHEN** Kafka 任务中的学生和教师视频输入都是可下载的 HTTP/HTTPS URL
- **THEN** ai_quality SHALL 将它们下载到任务临时目录，并使用下载后的文件抽帧

#### Scenario: URL 下载失败

- **WHEN** 视频 URL 无法下载，或下载后的文件为空
- **THEN** ai_quality MUST 将 workflow 标记为失败，并记录下载相关失败原因

### Requirement: 本地视频不得被任务清理删除

当 Kafka 视频输入是任务临时目录外部的本地文件路径时，ai_quality SHALL 不删除、不修改源视频文件。

#### Scenario: 本地视频处理成功

- **WHEN** ai_quality 完成使用本地视频文件路径的任务处理
- **THEN** 原始本地视频文件 MUST 仍然存在

#### Scenario: 本地视频处理失败

- **WHEN** ai_quality 使用本地视频文件路径后，在抽帧或下游分析过程中失败
- **THEN** ai_quality MUST 清理自己的任务临时目录，并且 MUST NOT 删除原始本地视频文件

### Requirement: 本地视频路径必须可访问

ai_quality SHALL 校验 Kafka 中已提供的本地视频路径输入是否可访问；学生视频和教师视频必须在抽帧前通过校验，slides 视频字段如果传入本地路径，也必须通过存在性、普通文件和可读性校验。

#### Scenario: 本地文件不存在

- **WHEN** Kafka 任务中的视频 path 指向不存在的本地文件
- **THEN** ai_quality MUST 拒绝处理该任务，并将 workflow 标记为失败，失败原因应说明本地文件不存在

#### Scenario: 本地路径是目录

- **WHEN** Kafka 任务中的视频 path 指向目录
- **THEN** ai_quality MUST 拒绝处理该任务，并将 workflow 标记为失败，失败原因应说明本地路径不是有效文件

#### Scenario: 本地文件不可读

- **WHEN** Kafka 任务中的视频 path 指向 ai_quality 进程不可读的文件
- **THEN** ai_quality MUST 拒绝处理该任务，并将 workflow 标记为失败，失败原因应说明本地文件不可读

#### Scenario: slides 本地文件不存在

- **WHEN** Kafka 任务提供了 `slides_video_path`，且该 path 指向不存在的本地文件
- **THEN** ai_quality MUST 拒绝处理该任务，并将 workflow 标记为失败，失败原因应说明 slides 本地文件不存在

### Requirement: 视频来源类型必须可观测

ai_quality SHALL 记录每个已处理学生视频和教师视频的来源类型是 `url` 还是 `local_file`。

#### Scenario: 处理混合输入

- **WHEN** Kafka 任务的 `student_video_path` 使用本地文件路径，`teacher_video_path` 使用 HTTP URL
- **THEN** ai_quality SHALL 记录任务 ID 以及两个视频的来源类型

### Requirement: slides 视频字段保持可选且不触发主流程抽帧

ai_quality SHALL 继续将 `slides_video_path` 作为可选字段，并且本次变更 SHALL NOT 新增 slides 抽帧流程。

#### Scenario: slides 字段为空

- **WHEN** Kafka 任务未提供 `slides_video_path`
- **THEN** ai_quality SHALL 正常处理学生视频和教师视频

#### Scenario: slides 字段是本地路径

- **WHEN** Kafka 任务提供的 `slides_video_path` 是本地文件路径
- **THEN** ai_quality SHALL 校验该本地文件可访问，并且当前处理流程 SHALL NOT 要求执行 slides 抽帧
