# Live Drift Reconciliation（实盘 realized vs 模型 expected 对账合同）

## v4 executable-entry alert provenance (exp-20260802-002)

`live_drift_reconciliation_v4` keeps the raw drift arithmetic and exposure
buckets unchanged, but an execution alert now requires three independent facts:

1. the position consumes a core slot and carries a static strategy tag from
   `CORE_STRATEGY_POSITION_TAGS`;
2. canonical `data/live_pilot/broker_execution/order_snapshots.jsonl` contains
   BUY fill evidence for the ticker on the entry market session, covering the
   current share quantity; every matching entry fill must be `session=RTH` or
   `session=ALL` and must explicitly record `fill_outside_rth=false`;
3. the exact prior completed market session's
   `data/daily/signals/quant/quant_signals_YYYYMMDD.json` contains a matching
   strategy row in the final top-level `signals` list, with
   `sizing.shares_to_buy > 0` and explicit next-session-open timing.

Missing files, malformed JSON/schema, absent/mismatched signals, zero-share
decisions, ETH fills, or any outside-RTH/unknown session flag fail closed for
alert eligibility. Each row exposes the broker and policy evidence statuses plus
the final exclusion reason. Raw `fill_drift_pct`, `trajectory_drift_pct`, and
bucket aggregates remain visible even when the row is ineligible. In particular,
the 2026-07-31 AMZN fills are canonical ETH/outside-RTH orders, so the raw
`+2.352%` fill drift remains in the core bucket but cannot trigger the regular-open
execution alert.

Every v4 row stamps `market_session_date` from the canonical ticker bars. Ledger
append and alert streak identity are `(market_session_date, position_id)`, not
wall-clock `asof_date`; weekend, holiday, UTC-boundary, and restart reruns of the
same completed session therefore neither append a second row nor advance the
streak. A newly completed market session advances it exactly once.

The v1-v3 ledger remains byte-for-byte append-only. Legacy rows have no standalone
v4 alert authority. While a position is still open, evaluation may enrich an
in-memory legacy copy with the current verified v4 evidence; persisted history is
never rewritten. Orders, ranking, sizing, exits, thresholds, and drift formulas
are unchanged.

## v3 policy-entry alert eligibility (exp-20260726-003)

> Historical contract, superseded for alert eligibility by v4. The static tag is
> still required, but is no longer sufficient without broker and prior-policy
> evidence.

`strategy_bucket` is an exposure/capacity classification, not proof that the
position was entered by the core execution policy. A position that consumes a
core slot therefore remains in the `core` bucket even when it was opened by a
manual, FOMO, or otherwise non-policy path.

Every v3 row records explicit entry provenance and the then-current
`core_execution_alert_eligible`. At v3, eligibility required both core exposure
and an `opened_by_strategy` value in the shared `CORE_STRATEGY_POSITION_TAGS` set.
Raw drift and bucket notional remain visible for ineligible positions, but only
eligible rows contribute to the core fill/trajectory alert calculation. A
session containing only ineligible core exposure is a non-breach session and
resets an older alert streak.

The v1/v2 JSONL ledger remains append-only. During alert evaluation only, a
current position with the same `position_id` may enrich an in-memory copy of a
legacy row; persisted history is never rewritten. Missing eligibility is
legacy-compatible for v1/v2 rows and fail-closed for v3 or later rows. Drift
formulas, alert thresholds, orders, ranking, sizing, and exits are unchanged.

The position schema itself does not carry a trustworthy exchange-session flag.
v4 therefore resolves session provenance from canonical broker order snapshots
and never infers regular versus extended-hours execution from `entry_date`.

## v2 shared-position-schema alignment (exp-20260723-010)

`live_drift_reconciliation_v2` uses `quant/open_position_schema.py` as the
single source of truth for account grouping and core-slot ownership:

- all real holdings in `positions`, `core_positions`, and `observations` enter
  the reconciliation surface;
- any row for which `position_consumes_core_slot(...)` is true is bucketed as
  `core`; an explicit `no_core_slot` policy remains non-core;
- v1 ledger rows remain append-only historical evidence and are not rewritten.

This is a measurement-only schema repair. Drift formulas, alert thresholds,
orders, ranking, sizing, and exits are unchanged.

> 背景（2026-07-06 系统盲区评审）：系统能验证 replay parity，但没有任何面回答
> "核心 edge 现在还活着吗"。三个标准窗口冻结在 2024-10 ~ 2026-04；基线冠军在
> 18 个月里只有 ~61 笔；`data/live_pilot/` 只有 pilot 推荐与 stop alert，没有
> 实盘已实现表现与回测模型期望的持续对账。若核心 edge 在最近数月衰减，
> 仓库里没有一个面会报警。本合同定义那个面。

## 合同

**面（surface）**：`data/live_pilot/live_drift/`
- `ledger.jsonl` — 每个已完成交易日一批行，v4 按 `(market_session_date, position_id)` 幂等；
- `state.json` — 最新一次对账的汇总。

**逐持仓行（v1，开仓与在途侧）**，对每个 moomoo 长仓（`operator_inputs/open_positions.json`）：

| 字段 | 含义 |
|---|---|
| `modeled_entry_price` | 模型口径入场价：entry_date 当日 open × 入场滑点（与 backtester fill model 同参） |
| `fill_drift_pct` | `avg_cost / modeled_entry_price - 1`（正 = 实盘买贵了） |
| `realized_return_pct` | `(market_val/shares) / avg_cost - 1`（moomoo 实际标记） |
| `modeled_return_pct` | `close_asof / modeled_entry_price - 1`（同一 exit 政策下模型应有的在途收益） |
| `trajectory_drift_pct` | `realized - modeled`（执行 + 费用 + 分红的累计偏差） |
| `strategy_bucket` | `core` / `sleeve` / `discretionary_legacy`（按 opened_by_strategy / sleeve 标签） |

**汇总（state.json + 日报一行）**：全账簿名义加权 `trajectory_drift_pct`、按 bucket 拆分、
不可对账持仓数（缺 entry_date / 缺 bar）及原因。

**警戒口径（供 sleeve_health / 日报引用）**：core bucket 名义加权 trajectory drift
连续 10 个交易日 < -1.5%，或 fill drift 均值 > +30bp，视为执行/模型漂移事件，
按 measurement_repair 插队处理。

## 明确不做（v1 边界）与 v2 重开条件

- **已平仓侧对账（exit drift、每笔已实现 PnL vs 模型 PnL）**：当前 moomoo 历史成交
  （deal history）未物化为任何 PIT 面。v2 重开条件：`operator_inputs/`（或 sidecar）
  出现按日追加的成交历史档案，且覆盖 ≥20 笔已平仓。届时把 ledger 扩展
  `exit_drift_pct` / `realized_pnl_vs_modeled`，不新开面。
- **信号级归因**（哪个信号贡献了 drift）：属于 alpha 归因，不塞进这个测量面。
- 本面是纯观察：不改变任何订单、排序、仓位。

## 与"edge 是否还活着"的关系

本面回答执行保真度（实盘是否复现模型轨迹）。edge 本身的存活由
`recent_observe` 窗口 + forward 记分卡回答；两者结合的解读规则：
drift ≈ 0 且 recent_observe 恶化 → edge 问题；drift 显著负 → 执行/成本问题；
两者都恶化 → 先修执行再评 edge。

首建实验：exp-20260706（measurement_repair，见 experiment log）。
