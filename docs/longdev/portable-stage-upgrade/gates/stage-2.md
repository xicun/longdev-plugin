# 阶段 2 主会话 gate

2026-09-23：检查通过。V05实际阶段提交与V06安装/发布已验证，review无阻塞；成果尚待用户验收。

- V05：fb31eddca721c64a24b8adb5ee71744cbf13c1bb 包含28个授权路径，git diff-tree结果与提交清单完全一致；提交后子工作区clean，阶段记录已跟踪。
- V06：codex plugin add longdev@zzm-plugins --json exit 0；codex plugin list --json installed/enabled true，版本0.13.0+codex.20260923092211；实际缓存29文件与当前gate manifest的SHA256一致。
- 主会话从缓存脚本执行独立Git fixture迁移与--check，两次exit 0，旧状态保留；独立reviewer复验同样通过。原生CLI自动清理旧缓存的行为已在stages/2.md记录，未手动删除。
- git push gitee main exit 0；主会话和reviewer分别git ls-remote gitee refs/heads/main核实远端fb31edd。源码已发布，本阶段新增记录须在本gate后单独commit；最终tag/记录发布及父指针同步仍为收尾动作。
- 证据：evidence/installed-plugin.json、evidence/review-installed-plugin.json、reviews/stage-2.md。代码未变，复用阶段1当前有效24测试及产物指纹。

下一步：提交本阶段记录，整体独立审查；收尾记录再限定提交并发布。Windows真机与新模型会话长期执行未验证，不将安装验证扩大为此类结论。
