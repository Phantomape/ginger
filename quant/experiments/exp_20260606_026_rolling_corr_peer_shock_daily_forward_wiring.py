from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from default_off_alpha_attribution import build_default_off_alpha_attribution_report
from report_generator import generate_daily_report
from rolling_corr_peer_shock_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_rolling_corr_peer_shock_historical_trades,
    build_rolling_corr_peer_shock_paper_sleeve_snapshot,
)


EXPERIMENT_ID = "exp-20260606-026"
STEM = "exp_20260606_026_rolling_corr_peer_shock_daily_forward_wiring"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260606-025"
    / "exp_20260606_025_rolling_corr_peer_shock_shared_adapter.json"
)
ARTIFACT_PATH = ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"


def _rows(
    *,
    base: float,
    normal_return: float,
    shock_day: int,
    shock_return: float,
    days: int = 90,
    volume: float = 1_000_000.0,
    shock_volume: float | None = None,
) -> list[dict[str, Any]]:
    current = date(2026, 1, 1)
    rows = []
    close = base
    while len(rows) < days:
        if current.weekday() < 5:
            idx = len(rows)
            base_ret = normal_return + (((idx % 7) - 3) * 0.0002)
            ret = shock_return if idx == shock_day else base_ret
            close *= 1.0 + ret
            open_ = close / (1.0 + max(ret * 0.55, -0.02))
            low = min(open_, close) * 0.992
            high = max(open_, close) * 1.006
            rows.append(
                {
                    "date": current.isoformat(),
                    "open": round(open_, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": shock_volume if idx == shock_day and shock_volume else volume,
                }
            )
        current += timedelta(days=1)
    return rows


def _fixture_ohlcv() -> dict[str, list[dict[str, Any]]]:
    shock_day = 70
    return {
        "SPY": _rows(
            base=100.0,
            normal_return=0.001,
            shock_day=shock_day,
            shock_return=0.001,
            volume=50_000_000.0,
        ),
        "PEER": _rows(
            base=120.0,
            normal_return=0.002,
            shock_day=shock_day,
            shock_return=0.08,
            volume=1_200_000.0,
            shock_volume=2_800_000.0,
        ),
        "LAG": _rows(
            base=80.0,
            normal_return=0.002,
            shock_day=shock_day,
            shock_return=0.01,
            volume=1_300_000.0,
            shock_volume=1_500_000.0,
        ),
        "CORE": _rows(
            base=60.0,
            normal_return=0.0015,
            shock_day=shock_day,
            shock_return=0.012,
            volume=1_000_000.0,
        ),
    }


def _sector_entries() -> dict[str, dict[str, Any]]:
    return {
        "PEER": {"sector": "Technology", "industry": "Semiconductors", "status": "ok"},
        "LAG": {"sector": "Technology", "industry": "Semiconductors", "status": "ok"},
        "CORE": {"sector": "Technology", "industry": "Software", "status": "ok"},
    }


def _load_source_artifact() -> dict[str, Any]:
    with SOURCE_ARTIFACT.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_forward_wiring() -> dict[str, Any]:
    ohlcv = _fixture_ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]
    core_entries = {signal_day: [{"ticker": "CORE", "entry_signal": "B"}]}

    historical_trades, _audit = build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=core_entries,
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        signal_snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
            as_of=signal_day,
            ohlcv_by_ticker=ohlcv,
            core_entries=core_entries[signal_day],
            sector_entries=_sector_entries(),
            state_path=tmp / "state.json",
            snapshot_log_path=tmp / "snapshots.jsonl",
            persist=True,
        )
        closed_snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
            as_of=exit_day,
            ohlcv_by_ticker=ohlcv,
            core_entries=[],
            sector_entries=_sector_entries(),
            state_path=tmp / "state.json",
            snapshot_log_path=tmp / "snapshots.jsonl",
            persist=True,
        )

    attribution = build_default_off_alpha_attribution_report(
        as_of=signal_day,
        rolling_corr_peer_shock_paper_sleeve=signal_snapshot,
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        default_off_alpha_attribution=attribution,
        rolling_corr_peer_shock_paper_sleeve=signal_snapshot,
    )
    surfaces = {
        row.get("name"): row for row in attribution.get("surfaces") or []
    }
    historical = historical_trades[0]
    closed = closed_snapshot["closed_positions_this_run"][0]
    parity_checks = {
        "historical_trade_count": len(historical_trades),
        "signal_snapshot_candidate_count": signal_snapshot.get("candidate_count"),
        "signal_snapshot_trade_enabled": signal_snapshot.get("trade_enabled"),
        "closed_snapshot_closed_count_today": closed_snapshot.get("closed_count_today"),
        "closed_snapshot_trade_enabled": closed_snapshot.get("trade_enabled"),
        "pnl_matches_historical": closed.get("pnl") == historical.get("pnl"),
        "pnl_pct_matches_historical": closed.get("pnl_pct_net")
        == historical.get("pnl_pct_net"),
        "entry_date_matches_historical": closed.get("entry_date")
        == historical.get("entry_date"),
        "exit_date_matches_historical": closed.get("exit_date")
        == historical.get("exit_date"),
        "attribution_surface_present": "rolling_corr_peer_shock" in surfaces,
        "attribution_trade_enabled": surfaces["rolling_corr_peer_shock"].get(
            "trade_enabled"
        )
        if "rolling_corr_peer_shock" in surfaces
        else None,
        "report_block_present": "ROLLING-CORR PEER-SHOCK PAPER SLEEVE" in report,
        "report_trade_enabled_false": "Trade enabled: False" in report,
        "production_orders_changed": (
            signal_snapshot.get("production_impact") or {}
        ).get("production_orders_changed"),
    }
    passed = all(
        [
            parity_checks["historical_trade_count"] == 1,
            parity_checks["signal_snapshot_candidate_count"] == 1,
            parity_checks["signal_snapshot_trade_enabled"] is False,
            parity_checks["closed_snapshot_closed_count_today"] == 1,
            parity_checks["closed_snapshot_trade_enabled"] is False,
            parity_checks["pnl_matches_historical"],
            parity_checks["pnl_pct_matches_historical"],
            parity_checks["entry_date_matches_historical"],
            parity_checks["exit_date_matches_historical"],
            parity_checks["attribution_surface_present"],
            parity_checks["attribution_trade_enabled"] is False,
            parity_checks["report_block_present"],
            parity_checks["report_trade_enabled_false"],
            parity_checks["production_orders_changed"] is False,
        ]
    )
    return {
        "passed": passed,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "parity_checks": parity_checks,
        "fixture_closed_trade": {
            "ticker": closed.get("ticker"),
            "entry_date": closed.get("entry_date"),
            "exit_date": closed.get("exit_date"),
            "pnl": closed.get("pnl"),
            "historical_pnl": historical.get("pnl"),
        },
    }


def _artifact() -> dict[str, Any]:
    source = _load_source_artifact()
    delta = source["delta_metrics"]
    forward = _validate_forward_wiring()
    accepted = bool(source.get("gate4", {}).get("passed")) and forward["passed"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "default_off_forward_adapter_wiring",
        "changed_variable": "rolling_corr_peer_shock_daily_default_off_observation_wiring_v1",
        "hypothesis": (
            "The accepted rolling-correlation peer-shock alpha should now be wired "
            "into daily default-off observation so it can collect forward closed "
            "replacement-value rows using the same helper semantics that passed "
            "the three-window replay."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/free-OHLCV relation alpha: use same-day core A/B "
                "flow to identify lagging correlated peers after a peer shock, then "
                "collect daily default-off paper outcomes without live-order impact."
            ),
            "2_history_check": {
                "exp-20260606-018": (
                    "Broader rolling-correlation peer-shock lag failed Gate 4; old_thin "
                    "and drawdown were not acceptable."
                ),
                "exp-20260606-024": (
                    "Core-flow + positive candidate reaction fixed the mechanism: "
                    "aggregate EV +0.3845, PnL +6107.66, 48 trades, 3/3 windows improved."
                ),
                "exp-20260606-025": (
                    "Accepted shared helper reproduced exp024 exactly, but daily "
                    "run/reporting were not wired."
                ),
            },
            "3_single_causal_variable": (
                "rolling_corr_peer_shock_daily_default_off_observation_wiring_v1"
            ),
            "4_acceptance_standard": (
                "Preserve exp025's canonical three-window before/after evidence; "
                "daily wiring must be default-off, trade_enabled=false, share the "
                "historical fill/exit semantics, and alter no orders/ranking/sizing/exits."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_026_rolling_corr_peer_shock_daily_forward_wiring.py"
            ),
        },
        "backtest_protocol": source.get("backtest_protocol"),
        "source_three_window_artifact": str(
            SOURCE_ARTIFACT.relative_to(ROOT).as_posix()
        ),
        "before_metrics": source.get("before_metrics"),
        "after_metrics": source.get("after_metrics"),
        "delta_metrics": delta,
        "gate1": {
            "passed": True,
            "baseline_artifact": (
                "data/experiments/exp-20260606-025/"
                "exp_20260606_025_rolling_corr_peer_shock_shared_adapter.json#before_metrics"
            ),
            "standard_windows": list((source.get("backtest_protocol") or {}).get("windows") or {}),
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "daily broad-market OHLCV rows from free data",
                "SPY OHLCV",
                "broad_market_candidate_universe sector/status entries",
                "same-day selected core A/B entries from plan_entry_candidates",
                "paper state pending/open/closed entries",
            ],
            "open_positions_field_check": source.get("gate2", {}).get("open_positions"),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "minimum_core_survival_rate": source.get("gate3", {}).get(
                "minimum_core_survival_rate"
            ),
            "note": (
                "No live/core filter is added. Daily sleeve candidates are default-off "
                "paper rows built after core entry planning."
            ),
        },
        "gate4": {
            "passed": accepted,
            "three_window_evidence_from_exp025": True,
            "aggregate_ev_delta": delta["aggregate"]["expected_value_score_delta_sum"],
            "aggregate_pnl_delta": delta["aggregate"]["total_pnl_delta_sum"],
            "windows_ev_improved": delta["aggregate"]["windows_ev_improved"],
            "windows_ev_regressed": delta["aggregate"]["windows_ev_regressed"],
            "windows_pnl_improved": delta["aggregate"]["windows_pnl_improved"],
            "windows_pnl_regressed": delta["aggregate"]["windows_pnl_regressed"],
            "target_trade_count": delta["aggregate"]["target_trade_count_sum"],
            "max_drawdown_worse": delta["aggregate"]["max_drawdown_delta_max"],
            "forward_wiring_validation_passed": forward["passed"],
            "decision": (
                "accepted_daily_default_off_forward_wiring"
                if accepted
                else "rejected_daily_default_off_forward_wiring"
            ),
        },
        "forward_wiring_validation": forward,
        "production_impact": {
            "run_adapter_changed": True,
            "report_surface_changed": True,
            "default_off_alpha_attribution_changed": True,
            "daily_paper_state_lifecycle_changed": True,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "uses_free_ohlcv_only": True,
        },
        "interpretation": (
            "Accepted. The historical alpha evidence remains the exp025 shared-helper "
            "three-window result, and this run makes the same helper visible in the "
            "daily default-off path with a tested pending/open/closed paper lifecycle. "
            "It remains observe-only; activation still requires forward closed rows "
            "and a separate Gate 1-4 trade adapter."
        ),
        "anti_js": "No JavaScript was used.",
        "verification_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_rolling_corr_peer_shock_paper_sleeve.py quant\\test_default_off_alpha_attribution.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260606_026_rolling_corr_peer_shock_daily_forward_wiring.py",
        ],
        "related_files": [
            "quant/rolling_corr_peer_shock_paper_sleeve.py",
            "quant/run.py",
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "quant/test_rolling_corr_peer_shock_paper_sleeve.py",
            "quant/test_default_off_alpha_attribution.py",
            "quant/experiments/exp_20260606_026_rolling_corr_peer_shock_daily_forward_wiring.py",
            "docs/production_backtest_parity.md",
            "docs/data_edge_context_layers.md",
        ],
    }


def main() -> None:
    payload = _artifact()
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    ARTIFACT_PATH.write_text(text + "\n", encoding="utf-8")
    LOG_PATH.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(ARTIFACT_PATH), "status": payload["status"]}, indent=2))
    if payload["status"] != "accepted":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
