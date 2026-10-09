"""V3 paper ledger: forward replay of deployed rules with the frozen engine and cost model.

Each run replays every deployment from its start date to the latest stored session and appends one
snapshot per new as-of date (append-only).  If replaying an already-recorded date gives a different
NAV, the data under it was revised: that is reported as an alert and the stored row is kept.

Usage:  .venv/Scripts/python.exe v3/tools/paper.py
Deployments: v3/ledger/paper/deployments.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / "evaluator"))
import baselines  # noqa: E402
import engine  # noqa: E402
import evaluate  # noqa: E402

PAPER = V3 / "ledger" / "paper"
SIGNALS = {"baselines:s1_spy_200dma": baselines.s1_spy_200dma, "baselines:s0_spy": baselines.s0_spy}
REL_TOL = 1e-9


def replay(dep: dict, returns: pd.DataFrame, cash: pd.Series) -> dict:
    signal = SIGNALS[dep["signal"]]
    last = returns.index[-1]
    res = engine.run(signal, returns, cash, start=dep["start"], end=last, freq="M",
                     cost_kind="etf", exec_lag=1, capital=dep["capital"])
    nav = pd.Series(dep["capital"] * (1 + res.net).cumprod().values, index=res.net.index)
    holdings = {}
    if res.weights:
        holdings = list(res.weights.values())[-1]
    # value of current holdings after drift is approximated by the last executed weights
    spy = returns["SPY"].loc[res.net.index]
    month_end = pd.bdate_range(last, last + pd.offsets.MonthEnd(0))[-1]
    return {
        "nav_series": nav,
        "snapshot": {
            "as_of": str(last.date()),
            "nav": float(nav.iloc[-1]) if len(nav) else dep["capital"],
            "return_since_start": float((1 + res.net).prod() - 1) if len(nav) else 0.0,
            "spy_return_since_start": float((1 + spy).prod() - 1) if len(nav) else 0.0,
            "last_executed_weights": holdings,
            "trades": [{"date": str(d.date()), "weights": w, "dollars": {k: round(v * float(nav.loc[d]), 2) for k, v in w.items()}}
                       for d, w in res.weights.items()],
            "rule_state_now": signal(engine.History(returns, cash)),
            "next_decision_on_or_before": str(month_end.date()),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    lock = evaluate.verify_lock()
    returns, cash = evaluate.panels(lock)["trading"]
    deployments = json.loads((PAPER / "deployments.json").read_text(encoding="utf-8"))
    alerts, lines = [], ["# V3 paper（自动生成）", ""]
    for dep in deployments:
        path = PAPER / f"{dep['id']}.jsonl"
        stored = evaluate.read_jsonl(path)
        out = replay(dep, returns, cash)
        snap, nav = out["snapshot"], out["nav_series"]
        for row in stored:
            d = pd.Timestamp(row["as_of"])
            if d in nav.index and abs(nav.loc[d] - row["nav"]) > REL_TOL * row["nav"]:
                alerts.append(f"{dep['id']}: replayed NAV on {row['as_of']} is {nav.loc[d]:.2f}, stored {row['nav']:.2f} (data revised)")
        if not stored or stored[-1]["as_of"] < snap["as_of"]:
            evaluate.append(path, snap)
        lines += [
            f"## {dep['id']}（{dep['note']}）",
            "",
            f"- 起点 {dep['start']}，名义资本 ${dep['capital']:,.0f}；截至 {snap['as_of']}：NAV ${snap['nav']:,.2f}，"
            f"累计 {snap['return_since_start']:+.2%}（同期 SPY {snap['spy_return_since_start']:+.2%}）",
            f"- 当前持仓（最近一次成交）：{snap['last_executed_weights'] or '现金'}；规则此刻的状态：{snap['rule_state_now'] or '现金'}",
            f"- 下一次月末决定：{snap['next_decision_on_or_before']}，次日收盘成交",
            "",
        ]
    if alerts:
        lines = ["**ALERT** " + a for a in alerts] + [""] + lines
    (PAPER / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
