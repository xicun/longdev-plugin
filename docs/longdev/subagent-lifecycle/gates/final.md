# 生命周期协议主会话 gate

2026-09-29：R01–R05/V01–V05 的协议改进检查通过，待用户验收。范围是技能/协议行为要求，不是实际宿主运行器修复。

- V01：独立演练1/4/6/7/15/16覆盖连续工作复用、独立审查、任务归属；双槽六项工作17步，峰值2。
- V02：演练1–5/7/10/12/15/16覆盖成果/证据/交接、在途操作、暂留与回收条件。
- V03：演练1/7–11覆盖满额、失败、无关闭接口、异步pending、关闭与容量确认分离，无无据spawn/close等待循环。
- V04：演练1/5/6/12–16覆盖阶段/迭代收尾、失效ID、权限/文件漂移及无旧代理表兼容。
- V05：两个入口引用共享单一规则，runtime只定义工具核实；实施者两技能quick_validate通过。主会话亲跑Python 3.12 `-X utf8 -B -m unittest discover -s tests -p test_install.py -v`，cwd为插件根，PYTHONUTF8=1/PYTHONIOENCODING=utf-8，9项通过、exit0。源码指纹前后相同。

独立checker的完整推演见evidence/forward-test.md；未参与实现的reviewer确认无阻塞，见reviews/stage-1.md。主会话核读16项及完整容量轨迹，对照R/V和原始反馈，未发现缺项。实际命令、当前源指纹和证据哈希见evidence/validation.json；原始日志在.work/longdev/subagent-lifecycle/gate-install.log。

BUG-0004只记录已尝试协议修正，保持investigating等待用户宿主实测；FB-0005为正确用户原话，FB-0004是本轮stdin编码损坏并已显式关联补全，不用损坏记录冒充原话。使用范围化普通check，不以--delivery伪造运行时症状修复。

限制：当前宿主无显式close，本轮没有真实创建/关闭代理来测资源回收，没有声称DeepSeek/GLM长期改善。已有三位代理完成本轮职责且停止写入，结果均接收；无后续返工，关闭能力缺失，资源释放未知。任务记录保留交接，不能用interrupt代替关闭。旧任务和业务记录未改，本机插件未更新。

本轮按gate结果限定范围本地提交；下一步：源码待用户验收，后续若授权发布再更新插件缓存版本并发布。本机原有生成入口大小写差异不纳入提交。
