---
name: longdev
description: 长程开发编排。把一个跨越多个会话的大任务（新功能、重构、迁移）拆成阶段，主会话只做编排和决策：调研派给 scout，每个阶段的实现派给干净 context 的 implementer，审查派给 reviewer，全部完成后派 final-reviewer 做收尾全盘审查，状态落盘在 PLAN.md。默认可以一口气跑完所有阶段而不积压 context，也不需要用户逐阶段 /clear。当用户要开始或继续一个大型开发任务，或提到"长程开发""分阶段做""接着上次继续"时使用。
---

# 长程开发编排

核心约束是 **context 是有限资源**。解法不是让用户逐阶段 `/clear`，而是：**状态落盘，实现发生在 subagent 里**。每个阶段由一个干净 context 的 `longdev-implementer` 执行——这和"用户 /clear 后重开会话"语义等价（交接物都是 PLAN.md），但不需要人工介入，且 subagent 的读写噪音永远不进主会话。主会话是编排者，每个阶段只沉淀几十行摘要，因此可以连续推完全部阶段。

## 落盘目录

全部状态放在项目内 `.claude/longdev/`：

| 路径 | 写入者 | 内容 |
|---|---|---|
| `PLAN.md` | 立项时主会话；之后每阶段 implementer 更新 | 唯一的跨阶段、跨会话状态载体，也是每个 implementer 的唯一输入契约——必须写给"没有任何 context 的人"看 |
| `scout/<主题>.md` | scout | 调研的完整报告；PLAN.md「调研结论」只写结论并指向这些文件 |
| `reviews/stage-<N>.md` | reviewer | 每阶段审查的完整报告；修复轮只传路径 |
| `reviews/final.md` | final-reviewer | 收尾全盘审查报告 |

**主会话不读这些文件的全文**——它们是 subagent 之间的交接物。主会话只看 subagent 的回传摘要（≤30 行）。

## context 预算：主会话的 token 花在哪

实测一个 5 阶段任务的主会话，各阶段 implementer + reviewer 的回传合计只占不到 20%；其余 80% 来自三处，本流程针对它们做了约束：

1. **立项阶段**（占大头）：多个调研 agent 各自回传上万字、plan mode 的方案文本、以及主会话亲手把几十 KB 的 PLAN.md 写进去——这些内容对后续任何阶段都零价值，却一直留在 context 里。→ 调研只派 `longdev-scout`（完整报告落文件，回传摘要），立项完成后建议 `/clear` 再续接（见 A.7）。
2. **主会话自己读文件**：`cat`/`head` PLAN.md、`grep`/`sed` 源码"确认一下"。→ 硬规矩：主会话不读源码，PLAN.md 只 `grep` 阶段清单。
3. **修复轮复述**：把 reviewer 的问题清单原文粘进 `SendMessage`。→ 只传报告路径。

派活用 Agent tool，`subagent_type` 填 `longdev-scout` / `longdev-implementer` / `longdev-reviewer` / `longdev-final-reviewer`（随本 plugin 的 `agents/` 目录一起分发）。**不要用 `Plan` / `Explore` / `general-purpose` 等通用 agent 做调研**——它们没有输出长度约束，一次回传就能吃掉主会话几万 token。多个互不依赖的调研放在同一条消息里并发派出。

## 第一步：判定当前处于什么状态

读 `.claude/longdev/PLAN.md`（用 `grep -n "^## \|^- \[.\] \|^\*\*状态"` 看结构，不要 cat 全文）：

- **文件不存在** → 走「立项」流程（下方 A）
- **文件存在，且用户带了新目标描述** → 问清是新开任务还是继续旧的，不要擅自覆盖已有计划
- **文件存在** → 走「续接」流程（下方 B）
- **用户传了 `status`** → 只读阶段清单并汇报进度，不做任何改动，结束

## A. 立项流程（首次）

0. **先看一眼当前会话用的是哪个模型。** 拆解阶段的质量决定后面所有阶段的走向，而 plan mode 不会自动升级模型——用的就是当前会话的模型。如果当前不是可用的最强模型（Fable 5），提醒用户一句：可以 `/clear` 后用 `claude --model fable` 重开一个会话专门做立项，拆完的结果会落进 PLAN.md，执行阶段的模型另算（见「模型分层」）。说完就继续，不要卡在这里等确认——用户不接受就照当前模型往下做。

1. **进 plan mode 拆解**（`EnterPlanMode`）。在方案定型前不要写任何代码。
2. **需要摸清代码库时，派 `longdev-scout` subagent 去调研**，不要自己在主会话里逐个读文件。可以并发派多个 scout 分头查不同子系统。prompt 里给它输出文件路径 `.claude/longdev/scout/<主题>.md`——它把完整报告写进去，只回传 ≤15 行摘要。主会话据摘要决定方案；需要细节时下一个 scout 或 implementer 自己去读那个文件。
3. 把任务拆成 **3-7 个阶段**。每个阶段必须满足：
   - 一个干净 context 的 implementer 拿着 PLAN.md 就能独立完成（这是比"一次会话能做完"更严的标准：入口信息必须写全）
   - 有可验证的完成标准，**优先写成可自动运行的测试**（"运行 X 看到 Y 通过"），只在确实无法自动化时才写观察行为
   - 与其他阶段的依赖关系明确
   - 少数确实需要用户现场做决策的阶段（如 API 设计定稿），在阶段名后标 **【主会话】**，走 D 流程
4. **定下测试约定**，写进 PLAN.md「验证方式」：项目现有测试框架/目录/命名/运行命令是什么；新增行为的阶段必须随实现补单元测试。项目没有测试基础设施的，"要不要引入"是方案级决策——在 plan mode 里和用户定，写进「已做出的决策」，不要留给 implementer 顺手拍板。
5. 用 `ExitPlanMode` 让用户确认方案。这是默认流程里**唯一必经的 HIL 点**——确认后整个任务可以自动推到底。用户想逐阶段过目的话，尊重，每阶段收尾多停一步。plan mode 的方案文本只写阶段清单、决策、测试约定——调研细节已经在 scout 文件里，不要再抄一遍。
6. 确认后，按 `references/plan-template.md` 的结构创建 `.claude/longdev/PLAN.md`，填入目标、**基线 commit**（`git rev-parse HEAD`，收尾审查算全量 diff 要用）、阶段清单、scout 结论（指向 scout 文件）、测试约定、第 1 阶段的入口。
7. **建议在这里 `/clear`。** 立项过程中积累的调研回传、方案讨论、PLAN.md 全文写入，对执行阶段没有任何用处，却是主会话 context 的最大单项。PLAN.md 已经是完整交接物，`/clear` 后 `/longdev` 会走 B 流程无缝续接。向用户说明这一点并停下；用户不愿意就直接进入 C。

## B. 续接流程（后续会话）

1. `grep` PLAN.md 的阶段清单，找到第一个未完成的阶段；用 `sed -n` 只读「下一阶段入口」一节。
2. **不要重新全库探索**——上次的调研结论已经在文件里了。主会话甚至不需要读关键文件本身，那是 implementer 的事。
3. 如果下一阶段入口信息明显不足，派 `longdev-scout` 补一次针对性调研（同样落文件、回摘要），把结论追加回 PLAN.md。
4. 向用户一句话汇报："上次做到 X，本次从阶段 N 继续：<阶段目标>"，然后进入 C。

## C. 推进阶段（默认：编排模式）

对每个未完成阶段，依次执行以下循环。**阶段之间串行**，不要因为下一阶段"看起来独立"就并行——除非计划里明确标注两个阶段完全不相交，且各自用 `isolation: "worktree"`。

1. **派 `longdev-implementer` 执行本阶段。** prompt 只需要给：项目根目录、PLAN.md 路径、阶段号。不要复述计划内容——它自己读 PLAN.md，复述反而会引入和落盘状态不一致的二手信息。implementer 会实现、补测试、跑验证、并把决策/坑/下一阶段入口更新进 PLAN.md。
2. **收到回传后先看「遗留/上报」**。有方案级问题上报的，停下来问用户，拿到决策后写进 PLAN.md，再用 `SendMessage` 让同一个 implementer 继续（它的 context 还在，不要重开）。
3. **派 `longdev-reviewer` 独立审查。** prompt 给：项目根目录、阶段号、报告路径 `.claude/longdev/reviews/stage-<N>.md`。它在干净 context 里做两个维度：自己核对 diff 与 PLAN.md 阶段目标/决策/测试要求的一致性，并调用 `/code-review` skill 做代码正确性审查；完整报告写进文件，只回传结论 + 阻塞问题条数。主会话不要替它再跑一遍 review，也不要读报告全文。
4. **有阻塞问题** → 用 `SendMessage` 给同一个 implementer 一句话："读 `.claude/longdev/reviews/stage-<N>.md`，修阻塞问题，修完重跑验证"，**不要把问题清单粘过去**。修完再让 reviewer 复查（也用 `SendMessage` 续同一个 reviewer，它追加到同一份报告）。两轮修复后仍有阻塞，停下来向用户汇报，不要无限循环。
5. **主会话抽查勾选状态**：只跑 `grep -n "^- \[.\] " .claude/longdev/PLAN.md` 确认本阶段勾掉、当前标记移到下一阶段。PLAN.md 内容是否属实、入口是否够用，reviewer 的维度一已经核过了，不要再 cat 全文自己看一遍。
6. 向用户简短汇报本阶段结果（做了什么、验证输出、review 结论），然后**直接进入下一阶段**——不需要 `/clear`，主会话每阶段只积累这几段摘要。
7. **全部阶段完成后，派 `longdev-final-reviewer` 做收尾全盘审查。** prompt 给：项目根目录、报告路径 `.claude/longdev/reviews/final.md`。它拿 PLAN.md 里的基线 commit 算整个任务的 diff，查逐阶段 review 结构上抓不到的东西：总目标是否端到端达成、跨阶段接缝、决策漂移（后期改了决策但早期代码没回头改）、跨阶段残留（脚手架/shim/TODO），并全量跑一遍测试。**它不重跑全量 `/code-review`**——那是逐阶段已经做过的事。
8. 收尾审查有阻塞问题 → 派一个新的 `longdev-implementer` 做「收尾修复轮」：prompt 给项目根目录、PLAN.md 路径、报告路径，说明这是收尾修复不是某个阶段；修完 `SendMessage` 让同一个 final-reviewer 复查。同样最多两轮。
9. 通过后，在 PLAN.md 标题下加 `**状态：已完成**`，向用户做总结报告（含收尾审查结论和全量测试结果）。

## D. 主会话亲自执行（例外）

仅用于计划里标了**【主会话】**的阶段，或用户明确要求参与实现的场合：

1. 主会话实现 + 验证，大范围调研仍派 scout、批量机械修改仍派并发 subagent。
2. 完成后照常派 `longdev-reviewer`，照常更新 PLAN.md。
3. 因为实现细节进了主会话 context，本阶段收尾时**提示用户 `/clear` 后重新 `/longdev` 继续**——这是旧流程保留下来的场景之一（另一个是 A.7）。剩余阶段若都是编排模式，续接后就能一路推完。

## 模型分层

阶段之间可以换模型——状态在 PLAN.md 里，不在 context 里。

- **立项/拆解**：最强模型（Fable 5）。一次性成本，但影响所有后续阶段。
- **implementer**：默认不传 `model`（继承主会话模型）。基本是照方案敲代码的机械阶段，派活时传 `model: "sonnet"` 省成本；最难的核心阶段可传 `model: "opus"` 或由 Fable 会话直接派（继承 Fable）。
- **scout / reviewer / final-reviewer**：已在 agent 定义里固定为 `haiku` / `sonnet` / `sonnet`，不要在调用时覆盖。

## 几条硬规矩

- PLAN.md 里绝不写"见上文""如前所述"——它的每个读者（implementer、下次会话）都没有你的 context。
- 主会话不读源码，也不 `cat`/`head` PLAN.md 或任何 `.claude/longdev/` 下的报告全文。要么信 reviewer 的独立审查，要么把疑点写成问题发回给 implementer。自己下场重读会让 context 积压卷土重来。
- 主会话不复述 subagent 的产出：修复轮传路径不传清单，向用户汇报只写结论。
- 调研只派 `longdev-scout`，不派通用 agent。
- 不要为了让进度看起来快而合并阶段，也不要跳过逐阶段 review 或收尾审查。
- 新增行为不带测试的阶段不算完成，除非 PLAN.md 决策里明确写了该项目不引入测试。
- 阶段验证失败时如实报告失败输出，不要模糊成"基本通过"。
- 用户只是在问问题或讨论方案时，不要动手改代码。
