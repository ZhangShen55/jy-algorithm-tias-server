## 1. 消息模型与配置

- [ ] 1.1 调整 `VisualTaskMessage` 视频字段命名和校验口径，支持 HTTP/HTTPS URL 或本地文件路径。
- [ ] 1.2 保持现有 Kafka 字段别名兼容，包括 `teacher_video_path`、`teacher_video_url`、`teacherVideoPath`、`teacherVideoUrl` 等。
- [ ] 1.3 增加 `LocalVideoBaseRoot` 配置项，用于相对本地视频路径解析，并更新 `config.toml.example`。

## 2. 视频资源准备

- [ ] 2.1 在媒体模块中实现视频来源类型判断，区分 `url`、`local_file` 和不支持的 scheme。
- [ ] 2.2 实现统一的视频资源准备函数，URL 输入下载到任务临时目录，本地文件输入直接返回源路径。
- [ ] 2.3 增加本地文件存在性、普通文件、可读性校验，并输出明确错误信息。
- [ ] 2.4 保证任务清理只删除 ai_quality 自己的临时目录，不删除外部本地源视频。

## 3. Worker 集成与日志

- [ ] 3.1 将 `VisualAnalysisWorker.process_task` 中固定 `download_video` 的逻辑替换为统一视频资源准备逻辑。
- [ ] 3.2 记录学生视频和教师视频的来源类型、任务 ID、准备结果和失败原因。
- [ ] 3.3 保持 `slides_video_path` 可选，放宽校验但不新增 slides 抽帧流程。

## 4. 测试与文档

- [ ] 4.1 增加消息解析单元测试，覆盖 URL、本地绝对路径、本地相对路径和不支持 scheme。
- [ ] 4.2 增加视频资源准备单元测试，覆盖 URL 下载、本地文件复用、本地文件不存在、目录路径和不可读文件。
- [ ] 4.3 增加 worker 层测试，验证本地源视频处理后不会被删除。
- [ ] 4.4 更新 ai_quality 运行文档，补充 Kafka 本地视频路径消息示例和 Docker 挂载注意事项。
- [ ] 4.5 执行相关自动化测试，并使用 `tests/fixtures/ai_qualitu_lesson_local_path.json` 做本地视频路径 Kafka 样例冒烟验证。
