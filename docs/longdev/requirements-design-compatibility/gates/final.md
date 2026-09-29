# 主会话整体 gate（含阶段1–3）

日期：2026-09-29。结论：本轮源码与隔离安装成果检查通过，待用户验收；无发布、push或真实用户入口迁移。

## 覆盖与证据

| V全集 | 覆盖及有效结果 |
|---|---|
| V01–V04 | 独立requirements-design、设计gate、planner/testcases/PO/reviewer、变更失效；stage-1-recheck独立通过；格式及安装9项通过 |
| V05–V07 | 单任务兼容旁车、原文/授权/RV/状态保留、幂等和中断/冲突/未来格式；19项测试通过；stage-2 F01反例修复后独立复查通过 |
| V08 | 父子diff --check无错误；主会话运行compose -Check exit0，九层与源一致；生成入口3150字节 |
| V09–V10,V12–V13,V16 | 重复调查/成功验证/ABCABC、正常空/pending/错误分类、交接与模型授权；flow-scenarios及独立review静态通过，非GLM实机证据 |
| V11,V14–V15 | 三端真实隔离install/doctor、用户内容/旧收据、快照不可变、相对/旧全文软链迁移、共享源保留、不同路径换机重绑；父独立review及增量反例复查通过 |
| V17 | 源文件严格UTF8无U+FFFD；本机默认Python stdout/stderr=GBK，-X utf8后正常；子进程继承PYTHONUTF8/PYTHONIOENCODING，中文日志可读，过时断言已修复 |

完整R01–R11/V01–V17逐项覆盖，无新增未处置需求。运行时原话FB-0002/FB-0003逐项分流后覆盖check exit0，不声称GLM故障已修复。

## 实际执行

- 插件独立checker：在 longdev-plugin 运行 `py -3.12 -X utf8 -B skills/checks/scripts/check_runner.py --catalog-root testcases --source-root . --profile smoke --output .work/checks/requirements-design-final`，runner exit0，内部完整unittest 87项/95.819秒全通过。环境PYTHONUTF8=1、PYTHONIOENCODING=utf-8。报告 reviews/final-plugin.md，含当前源码指纹及证据边界。
- 父主会话gate：在 harness 根运行 `py -3.12 -X utf8 -B longdev-plugin/skills/checks/scripts/check_runner.py --catalog-root testcases --source-root . --profile smoke --output .work/checks/requirements-design-parent-final`，同UTF8环境，runner exit0；内部98项/59.758秒，OK(skipped=1，平台限定)。
- 随后独立review发现旧全文软链迁移会重生共享源：修复为迁移及后续升级仅写目标runtime/entry/receipt。旧父证据不再单独支持该变更；主会话运行 `py -3.12 -X utf8 -B -m unittest tests.test_bootstrap tests.test_document_contract -v`，52项/40.588秒全通过，11个父产物before/after SHA相同。原始日志/指纹：父 `.work/checks/requirements-design-parent-final/migration-recheck.log` 与 `.json`。
- 独立reviewer重跑三个客户端原反例、后续升级、真实receipt写失败、后写者保护和复制home/换路径场景，均通过。父 `.work/parent-independent-review/link-migration-recheck.json`；报告 reviews/stage-3-parent.md。正常空stdout的diff --check记录为通过，不再次触发重试。
- 原始详细日志在各自项目.work；本文件和独立报告保存可携带命令、期望、结果及限制。evidence/final-validation.json保存当前最终产物指纹；目录历史不足不伪称任务起点完整基线。

## 限制

GLM模型/工具适配/compact根因未在真实环境复现，流程规则不是强制运行时循环检测器。三端真实新会话读取未执行。旧真实全局软链仍连开发源，本轮仅提供并隔离验证迁移命令。插件旁车跨机器缺本地journal时报告needs_review并保留原文，不能宣称完整性自动通过。父历史迁移的ignored持久证据阻碍未改动，不阻断本轮独立产物。

实现与独立审查已完成；本地提交记录交付后保存在Git。用户验收和实际发布仍单独处理，无自动验收授权。
