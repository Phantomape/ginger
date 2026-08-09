# 核心股票池超跌反弹：OpenD 观察与 Alpha 实验设计

```yaml
document_type: research_design_note
market_data_as_of: 2026-07-17_close
analysis_date: 2026-07-18_America/Los_Angeles
experiment_id: null
strategy_change: false
trade_enabled: false
live_ready: false
```

本文固化一次核心股票池横截面扫描的输入、公式、结果和后续实验合同。本文不是
accepted alpha，不改变生产 entry / exit / ranking / sizing / orders，也不构成个股交易指令。

## 1. 结论摘要

本次观察得到的 lead：

1. `CAT`：风险调整后最完整。60 日回撤约 `-18%`，RSI14 约 `40.1`，主力资金为正，
   现价附近和下方存在多层 put OI；但它不是最深超跌。
2. `NFLX`：最强战术反弹形态。RSI14 约 `30.7`，60 日回撤约 `-27.2%`，当日从低点明显
   收回，`65-68` put OI 密集；但当日主力资金仍为负，属于事件后高风险反弹。
3. `AVGO` / `TSM` / `CRDO`：有结构、缺确认。分别需要观察 `370`、`400`、`200`
   附近能否站稳；`CRDO` ATR14 约 `12.5%`，风险显著高于前两者。
4. `MU`：价格和期权结构可观察，但资金确认不足。组合已经通过 `MUU` 暴露于 `MU`，
   不能把 alpha 候选直接翻译为继续叠加存储和每日重置杠杆风险。
5. `APP` / `ISRG`：暂不支持直接抄底。`APP` 主力流出；`ISRG` 是放量财报缺口且收盘接近
   日低，期权 IV 还出现异常报价。

最重要的研究结论不是“哪个 put wall 必涨”，而是：

```text
深回撤本身不够；
低 skew 也不是单调的反弹信号；
更值得验证的是：
价格超跌候选中，资金吸收与近价 put 持仓结构同时出现时，
是否提高下一阶段的 replacement value。
```

## 2. 数据范围

### 2.1 股票池

来源：`quant/filter.py::_BASE_WATCHLIST`。

```text
base symbols: 43
equities analyzed: 37
excluded reference ETFs: IAU, GLD, SLV, QQQ, SPY, IWM
```

运行时 `WATCHLIST` 还会合并真实账户持仓。账户中的 `MUU` / `SNXX` 等杠杆产品只能进入
组合风险检查，不能和普通股横截面直接比较。

### 2.2 OpenD 输入

```python
price_source = "OpenQuoteContext.request_history_kline"
price_adjustment = "QFQ"
price_window = ["2025-07-01", "2026-07-17"]

snapshot_flow_source = "OpenQuoteContext.get_capital_distribution"
historical_flow_source = "OpenQuoteContext.get_capital_flow(period_type=DAY)"

option_expiries = ["2026-07-24", "2026-07-31", "2026-08-21"]
option_type = "standard"
```

`get_capital_distribution` 是当前快照。它只能解释本次横截面，不能伪装成历史 PIT 特征。
未来实验应使用已归档的 `get_capital_flow(DAY)`，并按 `usable_trade_date=next_session`
处理。当前历史归档边界为 `2025-07-02` 起，`old_thin` 窗口结构性缺失。

### 2.3 新闻上下文

新闻只用于解释事件风险或 veto，不进入本次数值排名：

- `NFLX`：下一季度业绩预测低于市场预期
  ([Reuters / Investing.com](https://www.investing.com/news/stock-market-news/netflix-thirdquarter-earnings-forecast-falls-shy-of-wall-street-expectations-4796687))；
- `TSM`：季度结果强、上调年度增长预期
  ([Associated Press](https://apnews.com/article/ba05b1b952257d371acb9d070e7914ff))；
- `ISRG`：财报数值不差，但市场关注手术量增速放缓
  ([Intuitive Surgical](https://investor.intuitivesurgical.com/news-releases/news-release-details/intuitive-announces-second-quarter-earnings-6))；
- `MU`：最近季度收入创纪录
  ([Micron](https://investors.micron.com/node/50671))；
- `CRDO`：完成 DustPhotonics 收购
  ([Credo](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Completes-Acquisition-of-DustPhotonics/default.aspx))；
- `CAT`：提高季度股息
  ([Caterpillar](https://www.caterpillar.com/en/news/corporate-press-releases/h/june-2026-dividends.html))。

新闻若要进入 alpha，必须另做结构化 PIT 事件字段，不能依赖 agent 记忆或事后叙事。

## 3. 特征定义

### 3.1 价格特征

```python
ret_5d = close / close.shift(5) - 1
ret_20d = close / close.shift(20) - 1
drawdown_60d = close / close.rolling(60).max() - 1

true_range = max(
    high - low,
    abs(high - prev_close),
    abs(low - prev_close),
)
atr14 = wilder_ewm(true_range, alpha=1 / 14)
atr14_pct = atr14 / close

delta = close.diff()
rsi14 = 100 - 100 / (
    1 + wilder_ewm(delta.clip(lower=0), alpha=1 / 14)
      / wilder_ewm((-delta).clip(lower=0), alpha=1 / 14)
)

close_location = (close - low) / (high - low)
volume_ratio_20 = volume / volume.shift(1).rolling(20).mean()
```

本次初筛只用于生成观察候选：

```python
is_drawdown_candidate = (
    drawdown_60d <= -0.15
    and (rsi14 <= 40 or ret_20d <= -0.15)
)
```

它不是待上线规则。OHLCV 深跌、RSI 和均线形态已经属于高度探索面，未来不得只在这些阈值
附近继续 sweep。

### 3.2 本次资金流口径

```python
net_super = capital_in_super - capital_out_super
net_big = capital_in_big - capital_out_big
net_main = net_super + net_big

# 仅用于本次 2026-07-17 横截面展示
snapshot_main_flow_pct = net_main / same_day_stock_turnover
```

不得混用以下口径：

```text
snapshot_main_flow_pct                = net_main / stock_turnover
sidecar main_flow_ratio               = net_main / gross_order_flow
historical experiment main_flow_ratio = main_in_flow / adv20
```

后续实验必须预先固定一个口径。建议沿用历史归档的：

```python
flow_strength = main_in_flow / avg_dollar_volume_20
```

### 3.3 期权结构口径

“最大 OI 行权价”不能自动称为 put wall。深度实值或远价 OI 可能与当前支撑无关，且 OI 不提供
dealer 净多/净空方向。

```python
put_support_range = [0.75 * spot, 1.01 * spot]
call_resistance_range = [0.99 * spot, 1.30 * spot]

# 对三个到期日按 strike 聚合
put_oi_by_strike = sum(open_interest for matching put strikes)
call_oi_by_strike = sum(open_interest for matching call strikes)

near_put_oi_share = (
    sum(put_oi for strike in [0.94 * spot, 1.01 * spot])
    / sum(put_oi for strike in [0.75 * spot, 1.01 * spot])
)

put_25d_iv = IV of put minimizing abs(abs(delta) - 0.25)
call_25d_iv = IV of call minimizing abs(delta - 0.25)
skew_25d = median(put_25d_iv - call_25d_iv across expiries)
```

`skew_25d` 保留为诊断字段，不进入首个实验的硬 gate 或主分数。本次候选中 `NFLX` 为负 skew，
而 `TSM` / `CRDO` / `MU` 为明显正 skew，说明“skew 越低越容易反弹”在单次横截面上并不成立。

## 4. 2026-07-17 横截面

`main%` 为本次 `snapshot_main_flow_pct`；`skew` 为 IV 百分点。

| Ticker | Close | 20d | DD60 | RSI14 | ATR14 | main% | 近价 put OI | 25d skew | 观察 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| CAT | 880.28 | -7.91% | -18.00% | 40.1 | 5.1% | +1.58% | 880: 1,376; 820: 1,858; 800: 1,922 | +5.66 | 资金与结构最完整 |
| NFLX | 68.95 | -10.41% | -27.19% | 30.7 | 4.1% | -0.30% | 68: 11,699; 67: 12,936; 65: 33,622 | -1.14 | 战术反弹强，资金未确认 |
| AVGO | 370.82 | -5.47% | -24.97% | 43.9 | 4.3% | +0.02% | 370: 6,614; 350: 8,834 | +2.40 | 观察 370 |
| TSM | 398.37 | -7.82% | -16.83% | 39.2 | 5.2% | -0.25% | 400: 15,741; 385: 13,250; 380: 28,978 | +9.14 | 观察能否收复 400 |
| CRDO | 202.68 | -18.71% | -34.34% | 39.5 | 12.5% | +0.24% | 200: 2,370; 190: 1,648; 180: 1,570 | +11.64 | 高波动确认候选 |
| MU | 848.95 | -18.61% | -32.34% | 41.0 | 9.6% | -0.25% | 850: 14,954; 820: 10,460; 800: 24,644 | +10.00 | 结构有、资金弱、组合重叠 |
| APP | 424.54 | -11.46% | -31.75% | 36.2 | 7.9% | -0.99% | 400: 1,604 | +3.34 | 主力流出，先观察 |
| ISRG | 345.42 | -14.11% | -29.67% | 30.2 | 5.2% | -0.91% | 345: 451; 340: 420 | invalid | 财报缺口、收近日低 |
| AMD | 495.76 | n/a | -15.22% | 46.1 | 8.2% | +0.06% | 450: 13,142; 400: 27,850 | +2.35 | 支撑离现价过远 |
| COIN | 157.12 | n/a | -29.34% | 45.8 | 5.8% | -1.53% | 155: 3,207; 150: 6,430 | +2.78 | 流出且事件 beta 高 |
| NOW | 103.24 | n/a | -25.83% | 48.5 | 5.5% | -1.74% | 100: 15,911 | -0.89 | 流出且临近财报 |
| TSLA | 380.84 | n/a | -16.00% | 42.6 | 4.9% | -0.70% | 380: 13,410; 370: 14,174 | +0.55 | 流出且临近财报 |

本次未进入主观察名单的核心普通股：

```text
AAPL AMZN BKNG CVX DDOG DE DIS GE GOOG GS JPM LLY MA MCD META MSFT
NVDA NVO PLTR RTX SNOW SPOT UNH V XOM
```

## 5. 这次观察不能证明什么

```text
不能证明 put OI 是 dealer 支撑；
不能证明低 skew 单调预测反弹；
不能证明当日特大单流入会持续；
不能用 12 个横截面候选估计稳定胜率；
不能把正股信号直接映射到 MUU / SNXX 等每日重置杠杆产品；
不能把事后新闻解释加入历史回测；
不能按本表结果反复调整 RSI、回撤、moneyness、skew 或 flow 阈值。
```

主要数据风险：

1. OI 有报告滞后，且缺少交易方向和 dealer inventory sign。
2. 期权报价可能异常；`ISRG` 2026-07-24 到期链出现约 `-147.9` IV 点异常，因此 fail closed。
3. `get_capital_distribution` 无历史 PIT 回放能力。
4. 新闻、财报和并购会把“技术性超跌”变成基本面重定价。
5. 杠杆 ETF 的日内重置和波动率损耗会改变长期持有收益，不能用正股 10 日收益替代。

## 6. 已有实验与禁止近邻重试

### 6.1 期权面

`exp-20260617-004` 已将 `options_chain_skew_candidate_pool_readiness` 标为 blocked：

```text
reason:
  no fixed-window PIT options-chain replay coverage

forbidden:
  call/put skew, OI, IV, volume, expiration, moneyness,
  ticker-list, top-N, hold-day, notional threshold retunes

reopen:
  PIT-safe chains across all canonical windows with vendor/as-of controls
  OR at least 20-30 closed forward replacement-value rows
```

当前 `data/non_ohlcv/options_forward/options_forward_candidate_ledger_report.json`：

```yaml
generated_at_utc: 2026-07-19T03:37:16Z
candidate_count: 218
options_scoring_allowed: 27
pit_join_safe: 34
closed_5d: 14
closed_10d: 12
closed_20d: 9
closed_60d: 0
decision: shadow_only
```

结论：尚未达到合法重开条件。

### 6.2 Moomoo 资金流面

`exp-20260702-019` 已测试：

```text
main_in_flow > 0
rank = main_in_flow / adv20
top1/day, 10d hold
```

该实验在覆盖窗口内产生正增量，但因 drawdown drift、未击败 accepted comparator、daily snapshot
合同不完整而 rejected。禁止继续 retune main-flow 阈值、super/big bucket、guard、hold、cooldown
或 notional。

已存在的后续基础设施：

```text
exp-20260703-007  daily default-off snapshot wiring: accepted
exp-20260705-016  first forward-row materialization: accepted
reopen condition: materially more settled forward rows with cash/SPY/QQQ replacement value
```

## 7. 合法的下一项 Alpha 假设

在 readiness 条件满足后，只开一张批量实验票，覆盖整个核心股票池，不按 ticker 逐个开 ID。

```yaml
lane: alpha_search
decision_class: ranking_candidate_pool
working_name: core_drawdown_flow_put_support_interaction_v1
single_causal_hypothesis: >
  在固定的核心深回撤候选集中，Moomoo PIT 主力资金强度与近价 put OI 集中度的
  交互排名，比同一候选集的价格-only 排名产生更高的 10 日 replacement value，
  且不显著恶化组合回撤和集中度。
```

固定 treatment，不做阈值搜索：

```python
base_candidates = fixed_drawdown_candidate_set  # same rows for baseline/treatment

flow_rank = cross_sectional_percentile(
    main_in_flow / avg_dollar_volume_20
)
put_support_rank = cross_sectional_percentile(near_put_oi_share)

# 两个来源都必须存在；缺失时 fail closed，不补 0、不猜测。
confirmation_score = sqrt(flow_rank * put_support_rank)

selection = top_1_per_day(confirmation_score)
entry = next_session_open
hold = 10_sessions
same_ticker_cooldown = 10_sessions
instrument = common_stock_only
```

为什么首个实验不放入 skew：本次横截面没有显示稳定单调方向。为什么不交易 `MUU` / `SNXX`：
杠杆映射是独立的 risk-allocation 假设，会污染候选排名归因。

### 7.1 Readiness 条件

reserve 实验 ID 前只做一行计数，不占 ID：

```python
eligible = rows[
    rows.options_scoring_allowed
    & rows.pit_join_safe
    & rows.flow_usable_at_entry
    & rows.forward_10d.notna()
    & rows.cash_spy_qqq_replacement_value_complete
]

ready = (
    eligible.candidate_id.nunique() >= 30
    and eligible.ticker.nunique() >= 10
    and new_settled_rows_since_last_same_surface_probe >= 10
    and settled_row_growth_since_last_same_surface_probe >= 0.50
)
```

另一条合法路径是获得覆盖全部三个 canonical windows、带 vendor/as-of 控制的历史 PIT 期权链。

证据等级必须按数据路径分开：

```text
只有新增 forward settled rows:
  observed-only attribution
  no Gate 4 acceptance
  no production ranking/sizing change

历史 PIT 期权链覆盖三个 canonical windows:
  shared-paper-first helper
  canonical Gate 1-4 challenger
  仍须通过全部保留标准
```

### 7.2 对照与产出

```yaml
baseline:
  candidate_rows: identical
  execution: identical
  ranking: existing price_only_rank

treatment:
  candidate_rows: identical
  execution: identical
  ranking: confirmation_score

primary_horizon: 10_sessions
diagnostic_horizons: [5_sessions, 20_sessions]
primary_value:
  - replacement_value_vs_cash
  - replacement_value_vs_SPY
  - replacement_value_vs_QQQ
  - incremental_value_vs_current_core_slot
secondary_risk:
  - maximum_adverse_excursion
  - max_drawdown
  - future_realized_volatility
  - single_ticker_contribution_share
  - sector_and_theme_concentration
```

必须保留每个候选，而不只保留被选中行，避免 winner-only logging。

## 8. Forward Ledger 合同

```json
{
  "decision_id": "stable-id",
  "signal_date": "YYYY-MM-DD",
  "usable_trade_date": "YYYY-MM-DD",
  "ticker": "CAT",
  "candidate_universe_version": "core_watchlist_hash",
  "price_asof": "timestamp",
  "flow_date": "YYYY-MM-DD",
  "flow_fetched_at": "timestamp",
  "flow_strength": 0.0,
  "options_quote_date": "YYYY-MM-DD",
  "options_retrieved_at": "timestamp",
  "vendor_asof_available": false,
  "option_expiries": [],
  "near_put_oi_share": 0.0,
  "skew_25d_diagnostic": 0.0,
  "options_quality_status": "pass|quarantined",
  "flow_rank": 0.0,
  "put_support_rank": 0.0,
  "confirmation_score": 0.0,
  "baseline_rank": 0.0,
  "selected_by_treatment": false,
  "selected_by_baseline": false,
  "entry_price_next_open": null,
  "forward_return_5d": null,
  "forward_return_10d": null,
  "forward_return_20d": null,
  "replacement_value_cash_10d": null,
  "replacement_value_spy_10d": null,
  "replacement_value_qqq_10d": null,
  "slot_displacement_value_10d": null,
  "outcome_status": "pending|settled|excluded_with_reason",
  "trade_enabled": false
}
```

`NO_SELECTION`、数据缺失、质量隔离和基线选择也必须写入 ledger。

## 9. Gate 与保留标准

执行顺序：

```text
Gate 1: 复用 docs/backtesting.md 当前 cash-feasible frozen baseline
Gate 2: 验证 entry_date、target_price、flow/options as-of 与 usable_trade_date
Gate 3: 检查 generated/survived；survival < 5% 时禁止继续加过滤器
Gate 4: 三个 canonical windows before/after；recent_observe 只作诊断
```

若期权链仍不能覆盖 canonical windows，则只允许 forward observed-only attribution，不能声称
Gate 4 accepted alpha。保留至少需要：

```text
aggregate expected_value_score 提升；
多数窗口 EV 提升且无不可接受回撤恶化；
replacement value 在 cash/SPY/QQQ 和 slot displacement 下仍为正；
样本量、survival、ticker/sector concentration 合格；
成本和 next-open 执行后仍成立；
shared default-off helper 与 daily snapshot/replay 完全同口径。
```

若失败：回滚策略改动，保留 observer/ledger，记录禁止近邻重试，不得改权重、moneyness、hold、
top-N 或 flow/skew 阈值继续消耗 ID。

## 10. 生产与组合边界

首轮实验固定：

```yaml
trade_enabled: false
instrument: common_stock_only
max_positions_in_paper_sleeve: 1
live_orders: none
leveraged_etf_mapping: excluded
```

未来若 alpha 通过，live-realistic envelope 仍需单独验证：

- 滑点、spread、期权数据延迟和 OpenD 失败处理；
- 单票 notional cap、行业/主题 cap 和现有持仓 displacement；
- `MU` 与 `MUU`、`SNDK` 与 `SNXX` 的共同底层暴露；
- 财报窗口 kill switch；
- ATR、gap、stale quote 和 options-quality quarantine；
- 杠杆 ETF 每日重置与复利损耗。

## 11. 相关文件

```text
quant/filter.py
quant/moomoo_capital_flow_sidecar.py
quant/experiments/exp_20260617_004_options_chain_skew_readiness.py
quant/experiments/exp_20260702_019_moomoo_capital_flow_accumulation.py
data/non_ohlcv/moomoo_capital_flow_day/manifest.json
data/non_ohlcv/options_forward/options_forward_candidate_ledger_report.json
experiments/cards/exp-20260702-019.md
docs/backtesting.md
docs/agent_experiment_protocol.md
docs/production_backtest_parity.md
```

开始实验前先运行：

```powershell
.\.venv\Scripts\python.exe -B scripts\list_experiments.py
.\.venv\Scripts\python.exe -B scripts\check_experiment_novelty.py `
  --describe "core drawdown flow put support interaction"
```

只有 readiness 计数满足后，才用 `scripts/experiment.py new` reserve 单一批量实验 ID。
