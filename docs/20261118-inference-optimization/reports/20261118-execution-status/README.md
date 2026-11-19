# 连续执行检查点

状态：执行中，未结项。用户已授权连续推进，不需要逐阶段询问启动。

## 最新状态：C256补证结束，同配置配对已启动（北京时间2026-11-19 10:00以后）

两端各一次C256已正常cleanup、计数/双摘要核对并完整备份。PT2586计划槽：2555成功、28次ReadError、3本地未发；TRT5214槽：4954成功、1次ReadError、259本地未发。两端0～30秒在途持续增长均发生在保护前；精确连接层根因未记录，不把ReadError当429或60秒超时，不继续提高C。原控制脚本473433/479865因守卫在保存结果后退出，不重启或覆盖原case。详见 ../20261119-sync-c256/report.md。

sync-c256-checkpoint-20261119/evidence.tar.gz共66文件、2885560字节、SHA5d6c24f7e9533387c2b0e996aaa9bc1761e422f0692cd4f6ea9f6304ed2adea9，源前后不变，本机整包/逐文件校验解包通过。完整PT69/TRT74备份继续保留。

当前唯一GPU调度是backend-paired-i1-c1-20261119，父485407、首轮sync-r1-pytorch实例管理485413；三接口各3轮PT/TRT交错18组，I1/C1/b1、seed20261118、预热30秒/发送300秒、HTTP timeout60。使用普通load.py，仍冻结服务器b15dd39；待全部18轮cleanup及GPU空闲后才同步新audit/timing/协调工具。资源/代码守卫和完整日志保留，遇失败停止调查，不重复启动。方法/计划哈希见 ../20261119-backend-paired/report.md；教师单双发生器、并发业务审计、真实GPU统计开关、回退/分段及最终报告等仍待完成。下文为历史检查点，不能据此操作旧PID。

## 最新连接核查（北京时间2026-11-19 08:29～08:32）

本机至zhangs12（192.168.29.12:22）的有界SSH及独立TCP探测均超时，服务器进程/产物/GPU状态本轮不可核实，不能沿用历史描述声称当前正常，也不据此认定实验已停止。未向服务器发出更改或另启GPU任务，自动续跑保留；恢复后先重新核实实际进程/文件再继续。详见 [连接检查点](../20261119-connectivity/report.md)。下文运行状态均为最后已验证的历史证据。

## 连接恢复与原串行全部结束（北京时间2026-11-19 09:40以后，覆盖上节）

SSH恢复。已实查无capacity/instances/load遗留，指定GPU3MiB/0%，两份environment日志均正常finished。PT69/TRT74轮均有case-result及cleanup，无未完成轮；TRT完整原始计数/双摘要核对通过，新快照summary SHA10693fbcc95f0e9c0f2345262baf5c61e7d46f59f5b98578d261338a737ce9a5、cases SHA0b973687821a5ba7f5314d35fa17f6e6b07778d5b66a2e0c68a331ac222c9d67，本机相同。

完整原PT69+TRT74共2797文件已打包formal-capacity-checkpoint-20261119/evidence.tar.gz，386327166字节、SHAdd7823f5bf89ae6e398b877871e36e90df4aefa43d75569d99a245a83d122fc6；源打包前后不变，本机整包/逐文件验证解包。学生21轮和教师29轮分别见 ../20261119-trt-student-capacity/report.md、../20261119-trt-teacher-capacity/report.md。学生稳定性I2/C8/b4共31758成功，110%341次429已对应b4满载；教师I8/C16/b2共404683成功，100%/110%有615/4680未发送积压，需独立单双发生器补证，不能称目标到达能力。

本地协调工具47ac26f已推送，25项CPU回归通过；Linux资源采样与真实GPU未验。服务器继续b15dd39，不拉取。已启动独立sync-c256-supplement-20261119串行驱动473433，先PT I8/rate14.366/C256，再TRT I8/rate28.963/C256，同seed2725806188、30秒预热/180秒发送/60秒超时；保留原b/队列/服务/FP16，先检查主机20GiB预算及GPU空闲。不重复启动，待两轮cleanup和GPU空闲后再同步后续工具。驱动日志environment-20261118/sync-c256-supplement-20261119.log。整体任务及采用未完成。

## 历史检查点（北京时间2026-11-18 23:47，最新状态见下节）

人数原计划22轮已采集。闭环30分钟23766次零失败；开放80%/100%均零失败，110%有168个发生器保护槽未发，实际2418 HTTP/业务全成功。不能把C32保护当服务器峰值，首次保护17.81985秒。发生器CPU8.54%均值，发送滞后最大3.61ms；需原流程结束后补110%同配置C256，协议已写入02/04/05。旧人数路由不走BatchAdmissionController，报告已修正b配置作用口径。原始粗分类保留不改，离线细分归因。

PyTorch学生原定19轮采集完成：闭环稳定性15774次零失败；定速80% 1249次零失败，100%/110%各5/154次服务429，已与日志running_batches=2及max=2逐项数量核对。100%首次拒绝时两请求约2.87/2.46秒，GPU显存增长同窗，底层慢原因未由日志证明；失败点不推荐，不能由闭环吞吐认定持续定速零失败。确认/稳定性100文件、定速50文件均已取回本机校验，见 ../20261118-torch-student-capacity/report.md。当前教师搜索已自动开始，随后PyTorch成功自动TensorRT；原调度4182465正常，不插入新GPU任务。新阶段证据见 ../20261118-torch-sync-capacity/report.md；22轮中110%不是零失败推荐点，人数最终结论仍待补测/同配置对照。

学生独立False基线、组合全量各5901条、96张私有差异图及校验备份已完成。仍需学生/教师容量、TensorRT容量、同配置对照、并发一致性和兼容回退。下文历史暂停记录不代表当前状态。

## 最新检查点：PyTorch原串行结束，TensorRT容量接续（2026-11-19）

PyTorch69轮原始采集已全部结束，完整原始计数/双摘要核对通过，无未完成轮；原调度4182465已自然退出，不能再按旧记录操作。shell4182399已自动启动TRT capacity父调度241591，服务源仍b15dd39。TRT第一点I1/C1零失败；目前按真实进程/journal继续，不拉取新工具、不插入GPU负载。

教师原定28轮均无HTTP/业务失败：稳定性351331次、195.17056图/s、P95 157.20ms；定速80%/100%/110%分别28202/35252/38777成功。但110%180秒计划38777，已发35786、完成35764，客户端未发2991/已发在途22，发送滞后均值7.80秒、最大15.42秒、发生器单核均值98.83%。不能把目标215.43或原usable=True写成真实服务到达能力，0～30秒检出的主要是客户端未发送增长，并非已证明服务排队。原流程后必须补教师单/双发生器闭环及I12/C96/b2、rate215.4276667定速配对，条件见02。

教师完整闭环560文件/104614416字节包SHA7be90556a89cfa7f5915612fece0a4f41889d3ad89a8ee0761f4b83d0af1cb3e；开放式103文件/13627089字节包SHA49303c8c432d61251563e42b0e3e518d4da4a2ca139b7a79186f381f1c287cc3，两包均已本机整包/逐文件验证解包。完整69轮及新增未发/在途分量版离线快照均已本机校验；旧快照不覆盖，详见教师报告。

现有TRT实例公开OpenAPI已只读取得，与PyTorch7路径/完整schema完全相同并备份；实际并发业务响应、回退、同配置配对、统计开关与读取下载等仍待执行。未完成整体任务或部署采用；无需用户干预，继续已授权范围。下方历史父PID/阶段记录均以本节及实时进程为准。

## TensorRT人数稳定性检查点（2026-11-19）

人数原定24轮已全部采集：14搜索、两候选各3轮确认、I8/C16的1800秒稳定性及80%/100%定速均零失败。稳定性47433次、26.34278图/s、P95 683.03ms；GPU显存12542MiB全窗、均值98.26%，发生器单核CPU均值14.87%。不同总C的PT/TRT稳定性不能冒充同配置收益。

sync-open-1.1（rate28.963、I8/C64）已完成：5214计划槽、418本地保护未发、4796实际HTTP/业务全成功，首次保护14.08694秒；CPU均值17.38%、发送滞后最大7.11ms，未见持续发生器CPU饱和。在途曲线受保护截断，不能称服务硬峰值。原流程已自动进入TRT学生搜索。原串行继续，无新增GPU任务。之后必须独立补TRT人数同服务I8/rate28.963/seed2725806188、C256单轮，条件见02，不省略原PT C256补测。

trt-sync-closed-checkpoint-20261119/evidence.tar.gz含21个已cleanup闭环case的403文件，47794159字节、SHA f547dbf114d6f82ac57ce20394ed0a884eb71caf959e35ec5acd917a6e9fa814，本机整包/逐文件核验解包。23轮离线快照capacity-analysis-20261119-trt-sync-stability亦已本机校验；新trt-sync-open-checkpoint-20261119/evidence.tar.gz为77文件、5014017字节、SHA1cd311ae0a60f7298a757a45a042a1c427029898fc5e9e8b7fef14a28ee4e7ea，已本机整包/逐文件核验解包，25轮新快照也已本机相符。详细资源、六轮确认与限制见 ../20261119-trt-sync-capacity/report.md。整体任务未完，不拉取服务代码，继续原调度241591。

## 当前长任务

服务器 `ssh zhangs12`，仓库 `/home/zhangs/workspace/vbas/`，分支 perf。原串行命令的PyTorch段已成功结束，TensorRT段正在执行。不要重复启动 GPU 任务。

- PyTorch：`/home/zhangs/workspace/vbas-benchmarks/torch-capacity-20261118/`。
- TensorRT：`/home/zhangs/workspace/vbas-benchmarks/trt-capacity-20261118/`。
- 日志：`/home/zhangs/workspace/vbas-benchmarks/environment-20261118/torch-capacity.log`、`trt-capacity.log`。
- 启动时服务器代码：0ca3a43。实验进行中避免改动或拉取会改变测量行为的代码；修复工具问题时保留无效轮证据并明确版本。
- 当前对话自动续跑心跳 ID：`vbas`，每 10 分钟。正常无变化保持安静，异常需检查恢复，全部已授权工作完成后删除心跳。
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
6. 生成正式报告/图表、结果校验及备份，按真实证据更新05任务清单和07完成出口，提交推送perf，完成后删除心跳。

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

## 2026-11-19新增工具准备（未改当前正式服务）

代码0beae6b已推送：timing.py及--trace-http默认关闭，只供audit-reference独立诊断；13项无模型回归、服务器FastAPI CPU替身body/headers/OpenAPI透明性检查通过。三接口各64回归集已冻结，201文件本机校验；R3对两后端×三接口快速/全量输入均通过，兼容旧ImageList省略及Torch half证据，原基线不改写。两次CPU预检失败与修复证据保留，未启动GPU。详见 ../20261119-http-timing/report.md 和 ../20261119-quick-regression/report.md。

原串行流程后还需执行：64图×3的两后端/三接口off/on诊断12组（I1/C1/b1）；全量池/load.py同配置I1/C1/b1各后端3×300秒交错配对；两后端三接口全量并发业务审计；人数C256边界补测；PyTorch显式回退、TensorRT运行OpenAPI及输入读取/下载成本。所有真实GPU项仍待验，先查进程与空闲，不能重复启动或用诊断数据冒充普通容量。
