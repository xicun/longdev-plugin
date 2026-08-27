---
name: longdev
description: 长程开发编排：大任务拆阶段，subagent 逐阶段实现+审查+收尾全盘审查，状态落盘在结构化的 PLAN.md 索引 + stages 文档，主会话不积 context。用于新功能/重构/迁移等跨会话任务；用户说"长程开发""分阶段做""接着上次继续"时触发。
---

# longdev

**开工第一句话报版本**：读本 plugin 根目录的 `.claude-plugin/plugin.json`（相对本文件是 `../../.claude-plugin/plugin.json`），把它的 `version` 报成 `longdev vX.Y.Z`。**不要凭记忆或从别处猜版本号**——plugin.json 是唯一真源。用户据此判断是否已更新（最新版见 GitHub `xicun/longdev-plugin` 的 CHANGELOG 顶部；不一致就 `/plugin update longdev@zzm-plugins`）。

原则：**状态落盘，重活全在 subagent 里**。调研、拆解、实现、审查都由干净 context 的 subagent 完成，交接物是文件。主会话只收摘要，subagent 只读自己那一份。

## 落盘结构

一个任务一个目录：`.claude/longdev/<任务名>/`（`<任务名>` 用 kebab-case 英文短名，从目标里取，如 `agentops-observability`）。

| 路径 | 写入者 | 内容 | 上限 |
|---|---|---|---|
| `PLAN.md` | planner 草稿转正；每阶段 implementer 只改状态和提升项 | **索引**：目标、基线 commit、阶段表、全局决策、全局坑、入口级关键文件、参考物索引、调研结论指针、验证方式 | 120 行 |
| `stages/<N>.md` | planner 写「入口」；本阶段 implementer 追加「完成记录」 | 该阶段的完成标准、要改的文件、前置条件、风险；完成后的改动/决策/坑/验证/交接 | 80 行 |
| `notes/<主题>.md` | planner / implementer | 跨阶段参考物：API 契约、字段映射、状态机、错误码表 | — |
| `scout/<主题>.md` | scout / planner | 调研完整报告 | — |
| `reviews/stage-<N>.md`、`reviews/final.md` | reviewer / final-reviewer | 审查完整报告 | — |
| `decisions/agent-<N>-<slug>.md` | decider | 代你拍板的一条决策：问题、依据、选项、结论、影响面、回滚方式。用户复核后主会话 `mv` 进 `decisions/reviewed/` | 40 行 |

**分工的意义**：PLAN.md 每个 implementer 都全读，所以只放「每个阶段都用得上」的东西；阶段局部的一切留在 `stages/N.md`。PLAN.md 每胖一行，后面每个阶段的固定成本都涨一行。

**各角色读什么**：implementer N 读 `PLAN.md` + `stages/N.md` + `stages/N-1.md` 的「交接」小节 + 入口点名的 notes。reviewer N 读 `PLAN.md` + `stages/N.md` + diff。final-reviewer 读 `PLAN.md` + 全部 `stages/*.md` + 全量 diff。**主会话只 `grep` PLAN.md 的阶段表**，不 cat 任何文件。

## 派活

Agent tool，`subagent_type` 填 `longdev-scout` / `longdev-planner` / `longdev-implementer` / `longdev-reviewer` / `longdev-decider` / `longdev-final-reviewer`。每个 prompt 都要给**任务目录的路径**。互不依赖的调研放同一条消息并发派出。**不用 `Plan` / `Explore` / `general-purpose` 等通用 agent**——它们没有输出长度约束。

## 第一步：判定状态

跑一次：`ls -d .claude/longdev/*/ 2>/dev/null; ls .claude/longdev/*.md 2>/dev/null`，再对候选任务 `grep -n "^| [0-9]\|^\*\*状态" <任务目录>/PLAN.md`。不 cat 全文。

- **没有 `.claude/longdev/`，或目录空** → A 立项
- **恰好一个任务目录且有未完成阶段** → B 续接
- **多个任务目录有未完成阶段** → 列出来问用户接哪个，不擅自挑
- **任务目录里只有 `PLAN.draft.md`** → 上次立项没确认完，从 A.4 起（有修改意见就派新 planner，说明"修改已有草稿"）
- **`.claude/longdev/PLAN.md` 直接躺在根下、没有 `stages/` 目录**（v0.4 及以前的旧版）→ E 迁移
- **用户带了新目标描述** → 问清是新开任务还是继续某个已有的，不擅自覆盖
- **用户传 `status`** → 只 grep 阶段表汇报进度，结束

## A. 立项

0. planner 继承主会话模型。当前不是最强模型（Fable 5）的话提醒一句可 `/clear` 后 `claude --model fable` 重开做立项；说完继续，不等确认。
1. **建目录**：`mkdir -p .claude/longdev/<任务名>/{stages,notes,scout,reviews,decisions}`。
2. **派 scout**：按子系统拆几个互不依赖的主题并发派出。prompt 给项目根目录、要查什么、输出路径 `<任务目录>/scout/<主题>.md`。它写文件，回 ≤15 行。**不进 plan mode，不自己读文件。**
3. **派 planner**：prompt 给项目根目录、**任务目录**、用户目标描述原话、scout 文件清单、两份模板的绝对路径（本 skill 目录下 `references/plan-template.md` 和 `references/stage-template.md`）。它写 `PLAN.draft.md` + 全部 `stages/N.md` 入口，回 ≤30 行：草稿路径、阶段清单（含预计文件数）、关键决策、**待用户拍板**、风险。
4. **展示草稿**：按 `references/show-file.md` 打开 `PLAN.draft.md`，回显 planner 摘要，重点列「待用户拍板」及推荐。等用户表态。这是**唯一必经的 HIL 点**。
5. **有修改意见** → 用户原话 `SendMessage` 给同一个 planner，它改草稿和相关 stages 文件、回本轮变更；回到 4。主会话不自己动草稿。
6. **确认** → `mv <任务目录>/PLAN.draft.md <任务目录>/PLAN.md`，一句话告知，进入 C。不需要 `/clear`。

## B. 续接

1. `grep` PLAN.md 阶段表找第一个未完成阶段（状态 `▶` 或 `⬜`）。**不读 stages 文件**——那是 implementer 的输入。
2. 不重新探索。用户明确说上次的入口信息不够才派 scout 补一次（落文件回摘要）。
3. 一句话汇报"上次做到 X，本次从阶段 N 继续：<阶段表里的一行目标>"，进入 C。

## C. 推进阶段

阶段串行；除非计划明确标注两阶段完全不相交且各用 `isolation: "worktree"`。

1. **派 implementer**：prompt 只给项目根目录、**任务目录**、阶段号。不复述计划。它读索引+本阶段入口+上一阶段交接，实现、补测试、跑验证、写 `stages/N.md` 完成记录、精修 `stages/N+1.md` 入口、只改 PLAN.md 的状态和提升项。
   - **主会话是 Fable 时降一档派**：传 `model: "opus"`，并说明一句「本阶段以 opus 派 implementer——立项用的 Fable 会话不带到执行；某个阶段想用 Fable 跑就说一声」。A.0 让你用 Fable **是为了立项**，A.6 又说不用 `/clear`，那个会话是自己滑过来的，降档是还原意图不是覆盖它。
   - planner / decider / final-reviewer **不降**——它们都是低频高判断、基数小。只有 implementer 是每阶段都跑且 token 基数最大的。
   - **降级只向下，不向上**：向上靠你在什么会话里跑，向下靠这条规则。机械阶段仍可手动传 `sonnet`。
2. **先看回传的「遗留/上报」**：前置条件不成立、验证反复失败、**阶段尺寸超标**（>8 文件 / >400 行，通常该拆阶段）→ 直接停下来问用户。**只是「判不准是否不可逆」的分叉** → 派 decider 判一次（见第 5 步），判定可逆就地定夺、判定不可逆则升级。拿到决策后写进 stages 文件，`SendMessage` 让同一个 implementer 继续。
3. **派 reviewer**：prompt 给项目根目录、任务目录、阶段号、报告路径 `<任务目录>/reviews/stage-<N>.md`。它核对 diff 与 stages/N.md 完成标准、PLAN.md 全局决策、测试要求的一致性，并调 `/code-review`；报告写文件，回 ≤12 行。主会话不重跑 review，不读报告。
4. **有阻塞** → `SendMessage` 给同一个 implementer："读 `<任务目录>/reviews/stage-<N>.md`，修阻塞问题，重跑验证"，不粘清单。修完 `SendMessage` 让同一个 reviewer 复查。两轮仍阻塞就停下汇报。
5. **回传里有「方案级决策待确认」** → **先派 `longdev-decider`**（prompt 给项目根目录、任务目录、阶段号、reviewer 报告路径）。它逐条判类型：只用 PLAN.md 目标+全局决策+代码事实推得出来的自己定夺并写 `decisions/`，需要用户意图、后果不可逆、依据不足、或要改 PLAN.md 全局决策的标「需用户」。回 ≤12 行，末行是**未复核代理决策累计数**。
   - **全部已决且累计 <3** → 一句话 `SendMessage` 让 implementer 按 decider 口径写实（跨阶段的提升到 PLAN.md「全局决策」并标「阶段 N 提升」）；汇报时每条念一行「已代你决定：X，因为 Y」，直接进入下一阶段，不等确认。
   - **有「需用户」或累计 ≥3** → 停下来问用户，逐条念一行标题，要细节就按 `references/show-file.md` 打开 `decisions/` 下对应文件。用户复核后 `mkdir -p <任务目录>/decisions/reviewed && mv <任务目录>/decisions/agent-*.md <任务目录>/decisions/reviewed/` 清零计数。否决某条 → 当阻塞问题走第 4 步发回 implementer 改。用户说“你定”就当认可，不反复问。
   - **派它之前先看当前会话的模型**：不是最强模型（Fable 5 / Opus）时，prompt 里加一句「本次以**保守档**运行：拿不准的一律标『需用户』」，并对用户提醒一句「decider 会以 <当前模型> 运行，想要更强的代拍质量可 `/clear` 后换模型重开」——说完继续，不等确认（同 A.0）。
   - **软失败**：decider 派不出来或回传异常（无该模型权限、撞额度、超时）→ **绝不卡住**，退回 v0.5.x 的行为直接问用户，并说明一句「decider 本轮不可用，这几条由你拍板」。降级的是自动化程度，不是正确性。
6. **抽查**：只跑 `grep -n "^| [0-9]" <任务目录>/PLAN.md` 确认本阶段状态变 `✅`、下一阶段变 `▶`。内容属实性 reviewer 已核。
7. 简短汇报本阶段（做了什么、验证输出、review 结论），直接进入下一阶段。
8. **全部完成 → 派 final-reviewer**：prompt 给项目根目录、任务目录、报告路径 `<任务目录>/reviews/final.md`。它读 PLAN.md + 全部 stages + 按基线 commit 算全量 diff，查总目标端到端达成、跨阶段接缝、决策漂移、跨阶段残留，全量跑测试；不重跑全量 `/code-review`。
9. **收尾有阻塞** → 派新 implementer 做「收尾修复轮」（prompt 给项目根目录、任务目录、报告路径，说明是收尾修复不是某阶段），修完 `SendMessage` 同一个 final-reviewer 复查。最多两轮。
10. 通过 → `sed` 在 PLAN.md 标题下加 `**状态：已完成**`，按 `references/show-file.md` 展示 `reviews/final.md`，做总结（含收尾结论和全量测试结果）。

## D. 主会话亲自执行（例外）

仅用于标了**【主会话】**的阶段或用户明确要求参与实现时。实现 + 验证后照常派 reviewer，照常写 `stages/N.md` 完成记录。因为实现细节进了主会话，收尾时**提示用户 `/clear` 后 `/longdev` 续接**——这是全流程唯一需要 `/clear` 的场景。

## E. 迁移旧版单文件计划

发现 `.claude/longdev/PLAN.md` 没有配套 `stages/` 目录（v0.4 及以前立项的）：

1. 告知用户："检测到旧版单文件计划，先迁移成索引+阶段结构再继续，不影响已完成的阶段。"
2. `mkdir -p .claude/longdev/<任务名>/{stages,notes,scout,reviews,decisions}`，把旧 `PLAN.md` 和已有的 `scout/`、`reviews/` 移进去。
3. 派 `longdev-planner`，prompt 说明这是**迁移轮**：给任务目录、旧文件路径、两份模板路径。它把阶段局部内容下沉到 `stages/N.md`、契约类内容进 `notes/`、跨阶段的留在 PLAN.md，保留原有阶段状态和基线 commit，旧文件改名 `PLAN.legacy.md`。回 ≤20 行。
4. 汇报"PLAN.md 从 X 行降到 Y 行，拆出 N 个阶段文档"，然后走 B 续接。

## 模型分层

- **planner**：继承主会话 → 立项在 Fable 5 会话里做。
- **implementer**：默认继承，但**主会话是 Fable 时降一档传 `opus`**（见 C.1）——它是全流程 token 基数最大的角色，执行的又是 planner 已写好的规格，Fable 的边际收益撑不起两倍单价。机械阶段仍可手动传 `sonnet`。
- **scout / reviewer**：agent 定义里固定 `sonnet`，不覆盖。都是每阶段都跑的高频角色，且 reviewer 把正确性硬活委托给 `/code-review`，自己只做清单式核对。
- **final-reviewer**：**不写死，继承主会话**。一次任务只跑一次，做的是跨阶段接缝、决策漂移、端到端达成这类综合判断（不是逐行找 bug），且明确不重跑 `/code-review`——没有更强的子工具兜底，它就是交付前最后一道网。
- **decider**：**不写死，继承主会话**。写死具体模型会让没有该模型权限的人（如 standard team seat 没有 Fable 5）直接用不了，也躲不开额度限制。当前会话不是最强模型时改用「保守档」派，见 C.5。

## 硬规矩

- 落盘文件里绝不写"见上文"——每个读者都只读自己那一份。
- 主会话不读源码，不 `cat`/`head` 任何 `.claude/longdev/` 下的文件。给用户看就用 `references/show-file.md`，要改就发回给写它的 subagent。
- 主会话不复述 subagent 产出：修复轮传路径，汇报只写结论。
- 调研只派 scout，拆解只派 planner，不进 plan mode。
- 阶段尺寸超标（>8 文件 / >400 行）当拆阶段处理，不要放行。
- implementer 自己新立的方案级决策由 **decider** 在「PLAN 目标 + 代码事实」范围内代拍，越界的（要用户意图、不可逆、依据不足、动全局决策）必须升级给用户。reviewer 只负责揪出来，**主会话永远不代拍**。
- 不合并阶段，不跳过逐阶段 review 或收尾审查。
- 新增行为不带测试的阶段不算完成，除非 PLAN.md 决策明确该项目不引入测试。
- 验证失败如实报输出，不说"基本通过"。
- 用户只是提问或讨论时，不动代码。
