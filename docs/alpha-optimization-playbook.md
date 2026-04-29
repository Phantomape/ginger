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

当前固定三窗口 baseline，按 `docs/backtesting.md`：

| Window | Range | EV | Return | Sharpe daily | Max DD | Win rate | Trades | Main interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `late_strong` | 2025-10-23 -> 2026-04-21 | 1.5039 | +35.47% | 4.24 | 2.81% | 71.4% | 21 | accepted A+B 非常强 |
| `mid_weak` | 2025-04-23 -> 2025-10-22 | 0.4773 | +20.31% | 2.35 | 2.47% | 47.6% | 21 | 赚钱但跑输 SPY/QQQ，最像 meta-allocation 问题 |
| `old_thin` | 2024-10-02 -> 2025-04-22 | 0.1310 | +11.39% | 1.15 | 4.56% | 37.5% | 24 | 赚钱且跑赢指数，但 win rate 不稳定 |

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
