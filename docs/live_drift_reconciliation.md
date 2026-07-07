# Live Drift Reconciliation（实盘 realized vs 模型 expected 对账合同）

> 背景（2026-07-06 系统盲区评审）：系统能验证 replay parity，但没有任何面回答
> "核心 edge 现在还活着吗"。三个标准窗口冻结在 2024-10 ~ 2026-04；基线冠军在
> 18 个月里只有 ~61 笔；`data/live_pilot/` 只有 pilot 推荐与 stop alert，没有
> 实盘已实现表现与回测模型期望的持续对账。若核心 edge 在最近数月衰减，
> 仓库里没有一个面会报警。本合同定义那个面。

## 合同

**面（surface）**：`data/live_pilot/live_drift/`
- `ledger.jsonl` — 每交易日一批行，按 `(asof_date, position_id)` 幂等；
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
