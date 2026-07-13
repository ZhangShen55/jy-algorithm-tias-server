## Why

当前 ai_quality 消费 Kafka 任务时，把 `teacher_video_path`、`student_video_path`、`slides_video_path` 都按完整 HTTP URL 校验，并在处理前下载到临时目录。后续上游可能直接投递已下载好的本地视频路径，如果仍强制 URL，会导致任务在消息解析阶段失败，无法复用本地视频文件。

## What Changes

- Kafka 任务中的三个视频 path 字段支持两类输入：
  - HTTP/HTTPS URL：保持现有逻辑，下载到任务临时目录，处理完成后删除临时文件。
  - 本地文件路径：不下载，直接读取该路径对应的视频文件，处理完成后不删除源文件。
- ai_quality 增加视频资源归一化逻辑，统一判断输入是 URL 还是本地路径，并返回可用于抽帧的本地 `Path`。
- 本地路径需要做存在性、文件类型、可读性校验，失败时按任务异常处理，并保留当前 workflow 失败标记逻辑。
- `teacher_video_path`、`student_video_path` 为必填；`slides_video_path` 保持可选，但如果传入也应接受 URL 或本地文件路径。
- 日志补充视频输入来源类型，便于区分任务使用的是下载视频还是本地视频。

## Capabilities

### New Capabilities

- `ai-quality-video-inputs`: 约束 ai_quality 消费 Kafka 后对视频 path 字段的 URL/本地路径识别、校验、临时文件生命周期和错误处理。

### Modified Capabilities

- 无。

## Impact

- 影响 `ai_quality.infrastructure.kafka.message`：视频字段校验从“必须是完整 HTTP URL”调整为“必须是 URL 或本地文件路径字符串”。
- 影响 `ai_quality.infrastructure.media.video`：增加视频输入准备能力，区分下载文件和外部本地文件。
- 影响 `ai_quality.application.worker`：处理任务时改为调用统一的视频资源准备逻辑，并只清理任务临时目录，不删除外部本地源文件。
- 影响 ai_quality 运行文档、配置示例和测试脚本：补充 Kafka 本地路径示例和验证方式。
- 不影响 TIAS 推理接口、NPU 适配、数据库表结构和 Kafka topic。
