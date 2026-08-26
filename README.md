# longdev

长程开发编排 plugin：把跨会话的大任务（新功能、重构、迁移）拆成阶段，主会话只做编排和决策——调研派 `longdev-scout`（sonnet），每阶段实现派干净 context 的 `longdev-implementer`（继承会话模型），审查派 `longdev-reviewer`（sonnet），全部阶段完成后派 `longdev-final-reviewer`（sonnet）做收尾全盘审查，状态落盘在项目内 `.claude/longdev/`（PLAN.md + scout/ + reviews/）。默认一口气推完全部阶段，不积压 context，也不需要逐阶段 `/clear`。

## 安装（每台设备一次）

```
/plugin marketplace add xicun/longdev-plugin
/plugin install longdev@zzm-plugins
```

安装后 skill 调用名为 `longdev:longdev`（或直接说"长程开发/接着上次继续"触发）。

## 更新

发布者：改代码 → 更新 CHANGELOG.md → bump `.claude-plugin/plugin.json` 的 `version` → commit + `git tag vX.Y.Z` → push。**不改 version 只推代码不会触发任何设备更新。**

其他设备：`/plugin update longdev@zzm-plugins`；或在 `/plugin` 界面 → Marketplaces 中对 zzm-plugins 开启 auto-update。

锁定/回滚：在 marketplace.json 的 source 里加 `"ref": "<tag或分支>"` 或 `"sha": "<commit>"`。

## 结构

```
.claude-plugin/plugin.json      # 清单，version 是发版开关
.claude-plugin/marketplace.json # 本仓库同时作为 marketplace（zzm-plugins）
skills/longdev/                 # SKILL.md + references/plan-template.md
agents/                         # scout / implementer / reviewer / final-reviewer 四个 subagent
```
