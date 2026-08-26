# Changelog

发版流程：改代码 → 更新本文件 → bump `.claude-plugin/plugin.json` 的 `version` **和** `skills/longdev/SKILL.md` 第一行标题里的版本号（两处必须一致，SKILL.md 的那个是用户在会话里看到的）→ commit → `git tag vX.Y.Z` → push。
其他设备只有在 `version` 字符串变化后才会收到更新（`/plugin update longdev@zzm-plugins` 或自动更新）。

## 0.5.0 — 2026-08-26

计划文件结构化 + 全角色读写卫生。起因是实测：一个 5 阶段任务里 7 个 implementer 子会话的 context 冲到 200k–600k 字符（60–180k token，最大的已贴近上限会触发压缩），而那份 PLAN.md 长到 65k 字符 / 291 行，其中 ~85% 是阶段局部信息却让每个 implementer 全读。诊断结论是**该拆的是阶段和文档，不是 implementer 的角色**——把实现和测试拆成两个 agent 只会让第二个重读一遍所有文件。

- **一个任务一个目录**：`.claude/longdev/<任务名>/`，含 `PLAN.md`（索引，≤120 行）、`stages/<N>.md`（每阶段入口 + 完成记录，≤80 行）、`notes/<主题>.md`（跨阶段契约类参考物）、`scout/`、`reviews/`。多任务共存不再靠手动改名。
- **PLAN.md 降级为索引**：只放每个阶段都用得上的（目标、基线 commit、阶段表、**全局**决策、**全局**坑、入口级关键文件 ≤15 行、参考物索引、调研指针、验证方式）。阶段局部的决策/坑/文件清单一律留在 `stages/N.md`；只有 implementer 判断跨阶段的才提升到 PLAN.md 并标 `（阶段 N 提升）`。中途冒出的契约类内容进 `notes/`，禁止在 PLAN.md 新开节。
- **各角色只读自己那一份**：implementer N 读 `PLAN.md` + `stages/N.md` + `stages/N-1.md` 的「交接」小节（`sed` 只读该节）+ 入口点名的 notes——从 65k 降到 ~10k；reviewer 读索引 + 本阶段文档 + diff；final-reviewer 读索引 + 全部 stages + 全量 diff（决策漂移检查反而更容易，每阶段决策天然带出处）；主会话只 `grep` 阶段表。
- **阶段尺寸硬约束**：planner 拆解时每阶段 ≤8 个文件 / ≤400 行，超了必须拆成两个。implementer 开工发现超标要先上报，主会话按"拆阶段"处理而不是放行。
- **读写卫生写进全部五个 agent**：>200 行的文件按段读（先 `grep -n` 定位）、禁止 `cat` 整个目录、改文件用 Edit 不用 Write（同一文件 Write 两次以上就是信号）、测试输出走静默 reporter 或 `tail`、**禁止读 `~/.claude/` 下的会话记录/transcript/plans**（实测有 implementer 因入口信息不足去"考古"主会话 transcript，一次吃掉 28k+22k+18k 字符）、同一文件不读第二次。final-reviewer 额外要求按文件读 diff 而不是一把梭。
- **stages 文档两段式**：「入口」由 planner 写、上一阶段 implementer 精修，写完冻结；「完成记录」由本阶段 implementer 追加，含「给下一阶段的交接」——收尾审查靠比对这两段判断阶段是否达成目标。新增 `references/stage-template.md`。
- **旧版计划迁移**（流程 E）：检测到 `.claude/longdev/PLAN.md` 没有配套 `stages/` 目录时，派 planner 走「迁移轮」拆分（只搬运，不重新规划阶段），旧文件留作 `PLAN.legacy.md`。
- 状态判定重写：扫 `.claude/longdev/*/`，多个未完成任务时列出来问用户，不擅自挑。
- reviewer 维度一新增一条：报告「该下沉的内容被塞进 PLAN.md」和文件超行数上限。

## 0.4.1 — 2026-08-26

- SKILL.md 的 description 缩短并前置"做什么"：`/` 命令菜单只显示开头一截，原 150+ 字的描述被截断到看不出用途。触发词保留在句尾。

## 0.4.0 — 2026-08-26

- **立项编排化，不再进 plan mode**：新增 `longdev-planner` agent（继承主会话模型）。主会话派 scout 落文件 → 派 planner 读 scout 报告、按模板写 `PLAN.draft.md`、回传 ≤30 行摘要（阶段清单 / 关键决策 / 待用户拍板 / 风险）→ 主会话把草稿文件展示给用户确认 → 修改意见 `SendMessage` 给同一 planner 迭代 → 确认后 `mv` 转正为 PLAN.md。立项期间主会话只积累摘要，**删除了 v0.3.0 的"立项后建议 /clear"**；全流程唯一需要 `/clear` 的场景只剩 D（主会话亲自执行的阶段）。
- **按客户端选择文件展示方式**：新增 `references/show-file.md`。用 `CLAUDE_CODE_ENTRYPOINT` 判定：CLI 下有 `code`/`cursor` 就 `--reuse-window --goto` 在用户编辑器里打开；裸终端回显绝对路径；非 CLI（桌面 App / 网页）用 `SendUserFile` 推侧栏。立项草稿和收尾 `reviews/final.md` 都走这个机制，主会话自己不读文件。
- **SKILL.md 精简并加版本号**：第一行 `# longdev vX.Y.Z`，主会话开工第一句报版本，用户据此判断是否已更新。删掉解释性的"context 预算"段和历史备注（保留在本文件里），只留操作规则；从 ~140 行压到 ~85 行。
- 状态判定新增"只有 PLAN.draft.md"分支（上次立项没确认完）。

 — 2026-08-26

- `longdev-scout` 模型从 haiku 改为 sonnet（effort medium）。haiku 实测不遵守回传长度约束（40 行上限回了 ~1000 行），调研质量也不稳。

## 0.3.0 — 2026-08-26

- **新增 `longdev-final-reviewer`**：全部阶段完成后做收尾全盘审查。拿 PLAN.md 记录的基线 commit 算整个任务的 diff，查逐阶段 review 结构上抓不到的问题（总目标端到端达成、跨阶段接缝、决策漂移、跨阶段残留），全量跑测试；默认不重跑 `/code-review`（diff ≤800 行或某阶段缺审查记录时才跑 low 档）。SKILL.md C-7/C-8 新增收尾审查与收尾修复轮，最多两轮。
- **测试要求显式化**：立项时阶段完成标准优先写成自动化测试并定下「测试约定」（写进 PLAN.md 验证方式）；implementer 把补单元测试列为交付物，断言行为不断言实现；reviewer 维度一新增测试核对（存在性、锚在完成标准、有无凑绿痕迹）。项目无测试基础设施时"是否引入"是立项决策，不由 implementer 顺手拍板。
- **主会话 context 收缩**（基于实测：一个 5 阶段任务的主会话中，各阶段 implementer/reviewer 回传合计 <20%，其余来自立项调研回传、主会话自己读文件、修复轮复述）：
  - scout / reviewer / final-reviewer 的完整报告一律落文件（`.claude/longdev/scout/*.md`、`reviews/stage-N.md`、`reviews/final.md`），回传只给 ≤15 / ≤10 行摘要；修复轮 `SendMessage` 只传报告路径不粘清单。
  - 立项只派 `longdev-scout`，禁止用 Plan / Explore 等无输出约束的通用 agent 调研；立项完成后建议 `/clear` 再续接（A-7）。
  - 主会话不 `cat` PLAN.md 或任何报告全文，抽查只 `grep` 阶段清单；PLAN.md 内容属实性由 reviewer 核。
- PLAN.md 模板新增「基线 commit」、「测试约定」，决策条目标注来源阶段，「调研结论」只放结论和指向 scout 文件的指针。
- scout / reviewer 的 tools 增加 `Write`。

## 0.2.0 — 2026-08-18

- `longdev-reviewer` 重构为双维度审查：一致性核对（diff vs PLAN.md 阶段目标/决策/入口更新，自己做）+ 代码正确性（调用 `/code-review` skill，medium 档，不带 --fix）。回传的阻塞问题标注来源 `[一致性]` / `[code-review]`。
- reviewer 的 tools 增加 `Skill`；修复轮复查只聚焦上一轮问题，不重跑完整两维度。
- SKILL.md C-3 相应更新，并明确主会话不要替 reviewer 重跑 review。

## 0.1.0 — 2026-08-18

- 首个打包版本。
- 编排模式为默认：主会话只编排，每阶段派干净 context 的 `longdev-implementer` 执行，`longdev-reviewer` 独立审查，全程无需逐阶段 `/clear`。
- 主会话亲自执行降级为例外（阶段标【主会话】时）。
- 状态载体为项目内 `.claude/longdev/PLAN.md`。
