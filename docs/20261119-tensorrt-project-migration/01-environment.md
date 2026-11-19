# 环境与约束

## 迁移前调查基线

本机仓库 /Users/zhangshen/Documents/workspace/vbas，分支 perf；只读调查提交 c547abb2d57fa2a508cf7a0a4361ed32ea56f0aa。当时core/settings.py已有双后端入口，默认 pytorch、InferenceHalf=False，EngineRoot 为空；路径仍是 models/*.pt，TRT 分支从文件 stem 推导 EngineRoot/<name>/<name>.engine。

已有引擎来自服务器 /home/zhangs/workspace/vbas-benchmarks/ 的 engines-fp16-io-20261118 资产。不能仅凭目录名发布：实施阶段先核对四份 manifest、源权重、输入输出、Engine SHA 和完整包备份，再决定复用还是重建。原件只读，重建使用新 run_id。

## 受测目标

ssh zhangs12，仓库 /home/zhangs/workspace/vbas/；唯一 GPU 为物理 GPU1 RTX3090，UUID GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49。保留 jy-tias、用户目录 vbas 和 vbas-trt 环境，不改驱动或其他服务。进程启动前配置 UUID，应用内部仅访问逻辑 cuda:0；必须防止 settings 重写 CUDA_VISIBLE_DEVICES 导致选错卡，GPU 选择代码审查列为实施门槛。

已测软件为 TensorRT 10.13.3.9、Ultralytics 8.3.156、PyTorch 2.12.1+cu130、torchvision 0.27.1，驱动 580.126.09；完整依赖以原私有环境清单为准。这些是已有测试环境事实，不表示当前 Docker 已兼容。

现有 docker/Dockerfile 和 Dockerfile.runtime 使用 PyTorch2.6/CUDA11.8，requirements.txt 未声明 TensorRT，不能将已有 engine 直接搬入后认定容器可用。本轮不构建镜像。直接使用并核验已有 vbas-trt 环境，保存完整依赖清单及已知声明冲突；不在旧环境试装。Docker版本差异仅记录为后续部署风险，不作为本轮服务器验证的阻塞项。

## 兼容性限制

本方案不启用新的 hardware/version compatibility 构建模式；按构建目标 GPU、平台和 TensorRT 版本校验，不将 engine 当跨平台通用权重。更换目标环境需重新构建和验证，不能在线启动时自动重建。依据：[NVIDIA TensorRT 10.x 支持矩阵](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/support-matrix.html)。

Mac 仅用于编辑、CPU 回归和可用的镜像静态检查；真实反序列化、FP16、显存和性能需在指定 GPU 验证。main_910b_npu、生产上线、合并和 C++ 均不在本轮范围。AGENTS.md 为用户未跟踪文件，不提交、覆盖。原始照片、权重、引擎、密钥、私有配置与日志不推 Git。

## 实施核验状态

旧参考冻结e90b31f，新运行实现/专项验证冻结f5a7f3a。两环境完整清单、原件SHA及26源文件参考包已本机核验，见[预检报告](reports/20261119-preflight/report.md)。当前model/使用同一套受审FP16 Engine，默认TRT-only/half=true，设备在GPU库导入前绑定，原models权重和环境保留。新离线构建工具的独立测试产物不自动替换已完成100张对照的发布。后续文档提交不在测量期间同步到服务器。
