# 阶段 1 主会话 gate

日期：2026-09-23。

结论：阶段 1 检查通过，进入限定本地提交。独立审查报告 `reviews/stage-1.md` 结论通过；主会话复核需求 R01–R08、V01–V07/V09，确认 dry-run 与正式迁移共用计划构建，且只读预览不创建锁、journal、marker 或修改 Git index。

证据：

- `python3 -B -m unittest discover -s tests -v`：36 项通过，退出码 0。
- `git diff --check`：退出码 0。
- `.work/history-convergence/native_probe.py`：真实 CLI fixture 验证 dry-run 字节/目录时间/index 不变、活动任务迁移、结束任务归档、portable evidence、跟踪前保留旧源、跟踪后收敛、未知客户端内容保留及 guard；退出码 0。
- 双 manifest 已由 plugin-creator validator 校验，版本为 `0.14.0+codex.20260923183000`。

范围核对：迁移只处理当前工作区；unknown、客户端配置/skills/runtime、冲突和证据缺口保留并报告。阶段 1 不宣称本机原生安装、缓存刷新、Gitee 发布或 Windows 真机通过；这些属于阶段 2/V08。

提交授权：按用户已授权的 longdev 子模块阶段提交约定，仅提交本阶段源码、测试、协议/角色/文档、manifest 和任务记录；不提交 `.work` 测试产物，不修改或发布父仓库。
