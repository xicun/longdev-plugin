# Changelog

发版流程：改代码 → 更新本文件 → bump `.claude-plugin/plugin.json` 的 `version` → commit → `git tag vX.Y.Z` → push。
其他设备只有在 `version` 字符串变化后才会收到更新（`/plugin update longdev@zzm-plugins` 或自动更新）。

## 0.1.0 — 2026-08-18

- 首个打包版本。
- 编排模式为默认：主会话只编排，每阶段派干净 context 的 `longdev-implementer` 执行，`longdev-reviewer` 独立审查，全程无需逐阶段 `/clear`。
- 主会话亲自执行降级为例外（阶段标【主会话】时）。
- 状态载体为项目内 `.claude/longdev/PLAN.md`。
