# longdev

长程开发编排 plugin：把跨会话的大任务（新功能、重构、迁移）拆成阶段，主会话只做编排和决策——调研派 `longdev-scout`（sonnet），拆解派 `longdev-planner`（继承会话模型，写 PLAN.draft.md 给用户确认），每阶段实现派干净 context 的 `longdev-implementer`（继承会话模型），审查派 `longdev-reviewer`（sonnet），全部阶段完成后派 `longdev-final-reviewer`（sonnet）做收尾全盘审查，状态落盘在项目内 `.claude/longdev/<任务名>/`：`PLAN.md` 是索引（≤120 行，每个 agent 都读），`stages/<N>.md` 是每阶段的入口和完成记录，另有 `notes/`（跨阶段契约）、`scout/`、`reviews/`。从立项到收尾主会话只沉淀摘要，不积压 context，不需要 `/clear`。

## 安装（每台设备一次）

```
/plugin marketplace add xicun/longdev-plugin
/plugin install longdev@zzm-plugins
```

安装后 skill 调用名为 `longdev:longdev`（或直接说"长程开发/接着上次继续"触发）。

## 我用的是最新版吗

skill 开工第一句会报 `longdev vX.Y.Z`（运行时读 `.claude-plugin/plugin.json` 的 `version`）。和本仓库 CHANGELOG.md 顶部的版本比对；落后就 `/plugin update longdev@zzm-plugins`。本机已安装的版本也可以看 `~/.claude/plugins/cache/zzm-plugins/longdev/` 下的目录名。

## 更新

发布者：改代码 → 更新 CHANGELOG.md → bump `.claude-plugin/plugin.json` 的 `version`（唯一一处版本号）→ commit + `git tag vX.Y.Z` → push。**不改 version 只推代码不会触发任何设备更新。**

其他设备：`/plugin update longdev@zzm-plugins`；或在 `/plugin` 界面 → Marketplaces 中对 zzm-plugins 开启 auto-update。

锁定/回滚：在 marketplace.json 的 source 里加 `"ref": "<tag或分支>"` 或 `"sha": "<commit>"`。

## 结构

```
.claude-plugin/plugin.json      # 清单，version 是发版开关
.claude-plugin/marketplace.json # 本仓库同时作为 marketplace（zzm-plugins）
skills/longdev/                 # SKILL.md + references/{plan-template,stage-template,show-file}.md
agents/                         # scout / planner / implementer / reviewer / final-reviewer 五个 subagent
```
