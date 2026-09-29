# 插件最终独立审查与 checker 结果

日期：2026-09-29。**结论：本报告限定的插件范围独立审查通过。** 主会话仍须同步任务记录并执行 gate；本报告不代表父仓库检查通过、真实客户端已升级或用户已验收。

审查者未实现插件的流程/技能/角色、安装器或兼容 Python；曾实现父仓库分层安装器，因此不对父仓库实现提供独立背书。本次只写本报告与 `.work` 验证证据，没有改插件产品、PLAN 或真实用户配置。未调用 code-review，采用逐文件控制流/接口核对、既有独立证据指纹复核和实际 smoke 验证。

## 需求范围与接缝核对

| 原始要求 / R、V | 当前结果与证据 |
|---|---|
| 可独立使用需求分析与设计技能，R01 / V01,V02 | `skills/requirements-design/SKILL.md` 有独立入口；方法由该文件维护，agent 包装定义写入与交接。`scripts/install.py` 将技能、角色和模板列入完整包必需项，三端安装测试实际通过。 |
| 连续形成完整结论/可评审方案，R02 / V02,V03 | 纯讨论不建 PLAN 或调用迁移；章节/小结不构成停顿。已有实施授权且设计 gate 无关键缺口才继续 planner，纯设计目标完成则结束；没有增设例行人工审批。 |
| planner/testcases/reviewer/PO 协作，R03 / V03,V04 | 既有需求/设计来源和 R/V 继续有效；planner 只消费并索引，testcases 在行为/R/V 稳定后设计用例，reviewer 可做 design 审查，PO 继续拥有产品目标和预算。变更需登记 C/R/V 和受影响证据，不能复用已失效验证。 |
| 旧内容与旧证据继续有效，R04 / V05–V07 | flow 在唯一任务已选、授权已明确、旧写入者停止后调用 standalone `compatibility_upgrade.py`，使用项目相对 task 路径。脚本只建立初始不可变旁车，不改 PLAN/CHARTER、R/V、授权和历史证据，不自动采纳新流程；终态不重开。状态不明或显式未知格式保留待核对。 |
| 低 context 循环与 compact 恢复，R06 / V09,V10 | 只采信可见水位，不臆造触发阈值或把手动 compact 恢复当根因证明；通过现有交接协议保存任务/证据/下一动作。没有把 skill 描述成自动 compact、重启或请求拦截器。 |
| 充足 context 下 no output/no tool，R08 / V12,V13 | 按工具协议、退出码及预期语义区分正常空输出、带 ID 的 pending 和缺失响应/适配器异常；pending 恢复原会话，不重复启动；失败无新依据不重试，有依据最多重试一次。异常不自动授权切换用户选择的模型/客户端。 |
| 成功动作亦反复循环，R10 / V16 | 规则要求每次调用前明确待判定项、结果后物化结论和下一动作；已有有效证据未变则复用。共享协议进一步识别不同动作形成的同决策节点循环，优先转实施、交付或独立工作，只有具体依赖缺口才阻塞。以上属于静态流程约束，不是模型实效证据。 |

跨阶段接口逐项核对：独立讨论技能不经过迁移；longdev/autopilot 在正确安全交接点使用单任务入口；`migrate_workspace.py --task` 仍会工作区盘点，技能已明确不能用它替代 standalone；安装完整 bundle 携带共享 helper、角色和设计模板，相对引用可在 bundle 内解析。项目安装器内容指纹命名旧包保留，入口更新需旧 receipt 哈希匹配，用户编辑和未知内容会报冲突。

## 复用的独立证据

- `reviews/stage-1-recheck.md`：13 个流程/技能/模板/安装产物的 SHA-256 与当前一致，原独立格式校验、9 个安装测试及静态场景结论继续有效。它解除初次 `stage-1.md` 的三个阻塞；本次未重复单项 skill 校验。
- `reviews/stage-2.md` 的“F01 修复复查”：当前四个指纹与最新复查一致。完成态 journal 现在先校验 schema、receipt/profile、编码哈希，再比较发布旁车的完整字节；初始快照不与后续正常演进的 PLAN 强制相等。本次完整 smoke 再次执行了 19 个兼容测试，包括五类 complete 篡改、缺 journal、apply/check/dry-run 保护及中断恢复。

| 兼容产物 | 当前 SHA-256 |
|---|---|
| `skills/longdev/scripts/compatibility_upgrade.py` | `f1f20954c15495458e1803768b9c9143730680952f158f25b515e01da517e58c` |
| `tests/test_compatibility_upgrade.py` | `d4b73fe0a46aa5dadf5424a5c34e9ced011c0725e22c3c4e4456bbe1f418250c` |
| `skills/longdev/scripts/migrate_workspace.py` | `61bca60eb04dba7f3b6c6c99ee452ae9c3f6409c0c3a0b1f3ae48ea84e460938` |
| `skills/longdev/scripts/history_convergence.py` | `5aa44bf2f835d27a8392fd72eb633875b0ca6c5515f63523a90f93f780cdb392` |

## 本次独立 checker

工作目录：`D:/Works/harness/longdev-plugin`。环境：Python 3.12.10、Windows 11，`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。

命令：`py -3.12 -X utf8 -B skills/checks/scripts/check_runner.py --catalog-root testcases --source-root . --profile smoke --output .work/checks/requirements-design-final`。

结果：runner **exit 0**；`plugin-unit-tests` expected/actual exit 均为 0。smoke 本身引用一个 catalog case，该 case 实际执行完整 `unittest discover -s tests -v`，**87 个测试通过，95.819 秒，OK**。它覆盖兼容 19 个测试、安装 9 个测试及现有迁移、问题档案、租约、路径和通用 runner 回归；没有把“一个 case”误写成一个单元测试。用例子进程通过继承 UTF-8 环境处理中文输出。

原始证据：

- `.work/checks/requirements-design-final/manifest.json`：命令、环境、时间、case、退出码与日志路径。
- 同目录 `fingerprints.json`：catalog 输入及 stdout/stderr 哈希；该 runner 文件未记录产品源码哈希，不能把它单独称为完整源码基线。
- 同目录 `source-manifest.json`：本次检查结束时的插件产品/测试文件 SHA-256，补充当前产物定位，不冒称阶段起点快照。
- `cases/plugin-unit-tests/stdout.txt`、`stderr.txt`：完整原始输出；stderr 中兼容新增篡改和缺 journal 测试均明确 `ok`。
- `git diff --check`：exit 0。Git 提示的现有 LF/CRLF 规范化警告不构成空白错误。
- 写报告前 `task_path.py check`：规范 Windows 绝对项目/任务/报告路径，exit 0、`status=allowed`。

## 限制与交接

本插件范围未发现新的实现阻塞。`.work` journal 不保证跨机器随 Git 存在；只有合法旁车而无本地 journal 时，脚本保留原文并返回 `needs_review`，不伪造新的校验依据。这是已明确的保护限制，不能宣传为跨机器自动恢复全部通过；旧任务原文和有效业务证据并未因此被改写或清除。

没有运行 Codex + GLM5.3 Flash 实际模型回放，没有验证 compact 调度、工具桥接故障的根因或长期循环减少；这些仍需用户真实部署遥测/后续任务观察。当前源代码和隔离安装测试也不代表原生插件已发布、真实用户入口已升级，版本发布/安装需遵循相应流程。

主会话下一步：同步仍写“待执行/修正中”的 PLAN/阶段记录与本报告、阶段复查的实际状态；纳入父仓库独立审查与新增软链迁移范围后执行最终 gate。不要把本报告的插件通过扩大为父仓库通过或整体用户验收。
