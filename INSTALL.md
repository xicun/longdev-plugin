# 给安装代理的入口

用户提供本仓库 URL 并要求安装时，先识别当前客户端和用户的目标项目目录。只安装技能，不启动业务任务、不改模型/密钥/权限配置，不把仓库克隆目录误当成目标项目。

## 统一安装（Claude Code、Codex、dsh）

1. 将完整仓库克隆到独立目录；已存在的 checkout 先检查改动，不覆盖或 reset。读取本文件及 `scripts/install.py`。
2. 找到 Python 3.9+：Windows 优先 `py -3`，其他系统 `python3`。无需 pip 包或管理员权限。
3. 在任意工作目录执行下列命令，将 `<project>` 换成用户的项目绝对路径，将 `<client>` 换成 `claude`、`codex`、`dsh`；明确要求三端共享时用 `all`。

```powershell
py -3 "<checkout>/scripts/install.py" --client <client> --project "<project>"
py -3 "<checkout>/scripts/install.py" --client <client> --project "<project>" --check
```

macOS/Linux 将 `py -3` 换成 `python3`。`--check` 校验完整包内容、入口和安装记录，非零退出不得报告成功。

共享包存入 `<project>/.longdev-runtime/<内容指纹>/`，包含完整 skills、references、问题管理 CLI、迁移脚本、agents 和版本文件。三端生成 longdev、autopilot、bug-reports、requirements-design 四个薄入口；checks 由完整包内调用：

| 客户端 | 自动发现入口 |
|---|---|
| Claude Code | `.claude/skills/{longdev,autopilot,bug-reports,requirements-design}/SKILL.md` |
| Codex CLI | `.agents/skills/{longdev,autopilot,bug-reports,requirements-design}/SKILL.md` |
| dsh | `.dsh/skills/{longdev,autopilot,bug-reports,requirements-design}/SKILL.md` |

入口使用完整包的绝对路径，无软链权限要求。移动项目后须从新路径重跑安装。升级同样重跑；旧包保留供现有会话使用，不自动清理。未知来源的已有入口或用户编辑会被拒绝覆盖；报告冲突路径，不自行删除。dsh 默认 filesystem provider 必须启用；自定义 profile 禁用它时，报告发现能力缺口，不改用户 profile。

安装后新开一次客户端会话，要求列出上述四个入口并读取适用技能及版本。已有用户级技能或插件可能同名遮蔽，核对实际加载路径，不能仅凭目录存在宣布已加载。安装器校验不证明模型调用、独立审查、自动 restart 或视觉隔离已实跑。

requirements-design 可独立完成需求讨论与方案设计，不要求创建 PLAN 或运行迁移。设计达到目标即交付；已有实施授权且无关键待决项时继续 planner，不在章节小结处反复请求继续。旧任务沿用既有设计来源和 R/V，不重编号或复制为第二套事实源。

已授权启动/续接且选定唯一任务后，主会话在旧写入者停止的安全交接点自动调用 `skills/longdev/scripts/compatibility_upgrade.py --project <项目绝对根> --task docs/longdev/<任务>`（autopilot 使用 docs/autopilot/<产品>）。该命令只处理选中任务，不扫描其它任务；纯讨论不调用，状态查询/预演加 `--check`/`--dry-run`。旁车 `COMPATIBILITY.json` 是不可变初始快照，保留旧语义，不代表新设计通过或旧证据重新验收。终态不重开，未知状态/格式和完整性冲突保留待核对；`.work/longdev-migration/compatibility/` journal 支持中断恢复。旁车存在但 journal 缺失时只能保留并报告无法校验，不能宣称完整性通过。

旧版双技能受管理入口可直接升级；新增 bug-reports 入口不存在时创建，已有未知内容或手改内容保留并报冲突。`--check` 只读，不自动补包或改写用户档案。

bug-reports 可独立使用，无需启动 longdev 或执行其任务迁移、独立审查流程。问题事实源为业务项目 `docs/bugs/reports.json`，`docs/bugs/index.json` 可重建；原始临时材料在 `.work/bugs/`。安装目录只提供技能和 CLI，不保存业务问题。

## Codex 原生插件方式（可选）

完整 checkout 保留 Claude-compatible marketplace 和 Codex manifest，可使用当前 CLI：

```powershell
codex plugin marketplace add "<checkout>"
codex plugin add longdev@zzm-plugins
```

也可把 `<checkout>` 换为 `https://gitee.com/xicun/longdev-plugin`。远程版本必须已推送。选择统一安装或原生插件一种入口，避免同名重复；不要为安装这个插件覆盖用户 marketplace 或配置。

## 共用任务

安装目录只存流程规则。持久任务记录位于原项目 `docs/longdev/<任务>/`，autopilot 在 `docs/autopilot/<产品>/`，随阶段 commit 进入 Git；原始日志、图片和备份位于项目 `.work/`。换机器需取得包含记录的提交，安装技能不自动同步代码或任务记录。单写入者交接、独立审查、default/更强模型和单图隔离遵守共享运行时协议。

## 升级后的工作区迁移

v0.14.0 技能启动/续接当前工作区时运行包内 `skills/longdev/scripts/migrate_workspace.py --project <项目根>`，Python 与安装器要求相同。说“先预览迁移/迁移 dry-run”时加 `--dry-run`，只读输出完整动作；`--check` 仅简短探测。安装和更新插件本身不遍历历史工作区，也不启动旧任务；以后在哪个项目使用新版技能，就检查哪个项目。

旧 `.claude/longdev/`、前导空格 `.claude`、`.longdev` 候选及 `.claude/autopilot/` 按内容识别迁入 `docs/`，可靠结束记录进入 `docs/<kind>/archive/`，原始基线/日志/图片等迁入 `.work/`；旧入口原始副本完成 Git 跟踪核验后进入 `.work/longdev-migration/archive/`。未知文件/目录、冲突、外部 .work 证据和未解析引用保留报告。完成标记 `docs/longdev/.migration-v014.json` 兼容 v0.13 指纹；旧目录新增/变更会报告分叉，不覆盖新 docs。脚本不会修改 Git 索引或业务代码。

`--check`/`--dry-run` 完全只读：exit 0 表示无待处理，1 表示存在待跟踪或预演动作，2 表示冲突/忽略/环境受阻。任何启动都检查持久目录是否被忽略。命中时 agent 在项目授权范围内修复最小 `.gitignore` 例外并重验，不改全局规则，不用 `git add -f` 绕过。正式迁移返回 awaiting_tracking 时可先提交阶段记录，再重跑完成归档；迁移成功只表示文件准备好，主会话仍须核对归属。非 Git 项目需明确同步限制。
