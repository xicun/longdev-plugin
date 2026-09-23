# 阶段 1 独立审查

日期：2026-09-23。审查者未参与实现；采用人工式独立检查（未调用 code-review，本环境没有该 skill）。

**结论：实现与提交前条件独立审查通过。** 覆盖 V01–V04 及 V05 提交前条件；V05 实际阶段提交须由主会话在 gate 后执行并核验，本报告不冒充其已发生。V06 属阶段 2，尚未在此报告验证。成果不等于用户已验收。

## 范围与产物

- 按用户两项缺陷、当前工作区启动自动迁移的确认、PLAN R01–R04 及阶段入口独立形成检查范围。
- 子仓库起点 HEAD `bcf726091638becec1ae167ce7d5528e33981357`，主会话提供起始父/子工作区均干净的基线；审查当前 tracked diff 和未跟踪迁移脚本/测试/任务记录，未只用 HEAD 代表工作区。
- 当前代码、协议、角色、模板、安装器、测试、版本和用户文档指纹：[review-stage-1-manifest.json](../evidence/review-stage-1-manifest.json)。验证前后指纹一致。双 manifest 为 `0.13.0+codex.20260923092211`。
- 父仓库关联审查：INSTALL.md、PLAN.md 新增任务索引、scripts/bootstrap.py 恢复路由、tests/test_bootstrap.py 路由与版本升级测试。未接手父仓库历史任务。

## 验证与观察

| V / R | 独立方法与期望 | 实际结果与证据 | 结论 |
|---|---|---|---|
| V01 / R01 | 逐项追踪 review→gate→记录→限定提交→下一阶段；隔离 Git fixture 建立他人 staged，提交自己的代码与新增计划，再用失败 hook 验证保护；审阅无 Git、无变化、用户禁止分支 | `git commit --only` 只包含 PLAN.md/own，他人 cached diff 字节不变；hook 失败 exit 1，HEAD 与他人 cached diff 不变。原始结果在项目 `.work/portable-stage-upgrade/review-commit-protocol.json`。例外明确记录且不伪报成功 | 通过 |
| V02 / R02 | 读两个 SKILL、共享协议、全部变更角色/模板、README/INSTALL、安装薄入口；搜索旧目录及 baselines 引用 | 新入口统一 docs；.claude 仅迁移兼容说明；基线/原始日志进入 .work，摘要/manifest/决定/交接随 Git；外部引用与未知格式明确人工核对，不声称迁移等于已提交 | 通过 |
| V03 / R03 | 子仓库执行 `python3 -B -m unittest discover -s tests -v`；独立读安全、路径变换、journal/marker 控制流和行为断言 | 24 tests，exit 0，零 skip；覆盖正常迁移、状态、备份字节、JSON/命令、Windows 路径、链接标题、冲突、ignore、幂等、中断及源集合变化、symlink/reparse、并发锁、只读 status、新工作区/兄弟目录不变、跨机器无 .work/旧目录和合法新状态。日志 `.work/portable-stage-upgrade/review-tests.log`；Python 环境及哈希见 manifest | 通过 |
| V04 / R02–R04 | 同一完整测试运行，核查三客户端安装包测试和双版本文件；父仓库针对路由与版本升级执行测试 | 三端 bundle 均包含字节一致迁移脚本，技能相对入口可定位，安装幂等/损坏检查保留。父仓库 `.work/keyboard/venv/bin/python -B -m unittest tests.test_bootstrap.BootstrapTests.test_new_install_receipt_routing_and_idempotence tests.test_bootstrap.BootstrapTests.test_native_version_upgrade_preserves_old_cache -v`：2/2 通过、exit 0；日志在子项目 `.work/portable-stage-upgrade/review-parent-tests.log` | 通过 |
| V05 / R01,R02 | `git diff --check`；核对待提交路径与起点归属、持久记录位置 | 子仓库 diff 检查 exit 0；本阶段仅升级相关文件及任务记录。主会话后置实际 commit/原索引/持久记录跟踪核验尚待执行 | 提交前条件通过；实际提交待 gate 后核验 |

## 初查问题及修复复查

以下为初查时真实缺陷，均已在当前产物修复；初查产物不构成通过证据。

1. **高 / R03,V03：命令前缀丢失。** 初版把整个 backtick/JSON 字符串当路径，`cat .claude/longdev/t/PLAN.md` 变成仅 `docs/longdev/t/PLAN.md`。现仅替换路径 token，测试保留 cat/python/绝对命令前缀。
2. **高 / R03,V03：有效 JSON 被改坏。** 内嵌引号命令曾经产生无效 JSON。现先解析并递归处理字符串，再序列化；保留布尔/数字/null/状态，测试内嵌引号与 Windows 路径。纯相对 JSON 日志路径另经精确 mapping，指向迁移后的 .work。
3. **中 / R02–R03,V02–V03：备份与路径边界。** 原始 baseline 文本曾被重写、Markdown 标题链接路径错误、模板仍指任务内 baselines。现备份原字节保留、链接重算并保护、模板/角色同步 .work。
4. **中 / R03,V03：中断后的源集合、新目录 ignore 与 Windows 越界。** 主会话和独立审查联合提出；现校验源文件全集，新工作区同样探测 ignore；拒绝 POSIX/Windows drive/UNC/上级路径与 reparse。已有完成标记后的正常修改不再重导入旧记录。

首轮父仓库针对性运行曾误写不存在的测试名，loader error 后按实际名称重新执行 2/2 通过；属审查命令错误，未修改产品以凑测试通过。

## 限制与交接

- 本次实际运行环境为 macOS；Windows 路径拒绝与 reparse 属性通过模拟验证，Windows msvcrt 锁与真实 junction 未在 Windows 机器执行，文档已如实列明。
- 父仓库完整测试需要 PowerShell；本报告只主张受影响的两个针对性测试通过，不宣称父全量通过。
- 迁移保留历史状态但不为历史证据重新背书；缺少本机原始证据时依协议定向重验。未知格式/外部引用由迁移报告列出，主会话须处理。
- 未发现剩余阻塞实现问题或需用户决定的范围取舍。下一步：主会话执行 gate、实际限定提交并补 V05，随后进入 V06 安装/发布核验。
