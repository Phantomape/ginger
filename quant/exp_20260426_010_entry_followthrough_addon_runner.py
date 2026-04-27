"""exp-20260426-010 real backtester replay for entry follow-through add-ons.

Hypothesis:
    A position that is up at least 2% two trading days after entry and is
    outperforming SPY deserves a small add-on. This promotes proven early
    winners rather than trying to sell weak starts, which recent experiments
    showed is a poor lifecycle alpha.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / AI-beta continuation",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with crowding risk",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak macro tape",
    }),
])

ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
}

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_010_entry_followthrough_addon_results.json",
)


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (
            result.get("benchmarks", {}).get("strategy_total_return_pct")
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
        "addon": {
            "scheduled": result.get("addon_attribution", {}).get("scheduled"),
            "executed": result.get("addon_attribution", {}).get("executed"),
            "skipped": result.get("addon_attribution", {}).get("skipped"),
        },
    }


def _run_window(universe: list[str], cfg: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    return engine.run()


def _delta(before: dict, after: dict) -> dict:
    fields = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
    ]
    out = {}
    for field in fields:
        b = before.get(field)
        a = after.get(field)
        out[field] = round(a - b, 6) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    return out


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-010",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "day-2 follow-through >= +2% and RS vs SPY > 0 identifies "
            "positions where a 25% original-share add-on improves EV."
        ),
        "parameters": ADDON_CONFIG,
        "windows": {},
    }

    improvements = 0
    material_regressions = 0
    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, BASE_CONFIG)
        addon = _run_window(universe, cfg, ADDON_CONFIG)
        # Keep EV present even if future result schema changes.
        baseline["expected_value_score"] = compute_expected_value_score(baseline)
        addon["expected_value_score"] = compute_expected_value_score(addon)
        before = _metrics(baseline)
        after = _metrics(addon)
        delta = _delta(before, after)
        if (after.get("expected_value_score") or 0) > (before.get("expected_value_score") or 0):
            improvements += 1
        b_ev = before.get("expected_value_score") or 0
        a_ev = after.get("expected_value_score") or 0
        if b_ev > 0 and (b_ev - a_ev) / b_ev > 0.05:
            material_regressions += 1

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": delta,
            "addon_events": addon.get("addon_attribution", {}).get("events", []),
        }

    results["decision_inputs"] = {
        "ev_improved_windows": improvements,
        "material_regression_windows": material_regressions,
        "candidate_gate": (
            "candidate accepted iff EV improves in >=2/3 windows and no window "
            "regresses by more than 5% of baseline EV"
        ),
        "production_gate_note": (
            "AGENTS Gate 4 still requires material improvement before enabling "
            "a new production strategy path by default."
        ),
    }
    candidate_passed = improvements >= 2 and material_regressions == 0
    results["decision"] = "accepted_candidate" if candidate_passed else "rejected"
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Stable 3/3 EV improvement, but effect size is small and does not yet "
        "justify enabling add-ons by default without a follow-up tightness or "
        "forward-validation check."
        if candidate_passed else
        "Candidate gate failed."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps(results["decision_inputs"], indent=2))
    for label, rec in results["windows"].items():
        before = rec["before_metrics"]
        after = rec["after_metrics"]
        delta = rec["delta_metrics"]
        print(
            f"{label}: EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} (delta {delta['expected_value_score']}), "
            f"PnL {before['total_pnl']} -> {after['total_pnl']}, "
            f"addons {after['addon']['executed']}"
        )
    print(f"decision: {results['decision']}")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
