# Regression Checks 整合（longdev 侧）

> 任务：把测试用例能力整合进 longdev，作为**开发测试闭环**。项目级**共享用例库** `testcases/` 由 `longdev-testcases` 角色按 Plan 构建并映射 R/V，`longdev-checker` 角色每阶段/收口用 `checker.py --cases <子集>` 跑回归出证据；harness 父仓库只驱动它，子模块不反向依赖 harness；harness/插件自身 dev cases 留在各自仓库，不进使用方项目。退役 ../test-cases。

## 目标 / 授权

- 用户：① 父驱动子、子对父不可见；② harness+longdev 自身 dev cases 不是使用方项目内容；③ 退役 ../test-cases；④ 用例**项目级全局共享**，任务引用子集；⑤ 每阶段 implementer/checker/reviewer，收口也有 checker；⑥ bug 修复后可晋升 case。
- 范围：longdev-plugin（共享库 runer、两个角色、模板/协议接入、文档版本）；harness 父仓库（自身库 + 驱动说明 + PLAN 索引）。
- 不引入项目专属 case 到通用运行器；不改插件业务执行逻辑；不自动 push/发布（单独授权）。

## 需求与验证

| R | 内容 | 交付物 | V | 状态 |
|---|---|---|---|---|
| R01 | 通用运行器 `checks`（runner+catalog-schema+测试），标准库、不 import 源码、不硬编码父路径 | skills/checks/* | V01 | 待检查 |
| R02 | `--cases <id,...>` 子集运行（任务引用子集） | check_runner.py + tests | V02 | 待检查 |
| R03 | 项目级共享库 `testcases/`（cases/matrix/quality_refs） | 插件 `testcases/` + 父 `testcases/` | V03 | 待检查 |
| R04 | `longdev-testcases` 角色（设计/维护库、bug→case 晋升、映射 R/V） | agents/longdev-testcases.md | V04 | 待检查 |
| R05 | `longdev-checker` 角色（每阶段/收口跑子集出证据） | agents/longdev-checker.md | V05 | 待检查 |
| R06 | 接入 plan/stage 模板、执行协议、longdev SKILL（闭环在 Plan 与每阶段/收口） | 模板+协议+SKILL | V06 | 待检查 |
| R07 | 版本 0.16.0 + CHANGELOG + 两份 plugin.json 同步 | 版本文件 | V07 | 待检查 |

- 追加（0.17.0）：跨 worktree 写租约 `skills/longdev/scripts/write_lease.py`（锁在 Git common dir，串行写共享状态不吞冲突），已接入 checks/协议/`longdev-testcases` 角色，并含测试 `tests/test_write_lease.py`。## 验证证据（已实测，待独立 review/最终 gate）

- 插件单测 `tests/test_check_runner.py` 5/5（含 `--cases` 子集与未知 id 拒绝），exit 0。
- 插件共享库独立运行 `.work/checks/plugin-smoke` exit 0；父 `testcases/` 经插件 runner 跑 `full`（`--cases` 或 profile）`harness-full` exit 0，`harness-unit-tests-full` 与 `plugin-regression` 通过。
- 父/子 `catalog/` 已迁移为 `testcases/`；`../test-cases` 已退役并删除。

## 待办

- 独立 review：已完成，插件核心通过（`.work/regression-checks-review/review.md`）；P1 父侧驱动命令已补 `--profile/--output`（修正后 exit 0），P2 属任务 1（循环收敛规则）同属授权范围，P3 为历史档案残留引用、按保留历史不改写。
- 最终 gate（主会话）待执行。
- 父仓库侧：`AGENTS.md`/`README`/`PLAN` 驱动说明已更新；提交/push 按授权。