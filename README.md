# longdev

Claude 长程开发插件，包含两个执行方式：

- **longdev**：按风险和依赖拆分长任务，逐阶段实现、独立审查、主会话 gate、整体检查和验收。
- **autopilot**：在已确认目标、授权和预算内自主迭代，每轮使用 longdev，由获授权的 acceptance 核对产品验收项。

## 工作机制

共享协议位于 `skills/longdev/references/execution-protocol.md`：需求和验收有稳定编号，PLAN 作为索引，阶段入口与实际记录分开；基线涵盖任务相关的既有改动和未跟踪文件，证据对应当前产物状态。

实现结束只进入待检查；独立 review 和主会话 gate 通过后进入检查通过。整体检查后提交待验收，只有用户接受或有效代理验收授权才标已验收。恢复时检查实际产物和证据，不只看完成标签。

阶段按耦合、风险和可验证性拆分；模型默认继承。按需读取资料，摘要链接完整证据；错误日志保留，修改后重验受影响部分。已有授权不重复确认，范围外想法只进入观察区。

自主模式逐项核对产品 V 全集，报告缺失、重复、过期与未验证项。本轮任务只以明确选定目标及回归为必需子集。隔离项保留失败及依赖，独立子集可以交付，整体未达成不能写成成功。停止原因区分目标达成、预算停止、候选耗尽和受阻。

## 使用与维护

插件清单位于 `.claude-plugin/marketplace.json`，插件版本唯一来源是 `.claude-plugin/plugin.json`，变更记录在 `CHANGELOG.md`。仅查看或修改本插件的请求不应触发产品开发循环。

本目录作为 harness 的 Git submodule 使用，origin 指向 `https://gitee.com/xicun/longdev-plugin`。插件文件在这里独立提交并推送；父仓库只更新子模块 commit 指针，不重复收录文件。发布父仓库指针前确认插件 commit 已能从 Gitee 获取。

## 结构

| 路径 | 用途 |
|---|---|
| `skills/longdev/` | 阶段编排、共享执行协议、计划与阶段模板 |
| `skills/autopilot/` | 产品循环、宪章问卷、backlog 与迭代模板 |
| `agents/` | scout、planner、implementer、reviewer、decider、final-reviewer、product-owner、acceptance |

验证分为文件结构/一致性检查、场景推演和实际 Claude 执行。前两者不能证明第三者已通过，也不能证明长期质量收益。