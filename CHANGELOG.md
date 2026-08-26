# Changelog

发版流程：改代码 → 更新本文件 → bump `.claude-plugin/plugin.json` 的 `version` → commit → `git tag vX.Y.Z` → push。
其他设备只有在 `version` 字符串变化后才会收到更新（`/plugin update longdev@zzm-plugins` 或自动更新）。

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
