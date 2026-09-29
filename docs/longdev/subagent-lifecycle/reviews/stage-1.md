# 阶段 1 独立审查

审查者：`workflow_review`；日期：2026-09-29。未参与本轮四文件实现，采用人工式独立审查；未使用不存在的 code-review 技能。先读取 PLAN 的 R01–R05/V01–V05、原始场景输入、角色和共享协议，再检查实际 diff，最后核对实施说明与验证证据。

结论：本轮协议改进审查通过，未发现阻塞问题；静态审查、16 项独立场景应用证据和安装回归证据均已核对。当前不代替主会话 gate 或用户验收。只审查本轮生命周期协议，不重启历史维护任务。

## 覆盖与判断

| 需求/验收 | 独立判断与依据 |
|---|---|
| R01/V01 | 共享协议第 137 行同时限制职责、任务链、权限/写入范围。实现返工可匹配复用，独立 reviewer 对修订产物可复用；实现者改名、换角色仍不能承担该产物的独立 checker/reviewer/acceptance。旧任务有未完成写入时不能借同仓库、同角色之名接入无关任务。入口未产生相反调度规则。 |
| R02/V02 | 第 132、138–139 行要求实际产物、有效证据、剩余事项及可恢复交接，并检查代理及其发起的在途操作已结束。final/idle/interrupt 成功不证明安全停止或关闭。缺成果时不能安全回收；仍写测试结果的工具也在核查范围内。暂留必须指定下一动作与可观察复核点，review/gate 后无返工不得无限延期。 |
| R03/V03 | 第 134–140 行区分工作完成、关闭待确认、已关闭和容量可用。容量不能只由 close 名称、final 或 idle 推断。槽位不足先安全回收，再匹配复用，再等实际工作；无运行工作或缺关闭能力时记录缺口并推进独立可行部分，独立审查仍待检查。失败/pending 无新状态不能构成重复 spawn/close/list 的循环。 |
| R04/V04 | 第 139–141 行覆盖阶段、迭代及最终盘点，并要求复用/resume 前重核项目、任务、职责、目标、授权、最新文件与证据。旧 ID 不存在不证明旧工具停止；结合安全交接条款和 runtime 会话切换约束，不能建立并行写入者。旧任务只补可核实当前状态，不补造历史代理表、不改历史语义。 |
| R05/V05 | 完整生命周期规则仅在共享协议；longdev/autopilot 各新增一段链接，runtime 仅核实接口及回执语义。链接目标和标题存在。runtime 明确主会话 CLI 不是子代理接口，不猜 close/interrupt/resume 语义，不用 kill、删记录或构造命令冒充回收。未引入执行运行器或修改任务授权/验收状态。 |

## 当前产物与证据

基线为 `d49d071`。独立核对 `.work/longdev/subagent-lifecycle/baselines/` 的四文件，均与该提交对应 blob 逐字节一致。实际 diff 仅新增 2、2、20、6 行，原有模型选择、独立审查、共享写入及连续性约束保留。当前 SHA-256 与阶段执行记录、主会话安装回归记录一致：

| 文件 | SHA-256 |
|---|---|
| `skills/longdev/SKILL.md` | `b82baadf158d19a584ba097c569406024f2e1bedca6446f6ea7ab7ec82354f01` |
| `skills/autopilot/SKILL.md` | `d9a1f5a7f100aa61f2917d1c86eb4f15bf26e369171a746f3128266b91e66d9a` |
| `skills/longdev/references/execution-protocol.md` | `2f661398a1c8b51b624865d90a4a67981a085f56a3d1de948c8bc3749f2846e2` |
| `skills/longdev/references/session-runtime.md` | `6dce2f94e55b46d29a2f2c8d8ca0c50b680b9a80404bbcd02b2c351b3e362e41` |

复用并读取 `.work/longdev/subagent-lifecycle/gate-install.json` 与 `gate-install.log`：主会话以 Python 3.12 `-X utf8 -B -m unittest discover -s tests -p test_install.py -v` 执行 9 项安装行为测试，退出码 0、9 项通过，前后源指纹不变。没有重复运行该组测试。该证据覆盖安装、升级、旧回执及用户修改保留，不证明宿主关闭或容量释放。

定向复核独立 checker 的 `evidence/forward-test.md`（SHA-256 `69eeb9804db7a504187b539d7e0a3ed683f15f478442ea71c94c40aa1f9e56ee`）：16 个编号覆盖原题全部情形，四源文件指纹与本审查一致，场景输入指纹 `81d985686e409d6875a4d6f4f8cdb2d17586cd9b1cc0c51a4097e7a7e210cb46` 与实文件一致。双槽题的 0–16 步确实覆盖六项工作，开放数为 0→1→1→0→1→1→2→2→2→2→2→2→1→0→1→1→0；返工/复查分别复用 A-I1/A-C1，没有实现者自审，关闭成功明确是题设分支条件。第 8–11 题没有将失败、interrupt、pending、closed 无遥测误记为槽位释放；第 12 题 not found 仍要求核实旧工具停止；第 14–16 题保留未知归属、旧任务语义、原授权及产品状态。未发现演练答案与协议冲突，也没有用模拟结果宣称真实宿主已通过。

写入本报告前执行 `skills/longdev/scripts/task_path.py check --project D:\Works\harness\longdev-plugin --task D:\Works\harness\longdev-plugin\docs\longdev\subagent-lifecycle --target D:\Works\harness\longdev-plugin\docs\longdev\subagent-lifecycle\reviews\stage-1.md`，返回 `allowed`、退出码 0。

## 边界与交接

当前宿主没有显式 close 接口，本审查未创建真实代理执行占槽实验，未证明真实关闭、释放、长期协作改善或 GLM 实效。BUG-0004 保持待真实验证，规则改进不能冒充原始宿主症状已修复。场景演练也不能替代实际运行；用户验收、主会话 gate 和问题关闭权限保持原协议边界。

本 reviewer 已完成报告并停止写入，没有本轮在途工具或文件写入；成果与证据以上述路径交接给主会话执行 gate。当前无明确审查返工任务，主会话按实际宿主能力处理回收；本报告不宣称 reviewer 槽位已释放。
