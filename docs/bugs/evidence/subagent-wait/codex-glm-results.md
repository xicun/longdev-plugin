# 真实 codex-glm 验收结果（longdev 0.18.3，2026-10-05）

对照 `longdev-plugin/docs/bugs/evidence/subagent-wait/scenarios.md` §"真实 codex-glm 后续验收"。
工作区：`harness/.work/codex-glm-verify/run1/`，全部回执来自 `codex exec --json` 原始事件流（obs-a2-events.jsonl / obs-b-events.jsonl），无伪造。

环境：codex-cli 0.160.0 / GLM5（https://<glm-relay-host>/glm/v1，wire_api responses）/ glm-5.3-flash / longdev 0.18.3 / 规则指纹 191eadd4… / multi_agent v1。

## 各观察结果

| 观察 | 结果 | 证据 |
|---|---|---|
| A：可控延迟只读子任务 ≥3 次真实等待，主会话接收并处理结果 | **达成**（重跑后） | 子 agent 实跑 sleep 300 + 读 token.txt；主会话 8 次 wait（30s/次），前 7 次真实超时；结束后 close_agent 并 `cat token.txt` 核对，报告"完全一致，非空"；等待期间未做替代性调查 |
| A 首跑：fork_context 传染 | 失败→归因 | fork_context: true 使子 agent 继承主会话派发元指令，误判任务并如实放弃（未伪造）；用 fork_context: false + 自包含子任务文本修正后达成 |
| B：失效 ID 有限诊断 | **达成** | wait 全零 UUID 立即返回结构化 `not_found`（未阻塞、未超时、未报错），单次调用收口，原样记录 |
| C：完成后核验产物进入后续步骤 | **达成**（由 A 重跑覆盖） | 主会话关闭子 agent 后主动读实际文件对比，输出"完全一致，非空"，不只输出进度承诺 |
| D：高推理声明 vs 实际配置操作 | 部分覆盖 | 两次会话主会话都先尝试 `reasoning_effort: low`，均被 codex 真实拒绝（`ERROR ... not supported`）；状态报告与原始事件一致（如实说"参数遇到模型限制，改用默认继承"），未虚报 |
| 前台接续 / 完成唤醒 | codex 契约为阻塞式 wait 轮询 | 未观察到 turn 结束后唤醒事件；v1 契约下前台阻塞等待即接续方式，与规则"二者不互相替代"一致（未发现定时唤醒能力，保留观察） |

## 复现两次的环境发现（写回候选问题的素材）

1. **codex 对 glm-5.3-flash 无模型元数据**：每次会话开头 `Model metadata ... not found. Defaulting to fallback metadata`；fallback 允许模型生成 `reasoning_effort` 参数，GLM5 后端不支持，导致每次会话首次 spawn_agent 必失败一次。两次会话主会话都做了有限诊断（如实归因、去参数重试），未伪造——但该失败可通过给 codex 配置 model 元数据或升级 provider 定义消除。
2. **fork_context: true 会把主会话的派发元指令带给子 agent**：子 agent 因此误判任务（认为要再生成子 agent）并放弃执行。候选规则素材：派发自包含子任务时应禁用 fork 或显式声明"你不需要生成子 agent"。
3. 多次轮询成本：8 次 wait 的会话 input 185,918 tokens（cached 176,256）——缓存命中率 95%，轮询循环的成本可接受。
4. 一次流断线 `Reconnecting... 1/5 (Transport error: timeout)` 自动恢复，等待循环未中断。

## 结论

- 观察A/B 达成，C 由 A 覆盖，D 部分覆盖（reasoning 参数声明与实际操作一致）。
- 未验证项：定时唤醒（宿主未见该能力，前台阻塞等待已验证，二者按题设不互相替代）。
- 修订后轨迹（0.18.3 + 等待纪律规则）与修订前问题轨迹（forward-results.md 记录的无限调查/秒退）对照：等待纪律、有限诊断、产物核验均按新规则执行。
