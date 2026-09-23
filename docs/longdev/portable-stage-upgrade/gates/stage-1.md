# 阶段 1 主会话 gate

日期：2026-09-23。结论：实现检查通过，允许本阶段限定提交；实际 commit/跟踪核验作为 V05 后置条件，成功后才能启动阶段 2。用户验收仍未发生。

产物：[gate-stage-1-manifest.json](../evidence/gate-stage-1-manifest.json)。主会话逐项核对独立 review 指纹与当前文件完全一致，包含未跟踪脚本和测试。独立审查：[stage-1.md](../reviews/stage-1.md)，无未解决阻塞。

| V | 主会话验证与实际结果 |
|---|---|
| V01 | 真实隔离 Git fixture：明确 --only 提交 feature.txt 与新增 docs PLAN，user.txt 原 cached diff 字节不变；失败 pre-commit hook exit 1，HEAD不变、原staged保留。日志 .work/portable-stage-upgrade/commit-protocol.json。无Git/无变化/用户禁提交/归属冲突规则静态复核通过。 |
| V02 | 读取入口、协议与变更模板；rg旧目录结果仅兼容迁移说明，持久目录docs，原始日志/基线.work，摘要和manifest跟踪。实际脚本 --project longdev-plugin --check 返回 no_legacy_records、git true、exit 0，无迁移写入。 |
| V03,V04 | 子仓库 python3 -B -m unittest discover -s tests -v：24/24、零skip、exit 0；日志 .work/portable-stage-upgrade/gate-tests.log。真实迁移/失败/只读/跨机器fixtures及三客户端完整bundle路径均覆盖。plugin-creator validate_plugin.py exit 0，双manifest版本一致。 |
| V05 | 父/子 git diff --check exit 0；初始全部干净，目前仅任务授权范围。待按明确文件列表提交并核对 git show、status、git ls-files；消息 trailer定位本阶段commit，避免自身SHA循环。 |

父仓库补充回归：.work/keyboard/venv/bin/python -B -m unittest discover -s tests -v，共66项，16个errors全部为缺少powershell/powershell.exe，1 skip；日志父 .work/longdev-upgrade-parent-tests-final.log。受影响路由/插件升级测试通过；不宣称父全量通过。Python compose与生成规则字节一致。最初系统Python另缺tomlkit，改用已有项目venv后该依赖错误消除。

限制：Windows真实锁/junction、真实新模型会话长期执行未验证；不影响本机已运行的迁移、安装bundle及协议检查结论。阶段2实际原生安装尚未执行。
