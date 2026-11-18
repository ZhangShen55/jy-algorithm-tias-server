# 连续执行检查点

状态：执行中，未结项。用户已授权连续推进，不需要逐阶段询问启动。

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
