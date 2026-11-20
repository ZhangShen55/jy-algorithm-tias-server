# 完整证据索引

所有下列包均源前后指纹一致，本机整包及全部成员/解包逐文件核验。服务器私有根/home/zhangs/workspace/vbas-benchmarks/；本机根/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/。实际文件/密钥/照片不入Git，校验元数据与local-verification.json随同名目录保存。

| 目录 | 文件数 | 包字节 | SHA256 |
|---|---:|---:|---|
| trt-migration-20261119-reference-r1 | 31 | 1593570673 | 2dc960f08af14ff468017f51a09877c9972de774999a8869e4a4724fdcaa07c3 |
| trt-migration-20261119-model-checkpoint-r1 | 279 | 259295746 | d4986aa32c1c0ac8814dc9378f8fbea0893c8bc6f0213c08931d0e8b03646cbc |
| trt-migration-20261119-business-checkpoint-r1 | 140 | 16350948 | e7507f5296574f17d86164735f41b183414b15b2048c0adc9d717b27ce96ccea |
| trt-migration-20261119-functional-checkpoint-r1 | 312 | 74845956 | 8c9e9545e103b558810035e622bbc5f1524045fbab59a7d50aa4bf4aa5aba0de |
| trt-migration-20261119-protection-checkpoint-r1 | 48 | 403134042 | 39706a4a68feaf807941e315bba53726a09499664a3aa1995a22fe9d11c778af |
| trt-migration-20261119-full-input-checkpoint-r1 | 3740 | 986801722 | ac73270ffec4bac045856329b8d6cb70fd229d5b5dcd1c556e38c542c8843038 |
| trt-migration-20261119-export-checkpoint-r1 | 44 | 2346343050 | f86ac31678760364f7e1dc191be557cf297b74a55f556cb30137b1b0a4db004b |
| trt-migration-20261120-completion-checkpoint-r1 | 6155 | 1614726185 | 23c4eb98c1f9774ddc0f27cc67f238b2ca5d95733d113419ed7b50e1be12664f |
| trt-migration-20261120-handoff-checkpoint-r1 | 25 | 340661533 | 18435a887ff695a299633134f2a48752f480d574c7cbc85f21e8899e19a0317f |
| trt-migration-20261120-exit-checkpoint-r1 | 3 | 1817 | 63e3a6a9c0e9838c2258fcafb914c9f262481a4867d4895461e92b08559a238b |

reference含26源文件+5代码/环境快照共31；保护包另有12符号链接映射、分析视图另有17映射，不当成额外模型/原始请求文件。full-input包3739照片全部匹配冻结dataset清单，双端核验；completion包包含全部5901正式payload及原始结果。handoff包包含实际项目model四Engine/manifest、测量代码bundle、配置、直接main192调用、环境复核。exit包保留GPU空闲/无任务进程/受保护路径与环境核对。首次不完整传输文件和异常分类保留，完整包恢复后重新校验；不以传输异常伪称GPU失败。旧优化任务备份未改写。
