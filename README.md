# longdev

长程开发编排 plugin，两种驾驶方式：

- **手动挡 `longdev`**——单个边界明确的大任务，立项确认一次，逐阶段推进；
- **自动挡 `autopilot`**——给一个产品目标，问卷式宪章确认一次，之后自主迭代到收官，无人值守。

## longdev（手动挡）

把跨会话的大任务（新功能、重构、迁移）拆成阶段，主会话只做编排和决策——调研派 `longdev-scout`（sonnet），拆解派 `longdev-planner`（继承会话模型，写 PLAN.draft.md 给用户确认），每阶段实现派干净 context 的 `longdev-implementer`（继承会话模型），审查派 `longdev-reviewer`（sonnet），reviewer 揪出的方案级分叉交 `longdev-decider`（opus）在计划目标范围内代你拍板、越界的才升级给你，全部阶段完成后派 `longdev-final-reviewer`（继承会话模型）做收尾全盘审查，状态落盘在项目内 `.claude/longdev/<任务名>/`：`PLAN.md` 是索引（≤120 行，每个 agent 都读），`stages/<N>.md` 是每阶段的入口和完成记录，另有 `notes/`（跨阶段契约）、`scout/`、`reviews/`、`decisions/`（代理决策备案）。每阶段收尾主会话**亲自跑一组 gate 命令**（真实退出码、真实 diff 尺寸、测试新增行里的 skip 痕迹、证据块存在性），不靠 subagent 转述——只有主会话自己的工具输出是不经转述、你直接看得见的。从立项到收尾主会话只沉淀摘要，不积压 context，不需要 `/clear`。

## autopilot（自动挡）

autopilot 骑在 longdev 上面：上层是「宪章 → backlog → 迭代 → 验收 → 停机判定」的循环，执行层每轮迭代就是一个标准 longdev 任务（gate 纪律一条不松）。立宪是**唯一必经的人工环节**，且做成了引导式问卷——`longdev-product-owner`（继承会话模型）调研主流形态后起草宪章草稿并出选择题（目标用户/形态/功能范围/质量档位/迭代预算/授权边界），推荐项排第一、全选推荐也能开工，最后确认一次草稿全文即冻结为 `CHARTER.md`。此后所有「问用户」都变成「问宪章」：backlog 每条功能必须引用宪章条款编号（引不出的不入表，防功能爆炸），`longdev-acceptance`（继承会话模型）代行用户的眼睛——立项时按宪章核计划、收尾时真实运行产品逐条验收；decider 判不了的可逆分叉选最小方案备案待复核，不可逆的一律隔离。功能修复两轮仍阻塞就回滚到快照进隔离名单，永不静默重试；同一功能二次隔离或单轮隔离过半触发熔断停机等人。宪章验收清单全绿、迭代到上限、或候选全部低于阈值即自动收官，收官报告可十分钟复核全部代拍。产品层状态落盘 `.claude/autopilot/<产品名>/`，每轮只在主会话沉淀 5 行，随时 `/clear` 续接零成本。

## 安装（每台设备一次）

```
/plugin marketplace add xicun/longdev-plugin
/plugin install longdev@zzm-plugins
```

安装后 skill 调用名为 `longdev:longdev`（或直接说"长程开发/接着上次继续"触发）和 `longdev:autopilot`（或说"自动挡/自主迭代/无人值守把这个产品做出来"触发）。

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
skills/longdev/                 # 手动挡：SKILL.md + references/{plan-template,stage-template,show-file}.md
skills/autopilot/               # 自动挡：SKILL.md + references/{charter-template,charter-interview,backlog-template,iteration-template}.md
agents/                         # scout / planner / implementer / reviewer / decider / final-reviewer / product-owner / acceptance 八个 subagent
```
