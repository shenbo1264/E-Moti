# 原首次全量控制台日志未保留

最终重跑前输出目录替换错误覆盖了首次控制台日志。本目录的原始 JUnit XML 和 completed run.json 已在覆盖前保存并恢复，准确记录 2,136 passed、8 failed、4 skipped。8 项失败另有独立 subject-precedence-red.log / .xml 复现。不能把最终重跑日志当作首次日志。最终 b5 全量的原始 log/XML/run.json 已按原字节归档到 ../final-tests/；完整保管记录见 ../test-artifact-custody.json。
