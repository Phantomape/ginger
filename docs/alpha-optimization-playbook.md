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

## 3. 当前优先级

默认下一轮从高到低：

1. `alpha_search` 优先，除非存在明确测量阻断项。
2. lifecycle alpha，尤其是已方向性为正但未 production-promoted 的 entry follow-through add-on。
3. meta-allocation / regime routing，重点解释 `mid_weak` 为什么赚钱但跑输指数。
4. LLM / news attribution repair，只在它能释放 soft ranking、news-confirmed exit 或 C strategy grading 时插队。
5. 新 universe / 新 entry 只做 shadow audit；不要直接接 production。

当前不建议继续消耗迭代的方向：

- 弱持仓 day-5/day-10 price-only early exit。
- 纯 OHLCV pullback reclaim / leadership / compression entry 的局部扫参。
- broad macro defensive overlay 的简单门控。
- C 策略的单字段或小 checklist 修修补补。
- entry follow-through add-on 的附近阈值微调。

## 4. 机制状态表

| Mechanism family | Status | Long-term conclusion | Key experiments |
|---|---|---|---|
| Accepted A+B stack | accepted baseline | 三窗口均赚钱，late 强，mid 跑输指数，old win rate 不稳 | fixed-window backtests |
| Technology trend wider target | accepted | winner-truncation repair 可在窄 cohort 上成立 | exp-20260425 target-width family |
| Commodity trend wider target | accepted narrow | 部分 commodity trend winner 需要更宽 target，但不可泛化到 breakout | exp-20260425 target-width family |
| Single-position cap 25% | accepted | 改善 winner capture / risk allocation，保留 | exp-20260425 cap family |
| Entry follow-through add-on | promising, default-off | day2 `>= +2%` 且 RS vs SPY `> 0` 的 25% add-on 三窗口方向性为正，但 materiality modest | exp-20260426-009/010/011/012/035, exp-20260427-010/011 |
| LLM soft ranking | blocked / high-upside | 方向仍重要，但必须先有足够 production-aligned replay sample | exp-20260426-015/022/023 |
| News-confirmed weak-hold exit | blocked, not falsified | 概念比 price-only exit 干净，但 archive coverage 不足 | exp-20260425-037 |
| Earnings C strategy revival | deferred | PEAD 大类未死，但当前实现不是简单补数据能救 | exp-20260418+, C-gate families |
| Meta-allocation / regime routing | promising but early | `mid_weak` 问题更像什么时候用哪个 sleeve，而不是缺一个 entry | exp-20260423 meta series |
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
