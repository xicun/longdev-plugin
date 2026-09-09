---
name: autopilot
description: 产品级自主研发编排（longdev 的自动挡）：给一个产品目标，问卷式宪章确认一次，之后自主迭代到收官——product-owner 在宪章边界内维护 backlog，每轮迭代作为一个标准 longdev 任务全流程执行（gate 纪律不变），acceptance 代行用户验收，失败功能回滚隔离，触发停机条件自动收官。用户说"自动挡""自主迭代""无人值守把这个产品做出来""autopilot"时触发；单个边界明确的任务用 longdev。
---

# autopilot

**开工第一句话报版本**：读 `../../.claude-plugin/plugin.json`（相对本文件）的 `version`，报成 `longdev vX.Y.Z (autopilot)`。不凭记忆猜。

autopilot 是 longdev 的自动挡：上层多一个「宪章 → backlog → 迭代 → 验收 → 停机判定」的循环，执行层每轮迭代就是一个标准 longdev 任务。**先读一次 `../longdev/SKILL.md`**（相对本文件）——它的落盘结构、派活方式、A/C 流程、模型分层、硬规矩、Gate 纪律在迭代内**原样适用**，本文件只写上层循环和「B.2 替换表」列出的分支差异。

原则一句话：**宪章是唯一的人**。立宪确认后，longdev 里所有「问用户」的分支都改成「问宪章」；宪章答不了的，可逆分叉选范围最小的选项备案，不可逆的隔离，**绝不猜**。

## 落盘结构

产品层一个目录：`.claude/autopilot/<产品名>/`（kebab-case 英文短名）。每轮迭代是一个标准 longdev 任务目录：`.claude/longdev/<产品名>-i<N>/`，内部结构、写入者、上限全按 longdev。

| 路径 | 写入者 | 内容 | 上限 |
|---|---|---|---|
| `CHARTER.md` | product-owner 起草，问卷+用户确认后转正并**冻结** | 宪章：目标用户、形态、核心场景、非目标、验收清单、质量约定、预算与停机、授权边界。条款全部带编号 | 80 行 |
| `BACKLOG.md` | product-owner 独占 | 功能候选表（每条必须引用宪章条款编号）+ 观察区 | 60 行 |
| `iterations/<N>.md` | PO 写「入场」；主会话追加「收尾」（≤12 行机器数字与指针） | 本轮选题与理由；gate 数字、验收计数、隔离清单 | 40 行 |
| `acceptance/<N>.md`、`acceptance/final.md` | acceptance | 逐条核宪章验收清单的报告 + 观察 | — |
| `scout-repo.md` | scout | 立宪时的 repo 现状调研（绿地项目没有） | — |

## 派活

新增两个角色：`longdev-product-owner`、`longdev-acceptance`（都继承主会话模型；非最强模型会话时 prompt 加「保守档」，含义见各自定义）。迭代内的 scout / planner / implementer / reviewer / decider / final-reviewer 全按 longdev。

## 第一步：判定状态

跑一次：`ls -d .claude/autopilot/*/ 2>/dev/null; ls .claude/autopilot/*/CHARTER*.md 2>/dev/null`。

- **无目录** → A 立宪
- **只有 `CHARTER.draft.md`** → 问卷没走完，从 A.4 续（PO 实例已不在就派新的，说明"修改已有草稿"）
- **有 `CHARTER.md` 且没有「已收官」标记** → 续迭代：取 `iterations/` 下最大编号 N，`grep -c '^## 收尾' <产品目录>/iterations/<N>.md`——为 0 = 轮内续接（再 grep `.claude/longdev/<产品名>-i<N>/PLAN.md` 的阶段表，按 longdev B 续接进 B.2；连迭代任务目录都还没有就从 B.2 立项起）；为 1 = 从 B.7 停机判定接着走；`iterations/` 为空 = 从 B.1 起第 1 轮
- **`CHARTER.md` 标「已收官」** → 汇报收官报告位置；用户要继续做 = **修宪**：解冻走一次 A.4-A.7 的问卷增补+确认（这是收官后唯一的再次 HIL），修完重新冻结、🚫 项经用户点名可解禁，进 B
- **多个产品目录** → 列出来问用户，不擅自挑
- **用户传 `status`** → 只 grep BACKLOG 状态列 + 当前迭代任务的阶段表汇报，结束

## A. 立宪（唯一必经的 HIL）

1. `mkdir -p .claude/autopilot/<产品名>/{iterations,acceptance}`。
2. **有现成代码就派 scout**：摸清 repo 现状，输出 `<产品目录>/scout-repo.md`。绿地项目跳过。
3. **派 product-owner（立宪轮）**：prompt 给项目根目录、产品目录、用户目标原话、宪章模板绝对路径（本 skill 目录下 `references/charter-template.md`）、问卷规则绝对路径（`references/charter-interview.md`）。它做主流形态调研（WebSearch）、写 `CHARTER.draft.md`、回传 ≤30 行：草稿路径 + 问卷题目。
4. **问卷**：把 PO 回传的题目转成 **AskUserQuestion** 提问，转换规则见 `references/charter-interview.md`——每批 ≤4 题、推荐项排第一并标「（推荐）」、范围/授权类用 multiSelect、用户全选推荐也能开工。**这是本模式减输入负担的核心**：用户点选择题，不写需求文档。
5. 答案（含 Other 原话和 notes）原样 `SendMessage` 给同一个 PO。它落定答案、回传剩余待定；有新题就回到 4。**问卷最多两批**，之后剩余待定按 PO 推荐落定、宪章里标「（默认）」。
6. **展示草稿**：按 `../longdev/references/show-file.md` 打开 `CHARTER.draft.md`，重点回显「非目标」和「预算与停机」。等用户表态；修改意见原话 `SendMessage` 给 PO 改，回到本步。
7. **确认** → `mv <产品目录>/CHARTER.draft.md <产品目录>/CHARTER.md`。**此后冻结**：任何 agent 不得改它一个字（唯一例外是收官时主会话 sed 加状态行）；中途要改宪 = 停机等人。进入 B，第 1 轮。

## B. 迭代循环（第 N 轮）

1. **派 product-owner（规划轮）**：prompt 给产品目录、轮次 N。它读宪章+backlog+上轮入场收尾+上轮验收报告，更新评分（含减法项、搬运观察），选出本轮 ▶ 功能（≤宪章每轮上限），写 `iterations/<N>.md`「入场」，回 ≤12 行。它回「全部候选低于阈值」→ 直接进 C 收官。
2. **迭代内跑 longdev A+C 全流程**：任务目录 `.claude/longdev/<产品名>-i<N>/`，立项的"用户目标原话" = iterations/N.md 的**本轮目标一句话**。按下表替换分支，**其余一字不差地遵守**（含快照、gate、修复轮、证据块）：

   | longdev 的分支 | autopilot 替换成 |
   |---|---|
   | A.0 / C.5 模型提醒用户 | 跳过（无人在场），保守档规则照用 |
   | A.4 用户确认 PLAN.draft | 派 **acceptance（计划核对轮）**按宪章逐条核；打回清单 `SendMessage` 给 planner 改，改完让 acceptance 复核，≤2 轮；仍越界 → 该功能 🚫、`SendMessage` 让 planner 从计划中剔除后再核一次 |
   | planner「待用户拍板」 | 立项收尾时派 decider 裁决，依据从「PLAN+代码事实」扩成「**宪章**+PLAN+代码事实」（prompt 里给 CHARTER.md 路径并明说这一条） |
   | decider「需用户」 | B 类（意图）：宪章推不出 → 选**可逆且范围最小**的选项，写 `decisions/` 标「收官待复核」；C 类（不可逆）：宪章「授权边界」明确允许的才做，否则该功能 🚫。**永不猜，永不越权做不可逆动作** |
   | 未复核代理决策累计 ≥3 停下问人 | 不停不清零，全部备案，收官报告逐条汇总给用户复核 |
   | 阶段尺寸超标问用户 | `SendMessage` 发回 planner 拆阶段，重派 implementer |
   | 修复两轮仍阻塞 | **回滚+隔离**：`SendMessage` 让同一 implementer 按改动清单把本阶段回滚到快照（验证：`git diff --stat <SNAP>` 为空）；该功能 🚫；PLAN.md 阶段表如实标「⏭ 跳过（隔离）」；其余阶段继续。该功能已完成的早期阶段代码保留——死代码由 final-reviewer 按「跨阶段残留」抓，收尾修复轮清理 |
   | 计划里出现【主会话】阶段 | 不允许——acceptance 计划核对轮直接打回 |
   | D 主会话亲自执行 | 不存在 |
   | decider 软失败（派不出/异常） | 不能退回问用户 → 全部按「需用户」的保守分支处理（B 类最小方案备案、C 类隔离） |

3. final-reviewer 收尾照旧（含收尾修复轮，≤2 轮；仍阻塞按熔断处理）。
4. **派 acceptance（验收轮）**：prompt 给产品目录、轮次 N、报告路径 `acceptance/<N>.md`。它从宪章目标用户视角**真实运行产品**，逐条核宪章验收清单，回 ≤12 行。
5. **迭代 gate（主会话亲自跑，纪律同 longdev：固定命令、不诊断、产出是布尔值）**：

   ```
   # a. 宪章的机器可判清单（唯一允许 grep 宪章正文的地方，≈8 行）
   sed -n '/^### 机器可判/,/^### /p' <产品目录>/CHARTER.md
   # b. 逐条跑真实退出码
   set -o pipefail; <V条款命令> 2>&1 | tail -3; echo "exit=$?"
   # c. 验收报告存在性 + 未达成计数（acceptance 用 "- [ ]" 标未达成）
   grep -c '^- \[ \]' <产品目录>/acceptance/<N>.md
   # d. 隔离规模（熔断输入）
   grep -c '🚫' <产品目录>/BACKLOG.md
   ```

6. **收尾落盘**：主会话向 `iterations/<N>.md` 追加「收尾」（按 `references/iteration-template.md`，≤12 行：gate 退出码原样、验收 x/y、隔离清单、决策备案数、给下轮一行）。宪章授权了本地 commit 的（A 条款），此时 `git add -A && git commit -m "autopilot i<N>: <本轮目标>"`——跨迭代回滚靠它。
7. **停机判定**（主会话按规则判，不派 agent，按顺序查）：
   - **熔断**：同一功能第二次 🚫，或本轮 🚫 数 ≥ 本轮 ▶ 数的一半，或收尾修复两轮仍阻塞 → **停机报告等人**（如实列证据，不收官不继续——系统性失败时继续跑只会烧预算产生更多要回滚的代码）
   - 宪章验收清单全绿（gate b 全 exit=0 且 gate c 为 0）→ C 收官
   - 轮次 = 宪章迭代上限 → C 收官（如实列未达成项）
   - PO 报全部候选低于阈值 → C 收官
   - 都不是 → 汇报本轮一段（≤5 行，gate 数字原样念），进第 N+1 轮
8. **context**：主会话每轮只沉淀那 ≤5 行摘要。长跑配 `/loop`，或每 2–3 轮 `/clear` 后重新触发 autopilot——状态全在盘上，续接成本为零（第一步的状态判定就是为此设计的）。

## C. 收官

1. **派 acceptance（收官轮）**：写 `acceptance/final.md`——宪章逐条终判、全部 🚫/💤 及原因指针、全部「收官待复核」决策的标题清单、观察区全集。
2. `sed` 在 CHARTER.md 标题下加 `**状态：已收官（YYYY-MM-DD）**`（唯一允许动冻结宪章的一处）。
3. 按 show-file 展示 `acceptance/final.md`，汇报：轮数、交付/隔离/推迟功能数、待复核决策数、最后一轮迭代 gate 的证据行**原样**。用户十分钟内要能复核完全部代拍——这是自主模式对可审计性的交付标准。

## 授权边界（宪章也改不掉的底线）

- **永不**：push 远端、对外发布/部署、删项目外文件、把项目内容发给外部服务。这些不出现在问卷选项里，宪章写了也不算。
- **宪章可授权**（问卷勾选，没勾 = 不允许）：本地 git commit、安装项目内依赖、起本地服务跑验收。
- 熔断、收官、任何时刻都不清理 `.claude/autopilot/` 和 `.claude/longdev/` 下的落盘——那是全部审计记录。

## 硬规矩

- 宪章确认后冻结；**引用不到宪章条款编号的功能不入 backlog**——这是防功能爆炸的主闸，比任何措辞约束都硬；每轮 ▶ ≤ 宪章的每轮上限。
- acceptance 只对宪章负责，不提新需求；引不到条款的想法只进「观察」，**永不自动转功能**，收官时呈给用户。
- 同一功能 🚫 后永不静默重试；解禁唯一途径是修宪（HIL）。
- 主会话不读 acceptance / reviews / iterations / BACKLOG 正文，只按第一步和 B.5 的定向 grep 取机器可判的行；写入仅限 B.6 的「收尾」追加和 C.2 的一行 sed。
- longdev 的全部硬规矩和 Gate 纪律在迭代内原样适用；迭代 gate 的产出同样是布尔值，不是任务。
- 无人在场不是降低标准的理由，是提高标准的理由：所有自主决策必须落盘可审计（decisions/、iterations/、BACKLOG 状态列），停机报告和收官报告必须让用户能顺着指针查到每一步的原始证据。
