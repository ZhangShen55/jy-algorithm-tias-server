## Context

ai_quality 当前从 Kafka 消费课堂视觉分析任务，`VisualTaskMessage.from_payload` 会从 `teacher_video_path`、`student_video_path`、`slides_video_path` 等字段中取值，并通过 `_require_http_url` 强制校验为完整 HTTP/HTTPS URL。`VisualAnalysisWorker.process_task` 随后调用 `download_video` 将学生端和教师端视频下载到 `TempRoot/task_id` 临时目录，再抽帧、调用 TIAS、落库，最后删除整个任务临时目录。

新的输入口径是：Kafka JSON 中的视频 path 字段可能已经是本地下载好的视频文件路径。ai_quality 作为消费方需要判断 path 是 URL 还是本地文件，并在两种模式下都产出可抽帧的本地 `Path`。

当前 slides 视频字段已解析但未参与主流程抽帧，本次保持该行为不变，只调整字段校验口径，避免本地 slides path 导致消息解析失败。

## Goals / Non-Goals

**Goals:**

- 支持 `teacher_video_path`、`student_video_path`、`slides_video_path` 接收 HTTP/HTTPS URL 或本地文件路径。
- URL 输入保持现有行为：下载到任务临时目录，处理结束后删除临时文件。
- 本地文件路径输入直接读取源文件，处理结束后不删除源文件。
- 输入类型判断、校验和生命周期管理集中封装，避免 worker 业务流程里散落 `startswith("http")` 判断。
- 错误信息能明确指出是 URL 下载失败、本地文件不存在、本地路径不可读，还是视频无法打开。

**Non-Goals:**

- 不改变 Kafka topic、消费组、offset 提交策略和重试策略。
- 不改变 TIAS 推理接口、NPU/GPU 设备选择和批次调度策略。
- 不实现 slides 视频抽帧或课件指标分析。
- 不新增数据库字段。
- 不在本阶段实现远程路径白名单、路径沙箱或跨机器文件同步。

## Decisions

### 1. 将字段语义从 `*_url` 扩展为视频资源引用

继续兼容现有字段名 `teacher_video_path`、`teacher_video_url`、`teacherVideoPath`、`teacherVideoUrl` 等，但 `VisualTaskMessage` 内部字段建议调整为 `teacher_video_path`、`student_video_path`、`slides_video_path` 或等价的 `*_source` 命名。

原因：Kafka 原始字段本来就是 `path` 口径，继续在内部命名为 `url` 会误导后续维护者，也容易再次写出“必须 HTTP URL”的校验。

备选方案是保留 `*_url` 字段名但放宽校验。这个方案改动更小，但长期可读性差，不推荐。

### 2. 增加统一的视频资源准备函数

在 `ai_quality.infrastructure.media.video` 中增加类似 `prepare_video_source(source, destination, progress_callback)` 的能力，返回一个资源对象：

- `path`: 最终可传给 OpenCV 抽帧的本地路径。
- `source`: Kafka 原始输入。
- `source_type`: `url` 或 `local_file`。
- `owned_by_task`: 是否由本次任务临时目录持有。

URL 输入调用现有下载逻辑，`owned_by_task=true`。本地文件输入做路径校验后直接返回源路径，`owned_by_task=false`。

原因：worker 只关心拿到可读视频路径，不应该关心来源类型。临时文件清理由任务目录 `shutil.rmtree(task_dir)` 完成，外部源文件因为不在任务目录下，不会被删除。

备选方案是在 worker 中分别写 `if url then download else Path(...)`。这个方案短期简单，但会让校验、日志和测试分散，不利于后续扩展。

### 3. URL 与本地路径判断规则

判断规则建议如下：

- 使用 `urllib.parse.urlparse` 解析。
- `scheme` 为 `http` 或 `https` 且存在 `netloc` 时，判定为 URL。
- `scheme` 为空时，判定为本地文件路径。
- 其他 scheme，例如 `file://`、`ftp://`、`s3://`，本阶段判定为不支持并给出明确错误。

本地路径校验：

- 输入必须是非空字符串。
- 路径存在。
- 路径是普通文件，不是目录。
- 当前进程可读。
- 可选地保留后续扩展配置，例如 `AllowedLocalVideoRoots`，但本阶段不强制引入。

原因：该判断兼容 Linux/macOS 绝对路径、相对路径和 HTTP URL。`file://` 看似也是本地路径，但它需要 URL 解码、host 处理和权限口径，先不支持可以减少歧义。

### 4. 相对本地路径的解释口径

相对路径建议按 ai_quality 进程当前工作目录解析，或者按配置项 `LocalVideoBaseRoot` 解析。为了减少隐性风险，本阶段建议增加配置项：

```toml
# 本地视频相对路径基准目录。为空时按 ai_quality 进程当前工作目录解析。
LocalVideoBaseRoot = ""
```

当 Kafka path 是相对路径且 `LocalVideoBaseRoot` 非空时，使用 `LocalVideoBaseRoot/path`。当配置为空时，使用当前工作目录解析。

原因：Docker 部署时工作目录和宿主机路径容易不一致，显式基准目录能减少排查成本。

### 5. 日志和错误处理

任务处理日志应记录：

- `task_id`
- `teacher_video_source_type`
- `student_video_source_type`
- 本地视频最终路径或 URL 主体信息

错误继续抛出 `VideoProcessingError` 或 `InvalidTaskMessage`，由现有 worker 逻辑标记 workflow 失败。Kafka 侧是否 commit 仍沿用现有处理策略，不在本次变更中调整。

## Risks / Trade-offs

- [风险] Kafka 本地路径只对 ai_quality worker 所在机器有效，多实例部署时可能有的实例无法访问该路径。  
  [缓解] 文档明确要求本地路径必须对消费该任务的 ai_quality worker 可见；集群部署应使用共享挂载路径，或继续使用 URL。

- [风险] 相对路径在 Docker 内外解析不一致。  
  [缓解] 增加 `LocalVideoBaseRoot` 配置和文档示例，推荐生产环境使用绝对路径或容器内共享挂载路径。

- [风险] 本地文件由外部进程写入时，ai_quality 可能读到未写完的视频。  
  [缓解] 本阶段只校验文件存在和可读，要求上游在文件完全可用后再投 Kafka；后续如需要，可增加文件稳定性检查。

- [风险] 本地路径放宽后带来路径访问安全问题。  
  [缓解] 当前部署在可信内网任务链路内，先不做白名单；如果后续跨租户或外部输入，应增加 `AllowedLocalVideoRoots` 限制。

## Migration Plan

1. 增加视频资源引用解析和准备逻辑。
2. 保持 HTTP/HTTPS URL 任务完全兼容，原 Kafka 示例无需修改。
3. 增加本地路径 Kafka 示例和单元测试。
4. 部署前确认本地路径在 ai_quality worker 容器内可见，Docker 场景需要挂载宿主机视频目录。
5. 如新逻辑异常，可回滚到上一版本；URL 任务无数据迁移要求。

## Open Questions

- 本地相对路径是否需要强制配置 `LocalVideoBaseRoot`，还是允许按当前工作目录解析。
- 是否需要现在就增加 `AllowedLocalVideoRoots` 白名单，限制本地视频只能来自指定挂载目录。
- `slides_video_path` 后续是否会进入抽帧分析流程；当前只放宽校验，不改变使用方式。
