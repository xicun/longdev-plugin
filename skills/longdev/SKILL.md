---
name: longdev
description: 长程开发编排。把跨多个会话的大任务（新功能、重构、迁移）拆成阶段，主会话只做编排和决策：调研派 scout，拆解派 planner，每阶段实现派干净 context 的 implementer，审查派 reviewer，全部完成后派 final-reviewer 收尾全盘审查，状态落盘在 PLAN.md。主会话只沉淀摘要，可一口气跑完所有阶段，不需要 /clear。当用户要开始或继续一个大型开发任务，或提到"长程开发""分阶段做""接着上次继续"时使用。
---

# longdev v0.4.0

**开工第一句话报版本**：`longdev v0.4.0`。用户据此判断是否已更新（最新版见 GitHub `xicun/longdev-plugin` 的 CHANGELOG 顶部；不一致就 `/plugin update longdev@zzm-plugins`）。

原则：**状态落盘，重活全在 subagent 里**。调研、拆解、实现、审查都由干净 context 的 subagent 完成，交接物是文件，主会话只收每次几十行的摘要。

## 落盘目录 `.claude/longdev/`

| 路径 | 写入者 | 内容 |
|---|---|---|
| `PLAN.md` | planner 草稿转正；每阶段 implementer 更新 | 唯一的跨阶段/跨会话状态载体，implementer 的唯一输入。写给"没有任何 context 的人"看 |
| `PLAN.draft.md` | planner | 立项草稿，用户确认后改名为 PLAN.md |
| `scout/<主题>.md` | scout / planner | 调研完整报告；PLAN.md「调研结论」只写结论并指向这里 |
| `reviews/stage-<N>.md` | reviewer | 每阶段审查完整报告；修复轮只传路径 |
| `reviews/final.md` | final-reviewer | 收尾全盘审查报告 |

主会话**不读这些文件的全文**。要给用户看，按 `references/show-file.md` 探测客户端后打开文件；要改，发回给写它的 subagent。

## 派活

Agent tool，`subagent_type` 填 `longdev-scout` / `longdev-planner` / `longdev-implementer` / `longdev-reviewer` / `longdev-final-reviewer`。互不依赖的调研放同一条消息并发派出。**不用 `Plan` / `Explore` / `general-purpose` 等通用 agent**——它们没有输出长度约束。

## 第一步：判定状态

`ls .claude/longdev/` + `grep -n "^## \|^- \[.\] \|^\*\*状态" .claude/longdev/PLAN.md`，不 cat 全文：

- 无 PLAN.md 也无 PLAN.draft.md → A 立项
- 只有 PLAN.draft.md → 上次立项没确认完，从 A.3 起；有修改意见时派新 planner，说明"修改已有草稿"
- 有 PLAN.md 且用户带了新目标 → 问清是新开还是继续，不擅自覆盖
- 有 PLAN.md → B 续接
- 用户传 `status` → 只 grep 阶段清单汇报进度，结束

## A. 立项

0. planner 继承主会话模型。当前不是最强模型（Fable 5）的话提醒一句可 `/clear` 后 `claude --model fable` 重开做立项；说完继续，不等确认。
1. **派 scout**：按子系统拆几个互不依赖的主题并发派出。prompt 给项目根目录、要查什么、输出路径 `.claude/longdev/scout/<主题>.md`。它写文件，回 ≤15 行。**不进 plan mode，不自己读文件。**
2. **派 planner**：prompt 给项目根目录、用户目标描述原话、scout 文件清单、模板绝对路径（本 skill 目录 `references/plan-template.md`）、草稿路径 `.claude/longdev/PLAN.draft.md`。它写草稿，回 ≤30 行：路径、阶段清单、关键决策、**待用户拍板**、风险。
3. **展示草稿**：按 `references/show-file.md` 打开文件，回显 planner 摘要，重点列「待用户拍板」及推荐。等用户表态。这是**唯一必经的 HIL 点**。
4. **有修改意见** → 用户原话 `SendMessage` 给同一个 planner，它改草稿回本轮变更；回到 3。主会话不自己动草稿。
5. **确认** → `mv .claude/longdev/PLAN.draft.md .claude/longdev/PLAN.md`，一句话告知，进入 C。不需要 `/clear`。

## B. 续接

1. `grep` 阶段清单找第一个未完成阶段；`sed -n` 只读「下一阶段入口」一节。
2. 不重新探索。入口信息明显不足才派 scout 补一次（落文件回摘要），结论追加回 PLAN.md。
3. 一句话汇报"上次做到 X，本次从阶段 N 继续：<目标>"，进入 C。

## C. 推进阶段

阶段串行；除非计划明确标注两阶段完全不相交且各用 `isolation: "worktree"`。

1. **派 implementer**：prompt 只给项目根目录、PLAN.md 路径、阶段号。不复述计划。它实现、补测试、跑验证、更新 PLAN.md。
2. **先看回传的「遗留/上报」**：有方案级问题就问用户，决策写进 PLAN.md，`SendMessage` 让同一个 implementer 继续。
3. **派 reviewer**：prompt 给项目根目录、阶段号、报告路径 `.claude/longdev/reviews/stage-<N>.md`。它核对 diff 与 PLAN.md 目标/决策/测试要求的一致性，并调 `/code-review`；报告写文件，回 ≤10 行。主会话不重跑 review，不读报告。
4. **有阻塞** → `SendMessage` 给同一个 implementer："读 `reviews/stage-<N>.md`，修阻塞问题，重跑验证"，不粘清单。修完 `SendMessage` 让同一个 reviewer 复查。两轮仍阻塞就停下汇报。
5. **抽查**：只跑 `grep -n "^- \[.\] " .claude/longdev/PLAN.md` 确认勾选和当前标记。内容属实性 reviewer 已核。
6. 简短汇报本阶段（做了什么、验证输出、review 结论），直接进入下一阶段。
7. **全部完成 → 派 final-reviewer**：prompt 给项目根目录、报告路径 `.claude/longdev/reviews/final.md`。它按基线 commit 算全量 diff，查总目标端到端达成、跨阶段接缝、决策漂移、跨阶段残留，全量跑测试；不重跑全量 `/code-review`。
8. **收尾有阻塞** → 派新 implementer 做「收尾修复轮」（prompt 给项目根目录、PLAN.md 路径、报告路径，说明是收尾修复不是某阶段），修完 `SendMessage` 同一个 final-reviewer 复查。最多两轮。
9. 通过 → `sed` 在 PLAN.md 标题下加 `**状态：已完成**`，按 `references/show-file.md` 展示 `reviews/final.md`，做总结（含收尾结论和全量测试结果）。

## D. 主会话亲自执行（例外）

仅用于标了**【主会话】**的阶段或用户明确要求参与实现时。实现 + 验证后照常派 reviewer、更新 PLAN.md。因为实现细节进了主会话，收尾时**提示用户 `/clear` 后 `/longdev` 续接**——这是全流程唯一需要 `/clear` 的场景。

## 模型分层

- **planner**：继承主会话 → 立项在 Fable 5 会话里做。
- **implementer**：默认继承；机械阶段可传 `model: "sonnet"`，核心阶段传 `"opus"` 或由 Fable 会话派。
- **scout / reviewer / final-reviewer**：agent 定义里固定 `sonnet`，不覆盖。

## 硬规矩

- PLAN.md 里绝不写"见上文"——每个读者都没有你的 context。
- 主会话不读源码，不 `cat`/`head` PLAN.md、草稿或任何报告全文。
- 主会话不复述 subagent 产出：修复轮传路径，汇报只写结论。
- 调研只派 scout，拆解只派 planner，不进 plan mode。
- 不合并阶段，不跳过逐阶段 review 或收尾审查。
- 新增行为不带测试的阶段不算完成，除非 PLAN.md 决策明确该项目不引入测试。
- 验证失败如实报输出，不说"基本通过"。
- 用户只是提问或讨论时，不动代码。
