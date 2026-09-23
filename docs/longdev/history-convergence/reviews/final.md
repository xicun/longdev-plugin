# 整体独立审查：历史目录收敛

日期：2026-09-23。审查者未参与实现、阶段安装或发布；本报告不代行用户验收。

**结论：整体检查通过。** R01–R08、V01–V09 均有当前产物、阶段 review/gate 和可核查证据。Windows 真机行为与新会话长期遵循未验证，保留为限制；父仓库既有 resume 过滤提交不计入本任务成果。

## 基线、提交与范围

- 任务起点为子仓库 `0c48589`、父仓库 `3b68951`，任务记录声明父/子起点干净；`.work/longdev/history-convergence/baselines/task-start.json` 是原始基线指针。阶段提交已核对 trailer：阶段 1 为 `720ed5454a9d76a9f208e37c3f4bf10791f509e3`（`Longdev-Task: history-convergence` / `Longdev-Stage: 1`），阶段 2 为 `1154a6697a8a90c432d460706b8b51b7e4c302f9`（Stage 2）。子仓库当前工作区干净。
- 阶段 1 提交包含迁移收敛脚本、统一路径 guard、协议/角色/文档、测试和任务入口；阶段 2 只新增阶段 2 review/gate 与状态记录。未发现阶段提交混入 `.work` 原始日志。Gitee `main` 与 v0.14.0 远端 SHA 已由主会话记录为 `1154a6697a8a90c432d460706b8b51b7e4c302f9`。
- 父仓库当前改动限本轮 INSTALL/PLAN/子模块指针范围；父既有 `3b68951` resume 过滤提交未被重新归属、未作为本轮发布。父仓库未获本轮 push 授权，不能以子模块远端发布替代父同步。

## R/V 覆盖

| 需求 / 验收 | 独立核对与结果 |
|---|---|
| R01 / V01 | `history_convergence.py` 与 36 项行为测试覆盖 `.claude`、前导空格根、`.longdev`，客户端配置、skills、`.longdev-runtime`、兄弟未知内容均保留报告；仅当前工作区被扫描。通过。 |
| R02 / V02 | 阶段 review 独立核对活动/待检查/待验收迁移，终态必须有正向 review/gate 且无依赖、引用和证据缺口；活动引用的结束记录保持在迁移闭包内，不能只凭“已完成”归档。通过。 |
| R03 / V03 | 同内容副本 hash 去重，异内容冲突不覆盖；index blob 与持久目标一致后才归档，unknown 文件/目录和未跟踪、忽略、冲突来源保留。归档分为 Git 可携带 `docs/.../archive` 与 `.work` 原始保护副本，未粗暴 rename。通过。 |
| R04 / V04 | 原始日志/基线留 `.work`；可携带的必需证据写入 docs 并重写引用。任务外 `.work`、缺失或不支持格式证据进入 retain/manual review，避免跨机器悬空。通过。 |
| R05 / V05 | v0.13 marker 后不再短路：正常 docs 演进保留，旧源新增/变更报告 fork；重复、中断、锁、源集合变化、symlink/reparse、unsafe path、只读 status 均有测试。通过。 |
| R06 / V06 | `task_path.py` 集中解析绝对 `TASK_DIR` 并提供写前 guard；SKILL、协议及角色正文传递该值，拒绝旧根、前导空格、相对/越界/重定向路径。通过。 |
| R07 / V07 | 双 manifest 为 `0.14.0+codex.20260923183000`，bundle 含四个相关脚本，安装/迁移回归与 `git diff --check` 证据有效；两个阶段提交范围与 trailer 已核对。通过。 |
| R07 / V08 | 原生插件安装启用，缓存与源码 SHA 一致，缓存脚本真实执行迁移、dry-run 与 guard fixture，Gitee 发布 SHA 已核实；父仓库未 push。通过，PATH alias 权限警告已保留。 |
| R08 / V09 | dry-run 与 apply 共享计划构建；独立 fixture 证明输出包含来源、分类、动作、目标、冲突和 tracking 前提，且不改目录、字节、mtime、index、lock、journal、marker。通过。 |

## 接缝、残留与验证

- 接缝路径完整：候选盘点 → 保守分类/引用闭包 → docs 与 `.work` 分流 → index blob 跟踪核验 → 逐项归档 → marker 后分叉检测 → 绝对 TASK_DIR guard → bundle/缓存安装。dry-run 预览和实际迁移使用同一计划，避免预览与执行漂移。
- 未发现实现阻塞或未收口的未知内容被误删。未知来源、矛盾状态、外部证据和冲突均保留并报告；保留报告不被错误标为收敛完成。
- 独立重新执行 `python3 -B -m unittest discover -s tests -v`：36 项通过、0 skip、exit 0；原始输出保存在 `.work/longdev/history-convergence/final/tests.log`。`git diff --check` 通过。该测试覆盖阶段报告所列行为，未把 exit 0 扩大解释为 Windows 或长期会话验证。
- 子仓库安装缓存路径与版本、插件启用状态和 fixture 结果见阶段 2 review/gate；阶段 2同时记录 PATH alias 权限警告。Windows junction/reparse/锁、新会话长期运行及父仓库完整测试环境仍未验证。
- 阶段 1/2 当前 PLAN 状态仍由主会话最终 gate 收口；本报告自身应在最终 gate 后按限定路径提交，不能预先引用自身 SHA。整体通过不等于用户已验收。
