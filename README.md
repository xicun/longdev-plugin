# longdev

Claude Code、Codex CLI、dsh 共用的长程开发技能，包含两个执行方式。**收到仓库 URL 要求安装时，先读 [INSTALL.md](INSTALL.md)**，使用统一安装器并执行自检。

- **longdev**：按风险和依赖拆分长任务，逐阶段实现、独立审查、主会话 gate、整体检查和验收。
- **autopilot**：在已确认目标、授权和预算内自主迭代，每轮使用 longdev，由获授权的 acceptance 核对产品验收项。

## 工作机制

共享协议位于 `skills/longdev/references/execution-protocol.md`：需求和验收有稳定编号，PLAN 作为索引，阶段入口与实际记录分开；基线涵盖任务相关的既有改动和未跟踪文件，证据对应当前产物状态。

实现结束只进入待检查；独立 review 和主会话 gate 通过后进入检查通过。整体检查后提交待验收，只有用户接受或有效代理验收授权才标已验收。恢复时检查实际产物和证据，不只看完成标签。

每阶段 gate 通过并同步记录后，主会话默认自动本地 commit，只收录归属明确的阶段代码和记录，保护原有 staged/同文件他人修改。提交失败先解决，不静默积压；用户明确禁止提交优先，push 按独立授权办理。阶段提交由执行技能的 agent 完成，不是后台 Git hook。

持久任务记录使用 `docs/longdev/`、`docs/autopilot/` 随 Git 同步；备份、原始日志和图片使用 `.work/`。新版首次在当前项目启动/续接时自动运行迁移脚本，保留旧 `.claude/longdev/`、`.claude/autopilot/` 为只读保护副本；迁移后的 `docs/` 是唯一权威来源。冲突、忽略规则或并发写入会被报告；`status` 仅做只读探测。更新插件不扫描其它历史工作区。

v0.14 增加完整迁移预演：用户说“先预览迁移”“迁移 dry-run”时使用 `migrate_workspace.py --dry-run`，输出任务分类、引用依据、逐文件动作、冲突与 Git 前提且不写文件；`--check` 只给简短状态。活动记录迁入 docs，可靠结束且无未决引用的历史进入 `docs/<kind>/archive/`；旧入口原始副本进入 `.work/`，未知和冲突保留报告。所有角色使用解析后的绝对 `TASK_DIR`，写前通过 `task_path.py check` guard。

阶段按耦合、风险和可验证性拆分；模型默认继承。按需读取资料，摘要链接完整证据；错误日志保留，修改后重验受影响部分。已有授权不重复确认，范围外想法只进入观察区。

自主模式逐项核对产品 V 全集，报告缺失、重复、过期与未验证项。本轮任务只以明确选定目标及回归为必需子集。隔离项保留失败及依赖，独立子集可以交付，整体未达成不能写成成功。停止原因区分目标达成、预算停止、候选耗尽和受阻。

## 使用与维护

市场清单位于 `.claude-plugin/marketplace.json`；`.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json` 版本必须同步，技能开工从前者读取版本，变更记录在 `CHANGELOG.md`。仅查看或修改本插件的请求不应触发产品开发循环。

本目录作为 harness 的 Git submodule 使用，origin 指向 `https://gitee.com/xicun/longdev-plugin`。插件文件在这里独立提交并推送；父仓库只更新子模块 commit 指针，不重复收录文件。发布父仓库指针前确认插件 commit 已能从 Gitee 获取。

## 多客户端安装边界

共享底层是 `skills/` 下的标准 skill；不同客户端只提供安装入口和运行时适配。当前目录同时提供 `.claude-plugin/` 和 `.codex-plugin/` 清单，dsh 通过 `adapters/dsh/` 同步共享 skill。

- **Codex CLI**：使用 `.codex-plugin/plugin.json` 加载 `skills/`。Codex 插件安装后仍需核对 `agents/`、hooks、MCP 和权限能力；本插件的核心流程只依赖 skill、项目文件和普通工具，因此不要求 Claude 专属 agent 才能运行。
- **dsh**：统一安装器保存完整共享包，在 `.dsh/skills/` 生成薄入口；`adapters/dsh/install-dsh.ps1` 只是同一安装器的 PowerShell 包装。不会复制成缺失角色/版本文件的裸 skill。
- **跨客户端**：安装只是加载指令，不能共享会话历史。三个客户端必须指向同一项目目录和同一 `docs/longdev/<任务>/`，通过 `PLAN.md`、`context/current.md`、阶段记录和证据交接。

三端统一安装及可选 Codex 原生插件命令见 [INSTALL.md](INSTALL.md)。核心规则在 skills/，角色职责在 agents/，安装逻辑只有 scripts/install.py 一份；协议所说的租约和自动重启尚无运行器实现，安装不等于自动无限循环。

安装完成后至少验证：skill 能被发现、`references/` 能读取、当前客户端的工具/权限可用、模型能力档案已确认，以及跨会话交接文件可以读写。未完成这些检查前保持“已安装、未验证”，不宣称 longdev 已兼容该客户端。

## 结构

| 路径 | 用途 |
|---|---|
| `skills/longdev/` | 阶段编排、共享执行协议、计划与阶段模板 |
| `skills/autopilot/` | 产品循环、宪章问卷、backlog 与迭代模板 |
| `agents/` | scout、planner、implementer、reviewer、decider、final-reviewer、product-owner、acceptance |
| `skills/longdev/scripts/migrate_workspace.py` | 当前工作区迁移、只读探测、冲突/忽略检查与中断恢复 |

验证分为文件结构/一致性检查、场景推演和实际 Claude 执行。前两者不能证明第三者已通过，也不能证明长期质量收益。
