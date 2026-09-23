# 阶段 2 主会话 gate

日期：2026-09-23。

结论：V08 检查通过，原生安装与缓存可运行；阶段 2 进入限定收尾提交。独立报告 `reviews/stage-2.md` 通过，版本 `0.14.0+codex.20260923183000` 的双 manifest、缓存脚本指纹、插件启用状态和真实缓存 fixture 均已核对。

证据：`codex plugin add longdev@zzm-plugins --json` 成功；`codex plugin list --json` 显示 installed/enabled；plugin validator 通过；缓存 `migrate_workspace.py`、`history_convergence.py`、`workspace_common.py`、`task_path.py` 的 SHA-256 与源码一致；缓存 fixture 通过迁移、dry-run 和 guard。PATH alias 权限警告已记录，不影响插件缓存可发现性。

限制：未在 Windows 真机验证 junction/reparse/锁，未验证新会话长期遵循；Gitee 推送作为已授权的子模块发布动作单独执行并核对远端 SHA。阶段 2 不代替用户验收。
