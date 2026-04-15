"""Per-strategy P&L attribution - shared by backtester and forward_tester.

Single source of truth for the metric definitions so the two simulators
cannot drift.  Inputs are plain dicts so caller has to explicitly pick the
`pnl_pct_net` field that matches its fill model (avoids silently mixing
gross/net numbers across modules).

Expected input fields per trade:
    strategy            (str; missing → 'unknown' bucket)
    pnl_pct_net         (float; required - after fills + commission)
    pnl_usd             (float; optional - only backtester has it)
    initial_risk_pct    (float; optional - (entry - stop) / entry on long)

Metrics produced per strategy:
    trade_count, wins, losses, win_rate, avg_pnl_pct_net,
    profit_factor, total_pnl_usd, avg_R
"""

import math


def aggregate_by_strategy(trades):
    """Aggregate per-trade P&L into per-strategy rollups.

    `profit_factor = sum(win pct) / abs(sum(loss pct))`.
    When a strategy has no losses, profit_factor is `math.inf`; when it has
    no wins, 0.0.  `avg_R` is computed only when every trade in the bucket
    carries a positive `initial_risk_pct` - a partial set would produce a
    misleading average that mixes R-aware and R-blind trades.
    `total_pnl_usd` is omitted from the output when no trade in the bucket
    provided `pnl_usd` (avoids implying a dollar total from a pct-only run).
    """
    buckets = {}
    for t in trades:
        key = t.get("strategy") or "unknown"
        buckets.setdefault(key, []).append(t)

    out = {}
    for strat, rows in buckets.items():
        pnls = [r["pnl_pct_net"] for r in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        if gross_loss == 0:
            profit_factor = math.inf if gross_win > 0 else 0.0
        else:
            profit_factor = gross_win / gross_loss

        risks = [r.get("initial_risk_pct") for r in rows]
        if all(r is not None and r > 0 for r in risks):
            r_multiples = [p / r for p, r in zip(pnls, risks)]
            avg_R = round(sum(r_multiples) / len(r_multiples), 3)
        else:
            avg_R = None

        dollar_pnls = [r.get("pnl_usd") for r in rows if r.get("pnl_usd") is not None]
        total_pnl_usd = round(sum(dollar_pnls), 2) if dollar_pnls else None

        entry = {
            "trade_count":     len(rows),
            "wins":             len(wins),
            "losses":           len(losses),
            "win_rate":         round(len(wins) / len(rows), 4),
            "avg_pnl_pct_net":  round(sum(pnls) / len(pnls), 4),
            "profit_factor":    (round(profit_factor, 3)
                                 if profit_factor not in (math.inf, -math.inf)
                                 else profit_factor),
            "avg_R":            avg_R,
        }
        if total_pnl_usd is not None:
            entry["total_pnl_usd"] = total_pnl_usd
        out[strat] = entry
    return out


def format_attribution_table(by_strategy):
    """ASCII table for CLI output.  Columns adapt to what's present -
    `total_pnl_usd` column only appears if at least one bucket has it.
    """
    if not by_strategy:
        return "  (no trades to attribute)"

    has_dollar = any("total_pnl_usd" in v for v in by_strategy.values())

    header = f"  {'Strategy':<22} {'Trades':>6} {'Win%':>6} {'AvgNet%':>8} {'PF':>6} {'AvgR':>6}"
    if has_dollar:
        header += f" {'$ PnL':>10}"
    lines = [header, "  " + "-" * (len(header) - 2)]

    for strat in sorted(by_strategy.keys()):
        m = by_strategy[strat]
        pf = m["profit_factor"]
        pf_str = "inf" if pf == math.inf else f"{pf:.2f}"
        avg_r = m["avg_R"]
        r_str = f"{avg_r:.2f}" if avg_r is not None else "  -"
        row = (f"  {strat:<22} {m['trade_count']:>6} "
               f"{m['win_rate']*100:>5.1f}% "
               f"{m['avg_pnl_pct_net']*100:>+7.2f}% "
               f"{pf_str:>6} {r_str:>6}")
        if has_dollar:
            d = m.get("total_pnl_usd")
            row += f" {('$' + format(d, ',.0f')) if d is not None else '-':>10}"
        lines.append(row)
    return "\n".join(lines)
