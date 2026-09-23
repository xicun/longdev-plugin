# 阶段 1 独立审查：历史目录收敛

日期：2026-09-23。人工式独立检查，未调用 code-review；审查者未参与实现，也未修改业务代码或子模块。

**结论：独立审查通过。** 当前实现覆盖 R01–R08、V01–V07 与 V09；V08 属阶段 2，未在本报告宣称通过。主会话仍需执行 gate 和限定提交，不能把本报告当作用户验收。

## 独立验证

在子仓库根执行：`python3 -B -m unittest discover -s tests -v`，真实退出码 0，36 项通过，0 skip。完整 stdout/stderr：`.work/longdev/history-convergence/reviewer/final-tests-2.log`。测试覆盖候选识别、未知客户端资产、保守状态和引用闭包、同/异内容冲突、index tracking、归档中断/锁/路径、v0.13 marker 演进与分叉、dry-run、外部本地证据、guard 及安装打包回归。

我另建 Git fixture 验证：

- `converge(..., dry_run=True)` 返回 `awaiting_tracking/dry_run`，目录内容、文件字节、mtime 和 `git status` 前后完全一致；没有创建 lock、journal 或 marker。
- 旧任务 PLAN 指向存在但位于任务外的 `.work/shared/run.log` 时，当前计划将任务标为 `retain`，明确记录 `external:.work/shared/run.log`，避免跨机器后产生悬空必需证据。证据摘要：`.work/longdev/history-convergence/reviewer/external-local-evidence.json`（此前发现的缺口已修复，复查输出保存在终端日志和测试日志中）。
- `task_path.py resolve/check` 实际执行：规范 `docs/longdev/x` 和对应 `.work/longdev/x` 放行；旧 `.claude`、相对越界及含 `..` 的非规范绝对路径拒绝。

## 需求覆盖审查

| R / V | 独立判断 |
|---|---|
| R01 / V01 | `inventory/classify` 只识别 `.claude`、前导空格根和 `.longdev` 的任务候选；客户端配置、skills、runtime、兄弟未知内容保留并报告。未知扩展/来源不默认搬运。 |
| R02 / V02 | 活动、待检查、待验收保持 docs；终态要求明确正向 final review/gate，否定结论（含 `not passed`/失败/未验证等）不会归档；活动引用、传递依赖和证据缺口使任务保留。 |
| R03 / V03 | 迁移逐文件 hash 校验，同内容去重、异内容冲突保留；只有目标内容可从 Git index blob 核实后才归档旧 entry。归档只删除本次成功归档源的空祖先，未知文件/空目录保留。 |
| R04 / V04 | raw 日志/基线进入 `.work`；被引用且可携带的证据进入 durable portable 路径。任务外 `.work`、缺失相对证据和 unsupported 内容现在进入 retain/manual review；跨机器不可复核时不宣称完成。 |
| R05 / V05 | v0.13 marker 后允许 docs 正常演进，同时检测旧源新建/修改并报告 fork；幂等、锁、中断恢复、source 集合变化、symlink/reparse 和 unsafe path 有行为覆盖。 |
| R06 / V06 | `task_path.py` 是统一解析/写前 guard；SKILL、共享协议与角色正文传递绝对 `TASK_DIR`，guard 拒绝旧根、空白、相对、越界和重定向路径。静态核对所有适用角色未各自拼接新入口。 |
| R07 / V07 | 双 manifest/安装包、脚本和 guard 同步；`git diff --check` 与提交前范围由实现记录/主 gate 继续核对。v0.14.0 版本更新内容已在当前源码。 |
| R08 / V09 | `--dry-run` 输出任务/文件来源、分类、目标、动作、冲突及 tracking 前提，并与 apply 共享 `build_plan`；独立 fixture 证明它不改目录、mtime、字节和 index。 |

## 修复复查与限制

首轮审查发现并反馈的缺陷包括：`not passed` 可误归档、保留任务依赖的归档悬空、目录引用未重写、未知空目录被清理、portable local copy 冲突未预检，以及任务外 `.work` 必需证据未报告。实现者已增加保守正向终态判断、依赖连通分量保护、目录映射、归属明确的空目录清理、dry-run 冲突计划和外部本地证据 retain；36 项复测通过，旧发现证据不再支持当前实现，以上结论以最终测试和复查为准。

未验证项：真实 Windows junction/锁、真实新会话长期运行，以及阶段 2 本机安装/远端发布（V08）。父仓库全量测试环境限制也不影响本阶段子仓库行为结论。下一步由主会话执行 gate，核对持久记录/ignore/index 和限定阶段提交。
