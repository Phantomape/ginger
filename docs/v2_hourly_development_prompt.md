# Ginger V2 每小时任务启动器

> 运行频率：`RRULE:FREQ=HOURLY;INTERVAL=1`
>
> 本文件只负责启动任务，不重复维护量化规则。完整规则以 `AGENTS.md` 指向的
> `docs/quant_agent_protocol_v2.md` 为准。

在专用、长期保留的 V2 checkout/worktree 中运行。每轮先读 `AGENTS.md`，再按 V2 protocol 完成一个
最小但完整的工作单元：查看现场、选择当前里程碑最靠前的任务、实现、验证、留 receipt 和接力棒。

硬边界：

- 保留用户的无关改动；
- 始终保持 `trade_enabled=false`，不得下单或调整真钱权限；
- 完整完成一次改动后即可git commit & push;
- 没有安全且有价值的工作时，以 `no-op audit` 收尾，不要为了小时产出硬开实验。

最后只报告：状态、改动文件、验证结果、对科学可信度或 parity 的影响、下一步和需要用户决定的问题。
