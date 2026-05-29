# Alpha Direction: Expectation Drift × Residual Leadership × PEAD Continuation

> 目标：把 Ginger 下一阶段 alpha 搜索从“更多规则 / 更多 surface”收敛到一个更高信息密度、更可 replay、更接近 institutional medium-term systematic research 的主线。

---

## 1. 一句话结论

当前最值得深挖的 alpha 方向是：

```text
Expectation Drift
+
Residual Leadership
+
Post-Earnings Drift Continuation
```

也就是：

```text
市场预期在持续上修，
股票相对市场 / 行业 / theme 持续领先，
且财报后仍然有机构再定价 / 资金继续流入。
```

不要优先继续挖：

```text
更多 breakout rule
更多 filter
更多 top-up scalar
更多 regime subclass
更多 latent state abstraction
```

而应该优先挖：

```text
哪些股票在预期变化后，
还能持续成为 residual leader。
```

---

## 2. 为什么是这个方向

### 2.1 它是真正的数据 edge，不只是 OHLCV remix

Ginger 目前很多 alpha 仍来自：

```text
price momentum
breakout
relative strength
cap-aware sizing
slot condition
```

这些有用，但很容易变成：

```text
同一套 OHLCV 信息的不同包装
```

真正提高 alpha 上限的方向，是更上游的信息：

```text
expectation change
```

价格告诉我们：

```text
市场已经怎么反应
```

预期变化告诉我们：

```text
市场为什么可能继续反应
```

这比单纯价格形态的信息密度更高。

---

### 2.2 它和 Ginger 的系统结构高度匹配

Ginger 不是高频系统，也不是 intraday stat-arb。

它最适合：

```text
EOD
medium-term
event-enhanced
cross-sectional
replayable
paper-first
```

而 expectation drift / PEAD continuation 正好符合这些约束：

- 非日内；
- 可 daily snapshot；
- 可 replay；
- 可做 attribution；
- 可做 cross-sectional ranking；
- 可和已有 earnings / SEC / event infra 结合；
- 合理持仓周期可以是 5-20 trading days。

这比 options flow、order book、tick alpha 更适合当前 Ginger。

---

### 2.3 Core stack 的 scalar / cap 微调已经进入边际收益递减

当前 core stack 已经叠加了很多小型 sizing / cap / top-up 规则。

继续挖：

```text
1.025x top-up
1.05x top-up
再加一个 slot rule
再加一个 sector exception
```

边际收益大概率越来越低。

因此，下一阶段更应该提升：

```text
每个 candidate 背后的信息密度
```

而不是继续调已有 candidate 的微小 sizing scalar。

---

### 2.4 它符合 Ginger 现有 playbook 的经验结论

Ginger 历史上更有效的方向通常是：

```text
固定 candidate set
+
更好的 sizing / ranking / capital routing
```

而不是：

```text
broad filters
broad overlays
broad reranking
```

所以 expectation drift 不应该一开始做成 hard filter。

正确方式是：

```text
用 expectation drift 提高 ranking / sizing confidence，
而不是直接过滤所有股票。
```

也就是说：

```text
entry 可以继续由现有系统产生，
但 ranking_score / replacement value / paper sleeve attribution
应该加入 expectation drift 和 residual leadership。
```

---

## 3. 核心 alpha 假设

### Main Hypothesis

```text
同时满足 positive expectation drift 和 residual leadership 的股票，
在未来 5-20 trading days 的 realized R / PnL，
显著优于普通 breakout / trend candidates。
```

### 更具体地说

一个高质量 candidate 应该满足：

```text
市场预期在上修
+
价格相对市场 / QQQ / sector / theme 在超额上涨
+
财报后或事件后没有快速失败
+
后续仍有资金继续 reposition
```

---

## 4. 要挖的三个子方向

## 4.1 Expectation Revision Velocity

核心问题：

```text
EPS / revenue estimate 在过去 7d、30d 是否持续上修？
```

优先特征：

```text
eps_revision_velocity_7d
eps_revision_velocity_30d
eps_revision_acceleration
revenue_revision_velocity_30d
analyst_count_delta_30d
```

最重要的不是：

```text
当前 EPS estimate 是多少
```

而是：

```text
estimate trajectory 在怎么变化
```

高价值状态：

```text
EPS estimate 上修
+
revenue estimate 上修
+
analyst count 增加
+
surprise history 正
```

这比单纯 breakout 信息密度更高。

---

## 4.2 Post-Earnings Drift Continuation

核心问题：

```text
财报后 T+2 到 T+15，
是否还有机构持续 reposition？
```

不要赌财报当天。

重点是：

```text
财报后市场已经知道信息，
但资金还没完全完成换仓。
```

候选条件：

```text
positive surprise
or positive guidance / non-negative guidance
or positive estimate revision
+
post-earnings gap 没有快速失败
+
T+2 / T+5 后仍然相对 QQQ / sector 强
```

这比普通 breakout 更适合作为中短线 / 中频 alpha。

---

## 4.3 Residual Leadership

核心问题：

```text
它是真的强，
还是只是 QQQ / AI / sector 都在涨？
```

要看：

```text
ret20_excess_spy
ret20_excess_qqq
ret20_excess_theme
ret20_excess_sector
```

例子：

```text
META 涨 8%
```

不一定有 alpha。

但如果：

```text
META 涨 8%
QQQ 涨 2%
mega-cap peers 涨 1%
communication services 涨 0%
```

那才可能是 residual leadership。

---

## 5. 第一个实验设计

# EXP_EXPECTATION_RESIDUAL_LEADERSHIP_001

## Hypothesis

```text
positive expectation drift + residual leadership 的股票，
未来 5-20 trading days 的 realized R / PnL，
显著优于普通 breakout / trend candidates。
```

## Mode

第一阶段必须是：

```text
read-only attribution
```

不得直接改变 live entry / sizing / ranking / orders。

---

## 6. Attribution 分桶

把 candidate / trade 分成四组：

```text
Bucket A:
positive expectation drift + residual leader

Bucket B:
positive expectation drift + no residual leadership

Bucket C:
residual leader + no expectation drift

Bucket D:
neither
```

---

## 7. 观察指标

每个 bucket 至少看：

```text
avg_R
win_rate
avg_pnl
total_pnl
tail_loss
worst_trade
top5_contribution
max_drawdown contribution
replacement value vs next core slot
```

理想结果：

```text
Bucket A 明显 outperform B/C/D，
且不是只靠少数 jackpot trade。
```

---

## 8. 第二个实验：PEAD Paper Sleeve

如果第一个 attribution 通过，再做：

```text
SHORT_HORIZON_PEAD_PAPER
```

仍然默认 paper-only。

## Candidate Window

```text
T+2 到 T+10 after earnings
```

## Requires

```text
positive surprise or positive revision
residual strength > threshold
market not risk_off
no immediate gap failure
```

## Hold

```text
5-15 trading days
```

## Exit

```text
time-based
or loss-based
```

核心不是：

```text
财报好就买
```

而是：

```text
财报后仍然有 residual follow-through 才进入 paper queue。
```

---

## 9. 第三个实验：Ranking Score Replacement Test

目标：验证新的 expectation / residual component 是否改善 ranking。

比较：

```text
old alpha_score
vs
old alpha_score + expectation_residual_component
```

观察：

```text
top_decile 是否更 monotonic
top_decile - bottom_quintile spread 是否扩大
component_predictive_value 是否更稳定
```

如果 monotonicity 没改善：

```text
直接拒绝。
```

不要强行解释。

---

## 10. 为什么不是优先挖 theme lifecycle / state transition

Theme lifecycle 很有价值，但更适合作为：

```text
risk / context / concentration modifier
```

而不是第一 alpha source。

当前优先级应该是：

```text
1. expectation drift
2. residual leadership
3. PEAD continuation
4. breadth alignment
5. theme lifecycle as risk context
```

而不是：

```text
1. theme state machine
2. regime subclass
3. latent vectors
```

原因：

```text
state machine / lifecycle abstraction 很容易漂亮但过拟合。
```

---

## 11. 过拟合防线

这个方向虽然合理，但必须避免：

```text
beautiful overfitting
```

硬约束：

1. 不允许直接 live；
2. 先做 read-only attribution；
3. 必须证明 bucket monotonicity；
4. 必须跨窗口；
5. 必须看 tail / concentration；
6. 必须证明不是 SPY / QQQ beta；
7. 必须可以 production daily snapshot；
8. 如果 evidence 不清楚，拒绝而不是复杂化。

---

## 12. 判断标准

一个 feature / component 可以继续推进，必须至少满足：

```text
top bucket > mid bucket > bottom bucket
```

或至少：

```text
top bucket 显著优于 bottom bucket
```

并且：

```text
不是靠 1-2 笔 jackpot trade 支撑。
```

如果：

```text
feature 看起来合理，
但 attribution 不稳定，
monotonicity 不存在，
或者只在单窗口有效，
```

则：

```text
拒绝。
```

---

## 13. 最终方向

Ginger 下一阶段最值得挖的 alpha 主线是：

```text
Expectation Drift × Residual Leadership
```

原因：

```text
它更接近真正的数据 edge，
更适合中频系统，
更容易 replay，
更容易 attribution，
也更不容易沦为 OHLCV rule remix。
```

这是当前最符合 Ginger 阶段的 alpha 搜索方向。

---

## 2026-05-27 three-round observed-only suite

`exp-20260527-002` through `exp-20260527-010` ran three observed-only
rounds for each sub-direction in this memo:

- Expectation revision velocity:
  `exp-20260527-002` EPS 7d magnitude,
  `exp-20260527-003` previous-delta confirmation,
  `exp-20260527-004` same-event history depth.
- PEAD continuation:
  `exp-20260527-005` earnings-date readiness,
  `exp-20260527-006` post-revision 2d failure proxy,
  `exp-20260527-007` candidate-conversion lag.
- Residual leadership:
  `exp-20260527-008` residual-strength magnitude,
  `exp-20260527-009` SPY/QQQ residual agreement,
  `exp-20260527-010` residual-state quality.

All nine rounds stayed read-only and changed no entries, exits, ranking,
sizing, LLM/news prompts, paper sleeves, or orders. After tightening the gate
so both preferred and comparison buckets need enough closed 5d/10d outcomes,
all nine ended as `observed_only_data_gap`. A follow-up measurement repair
passed `same_event_history_count` through the compact watchlist rows and
reran the suite; `exp-20260527-004` then had full same-event-history coverage,
but the preferred `history_ge_10` bucket still lacked closed 10d outcomes. The
same repair also passed through existing `theme_residuals` as
`ret20_excess_theme`; theme residual coverage is now partial (`180/700` rows in
the rerun). A second measurement repair added read-only sector residuals from
`residual_strength_surface` and enriched missing feature-sector labels from the
offline deterministic `broad_market_sector_map` cache; `ret20_excess_sector`
coverage is now partial (`316/700` rows), with the caveat that this is a
replayable public-classification proxy rather than proof production observed
the label point-in-time. The remaining blockers are thin 10d
preferred/comparison buckets, missing PIT `last_earnings_date`, and zero
primary-positive candidate conversions within 10 trading days. Do not promote
this direction to ranking, sizing, or a PEAD paper sleeve until those fields
and closed outcomes mature.

---

## 2026-05-29 freeze note: 5d direction is disproven on the current single-season sample

The three measurement blockers above were fixed, and the three core
sub-hypotheses were then each tested directly with closed forward
outcomes. **All three were rejected at the 5d primary horizon.**

Measurement repairs that unblocked the tests (all read-only, all
committed as per-experiment artifacts):

- `exp-20260527-908` reconstructed PIT `last_earnings_date` from SEC EDGAR
  10-Q / 10-K / 8-K(2.02) filings — 40/47 (85.1%) primary positive rows
  resolved, populating the PEAD-eligible buckets that were previously empty.
- `exp-20260528-030` derived PIT `eps_estimate_delta_30d` from the
  `earnings_snapshot` history — 38/47 (80.85%) primary positive rows
  resolved, giving the revision-magnitude branch its 30d axis.

Direct attribution results (read-only, exp-20260527-005 published
gate thresholds: `min_bucket_closed_5d=8`, `min_bucket_closed_10d=5`,
concentration `top5<=0.6`, `single<=0.5`):

| Sub-hypothesis | Experiment | 5d lift (preferred − comparison) | 10d lift | Decision |
|---|---|---|---|---|
| Residual leadership inside PEAD window | `exp-20260528-027` | **−3.60 pp** (residual eligible −2.0% vs non-residual +1.6%) | +0.68 pp | `rejected_no_residual_pead_edge` |
| PEAD window itself (3 revision tiers, no residual filter) | `exp-20260528-028` | **−0.40 pp** on the cleanest tier (`wide_watchlist_positive`, 25 closed 5d, size+conc pass) | +0.35 to +1.12 pp | `rejected_no_pead_window_lift_across_tiers` |
| Revision magnitude high vs low (7d + 30d axes) | `exp-20260529-007` | **−1.15 pp** on the decisive 7d axis | +1.40 pp | `rejected_no_revision_magnitude_edge` |

**Recurring signature: 5d-negative / 10d-positive across all three.**
Every sub-hypothesis underperforms its comparison at the 5d primary
horizon yet flips positive at 10d. This is consistent with the doc's
own thesis that institutional re-pricing plays out slowly (T+2..T+15),
*but* every 10d bucket on the current sample is too thin to be decisive
(comparison buckets of 2–6 closed observations, below the 5/10d floors),
and AGENTS.md Section 12 treats a single-window sign flip as a rejection
signal rather than a discovery. The 10d signal is therefore recorded as
an open question, not evidence.

### Freeze decision

This direction is **frozen at the 5d horizon** as of 2026-05-29. Do not
re-test residual leadership, the PEAD window, or revision magnitude as a
5d alpha clue on the current watchlist — the measurement is no longer the
blocker (the fields are populated), the sample is.

A retry requires **new evidence**, specifically:

1. More than one earnings season of watchlist rows, so the 10d buckets
   clear the published floors and the 5d-negative / 10d-positive flip can
   actually be tested instead of guessed; and
2. A pre-registered 10d hypothesis (not a 5d one), since 5d is now
   disproven three independent ways.

Measurement work that is still allowed without new forward rows:
`revenue_estimate` / `analyst_count` velocity fields (still absent), and
full PIT `ret20_excess_sector` / `ret20_excess_theme` coverage (currently
partial), because those widen the eventual 10d test rather than re-running
a disproven 5d one. No new 5d attribution on this direction should take
the top priority slot until condition (1) is met.
