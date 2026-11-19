# TensorRT 模型目录

正式服务使用本目录的person_count.engine、face_count.engine、student.engine、teacher_behavior.engine和manifest.json。文件来自受审的私有发布包，不提交Git，不在服务启动时构建或下载。

manifest schema_version=1，release_id标识整套资产，environment记录构建环境，models按四模型名称包含file、engine_sha256、source_sha256、onnx_sha256、shape、names、precision、tf32_enabled和io_tensors。具体校验见core/engine_artifacts.py。静态校验只证明结构/完整性，真实TensorRT、FP16与环境兼容需指定GPU加载验证。

本轮只进行项目迁移及服务器验证，不涉及Docker或线上部署。源PT权重、历史Engine和回退环境保留在私有构建/备份区。
