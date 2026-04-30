# Alpha Optimization Playbook

## 文档职责

本文件是长期 alpha 手册，不是实验流水账。

它负责回答四个问题：

- 当前系统的 alpha 从哪里来？
- 哪些机制已经被验证、暂缓、阻塞或证伪？
- 下一轮最值得研究什么，为什么？
- 哪些思路不要重复尝试，除非出现新证据？

文档分工：

- `AGENTS.md`：门控、优先级约束、会话协议、实验纪律。
- `docs/experiment_log.jsonl`：单次实验的结构化主日志，保留参数、窗口、指标和结论。
- `docs/experiments/logs/*.json`：较新的单实验详细记录。
- `docs/experiments/artifacts/*.json` 与 `data/exp_*.json`：实验产物和审计明细。
- 本文件：把多轮实验后仍成立的结论压缩成长期 doctrine。

若本文档与 `AGENTS.md` 冲突，以 `AGENTS.md` 为准。若需要复现实验，先查本文档的实验索引，再查结构化日志。

## 1. 当前系统画像

当前系统不是高频、不是纯统计套利，也不是让 LLM 全权交易的黑箱。它更像：

> 事件增强型中短线趋势 / 突破交易系统。

当前可回放主力 sleeve：

- `trend_long`：更像持仓期管理和 winner capture 问题。
- `breakout_long`：更像标的质量、slot competition 和阶段适配问题。
- `earnings_event_long`：PEAD 大类仍有金融逻辑，但当前仓库实现尚未证明可稳定增厚 A+B。
- LLM / news：最适合事件理解、灾难 veto、结构化 grading / ranking；不适合接管仓位、止损、目标位和硬风控。

当前固定三窗口 baseline（最新 accepted stack，数据点来自 `data/backtest_results_20260429.json` 与同批固定窗口实验）：

| Window | Range | EV | Return | Sharpe daily | Max DD | Win rate | Trades | Main interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `late_strong` | 2025-10-23 -> 2026-04-21 | 2.4787 | +59.30% | 4.18 | 4.39% | 78.9% | 19 | accepted allocation stack 很强，risk-on sizing 已显著抬升 EV |
| `mid_weak` | 2025-04-23 -> 2025-10-22 | 1.0034 | +39.35% | 2.55 | 6.16% | 52.4% | 21 | 已明显改善，但仍是最需要解释的 meta-allocation / regime-routing 窗口 |
| `old_thin` | 2024-10-02 -> 2025-04-22 | 0.2267 | +18.58% | 1.22 | 6.91% | 40.9% | 22 | 仍是最脆弱窗口；弱带下 drawdown 与 win rate 约束最值得盯 |

最新 accepted-stack 测量盲区也要一并记住：news archive coverage 已升至 15/123 交易日（12.2%），但 production-aligned LLM ranking-eligible replay 仍只有 3 天 / 8 个信号，exit advisory replay 也仍处于 shadow-only 披露阶段。

北极星仍是 `expected_value_score = total_return_pct * sharpe_daily`，但任何策略逻辑改动必须做多窗口检查，不能只优化一个窗口。

## 2. 长期结论

### 2.1 当前最有价值的 alpha 不是无限加新 entry

多轮实验后，系统的高价值方向更像：

- 提纯已有 A+B 信号质量。
- 改善 exit / hold / add-on 生命周期管理。
- 让风险预算流向更高期望机会。
- 用 LLM 做结构化事件 grading / ranking，而不是让 LLM 做硬风控。

默认不优先：

- 围绕少数亏损样本新增规则。
- 继续堆 OHLCV-only entry 变体。
- 为了单窗口 Sharpe 好看而牺牲跨窗口稳定性。
- 把每个失败 trade 都解释成缺一个过滤器。

### 2.2 breakout 和 trend 的 alpha 载体不同

`breakout_long` 的 alpha 更偏：

- 标的质量筛选。
- bucket 内排序。
- 稀缺仓位槽位竞争。
- 对 fake breakout / crowded rotation 的适配。

`trend_long` 的 alpha 更偏：

- 持仓管理。
- target / stop / add-on / exit 质量。
- 在不同 market state 下是否继续让 winner run。

因此，breakout 上有效的排序规则不能默认迁移到 trend；trend 的下一步也不应反复扫 entry ranking key。

### 2.3 C 策略不是被永久否定，但“只差补数据”已经不成立

PEAD / post-earnings drift 作为大类 alpha 仍有研究依据，但当前仓库里的 `earnings_event_long` 已经不再能简单归因于数据缺口。

已知结论：

- `lxml` / earnings snapshot 修复后，C 策略可以真实回放。
- repaired-data 后，单字段 gate、小 checklist、共享质量分数 gate、standalone-day gate 都未能稳定让 `A+B+C` 跑赢 accepted `A+B`。
- C 策略若重启，需要更丰富的事件分级、边际槽位价值机制，或 LLM / news 对财报语义的结构化 grading。

不要继续把“再补一点 earnings 数据”当作默认主线，除非新增数据能直接释放一个清晰的 C 策略实验。

### 2.4 LLM 的正确方向是可审计 ranking / grading

长期边界：

- 代码负责仓位、止损、目标位、portfolio heat、行业暴露、硬过滤。
- LLM 负责新闻理解、事件分类、语义强弱、灾难 veto、结构化 ranking / grading。

当前阻塞：

- LLM replay 覆盖和 production-aligned effective sample 仍然很薄。
- soft ranking 不能只靠主观觉得“LLM 应该有用”来上线。
- 也不能因为历史回放缺口就否定 LLM；正确方向是补结构化输入输出和归因指标。

最新机制结论：

- backlog classification 已区分 `snapshot_only` 与真实 `context_only` 缺口，避免继续恢复没有实际上下文的日期。
- effective attribution subset 已加入，用于只统计生产对齐、ranking-eligible 的 LLM 样本。
- 已持仓过滤、同日行业上限、`BEAR_SHALLOW` 入场 gate 与 `NEUTRAL` / `BEAR_SHALLOW` 风险降档都已收敛到共享 helper；后续不要再接受 run/backtester 双份实现。
- trailing partial-reduce 现在已经可以共享回放；在有 15 次 partial reduction 的 fixed-window replay 中，它对当前 accepted stack 为负，因此“生产里看起来合理”不再是继续推广它的证据。

## 3. 当前优先级

默认下一轮从高到低：

1. `alpha_search` 优先，除非存在明确测量阻断项。
2. lifecycle alpha，尤其是已方向性为正但未 production-promoted 的 entry follow-through add-on。
3. meta-allocation / regime routing，重点解释 `mid_weak` 为什么赚钱但跑输指数。
4. LLM / news attribution repair，只在它能释放 soft ranking、news-confirmed exit 或 C strategy grading 时插队。
5. production/backtest parity 只在它能释放新的 alpha 实验或消除真实漂移时插队；不要把纯 parity 整理当作默认主线。
6. 新 universe / 新 entry 只做 shadow audit；不要直接接 production。

当前不建议继续消耗迭代的方向：

- 弱持仓 day-5/day-10 price-only early exit。
- 纯 OHLCV pullback reclaim / leadership / compression entry 的局部扫参。
- broad macro defensive overlay 的简单门控。
- C 策略的单字段或小 checklist 修修补补。
- entry follow-through add-on 的附近阈值微调。
- 没有 alpha 释放价值的 parity-only 重构。
- 仅凭直觉继续强化 production trailing partial-reduce 建议。

## 4. 机制状态表

| Mechanism family | Status | Long-term conclusion | Key experiments |
|---|---|---|---|
| Accepted A+B stack | accepted baseline | 三窗口均赚钱，late 强，mid 跑输指数，old win rate 不稳 | fixed-window backtests |
| Technology trend wider target | accepted | winner-truncation repair 可在窄 cohort 上成立 | exp-20260425 target-width family |
| Commodity trend wider target | accepted narrow | 部分 commodity trend winner 需要更宽 target，但不可泛化到 breakout | exp-20260425 target-width family |
| Single-position cap 25% | accepted | 改善 winner capture / risk allocation，保留 | exp-20260425 cap family |
| Trend Financials risk boost | accepted narrow | 已入选 Financials trend sleeve 在 mid/old 窗口重复贡献，适合 sizing boost；不要泛化成 sector priority | exp-20260429-015 |
| Entry follow-through add-on | promising, default-off | day2 `>= +2%` 且 RS vs SPY `> 0` 的 25% add-on 三窗口方向性为正，但 materiality modest | exp-20260426-009/010/011/012/035, exp-20260427-010/011 |
| LLM soft ranking | blocked / high-upside | 方向仍重要，但必须先有足够 production-aligned replay sample | exp-20260426-015/022/023 |
| News-confirmed weak-hold exit | blocked, not falsified | 概念比 price-only exit 干净，但 archive coverage 不足 | exp-20260425-037 |
| Earnings C strategy revival | deferred | PEAD 大类未死，但当前实现不是简单补数据能救 | exp-20260418+, C-gate families |
| Meta-allocation / regime routing | promising but early | `mid_weak` 问题更像什么时候用哪个 sleeve，而不是缺一个 entry | exp-20260423 meta series |
| Shared parity helpers | accepted governance | 入场 gate、regime risk sizing、partial-reduce 语义都应由共享 helper 驱动；未来不接受 run/backtester 双份逻辑 | exp-20260429-007/008/012 |
| Trailing partial reductions | measurable but rejected alpha | 现在可回放，但 replay-on 对当前 stack 为负；保留为共享可审计机制，不作为默认 alpha | exp-20260429-012 |
| Residual narrow sector pockets | accepted but overfit-prone | 可作为线索，不应无限挖残差 | exp-20260423/25 residual pocket series |
| Universe expansion scouts | observed-only | 事件/高 beta/mid-cap scouts 有线索，但受 snapshot / coverage 限制 | exp-20260426-013/021/025/031 |

## 5. 已证伪或降级的机制族

### 5.1 Weak-hold early exit

结论：不要用简单 day-5/day-10 弱势、RS lag、sector lag 作为早卖规则。

原因：

- 多数触发稀疏，收益改善极小。
- 容易截断 delayed winners，例如弱开局后恢复的大赢家。
- sector confirmation 未能救活 price-only weak-hold 模板。

除非新增信号是真正正交的 adverse information，例如新负面新闻、财报恶化、连续多日无法 reclaim，否则不要重试同构模板。

Key experiments：`exp-20260425-036`, `exp-20260425-037`, `exp-20260425-038`, `exp-20260426-059`。

### 5.2 Pullback / leadership / OHLCV-only new entry

结论：不要继续只靠近高、RS、pullback、inside-day、compression 等 OHLCV 形态反复造 D 策略。

原因：

- 严格定义样本太少。
- 放松定义后变成 noisy continuation clutter。
- 许多 shadow source 在一个窗口有 forward return，但跨窗口不稳。

如果重启，必须加入新的上下文来源，例如事件、sector leadership persistence、regime state，或先证明它与 A+B 有低重叠且跨窗口 forward return 稳定。

Key experiments：`exp-20260422-016`, `exp-20260423-001`, `exp-20260426-057`, pullback / VCP / opening-range / gap-and-hold / undercut-reclaim shadow audits。

### 5.3 Broad macro defensive overlay

结论：宏观/defensive 方向不能用简单 broad gate 或 gross haircut 直接上线。

原因：

- OR stress trigger 过宽，会误伤健康窗口。
- strict AND trigger 太稀疏或 vacuous。
- defensive / commodity 行为可能存在，但需要 sleeve routing 或更细状态，不是统一降风险。

如果重启，优先做 explainability map：什么状态下 `breakout_long`、`trend_long`、defensive exposure 各自应该拿风险。

Key experiments：`exp-20260423-013/014/015/016`, macro defensive v1/v2/budget, cross-asset proxy expansion。

### 5.4 C strategy single-field repair

结论：不要再用单字段 earnings gate 或小 checklist 试图救 C 策略。

原因：

- repaired-data 后仍拖累 A+B 或无法稳定通过多窗口。
- 问题更像事件质量分级和 slot opportunity cost，而非某个字段缺失。

如果重启，必须要么有 LLM 财报 grading，要么有更强 post-earnings continuation 机制。

### 5.5 Entry add-on local threshold tuning

结论：普通 strict add-on 仍是研究候选，但附近阈值不要再扫。

当前候选：

- checkpoint day: 2
- unrealized return: `>= +2%`
- RS vs SPY: `> 0`
- add-on size: `25%` original shares
- scheduling: allow schedule, enforce cap / heat on execution day

不要优先重试：

- RS 阈值 `0.5% / 1% / 2%`
- absolute unrealized threshold `3% / 4% / 5%`
- day1-to-day2 improvement filter
- checkpoint cap-room prefilter
- positive ticker day2 return confirmation

原因：这些都未稳定改善普通 `2% + RS>0 + 25%` 候选；多数只是减少有效 add-ons。

Key experiments：`exp-20260426-010/011/012/017/035`, `exp-20260427-010/011`。

## 6. Promising 但未生产化方向

### 6.1 Entry follow-through add-on

核心发现：

- trade-level approximation 先显示 day2 follow-through 有边。
- real BacktestEngine replay 后仍三窗口方向性为正。
- 但执行日 cap / heat 会吃掉大量理论收益，真实 effect size 较小。

代表结果：

- no-add-on -> ordinary 25% add-on：aggregate EV delta `+0.0447`，aggregate PnL `+$1,523.89`，3/3 windows improved。
- smaller fractions 10% / 15% 不如 25%。
- higher RS / higher unrealized threshold / improvement filter 都没有稳定胜过 ordinary candidate。

当前决策：

- 保留 default-off harness。
- 不默认上线。
- 下一步若继续，必须寻找 materiality unlock 或新 evidence source，而不是继续本地阈值微调。

可研究的下一步：

- cap / heat 是否过度阻止已确认 winner 的加仓，但这属于 capital allocation 实验，不是 add-on trigger 微调。
- forward sample 或 paper-trading 观察是否强化 materiality。
- LLM / news 是否能给 add-on 做事件确认，但需要 replay coverage。

### 6.2 LLM soft ranking / event grading

核心发现：

- LLM 仍是系统的合理优势来源，但不是硬风控执行器。
- 目前最大问题不是“LLM 有没有价值”，而是 replay archive / effective sample 还不够支撑归因。

下一步要求：

- 只统计 production-aligned、ranking-eligible 样本。
- 对 LLM 放行 / 降权 / veto 后收益做单独归因。
- 让 LLM 输出结构化字段，例如 event_type、event_strength、risk_type、time_sensitivity、confidence、ranking_reason。

### 6.3 Meta-allocation / regime routing

核心发现：

- `late_strong` 说明 A+B 在趋势友好期非常强。
- `mid_weak` 说明系统即使赚钱，也可能输给指数，问题不是单纯缺 signal，而是 allocation / sleeve routing。
- `old_thin` 说明弱环境下 win rate 低，可能需要状态识别或风险路由，而非新增局部 entry。

推荐研究框架：

- Market structure：breadth、equal-weight vs cap-weight、sector dispersion。
- Volatility / correlation：realized vol、intraday range、cross-asset pressure。
- Flow / positioning proxy：gap-up fade、leader reversal、fake breakout density。

不要直接跳到黑箱 classifier。先做少量、可回放、可解释的 state variables。

## 7. 已接受但需谨慎的窄规则

以下规则或 cohort 曾经通过多窗口或局部 Gate，但存在过拟合风险。它们可以作为当前 accepted stack 的组成或研究线索，但不要无限外推：

- `Technology trend` 更宽 target。
- `Commodity trend` 更宽 target。
- `single-position cap = 25%`。
- 若干 residual sector / DTE / near-high pockets。

使用原则：

- 不把窄 pocket 扩大成全局规则。
- 不用单窗口漂亮结果证明大类机制。
- 若新增相似 pocket，必须证明它不是既有 residual mining 的简单重复。

## 8. 失败记忆索引

下表不是完整日志，只是防止重复思路。完整参数查 `docs/experiment_log.jsonl` 或 `docs/experiments/logs/`。

| Family | Do not repeat without new evidence | Why |
|---|---|---|
| breakout breadth-only ranking | simple breadth scalar reorder | too weak / often null |
| pullback reclaim | nearby pullback/reclaim OHLCV thresholds | noisy continuation clutter |
| leadership D-strategy | near-high + RS only | strict too sparse, loose dilutes A+B |
| broad stress overlay | OR stress, simple gross haircut | overfires / wrong deployment shape |
| strict weak-tape AND | same two-feature AND as action trigger | often vacuous / insufficient exposure |
| macro defensive gate | simple cross-asset or defensive budget rule | not stable enough |
| weak-hold early exit | day-5/day-10 weak PnL / RS lag | truncates delayed winners |
| sector-confirmed weak exit | weak hold + same-sector lag | effect tiny and sparse |
| add-on RS tightening | global RS thresholds above 0 | removes profitable rotation-tape add-ons |
| add-on stronger unrealized | global thresholds above 2% | reduces realized add-on alpha |
| add-on improvement filter | day2 must improve vs day1 | not better than ordinary add-on |
| C strategy checklist | small earnings quality checklist | cannot overcome slot opportunity cost |

## 9. 下一轮实验队列

优先级 1：确认 add-on 的 materiality ceiling。

- 问题：严格 day2 follow-through add-on 已稳定为正，但真实收益小。下一步不是阈值，而是问“为什么 cap/heat 留不出空间，是否值得重分配风险？”
- 合格实验：default-off capital allocation replay，单一变量，只改变 cap / heat / add-on budget semantics。
- 风险：放松 cap 可能增加 concentration 和 tail risk，必须三窗口对比。

优先级 2：做 `mid_weak` 的 meta-allocation 解释图。

- 问题：`mid_weak` 绝对赚钱但跑输 SPY/QQQ，说明 allocation 不够适应 rotation-heavy bull。
- 合格实验：先做 audit / map，不直接改策略，输出 sleeve、sector、breadth、vol、fake-breakout density 的贡献分解。
- 风险：如果直接上 classifier，容易过拟合。

优先级 3：构造 LLM event grading replay 样本。

- 问题：LLM ranking 高 upside，但样本不够。
- 合格实验：增加结构化落盘和 effective attribution，不改变硬风控。
- 风险：不能让 LLM 在无归因时接管仓位或硬 veto。

优先级 4：新 universe / new D-strategy 只做 shadow。

- 问题：当前 universe 可能限制 alpha 搜索，但 snapshots 对 outside-production ticker 支持不足。
- 合格实验：先验证候选覆盖、重叠率、forward return、数据可用性，不接生产。
- 风险：shadow forward return 容易被幸存者偏差和 coverage bias 污染。

## 10. 证据级别

| Level | Meaning | Allowed use |
|---|---|---|
| L0 | 想法 / 金融直觉 | 只能写 hypothesis |
| L1 | shadow audit 有方向性 | 可进入 default-off replay |
| L2 | real backtester 三窗口方向性为正 | 可保留 harness / 继续研究 |
| L3 | 三窗口通过 Gate 4 且 effect size 足够 | 可考虑 production promotion |
| L4 | forward / paper / live 也确认 | 可提升为长期 accepted doctrine |

当前大多数新增方向只到 L1-L2。不要把 L1 shadow 当成生产 alpha。

## 11. 新实验写入规则

新增实验不要把完整流水账追加到本文档。只在以下情况下更新本文档：

- 一个机制族的状态改变了，例如 `promising -> accepted`、`promising -> rejected`、`blocked -> testable`。
- 出现新的防重复规则。
- 下一轮优先级发生变化。
- 有足够泛化价值的机制启发。

推荐写法：

```text
### Mechanism family name

Status: accepted / promising / rejected / blocked / deferred
Core conclusion: one paragraph.
Evidence: key experiment IDs and only the metrics needed to justify the state.
Do not repeat: nearby variants that are now low priority.
Next valid retry requires: concrete new evidence or changed data condition.
```

不要写入：

- 每个窗口的完整 stdout。
- 每个参数 sweep 的所有中间值。
- 已经在 `experiment_log.jsonl` 里的 JSON 字段。
- 只对单次实验有意义的过程性推理。

## 12. 快速启动清单

每轮开始读本文档时，先回答：

1. 本轮方向属于哪个 mechanism family？
2. 它是否踩中了第 8 节的防重复禁区？
3. 如果像旧方向的变体，新证据是什么？
4. 它是 `alpha_search` 还是解除 alpha 搜索阻塞的 `measurement_repair`？
5. 如果成功，会改变第 4 节状态表还是只是增加一条实验日志？

若第 5 点答案只是“增加一条实验日志”，默认不要改本文档，只写结构化实验记录。

### 2026-04-27 mechanism update: Entry follow-through add-on cap headroom

Status: promising, default-off.

Core conclusion: The clean strict day-2 trigger remains `unrealized >= 2%` and `RS vs SPY > 0`; nearby trigger tightening is now low priority. exp-20260427-012 moved the prior shadow-only cap-headroom audit into a real BacktestEngine config hook (`ADDON_MAX_POSITION_PCT`) and found that an add-on-only 35% position cap improved 3/3 fixed windows versus both no-add-on and ordinary 25% add-on.

Evidence: aggregate EV delta was `+0.1458` / PnL `+$4,415.14` versus no-add-on, and `+0.1011` / `+$2,891.25` versus ordinary 25% add-on. Max drawdown increased at most `+0.28 pp`; newly executed add-ons were 4.

Do not repeat: more local add-on trigger threshold tuning (`RS > 0`, day-2 unrealized thresholds, day1/day2 improvement filters).

Next valid retry requires: forward/paper evidence or an explicit production-promotion decision for the 35% add-on-only cap after reviewing concentration risk. Do not generalize this into a higher initial-entry position cap.

### 2026-04-27 mechanism update: Strict follow-through add-on production default

Status: accepted / production default.

Core conclusion: exp-20260427-013 promoted the strict day-2 follow-through add-on to the default backtester configuration with `ADDON_ENABLED=True` and `ADDON_MAX_POSITION_PCT=0.35`. The 25% initial-entry cap remains unchanged; the 35% cap applies only to follow-through add-ons after the existing day-2 `unrealized >= 2%` and `RS vs SPY > 0` trigger.

Evidence: fixed-window default-config replay matched the prior 35% headroom research harness. EV improved in all three windows versus no-add-on baseline: `late_strong 1.5039 -> 1.5855`, `mid_weak 0.4773 -> 0.5218`, `old_thin 0.1310 -> 0.1507`. Aggregate PnL improved by `$4,415.14` / `+6.57%`; max drawdown increased by at most `0.29 pp`.

Do not repeat: local add-on trigger threshold tuning. Keep day-2, `+2%` unrealized, and `RS > 0` as the clean trigger unless new forward evidence appears.

Next valid retry requires: live/paper concentration monitoring, or a genuinely new add-on evidence source. Do not generalize the 35% cap to initial entries or non-follow-through adds.

### 2026-04-27 mechanism update: Global capacity is not meta-allocation

Status: rejected.

Core conclusion: exp-20260427-014 tested whether the accepted A+B+strict-add-on stack was globally capacity constrained by sweeping `MAX_POSITIONS` across 4/5/6/7 on the fixed three-window snapshot set. The result does not support a global slot-count change. Wider capacity helped `mid_weak` PnL but added lower-quality exposure in `late_strong` and `old_thin`; tighter capacity helped only `old_thin` and damaged late/mid.

Evidence: versus the current default 5 slots, `MAX_POSITIONS=6` improved `mid_weak` PnL by `$2,020.42` but regressed `late_strong` EV by `-0.0206`, regressed `old_thin` EV by `-0.0050`, and increased `mid_weak` drawdown by `+1.28 pp`. `MAX_POSITIONS=7` damaged aggregate EV more sharply (`-0.2520` EV sum), while `MAX_POSITIONS=4` regressed two of three windows.

Do not repeat: nearby global `MAX_POSITIONS` scans as a default meta-allocation experiment.

Next valid retry requires: explicit market-state or sleeve-level conditioning that explains when additional slots should be used. The next meta-allocation step should map which sleeve/sector deserves risk in `mid_weak`, not change total portfolio capacity globally.

### 2026-04-27 mechanism update: Scarce-slot sleeve routing

Status: promising, default-off.

Core conclusion: exp-20260427-019 tested a conditional sleeve-routing rule rather than another global capacity change: when only one entry slot remains, defer `breakout_long` entries so the slot is preserved for `trend_long` candidates. This improved `mid_weak` and `old_thin` while leaving `late_strong` unchanged, supporting the exp-20260427-016 audit that scarce-slot trend entries have better marginal slot value than scarce-slot breakouts.

Evidence: EV deltas were `late_strong +0.0000`, `mid_weak +0.0491`, and `old_thin +0.0109`; aggregate PnL delta was `+$867.84`; max drawdown did not increase. The rule deferred 11 breakout candidates across the three windows.

Do not repeat: broad breakout de-risking, global `MAX_POSITIONS` changes, or combining this with add-on trigger tuning.

Next valid retry requires: stronger materiality, forward/paper confirmation, or a production-promotion decision that accepts the modest effect size. Keep it default-off until then.

### 2026-04-27 mechanism update: Scarce-slot threshold widening

Status: rejected.

Core conclusion: exp-20260427-020 tested whether the scarce-slot breakout defer rule should widen from `DEFER_BREAKOUT_WHEN_SLOTS_LTE=1` to `=2`. The wider rule improved `mid_weak` but behaved like broad breakout de-risking in `late_strong`, so the one-slot hook remains the best tested form.

Evidence: `slots_lte_2` produced EV deltas `late_strong -0.3648`, `mid_weak +0.1188`, `old_thin +0.0109`; aggregate EV delta was `-0.2351` and aggregate PnL delta was `-$3,237.82`. It deferred 23 breakout candidates versus 11 for the one-slot form.

Do not repeat: `DEFER_BREAKOUT_WHEN_SLOTS_LTE >= 2` as a threshold-only materiality unlock.

Next valid retry requires: an explicit market-state or sleeve-level discriminator that explains why broader breakout deferral should apply outside `late_strong`.

### 2026-04-27 mechanism update: Scarce-slot regime allowlist

Status: rejected.

Core conclusion: exp-20260427-021 tested whether the one-slot breakout defer hook could be made more robust with a simple market-regime allowlist. It could not. `BULL`-only exactly matched the unconditional one-slot rule because all useful deferrals occurred during BULL regimes, while `NEUTRAL/BEAR`-only never fired.

Evidence: `bull_only_lte_1` matched the exp-20260427-019 result exactly: aggregate EV delta `+0.0600`, PnL delta `+$867.84`, and 11 deferred breakouts. `neutral_bear_lte_1` had zero deferred breakouts and zero metric delta.

Do not repeat: simple `market_regime` allowlists for scarce-slot breakout deferral.

Next valid retry requires: a more specific state discriminator, such as sleeve/sector crowding, breadth, or marginal slot-quality context. Keep the existing one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot same-sector crowding

Status: rejected.

Core conclusion: exp-20260427-022 tested whether the one-slot breakout defer edge comes specifically from avoiding breakout candidates that add to same-sector exposure already held in the portfolio. It did not. The condition reduced the number of deferred breakouts versus the unconditional one-slot hook, but produced no EV improvement in `late_strong` or `mid_weak` and worsened `old_thin` EV/drawdown.

Evidence: EV deltas versus default were `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin -0.0009`; aggregate PnL rose only `$247.58` while max drawdown increased by `+1.55 pp`. The temporary hook deferred 5 breakouts across the three windows and was rolled back.

Do not repeat: same-sector held-count crowding as the next scarce-slot breakout discriminator.

Next valid retry requires: a different state variable, such as sector breadth, candidate-level rank gap, or explicit marginal slot-quality context. Keep the existing one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot same-day trend substitution

Status: rejected.

Core conclusion: exp-20260427-023 tested whether the one-slot breakout defer edge comes from direct same-day sleeve substitution. It does not. Requiring a same-day `trend_long` candidate before deferring `breakout_long` reduced deferrals from 11 to 3, produced zero EV change versus baseline in all three windows, and gave up the known unconditional one-slot improvement in `mid_weak` and `old_thin`.

Evidence: versus baseline, EV deltas were `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin +0.0000`; aggregate PnL delta was `$0.00`. Versus the unconditional one-slot hook, EV delta sum was `-0.0600` and PnL delta was `-$867.84`.

Do not repeat: same-day trend availability as the next scarce-slot breakout discriminator, or combinations of it with simple `market_regime` allowlists or same-sector held-count crowding.

Next valid retry requires: a different information source, such as candidate-level rank gap, breadth, or forward/paper evidence. The current evidence says the modest edge is more likely from leaving capacity open for later candidates than from same-day substitution.

### 2026-04-27 mechanism update: Scarce-slot candidate rank gate

Status: rejected.

Core conclusion: exp-20260427-024 tested whether the one-slot breakout defer edge could be made more precise by preserving top-ranked breakouts and only deferring lower-ranked breakout candidates. It could not. Candidate-rank thresholds `rank >= 2` and `rank >= 3` were EV-null versus baseline across all three fixed windows and gave up the known unconditional one-slot benefit.

Evidence: `rank_gte_2_lte_1` deferred only 3 breakouts and produced aggregate EV delta `+0.0000` / PnL delta `$0.00` versus baseline, compared with unconditional one-slot EV delta `+0.0600` / PnL `+$867.84`. `rank_gte_3_lte_1` deferred 0 breakouts and was inert.

Do not repeat: simple candidate-rank thresholds for scarce-slot breakout deferral, or combinations of rank thresholds with same-day trend availability, simple market-regime allowlists, or same-sector held-count crowding.

Next valid retry requires: a genuinely different information source such as breadth, candidate forward-quality context, or forward/paper evidence. The current evidence says the modest one-slot edge is not explained by weak same-day rank.

### 2026-04-27 mechanism update: Scarce-slot simple breadth gate

Status: rejected.

Core conclusion: exp-20260427-025 tested whether the default-off one-slot breakout defer edge could be explained by weak same-day universe breadth above the 50-day SMA. It could not. A strict `breadth <= 55%` condition was inert across all three fixed windows, while `breadth <= 65%` produced no EV improvement in late_strong or mid_weak and regressed old_thin.

Evidence: versus baseline, `breadth_lte_55_lte_1` deferred 0 breakouts and produced aggregate EV delta `+0.0000`. `breadth_lte_65_lte_1` deferred 3 breakouts but produced aggregate EV delta `-0.0134`, aggregate PnL delta `-$501.29`, and max drawdown increase `+0.19 pp`. The already-known unconditional one-slot hook remained best with aggregate EV delta `+0.0600` and PnL delta `+$867.84`.

Do not repeat: simple universe breadth-above-SMA thresholds as the next scarce-slot breakout discriminator.

Next valid retry requires: a genuinely different information source such as candidate forward-quality context, a richer breadth/dispersion map, or forward/paper evidence. Keep the existing one-slot scarce-slot hook default-off.

### 2026-04-27 mechanism update: Global TQS allocation ranking

Status: rejected.

Core conclusion: exp-20260427-026 tested whether the existing enriched `trade_quality_score` could be used as a global same-day allocation ranking key. It could not. Sorting all post-enrichment candidates by TQS regressed EV, PnL, Sharpe, and win rate in all three fixed windows, which means the current native strategy/order structure is carrying useful information that the heuristic TQS does not capture.

Evidence: EV deltas versus default were `late_strong -0.0746`, `mid_weak -0.0324`, and `old_thin -0.0706`; aggregate PnL delta was `-$5,555.30`. The temporary hook was rolled back after the failed Gate 4 check.

Do not repeat: global `trade_quality_score` sorting, confidence-score tie-break variants, or TQS-only allocation ordering as the next ranking experiment.

Next valid retry requires: a new information source or a narrower context that explains why TQS should dominate native ordering. Do not combine TQS sorting with scarce-slot breakout deferral unless a separate audit proves interaction value.

### 2026-04-27 mechanism update: Scarce-slot forward-quality audit

Status: observed-only / mechanism narrowed.

Core conclusion: exp-20260427-027 added measurement-only deferred-event details to the existing default-off one-slot breakout defer hook and measured deferred breakout forward returns. The one-slot hook still improved `mid_weak` and `old_thin` with no `late_strong` effect, but deferred breakouts were not uniformly weak. `mid_weak` deferred candidates were poor over 10/20 trading days; `old_thin` deferred candidates had positive 5/10 day average forward returns.

Evidence: metric deltas matched the known one-slot hook (`late_strong +0.0000`, `mid_weak +0.0491`, `old_thin +0.0109`; aggregate PnL `+$867.84`). Forward-quality audit: `mid_weak` deferred breakout 10d average `-7.81%` with 33.3% win rate; `old_thin` deferred breakout 10d average `+0.71%` with 75.0% win rate.

Do not repeat: same-day candidate-quality explanations that assume deferred breakouts are simply bad. This includes more TQS-only, rank-only, same-day trend availability, same-sector held-count, or simple breadth gates around the one-slot hook.

Next valid retry requires: forward/paper evidence, or a true capacity-timing discriminator that explains why leaving a slot open for later candidates beats taking the current breakout. Keep the one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot default promotion

Status: accepted / production default.

Core conclusion: exp-20260427-028 promoted the simple one-slot scarce-capacity sleeve-routing rule to default: when only one entry slot remains, defer `breakout_long` entries. This is a narrow capital-allocation rule, not broad breakout de-risking. The decision accepts modest but robust effect size because repeated attempts to add same-day discriminators failed, while the simple rule improved two fixed windows and regressed none.

Evidence: versus explicit no-defer baseline, EV deltas were `late_strong +0.0000`, `mid_weak +0.0491`, and `old_thin +0.0109`; aggregate PnL delta was `+$867.84`; max drawdown did not increase in any window and declined in `mid_weak` and `old_thin`. The rule deferred 11 breakout candidates across the three fixed windows.

Do not repeat: same-day scarce-slot explanation searches using simple rank, TQS, same-day trend availability, same-sector held-count, simple market-regime allowlists, or simple breadth thresholds.

Next valid retry requires: forward/paper concentration and opportunity-cost monitoring, or a new information source that explains capacity timing. Do not widen beyond one remaining slot without state-specific evidence.

### 2026-04-27 mechanism update: Extension weak-followthrough exit/ranking

Status: rejected.

Core conclusion: exp-20260428-007 checked whether an extended entry followed by strict short-term failure could become a clean lifecycle alpha. Even the all-three subset (entry day red, next close below entry open, and next-day RS vs SPY negative) was not good enough: it identified 10 losing trades worth `$3,626.04`, but still risked 3 winners worth `$3,828.88`, for a naive net of `-$202.84`.

Evidence: the broader exp-20260427-022 audit was worse (`-$21,607.85` naive net), and the strict subset still had winner collateral in `late_strong` and `mid_weak`. This means short-term OHLCV weakness after an extended entry is not sufficient adverse information by itself.

Do not repeat: nearby extension/weak-followthrough thresholds, entry-day red variants, next-close-below-entry variants, or simple next-day RS penalties as exit/reduce/ranking rules.

Next valid retry requires: an orthogonal adverse-information source such as negative news, earnings deterioration, or forward/paper evidence. Do not turn this into a production early-exit rule from OHLCV follow-through flags alone.

### 2026-04-27 mechanism update: Financials trend wider target

Status: rejected.

Core conclusion: exp-20260427-033 tested whether the accepted selective winner-truncation repair could extend from Technology/Commodities into `trend_long | Financials` with a single 6.0 ATR target. It cannot. The wider target had no late_strong exposure and materially damaged both weaker windows by delaying Financials trend exits and increasing drawdown.

Evidence: versus the current default stack, EV deltas were `late_strong +0.0000`, `mid_weak -0.2062`, and `old_thin -0.1219`; aggregate PnL delta was `-$10,170.05`, and max drawdown increased by up to `+3.54 pp`.

Do not repeat: broad Financials trend target widening or nearby 6.0-style target expansion as a simple extension of the Technology/Commodity target-width wins.

Next valid retry requires: a specific event or state discriminator that explains why wider Financials trend targets would not delay exits in `mid_weak` and `old_thin`. Do not generalize the accepted Technology/Commodity target-width mechanism to Financials.

### 2026-04-27 mechanism update: Second follow-through add-on

Status: promising but rejected for production materiality.

Core conclusion: exp-20260427-035 tested a day-5 second follow-through add-on after the accepted day-2 add-on. The idea is directionally positive and did not regress any fixed window, but the effect size is too small for production promotion under Gate 4.

Evidence: the best tested variant (`day5`, unrealized `>= +5%`, `RS vs SPY > 0`, `35%` original shares, `60%` add-on cap) improved EV in `late_strong` and `mid_weak`, was inert in `old_thin`, and executed 7 second add-ons. Aggregate EV delta was `+0.0655`, aggregate PnL delta was `+$1,658.82`, and max drawdown increased only `+0.01 pp`.

Do not repeat: nearby second-add-on size/cap tuning alone. The next retry needs forward/paper confirmation or a new independent evidence source that increases materiality without broadening concentration risk.

### 2026-04-27 mechanism update: Same-day sleeve ordering

Status: rejected.

Core conclusion: exp-20260427-036 tested whether same-day allocation should simply rank `trend_long` candidates ahead of `breakout_long` candidates when entry slots are scarce. It failed. The native signal order plus the accepted one-slot breakout defer rule remains better than global trend-first sleeve sorting.

Evidence: versus the current default stack, trend-first ordering regressed EV in `late_strong` (`1.5855 -> 1.5109`) and `mid_weak` (`0.5709 -> 0.5369`), and was inert in `old_thin`. Aggregate EV delta was `-0.1086`; aggregate PnL delta was `-$1,549.13`.

Do not repeat: global same-day trend-first ordering, simple sleeve-priority sorting, or broad breakout de-prioritization as a meta-allocation shortcut.

Next valid retry requires: a new information source or discriminator that explains when `breakout_long` should lose priority without broadly damaging strong or rotation tapes.

### 2026-04-27 mechanism update: Commodity breakout wider target

Status: rejected.

Core conclusion: exp-20260427-037 tested whether the accepted Commodity trend winner-truncation repair could extend to `breakout_long | Commodities` by widening target ATR to 5.0/6.0/7.0. It cannot be promoted. The only non-regressing variant, 5.0 ATR, was too small and only helped `late_strong`; 6.0/7.0 improved `mid_weak` SLV but damaged `late_strong` IAU/GLD by delaying exits and increasing drawdown.

Evidence: 5.0 ATR aggregate EV delta was `+0.0244` and PnL `+$307.94`, below Gate 4 materiality. 6.0 ATR aggregate EV delta was `-0.0313`; 7.0 ATR aggregate EV delta was `-0.0065`; both increased max drawdown by `+1.04 pp`.

Do not repeat: Commodity breakout target-width widening by nearby 5-7 ATR values, or mechanical extension of the accepted Commodity trend target-width rule into Commodity breakouts.

Next valid retry requires: a new event/state discriminator that explains why the `mid_weak` SLV breakout should be allowed to run longer without delaying `late_strong` IAU/GLD exits. Keep Commodity breakout exits on the current production target path.

### 2026-04-28 mechanism update: Commodity trend target-exit re-entry

Status: rejected.

Core conclusion: exp-20260428-002 tested whether accepted `trend_long | Commodities` winners should be re-entered after target exits. The post-target continuation audit looked tempting, but a production-path replay showed the simple same-ticker re-entry rule is inert: 7 scheduled re-entry signals created 0 incremental trades.

Evidence: fixed-window EV/PnL/Sharpe deltas were exactly `0.0000` in `late_strong`, `mid_weak`, and `old_thin`. The rule did not pass through existing slot/sizing/execution constraints, so no Gate 4 criterion passed.

Do not repeat: simple target-exit re-entry based only on `trend_long | Commodities` target exits, or any post-target forward-return audit treated as production evidence.

Next valid retry requires: a different execution semantic, such as explicit target extension before exit or a reserved lifecycle budget, tested as one independent causal variable with the fixed three-window replay.

### 2026-04-28 mechanism update: Commodity trend target extension above 7 ATR

Status: rejected.

Core conclusion: exp-20260428-003 tested the explicit target-extension-before-exit semantic suggested after the inert re-entry replay. Extending `trend_long | Commodities` from the current accepted 7 ATR target to 8 ATR helped `late_strong` and `old_thin`, but it materially damaged the rotation-heavy `mid_weak` window. Wider 9/10 ATR targets damaged `late_strong` severely.

Evidence: best variant 8 ATR produced EV deltas `late_strong +0.1630`, `mid_weak -0.1035`, `old_thin +0.0089`; aggregate PnL delta was only `+$656.83`, while `mid_weak` Sharpe fell `-0.25` and PnL fell `-$2,070.56`. 9/10 ATR variants had aggregate EV deltas below `-0.76`.

Do not repeat: nearby Commodity trend target-width sweeps above 7 ATR, or post-target continuation audits treated as production evidence.

Next valid retry requires: a state or event discriminator that explains when Commodity trend continuation should be held without damaging `mid_weak`; otherwise keep the accepted 7 ATR production target.

### 2026-04-28 mechanism update: Follow-through add-on fraction

Status: accepted / production default.

Core conclusion: exp-20260428-005 tested whether the accepted day-2 follow-through add-on was under-allocating to confirmed winners. Raising only `ADDON_FRACTION_OF_ORIGINAL_SHARES` from `0.25` to `0.50` improved EV in all three fixed windows while leaving entries, exits, add-on trigger thresholds, max add-on position cap, scarce-slot routing, LLM/news replay, and earnings unchanged.

Evidence: versus the 25% baseline, the 50% add-on fraction produced EV deltas `late_strong +0.0640`, `mid_weak +0.0374`, and `old_thin +0.0149`. Aggregate PnL improved by `$3,634.17` / `+5.016%`; max drawdown increased by at most `+0.09 pp`.

Do not repeat: nearby add-on fraction sweeps without forward/paper concentration evidence. This result changes add-on size only; it does not reopen day-2 trigger threshold tuning.

Next valid retry requires: concentration monitoring or a new independent evidence source. Keep `ADDON_CHECKPOINT_DAYS=2`, `ADDON_MIN_UNREALIZED_PCT=0.02`, `ADDON_MIN_RS_VS_SPY=0.0`, and `ADDON_MAX_POSITION_PCT=0.35` unchanged unless new evidence appears.

### 2026-04-28 mechanism update: Follow-through add-on position cap

Status: rejected for production materiality.

Core conclusion: exp-20260428-006 tested whether the newly promoted 50% day-2 add-on was still materially clipped by `ADDON_MAX_POSITION_PCT=0.35`. Raising only the add-on cap to 0.40/0.45/0.50 improved EV in all three fixed windows, but the effect was too small for Gate 4 and saturated at 0.40.

Evidence: best variants all matched at `ADDON_MAX_POSITION_PCT=0.40+`, with EV deltas `late_strong +0.0103`, `mid_weak +0.0162`, and `old_thin +0.0041`. Aggregate PnL delta was only `+$697.26` / `+0.916%`, below the 5% PnL gate and below the EV materiality threshold. Drawdown did not increase.

Do not repeat: nearby add-on cap sweeps above 0.35 as a production-promotion attempt. The cap leak is real but too small in the fixed windows.

Next valid retry requires: forward/paper concentration evidence, or a new independent add-on allocation signal that increases materiality without reopening day-2 trigger threshold tuning.

### 2026-04-28 mechanism update: Adverse next-open entry cancel

Status: accepted / production default.

Core conclusion: exp-20260428-017 tested whether entries that open modestly below signal entry are lower-quality fills rather than bargains. A 2% adverse next-open cancel improved EV in all three fixed windows and passed Gate 4 on aggregate PnL, while 1% was too tight and 3% lost the mid_weak benefit.

Evidence: versus the no-adverse-cancel baseline, `ADVERSE_GAP_CANCEL_PCT=0.02` produced EV deltas `late_strong +0.0718`, `mid_weak +0.1014`, and `old_thin +0.0002`; aggregate PnL delta was `+$4,319.99` / `+5.678%`. The rule cancelled 7 adverse-gap entries across the three fixed windows.

Risk: `mid_weak` max drawdown increased by `+1.40 pp`, so forward monitoring should focus on whether the rule improves PnL by admitting replacement trades while increasing interim drawdown.

Do not repeat: tightening the adverse gap threshold to 1%, or treating 3% as equivalent to 2%. The tested 1% threshold regressed late_strong and mid_weak; 3% preserved late/old but lost the mid_weak materiality.

Next valid retry requires: a genuinely different state discriminator around adverse gaps, or forward evidence that the mid_weak drawdown tradeoff is undesirable. Do not combine this with add-on threshold tuning or LLM/news ranking until each branch has separate evidence.

### 2026-04-28 mechanism update: Upside next-open entry cancel

Status: rejected.

Core conclusion: exp-20260428-021 tested whether the existing `CANCEL_GAP_PCT=0.015` upside next-open cancel was mis-sized. It was not. Tightening to 1% helped `late_strong` only trivially and materially damaged `mid_weak` and `old_thin`; loosening to 2%/3%/5% or disabling the rule admitted lower-quality fills and regressed aggregate EV/PnL.

Evidence: the best nonbaseline variant by aggregate EV was 2%, but it still had aggregate EV delta `-0.1391` and PnL delta `-$4,423.90` versus the current 1.5% baseline. Tightening to 1% had aggregate EV delta `-0.3313` and PnL `-$11,894.16`; disabling the upside cancel had aggregate EV delta `-0.7824` and PnL `-$17,821.97`.

Do not repeat: nearby global `CANCEL_GAP_PCT` sweeps around 1-5%, including disabling the upside gap cancel.

Next valid retry requires: a state or event discriminator explaining when upside gaps are momentum confirmation instead of overextension. Do not combine this with adverse-gap or add-on threshold changes without separate evidence.

### 2026-04-28 mechanism update: Upside-gap sleeve exception

Status: rejected.

Core conclusion: exp-20260428-022 tested whether accepted winner-truncation sleeves could justify an exception to the existing 1.5% upside next-open cancel. They cannot. `trend_long | Technology` improved late_strong EV but reduced aggregate PnL and regressed old_thin; `trend_long | Commodities` damaged late_strong; combining both cohorts was worse.

Evidence: best variant `trend_technology_exception` had EV deltas `late_strong +0.3726`, `mid_weak +0.0000`, and `old_thin -0.0047`, but aggregate PnL delta was `-$1,960.99`. `trend_commodity_exception` had aggregate EV delta `-0.3162` and PnL `-$4,254.55`; combined Technology+Commodity had aggregate PnL `-$6,133.77`.

Do not repeat: Technology/Commodity trend upside-gap cancel exceptions based only on accepted target-width or winner-truncation evidence.

Next valid retry requires: an orthogonal event/state source explaining why a specific upside gap is confirmation, such as fresh positive news, earnings context, or forward/paper evidence. Sector/strategy membership alone is not enough.

### 2026-04-28 mechanism update: Adverse-gap context exceptions

Status: rejected.

Core conclusion: exp-20260428-023 tested whether the newly accepted 2% adverse next-open cancel should have narrow context exceptions. It should not, at least not from simple sector, strategy, full-risk, or TQS predicates. The active exception variants either regressed the strong window or regressed all three fixed windows; the only zero-delta variant was inert because it found no qualifying exceptions.

Evidence: `trend_commodities_exception` allowed 4 late_strong adverse-gap entries and reduced aggregate EV by `-0.2279`, PnL by `-$906.85`, and increased max drawdown by `+1.40 pp`. `full_risk_trend_exception` and `high_tqs_exception` each allowed 7 adverse-gap entries, regressed all three windows, and reduced aggregate PnL by `-$4,715.80`. `breakout_energy_exception` triggered 0 exceptions and is not evidence of edge.

Do not repeat: adverse-gap exceptions based only on sector, strategy, full-risk status, or TQS. Do not weaken `ADVERSE_GAP_CANCEL_PCT=0.02` with a simple context allowlist.

Next valid retry requires: an orthogonal signal that explains why a specific adverse open is recoverable, such as intraday reclaim behavior, fresh positive event context, or forward/paper evidence. Keep the accepted 2% adverse-gap cancel unchanged meanwhile.

### 2026-04-28 mechanism update: Signal-day weak close entry cancel

Status: rejected.

Core conclusion: exp-20260428-024 tested whether A/B signals that failed to
close in the upper part of their own signal-day range should be cancelled at
next open. They should not. Even the loosest tested threshold,
`close_location < 0.50`, regressed EV and PnL in all three fixed windows.

Evidence: versus the current baseline, the best variant had EV deltas
`late_strong -0.4877`, `mid_weak -0.1738`, and `old_thin -0.1367`.
Aggregate PnL fell by `$20,677.68` / `-25.7168%`, with 13 signal-day
close-location cancels across the three windows.

Do not repeat: simple signal-day close-location entry cancels or nearby
0.50-0.70 thresholds as price-only signal-quality filters.

Next valid retry requires: an orthogonal event, intraday reclaim, or
forward/paper signal explaining why a weak signal-day close is harmful in one
context but not another. Do not combine this with gap-cancel threshold changes
without separate evidence.

### 2026-04-28 mechanism update: Initial position cap allocation

Status: accepted / production default.

Core conclusion: exp-20260428-025 tested whether the accepted 50% day-2 add-on
made the old 25% initial position cap too conservative. Raising only
`MAX_POSITION_PCT` to 40% improved EV in all three fixed windows and passed
Gate 4 on aggregate PnL. Lower caps at 15% and 20% damaged all windows; 30% was
directionally positive but missed materiality.

Evidence: versus the 25% baseline, the 40% cap produced EV deltas
`late_strong +0.0626`, `mid_weak +0.0641`, and `old_thin +0.0067`.
Aggregate PnL improved by `$5,602.35` / `+6.9676%`; max drawdown increased by
at most `+0.47 pp`; trade count did not change.

Risk: this is a capital-allocation change, not a new entry edge. It increases
single-name concentration and should be monitored for tail-loss clustering in
forward/paper runs.

Do not repeat: nearby initial-cap sweeps above 40% or below 25% without new
forward concentration evidence. The next valid retry needs an independent
allocation signal rather than simply raising the cap again.

### 2026-04-28 mechanism update: Reduced-risk initial cap

Status: rejected / strict null.

Core conclusion: exp-20260428-026 tested whether non-zero reduced-risk signals
should use a lower initial concentration cap after `MAX_POSITION_PCT` moved to
40%. They should not be changed globally. The tested 20%/25%/30% caps never
bound any reduced-risk position in the fixed windows, so the mechanism is not a
current allocation leak.

Evidence: EV, PnL, Sharpe, drawdown, trade count, and win rate deltas were all
exactly `0.0000` in `late_strong`, `mid_weak`, and `old_thin`; aggregate cap
bind count was `0`.

Do not repeat: nearby reduced-risk initial-cap values or generic "lower cap for
all reduced-risk positions" ideas.

Next valid retry requires: new concentration evidence or a narrower quality
bucket that actually reaches the position cap.

### 2026-04-28 mechanism update: Same-day sector cap

Status: rejected.

Core conclusion: exp-20260428-027 tested whether the global same-day sector cap
should move from `2` to `1` or `3`. Keep it at `2`. Tightening to `1` removed
profitable clustered exposure in all three fixed windows; relaxing to `3` was a
strict null under current slot competition.

Evidence: `MAX_PER_SECTOR=1` EV deltas were `late_strong -0.3724`,
`mid_weak -0.0566`, and `old_thin -0.0545`, with aggregate PnL
`-$14,411.22`. `MAX_PER_SECTOR=3` had aggregate EV/PnL deltas `0.0000`.

Do not repeat: nearby global sector-cap values as a capital-allocation shortcut.

Next valid retry requires: a state- or sleeve-specific sector leadership signal,
not a global cap change.

### 2026-04-28 mechanism update: Portfolio heat budget

Status: rejected.

Core conclusion: exp-20260428-028 tested whether the accepted 40% initial cap
and 50% day-2 add-on made the global `MAX_PORTFOLIO_HEAT=0.08` too tight. It
did not. Raising heat to 10%/12% released two late-strong add-ons and slightly
improved old_thin, but left mid_weak unchanged and missed Gate 4 by a wide
margin; lowering heat to 6% damaged all active windows.

Evidence: best variant `MAX_PORTFOLIO_HEAT=0.10` had EV deltas
`late_strong +0.0244`, `mid_weak +0.0000`, and `old_thin +0.0003`.
Aggregate PnL improved only `$588.01` / `+0.6837%`, with no drawdown, win-rate,
or trade-count improvement. The 12% variant matched 10%, so the effect already
saturated.

Do not repeat: nearby global portfolio-heat sweeps around 6-12% as a simple
materiality unlock for add-ons.

Next valid retry requires: an independent allocation signal or forward/paper
concentration evidence explaining when extra heat should be spent. Do not
combine heat-budget changes with add-on trigger, add-on cap, or initial-cap
changes without separate evidence.

### 2026-04-28 mechanism update: Candidate quality ordering

Status: rejected.

Core conclusion: exp-20260428-029 tested whether same-day slot competition
should globally sort candidates by existing `trade_quality_score` or
`confidence_score` before entry planning. It should not. The native ordering
plus the current breakout-only 52-week-high rerank remains better than a broad
quality-score sort.

Evidence: the best tested nonbaseline variant, `confidence_desc_order`, was
unchanged in `late_strong` but regressed `mid_weak` and `old_thin`; aggregate
EV delta was `-0.1425`, and aggregate PnL fell `$6,212.28` / `-7.2229%`.
`tqs_desc_order` also regressed all three fixed windows, including
`late_strong`.

Do not repeat: simple global candidate ordering by TQS, confidence, or nearby
score-only rank keys as a same-day allocation shortcut.

Next valid retry requires: a state-specific or event-backed ordering
discriminator that explains when the native order should be overridden. Do not
combine ordering changes with cap, heat, gap-cancel, or add-on parameter
changes without separate evidence.

### 2026-04-28 mechanism update: Scarce-slot breakout exceptions

Status: rejected.

Core conclusion: exp-20260428-030 tested whether the accepted one-slot
scarce-slot breakout deferral should allow candidate-level exceptions for
apparently stronger breakouts. It should not, at least not from existing
`trade_quality_score` or 52-week-high proximity fields.

Evidence: the best tested variant, `near_high_breakout_exception`, was
unchanged in `late_strong` and `mid_weak` but regressed `old_thin` by
`EV -0.0448` and PnL `-$2,169.46`. The diagnostic no-deferral variant and
`high_tqs_breakout_exception` also failed Gate 4.

Do not repeat: scarce-slot breakout exceptions based only on TQS,
confidence-adjacent quality, or 52-week proximity.

Next valid retry requires: an orthogonal event/state source that explains why a
specific deferred breakout deserves the last slot. Keep the current one-slot
scarce-slot breakout deferral unchanged.

### 2026-04-28 mechanism update: Second follow-through add-on after cap promotion

Status: rejected.

Core conclusion: exp-20260428-031 retested the prior best day-5 second
follow-through add-on after the production stack changed to a 50% day-2 add-on
and 40% initial cap. The new capital base did not make the second add-on
material. It helped only `mid_weak`, regressed `late_strong`, and was inert in
`old_thin`.

Evidence: versus the current default stack, enabling the day-5 second add-on
with unrealized `>= +5%`, `RS vs SPY > 0`, 35% original shares, and 60% add-on
cap produced EV deltas `late_strong -0.0081`, `mid_weak +0.0418`, and
`old_thin +0.0000`. Aggregate PnL improved only `+$717.99` / `+0.8348%`,
below Gate 4 materiality, with 4 second add-ons executed.

Do not repeat: nearby second-add-on size/cap tuning after the 40% initial cap
promotion. The mechanism remains directionally interesting but too small for
production.

Next valid retry requires: forward/paper evidence or an orthogonal confirmation
source such as event context. Keep `SECOND_ADDON_ENABLED=false` meanwhile.

### 2026-04-28 mechanism update: State-gated breakout deferral

Status: rejected.

Core conclusion: exp-20260428-032 tested whether the accepted one-slot
scarce-slot breakout deferral should only fire when the weaker of SPY/QQQ is
not far above its moving average. It should not be promoted. Relaxing deferral
in stronger index states admitted lower-quality breakouts in the weaker
windows, and the best tested gate still reduced aggregate EV/PnL.

Evidence: the best variant, `DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA=0.08`,
was unchanged in `late_strong` and `mid_weak`, but regressed `old_thin` by
`EV -0.0099` and PnL `-$226.65` aggregate, while increasing max drawdown by
`+1.58 pp`. Looser 0%/3%/5% gates damaged both `mid_weak` and `old_thin`.

Do not repeat: nearby global SPY/QQQ moving-average distance thresholds as the
state gate for scarce-slot breakout deferral.

Next valid retry requires: a more explanatory state source such as breadth,
dispersion, or event-backed breakout confirmation. Keep the current always-on
one-slot breakout deferral unchanged.

### 2026-04-28 mechanism update: Near-stop next-open entry cancel

Status: rejected.

Core conclusion: exp-20260428-033 tested whether entries that open below signal
entry but still above the planned stop should be cancelled when most of the
initial stop distance has already been consumed. This does not improve alpha.
Tight 15%/25% remaining-risk thresholds were inert in all three fixed windows;
looser 35%/50% thresholds only added one active cancel in `late_strong` and
materially damaged that window.

Evidence: best variants 15%/25% had aggregate EV and PnL deltas exactly
`0.0000`. Active variants 35%/50% reduced `late_strong` EV by `-0.2531` and
PnL by `-$4,154.41`, while `mid_weak` and `old_thin` were unchanged.

Do not repeat: nearby near-stop / remaining-risk next-open cancel thresholds as
a standalone entry execution filter.

Next valid retry requires: a new discriminator such as intraday reclaim
behavior, fresh event context, or forward/paper evidence. Keep the accepted
2% adverse-gap cancel unchanged.

### 2026-04-28 mechanism update: Profit-protective stop after early MFE

Status: rejected.

Core conclusion: exp-20260428-034 tested whether positions that first reached
`+3%` MFE should have their stop raised to breakeven, `+1%`, or `+2%`. This is
not a viable lifecycle alpha. It prevented some small losses, but it truncated
far more trend and breakout winners across every fixed window.

Evidence: the best variant, breakeven protection after `+3%` MFE, had EV deltas
`late_strong -1.1759`, `mid_weak -0.5094`, and `old_thin -0.1420`. Aggregate
PnL fell `-$49,004.06` / `-56.9764%`, with 0/3 windows improved and 53 changed
trades.

Do not repeat: simple breakeven / small-profit protective stops after early MFE,
or nearby `0-2%` stop locks after `+3%` MFE.

Next valid retry requires: an orthogonal adverse context such as failed
intraday reclaim, fresh negative event context, or forward evidence that
separates decaying losers from ordinary noisy winners. Do not add generic
profit protection to the accepted stack.

### 2026-04-28 mechanism update: ETF universe expansion

Status: rejected.

Core conclusion: exp-20260428-035 tested whether liquid sector/defensive ETF
proxies already present in the fixed snapshots should become tradeable universe
candidates. Broad ETF expansion and narrower sector/defensive variants did not
pass the fixed-window Gate 4 checks. The best variant, `XLE + USO`, released
large `late_strong` Energy continuation upside but displaced better A+B
opportunities in `mid_weak` and still regressed `old_thin`.

Evidence: `energy_only_etfs` produced EV deltas `late_strong +0.3609`,
`mid_weak -0.2328`, and `old_thin -0.0226`; aggregate PnL improved only
`+$334.72` / `+0.389%`, far below Gate 4 materiality, with 1/3 windows
improved. Broad sector/defensive expansion had positive aggregate EV only
because of `late_strong`, but aggregate PnL was `-$3,232.14`.

Do not repeat: broad sector/defensive ETF additions as a simple tradeable
universe expansion, or single-ETF additions such as XLE/XLP without a state
discriminator.

Next valid retry requires: a state or event discriminator explaining when
Energy/USO continuation deserves scarce slot competition, plus sector mapping
and production watchlist parity before any production promotion.

### 2026-04-29 mechanism update: Global position slot count

Status: rejected.

Core conclusion: exp-20260429-001 tested whether the accepted 40% initial cap
and 50% day-2 add-on changed the right global `MAX_POSITIONS` count. It did
not. The current `MAX_POSITIONS=5` remains the most robust fixed-window setting.
Cutting to 4 slots slightly improved `old_thin` but damaged the stronger
`late_strong` and `mid_weak` windows; raising to 6 or 7 admitted weaker
marginal trades and regressed all three windows.

Evidence: best nonbaseline variant `MAX_POSITIONS=4` had EV deltas
`late_strong -0.0748`, `mid_weak -0.1498`, and `old_thin +0.0069`, with
aggregate PnL delta `-$6,900.39` / `-8.023%`. `MAX_POSITIONS=6` and `7`
regressed all three fixed windows.

Do not repeat: nearby global slot-count sweeps as a capital-allocation shortcut.

Next valid retry requires: a state-specific or sleeve-specific allocation signal.
If slot count is revisited, the variable should be routing which sleeve gets the
scarce slot, not a global portfolio slot count.

### 2026-04-29 mechanism update: Sector-persistence entry source

Status: rejected.

Core conclusion: exp-20260429-002 tested whether sector-relative persistence
candidates should become a new executable entry source. The shadow signal did
not survive real slot, gap-cancel, sizing, add-on, and exit mechanics. It
injected many marginal trades and displaced stronger native A/B opportunities
in every fixed window.

Evidence: enabling `sector_persistence_long` produced EV deltas
`late_strong -1.4585`, `mid_weak -0.6688`, and `old_thin -0.1613`. Aggregate
PnL fell `-$53,807.02` / `-62.5608%`, with 0/3 windows improved and 97
sector-persistence trades added across the three windows.

Do not repeat: promoting sector-relative persistence from shadow forward-return
evidence directly into an entry source, or nearby 20d/60d sector-relative
threshold tuning without an orthogonal discriminator.

Next valid retry requires: a state/event discriminator that explains when a
sector-persistence candidate deserves scarce slot competition, or a different
candidate-pool source with production watchlist parity. Treat simple sector
momentum entries as noise until that evidence exists.

### 2026-04-29 mechanism update: State-gated extra slot

Status: rejected.

Core conclusion: exp-20260429-003 tested whether the rejected global sixth slot
could be rescued by allowing it only when both SPY and QQQ were strongly above
their 200-day moving averages. It should not be promoted. The strictest tested
gate helped the rotation-heavy `mid_weak` window, but still damaged
`late_strong` and `old_thin`; looser gates admitted weak marginal trades.

Evidence: best variant `min(SPY, QQQ) pct-from-200MA >= 10%` had EV deltas
`late_strong -0.0423`, `mid_weak +0.4616`, and `old_thin -0.0322`; aggregate
PnL fell `-$6,031.94` / `-7.0133%`, with only 1/3 windows improved.

Do not repeat: nearby SPY/QQQ pct-from-200MA thresholds as a sixth-slot state
gate, or simple index-distance gates as a capacity unlock.

Next valid retry requires: a genuinely different state source such as breadth,
dispersion, event context, or forward/paper evidence explaining which sleeve
deserves extra capacity. Keep `MAX_POSITIONS=5`.

### 2026-04-29 mechanism update: RS-gated Technology breakout target

Status: rejected.

Core conclusion: exp-20260429-004 tested whether the rejected broad Technology
breakout target-width idea could be rescued by widening targets only for
Technology breakouts with strong `rs_vs_spy`. It cannot be promoted. Candidate
RS gating improved `mid_weak` and aggregate PnL, but the same late-window EV
and Sharpe damage remained, so the variant failed the EV-first multi-window
gate.

Evidence: best variant `rs_vs_spy >= 5%` with a 6 ATR target had EV deltas
`late_strong -0.1994`, `mid_weak +0.0439`, and `old_thin +0.0000`. Aggregate
PnL improved `+$2,491.07` / `+2.8963%`, but aggregate EV fell `-0.1555` and
`late_strong` Sharpe daily fell `-0.57`.

Do not repeat: nearby Technology breakout target widths or simple
`rs_vs_spy` thresholds as the discriminator for wider Technology breakout
targets.

Next valid retry requires: an orthogonal event/state source, such as fresh
positive news, LLM event grading coverage, or forward evidence explaining why a
specific Technology breakout deserves a wider target without degrading the
dominant strong tape.

### 2026-04-29 mechanism update: Sector-sleeve priority ordering

Status: rejected.

Core conclusion: exp-20260429-005 tested whether stable Commodities/Financials
A+B candidates should be mechanically moved earlier in entry planning. They
should not. The best variant, `commodities_first`, left `late_strong` and
`old_thin` unchanged but damaged `mid_weak`; adding Financials priority
further damaged `old_thin`.

Evidence: best variant `commodities_first` had EV deltas
`late_strong +0.0000`, `mid_weak -0.0566`, and `old_thin +0.0000`.
Aggregate PnL fell `-$1,190.49` / `-1.3842%`, trade count rose by 1, and win
rate fell by 2.38 pp in the active window. Financials-priority variants
regressed `old_thin` more sharply.

Do not repeat: simple Commodities/Financials priority ordering as a
meta-allocation shortcut, or nearby sector-priority permutations without a new
state/event discriminator.

Next valid retry requires: breadth, dispersion, event context, or forward
evidence explaining when a sector sleeve deserves earlier slot access. This is
distinct from the already-rejected global sector cap and sector-persistence
entry source, but it reaches the same conclusion: sector labels alone are not a
strong enough allocation signal.

### 2026-04-29 mechanism update: Index-dispersion extra slot

Status: rejected.

Core conclusion: exp-20260429-006 tested whether the rejected sixth slot could
be rescued by using QQQ-vs-SPY 200MA-distance spread as a rotational-tape
discriminator. It should not be promoted. Variants that actually released extra
capacity damaged at least one fixed window; the apparent best EV/Sharpe variant
released zero extra slots and changed no trades or PnL, so it was rejected as a
harness artifact rather than alpha.

Evidence: `qqq_leads_spy_by_2pct` released 20 extra-slot days but regressed
`mid_weak` PnL by `-$3,613.11` and had 2/3 EV windows improved with 1/3
regressed. `balanced_index_spread_lte_2pct` released 23 extra-slot days but
reduced aggregate PnL by `-$1,989.77` and also regressed one window. The
zero-behavior `qqq_leads_spy_by_4pct` showed aggregate EV delta `+1.5402` only
because no trades changed; that is not valid promotion evidence.

Do not repeat: nearby SPY/QQQ leadership-spread thresholds as a sixth-slot
capacity unlock, or any extra-slot experiment that accepts Sharpe/EV movement
without changed trades, PnL, or slot-release counts.

Next valid retry requires: richer breadth/dispersion, event context, or
forward/paper evidence explaining which sleeve deserves extra capacity. A clean
extra-slot harness should also avoid the backtester top-level max-position skip
artifact before using Sharpe as acceptance evidence.

### 2026-04-29 mechanism update: ATR trailing full-exit lifecycle

Status: rejected.

Core conclusion: exp-20260429-009 tested whether current fixed target/stop
exits should be replaced by ATR trailing full exits after a profit trigger.
They should not. All six tested trigger/offset cells reduced EV and PnL in all
three fixed windows.

Evidence: the best variant, `TRAIL_TRIGGER_ATR_MULT=3.0` with
`TRAIL_OFFSET_ATR_MULT=2.0`, had EV deltas `late_strong -0.5018`,
`mid_weak -0.4186`, and `old_thin -0.1673`; aggregate PnL fell
`-$30,150.41`. The worst tested variant fell `-$68,250.09` aggregate PnL.

Do not repeat: broad ATR trailing-stop full exits or nearby trigger/offset
cells as a lifecycle alpha. Also do not use trailing-stop backtest
profitability to justify repeated production partial-reduce advice.

Next valid retry requires: an orthogonal discriminator such as event/news
context, forward evidence, or a state variable that separates decaying winners
from ordinary noisy trends. Any accepted future exit rule must be implemented
as a shared production/backtest policy before promotion.

### 2026-04-29 mechanism update: Trend Commodities near-high risk boost

Status: accepted.

Core conclusion: exp-20260429-013 tested whether the repeat winning sleeve in
`trend_long` Commodities should receive more risk only when the setup is already
within 3% of its 52-week high. This narrow allocation boost passed the fixed
snapshot windows without adding entries, filters, exits, or universe noise.

Evidence: `TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER=1.5` with
`pct_from_52w_high >= -0.03` moved EV by `late_strong +0.2315`,
`mid_weak +0.0266`, and `old_thin +0.0000`; aggregate PnL improved
`+$7,307.02`. Trade count, win rate, and survival rate were unchanged in all
three windows, so the result came from sizing the same accepted trades.

Do not repeat: broad Commodities risk boosts, deeper pullback thresholds, or
2.0x+ multipliers as simple variants. Wider tests improved aggregate PnL but
increased old_thin exposure to the weaker SLV shape, so the accepted mechanism
is specifically "near-high commodity trend continuation," not "all commodities
deserve more risk."

Next valid retry requires: forward evidence, an event/news discriminator, or a
separate risk-budget metric proving that a wider Commodities sleeve improves
without old_thin regression. Keep any future allocation rule in shared
`portfolio_engine` sizing, not in backtester-only code.

### 2026-04-29 mechanism update: Low-TQS Commodity breakout risk boost

Status: rejected.

Core conclusion: exp-20260429-014 tested whether the already-exempt
`breakout_long + Commodities + low-TQS` pocket should receive 1.5x risk. It
should not be promoted. The effect was directionally positive only in
`late_strong`, inert in `mid_weak` and `old_thin`, and too small to justify a
new sizing branch.

Evidence: the candidate moved EV by `late_strong +0.0398`, `mid_weak +0.0000`,
and `old_thin +0.0000`. Aggregate PnL improved only `+$931.56` / `+0.998%`,
below Gate 4 materiality, while max drawdown rose `+0.46 pp` in the only active
window.

Do not repeat: low-TQS Commodity breakout risk boosts, broad Commodity breakout
boosts, or low-TQS risk boosts without an independent state/event
discriminator.

Next valid retry requires: forward evidence, news/event confirmation, or a
state variable explaining when commodity breakouts deserve more risk. Keep the
current low-TQS Commodities exemption but do not add extra risk.

### 2026-04-29 mechanism update: Trend Financials risk boost

Status: accepted.

Core conclusion: exp-20260429-015 tested whether existing `trend_long +
Financials` candidates deserve a 1.5x risk budget. This passed because it
changed only sizing for already-selected trades, improved the two windows where
the sleeve was active, and left the dominant `late_strong` window unchanged.

Evidence: `TREND_FINANCIALS_RISK_MULTIPLIER=1.5` moved EV by `late_strong
+0.0000`, `mid_weak +0.1143`, and `old_thin +0.0135`; aggregate PnL improved
`+$5,735.09` / `+6.15%`. Trade count, win rate, and survival rate were
unchanged in all three fixed windows.

Do not repeat: Financials sector priority ordering, new Financials entry
sources, or broader Financials risk boosts as simple variants. This accepted
mechanism is specifically "already-selected Financials trend candidates deserve
more risk," not "Financials should get earlier slots."

Next valid retry requires: forward evidence, a stricter state/event
discriminator, or a risk-budget metric proving that a multiplier above 1.5x
does not add tail risk. Keep any future allocation rule in shared
`portfolio_engine` sizing.

### 2026-04-29 mechanism update: Financials near-high risk lift

Status: rejected.

Core conclusion: exp-20260429-016 tested whether the accepted `trend_long +
Financials` 1.5x sizing rule should be lifted to 2.0x when the setup is within
3% of its 52-week high. It should not be promoted. The extra near-high lift was
too small and only improved `old_thin`; it did not move `late_strong` or
`mid_weak`.

Evidence: versus the current accepted stack, the near-high 2.0x variant moved
EV by `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin +0.0147`.
Aggregate PnL improved only `+$892.55` / `+0.90%`, below Gate 4 materiality.
A stricter pretest that replaced broad Financials 1.5x with only near-high
2.0x regressed `mid_weak` from EV `0.9147` to `0.8004`.

Do not repeat: nearby Financials near-high multiplier thresholds, 2.0x
Financials trend sizing, or simple near-high narrowing of the accepted broad
Financials trend sleeve.

Next valid retry requires: forward evidence, an orthogonal event/state
discriminator, or a risk-budget metric proving material improvement without
damaging `mid_weak`.

### 2026-04-29 mechanism update: Commodity breakout risk boost

Status: rejected for production materiality.

Core conclusion: exp-20260429-017 tested whether already-selected
`breakout_long | Commodities` signals deserve a 1.5x risk budget after the
current three-window audit showed positive late/mid trades and no old-thin
exposure. The direction was positive, but not material enough to justify
another production sizing rule.

Evidence: versus the current accepted stack, the 1.5x boost improved
`late_strong` EV by `+0.0398` and `mid_weak` EV by `+0.0550`, with `old_thin`
unchanged. Aggregate EV delta was only `+0.0948`, just below the `+0.10` Gate
4 threshold, and aggregate PnL improved only `+$2,217.84` / `+2.239%`, below
the `+5%` PnL gate.

Do not repeat: broad Commodity breakout risk-budget boosts at nearby 1.5x
values, or another simple extension of Commodity trend convexity evidence into
Commodity breakouts.

Next valid retry requires: a new state/event discriminator that increases
materiality without reopening rejected Commodity breakout target-width changes
or low-TQS-only boosts.

### 2026-04-29 mechanism update: Shared entry-gate parity

Status: accepted governance.

Core conclusion: exp-20260429-007 moved already-held filtering, same-day sector
caps, and the `BEAR_SHALLOW` post-enrich entry gate into
`production_parity.filter_entry_signal_candidates`. This is not new alpha, but
it closes a real measurement drift vector. Future alpha conclusions should not
depend on duplicated run/backtester gate code.

Evidence: fixed-window metrics were unchanged after the refactor, while both
`quant/run.py` and `quant/backtester.py` now call the same helper and
production persists `entry_filter_audit` for inspection.

Do not repeat: run-only or backtester-only implementations of already-held,
same-day sector, or `BEAR_SHALLOW` entry gating logic.

Next valid retry requires: a new alpha hypothesis that actually changes gate
behavior, or a documented parity gap not already covered by the shared helper.

### 2026-04-29 mechanism update: Shared regime risk sizing parity

Status: accepted governance.

Core conclusion: exp-20260429-008 moved the `NEUTRAL` and `BEAR_SHALLOW`
`risk_pct` overrides into `production_parity.risk_pct_for_market_state`. This
is also not new alpha, but it removes another silent drift path between
production and replay.

Evidence: `BULL`/default, `NEUTRAL 0.75%`, `BEAR_SHALLOW 0.50%`, and
`BEAR_DEEP`/default sizing behavior is now covered by a shared helper and a
focused parity test, with no intended metric movement.

Do not repeat: duplicate adapter arithmetic for regime risk overrides, or
backtester-only sizing interpretations of market state.

Next valid retry requires: a real allocation hypothesis about when risk should
change, not another refactor of already-shared arithmetic.

### 2026-04-29 mechanism update: Trailing partial-reduce replay

Status: measurable but rejected alpha.

Core conclusion: exp-20260429-012 finished the missing parity work for
production trailing partial-reduce advice and added opt-in
`--replay-partial-reduces` support to BacktestEngine. That closes the audit
gap. Once replayed, the mechanism was negative on the fixed windows, so it
should stay off by default and should not be justified by intuition alone.

Evidence: replay-on executed 15 partial reductions and produced aggregate
`expected_value_score` delta `-0.3136` with aggregate PnL delta `-$9,441.76`
versus the current accepted baseline.

Do not repeat: promoting production partial-reduce advice without replay
evidence, or using full trailing-stop exit intuition as a reason to keep
partial reductions alive.

Next valid retry requires: an orthogonal event/state discriminator that can
separate decaying winners from normal trend noise, plus shared production and
backtest policy from the start.

### 2026-04-29 mechanism update: Risk-on unmodified sizing lift

Status: accepted.

Core conclusion: exp-20260429-018 tested whether already-selected `risk_on`
signals with no other active sizing modifier deserve a small risk-budget lift.
They do. The accepted rule is deliberately non-stacking: it does not apply to
existing 1.5x Commodities/Financials boosts or to 0.25x/0x haircut sleeves.

Evidence: `RISK_ON_UNMODIFIED_RISK_MULTIPLIER=1.25` moved EV by
`late_strong +0.1980`, `mid_weak +0.0525`, and `old_thin +0.0144`.
Aggregate PnL improved `+$8,404.99` / `+8.49%`. Trade count, win rate, and
survival rate were unchanged in all three fixed windows; max drawdown rose by
up to `+0.81 pp`, still below the Gate 4 drawdown materiality guardrail.

Do not repeat: simple risk-on leverage above 1.25x, stacking this lift onto
already-boosted sleeves, or using this result to relax low-TQS/sector haircut
rules. This is a plain-inventory risk-budget rule, not a new entry source.

Next valid retry requires: forward evidence, a tail-risk metric showing the
extra drawdown is still compensated, or an orthogonal discriminator that
separates the strongest unmodified risk-on candidates from the rest. Keep any
future change in shared `portfolio_engine` sizing.

### 2026-04-29 mechanism update: Breakout Energy risk boost

Status: rejected.

Core conclusion: exp-20260429-019 tested whether already-selected
`breakout_long + Energy` signals deserved 1.5x risk. The sleeve had visible
late-window continuation, but the effect was too concentrated and too small to
justify another production sizing branch.

Evidence: versus the current accepted stack, the candidate moved EV by
`late_strong +0.0827`, `mid_weak +0.0000`, and `old_thin +0.0000`. Aggregate
PnL improved only `+$2,216.67` / `+2.06%`, below Gate 4 materiality, and
Sharpe did not improve.

Do not repeat: simple `breakout_long + Energy` risk boosts at nearby
multipliers, or using the rejected Energy ETF expansion result as indirect
evidence for native Energy breakout sizing.

Next valid retry requires: a state/event discriminator that proves Energy
breakouts deserve scarce risk budget outside `late_strong`, without adding
universe noise or changing slot priority.

### 2026-04-29 mechanism update: Technology breakout risk boost

Status: rejected alpha.

Core conclusion: exp-20260429-020 tested whether already-selected
`breakout_long + Technology` signals deserved a dedicated 1.5x risk budget
instead of the generic risk-on 1.25x lift. The idea looked plausible from the
trade audit because late_strong and mid_weak Technology breakouts were positive,
but the fixed-window replay showed the extra risk was not worth carrying.
late_strong PnL rose by `$866.07`, but daily Sharpe fell from `4.22` to `4.11`
and EV fell from `2.2134` to `2.1915`. mid_weak added only `$191.59` and
`+0.0048` EV. old_thin lost `$326.18` and EV fell from `0.2113` to `0.2040`.
Aggregate EV declined by `-0.0244`; aggregate PnL improved only `+0.68%`.

Mechanism insight: Technology breakout winners are not a clean sizing sleeve
after the accepted stack. The pocket adds some upside in stronger windows, but
it is Sharpe-dilutive and still exposes the system to old_thin false breakouts.
This also reinforces the earlier Technology breakout target-width rejection:
simple Technology breakout promotion is not enough without a stronger
discriminator.

Do not repeat: nearby `breakout_long + Technology` risk multipliers, or simple
promotion of Technology breakouts based only on sector/strategy membership.
Also do not reuse plain `rs_vs_spy` as the discriminator; that family was
already rejected in the Technology breakout target experiment.

Next valid retry requires: an orthogonal event/state discriminator that
separates MU/AAPL-like winners from DDOG-like old_thin losses without changing
target width, candidate ranking, or global risk-on leverage.

### 2026-04-29 mechanism update: Risk-on score-threshold narrowing

Status: rejected.

Core conclusion: exp-20260429-021 tested whether the accepted non-stacking
`risk_on_unmodified` 1.25x sizing lift should require
`regime_exit_score >= 0.08`. It should not be promoted. The simple score
threshold removed useful low-score risk-on winner exposure and did not improve
trade count, win rate, survival, or drawdown.

Evidence: versus the current accepted stack, the threshold moved EV by
`late_strong -0.0333`, `mid_weak +0.0000`, and `old_thin -0.0197`.
Aggregate PnL fell `-$1,616.20` / `-1.50%`, with 0/3 windows improved and
2/3 windows regressed.

Do not repeat: nearby `regime_exit_score` thresholds as eligibility gates for
the broad `risk_on_unmodified` lift. This is distinct from raising the lift
above 1.25x, which was already discouraged; simple narrowing also damages
winner capture.

Next valid retry requires: a richer state, event, or tail-risk discriminator
that explains why a subset of plain risk-on inventory should lose the accepted
1.25x lift without cutting late_strong and old_thin winners.

### 2026-04-29 mechanism update: Technology trend unmodified risk lift

Status: rejected.

Core conclusion: exp-20260429-022 tested whether otherwise unmodified
`trend_long + Technology` signals deserved a dedicated 1.5x risk budget instead
of the accepted generic `risk_on_unmodified` 1.25x lift. The pocket was
directionally positive but too sparse and too small to justify a new production
sizing branch.

Evidence: versus the current accepted stack, the candidate moved EV by
`late_strong +0.0674`, `mid_weak +0.0000`, and `old_thin +0.0145`.
Aggregate PnL improved `+$1,952.83` / `+1.82%`, below Gate 4 materiality, and
no Sharpe improvement reached `+0.1`.

Do not repeat: nearby `trend_long + Technology` unmodified risk multipliers
without a broader sample or orthogonal discriminator. This is distinct from the
rejected Technology breakout branch, but it reaches the same practical lesson:
simple Technology sleeve promotion is not yet strong enough after the accepted
stack.

Next valid retry requires: evidence that the Technology trend pocket affects
more than isolated winners across the fixed windows, or a state/event
discriminator that increases sample quality without changing entry, ranking,
target width, or global risk-on leverage.

### 2026-04-29 mechanism update: Risk-on add-on fraction

Status: rejected as inert.

Core conclusion: exp-20260429-023 tested whether confirmed day-2 follow-through
positions that originally received the accepted `risk_on_unmodified` 1.25x
sizing lift should receive a larger first add-on fraction. The answer is no
under the current cap stack: raising the sleeve-specific fraction from 50% to
75% changed no executed shares and moved no metrics.

Evidence: fixed-window EV deltas were `late_strong +0.0000`, `mid_weak
+0.0000`, and `old_thin +0.0000`; PnL, drawdown, trade count, win rate,
survival rate, and add-on counts were unchanged in all three windows.

Do not repeat: risk-on add-on fraction increases while `ADDON_MAX_POSITION_PCT`
remains the binding constraint, or sizing-multiplier-specific production add-on
rules without persisted position metadata.

Next valid retry requires: concentration evidence for changing the add-on cap
itself, plus production position metadata that can execute sleeve-specific
add-on rules without drift.

### 2026-04-29 mechanism update: Financials multiplier above 1.5x

Status: rejected on risk-budget quality.

Core conclusion: exp-20260429-024 retested the accepted `trend_long +
Financials` sleeve by sweeping the risk multiplier above 1.5x. The only
material variant, 2.0x, cleared aggregate EV but bought that improvement with
too much mid-window drawdown expansion and a small Sharpe decline.

Evidence: `TREND_FINANCIALS_RISK_MULTIPLIER=2.0` moved EV by `late_strong
+0.0000`, `mid_weak +0.1041`, and `old_thin +0.0146`, but increased
`mid_weak` max drawdown by `+1.36 pp` and reduced `mid_weak` daily Sharpe by
`-0.01`. The 1.75x and 1.9x variants did not clear EV materiality.

Do not repeat: simple Financials trend multipliers above 1.5x, including
nearby 1.75-2.0 sweeps, without a new discriminator that controls the V-like
stop-out risk.

Next valid retry requires: forward evidence or an event/state discriminator
that separates COIN/GS/JPM winners from V stop-outs, plus a tail-risk metric
showing the higher budget does not expand drawdown.

### 2026-04-29 mechanism update: SIGNAL_TARGET partial-reduce replay

Status: rejected.

Core conclusion: exp-20260429-032 tested a replay-only parity hypothesis:
reinterpret the legacy ATR risk target as production-style `SIGNAL_TARGET`
partial trims (next-open sell 33%) instead of same-level full exits. It should
not be promoted. Across all three fixed windows the rule sharply reduced EV,
PnL, and trade completion because the remaining sleeves were left to stop /
end-of-backtest behavior without a compensating later lifecycle rule.

Evidence: the replay executed 15 `SIGNAL_TARGET` partial reductions and
produced aggregate `expected_value_score` delta `-3.0212` with aggregate PnL
delta `-$56,526.39`. Window EV deltas were `late_strong -2.0079`,
`mid_weak -0.8199`, and `old_thin -0.1934`; max drawdown worsened by up to
`+6.85 pp`.

Do not repeat: simple `SIGNAL_TARGET -> partial reduce -> let the rest ride`
replays, or nearby variants that only remove the old full-target exit without
adding a complete downstream lifecycle policy.

Next valid retry requires: a full shared lifecycle design that defines what
happens after the first trim, plus evidence that the broader lifecycle is
beneficial as a single causal variable rather than an isolated trim.

### 2026-04-29 mechanism update: Low-score plain risk-on sizing

Status: accepted as shared production/backtest sizing policy.

Core conclusion: exp-20260429-025 reversed the framing from the rejected
score-threshold experiment. Low `regime_exit_score` inside the already accepted
`risk_on` bucket was not a weakness signal; the affected plain, otherwise
unmodified sleeve contained profitable winners. The accepted rule keeps the
generic `risk_on_unmodified` 1.25x lift, but gives low-score plain risk-on
signals a non-stacking 1.5x budget when `regime_exit_score < 0.10`.

Evidence: fixed-window EV moved `late_strong +0.1183`, `mid_weak +0.0000`,
and `old_thin +0.0172`, for aggregate EV `+0.1355`. Aggregate PnL improved
`+$3,248.54`; trade count, win rate, and survival rate were unchanged in all
three windows. Max drawdown was unchanged in `late_strong` and `mid_weak`, and
rose only `+0.04 pp` in `old_thin`.

Do not repeat: nearby low-score multiplier tweaks, score eligibility gates, or
stacking this lift on top of sector-specific boosts / haircuts without new
forward or tail-risk evidence.

Next valid retry requires: a richer adverse-risk discriminator showing which
low-score risk-on trades are actually tail-risk warnings, or enough forward
sample to justify changing the 1.5x budget.

### 2026-04-29 mechanism update: Mid-score plain risk-on sizing

Status: accepted as shared production/backtest sizing policy, but risk-close.

Core conclusion: exp-20260429-031 extended the accepted plain `risk_on`
allocation family. Otherwise unmodified `risk_on` signals with
`0.10 <= regime_exit_score < 0.20` carried enough positive residual expectancy
to justify a non-stacking 1.6x risk budget instead of the generic 1.25x lift.
This is a capital-allocation rule, not a new entry source.

Evidence: versus the accepted stack after exp-20260429-025, the 1.6x mid-score
rule moved EV by `late_strong +0.1470`, `mid_weak +0.0362`, and `old_thin
-0.0018`. Aggregate PnL improved `+$6,531.45` / `+5.90%`; trade count, win
rate, and survival were unchanged. The risk warning is real: `old_thin` max
drawdown rose by `+0.96 pp`, just below the 1 pp guardrail.

Do not repeat: nearby mid-score risk-on multiplier tuning, broad risk-on
leverage increases, or stacking this lift on top of sector-specific boosts or
haircuts without new forward or tail-risk evidence.

Next valid retry requires: forward evidence, a tail-risk metric showing the
extra `old_thin` drawdown is compensated, or an orthogonal discriminator that
separates the strongest mid-score plain risk-on candidates from the rest.

### 2026-04-29 mechanism update: Post-low-score meta-allocation audit

Status: observed-only.

Core conclusion: exp-20260429-026 audited the accepted stack after the
low-score plain risk-on lift and did not find a production-worthy residual
allocation rule. The strongest cohorts are already accepted
(`trend_commodities_near_high`, `trend_financials`, and low-score plain
`risk_on_unmodified`). The remaining weak pockets are too small and too
localized to justify a new rule without overfitting.

Evidence: fixed-window baseline after exp-20260429-025 was `late_strong EV
2.3317`, `mid_weak EV 0.9672`, and `old_thin EV 0.2285`. The cohort audit found
`trend_commodities_near_high_risk_multiplier_applied` at 7/7 wins and
`+$32,004.78`, `trend_financials_risk_multiplier_applied` at 7 trades and
`+$18,374.95`, and low-score plain risk-on at 7 trades and `+$22,172.67`.
Negative pockets such as `breakout_financials_dte` had only 1-2 affected
trades and sub-$600 observed drag.

Do not repeat: adding zero-risk rules for `breakout_financials_dte`,
`breakout_healthcare_dte`, or Communication Services breakout gap/near-high
overlaps based only on this tiny-sample audit.

Next valid retry requires: forward evidence, event/news confirmation, or a
richer state discriminator that makes one of those pockets material across the
fixed windows. Otherwise the better alpha-search path is a broader
meta-allocation state map rather than another local sizing branch.

### 2026-04-29 mechanism update: Add-on cap to 40%

Status: rejected for production materiality.

Core conclusion: exp-20260429-027 tested whether the accepted strict day-2
follow-through add-on should lift `ADDON_MAX_POSITION_PCT` from 35% to the
existing 40% single-position cap. The direction was positive in all three
fixed windows, but not material enough to promote.

Evidence: versus the current accepted stack, the 40% cap moved EV by
`late_strong +0.0522`, `mid_weak +0.0172`, and `old_thin +0.0051`. Aggregate
PnL improved `+$1,766.97`, with one extra executed add-on in each window and
no drawdown change. This stayed below the +0.10 EV materiality bar and below
the 5% PnL gate.

Do not repeat: nearby global `ADDON_MAX_POSITION_PCT` values around 40%, or
using directionally positive but small add-on cap gains as production evidence.

Next valid retry requires: forward evidence, a concentration/event
discriminator, or tail-risk proof that a higher add-on cap materially improves
winner capture without adding weaker-tape damage.

### 2026-04-29 mechanism update: Second follow-through add-on

Status: rejected as inert.

Core conclusion: exp-20260429-028 tested enabling the existing second add-on
path with day-5, +5% unrealized, RS>0, 15% original shares, and 45% cap. It
should not be promoted. The rule added actions but did not release meaningful
alpha under the current cap/heat stack.

Evidence: EV moved only `late_strong +0.0005`, with `mid_weak` and `old_thin`
unchanged. Aggregate PnL improved only `+$11.37`.

Do not repeat: turning on `SECOND_ADDON_ENABLED` with the existing parameters,
or nearby second-add-on tweaks without a new event/state discriminator and a
complete lifecycle design.

### 2026-04-29 mechanism update: Risk-on unmodified breakout lift

Status: rejected for production materiality.

Core conclusion: exp-20260429-029 tested whether already-selected
`risk_on + breakout_long` signals with no other sizing modifier should receive
the same non-stacking 1.5x risk budget as the accepted low-score plain
`risk_on` sleeve. The direction was positive in the two newer windows but did
not clear materiality and slightly damaged the older tape.

Evidence: versus the accepted stack, the 1.5x breakout subset moved EV by
`late_strong +0.0364`, `mid_weak +0.0291`, and `old_thin -0.0070`.
Aggregate EV improved only `+0.0585`, and aggregate PnL improved only
`+$2,874.52` / `+2.60%`, below Gate 4. `late_strong` daily Sharpe also fell
from `4.28` to `4.17`.

Do not repeat: simple `risk_on_unmodified + breakout_long` 1.5x promotion,
nearby breakout-only unmodified risk multipliers, or using late/mid breakout
attribution alone to justify another production sizing branch.

Next valid retry requires: a richer event/state discriminator that removes
old_thin breakout damage, forward evidence under current cap/heat constraints,
or a tail-risk metric proving the Sharpe dilution is compensated.

### 2026-04-29 mechanism update: Sector-state allocation map

Status: observed only; no production rule promoted.

Core conclusion: exp-20260429-030 audited entry-day sector breadth,
sector 20-day return, sector dispersion, and ticker-vs-sector relative
strength across the fixed three windows. This was an alpha search, not a bug
repair: LLM soft-ranking data was still too thin for a production-aligned
ranking experiment, so the run tested deterministic OHLCV state features
instead.

Evidence: fixed-window metrics stayed unchanged at the accepted baseline:
`late_strong EV 2.3317`, `mid_weak EV 0.9672`, and `old_thin EV 0.2285`.
Across 62 executed trades, `sector_breadth_200 >= 75%` covered 54 trades,
57.4% win rate, and `+$103,141.12`; the lower-breadth buckets were only
7 known trades total and also net positive, so breadth alone is not a useful
filter. Strong sector 20-day return was also broad rather than selective:
`ret20 >= 5%` covered 44 trades, 59.1% win rate, and `+$85,790.18`.

Mechanism insight: the strongest stable state bucket was
`Commodities + breadth_gte_75 + ret20_gte_5` at 9/9 wins and `+$35,243.09`,
but this mostly confirms the already accepted commodity trend allocation
family. The more actionable warning is the opposite: `trend_long +
Technology + breadth_gte_75` had 15 trades, only 33.3% win rate, and much
lower average PnL than Commodities/Financials even in strong sector states.

Do not repeat: simple sector breadth gates, simple sector 20-day return gates,
or using "high breadth" as justification to add broad exposure. These states
mostly describe where the current system already trades.

Next valid retry requires: a production-shared Technology trend discriminator
or lifecycle rule that explains why high-breadth Technology trend entries have
low win rate without killing the existing positive PnL tail. A valid promoted
rule must run through `portfolio_engine`/shared policy or be explicitly listed
as replay-only parity.
### 2026-04-30 mechanism update: Technology trend marginal risk-on de-risking

Status: rejected.

Core conclusion: exp-20260430-002 tested whether `trend_long + Technology`
signals with `0.10 <= regime_exit_score < 0.13` should be cut to 25% risk.
The rule was production-shared during the test, then rolled back. It is not a
valid alpha improvement.

Evidence: versus the accepted stack, the candidate left `late_strong`
unchanged, improved `old_thin` only slightly (`EV +0.0058`, PnL `+$311.48`),
but damaged `mid_weak` (`EV -0.0117`, PnL `-$452.84`). Aggregate EV moved
`-0.0059` and aggregate PnL moved `-$141.36`.

Mechanism insight: simple `regime_exit_score` bands do not separate Technology
trend noise from delayed winners. The tested band included weak TSM/AMD/SNOW
shapes but also useful APP/AAPL-like convex winners, so score-only de-risking
misallocates capital.

Do not repeat: nearby Technology trend marginal-score haircuts or using
`regime_exit_score` alone as the missing Technology trend discriminator.

Next valid retry requires: an orthogonal event/state or lifecycle signal that
can distinguish delayed Technology winners from normal weak trend noise, with
shared production/backtest policy from the start.

### 2026-04-30 mechanism update: Scarce-slot deferral state caps

Status: rejected.

Core conclusion: exp-20260430-003 tested whether the accepted one-slot
`breakout_long` deferral should be restricted by a simple market-extension cap
after the newer sizing stack. It should not. The current unconditional one-slot
form remains the better shared policy.

Evidence: disabling the hook, or requiring `min(SPY, QQQ)` pct-from-200MA to be
`<= 0.0` or `<= 0.05`, left `late_strong` unchanged but damaged the two windows
where the hook matters. `mid_weak` EV fell `1.0034 -> 0.8404` and PnL fell
`$39,346.43 -> $37,523.67`; `old_thin` EV fell `0.2267 -> 0.2028` and PnL fell
`$18,584.08 -> $17,334.50`.

Mechanism insight: the one-slot deferral edge is not explained by a simple
index-extension state. A cap on `min(SPY, QQQ)` distance makes the rule inert in
the windows where preserving slots for later trend candidates has value.

Do not repeat: disabling one-slot breakout deferral, or adding simple
`min(SPY, QQQ)` pct-from-200MA caps to it, without new evidence.

Next valid retry requires: a different production-shared discriminator, such
as candidate forward-quality context or persisted sector-state fields, that
preserves `mid_weak` and `old_thin` benefits without damaging `late_strong`.

### 2026-04-30 mechanism update: Low-score Technology trend haircut release

Status: rejected.

Core conclusion: exp-20260430-004 tested the opposite of the prior Technology
trend score-band haircut: maybe low `regime_exit_score` Technology trend
signals were being over-de-risked by the accepted Technology gap / near-high /
DTE haircuts. The temporary shared `portfolio_engine` patch released those
Technology-specific haircuts when `regime_exit_score < 0.10`, then was rolled
back. This should not be promoted.

Evidence: versus the accepted stack, `late_strong` was unchanged, `mid_weak`
regressed materially (`EV 1.0034 -> 0.8360`, PnL `-$1,346.54`, Sharpe `2.55 ->
2.20`, max drawdown `+0.85 pp`), and `old_thin` PnL rose by `$626.93` while EV
fell (`0.2267 -> 0.2209`) and win rate fell (`40.9% -> 39.1%`). Aggregate EV
moved `-0.1732`; aggregate PnL moved `-$719.61`.

Mechanism insight: low score alone does not prove Technology trend haircuts are
too punitive. The release amplified PLTR/META/MSFT-like stop-outs more than it
recovered AMD/NOW-like delayed winners. This complements exp-20260430-002: both
score-only Technology trend de-risking and score-only haircut release are
invalid discriminators.

Do not repeat: full-risk or risk-on-unmodified releases of low-score Technology
trend haircuts, or any Technology trend haircut release that uses
`regime_exit_score < 0.10` alone as the qualifier.

Next valid retry requires: an orthogonal production-shared event, news, or
lifecycle discriminator that separates delayed Technology winners from ordinary
weak trend noise, plus tail-risk evidence that the release does not expand
`mid_weak` drawdown.

### 2026-04-30 mechanism update: Defensive ETF universe expansion

Status: rejected.

Core conclusion: exp-20260430-005 tested whether defensive rate/dollar ETFs
already present in the fixed OHLCV snapshots (`IEF`, `TLT`, `UUP`) should be
added to the tradeable production watchlist. They should not be promoted as a
simple universe expansion.

Evidence: versus the accepted stack, `late_strong` and `old_thin` were
unchanged on EV, while `mid_weak` improved EV by only `+0.0005` and reduced
PnL by `$440.21`. The only observed defensive trade was a `TLT` target in
`mid_weak`, but it displaced better opportunity under the current slot/heat
stack. Aggregate PnL regressed and no Gate 4 threshold was met.

Mechanism insight: low-volatility defensive targets can still be
opportunity-cost negative when they compete for scarce A/B slots. Adding
defensive ETFs increases candidate supply, not necessarily alpha.

Do not repeat: adding `IEF`/`TLT`/`UUP` as a simple defensive ETF universe
expansion, or treating defensive ETF targets as alpha without opportunity-cost
evidence.

Next valid retry requires: a state discriminator showing when defensive ETF
continuation should compete for scarce slots, or a ranking signal that prevents
low-volatility ETFs from displacing higher-EV A/B candidates.

### 2026-04-30 mechanism update: Zero-share slot prefilter

Status: rejected.

Core conclusion: exp-20260430-006 tested whether candidates already sized to
zero shares should be removed before shared scarce-slot routing and slot
slicing. This looked like a clean slot-allocation alpha, but it should not be
promoted.

Evidence: versus the accepted stack, `late_strong` was unchanged, `mid_weak`
regressed from EV `1.0034` to `0.9429`, and `old_thin` regressed from EV
`0.2267` to `0.1120`. Aggregate PnL fell by `$7,876.12`; no window improved
on EV.

Mechanism insight: zero-share candidates are not merely harmless slot
pollution. In the current ordering stack, preserving them through planning
sometimes blocks worse later candidates; removing them releases lower-quality
trades in weaker tapes.

Do not repeat: dropping zero-share sized candidates before shared entry
planning, or using `no_shares` counts alone as evidence for slot-routing alpha.

Next valid retry requires: candidate forward-quality evidence showing that the
released candidates are better than the blocked candidates, ideally with a
state-specific slot discriminator rather than a blanket pre-filter.

### 2026-04-30 mechanism update: Same-day sector cap sweep

Status: rejected.

Core conclusion: exp-20260430-007 tested whether the shared same-day sector
cap was suppressing existing A/B alpha. It was not. Tightening
`MAX_PER_SECTOR` from `2 -> 1` damaged all three fixed windows, while loosening
it to `3` changed candidate survival but did not improve any executed-trade
metric.

Evidence: `MAX_PER_SECTOR=1` moved aggregate EV by `-0.6565` and aggregate PnL
by `-$19,578.53`, with all three windows regressing. `MAX_PER_SECTOR=3` left
EV, PnL, drawdown, trade count, and win rate unchanged across the fixed
windows; only candidate survival changed.

Mechanism insight: the current same-day sector cap is not the binding alpha
bottleneck. Sector clustering that survives the accepted stack is valuable
enough that tightening removes winners, while loosening does not release
incremental executable alpha under the current slot/heat stack.

Do not repeat: global `MAX_PER_SECTOR=1`, global `MAX_PER_SECTOR=3`, or using
candidate survival-rate improvement alone as evidence for sector-cap alpha.

Next valid retry requires: a state-specific sector crowding discriminator, or a
production-shared ranking signal that chooses among same-sector candidates
rather than changing the global cap.

### 2026-04-30 mechanism update: Sector ETF universe expansion

Status: rejected.

Core conclusion: exp-20260430-008 tested whether sector / commodity ETFs already
available in the fixed OHLCV snapshots (`USO`, `XLE`, `XLP`, `XLU`, `XLV`)
should be added to the tradeable universe as cleaner candidate supply. They
should not be promoted as a simple universe expansion.

Evidence: the full bundle improved `late_strong` EV (`2.4787 -> 3.0879`) but
regressed `mid_weak` (`1.0034 -> 0.5735`) and `old_thin` (`0.2267 -> 0.1996`);
aggregate PnL fell by `$1,059.91`. Narrow variants also failed: `XLE_only`
regressed late/mid, `USO_only` regressed mid/old on EV, and excluding `USO`
still regressed all three EV windows except no old improvement.

Mechanism insight: sector ETFs are not automatically lower-noise replacements
for single-name candidates. `USO` added strong late-tape commodity exposure but
was repeatedly opportunity-cost negative in `mid_weak`, while broad sector ETFs
added slot competition without stable cross-window alpha.

Do not repeat: adding `USO` / `XLE` / `XLP` / `XLU` / `XLV` as a simple
tradeable universe expansion, or treating sector ETFs as safer candidate supply
without a state-specific routing signal.

Next valid retry requires: a state discriminator showing when ETF continuation
should compete for scarce slots, or a ranking signal that explicitly compares
ETF candidates against same-sector single-name candidates.

### 2026-04-30 mechanism update: LLM replay coverage audit

Status: observed-only measurement audit.

Core conclusion: exp-20260430-009 did not change behavior; it refreshed the
current accepted-stack LLM replay coverage picture so soft-ranking work does
not drift back into guesswork.

Evidence: for `2025-10-23 -> 2026-04-21`, the archive now has 10
`llm_prompt_resp` days, 8 `decision_log` days, 16 `quant_signals` days, 7
full-triplet days, and only 3 production-aligned ranking-eligible days
covering 8 presented signals.

Mechanism insight: replay readiness is improving, but the effective LLM sample
is still too thin for a promotion-grade ranking experiment. The bottleneck is
not model intuition; it is ranking-eligible archive density.

Do not repeat: treating raw prompt file count or archive presence alone as
evidence that LLM ranking is ready for alpha promotion.

Next valid retry requires: more production-aligned full-triplet days, or a
coverage push that directly increases ranking-eligible candidate overlap.

### 2026-04-30 mechanism update: Hold-quality oracle loss taxonomy refresh

Status: observed-only.

Core conclusion: exp-20260430-010 refreshed the current accepted-stack
loss-family map before any new lifecycle experiment. The biggest recurring
fixable drag still clusters in failed follow-through and low-MFE stop-out
families, not in broad overnight-gap or wide-stop buckets.

Evidence: the artifact showed `failed_followthrough` as the largest repeated
loss family at 14 losses and `$9,084.88` absolute loss with only `0.32`
winner-collateral, while `low_mfe_stopout` had 9 losses and `$5,712.45` loss
with zero winner-collateral. Overnight-gap and wide-stop families carried much
higher winner collateral and remain poor candidates for direct filters.

Mechanism insight: if lifecycle alpha search resumes, it should start from
follow-through quality or early hold-quality context, not blanket gap/wide-stop
defensiveness.

Do not repeat: broad overnight-gap or wide-stop filters justified only by raw
loss dollars, without collateral accounting.

Next valid retry requires: a production-shared discriminator that targets the
failed-followthrough / low-MFE families while keeping winner collateral low.

### 2026-04-30 mechanism update: Exit advisory replay disclosure

Status: accepted measurement repair.

Core conclusion: production held-position exit advice and backtest price exits
are not the same object. Production computes advisory rules such as
`SIGNAL_TARGET`, profit ladders, and `TIME_STOP`,
then lets the LLM / daily workflow decide whether to issue or preserve
`REDUCE` / `EXIT` actions. The canonical backtest executes full-position
`stop_price` and `target_price` fills, plus only explicitly implemented shared
replay hooks.

Evidence: this repair adds an explicit
`known_biases.exit_policy_unreplayed` result block,
`exit_advisory_shadow_attribution`, and parity docs. It does not change trade
behavior or historical metrics. The anti-repeat evidence remains
`exp-20260429-032`: bare `SIGNAL_TARGET -> 33% trim` replay regressed EV and
PnL in all three fixed windows.

Mechanism insight: exit parity should be closed by shadow attribution and a
complete lifecycle design, not by changing the meaning of `target_price` inside
`backtester.py` alone.

Do not repeat: simple `SIGNAL_TARGET` partial-reduce replays, or any
backtester-only exit lifecycle that production cannot surface through the daily
report / LLM / pending-action path.

Next valid retry requires: enough shadow-attribution sample to identify which
rule families deserve executable replay, followed by a shared policy that both
`run.py` and `backtester.py` can expose.

### 2026-04-30 mechanism update: Approaching hard-stop partial reduce replay

Status: rejected.

Core conclusion: exp-20260430-012 tested the first actionable exit rule exposed
by shadow attribution: first `APPROACHING_HARD_STOP` trigger schedules a
next-open partial reduce using the shared production reduce-percentage helper.
This should not be promoted.

Evidence: the rule lowered max drawdown in all three fixed windows, but EV and
PnL regressed everywhere. EV moved `late_strong 2.4787 -> 1.6378`,
`mid_weak 1.0034 -> 0.6673`, and `old_thin 0.2267 -> 0.1534`; aggregate PnL
fell by `$35,055.21`. The replay executed 9/10/15 approaching-stop partial
reduces across the three windows.

Mechanism insight: `APPROACHING_HARD_STOP` is a noisy warning, not an
executable edge by itself. Many warnings occur during normal early drawdown in
positions that later reach target, so blanket de-risking buys drawdown
improvement by selling profitable convexity.

Do not repeat: first-trigger `APPROACHING_HARD_STOP` partial reduce, full exit,
or similar blanket de-risking variants without a discriminator that separates
true breakdowns from temporary drawdown.

Next valid retry requires: event/news/LLM context or a price-action state that
identifies which approaching-stop warnings deserve action, and must improve EV
rather than only drawdown.

Follow-up: after rejection, `APPROACHING_HARD_STOP` was removed from advisory
rule generation and shared reduce-percentage mapping. It should not appear in
production prompts or future shadow attribution as a standalone rule.

### 2026-04-30 mechanism update: Remove approaching-stop advisory generation

Status: accepted measurement simplification.

Core conclusion: exp-20260430-013 removed `APPROACHING_HARD_STOP` from the
generated advisory exit rule set. Its executable replay was rejected in
exp-20260430-012, and keeping it as a standalone warning adds LLM prompt noise
without demonstrated alpha value.

Evidence: deterministic stop/target backtest metrics are unchanged by
construction and by the late-strong no-drift check: EV remains `2.4787`, PnL
remains `$59,304.19`, and trade count remains `19`. The shared reduce helper
now maps `APPROACHING_HARD_STOP` to `0%` if encountered defensively.

Mechanism insight: a warning that is not actionable should not be generated as
a first-class rule. If a future version wants near-stop context, it needs a
specific event/price-action discriminator rather than a standalone proximity
rule.

Do not repeat: reintroducing `APPROACHING_HARD_STOP` as an independent advisory
or reduce/exit trigger without new LLM archive evidence or a discriminator.

### 2026-04-30 mechanism update: Remove pure trailing-stop advisory generation

Status: accepted measurement simplification.

Core conclusion: exp-20260430-014 disabled pure `TRAILING_STOP` advisory rule
generation from `position_manager.evaluate_exit_signals`. This does not remove
trailing stop risk references: `TRAILING_STOP_PCT`, portfolio heat effective
stops, and `production_trailing_stop_price` remain available for risk context.

Evidence: pure trailing partial-reduce replay was already rejected
(`exp-20260429-011` / `exp-20260429-017`), and shared policy maps pure
`TRAILING_STOP` to `0%` reduce by default. The no-drift fixed-window check
stayed unchanged: EV `2.4787`, PnL `$59,304.19`, 19 trades, and max drawdown
`4.39%`.

Mechanism insight: a rule that is disabled as an action should not keep
appearing as a first-class LLM advisory trigger. Keep the risk level as context,
but do not ask the LLM to infer an action from a rejected standalone signal.

Do not repeat: reintroducing pure `TRAILING_STOP` as an advisory reduce/exit
trigger without new LLM archive evidence or a more specific discriminator.

### 2026-04-30 mechanism update: High-score plain risk-on sizing

Status: rejected as inert.

Core conclusion: exp-20260430-013 tested whether the residual high-score plain
risk-on sleeve (`regime_exit_score >= 0.20`, after accepted low/mid-score
lifts) should move away from the generic 1.25x budget. Variants
1.00x/1.40x/1.50x/1.60x changed no fixed-window trades or metrics.

Evidence: all three fixed windows were identical to baseline: late_strong EV
2.4787 / PnL $59,304.19, mid_weak EV 1.0034 / PnL $39,346.43, old_thin EV
0.2267 / PnL $18,584.08. Aggregate EV delta 0.0 and PnL delta $0.00.

Mechanism insight: the residual high-score plain risk-on scalar is not a
binding alpha lever under current 40% initial cap, heat, and slot constraints.
Candidate-level sizing attribution can show the rule present, but the tested
scalar does not change realized allocations.

Do not repeat: nearby high-score plain risk-on multiplier tweaks or treating
the residual plain sleeve as the next allocation lever without forward/tail-risk
evidence.

Next valid retry requires: an orthogonal event/state discriminator that changes
which candidates get scarce capital, not another scalar budget tweak.

### 2026-04-30 mechanism update: Add-on no-undercut gate

Status: rejected.

Core conclusion: exp-20260430-014 tested whether day-2 follow-through add-ons
should require the position to avoid any intraday undercut of the original
entry price between entry and checkpoint. It should not be promoted. The rule
was temporarily implemented in the shared production/backtest add-on paths,
then rolled back after fixed-window failure.

Evidence: versus the accepted stack, the candidate eliminated all add-on
executions in all three fixed windows. EV moved `late_strong 2.4787 -> 2.4682`,
`mid_weak 1.0034 -> 0.9780`, and `old_thin 0.2267 -> 0.2267`; aggregate PnL
fell by `$2,125.72`.

Mechanism insight: simple intraday entry undercut is too blunt as a
follow-through quality discriminator. It mostly disables the accepted add-on
alpha rather than separating fragile recoveries from normal noisy winners.

Do not repeat: no-entry-undercut add-on gates or nearby intraday-undercut
variants without new evidence that they preserve executed add-ons.

Next valid retry requires: an orthogonal adverse-information source, such as
news/event context or a richer hold-quality state, that targets
failed-followthrough / low-MFE losses without turning off the accepted add-on
mechanism.

### 2026-04-30 mechanism update: Same-sector candidate chooser

Status: rejected.

Core conclusion: exp-20260430-015 tested whether `MAX_PER_SECTOR=2` should
choose retained same-sector candidates by `trade_quality_score` or confidence
instead of native candidate order. It should not be promoted.

Evidence: confidence ordering was inert across all three fixed windows. TQS
ordering left `late_strong` and `old_thin` unchanged, but regressed `mid_weak`
EV `1.0034 -> 0.9429`, PnL `$39,346.43 -> $38,016.04`, and win rate
`52.4% -> 50.0%`. No Gate 4 condition passed.

Mechanism insight: the same-day sector cap is not currently a useful alpha
bottleneck by itself. Simple same-sector score ordering either does nothing or
releases worse slot competition; sector-cap movement is not alpha without
executed-trade improvement.

Do not repeat: simple same-sector TQS or confidence ordering before
`MAX_PER_SECTOR`, or treating sector cap mechanics as the next alpha without a
state/event discriminator.

Next valid retry requires: state-specific sector crowding evidence or
event/news quality context showing that the replacement candidate beats the
dropped candidate after slot and heat constraints.
### 2026-04-30 mechanism update: Breakout deferral quality exception

Status: rejected.

Core conclusion: exp-20260430-016 tested whether the accepted one-slot
`breakout_long` deferral should allow narrow high-quality exceptions for
breakouts with strong `trade_quality_score` and proximity to the 52-week high.
It should not be promoted.

Evidence: both tested variants (`TQS >= 0.90 and pct_from_52w_high >= -3%`,
`TQS >= 0.85 and pct_from_52w_high >= -5%`) produced zero metric movement in
all three fixed windows. Baseline and candidate stayed at `late_strong EV
2.4787`, `mid_weak EV 1.0034`, and `old_thin EV 0.2267`; aggregate PnL delta
was `$0.00`.

Mechanism insight: the breakouts currently blocked by scarce-slot deferral are
not the clean high-quality near-high candidates this rule was meant to rescue.
The bottleneck is not a simple quality exception inside deferral.

Do not repeat: high-TQS near-high breakout exceptions to one-slot deferral, or
treating fewer deferred candidates as alpha without executed-trade movement.

Next valid retry requires: event/news quality context or a candidate
replacement audit proving the allowed breakout beats the displaced trade after
slot, heat, gap-cancel, and add-on effects.

### 2026-04-30 mechanism update: Day-1 weak follow-through partial reduce

Status: rejected.

Core conclusion: exp-20260430-017 tested whether positions that were below
cost and underperforming SPY on day 1 should receive a 50% next-open partial
reduce. The rule was tested through a temporary shared production/backtest
helper, then rolled back after fixed-window failure.

Evidence: versus the accepted stack, the rule executed 17 partial reduces and
regressed EV in all three fixed windows: `late_strong 2.4787 -> 2.4713`,
`mid_weak 1.0034 -> 0.7490`, and `old_thin 0.2267 -> 0.2160`. Aggregate PnL
fell by `$12,673.23`.

Mechanism insight: day-1 below-cost plus negative RS is still too blunt. It
does identify some early weakness, but it sells enough delayed winners and
changes subsequent slot/capital paths enough to overwhelm the saved loss.

Do not repeat: day-1 price-only weak-followthrough partial reduces, or nearby
below-cost / negative-RS de-risking variants without orthogonal adverse
information.

Next valid retry requires: event/news/LLM context or a richer hold-quality
state that separates true failed follow-through from delayed winners before
turning weak early price action into an executable action.

### 2026-04-30 mechanism update: Technology trend near-high multiplier drift

Status: rejected.

Core conclusion: exp-20260430-018 tested whether the accepted
`trend_long` Technology near-high haircut was too punitive. It should not be
promoted or locally retuned. The current 0.25x form remains the better default
until a new discriminator appears.

Evidence: lowering the multiplier to `0.0` badly damaged `mid_weak`
(`EV 1.0034 -> 0.7391`) and `old_thin` (`0.2267 -> 0.1392`). A softer `0.10`
variant also regressed both weak windows. Raising it to `0.50` improved
`mid_weak` and `old_thin` only slightly, but regressed `late_strong`
(`2.4787 -> 2.4711`) and produced only `+0.0038` aggregate EV / `+$948.45`
aggregate PnL, below Gate 4 materiality.

Mechanism insight: the near-high Technology trend pocket is not solved by
nearby multiplier drift. Full bans over-prune delayed winners, while partial
release adds too little edge and slightly damages the dominant strong tape.

Do not repeat: nearby `TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER` values around
`0.10`, `0.25`, or `0.50`, or a full zero-risk near-high Technology trend ban,
without new evidence.

Next valid retry requires: an orthogonal event, news, or lifecycle
discriminator that separates delayed Technology winners from weak near-high
trend noise, and a material aggregate EV improvement rather than tiny
weak-window PnL recovery.

### 2026-04-30 mechanism update: Current-stack second add-on retry

Status: rejected.

Core conclusion: exp-20260430-019 retested the prior best day-5 second
follow-through add-on after the accepted low/mid-score plain risk-on sizing
promotions changed the current capital path. It should not be promoted.

Evidence: the best current-stack retry executed only one second add-on. EV
moved `late_strong 2.4787 -> 2.4779`, while `mid_weak` and `old_thin` were
unchanged at `1.0034` and `0.2267`. Aggregate PnL moved `-$12.73`, so the
qualified retry failed Gate 4.

Mechanism insight: the current accepted stack already captures almost all
available follow-through add-on materiality. A second add-on using only day-5
`>= +5%` unrealized and RS `> 0` no longer releases meaningful alpha.

Do not repeat: day-5 second follow-through add-on variants based only on
unrealized return and RS, or nearby second-add-on fraction/cap tuning on the
current accepted stack.

Next valid retry requires: an orthogonal event, news, or richer lifecycle
quality discriminator that materially increases eligible executions without
expanding concentration risk.

### 2026-04-30 mechanism update: Risk-on Commodities final budget

Status: rejected.

Core conclusion: exp-20260430-020 tested whether the current accepted stack
should raise the final risk budget for `sector == Commodities` only when
`regime_exit_bucket == risk_on`, explicitly excluding the known weak defensive
SLV shape. It should not be promoted.

Evidence: 1.8x and 2.0x variants improved only `late_strong`. The 2.0x variant
lifted `late_strong` EV `2.4787 -> 2.6604` and PnL by `$2,853.32`, but
`mid_weak` and `old_thin` were unchanged. Aggregate EV improved, but the
fixed-window protocol requires majority-window improvement for strategy logic.

Mechanism insight: the commodity sleeve is not necessarily under-allocated
across the whole stack; in `mid_weak` and `old_thin`, the 40% single-position
cap already prevents the tested multiplier from changing realized exposure.
The apparent improvement is a late-strong-only amplification, not a robust
capital-allocation unlock.

Do not repeat: nearby `risk_on` Commodities final multipliers such as 1.8x or
2.0x, or using aggregate EV alone to accept a late-strong-only commodity boost.

Next valid retry requires: cap/headroom evidence that the rule changes realized
shares in at least two fixed windows, or forward evidence that commodity
risk-on exposure remains under-allocated outside the late strong tape.

### 2026-04-30 mechanism update: Trend Technology mid-score state route

Status: rejected.

Core conclusion: exp-20260430-021 tested whether `trend_long` Technology
candidates in the `risk_on` `regime_exit_score` band `[0.10, 0.20)` should
receive an extra risk haircut. This looked like a cleaner state-routing
variant than the rejected near-high / gap / DTE Technology retunes, but it
should not be promoted.

Evidence: the best 0.50x variant only marginally improved `mid_weak` EV
(`1.0034 -> 1.0051`) while damaging `late_strong` (`2.4787 -> 2.2510`) and
`old_thin` (`0.2267 -> 0.1853`). Aggregate PnL fell by `$6,284.02`; stricter
0.25x and 0x variants were worse.

Mechanism insight: regime-exit score alone is not enough to separate fragile
Technology trend entries from delayed winners. The same score band contains
important strong-tape Technology winners, so score-only state routing behaves
like another blunt Technology haircut.

Do not repeat: trend Technology `risk_on` `[0.10, 0.20)` score haircuts, or
nearby score-only Technology state-routing variants without orthogonal
event/news/lifecycle evidence.

Next valid retry requires: a discriminator that preserves late strong
Technology winners while identifying mid-window failed follow-through, ideally
with event/news context or richer hold-quality state rather than score alone.

### 2026-04-30 mechanism update: Breadth-conditioned risk-on boost

Status: rejected.

Core conclusion: exp-20260430-022 tested whether accepted low/mid-score
`risk_on_unmodified` sizing boosts should require healthy 50-day universe
breadth. This should not be promoted.

Evidence: the best variant, `breadth50_min_0_50`, damaged `late_strong` EV
`2.4787 -> 2.3374` and PnL by `$2,151.82`, while `mid_weak` and `old_thin`
were inert. Stricter 0.60 and 0.70 breadth thresholds also hurt weak windows:
0.60 moved `old_thin` EV `0.2267 -> 0.2165`, and 0.70 moved `mid_weak`
`1.0034 -> 0.9715` plus `old_thin` `0.2267 -> 0.2179`.

Mechanism insight: broad 50dma universe breadth is not a useful gate for the
already accepted risk-on plain boost. It removes or reduces exposure to winners
in the dominant strong tape and does not unlock a compensating weak-window
edge. The issue is not "risk-on boost only works when breadth is high"; the
remaining alpha problem still needs a candidate-level, event/news, or richer
lifecycle discriminator.

Do not repeat: requiring broad 50dma breadth before applying accepted
low/mid-score `risk_on_unmodified` boosts, or nearby blunt breadth thresholds
used as overlays on existing risk-on sizing.

Next valid retry requires: evidence that a breadth-derived variable changes
realized exposure in at least two fixed windows without damaging `late_strong`,
or a narrower discriminator that targets a repeated weak-tape failure mode
while preserving accepted strong-tape winners.

### 2026-04-30 mechanism update: Technology sector-leader de-risking

Status: rejected.

Core conclusion: exp-20260430-023 tested whether `trend_long` Technology
signals should receive less risk when Technology sector breadth was high
(`sector_breadth_200 >= 75%`) and the ticker had already outperformed its
sector by at least 3 percentage points over 20 trading days. This should not
be promoted.

Evidence: every tested multiplier regressed all three fixed windows. The best
variant, `0.50x`, moved EV `late_strong 2.4787 -> 2.2502`,
`mid_weak 1.0034 -> 0.9978`, and `old_thin 0.2267 -> 0.1521`; aggregate PnL
fell by `$8,055.31` (`-6.87%`).

Mechanism insight: Technology trend winners are still too dependent on
individual convexity for a sector-relative leadership haircut to work. Even a
candidate-level sector-state discriminator clipped more winner exposure than
it saved; high sector breadth plus ticker leadership is not adverse
information by itself.

Do not repeat: nearby Technology sector-relative 20-day return haircuts,
sector-leader de-risking, or high-breadth Technology trend de-risking without
orthogonal event/news/lifecycle evidence.

Next valid retry requires: a discriminator that separates delayed Technology
winners from fragile leaders using new information, not another relative-return
cutoff around the same sector-state audit.

### 2026-04-30 mechanism update: Earnings and pending-action bias disclosure

Status: accepted measurement repair.

Core conclusion: the backtester disclosure layer was stale in two places. It
still described `earnings_event_long` as `days_to_earnings`-only even though
P-ERN snapshots now provide `eps_estimate` and surprise-history fields when
coverage exists, and it did not expose the current production
`pending_actions.json` ledger as a separate non-replayed gap.

Evidence: this repair does not change trading behavior. It refreshes
`known_biases.earnings_event_long_data_quality` from the actual loaded snapshot
archive, adds `known_biases.pending_action_replay_unreplayed`, and corrects the
LLM attribution note so it no longer implies LLM `position_actions` are
historically replayed.

Mechanism insight: disclosure must distinguish "field absent" from "field
snapshot-backed but coverage-limited." Treating those as the same blind spot
would send future agents back into already-resolved P-ERN work instead of the
real remaining blockers: LLM/news archive density and point-in-time action
ledger snapshots.

Do not repeat: saying Strategy C has no EPS/surprise history without checking
the snapshot coverage fields in `known_biases.earnings_event_long_data_quality`.

### 2026-04-30 mechanism update: Breakout gap-quality subsequence ranking

Status: rejected.

Core conclusion: exp-20260430-025 tested whether the existing `breakout_long`
subsequence should be ranked by setup quality or lower `gap_vulnerability_pct`
instead of the current `pct_from_52w_high` then confidence order. This should
not be promoted.

Evidence: all three tested ranking variants were inert in all three fixed
windows. EV stayed `late_strong 2.4787`, `mid_weak 1.0034`, and `old_thin
0.2267`; aggregate PnL delta was `$0.00`, and trade count / win rate /
drawdown were unchanged.

Mechanism insight: current executed trades are not bottlenecked by these
breakout subsequence sorting keys. The accepted stack's slot, heat, same-sector
cap, and one-slot breakout deferral path mean simple deterministic reordering
inside the breakout subsequence does not change realized allocation.

Do not repeat: nearby breakout subsequence sort keys based only on
`trade_quality_score`, `confidence_score`, `gap_vulnerability_pct`, or
`pct_from_52w_high` without candidate replacement evidence.

Next valid retry requires: event/news context or a candidate replacement audit
showing that the new rank key changes executed trades in at least two fixed
windows after slot, heat, gap-cancel, and add-on effects.
