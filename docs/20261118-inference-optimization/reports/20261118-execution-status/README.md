# 连续执行检查点

状态：执行中，未结项。用户已授权连续推进，不需要逐阶段询问启动。

## 当前检查点（北京时间2026-11-18 23:47）

人数原计划22轮已采集。闭环30分钟23766次零失败；开放80%/100%均零失败，110%有168个发生器保护槽未发，实际2418 HTTP/业务全成功。不能把C32保护当服务器峰值，首次保护17.81985秒。发生器CPU8.54%均值，发送滞后最大3.61ms；需原流程结束后补110%同配置C256，协议已写入02/04/05。旧人数路由不走BatchAdmissionController，报告已修正b配置作用口径。原始粗分类保留不改，离线细分归因。

PyTorch学生原定19轮采集完成：闭环稳定性15774次零失败；定速80% 1249次零失败，100%/110%各5/154次服务429，已与日志running_batches=2及max=2逐项数量核对。100%首次拒绝时两请求约2.87/2.46秒，GPU显存增长同窗，底层慢原因未由日志证明；失败点不推荐，不能由闭环吞吐认定持续定速零失败。确认/稳定性100文件、定速50文件均已取回本机校验，见 ../20261118-torch-student-capacity/report.md。当前教师搜索已自动开始，随后PyTorch成功自动TensorRT；原调度4182465正常，不插入新GPU任务。新阶段证据见 ../20261118-torch-sync-capacity/report.md；22轮中110%不是零失败推荐点，人数最终结论仍待补测/同配置对照。

学生独立False基线、组合全量各5901条、96张私有差异图及校验备份已完成。仍需学生/教师容量、TensorRT容量、同配置对照、并发一致性和兼容回退。下文历史暂停记录不代表当前状态。

## 当前长任务

服务器 `ssh zhangs12`，仓库 `/home/zhangs/workspace/vbas/`，分支 perf。当前已启动串行命令：PyTorch capacity.py 成功完成后自动执行 TensorRT capacity.py。不要重复启动 GPU 任务。

- PyTorch：`/home/zhangs/workspace/vbas-benchmarks/torch-capacity-20261118/`。
- TensorRT：`/home/zhangs/workspace/vbas-benchmarks/trt-capacity-20261118/`。
- 日志：`/home/zhangs/workspace/vbas-benchmarks/environment-20261118/torch-capacity.log`、`trt-capacity.log`。
- 启动时服务器代码：0ca3a43。实验进行中避免改动或拉取会改变测量行为的代码；修复工具问题时保留无效轮证据并明确版本。
- 当前对话自动续跑心跳 ID：`vbas`，每 10 分钟。正常无变化保持安静，异常需检查恢复，全部已授权工作完成后暂停心跳。
- 续跑需要本机和桌面 app 保持运行。服务器进程状态应通过 SSH、journal、events 和 case-result 核对，不只依赖本机 exec session。

首个正式点 `/AE/SyncTasks2`，I=1/C=1/准入1，180秒、全量请求池2162张轮换：1723次成功，0失败，窗口9.57图/s，P50 104.68ms、P95 107.34ms、均值104.46ms。仅一个搜索点，不代表峰值。检查点记录时已进入 I=1/C=2。

## 已完成的证据

- 用户目录 vbas、vbas-trt 环境；原 jy-tias 保留。服务器仓库 Git 身份已配置。
- PyTorch 与 TensorRT 各5901次全量采集，四模型 FP16 推理运行验证。
- 四个显式 FP16 I/O 引擎：`/home/zhangs/workspace/vbas-benchmarks/engines-fp16-io-20261118/`。旧的 `engines-fp16-20261118/teacher_behavior/` 为转换技术试验，I/O 是 FP32，不用于正式 FP16 对照。
- PyTorch 基线已额外备份到本机，详见基线报告。
- 一致性第一版：126924框匹配、45参考独有、45候选新增，平均IoU 0.99745；这不是实际准确率。
- 完整业务计数和业务框几何复核：`torch-trt-comparison-r2-20261118/`，需汇总与人工差异案例。
- 加密引擎正常加载/推理通过；篡改密文被明确拒绝；两种路径均无明文文件遗留。证据：`protected-engine-check-20261118/summary.json`。
- 独立分段诊断每模型200样本：`torch-stages-20261118/`、`trt-stages-20261118/`。自定义拆分预处理已与原 predictor.preprocess 验证张量相等。
- 全量性能请求池：`full-performance-payloads-20261118/`，输入文件逐图验证基线SHA，正式负载按固定种子轮换。预热最多16张，正式性能不是只测16张。

## 后续继续做

1. 持续检查正式容量流程，失败必须归因；不要把429准入拒绝、OOM、客户端限制等混为纯GPU算力峰值。检查负载发生器CPU和GPU资源，必要时增加负载发生器并保留协议变更记录。
2. 完成三个接口的实例/并发搜索、三次交错复测、定速实验和30分钟稳定性。推荐配置在测试窗口零失败；P95无生产门槛，只报告观察结果。
3. 补齐同配置后端正式对照，不能只比较各自最佳点；必要时在两后端补跑相同配置与种子。
4. 检查高并发业务结果一致性、OpenAPI不变、PyTorch回退，补齐逐请求分段或响应编码等尚未完成的协议项。
5. 用 visualize.py 生成差异图并检查显示；图片只放私有产物/本机备份，不将课堂原图推到Git。汇总计数、框/置信度、业务几何差异与异常案例。
6. 生成正式报告/图表、结果校验及备份，按真实证据更新05任务清单和07完成出口，提交推送perf，完成后暂停心跳。

用户确认：没有人工标注，先做相对PyTorch一致性；TensorRT先出完整差异报告，由用户复核后决定采用；不自动上线/合并，不开展C++改造，不动main_910b_npu或其他服务。

## TensorRT 实验依赖说明

实际验证版本：PyTorch2.12.1+cu130、TensorRT10.13.3.9、ONNX1.17.0、驱动580.126.09。旧版Ultralytics8.3.156导出使用legacy ONNX路径，TensorRT输入输出显式HALF，TF32关闭，层信息和构建缓存哈希已保留。

旧TensorRT依赖声明要求 nvidia-cuda-runtime-cu13，该包当前发布项为弃用占位包，常规解析安装失败。实验使用已下载的官方TensorRT wheel按 --no-deps 安装，并使用原PyTorch已安装的统一包 nvidia-cuda-runtime13.0.96；实际导入、构建及5901次推理已验证。pip check仍会报告该声明缺项，不能宣称环境依赖检查全通过。原环境另有fireredvad缺kaldiio/soundfile的既有无关项，未擅自修复。生产采用前需处理/复核依赖声明及交付方式；本轮只验证实验栈。

## 心跳核查（北京时间 2026-11-18 19:19）

正式 PyTorch 人数接口搜索正常推进，已完成 I1/C1、I1/C2、I2/C2、I2/C4，均零失败；当前正在 I2/C8。I2/C4 的180秒窗口为11.08图/s，P50 364.69ms、P95 391.97ms、平均360.52ms，尚非峰值结论。

四个已完成点分别有180条采样窗口资源记录；负载发生器平均CPU约4.77%～5.08%（单核100%口径），未出现持续客户端CPU饱和证据。I2/C4 GPU平均利用率82.34%，GPU显存采样峰值3578MiB。资源监控、推理/预热显存分离文件及清理流程正常。

后续仍需在更高吞吐点重新检查客户端CPU，不将本轮观察外推为所有配置均无客户端瓶颈。

## 学生口径修正检查点

用户已确认学生人数保持独立默认 `agnostic_nms=False`，详见 ../20261118-student-nms-correction/report.md。父调度4182465已 SIGSTOP，当前 sync-confirm-sync-explore-i8-c8-b1-r1 子轮继续自然结束。必须先核对无 instances/load 且 GPU 空闲，才能拉取修正并顺序重采学生两后端；然后 SIGCONT 原父调度。旧学生结果不可作最终独立基线，原始文件保留；不要另启容量任务。

修正协调器已于 GPU 空闲后启动（PID30437），状态 `student-nms-correction-20261118/state.json`；脚本在 `environment-20261118/student-nms-correction.py`，成功自动恢复4182465，失败保持暂停。服务器代码 b15dd39。首批学生输出三模型FP16且人数False已核验。完成后取回 `student-nms-correction-20261118/corrected-baselines.tar.gz` 并验证SHA。不要在协调器运行期间另启GPU任务。同步期间人数测量逻辑未改，需在最终报告记录0ca3a43→b15dd39版本边界。

## 离线分析工具已备妥

`scripts/benchmark/summarize_capacity.py`（0855c07）已完成合成验证及15个正式完成轮离线核对；服务器私有副本 `environment-20261118/summarize_capacity-0855c07.py`，r2归集产物与本机备份哈希见 ../20261118-capacity-analysis/report.md。该工具只读证据，无GPU/服务操作，正式服务仍b15dd39。容量结束后用新run_id补做全量归集，开放式时间线按协议区分实际在途、计划发送滞后与发生器本地丢弃。

## 公开结构核查补证

已从现有PyTorch实例只读获取OpenAPI，学生NMS修正后与先前测量版7个公开路径及完整schema相同，SHA697baa96efd0949fd6e787412ccee994154a026636b596d37602b9cb4ec53068；本机备份校验通过。证据见 ../20261118-contract-check/report.md。TensorRT及原main对照、并发响应仍待补齐，不提前标为全部通过。

人数定速补证已取回本机：torch-sync-open-checkpoint-20261118/evidence.tar.gz，SHA672b9f80c20e9ce6cbd9fa70c592da479ee83fb6eb8cb17ce3d59c268d9129d4；74文件校验通过。新版离线0e51d43已实测，110%明确标记保护截断，后续C256补测不可省略。学生原正式流程继续，勿插入GPU实验。

## 已准备的并发核查工具

本地audit.py及instances.py --audit-reference模式已实现，4项无模型回归、编译与差异检查通过，未拉取到正在测量的服务器。原串行容量完成且GPU空闲后再同步并执行两后端×三接口全量业务审计，独立目录，不混入性能成绩；见 ../20261118-concurrent-audit/report.md。完整性CPU扫描也已完成，两后端共255646框均无NaN/Inf/非法类/越界/反序/零面积，记录见 ../20261118-baseline-integrity/report.md。以上不表示真实GPU并发或准确率已通过。

## 响应编码组件已离线补测

serialization.py对两份修正版基线的三接口响应重放35406次，JSONResponse构造/render/头初始化均值约0.03～0.10ms，全部值往返校验通过；无模型/GPU，未改变正式服务。逐图证据已取回本机校验，见 ../20261118-response-serialization/report.md。该项排除Pydantic响应校验、请求解析、业务构造及网络，不能写成完整响应耗时或完成全部分段项。
