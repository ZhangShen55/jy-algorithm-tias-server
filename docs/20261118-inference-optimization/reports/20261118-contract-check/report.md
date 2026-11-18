# 接口结构核查

状态：本次优化与main起点的API/Schema静态定义相同，PyTorch学生NMS修正前后公开OpenAPI一致；TensorRT运行OpenAPI已比对相同，并发实际响应与回退仍待验证，不据此宣布全部接口兼容性验收完成。

## 当前PyTorch实测

从本轮已启动的实例 `http://127.0.0.1:18981/openapi.json` 读取公开契约，没有启动额外服务或模型推理。服务代码b15dd396172e5532661a88e547cb70e92a9f5147，与此前测量版 `contracts-20261118/openapi-pytorch.json` 逐结构相等；均为7个公开路径，压测专用控制端点未进入公开schema。前后SHA256相同：`697baa96efd0949fd6e787412ccee994154a026636b596d37602b9cb4ec53068`。

服务器证据：`/home/zhangs/workspace/vbas-benchmarks/contracts-pytorch-nms-false-20261118/{openapi.json,result.json}`，包含来源、采集时间、代码版本及校验值。已复制本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/contracts-pytorch-nms-false-20261118/`，schema校验通过。

此项只验证公开请求/响应结构与上一测量版一致，不等于检测数值完全一致；学生人数NMS=False语义已由用户确认。也不能替代与原main版本、TensorRT运行实例及高并发实际响应的后续核查。

## 与本任务main起点的静态核对

main固定为本任务起点 `9f2a5f0f9724f1b99a7269965105522b46e8ae88`，perf快照 `89cfe26d57138bc8b7e11d09a391f7c5e66600ec`。逐文件比较api/与schemas/的Git blob，19份文件清单及内容全部相同，没有新增、删除或改写路由/请求响应Schema。main.py唯一差异是开启旧接口时的导入从 `from .api.tasks` 修正为根目录运行所需的 `from api.tasks`，路由包含条件未改。

静态证据保留于本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/contracts-main-static-20261118/result.json`，SHA256 `be290e22186ba29d2b191ec359520427aeb368b1dcdcadf4d9415d9322c97cd8`，含每文件blob标识及入口完整差异。此处是相对已经移除教师头姿功能的main起点，不追溯更早历史接口。静态定义相同不证明运行时数值、错误路径或高并发结果都一致，也不替代原main实际启动验证；TensorRT运行实例的OpenAPI及并发实际响应仍需后续补证。

## TensorRT现有运行实例核查（2026-11-19）

从原容量流程已经启动的TensorRT实例18981只读GET /openapi.json，不新建GPU实例、不调用推理；公开7条路径及完整schema与已冻结PyTorch逐JSON结构完全相等。采集代码仍b15dd39，证据服务器contracts-tensorrt-runtime-20261119/{openapi.json,result.json}及本机私有同名目录已相互校验。

本次文件JSON排版与原快照不同，文件SHA分别为openapi.json 817d60ae857e2929628e16a166b61301e11d715210c92877b5d855f70388adaa、result.json 6ae15f1d1549b748508aeecd222b8072a26b5d7b21be5679eb5fc96f9f912be6；文件哈希不同不代表结构变化，结构比较结果单独记录为true。高并发实际业务响应、异常路径与显式PyTorch回退仍待后续验证，不能仅凭OpenAPI相同认定所有兼容性完成。
