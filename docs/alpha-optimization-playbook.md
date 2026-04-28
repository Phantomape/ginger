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

### 2026-04-28 mechanism update: Initial position cap

Status: accepted / production default.

Core conclusion: exp-20260428-025 tested whether the accepted 50% day-2 add-on
made the old 25% initial position cap too front-loaded. The opposite was true:
raising only the initial cap to 40% improved EV in all three fixed windows and
aggregate PnL by 6.97%, while trade count and add-on execution count were
unchanged.

Evidence: versus the 25% baseline, `MAX_POSITION_PCT=0.40` produced EV deltas
`late_strong +0.0626`, `mid_weak +0.0641`, and `old_thin +0.0067`; aggregate
PnL delta was `+$5,602.35`. The tradeoff is concentration risk: max drawdown
rose in all windows, with worst increase `+0.47 pp`.

Do not repeat: nearby initial-cap sweeps around 30-40% without forward
concentration evidence. This result changes only initial position capacity; it
does not reopen add-on trigger, add-on cap, gap-cancel, or scarce-slot tuning.

Next valid retry requires: live/paper concentration evidence, or a new
independent allocation signal that controls when higher initial concentration
is worth the drawdown tradeoff.

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
