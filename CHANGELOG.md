# Changelog

发版流程：改代码 → 更新本文件 → bump `.claude-plugin/plugin.json` 的 `version` → commit → `git tag vX.Y.Z` → push。
其他设备只有在 `version` 字符串变化后才会收到更新（`/plugin update longdev@zzm-plugins` 或自动更新）。

## 0.2.0 — 2026-08-18

- `longdev-reviewer` 重构为双维度审查：一致性核对（diff vs PLAN.md 阶段目标/决策/入口更新，自己做）+ 代码正确性（调用 `/code-review` skill，medium 档，不带 --fix）。回传的阻塞问题标注来源 `[一致性]` / `[code-review]`。
- reviewer 的 tools 增加 `Skill`；修复轮复查只聚焦上一轮问题，不重跑完整两维度。
- SKILL.md C-3 相应更新，并明确主会话不要替 reviewer 重跑 review。

## 0.1.0 — 2026-08-18

- 首个打包版本。
- 编排模式为默认：主会话只编排，每阶段派干净 context 的 `longdev-implementer` 执行，`longdev-reviewer` 独立审查，全程无需逐阶段 `/clear`。
- 主会话亲自执行降级为例外（阶段标【主会话】时）。
- 状态载体为项目内 `.claude/longdev/PLAN.md`。
