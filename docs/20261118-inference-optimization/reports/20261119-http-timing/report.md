# 可关闭HTTP时间线：实现、CPU检查与GPU待验

状态：12组真实GPU开关诊断已完成，2304正式调用零失败，开关业务响应和12份公开OpenAPI结构相同；1152条正式时间线、2304个模型span完整，171份原始/派生证据已本机整包及逐成员核验。统计开销限于本次单组开关观察，不作为容量评分或完整分段全部完成。

## 采集范围与默认关闭

instances.py新增--trace-http，仅允许与--audit-reference独立诊断共同使用；不传时清除继承的诊断变量，worker不安装任何时间线补丁。生产main.py和公开API没有修改。不能把诊断额外采集/审计开销算作普通容量成绩。

启用时只在benchmark worker安装ASGI及函数时间线，记录请求收取、Request.json、请求体验证、Base64/图片解码、ROI/业务函数、模型predict完整调用、响应校验/dump、JSON render、ASGI发送。保存request_id、PID、线程ID、起止/耗时与大小；不保存请求body、张量或认证头。模型层只读取原已有Ultralytics speed，不新增CUDA同步，也不消费stream生成器或保留Results/张量引用。

审计客户端附带两项内部关联头：序号及经UTF-8百分号编码的图片ID；不改JSON请求或响应，不向响应添加调试字段。warmup没有client_sequence，正式诊断可据此与responses.jsonl逐条关联。输出为独立的timing-端口.jsonl，存在时拒绝覆盖。

各span是wall-clock，异步函数含等待/调度；Request.json可能含body等待，服务/模型span相互嵌套，学生模型并行不能直接求和。Ultralytics speed包含其同步/调度影响，不当作纯内核时间。ASGI send返回只代表交给传输层，不是客户端接收完成；total_asgi_ms不包含时间线写盘。H2D/归一化/纯forward/NMS/D2H等细分继续结合已有独立CUDA Events分段诊断，不能把两种模式混为正常并发容量成绩。

## 已通过的非GPU检查

- `python3 -m unittest discover -s tests/benchmark -p 'test_*.py'`：13项通过，涵盖审计输入/历史格式/FP16及NMS保护、失败停发、并发采集、时间线线程上下文传播/请求隔离、Unicode ID、异常保持与原证据不覆盖。
- 服务器vbas FastAPI0.115.13：只构造CPU替身应用和4×4图像，不导入torch，CUDA_VISIBLE_DEVICES为空。启用前后响应body字节及规范化headers字典相同、OpenAPI相同，9类必要span均被捕获。此检查不是真实GPU模型或生产服务验收。
- CPU集成证据服务器 `http-timing-cpu-check-20261119/{result.json,timing.jsonl}`，已取回本机同名目录并核验trace SHA `2debcf50725986b4a4f912951e7133adcb412104cc36358fa5552bdd41458391`；时间线实现SHA `2f22188eabbe45b5c681d7a6e5864bddb00a072d7fc5906f1a9b954126f9b9c0`。

## 原定GPU开关对照方法（完成结果见末节）

确认原PyTorch→TensorRT流程完成、没有instances/load运行且指定GPU空闲后再同步代码；三接口分别在两后端做关闭/开启各一组，共12组。固定I1/C1/b1、FP16、30秒预热、quick-regression-20261119每接口64张、audit-repetitions=3、seed=20261118，每组192次，共2304次正式调用。开启组加--trace-http，其它请求、配置、输入排列及服务相同。各接口两后端使用相反的off/on次序减少顺序偏差，记录真实次序和版本，不覆盖旧结果。

audit.py已增加客户端post至完整body接收的逐图P50/P95/P99/均值，排除本次响应对照及落盘；该模式仍不能用于正常容量评分。比较开关时延差、服务端时间线、实际响应一致性、OpenAPI和资源。192样本的P99需注明尾部采样限制，不建立看结果后倒推的开销/SLO验收门槛，只报告观察值及限制。所有HTTP/业务失败必须检查，不能据此声称配置通过。

检查每个开启组的正式client_sequence覆盖全部0～191、image_id匹配，模型调用数按人数2/学生3/教师1核对；时间线写入失败或缺项不能作为完整分段证据。若出现数值差异，保留全量对照而不自动接受。关闭组不应生成时间线文件。

## 保持独立的后端公平比较

上述开关组只测统计开销，不能替代同配置后端性能比较。三接口另用load.py、全量请求池、I1/C1/b1、相同seed=20261118，固定30秒预热/300秒发送，各后端3轮交错配对；同时保留各自最佳配置的正式容量结果。配对差异、样本覆盖和加载策略均需报告，不把审计保存/比较开销归为后端性能。

真实GPU阶段、输入读取/下载成本、完整开销与最终出口仍待完成；本报告不是全部分段或任务完成声明。

## 2026-11-19 真实GPU阶段启动记录

六组全量审计11802次业务一致、42个运行OpenAPI结构相同、197文件本机完整核验后，确认GPU3MiB/0%且无instances/audit/load，才启动控制567989。run_id为http-timing-gpu-20261119，脚本/日志在environment-20261118/同名.py/.log，驱动SHA35b829a0f38e107603b03dac7a56bdb1d1090fe3621383cc5d092b76eb637b6a。服务器冻结e90b31f，正式四引擎/FP16/请求与服务配置不变。

驱动仅编排既定12组：每接口PT off→on、TRT on→off，I1/C1/b1、30秒预热、64×3、seed20261118、timeout60，总2304正式调用。每组独立目录，保留完整响应、资源、运行OpenAPI、开启组时间线及关闭组无时间线检查。每个开启组验证正式序号0..191/图像ID、模型调用人数2/学生3/教师1及8类公共span；失败保留、停止调查，不自动覆盖重跑。默认无参数仅CPU输入预检，--run才启动；服务器12组CPU预检及本机12项合成校验已通过，preflight.json保存，但不能替代真实GPU或开销验证。该阶段正在执行，结果、对照、完整备份及限制后续按实际证据补写。

## 真实GPU执行结果与时延变化（2026-11-19）

12组全部自然结束并cleanup，原控制567989已退出，指定GPU3MiB/0%。各组完整192次、序号0..191、64个ID各3次，SHA及请求顺序一致，业务响应规范化后与同后端子集顺序基线相同；同接口/后端开关之间192对亦相同。12份运行OpenAPI完整结构相同且与此前全量审计契约相同。六个关闭组均无trace；六个开启组共有1152正式HTTP时间线，按接口2/3/1模型调用逐请求核对，共2304模型span；预热trace另存，不混入正式统计。8类公共span逐请求覆盖，数值有限且非负，无时间线写入错误标记。

下表为客户端post至完整body时延，排除随后响应比较/落盘；每个off/on各192样本。P95差为两组分位数相减，非差值分布的P95。每个后端/接口只有1个off组和1个on组，64图重复3次不是三轮独立实例复测；负差也不证明零开销。未建立事后开销合格阈值，不称生产SLO通过。

| 接口 | 后端 | off均值 ms | on均值 ms | on−off均值 ms | 均值变化% | off/on P95 ms |
|---|---|---:|---:|---:|---:|---:|
| sync | pytorch | 103.983 | 105.158 | +1.175 | +1.130 | 107.019/108.517 |
| sync | tensorrt | 70.837 | 69.930 | -0.907 | -1.280 | 74.670/72.773 |
| student | pytorch | 137.726 | 140.852 | +3.126 | +2.270 | 140.245/143.300 |
| student | tensorrt | 75.825 | 76.306 | +0.481 | +0.634 | 78.012/78.751 |
| teacher | pytorch | 33.395 | 32.859 | -0.536 | -1.605 | 36.531/35.706 |
| teacher | tensorrt | 21.220 | 21.856 | +0.636 | +2.996 | 23.547/24.440 |

六对平均变化范围−1.605%至+2.996%；观察值受组次顺序、GPU温度/时钟、CPU调度和有限样本影响，不能把负值当作追踪加速或零成本。每组P50/P95/P99/均值、同序号差值分布及每遍均值保存在summary。192样本的P99仅依赖极少数尾部值，不能认为尾延迟稳定。原普通load.py配对结果继续作为后端性能对照，不能用本诊断替代。

## 请求内分段观察

下表为开启组各span的均值ms，均为wall-clock。JSON方法span可能含缓存/等待，Pydantic响应span含校验与dump；ASGI总时间不含trace写盘。ASGI send返回只代表交给传输层，不等于客户端接收。各span相互嵌套、学生模型并行，禁止相加或以客户端减ASGI残差直接认定网络/排队耗时。

| case | JSON方法 | 请求体验证 | Base64 | JPEG | 响应校验/dump | JSON render | ASGI总计 |
|---|---:|---:|---:|---:|---:|---:|---:|
| sync-pytorch-on | 0.5219 | 0.0544 | 0.9506 | 8.8394 | 0.1019 | 0.1411 | 100.2669 |
| sync-tensorrt-on | 0.5195 | 0.0496 | 0.9411 | 8.8045 | 0.0906 | 0.1488 | 65.0893 |
| student-pytorch-on | 0.5359 | 0.0315 | 0.9848 | 8.9050 | 0.0904 | 0.1566 | 135.8989 |
| student-tensorrt-on | 0.5384 | 0.0329 | 0.9790 | 9.1102 | 0.0921 | 0.1380 | 71.2130 |
| teacher-pytorch-on | 0.4412 | 0.0326 | 0.8483 | 8.4128 | 0.0404 | 0.0464 | 28.3861 |
| teacher-tensorrt-on | 0.4513 | 0.0320 | 0.8595 | 8.5980 | 0.0396 | 0.0456 | 17.3794 |

| case | 模型 | predict完整wall均值/P95 ms |
|---|---|---:|
| sync-pytorch-on | yolo_face_model | 40.998/42.116 |
| sync-pytorch-on | yolo_person_model | 41.491/42.043 |
| sync-tensorrt-on | yolo_face_model | 23.229/23.734 |
| sync-tensorrt-on | yolo_person_model | 24.288/24.622 |
| student-pytorch-on | yolo_face_model | 121.929/123.122 |
| student-pytorch-on | yolo_person_model | 122.905/123.937 |
| student-pytorch-on | yolo_student_model | 122.679/123.825 |
| student-tensorrt-on | yolo_face_model | 57.071/58.313 |
| student-tensorrt-on | yolo_person_model | 58.138/59.257 |
| student-tensorrt-on | yolo_student_model | 57.759/58.852 |
| teacher-pytorch-on | yolo_teacher_behavior_model | 17.250/18.302 |
| teacher-tensorrt-on | yolo_teacher_behavior_model | 6.080/6.337 |

predict墙钟包含其预处理、搬运、锁/调度、网络执行及后处理，不等于纯forward或CUDA kernel时间；沿用原分段CUDA Events诊断解释细项。学生PT三个predict均约122ms而ASGI总约136ms，正体现并行/嵌套，不能求和为367ms请求耗时。人数ROI mask和process_polygon等业务span亦保存于stages.json；教师/学生未执行的ROI路径没有伪造耗时。

资源时间序列完整保留，但audit summary未保存容量模式同款绝对正式窗口起点，关闭组不能据此重建精确的逐请求Unix采样窗口；本报告不将含启动/预热的GPU/CPU均值冒充普通容量正式窗资源。本轮未新增CUDA逐段同步，不修改业务响应或默认生产入口。输入文件读取/URL下载成本仍待独立CPU补测，业务聚合/准入/网络各自独占耗时也不能由嵌套span机械拆分，因此不标所有分段已完成。

## 完整原始证据与备份

- run_id：http-timing-gpu-20261119，代码e90b31f943f9ec59942297214b0397913f07e08c，plan SHA5be716efff0985d7cc61a115aead3dad0e989f2e9c741e21dc20b67699ba5184；驱动SHA35b829a0f38e107603b03dac7a56bdb1d1090fe3621383cc5d092b76eb637b6a。
- 独立归集http-timing-analysis-20261119/summary.json SHA114421ce908214bf27ccacb11f88ae031acb1ae76623fb122609ca2439f16ed9；stages.json保留每项数量/均值/分位数及OpenAPI成员清单，归集脚本也入包。
- http-timing-checkpoint-20261119/evidence.tar.gz含171源文件、3663335字节，SHAa67e70fa717015a639b684de8dbdf281b6048c6620f387cff8ce2a0d55830197，源打包前后不变。包含全量正式/预热时间线、响应、资源、配置/日志/事件、运行OpenAPI、两个控制/分析脚本及CPU预检。
- 本机/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/http-timing-checkpoint-20261119/已整包及171成员核验解包，local-verification.json保存结果；原照片/Base64/完整配置/响应不推Git。

本阶段工具开关与有限开销观察完成，后续发生器GPU工具预检和42组教师补证、显式回退、读取下载成本以及最终图表/报告继续，不重复本12组或改写历史结果。
