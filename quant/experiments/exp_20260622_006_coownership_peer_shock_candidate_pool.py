"""exp-20260622-006: institutional co-ownership peer-shock candidate pool.

Head-to-head Gate-4 of the Anton-Polk "Connected Stocks" peer definition against
the accepted rolling-correlation peer definition. Both sleeves are run on the
SAME canonical 3-window data with the SAME core-flow confirmation entries; the
ONLY difference is how a (peer-shock, laggard) pair is admitted:

  rolling_corr : 60d Pearson correlation of return vectors >= 0.58
  coownership  : the two names are 13F co-ownership network peers
                 (shared institutional managers, lift over independence >= 1.5)

For each window we overlay each sleeve's default-off paper trades on the core
baseline and read the after-vs-before aggregate EV / PnL delta, so the comparison
is apples-to-apples. Default-off: neither sleeve alters live orders.

Run:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260622_006_coownership_peer_shock_candidate_pool.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402

shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve_overlay = framework.sleeve  # exp_20260525_011: _overlay_from_paper_trades
WINDOWS = framework.WINDOWS
REPO_ROOT = framework.REPO_ROOT

import coownership_peer_shock_paper_sleeve as cps  # noqa: E402
import rolling_corr_peer_shock_paper_sleeve as rc  # noqa: E402

EXPERIMENT_ID = "exp-20260622-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "coownership_vs_rolling_corr_peer_shock.json"

SLEEVES = {
    "coownership": {
        "build": cps.build_coownership_peer_shock_historical_trades,
        "rule_version": cps.RULE_VERSION,
    },
    "rolling_corr": {
        "build": rc.build_rolling_corr_peer_shock_historical_trades,
        "rule_version": rc.RULE_VERSION,
    },
}


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _trade_economics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(t.get("pnl") or 0.0) for t in trades]
    wins = [p for p in pnls if p > 0]
    by_ticker: dict[str, float] = {}
    for t in trades:
        by_ticker[str(t.get("ticker"))] = by_ticker.get(str(t.get("ticker")), 0.0) + float(t.get("pnl") or 0.0)
    positive = {k: v for k, v in by_ticker.items() if v > 0}
    pos_total = sum(positive.values())
    max_share = max(positive.values()) / pos_total if pos_total > 0 else None
    hhi = sum((v / pos_total) ** 2 for v in positive.values()) if pos_total > 0 else None
    return {
        "trade_count": len(trades),
        "net_pnl": _round(sum(pnls), 2),
        "win_rate": _round(len(wins) / len(trades), 4) if trades else None,
        "avg_pnl_per_trade": _round(sum(pnls) / len(trades), 2) if trades else None,
        "unique_tickers": len(by_ticker),
        "single_ticker_positive_share": _round(max_share, 4) if max_share is not None else None,
        "positive_pnl_hhi": _round(hhi, 4) if hhi is not None else None,
    }


def run() -> dict[str, Any]:
    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()

    per_window: dict[str, Any] = {}
    agg = {name: {"overlay_pnl": 0.0, "trade_count": 0, "ev_delta": 0.0, "trades": []} for name in SLEEVES}

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline ...", flush=True)
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=set(sector_entries))
        core_entries_by_date = shadow._baseline_entries(before_result)
        sector_map = {t: m for t, m in sector_entries.items() if t in snapshot}

        window_record: dict[str, Any] = {
            "before_ev": before.get("expected_value_score"),
            "before_pnl": before.get("total_pnl"),
            "core_entry_days": len(core_entries_by_date),
            "loaded_ticker_count": len(snapshot),
            "sleeves": {},
        }

        for name, spec in SLEEVES.items():
            print(f"[{label}] {name} peer-shock replay ...", flush=True)
            trades, audit = spec["build"](
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries_by_date,
                windows={label: {"start": cfg["start"], "end": cfg["end"]}},
                sector_entries=sector_map,
            )
            overlay = sleeve_overlay._overlay_from_paper_trades(before_result, trades)
            after = overlay_helper._metrics_with_overlay(before_result, overlay)
            delta = overlay_helper._delta(after, before)
            econ = _trade_economics(trades)

            ev_delta = (after.get("expected_value_score") or 0.0) - (before.get("expected_value_score") or 0.0)
            agg[name]["overlay_pnl"] += float(overlay["overlay_total_pnl"] or 0.0)
            agg[name]["trade_count"] += econ["trade_count"]
            agg[name]["ev_delta"] += ev_delta
            agg[name]["trades"].extend(trades)

            window_record["sleeves"][name] = {
                "rule_version": spec["rule_version"],
                "after_ev": after.get("expected_value_score"),
                "ev_delta": _round(ev_delta, 6),
                "overlay_total_pnl": _round(overlay["overlay_total_pnl"], 2),
                "max_drawdown_pct_after": after.get("max_drawdown_pct"),
                "economics": econ,
                "scan": audit.get("scan_by_window", {}).get(label, {}),
            }
        per_window[label] = window_record

    aggregate = {}
    for name in SLEEVES:
        aggregate[name] = {
            "aggregate_overlay_pnl": _round(agg[name]["overlay_pnl"], 2),
            "aggregate_ev_delta": _round(agg[name]["ev_delta"], 6),
            "total_trade_count": agg[name]["trade_count"],
            "economics_all_windows": _trade_economics(agg[name]["trades"]),
        }

    co = aggregate["coownership"]
    rcm = aggregate["rolling_corr"]
    incremental = {
        "coownership_minus_rolling_corr_overlay_pnl": _round(
            (co["aggregate_overlay_pnl"] or 0.0) - (rcm["aggregate_overlay_pnl"] or 0.0), 2
        ),
        "coownership_minus_rolling_corr_ev_delta": _round(
            (co["aggregate_ev_delta"] or 0.0) - (rcm["aggregate_ev_delta"] or 0.0), 6
        ),
    }
    # Decision: co-ownership must (a) be additive at all (positive aggregate EV
    # delta over the core) AND (b) beat the accepted rolling-corr peer definition
    # on aggregate overlay PnL to justify a distinct sleeve.
    co_additive = (co["aggregate_ev_delta"] or 0.0) > 0 and (co["aggregate_overlay_pnl"] or 0.0) > 0
    beats_comparator = (incremental["coownership_minus_rolling_corr_overlay_pnl"] or 0.0) > 0
    if co_additive and beats_comparator:
        decision = "accepted_paper_pending_forward"
    elif co_additive:
        decision = "additive_but_not_better_than_rolling_corr"
    else:
        decision = "reject"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": "13F co-ownership network peers (Anton-Polk Connected Stocks) admit better peer-shock laggards than rolling-correlation peers.",
        "decision_variable": "peer-adjacency source: co-ownership graph vs rolling correlation",
        "windows": list(WINDOWS.keys()),
        "per_window": per_window,
        "aggregate": aggregate,
        "incremental_vs_rolling_corr": incremental,
        "decision": decision,
        "production_impact": cps._production_impact(),
        "execution_envelope": {
            "base_notional": cps.DEFAULT_CONFIG["paper_notional_usd"],
            "max_concurrent": None,
            "min_dollar_volume": cps.DEFAULT_CONFIG["min_avg_dollar_volume_20d"],
            "slippage_bps": "fill_model.SLIPPAGE_BPS_TARGET",
            "order_semantics": "next_open",
            "hold_days": cps.DEFAULT_CONFIG["hold_days"],
            "kill_switch_drawdown_pct": None,
            "notes": "Paper-pending; forward closed rows required before live eligibility.",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = run()
    print(json.dumps({
        "decision": payload["decision"],
        "aggregate": payload["aggregate"],
        "incremental_vs_rolling_corr": payload["incremental_vs_rolling_corr"],
        "out": str(OUT_JSON),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
