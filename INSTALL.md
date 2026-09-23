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

共享包存入 `<project>/.longdev-runtime/<内容指纹>/`，包括两个 skills、所有 references、工作区迁移脚本、agents 和版本文件。三端只生成薄入口：

| 客户端 | 自动发现入口 |
|---|---|
| Claude Code | `.claude/skills/{longdev,autopilot}/SKILL.md` |
| Codex CLI | `.agents/skills/{longdev,autopilot}/SKILL.md` |
| dsh | `.dsh/skills/{longdev,autopilot}/SKILL.md` |

入口使用完整包的绝对路径，无软链权限要求。移动项目后须从新路径重跑安装。升级同样重跑；旧包保留供现有会话使用，不自动清理。未知来源的已有入口或用户编辑会被拒绝覆盖；报告冲突路径，不自行删除。dsh 默认 filesystem provider 必须启用；自定义 profile 禁用它时，报告发现能力缺口，不改用户 profile。

安装后新开一次客户端会话，要求列出 longdev/autopilot 并读取完整技能及版本。已有用户级技能或插件可能同名遮蔽，核对实际加载路径，不能仅凭目录存在宣布已加载。安装器校验不证明模型调用、独立审查、自动 restart 或视觉隔离已实跑。

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

v0.13.0 技能启动/续接当前工作区时运行包内 `skills/longdev/scripts/migrate_workspace.py --project <项目根>`，Python 与安装器要求相同。安装和更新插件本身不遍历历史工作区，也不启动旧任务；以后在哪个项目使用新版技能，就检查哪个项目。

旧 `.claude/longdev/`、`.claude/autopilot/` 迁入 `docs/`，原始基线/日志/图片等迁入 `.work/`；旧目录保留完整保护副本。完成标记 `docs/longdev/.migration-v013.json` 随记录提交，此后只认新目录，不重导入残留旧数据。脚本不会修改已有冲突内容、Git 索引或业务代码。Markdown/JSON 常见路径会更新；其它格式及迁移树外引用保留并报告供核对。旧状态原样保留，不把迁移当作验证/验收通过。

`--check` 只读探测：exit 0 表示无需迁移或已迁移，1 表示待迁移，2 表示冲突/忽略/环境受阻。任何启动都检查持久目录是否被忽略。命中时 agent 在项目授权范围内修复最小 `.gitignore` 例外并重验，不改全局规则，不用 `git add -f` 绕过。迁移成功只表示文件准备好，主会话仍须核对归属，并在阶段 gate 后提交记录/标记。用户禁止提交或非 Git 项目需明确同步限制。
