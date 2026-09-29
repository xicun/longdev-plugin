# 阶段 1 独立复审与检查

**日期**：2026-09-29  
**结论**：独立审查通过（本报告限定的流程、技能和安装范围）；主会话仍须执行 gate。  
**审查者独立性**：未参与本报告所审查的流程/角色/模板/安装器实现；曾实现兼容 Python，因此本报告明确不审查、不背书兼容 Python 的正确性。  
**写入范围**：只写本报告；测试日志与指纹放项目 `.work/`，未改实现或 PLAN。

## 范围与依据

从用户原始目标、PLAN 的 R01–R03/V01–V04 及追加的工具/循环要求形成检查，再核对当前实际文件及上轮 `reviews/stage-1.md`。覆盖 requirements-design 独立技能、设计角色/planner/testcases/product-owner/reviewer、longdev/autopilot 入口、共享协议、分析设计/PLAN 模板、`scripts/install.py` 与 `tests/test_install.py`。兼容接续仅审查事实源、编号、授权和单任务调用契约，不包含兼容脚本独立验收；父仓库分层部署也不在本报告范围。

实现者通知停止写入后开始最终检查；本次 13 个被检查产物在验证前后 SHA-256 相同。本报告以当前内容为准，不宣称缺失的阶段起点补丁可被 HEAD 替代。

## 上轮问题复核

| 上轮事项 | 当前证据与判断 |
|---|---|
| 独立 skill 入口缺失 | `skills/requirements-design/SKILL.md` 存在且独立可用；安装器 SKILLS/REQUIRED 纳入该技能及角色/模板，三端入口实测均携带完整 bundle 路径。通过。 |
| 唯一详细来源与旧记录复用冲突 | 技能、协议、planner 和模板统一要求优先保留既有需求/设计事实源；新文件只在需要且获授权时建立，已有来源只引用稳定 ID 和映射。通过。 |
| 空 stdout 被误判为工具失败 | 三入口/协议/reviewer 按协议、退出码及预期语义分类，`no output` 本身不等于失败；pending 走恢复接口，no tool 或无法确认执行成功才记异常/未验证。通过。 |
| 异常后擅自切模型 | 独立技能与共享协议明确保留用户选择，切换需要明确既有授权及能力核实。通过。 |
| R/V 重号与旧语义变更 | 技能、planner、协议及模板沿用已有稳定编号，只有新增项分配 ID；旧事实源与历史授权/证据不因插件升级重写。通过。 |
| 安装测试只断言角色存在 | 测试检查三端独立技能入口、包内源码等值、新旧入口升级、未知/用户编辑保留、缺依赖和只读完整性。9 项实际运行通过。 |

## 需求与场景核对

下表为独立静态场景推导，非模型在线运行或故障注入。

| V / 场景 | 期望与实际规则结论 |
|---|---|
| V01：独立讨论/设计技能 | 不要求 PLAN、迁移或任务目录；只有持久设计授权才写文件。方法与 agent 包装职责分离。格式校验及三端安装通过。 |
| V02/V03：设计章节完成但目标未完成 | 小结不构成等待；有充分信息则继续分析与映射。有实施授权且设计 gate 无关键缺口时转 planner；纯设计目标完成则交付结束。通过。 |
| V03：planner/testcases/PO/reviewer 接续 | planner 消费稳定需求/设计，testcases 在行为和 R/V 稳定后定义用例；PO 继续掌管产品目标/预算/backlog，设计角色只做已选任务；reviewer 可使用 design 模式。通过。 |
| V04：设计变更新增异常路径 | 先登记 C/R/V 和影响范围，旧证据按影响失效，更新用例及后续入口后重验；不静默降低标准。协议及 testcases 边界可导出此动作。通过。 |
| R04 流程范围：旧 PLAN 已有设计和 R07/V09 | 复用原路径与编号，仅补设计映射，不制造第二事实源；选中任务且授权/安全边界满足后由主会话自动调用单任务 compatibility CLI。通过（不含 Python 验收）。 |
| V12/V16：exit 0 且 stdout 为空 | 结合命令语义记正常成功，不转适配器失败、不重复调用。通过。 |
| V12/V16：工具有 session/task ID 且 pending | 用对应恢复接口继续原任务，不重新启动同动作。通过。 |
| V12/V13：no tool / 缺失响应且无法证实成功 | 保留原文、上下文、ID/退出码和影响；无新依据不重试，有依据最多重试一次，后续核对入口或交接具体阻碍，继续独立工作，不自动切模型。通过。 |
| V09/V16：成功验证已覆盖同产物 | 无产物/环境/验收变化时复用有效证据；独立职责仍须说明新增覆盖，不以实施者自测冒充独立检查。通过。 |
| V09/V16：ABCABC，各工具成功且有记录但回到同决策节点 | 协议按目标、未完成项、有效证据和产物是否实质变化判断；结束无进展调查链。已知缺口实施、已有覆盖由获权限角色转下一项、单一未知定向补查、具体依赖才受阻并继续独立项。表态/重写清单/mtime 不算推进。通过。 |
| V09/V16：同节点但新实验排除假设或产物改变 | 存在可核实推进，可继续合理迭代；不会被固定次数强行终止。通过。 |

## 独立执行证据

工作目录：`D:/Works/harness/longdev-plugin`。环境：Python 3.12，`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`；子进程均使用 `-X utf8 -B`，stdout/stderr 以 UTF-8 完整保存。

- `py -3.12 -X utf8 -B C:/Users/<local-user>/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/requirements-design`：exit 0，`Skill is valid!`。
- 同命令分别校验 `skills/longdev`、`skills/autopilot`：均 exit 0，`Skill is valid!`。
- `py -3.12 -X utf8 -B -m unittest tests.test_install -v`：exit 0，`Ran 9 tests in 6.917s`，`OK`。这些测试在 `.work` 隔离项目安装三客户端，不修改真实用户入口。
- 报告写入前 `task_path.py check --project "D:\Works\harness\longdev-plugin" --task "D:\Works\harness\longdev-plugin\docs\longdev\requirements-design-compatibility" --target "D:\Works\harness\longdev-plugin\docs\longdev\requirements-design-compatibility\reviews\stage-1-recheck.md"`：exit 0，`status=allowed`。此前使用正斜杠绝对路径被 guard 拒绝（exit 1），已按 Windows 规范路径重试，无绕过。

原始日志/命令/环境及验证前后指纹：`.work/longdev/requirements-design-compatibility/stage-1-recheck/manifest.json`，同目录 `validate-*.log` 和 `install-tests.log`。以下指纹及命令摘要随本报告携带，避免只依赖本机日志：

| 产物 | SHA-256 |
|---|---|
| `skills/requirements-design/SKILL.md` | `82004c751b474f10c19fb592b79c09766e4657a69f56c208a5bc9e9f524f218d` |
| `agents/longdev-requirements-designer.md` | `5c4a60e830ab21a3a95116cc3ba55553188fecf6b2765e4da5aee1f8abf81249` |
| `agents/longdev-planner.md` | `d1355da3d6c46976f399a9fcdd0e34a0f6537e63730eed839f375f321b7c2aa5` |
| `agents/longdev-testcases.md` | `fffb403a7419e7fbea0f8c525e009f6f29bb6cbad7dbf639ea2faa96be67634f` |
| `agents/longdev-product-owner.md` | `839308aedac7869faa44e2fadbcf0f97349be814ecf335455ea8609c5c02bfea` |
| `agents/longdev-reviewer.md` | `7128efbbad0f36cd6844650afef6830084a49da0a61757dc99837386dab9a6e0` |
| `skills/longdev/SKILL.md` | `0475f6eb74bbf3489b2189eaeaa72831dd0d9570ad5c2d746e7f739cc70e498d` |
| `skills/autopilot/SKILL.md` | `9861751ee96d6f8d6071ebc2beedd71b3af3a240ffe9a3195530bd60b1343a0c` |
| `skills/longdev/references/execution-protocol.md` | `8af2db0b7cf4b18e9bcecdc7c52c7c770d5d400e10fe38e26d892e02295ec2a0` |
| `skills/longdev/references/analysis-design-template.md` | `e669f0757b90c89ecfd08ff02bacf2b57957ad06a61580399b749ed71ce5d8fb` |
| `skills/longdev/references/plan-template.md` | `38ddfd80c90487fe5678c9303de8dbc2becdf44e2d7b77a215ebc20d9fb1550b` |
| `scripts/install.py` | `f6dd4e994fab5c45dc5db1af446e5f5dfaf8f4c9a1e030a168a17ad12c3753fe` |
| `tests/test_install.py` | `6ab0214f7ebdf1db0ee03121f1cc04671aa8805d4f71d310b3d53f4a3a07b89a` |

## 限制与交接

本范围未发现阻塞。未使用 code-review 工具，以逐文件独立审查、静态场景推导和实际安装回归完成本范围检查。上轮 stage-1.md 的三个阻塞和三项建议已在当前指纹产物上复核解除；原报告保留为历史证据。

未运行 GLM/Codex 的真实模型回放，未验证自动 compact 或工具桥接的根因，也未证明长期任务中循环/中断已减少；本轮只交付流程护栏与诊断边界。安装器回归不代表三客户端真实模型已执行该技能。兼容 Python、父仓库分层发布、整体 gate、最终用户验收仍由各自独立范围处理。本报告不更新 PLAN 状态、不代替 gate 或用户验收。
