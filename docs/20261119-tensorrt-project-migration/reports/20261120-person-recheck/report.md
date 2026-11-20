# 四张人数差异图定向复验

状态：复验、原始记录复核、完整封存和本机逐文件核验完成。结果说明框数/业务计数差异，未进行人工真值标注或生产验收。范围是原四张图，不扩大为新的百图或性能测试。

## 核心结论

四图 `student_false` 模式下TRT各少一个同类别匹配后的原始框，重复三次稳定复现。但四个位置的TRT仍输出另一类别的高度重叠框（Head/Top_Head，IoU 0.94062～0.98551）；Torch中该另一类别框也存在。因此这里是同一空间位置的跨类别重叠候选差异，不能把“少一个框”表述成“确定漏掉一个人”。无人工标注，也不能由此宣布TRT真实准确率更高。

学生统计函数保持原NMS=False并逐类阈值筛选，三图有效计数少1，0054有效计数相同；传统人数路径原NMS=True的四图逐类筛选后计数全部相同。以上是现有统计口径下的计数，不是真实人头标注。

| 图片 | 学生口径原始框 PT / TRT | 学生有效计数 PT / TRT | 传统人数有效计数 PT / TRT | PT独有类别 → TRT同位置保留类别 | 空间IoU |
|---|---:|---:|---:|---|---:|
| 0327.jpg | 53 / 52 | 53 / 52 | 51 / 51 | Top_Head → Head | 0.95238 |
| 0352.jpg | 44 / 43 | 43 / 42 | 42 / 42 | Head → Top_Head | 0.94691 |
| 0054.jpg | 44 / 43 | 43 / 43 | 43 / 43 | Head → Top_Head | 0.94062 |
| 0437.jpg | 24 / 23 | 24 / 23 | 22 / 22 | Top_Head → Head | 0.98551 |

0054的Torch独有Head框置信度0.11474609375，低于原Head业务阈值0.25，两端有效计数因此均43。其余三图独有框通过既有业务阈值，学生计数差异如表保留。NMS=False保持跨类别独立抑制，输出Head与Top_Head重叠框并不自动合并为一个人；本次不修改NMS、阈值或计数逻辑。尚未定位产生候选差异的具体数值运算/抑制步骤，不直接归因为FP16舍入。

## 冻结条件与方法

- 时间：2026-11-20T14:19:24.972344+08:00 ～ 2026-11-20T14:23:21.246467+08:00（北京时间）。run_id为 `trt-migration-20261120-person-recheck-r1`（PT完成、TRT启动失败）及 `...-r2`（仅TRT补正复验脚本）。
- 实测代码 `3f77bfdcb197fd7bb957e45104342389ed3daca7`，服务器tracked/worktree干净；未更新项目代码、私有配置或模型。源PT SHA `236b0c44a71c5f2d06b6572a681ac16cc7f33564071b92aa1f60f026e61b0837`，Engine SHA `6bb59afb8b46b13ff1506fb70220bec3f5274cbde20e8920f68740a53801722c`，manifest SHA `0af5bc09e65fc318fcdb7a2b66263522091b79f66d1bbe32892bb0fc53517360`，均与既有受审资产一致。
- 唯一受测目标 `GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49`，RTX3090；r2实际设备UUID、名称、计算能力8.6逐项断言。PT使用vbas，TRT使用vbas-trt；Torch2.12.1+cu130、Ultralytics8.3.156、TensorRT10.13.3.9，既有环境不改。
- 四张原图ID/内容SHA、原100张清单SHA及预测原件SHA逐项核对；固定FP16、1088×1920、rect=False、conf0.1、IoU0.7、max_det300，False/True两种原有NMS模式各3次。两端各1次零图预热不计正式。
- 共48次原始预测和24次实际 `services.student_behavior_service.process_person_detection` 调用成功；48份原始框数组均逐值等于各自旧结果，同后端三次也严格一致。实际学生函数注入隔离的真实单模型及原阈值，避免加载其他模型，输出位置/计数完整保存；不是HTTP端点复测。传统人数数值按相同既有逐类筛选逻辑从NMS=True实测框计算，也不是HTTP响应采集。
- 业务阈值保持Head0.25，其余Top_Head/Hat/Headphones/Shoulder0.1；类别Other不计数。图像、置信度、类别、坐标与完整输出均留在私有证据。

## 启动异常与处置

r1的TRT在零图warmup前加载失败，日志含 `expecting compute 8.9 got compute 8.6` 和后续 `AttributeError`。此前临时状态中对错误字面的Engine兼容性解释不是最终结论。定位到私有复验脚本未先初始化指定CUDA设备，使用整数device=0触发Ultralytics `select_device` 对CUDA_VISIBLE_DEVICES的改写。PT在model.to时已初始化，因此未出现该启动异常。

r2仅在独立复验脚本中先初始化指定卡、断言唯一实际UUID/RTX3090/8.6，并传 `torch.device('cuda:0')` 避免该分支改写；未重建/替换Engine、未切换授权GPU或修改项目运行库。同一SHA Engine成功加载并完成全部36次调用，证明不是本Engine无法在3090加载。r1未记录失败时最终CUDA设备属性，不能补造该属性，也不把错误文字当作Engine构建卡的独立证明。启动失败日志、异常链、原脚本/plan全部保留，单列1次启动失败，不能说整次补证没有任何失败。

## 完整性、复现与清理

原始目录：服务器 `/home/zhangs/workspace/vbas-benchmarks/trt-migration-20261120-person-recheck-r1/` 和 `...-r2/`；脚本副本、plan、模型清单、四张原图、源业务函数、两端原始预测、实际函数输出、异常日志、summary及cleanup完整留存。精确启动命令：设CUDA_VISIBLE_DEVICES为指定UUID，分别用vbas/bin/python运行r1/recheck.py --backend pytorch、vbas-trt/bin/python运行r2/recheck.py --backend tensorrt；cwd由脚本绝对锚定仓库。再次运行必须另建run_id，不能覆盖原件。

完整包 `trt-migration-20261120-person-recheck-checkpoint-r1/evidence.tar.gz`：30文件、1383299字节，SHA256 `dbc29a9e3ce7e56316845da8e1c6a2216a2206f01c9417aa25b4d5aff4e6dcc0`；打包前后源指纹不变。本机 `/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/trt-migration-20261120-person-recheck-checkpoint-r1/` 整包、30成员及解包文件全部核验。相同归集器在本机对解包原件独立重算，与服务器summary逐字节一致，SHA256 `a8f8dbea58f512b078e58a38cfca438f0d84c5930a55ad856c666a84f9e8855d`。

子进程自然退出，指定GPU恢复3MiB/0%，Engine SHA未变，服务器工作区干净。仅新增脱敏补充报告/任务记录，照片、完整配置和日志不推Git。原37项迁移交接与旧报告不覆盖，采用/部署决定继续由用户复核。
