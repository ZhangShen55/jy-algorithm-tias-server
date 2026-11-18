# 接口结构核查

状态：PyTorch学生NMS修正前后公开OpenAPI一致；TensorRT与原main契约对照、并发响应一致性仍待验证，不据此宣布全部接口兼容性验收完成。

## 当前PyTorch实测

从本轮已启动的实例 `http://127.0.0.1:18981/openapi.json` 读取公开契约，没有启动额外服务或模型推理。服务代码b15dd396172e5532661a88e547cb70e92a9f5147，与此前测量版 `contracts-20261118/openapi-pytorch.json` 逐结构相等；均为7个公开路径，压测专用控制端点未进入公开schema。前后SHA256相同：`697baa96efd0949fd6e787412ccee994154a026636b596d37602b9cb4ec53068`。

服务器证据：`/home/zhangs/workspace/vbas-benchmarks/contracts-pytorch-nms-false-20261118/{openapi.json,result.json}`，包含来源、采集时间、代码版本及校验值。已复制本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/contracts-pytorch-nms-false-20261118/`，schema校验通过。

此项只验证公开请求/响应结构与上一测量版一致，不等于检测数值完全一致；学生人数NMS=False语义已由用户确认。也不能替代与原main版本、TensorRT运行实例及高并发实际响应的后续核查。
