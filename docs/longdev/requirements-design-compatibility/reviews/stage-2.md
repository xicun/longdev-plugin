# 阶段 2 独立审查：兼容旁车

当前结论（2026-09-29 复查）：**本报告范围独立审查通过，F01 已修复**。见末尾复查证据及限制；此结论不代替主会话 gate 或用户验收。

初次审查历史（2026-09-29）：**有阻塞**。当时 R04 / V05–V07 部分已有有效证据，但完整性与冲突保护存在可复现缺口，不能判阶段通过。以下初次结果对应旧指纹，保留作为修复依据。

审查者未参与兼容 Python 实现；此前仅实现 flow 文档。本报告依据用户原始兼容目标、当前代码与独立执行结果，不以实现者完成声明作为通过依据。任务阶段 2 入口文件尚不存在，审查范围由主会话明确派发及 PLAN 的 R04/V05–V07确定；主会话仍须补齐阶段记录和 gate。

## 对象与方法

- 对象：`skills/longdev/scripts/compatibility_upgrade.py`、`migrate_workspace.py`、`history_convergence.py` 的本轮改动，以及 `tests/test_compatibility_upgrade.py`。
- 从来源读取、状态/格式识别、路径限制、journal、发布、重复调用到 CLI 退出码追踪控制流，并核对共享 `safe`、Git 忽略/跟踪函数。
- 独立执行：工作目录为插件根；`PYTHONUTF8=1`，`py -3.12 -X utf8 -B -m unittest tests.test_compatibility_upgrade -v`，17 项全部通过，exit 0。工具原始执行记录 chunk `ddb820`，耗时 8.481 秒。
- 补充实验在插件 `.work/` 下的 `TemporaryDirectory` 中创建隔离 Git 仓库，通过真实独立 CLI 验证只读边界，并对已经完成的事务分别注入旁车哈希和 journal 哈希变更。实验不修改产品代码或真实任务。原始执行记录 chunk `e495ce`，exit 0（实验命令成功，不代表全部预期通过）。

## 阻塞 F01：完成后的 journal 未验证快照完整性

关联：R04 / V06,V07。严重度：高，阻塞本阶段。

位置：`compatibility_upgrade.py` 的 `_pending` 中 `state == "complete"` 分支，以及 `build_plan` 的 `elif existing.exists()` 分支。

当前 `_pending` 只确认目标文件存在便返回 `None`；没有验证该 journal 的 receipt 与 sha256，也没有比较目标旁车与完成事务的快照。随后 `_validate_receipt` 仅检查结构和哈希字符串形状，因此看似合法的篡改被认作 `current`。

最小复现：

1. 在隔离仓库建立 `docs/longdev/receipt/PLAN.md`，内容为 `status: in progress` 和一条原始授权，调用 `upgrade(..., task="docs/longdev/receipt")` 成功。
2. 仅将生成 `COMPATIBILITY.json` 中 `source_sha256["docs/longdev/receipt/PLAN.md"]` 改为 64 个 `0`，其他字段和源文件不改。
3. 调用 `upgrade(..., task=..., check=True)`：实际 `current`，预期 `needs_review`。
4. 在另一任务重复正常升级，仅将 `.work/longdev-migration/compatibility/<task-hash>.json` 中 complete journal 的 `sha256` 改为 64 个 `0`：实际仍 `current`，预期 `needs_review`。

影响：原 PLAN 未被覆盖，但不可变来源快照的完整性与冲突检测承诺未满足；既有测试只覆盖 applying 中断与明显不合法/未来格式，没有覆盖 complete 后的合法形状篡改。

建议修复：有本地 complete journal 时验证其 receipt/sha256 及目标快照一致性，异常保留原文并返回 `needs_review`；比较对象应为初始旁车，不得拿正常演进的当前 PLAN 哈希去否定历史快照。跨机器没有本地 journal 时明确可验证边界，不把旁车结构校验冒称初始完整性已独立验证。增加以上两项行为回归，再复查恢复及正常演进。

## 通过与限制

| 验收 | 证据与实际结果 | 结论 |
|---|---|---|
| V05 状态和旧记录保留 | 17 项测试含待验收、带待验收限定的 completed、已验收、无版本标记；完整状态精确匹配，限定状态 needs_review，原字节保留 | 已覆盖这些样本；终态识别不等于验收证据核实 |
| V06 幂等/恢复 | 17 项含发布前中断、来源/目标变化、恢复，发布后中断及后续来源演进；正常演进补充实验 `current` 且初始旁车字节不变 | 对已测路径通过；F01 阻塞整体完整性 |
| V06 真实 CLI 只读 | `compatibility_upgrade.py --project <fixture> --task docs/longdev/readonly --check` 和 `--dry-run` 均 exit 1、pending；逐文件 bytes+mtime 快照完全相同 | 通过 |
| V06 忽略目标 | 将目标 COMPATIBILITY.json 加入 Git ignore；实际 needs_review 且无目标文件生成 | 通过 |
| V07 格式与来源信息 | `_source_text` 拒绝显式 schema/profile 声明；receipt 含插件版本、unknown 来源版本、unversioned 格式、unchanged adoption、来源哈希；未来 receipt schema/profile 测试保护原文 | 格式边界通过；F01 表明完成后哈希可信性不足 |
| 单任务入口/flow 契约 | standalone 接受项目相对 `docs/longdev/<id>` / `docs/autopilot/<id>`；补充 autopilot CHARTER 实验 upgraded；无 --task 的 API 不扫描，其他任务不生旁车；flow 选中授权任务并停写后调 standalone | 通过；任意编辑器停写由编排保证，锁不覆盖所有编辑器 |
| 工作区迁移包装 | `migrate_workspace.py` 仍先 converge，再 upgrade；无 task 不做旁车。flow 明确单任务旁车不用此包装入口，以免盘点其他任务 | 与当前 flow 契约一致 |

正常后续源码/需求变化不重写旁车是预期行为，不能用“不等于当前源哈希”直接判异常。快照也不是当前状态、设计通过或用户验收的证据。

## 审查产物指纹

| 文件 | SHA-256 |
|---|---|
| compatibility_upgrade.py | c974b142f625da1adbffacc20c469bd36d1e058ee6221d4e66ebadcedfbfc2eb |
| migrate_workspace.py | 61bca60eb04dba7f3b6c6c99ee452ae9c3f6409c0c3a0b1f3ae48ea84e460938 |
| history_convergence.py | 5aa44bf2f835d27a8392fd72eb633875b0ca6c5515f63523a90f93f780cdb392 |
| test_compatibility_upgrade.py | 800173a94ae2de9673e99fd30bf587e7d011096419f3f7d7d0e4ef16eb22bb98 |

下一步：由兼容实现者修复 F01、补行为测试，独立 reviewer 对受影响路径复查；主会话 gate 前不写检查通过。本报告写入前 task_path guard 已 exit 0，未改 Python、父目录或主 PLAN。未调用 code-review；本次为逐函数控制流与真实隔离实验的独立检查。

## F01 修复复查（2026-09-29）

复查结论：**F01 已修复，本报告范围独立审查通过**。初次失败证据继续保留，但不能代表当前实现。未改产品或 PLAN，报告写入前再次通过 task_path guard。

当前代码中 applying/complete 均先校验严格整数 schema、receipt 格式/profile 及编码后哈希；complete 再要求发布旁车字节与 journal receipt 相同。校验不拿当前 PLAN 的哈希匹配初始快照，因此保留正常演进。已有旁车但本地 journal 缺失时不重新生成 journal 或覆盖旁车，而是明确记录完整性无法核实。

独立重跑命令仍为 `PYTHONUTF8=1` 下 `py -3.12 -X utf8 -B -m unittest tests.test_compatibility_upgrade -v`：19 项通过，exit 0，9.783 秒；原始工具记录 chunks `dca8b4`、`855512`。新增测试包含五类 complete 篡改及缺 journal 的 apply/check/dry-run 保留。随后独立复跑原反例，使用真实 standalone CLI `--check`，结果如下（chunk `837476`，实验命令 exit 0，含逐项断言）：

| 隔离输入变化 | 实际 CLI 结果 | 写入检查 |
|---|---|---|
| complete 后仅把旁车 source_sha256 改成 64 个 0 | needs_review / exit 2；`Completed compatibility output differs from its journal` | 全文件 bytes/mtime 不变，保留实验注入的原现场 |
| complete 后仅把 journal.sha256 改成 64 个 0 | needs_review / exit 2；`Changed compatibility journal` | 全文件 bytes/mtime 不变，旁车初始快照保留 |
| 删除本地 journal，保留合法旁车 | needs_review / exit 2；`integrity is unverifiable` | 不重建 journal、不改旁车和来源 |
| 正常更新 PLAN 为 pending 并保留后续授权说明 | current / exit 0 | 初始旁车及本次检查前后全文件 bytes/mtime 均不变 |

当前指纹（未改变文件继续使用原有效检查证据）：

| 文件 | 当前 SHA-256 |
|---|---|
| compatibility_upgrade.py | f1f20954c15495458e1803768b9c9143730680952f158f25b515e01da517e58c |
| test_compatibility_upgrade.py | d4b73fe0a46aa5dadf5424a5c34e9ced011c0725e22c3c4e4456bbe1f418250c |
| migrate_workspace.py | 61bca60eb04dba7f3b6c6c99ee452ae9c3f6409c0c3a0b1f3ae48ea84e460938 |
| history_convergence.py | 5aa44bf2f835d27a8392fd72eb633875b0ca6c5515f63523a90f93f780cdb392 |

## 有界跨阶段接缝检查

只核对未由本审查者实现的兼容 Python 与父仓库公开文档契约；不对自己实现的 flow、项目安装器及角色文档提供独立背书。父安装器代码未作完整正确性审查，此处不代替阶段 3 review。

- 父 `INSTALL.md` 明确四个技能随插件安装、requirements-design 独立讨论不建立任务目录也不迁移历史；安装不启动业务开发。与兼容脚本仅显式选定 task 才处理旁车的边界一致。
- 父入口 `agents-entry.md` 区分技能路由和实施授权，恢复须核对任务记录及证据；旁车明确不授予授权、不改 adoption/state，与其不冲突。
- 父 `INSTALL.md` 对旧安装 receipt 的迁移只处理受管理技能入口，保留任务记录/旧 runtime，并将工作区迁移预览指向 `migrate_workspace.py --dry-run`；这与单任务旁车是不同操作，不应合并为“安装即升级所有任务”。当前文字未作此承诺。
- 限制：`.work/` journal 不是随 Git 保证迁移的持久证据。换机器只有旁车时脚本返回 needs_review 并保护旧内容，不能声称完整性已校验或自动兼容已全绿；正常任务记录仍可只读核对，具体解除方式需主会话说明。此为保守保护，不重写或使历史授权/证据自动失效。

下一动作：主会话核对阶段入口与审查指纹，完成 gate 并报告上述跨机器限制；独立 flow reviewer 提供另一范围的结论。当前审查中未发现新的兼容代码阻塞。
