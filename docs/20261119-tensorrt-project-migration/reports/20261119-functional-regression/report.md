# 专项输入、几何、共享状态与恢复

新代码f5a7f3a，旧参考e90b31f。全程仅指定GPU1、FP16、独立loopback端口、外部注册关闭，未部署。功能诊断I1/C3/b3、queue0仅用于三接口共享隔离，不是正常容量配置。

| 阶段 | 调用 | 200 | 既定500负例 | 既定422负例 |
|---|---:|---:|---:|---:|
| 旧TRT：42专项+192交替 | 234 | 225 | 6 | 3 |
| 新TRT：42专项+192交替+576混合 | 810 | 801 | 6 | 3 |
| 新TRT其他cwd重启 | 192 | 192 | 0 | 0 |
| 旧PT恢复单元 | 192 | 192 | 0 | 0 |

合计1428调用。正常输入1404次成功；另外6次空ROI返回兼容200；18次预先声明的错误输入状态/详情符合旧契约。42项迁移前后同Engine TRT响应与状态全部规范化相等；交替、混合三轮及重启均对独立64图顺序TRT参考逐项一致。旧PT恢复在vbas环境、旧工作区以三接口各64图核对独立PT参考；没有在新TRT-only服务中添加PT后退。

专项覆盖横/竖图、1280×720/640×480、多个/空ROI、多图请求；Base64/data URL/本地绝对与相对文件/受控localhost URL，缺图/坏图及schema错误。Health、WorkerStatus、Drain均保存，排空后健康状态draining；服务从项目根与/tmp启动，EngineRoot为空仍定位项目model/。所有测试实例正常终止回收。

7个加载前拒绝：教师ImageSize1280/320/640.5/无效字符串、pytorch后端、half=False及CPU。均具体说明错误且torch/TRT未导入，符合用户固定640决定。原图尺寸仍可变化。

## 几何结果与PT原业务差异

实际LetterBox与scale_boxes的CPU几何往返：两种目标shape×6种原图共12组，最大绝对误差0.00006103515625像素，满足预设0.001像素数学往返检查。它验证坐标变换，不衡量检测准确率。

另以旧PT原可变矩形预处理跑同42项，27项规范化响应不同、8项有计数差异，完整逐项记录于私有pt-trt-original-business-differences.json。以下TRT减PT的计数变化必须保留。这一对照同时包含预处理与后端差异，不能归因于单独FP16转换；同形状模型100张数值对照见独立报告。未改阈值或挑图求相等。

| 场景 | 计数差（TRT−PT） |
|---|---|
| sync-wide | {"PersonCnt": 1} |
| sync-portrait | {"PersonCnt": -2} |
| sync-small | {"PersonCnt": -12, "FaceCnt": -1} |
| sync-roi | {"PersonCnt": -1} |
| student-wide | {"ObjectType:100": 3} |
| student-portrait | {"ObjectType:100": -2} |
| student-small | {"ObjectType:205": -1, "ObjectType:101": -1, "ObjectType:100": -13} |
| student-roi | {"ObjectType:100": -1} |

用户差异复核/采用仍待定；没有人工标注，不宣称真实精度通过。

## 驱动异常与证据

首次functional-r1在旧学生缺图返回既定500时，被驱动过严的“全部5xx拒绝”拦住。服务原代码本就以该状态/detail表示缺图；未改服务行为。r1原件保留，部分响应体未逐请求落盘，不能追认其完整响应对比。r2预先按错误场景分类，正常输入仍要求200，未知500/CUDA错误拒绝；3项驱动CPU回归通过后新run_id执行，并逐请求flush保存。所有r2正常场景零失败，负例单列。

完整备份trt-migration-20261119-functional-checkpoint-r1/evidence.tar.gz包含r1/r2、几何补测、7项启动拒绝、quick64完整参考与输入、控制脚本/日志/摘要。312文件、74845956字节、SHA256 8c9e9545e103b558810035e622bbc5f1524045fbab59a7d50aa4bf4aa5aba0de；源前后未变，本机整包/全部成员/解包文件逐项核验通过，位置为用户.codex/backups/vbas-benchmark-20261118/同名目录。完整照片/请求/配置/日志仅私有保存。

保护、多worker、离线新构建工具和有限性能/稳定性另行验证，本报告不替代这些出口。
