# 可关闭HTTP时间线：实现、CPU检查与GPU待验

状态：工具及CPU替身检查完成；原18组配对和六组全量并发业务审计已结束并完整备份，正在e90b31f上执行12组真实GPU开关诊断。实际分段/开销和开关结果尚未归集，不写为已完成。历史实现/CPU记录保留。

## 采集范围与默认关闭

instances.py新增--trace-http，仅允许与--audit-reference独立诊断共同使用；不传时清除继承的诊断变量，worker不安装任何时间线补丁。生产main.py和公开API没有修改。不能把诊断额外采集/审计开销算作普通容量成绩。

启用时只在benchmark worker安装ASGI及函数时间线，记录请求收取、Request.json、请求体验证、Base64/图片解码、ROI/业务函数、模型predict完整调用、响应校验/dump、JSON render、ASGI发送。保存request_id、PID、线程ID、起止/耗时与大小；不保存请求body、张量或认证头。模型层只读取原已有Ultralytics speed，不新增CUDA同步，也不消费stream生成器或保留Results/张量引用。

审计客户端附带两项内部关联头：序号及经UTF-8百分号编码的图片ID；不改JSON请求或响应，不向响应添加调试字段。warmup没有client_sequence，正式诊断可据此与responses.jsonl逐条关联。输出为独立的timing-端口.jsonl，存在时拒绝覆盖。

各span是wall-clock，异步函数含等待/调度；Request.json可能含body等待，服务/模型span相互嵌套，学生模型并行不能直接求和。Ultralytics speed包含其同步/调度影响，不当作纯内核时间。ASGI send返回只代表交给传输层，不是客户端接收完成；total_asgi_ms不包含时间线写盘。H2D/归一化/纯forward/NMS/D2H等细分继续结合已有独立CUDA Events分段诊断，不能把两种模式混为正常并发容量成绩。

## 已通过的非GPU检查

- `python3 -m unittest discover -s tests/benchmark -p 'test_*.py'`：13项通过，涵盖审计输入/历史格式/FP16及NMS保护、失败停发、并发采集、时间线线程上下文传播/请求隔离、Unicode ID、异常保持与原证据不覆盖。
- 服务器vbas FastAPI0.115.13：只构造CPU替身应用和4×4图像，不导入torch，CUDA_VISIBLE_DEVICES为空。启用前后响应body字节及规范化headers字典相同、OpenAPI相同，9类必要span均被捕获。此检查不是真实GPU模型或生产服务验收。
- CPU集成证据服务器 `http-timing-cpu-check-20261119/{result.json,timing.jsonl}`，已取回本机同名目录并核验trace SHA `2debcf50725986b4a4f912951e7133adcb412104cc36358fa5552bdd41458391`；时间线实现SHA `2f22188eabbe45b5c681d7a6e5864bddb00a072d7fc5906f1a9b954126f9b9c0`。

## 原容量流程后的GPU开关对照（待执行）

确认原PyTorch→TensorRT流程完成、没有instances/load运行且指定GPU空闲后再同步代码；三接口分别在两后端做关闭/开启各一组，共12组。固定I1/C1/b1、FP16、30秒预热、quick-regression-20261119每接口64张、audit-repetitions=3、seed=20261118，每组192次，共2304次正式调用。开启组加--trace-http，其它请求、配置、输入排列及服务相同。各接口两后端使用相反的off/on次序减少顺序偏差，记录真实次序和版本，不覆盖旧结果。

audit.py已增加客户端post至完整body接收的逐图P50/P95/P99/均值，排除本次响应对照及落盘；该模式仍不能用于正常容量评分。比较开关时延差、服务端时间线、实际响应一致性、OpenAPI和资源。192样本的P99需注明尾部采样限制，不建立看结果后倒推的开销/SLO验收门槛，只报告观察值及限制。所有HTTP/业务失败必须检查，不能据此声称配置通过。

检查每个开启组的正式client_sequence覆盖全部0～191、image_id匹配，模型调用数按人数2/学生3/教师1核对；时间线写入失败或缺项不能作为完整分段证据。若出现数值差异，保留全量对照而不自动接受。关闭组不应生成时间线文件。

## 保持独立的后端公平比较

上述开关组只测统计开销，不能替代同配置后端性能比较。三接口另用load.py、全量请求池、I1/C1/b1、相同seed=20261118，固定30秒预热/300秒发送，各后端3轮交错配对；同时保留各自最佳配置的正式容量结果。配对差异、样本覆盖和加载策略均需报告，不把审计保存/比较开销归为后端性能。

真实GPU阶段、输入读取/下载成本、完整开销与最终出口仍待完成；本报告不是全部分段或任务完成声明。

## 2026-11-19 真实GPU阶段启动

六组全量审计11802次业务一致、42个运行OpenAPI结构相同、197文件本机完整核验后，确认GPU3MiB/0%且无instances/audit/load，才启动控制567989。run_id为http-timing-gpu-20261119，脚本/日志在environment-20261118/同名.py/.log，驱动SHA35b829a0f38e107603b03dac7a56bdb1d1090fe3621383cc5d092b76eb637b6a。服务器冻结e90b31f，正式四引擎/FP16/请求与服务配置不变。

驱动仅编排既定12组：每接口PT off→on、TRT on→off，I1/C1/b1、30秒预热、64×3、seed20261118、timeout60，总2304正式调用。每组独立目录，保留完整响应、资源、运行OpenAPI、开启组时间线及关闭组无时间线检查。每个开启组验证正式序号0..191/图像ID、模型调用人数2/学生3/教师1及8类公共span；失败保留、停止调查，不自动覆盖重跑。默认无参数仅CPU输入预检，--run才启动；服务器12组CPU预检及本机12项合成校验已通过，preflight.json保存，但不能替代真实GPU或开销验证。该阶段正在执行，结果、对照、完整备份及限制后续按实际证据补写。
