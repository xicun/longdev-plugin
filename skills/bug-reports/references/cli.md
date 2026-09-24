# CLI 与数据契约（schema 1）

入口：`python <实际技能目录>/scripts/bug_reports.py --project <已存在项目绝对根> <command> [options]`。Python 3.9+，无额外依赖。Windows 可用 `py -3.12 -B`，中文输出建议 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。JSON 文件以 UTF-8 保存（允许 BOM），避免 shell 拼接多行或转义。

所有结果为 JSON。exit 0 成功，check 发现未闭环项 exit 1，输入/引用/并发/路径/证据错误 exit 2；诊断写 stderr。失败不写事实源。`docs/bugs/reports.json` 为唯一事实源；issue 和 feedback 永久编号，自增且不重用。`index.json` 只派生，写事实源后返回 index_stale=true，按需 reindex。不要手动并行编辑事实源。

## 读写入口

| 命令 | 参数 | 结果 |
|---|---|---|
| init | 无 | 创建空档案，已存在时拒绝覆盖 |
| status | 无 | 当前 revision、未关闭问题摘要与反馈未路由条目 |
| show | `--id BUG-0001` 或 `--id FB-0001` | 指定问题/反馈的完整记录与历史；旧别名仍返回原记录 |
| search | `--query "保存 刷新" --offset 0 --limit 20` | 词面候选，含已关闭/合并记录，limit 1..100；空 query 可遍历 |
| reindex | 无 | 按当前档案重建索引，原始反馈及历史不变 |
| check | 可重复 `--feedback FB-0001`、`--bug BUG-0001`；可选 `--delivery` | 无 selector 检查全档；指定 selector 只检查本轮及其关联问题；delivery 额外要求复发分析完整且已验证 |
| create / feedback / route / update / repair / investigate / verify / accept / relate | `--input <JSON文件> --expected-revision <status/show返回的整数>` | 乐观版本写入；成功返回新 revision |

`check` 普通模式允许待澄清/调查中的问题，但拒绝未路由反馈、坏引用、已验收状态缺证据或证据漂移。待澄清需要具体待答问题/去向，不能用其掩盖已承诺修复。`--delivery` 用于声称选中范围已修复时；保留未完成项的部分交付须明确说明，不能拿普通模式通过冒充全部修复。

写锁位于 `docs/bugs/.write.lock`；工具不会抢锁，遗留锁须核实进程及现场后人工处理。项目路径及证据相对路径不接受 symlink/reparse 穿透或 `..`。input 可位于项目临时目录；脚本只将持久数据写到 docs/bugs。单一 JSON 原子替换避免跨文件事务半写；索引单独生成，不作为事实依据。

## 写入 JSON

### create

```json
{"title":"保存后列表仍是旧值","goal":"更新资料后看到新值","expected":"返回列表即显示新值","actual":"仍显示旧值","conditions":"编辑后保存并返回","scope":"资料页与列表","facts":["用户反馈保存成功提示"],"hypotheses":["列表缓存未失效，待验证"],"next_step":"复现操作并观察请求","close_condition":"原操作路径及刷新/重进均一致"}
```

除 facts/hypotheses（数组，默认空）外上述文本字段均必填。返回永久 BUG ID。

可选 `quality_refs` 用于关联现有质量记录，例如 `[{"kind":"requirement","id":"R01","reference":"PLAN.md#R01"},{"kind":"test_case","id":"TC-12","reference":"tests/test_profile.py::test_return_list"},{"kind":"test_run","id":"RUN-8","reference":"docs/test-runs/RUN-8.json"}]`。kind 支持 requirement/acceptance/test_case/test_run；id/reference 为非空文本。create/update 均支持，show/历史保留。引用本身不证明已运行或通过，不替代 verify 的真实证据/指纹，不自动创建或执行测试。

### feedback 与 route

```json
{"raw":"保存还是旧值；导出报错；希望批量处理；另一个情况待补充","source":"用户反馈 2026-09-24 第2轮","items":[{"id":"1","text":"保存还是旧值"},{"id":"2","text":"导出报错"},{"id":"3","text":"希望批量处理"},{"id":"4","text":"另一个情况待补充"}]}
```

保存原话，条目 text 必须是 raw 中的原文片段，ID 在批次内唯一；不预填 route，先持久化再逐项分流。返回 FB ID。分流示例：

```json
{"feedback":"FB-0001","item":"1","route":{"kind":"bug","target":"BUG-0001","confidence":"suspected","reason":"同一更新目标与返回列表路径，先按疑似复发调查"}}
```

Bug confidence 可 confirmed/suspected。需求路由 `{"kind":"requirement","destination":"PLAN.md#R12","reason":"新增批量行为"}`；待澄清路由 `{"kind":"clarify","destination":"待补充页面和实际现象","reason":"当前缺定位条件"}`。所有路由都有 reason；旧路由记录保留在条目 history。反馈/repair 的登记 revision 用于识别时间顺序，修复前已登记的同批反馈晚路由不误计复发；应按真实反馈顺序及时登记，不回填伪时间。

### update、repair、investigate

```json
{"id":"BUG-0001","fields":{"facts":["接口已返回新值，列表未刷新"],"hypotheses":[],"next_step":"检查缓存失效路径"}}
```

fields 限 create 的当前描述字段，不允许直接改 status/history/编号。update 清除当前验证，保留历史，并要求新的 repair 后才能 verify。

```json
{"id":"BUG-0001","version":"commit-or-build-identifier","summary":"保存后更新列表缓存","cause":"缓存未失效","coverage":"编辑保存、列表返回、重新进入"}
```

repair 分配问题内永久 FIX 编号，状态进入 verification（待验证），旧验证留在 history；只表示已尝试修复，不表示验证通过。

```json
{"id":"BUG-0001","previous_repair":"FIX-0001","old_cause":"上次判断缓存未失效","support":"保存响应已是新值","counterevidence":"第二列表入口仍读旧缓存","runtime_version":"build-A","coverage":"旧修复只覆盖资料页入口","missed_validation":"未测试第二列表入口","experiment":"分别从两个入口保存后返回","result":"第二入口修复前失败；已据此定位共享缓存更新缺口"}
```

investigate 绑定 previous_repair 指定的失败 FIX，允许逐一补齐历史未闭环调查；每个复发 FIX 都须有独立调查，不能只填写最后一次。文本均必填，pending 不会被脚本当成根因事实。AI 必须核验实验是否真的执行，有缺口就保持调查，禁止为了过字段校验填写虚假结论。新 FIX 的 verify 仍须原路径复现、完整覆盖与当前运行版本。

### verify 与 accept

```json
{"id":"BUG-0001","method":"按两入口执行保存/返回/刷新回归","expected":"所有入口新值一致","actual":"两入口均通过，修复前可稳定失败","runtime_version":"commit-or-build-identifier","reproduced":true,"result":"pass","coverage":"complete","artifacts":[{"path":"src/profile.py","sha256":"实际SHA256"}],"evidence":[{"path":"docs/bugs/evidence/BUG-0001-run2.json","sha256":"实际SHA256"}]}
```

artifacts/evidence 均至少一个真实项目内文件，SHA256 必须匹配；提供所有影响行为的源码/配置/输入，不仅一个无关文件。可携带 evidence 记录方法、环境、原始日志位置、实际退出码、指纹和限制。每轮至少一个新的证据指纹，不能给旧证据换路径重用。脚本校验文件存在与哈希，AI负责核对证据是否支持宣称；版本文字和 pass 不是独立实验证明。

```json
{"id":"BUG-0001","kind":"user","source":"用户 2026-09-24 对本问题的明确验收消息","decision":"accepted"}
```

自动验收 kind=authorized_auto 时还须 authorization（授权来源与范围）、criteria（标准）、assessor（验收者）。字段不能创建授权。verify 仅进入 acceptance；accept 重新检查证据后进入 closed。复发/修改会清除当前验证和验收，历史始终保留。

### relate

```json
{"id":"BUG-0002","target":"BUG-0001","kind":"merge","reason":"已核实同一触发链与根因"}
```

kind=related 只建立关系；split 表示 id 为原问题、target 为先 create 的新子问题；merge 将 id 作为 target 的别名。合并保留两边全文/history、旧 ID，目标重新调查以覆盖合并范围。读取旧 ID 会得到 alias_of，可继续 show 目标；后续写旧 ID 解析到目标。禁止自身关联与别名循环。调查目标时须沿关系读原问题证据；不能仅因同样报错就 merge。

split 是明确交付依赖：建立关系会使原问题验证失效，子问题未验证时原问题不能 verify/accept，delivery 检查沿 split 关系查漏；related 不形成阻塞。拒绝拆分循环。merge 将来源修复、复发及逐项调查带入目标，继承 previous_repair 使用 `BUG-0002/FIX-0001` 形式；已完成调查保留，所有未完成调查须逐一 investigate 后重新修复验证。合并后新反馈仍能识别来源历史修复，来源旧验证证据也不能重用。含 split/split_from 依赖的问题拒绝直接 merge，先保留 related 并核对范围，避免别名吞掉依赖。
