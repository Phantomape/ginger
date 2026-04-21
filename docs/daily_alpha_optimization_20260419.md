# Daily Alpha Optimization Report - 2026-04-19

## 文档职责

本文件是“当日研究快照”，只记录某一天新增了什么发现、哪些优先级被调整、哪些方向被证伪或阻塞。

它不负责长期 doctrine，不重复 `AGENTS.md` 的流程约束，也不应该长期保存已经稳定成立的策略总纲。

长期有效的内容应上收至：

- `docs/alpha-optimization-playbook.md`：长期 alpha 地图、机制级启发、已证伪模式、当前默认优先级
- `docs/experiment_log.jsonl`：单次实验的参数、窗口、指标与接受/拒绝结论

使用本文件时，优先回答两个问题：

1. 今天新增了什么信息，改变了我们对系统的判断？
2. 这些新增信息是否已经上收为长期结论，还是仍然只是阶段性观察？

---

## 当日快照

日期：2026-04-19

日终系统状态：

- `expected_value_score = 0.7531`
- `sharpe_daily = 2.83`
- `max_drawdown_pct = 4.08%`
- 启用策略：`trend_long + breakout_long`
- `LLM replay coverage = 0%`
- `News veto coverage = 10.5%`

这一天的核心变化不是“新增了很多策略”，而是把系统从低 EV 状态推到了更清晰的 A+B 主线：

- 禁用默认拖累 EV 的 `earnings_event_long`
- 接受 `regime-aware exit`
- 接受 breakout 质量门控
- 接受 breakout bucket 内排序

---

## 当日新增信息

### 已确认有效

- `exp-20260418-003`
  结论：`earnings_event_long` 先禁用，避免在 P-ERN 数据未修复前继续拖累 EV。

- `exp-20260419-004`
  结论：`regime-aware exit` 能提升 EV，说明 exit 质量是当前真实 alpha 杠杆之一。

- `exp-20260419-007`
  结论：breakout 的问题更像“标的质量”问题，不是宏观压力日问题。

- `exp-20260419-008`
  结论：breakout bucket 内排序有效，说明 scarce-slot competition 确实存在 alpha。

### 已确认无效或应暂缓

- `exp-20260419-006`
  结论：按宏观压力环境关闭 breakout 无效，说明第三窗口 weakness 不是简单的 broad pressure 问题。

- `exp-20260419-009`
  结论：全局 breakout 风险折扣无效。质量筛选后剩余 breakout 暴露是有价值的，不应再做钝化式降权。

- `exp-20260420-001`
  结论：`above_200ma` 作为 breakout tie-breaker 没有增量信息。

- `exp-20260420-002`
  结论：`trend_long` 排序没有复制 breakout 排序的成功，主窗口无提升，另一个窗口恶化。

---

## 当日优先级调整

### 2026-04-19 收盘时的判断

当日原始建议是：

1. `NEW-A1`：trend_long ranking
2. `NEW-A4`：in-trade regime update
3. `NEW-A3`：C strategy revival（blocked by P-ERN）
4. `NEW-A2`：LLM soft ranking（blocked by P-LLM）

### 2026-04-20 补充后的修正

在 `exp-20260420-002` 完成后，这个排序已经改变：

1. `NEW-A4`：in-trade regime update
2. `NEW-A2`：LLM soft ranking（仍受 P-LLM 阻塞）
3. `NEW-A3`：C strategy revival（仍受 P-ERN 阻塞）
4. `NEW-A1`：trend_long ranking 暂缓，不应在无新证据时重试

---

## 当日最重要的机制结论

以下结论最初来自这份日报，但现在都应被视为长期结论，并以上收到 `playbook` 为准：

- breakout 的排序 alpha 不自动迁移到 trend
- `trend_long` 更像 `exit / hold-management` 问题，而不是 `ranking` 问题
- 以后要按“alpha 载体”而不是按“策略名字”组织优化方向
- 不要在 breakout 成功后陷入 ranking addiction

因此，本文件今后不再展开这些长期内容，只保留“它们是在什么时候被确认并触发了优先级变化”。

---

## 防重复提醒

后续代理读取本文件时，默认应避免直接重提以下方向：

- “breakout ranking 有效，所以 trend ranking 也应该有效”
- “继续给 trend_long 换一个接近的 ranking key 也许就会成功”

若未来重新打开 trend ranking，至少先回答：

1. 是否出现新的同日 trend slot collision 证据？
2. 新排序因子是否与 `momentum_10d_pct + pct_from_52w_high` 明显不同？
3. 为什么这次不是在重复 `exp-20260420-002`？

---

## 对下一轮的直接建议

如果下一轮按 alpha-first 原则启动，默认建议：

- 先测 `NEW-A4 / in-trade regime update`
- 不继续做新的 `trend_long ranking permutation`
- 若转去 `measurement_repair`，必须明确写清它在解除哪个 alpha 阻塞

---

## 关联记录

- 详细实验参数与指标：`docs/experiment_log.jsonl`
- 长期 alpha 地图与机制级启发：`docs/alpha-optimization-playbook.md`
- 顶层流程与门控约束：`AGENTS.md`
