# 阶段 1 独立审查：需求分析与设计流程衔接

**阶段**：1  
**任务**：`docs/longdev/requirements-design-compatibility`  
**审查模式**：阶段 1（含设计输入、角色衔接、安装打包和静态场景）  
**审查者**：独立 reviewer  2026-09-29  
**基线**：`.work/longdev/requirements-design-compatibility/baselines/task-start/`（仅保存 `head.txt`；未提供完整工作区补丁，故不能精确区分阶段改动与既有改动）

## 审查范围与方法

审查了阶段 1 的 PLAN/stage 入口、`longdev` 技能、共享执行协议、需求设计者/planner/testcases/reviewer 角色、两个模板、安装器和安装测试。独立执行了：

- `py -3.12 -X utf8 -B C:/Users/<local-user>/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/longdev`：通过（`Skill is valid!`）。首次未显式指定 UTF-8 时因 Windows 默认 GBK 解码失败，属于验证环境问题，使用 UTF-8 重跑通过。
- `py -3.12 -B skills/longdev/scripts/task_path.py check --project "D:\Works\harness\longdev-plugin" --task "D:\Works\harness\longdev-plugin\docs\longdev\requirements-design-compatibility" --target "D:\Works\harness\longdev-plugin\docs\longdev\requirements-design-compatibility\reviews\stage-1.md"`：通过，允许当前报告路径。
- 在隔离 `.work/scenarios/design-review-kgphbod2` 中调用 `scripts/install.py` 的 `codex` 安装路径：通过生成版本化 bundle；bundle 内包含 `agents/longdev-requirements-designer.md`，但客户端入口仍只安装三个既有 skill。

本轮未执行兼容 Python 迁移脚本测试，也未改动迁移脚本和兼容测试；这些属于阶段 2 范围。

## 需求与验收覆盖

| 需求/验收 | 结果 | 证据与说明 |
|---|---|---|
| R01 / V01：新角色职责、输入输出、路径 guard | **部分通过** | `agents/longdev-requirements-designer.md` 有 frontmatter、输入、写入边界、输出最低要求和 guard；安装器 bundle 含该角色。独立可发现技能入口缺失，见阻塞 1。 |
| R02 / V02：连续分析、设计 gate、planner 单一输入 | **部分通过** | `SKILL.md`、协议、角色和模板均写明连续推进、gate 和 planner 消费设计记录；但“唯一详细来源”的绝对表述与旧任务等价记录复用规则冲突，见阻塞 2。 |
| R03 / V03：planner/testcases/reviewer 衔接 | **通过（静态）** | planner 声明不重复泛化讨论；testcases 依赖稳定设计输入；reviewer 有 `design` 模式及独立检查项。尚未有独立 forward-testing 产物验证真实角色决策。 |
| V04：设计变更使 R/V/证据可追踪 | **部分通过** | 协议有 C 编号、受影响证据失效和重验要求；阶段入口仍待实现记录与 gate，不能据此宣称完整通过。 |

## 发现的问题

### 阻塞 1：新增角色没有可独立使用的 skill 入口（高）

用户要求的是“需求分析和设计人员的角色技能”。当前实现只新增了插件根目录 `agents/longdev-requirements-designer.md`，没有新增 `skills/<name>/SKILL.md`、入口元数据或安装器的 skill 名单。隔离安装实测 `project/.agents/skills` 只有 `autopilot`、`bug-reports`、`longdev` 三个入口；虽然 bundle 中携带 agent 文件，但宿主无法把它作为独立技能发现/调用。

这使 V01 的“安装 bundle 检查”和“可独立使用”未满足，也会导致需要直接使用需求分析设计能力的任务只能依赖 longdev 内部派发。应补充独立、可发现的 skill 入口，或在需求记录中明确把“角色”而非“技能”作为已批准的交付定义并补齐相应验收；当前用户语义支持前者。

### 阻塞 2：单一详细来源与旧任务等价记录规则互相冲突（中高）

以下文本同时存在：

- `skills/longdev/SKILL.md` 和协议称 `notes/analysis-design.md` 是需求与方案的“唯一详细来源”；
- planner、设计者和模板又允许旧任务直接使用“等价历史记录”，且不强制迁移/重写。

旧任务保留原路径时，实际详细来源就不是 `analysis-design.md`；若强行要求唯一文件，则会违反本轮“旧内容继续有效、不重写历史”的兼容目标。应改成“新任务的推荐详细来源；旧任务以已声明的等价记录为来源，通过索引/旁车记录统一引用”，并定义一项任务只有一个生效来源，禁止并存分叉。

### 阻塞 3：空 stdout 被写成工具失败，正常命令结果会被误判（高）

协议、`SKILL.md`、需求设计者和 reviewer 将“工具返回空 / no output / no tool / 未返回预期结果”放在同一失败分类中。`no tool` 或适配器错误确实应记录为运行时失败；但 `git diff` 干净、`rg` 无匹配、`Get-Content` 空文件、命令成功但没有 stdout 都是正常结果。当前规则没有先区分“进程/工具调用成功且 stdout 为空”和“工具桥接没有返回结果”，会把正常空输出引向重读、交接或受阻，反而可能诱发用户描述的循环。

应明确判断顺序：先记录调用是否实际执行、工具协议是否返回结构、退出码/错误流；`exit=0 + 空 stdout` 只能记录为正常空结果，按命令语义决定是否有事实；只有缺少工具响应、`no tool`、适配器异常或非零失败才进入运行时失败护栏。该修正不对 GLM 作能力结论。

### 建议 4：工具失败后的“切换模型”没有把用户授权写成硬前提（中）

协议和 reviewer 使用“在已有授权和能力核实后切换客户端/模型”。这比无条件切换安全，但没有明确“模型切换仍需用户既有授权；能力核实不能产生授权”。用户明确要求不可未经授权切换模型，建议补充：若没有预先授权，记录受阻/待决定并继续独立工作；模型切换只在授权范围内执行，并记录原因、模型和受影响 V。这样不会把运行时异常自动转成外部配置变更。

### 建议 5：旧任务 R ID 的“稳定候选”缺少冲突/重号判定（中）

设计者模板从 `R01` 开始，planner 也用 `R01` 作为示例，但迁移规则只说“抽取稳定 R/V”。没有明确旧任务已有 `R01`、新增分析记录也生成 `R01` 时必须沿用旧语义、从最大编号继续或建立映射。自动升级若按模板重新编号，会造成 R/V、review 和历史证据断链。

建议规定：旧任务已有 R/V 是不可重编号的事实；新增需求沿用现有命名空间继续编号，若无法可靠识别则保留原文并标未知/受阻，不自动猜测；分析设计中的候选 ID 只能在 planner 确认后映射到稳定任务 R ID。

### 建议 6：安装测试只断言角色文件存在，没有断言独立入口或入口清单一致（中）

`tests/test_install.py` 已断言 bundle 包含 `agents/longdev-requirements-designer.md`，但没有断言：独立技能目录存在、安装器 `SKILLS`/`REQUIRED` 与实际新入口一致、三个客户端入口能发现该能力。测试因此会在“角色随 bundle 携带但不可独立调用”时通过。

## 已通过与限制

- 新角色明确不改业务代码、PLAN、review/gate 和共享测试库，并要求使用 `task_path.py` guard 后写分析记录。
- 连续推进停止条件基本覆盖“阶段小结/章节结束不构成暂停”，并把真正关键意图、重大取舍、外部影响和授权缺口列为提问条件。
- reviewer 的 design 模式检查事实/决定/假设/待决、可行性证据、兼容策略和 planner/testcases 输入，方向符合需求。
- 静态 skill quick_validate 和隔离安装 bundle 已验证；未运行插件完整 unittest/checks，也未验证 GLM/Codex 实际运行时行为。规则只能提供诊断和停止护栏，不能宣称修复客户端 compact 或工具桥接实现。

## 结论

**有阻塞，阶段 1 不能通过 gate。** 需求分析角色的内部职责与流程衔接已有可审查内容，但交付缺少可独立发现的 skill 入口；同时单一来源规则和旧记录复用、正常空 stdout 和工具桥接失败之间存在会导致兼容性/循环的新歧义。先修复阻塞 1–3（至少明确空结果分类和来源契约），再复查 V01–V04；阶段 2 迁移脚本不应在阶段 1 未通过时宣称兼容性完成。

**报告写入**：本文件。主会话仍需执行 gate；本报告不改变 PLAN 状态、不改变 R/V 状态、不替代用户验收。
