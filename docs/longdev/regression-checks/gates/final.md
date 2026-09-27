# 最终 gate：regression-checks 整合

> 主会话执行。结论：**通过**。独立 review（`.work/regression-checks-review/review.md`）无插件侧阻塞；P1 父侧驱动命令已补并实测 exit 0，P2 属任务 1（循环收敛规则）、P3 历史档案残留按保留历史不改写。

## V 全集与证据

| V | R | 方法/命令 | 期望 | 实际/退出码 | 结论 |
|---|---|---|---|---|---|
| V01 | R01 | `--validate` 两库；`tests.test_check_runner` 5/5；grep `D:\Works\harness`/`harness/` 无硬编码 | 通过 | 两库 validate exit 0；单测 5/5；无硬编码 | 通过 |
| V02 | R02 | `--cases harness-unit-tests` 端到端；未知 id 拒绝 | 子集运行 exit 0；未知 id exit 2 | 子集 exit 0；`--cases does-not-exist` exit 2 | 通过 |
| V03 | R03 | 父/子 `testcases/` validate | 通过 | 两库 validate exit 0 | 通过 |
| V04 | R04 | `agents/longdev-testcases.md` | 角色存在、独立、映射 R/V、bug→case 门槛 | 已建并与协议一致；independent review 通过 | 通过 |
| V05 | R05 | `agents/longdev-checker.md` | 角色存在、独立执行、收口全量 | 已建；与 reviewer 职责分开；review 通过 | 通过 |
| V06 | R06 | plan/stage 模板、execution-protocol、longdev SKILL 已接入 | 闭环在 Plan 与每阶段/收口 | 模板/协议/SKILL 均含闭环段；review 通过 | 通过 |
| V07 | R07 | `.codex/.claude plugin.json` version == CHANGELOG 0.16.0 | 三处一致 | 0.16.0+codex.20260926224637 | 通过 |

## 独立验证结果（reviewer & 主会话）

- 父 `--profile full`：`harness-unit-tests-full`、`plugin-regression` 均 passed，exit 0。
- 插件 `--profile smoke` exit 0；父文档命令（P1 修复后）`--profile smoke --output .work/checks/smoke` exit 0。
- `--cases harness-unit-tests` exit 0；未知 id exit 2。
- 父子 `git diff --check` 干净。

## 结论

必需 V 全集均有当前有效证据；独立 review 通过；实际产物与代码一致。**主会话最终 gate 通过**。任务置待验收（不代用户验收）。下一动作：按共享协议限定提交子模块，父仓库只更新子模块指针并提交。