# 阶段 3 父仓库独立审查

**日期**：2026-09-29  
**结论**：本范围独立审查通过，无阻塞；整体 gate 及新追加迁移仍需各自验证。  
**独立性**：审查者未参与父仓库实现；未改父代码、文档或 PLAN。  
**路径基准**：除报告路径外，本报告所有相对路径均指父仓库 `D:/Works/harness`，不是 longdev-plugin。

## 范围与边界

覆盖父仓库 `scripts/bootstrap.py`、`compose-agents.ps1`、三份测试（test_bootstrap、test_compose、test_document_contract），以及最终停写的 entry/top/tool 源、README、INSTALL、AGENTS 和生成入口/九层。对应 R05/R07/R09/R11、V08/V11/V14/V15/V17 的父范围；连续设计规则仅核对与子插件职责的衔接，不重复阶段 1 审查。

用户刚追加的受控软链迁移由主会话另行实现，不纳入当前通过范围。当前实现对既有软链是拒绝改写并保留现场；本报告不把它说成已自动迁移。插件兼容 Python、真实用户安装、三客户端实际模型加载及 GLM 故障修复也不在本报告验收范围。

## 实现审查

| 对象 | 核对结果 |
|---|---|
| 小入口与九层 | agents-entry 只放稳定协作约定与场景路由；LAYER_SOURCES 按明确章节拆分九层，对未知/缺失/重复标题拒绝生成，不静默丢正文。当前生成入口 3150 字节，层数 9，未把完整规则拼回入口。 |
| 三端入口 | Codex/dsh 使用 AGENTS.md，Claude 使用 CLAUDE.md；显式 client-home/各自环境变量有独立解析，旧 codex-home 兼容；dsh/Claude 拒绝混用 Codex 专属扩展参数，不改模型配置。 |
| 版本快照 | 文件哈希集合决定完整发布 ID；运行时入口替换为同版 releases/<id>/layers 绝对路径。开发源变化不影响已部署内容，新发布保留旧版本，不共享开发工作树的实时规则。 |
| 用户内容与旧安装 | 只替换经 receipt 哈希验证的管理区，外部字节保留；未知管理区、手改 release、旧层哈希不符、非法路径和 symlink/reparse 点均拒绝覆盖。旧单体/flat-layer 收据保留并增量升级。 |
| 事务与恢复 | 多文件非原子事务的限制明确；写入前保留原内容，独占 recovery 日志，逐文件核对并发变化。同步失败只恢复本轮仍匹配预期的文件；他人后续修改不覆盖。中断/恢复失败保留 recovery，doctor/后续安装拒绝盲写。 |
| compose 与安装一致性 | PowerShell 调用同一 Python compose 逻辑，真实退出码透传；所有目标先做普通文件检查，check 模式不写锁/文件。没有独立 PowerShell 拼接实现漂移。 |
| UTF-8 | Python 主入口重配 stdout/stderr 为 UTF-8；Python 子进程携带 UTF-8 参数/环境；PowerShell 输入输出编码显式设置。源码与审查日志严格 UTF-8 可解码，未检测到 U+FFFD 替换字符；未改变系统全局代码页。 |
| 文档契约 | README/INSTALL/AGENTS 区分源、生成物、运行时快照及真实会话加载；不把静态磁盘 doctor 说成三端模型已读规则。开发/发布隔离、软链共享风险、旧内容保护及恢复操作与当前代码相符。 |

## 独立实际验证

在父仓库 `.work/parent-independent-review` 内创建隔离临时源和三个独立 home，复制真实 entry/top/tool 及 bootstrap；直接调用当前安装器的 install/doctor。未修改真实用户入口，也未改父仓库生成物。

Codex、dsh、Claude 各自均得到：install=0、doctor=0；9 个规则层；用户原有中文前言字节保留；入口引用绝对运行时层路径且不引用开发层；修改隔离源后 live 文件不变；发布新版本后 ID 改变，旧 release 所有文件字节不变。独立探查进程 exit 0。日志与代码指纹在 `.work/parent-independent-review/probe.log`、`manifest.json`；本报告形成时再次核对相应代码/测试指纹未变。

复用了实施者提供的已有专项原始日志，未无变化重跑：

- `.work/layered-rules-bootstrap.log`：44 tests，40.379s，OK；审阅了相应行为断言，包括旧收据、用户编辑、软链、只读、失败恢复和并发编辑。
- `.work/layered-rules-compose.log`：10 tests，18.621s，OK；含真实 PowerShell UTF-8、锁文件、重解析点、未知章节和失败恢复。
- 两份已提供日志合计 54 项；另两项 document_contract 测试在本审查中只读核对断言，未冒称已独立运行。主会话后续全量 gate 将验证最终文档状态。

最终源/生成物清单、哈希、3150 字节与九层计数在 `.work/parent-independent-review/final-manifest.json`。日志是补充证据，独立三端实测才是本次新增验证；既有专项日志没有产物 manifest，不能据此单独证明全量最终状态。

报告写入前调用插件 task_path.py check，project/task/target 均为规范 Windows 绝对路径，exit 0、status=allowed。报告写入后不改需求状态。

## 当前产物指纹

以下路径均为父仓库相对路径。

| 文件 | SHA-256 |
|---|---|
| `scripts/bootstrap.py` | `adc5c4d53a2febc95d984c12e3d6039dd37a6b046634e6262cdeed2c200b290e` |
| `compose-agents.ps1` | `4438ab761c00d535fd587670c4ac619ba6b322c9d65c3046ee0623e08b4664ec` |
| `tests/test_bootstrap.py` | `df584d894746ff2580cdbb3fa4af72e2e4749ec708fbbf5b3aa37d6516ef4b93` |
| `tests/test_compose.py` | `9859b14de9e9e3e53474f9cb8f78840d5008b4c139b099d75ee7d2487385131f` |
| `tests/test_document_contract.py` | `61d692af1b700a1de7dc9f9643a077bd4ca7c94a0f5a0c9dc2c06af87c34ff0d` |
| `README.md` | `ac882bbdb964d727fcf90326da1581d9a965104a3afa498e8cce72d79f92718c` |
| `INSTALL.md` | `9b5c306dafb39bd24ad91586c5caefd1b2481f00249ef73bde96ca28273a4212` |
| `AGENTS.md` | `0ae3819455ca82150139191c9212235c482a8afa2bd1c8cdaa63fbc0b64649b7` |
| `agents-entry.md` | `89c6fad49a5f229e74da3d08f44023640feb7eecb7686d5d7bb21d7503446283` |
| `agents-top.md` | `febeae66f22ebe73bba77ccc34e62fb1b43d4754e421ef5ec9f582b6290c9c9b` |
| `agents-tool.md` | `56ed5649c486f6c11a7c68294c6469480ef67ff20085416907914286698dac36` |
| `.harness/global-instructions.md` | `3c11f35b7a07906d18f551a5580550f6587865de09595e25e496e50e67125289` |
| `.harness/layers/collaboration.md` | `5eae266a5aedf7c5eff0d03f9b61b3b1a6d398a59f39136c0c634592fc057a7b` |
| `.harness/layers/continuity.md` | `8b725948513cfd54fbf562e01a1ac67b69a9158a3edbd12550b78d66e45f8b90` |
| `.harness/layers/delivery.md` | `f05ae39bb8f396b2e9fdc2def411e5d027865c0d64e3f2710c5937ab18bbfc9e` |
| `.harness/layers/dependencies.md` | `f78da0ae5cd9954c7647048e58e512367c0c3cd27a64247419011d50874b2665` |
| `.harness/layers/engineering.md` | `cc1b36dd58ee261a19e9a11e300b23e06704fa0fce272a6e6519d70e8092a9dd` |
| `.harness/layers/feedback.md` | `e11ac768e0d84606728cc9ac1b9fcf68515f060416f921cfa3c0f7401d3d4795` |
| `.harness/layers/maintenance.md` | `046c05746f518f2033ba74fc8cbec084c8b927a1fa3eb0b7df6c6159c83b7e98` |
| `.harness/layers/vision.md` | `b8e71f7546e7b816ba4cb3dce3dc5b46f6ab93448dbb1a5810b29aab99b81c39` |
| `.harness/layers/workflow.md` | `a747a4de12e722b42f0d3b6e677fd62ec2f59d039a0ad73de712dc0582dceb56` |

## 限制与下一步

按需读取由规则约定驱动，不是宿主强制装载器；未证明模型一定遵循、未验证真实新会话加载、未复现或修复 GLM 的 compact/工具桥接。安装器刻意拒绝既有软链，用户新增的受控迁移必须补独立增量审查。

当前阶段没有阻塞发现。主会话执行最终全量 gate，并将任何后续父代码/配置/文档变化按影响使本报告对应证据失效。仅规则发布隔离与上述检查范围通过，不代替完整任务交付或用户验收。


## 增量复审：受控软链迁移与换机路径重绑定

**日期**：2026-09-29。**结论**：本增量独立审查通过；此前正文“新增受控迁移不在通过范围”仅描述第一轮边界，当前由本节补齐。原审查与指纹保留，不抹掉历史反例。

### 独立发现与修复复核

首次审查真实复现了阻塞：旧全文生成文件同时被待迁移入口和另一个智能体软链引用；显式迁移调用普通 install，后者重生了 source 生成物。三客户端迁移均 exit 0，但旧共享目标从 32435 字节变为约 3.7 KB，另一条链接读到的内容随之改变。这违反迁移单个入口时保护其他使用者的隔离目标。反例对应 bootstrap SHA `31f11f17f62821d7454056dc7f4c9ec494f82a72f4c94e132838d2926fa2afe3`，证据位于父 `.work/parent-independent-review/link-migration-counterexample.json` 和 `.log`。

主会话随后修复：迁移调用安装器的 preserve_source 模式，只写运行时快照、入口及安装收据；`preserve_source_outputs: true` 写入收据并延续到后续普通安装。doctor 仍校验当前编译输入、运行时快照及入口；被保护的 source 生成物不再被要求等于新生成物，compose 检查与运行时安装检查分开。字段类型校验仅接受 bool。

### 独立三端实际复验

在父 `.work/parent-independent-review` 隔离源与 home 运行真实文件调用，CodeX/dsh/Claude 每端均完成以下断言，探查进程 exit 0；未修改真实用户入口：

| 场景 | 三端实际结果 |
|---|---|
| 普通 install 遇已知旧软链，无迁移参数 | 返回 1，原链接和 source 文件不变。 |
| 显式迁移旧全文，另一个入口仍指向相同目标 | 返回 0，迁移入口变普通文件；原共享目标、其他链接读到的内容、全部 source 文件字节与 mtime 均不变。 |
| 迁移后修改规则源，再普通 install | 返回 0，新运行时版本可用；source 生成物及旧共享全文仍保持原样，doctor 返回 0。 |
| 整体复制 home 与 source 到新目录 | install/doctor 返回 0；入口引用新 home 的 releases 绝对路径，不保留旧 home 引用；preserve_source 继续生效。 |
| 在真实安装事务写 installation.json 时注入 PermissionError | 返回 1；运行时事务恢复后空入口还原原链接目标；source 不变，link pending 与 recovery 均已收口。 |
| 入口已被新写入者创建后发生失败 | 保留新内容，不恢复链接覆盖它；保留 link pending，后续普通 install/doctor 返回 1 且不改变该内容。 |

最后两项是隔离失败注入，用于验证事务和恢复行为，不冒充外部系统故障。同步失败恢复、未知/手改拒绝和中断 pending 的代码路径与新增 tests.test_bootstrap 断言逐项核对；不重跑主会话正在执行的父全量 gate。

复验的 bootstrap SHA 为 `91686cf91e74cd730be2bc71d0a6c254ce0f5bc125038bc6421a8f9085a2a34f`，运行前后及报告形成前一致。JSON 结果和完整 UTF-8 日志为父 `.work/parent-independent-review/link-migration-recheck.json`、`.log`；最终产物指纹位于同目录 `link-migration-final-manifest.json`。

### 增量产物指纹

| 父仓库文件 | SHA-256 |
|---|---|
| `scripts/bootstrap.py` | `91686cf91e74cd730be2bc71d0a6c254ce0f5bc125038bc6421a8f9085a2a34f` |
| `tests/test_bootstrap.py` | `06c9d0340b344be013b8c67b7f9c73efd215cde89982ed646afdb6d783f1cbef` |
| `README.md` | `dbe2eedb144c8953505d4b4be0201b50704af2b9c36defa800dd3ad1c4d88797` |
| `INSTALL.md` | `615e3c4f88adf32bf91011a0ca963918690b65ff7bf9f784a998ae9f4c155745` |
| `AGENTS.md` | `fd9adb574cf13c28c08d51fc4cc2302f589435037d96783f70bb5430a56897b6` |

本增量未发现剩余阻塞。README/INSTALL/AGENTS 已记录显式迁移、默认保留、备份、pending 恢复及换机重绑边界；保护原共享目标的反例已关闭。主会话仍需核实最终父回归结果并执行 gate。本报告不授权修改真实用户软链，不把三端磁盘迁移验证说成真实模型会话已加载；当前有效审查为原范围结论与本增量共同组成。


### 最终证据补核

已读取并核实主会话最终回归证据：父全量日志 `.work/checks/requirements-design-parent-final/cases/harness-unit-tests/stderr.txt` 为 98 tests、OK（1 项 POSIX launcher 在 Windows 不适用而跳过）；共享源保护修复后受影响的 bootstrap + document_contract 回归为 52 tests、40.588s、OK、exit 0。后者命令、11 个输入指纹及 before==after 记录在同根 `migration-recheck.json`，本审查另行与当前文件逐项比对一致，原始 UTF-8 日志为 `migration-recheck.log`。全量运行先于共享源保护修复，不以旧全量结果替代修复后的受影响 52 项回归。

INSTALL 已明确软链迁移及后续升级保留源 `.harness` 产物，doctor 校验当前编译源及运行快照，source 生成物另由维护者选择 compose/-Check。该说明与修复后的行为一致。当前父范围（包括本增量）保持独立审查通过；证据来自独立三端实测、失败注入及当前指纹对应的已执行回归，不代表真实用户部署或模型加载已完成。
