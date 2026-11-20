# 阶段证据索引（持续补齐）

此索引只列实际封存并本机核验的包，不表示最终性能与交接完成。服务器私有根目录/home/zhangs/workspace/vbas-benchmarks/，本机私有根目录/Users/zhangshen/.codex/backups/vbas-benchmark-20261118/。表中目录下均有evidence.tar.gz、逐文件checksums.json与package-result.json，本机另有local-verification.json及已核验解包文件。

| 目录（前缀trt-migration-20261119-） | 实际文件数 | 包字节数 | SHA256 |
|---|---:|---:|---|
| reference-r1 | 31 | 1593570673 | 2dc960f08af14ff468017f51a09877c9972de774999a8869e4a4724fdcaa07c3 |
| model-checkpoint-r1 | 279 | 259295746 | d4986aa32c1c0ac8814dc9378f8fbea0893c8bc6f0213c08931d0e8b03646cbc |
| business-checkpoint-r1 | 140 | 16350948 | e7507f5296574f17d86164735f41b183414b15b2048c0adc9d717b27ce96ccea |
| functional-checkpoint-r1 | 312 | 74845956 | 8c9e9545e103b558810035e622bbc5f1524045fbab59a7d50aa4bf4aa5aba0de |
| protection-checkpoint-r1 | 48 | 403134042 | 39706a4a68feaf807941e315bba53726a09499664a3aa1995a22fe9d11c778af |
| full-input-checkpoint-r1 | 3740 | 986801722 | ac73270ffec4bac045856329b8d6cb70fd229d5b5dcd1c556e38c542c8843038 |

reference含26个源文件及5个旧代码/环境快照，共31成员；源件前后指纹不变。full-input包将本机现有3739张图片全部对照冻结服务器dataset.jsonl的ID/SHA/字节数核验，再将3739照片+清单3740文件封存；并非新增采样或替换原数据。该包本机整包/3740文件核验完成；服务器副本亦已整包及3740成员/解包核验，server-verification.json留存。

保护包含48实际文件，12符号链接映射另存symlinks.json，不将链接计为额外模型文件。原Engine内容保留于reference包；受审项目发布的manifest已在业务包留存。本机当前model四Engine SHA及manifest与实际业务测量时完全一致。私有测试密钥仅随私有保护包保留，不发布。

功能r1驱动拦截既定负例及保护r1路径冲突均保留在各阶段包，不删除异常。旧优化任务已有备份独立保留，不改写其清单或将未归集项标为完成。

离线构建补充：export-checkpoint-r1，44文件、2346343050字节、SHA256 f86ac31678760364f7e1dc191be557cf297b74a55f556cb30137b1b0a4db004b，本机全件核验。

尚待补齐：18配对及3稳定性全原始证据、最终代码/恢复/清理快照和最终统一索引。没有人工标注，模型差异接受仍由用户复核。
