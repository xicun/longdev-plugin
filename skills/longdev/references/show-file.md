# 把落盘文件展示给用户

主会话在两个时点要让用户看一份完整文件，但**自己不读它**（读了就进 context）：

- 立项：planner 交出 `.claude/longdev/PLAN.draft.md`（每轮迭代后再展示一次）
- 收尾：final-reviewer 交出 `.claude/longdev/reviews/final.md`

展示方式按用户当前客户端决定。用一次 Bash 调用探测并执行（`<abs>` 换成文件的绝对路径）：

```bash
f="<abs>"
if [ "${CLAUDE_CODE_ENTRYPOINT:-}" = "cli" ]; then
  if command -v code >/dev/null 2>&1; then
    code --reuse-window --goto "$f:1" && echo "OPENED code"
  elif command -v cursor >/dev/null 2>&1; then
    cursor --reuse-window --goto "$f:1" && echo "OPENED cursor"
  else
    echo "NOEDITOR"
  fi
else
  echo "NOTCLI"
fi
```

按输出决定下一步：

| 输出 | 含义 | 做什么 |
|---|---|---|
| `OPENED code` / `OPENED cursor` | 终端 CLI，文件已在用户的编辑器窗口打开（`--reuse-window` 不新开窗口；已打开同一文件时只是刷新） | 回显里再附一次绝对路径即可 |
| `NOEDITOR` | 裸终端，没有可调的编辑器 | 回显绝对路径，告诉用户自己打开 |
| `NOTCLI` | 桌面 App / 网页版 / 其他非终端入口 | 有 `SendUserFile` tool 就用它（`display: "render"`）推到侧栏；没有就回显绝对路径 |

注意：

- `CLAUDE_CODE_ENTRYPOINT=cli` 是实机验证过的值；其他客户端的取值未验证，所以规则只区分"是 cli / 不是 cli"，不依赖具体值。
- 不要用 `start`/`open`/`xdg-open` 开 `.md`——系统没有关联时会弹"选择打开方式"。
- `SendUserFile` 在 CLI 里也存在但只显示一张不可点的卡片，所以 CLI 分支不要调它。
- 每次要展示时现跑探测，不缓存——同一个项目用户可能换客户端接着做。
- 无论哪个分支，回显里都要写文件的绝对路径，这是最后的兜底。
