---
name: checks
description: 测试用例闭环能力：维护项目级共享测试用例库（cases/matrix/quality_refs），按任务的 R/V 引用子集运行回归并落 manifest/指纹证据，映射到需求/验收/测试/缺陷。供 longdev 的 testcases 角色设计/维护库、checker 角色在 Plan 与每阶段/收口做回归；也是任何“按目录跑可重复命令并落证据”场景的通用机制。
---

# Checks

`checks` 是 longdev 的**测试用例闭环**能力：一个项目级共享用例库 + 一个标准库运行器。它把“待开发对象的用例从哪来、如何验证、怎么映射回 R/V”串起来。

- 项目级共享库：`<项目>/testcases/`（`cases.json`、`matrix.json`、`quality_refs.json`），是被开发项目的内容；任务只**引用**其中子集，不复制。
- 运行器：`scripts/check_runner.py`。
- 目录格式与约定：见 [catalog-schema](references/catalog-schema.md)。

## 与 longdev 角色的配合

- **testcases 角色**：维护库——Plan 阶段为对象设计/补全用例、把任务引用子集映射 R/V；bug 修复验证通过且符合门槛时晋升为回归 case。
- **checker 角色**：执行——每阶段用 `--cases <子集>` 跑任务引用用例、出证据；收口跑全量闭环。
- **reviewer**：审设计/覆盖（核对 checker 证据），职责独立。

## 运行

```powershell
# 校验库
py -3.12 -B scripts/check_runner.py --catalog-root <项目>/testcases --validate
# 跑任务引用的一个子集（跨 profile）
py -3.12 -B scripts/check_runner.py --catalog-root <项目>/testcases --source-root <项目根> --cases <id,id> --output <evidence>
# 跑某个 profile
py -3.12 -B scripts/check_runner.py --catalog-root <项目>/testcases --source-root <项目根> --profile smoke --output <evidence>
```

`--validate` 只校验不写；`--cases` 指定子集（逗号分隔 case id）；`--profile` 为 `smoke|full|failure-probe`；`--output` 为 run 时必需；已存在 run 不覆盖。

## 证据与边界

- 跑出 `manifest.json` 的 `exit_code`、每 case `passed`/`actual_exit`、`fingerprints.json` 按 quality_refs 映射 R/V/Bug；`exit=0` 只证明该次运行，仍需核对需求覆盖。
- 用例库是项目内容；通用运行器不携带任何项目专属 case，也不引用 harness 父仓库路径。