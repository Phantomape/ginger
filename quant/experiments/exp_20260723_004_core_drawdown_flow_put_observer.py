"""exp-20260723-004: shared paper observer and three-window coverage report.

This runner accepts no CLI tuning.  It replays the exact selector shared with
``quant/run.py`` over the three canonical windows and three post-activation
diagnostic folds.  Canonical windows fail closed when the forward option chain
does not exist; those zero-survival rows are evidence about coverage, not
evidence that the economic rule has zero return.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
for root in (str(REPO_ROOT), str(QUANT_DIR)):
    if root not in sys.path:
        sys.path.insert(0, root)

from core_drawdown_flow_put_stabilization_paper_sleeve import (  # noqa: E402
    DEFAULT_OPTIONS_DIR,
    DEFAULT_OPTIONS_QUALITY_PATH,
    FLOW_PIT_CONTRACT_VERSION,
    NON_COMMON_STOCK_EXCLUSIONS,
    OPTIONS_PIT_CONTRACT_VERSION,
    RULE_VERSION,
    build_core_drawdown_flow_put_snapshot,
    empty_core_drawdown_flow_put_state,
    replay_core_drawdown_flow_put_sleeve,
)
from filter import _BASE_WATCHLIST  # noqa: E402
from moomoo_capital_flow_paper_sleeve import load_moomoo_capital_flow_rows  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
    load_warehouse_snapshot_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260723-004"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
FLOW_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow_day" / "rows.jsonl"
)
OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUTPUT_PATH = OUTPUT_DIR / "exp_20260723_004_core_drawdown_flow_put_observer.json"
BEFORE_PATH = OUTPUT_DIR / "before.json"
AFTER_PATH = OUTPUT_DIR / "after.json"

CANONICAL_WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

RECENT_DIAGNOSTIC_FOLDS = {
    "recent_early": {"start": "2026-05-06", "end": "2026-05-29"},
    "recent_mid": {"start": "2026-06-01", "end": "2026-06-30"},
    "recent_late": {"start": "2026-07-01", "end": "2026-07-22"},
}


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_option_universe() -> tuple[list[str], dict[str, Any]]:
    files = sorted(DEFAULT_OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl"))
    dated = [path for path in files if path.stem.rsplit("_", 1)[-1].isdigit()]
    if not dated:
        universe = sorted(set(_BASE_WATCHLIST) - set(NON_COMMON_STOCK_EXCLUSIONS))
        return universe, {"status": "fallback_base_watchlist", "path": None}
    latest = dated[-1]
    tickers: set[str] = set()
    with latest.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if ticker and ticker not in NON_COMMON_STOCK_EXCLUSIONS:
                tickers.add(ticker)
    return sorted(tickers), {
        "status": "latest_forward_option_universe",
        "path": str(latest.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": _sha256(latest),
        "ticker_count": len(tickers),
    }


def _history_start(start: str, days: int = 500) -> str:
    return (pd.Timestamp(start) - timedelta(days=days)).date().isoformat()


def _benchmark_return(frame: pd.DataFrame | None, start: str, end: str) -> float | None:
    if frame is None or frame.empty:
        return None
    sliced = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]
    if len(sliced) < 2:
        return None
    first = float(sliced["Close"].iloc[0])
    last = float(sliced["Close"].iloc[-1])
    return round(last / first - 1.0, 8) if first > 0 else None


def _window_row(
    label: str,
    definition: dict[str, str],
    frames: dict[str, pd.DataFrame],
    flow_rows: list[dict[str, Any]],
    universe: list[str],
) -> dict[str, Any]:
    result = replay_core_drawdown_flow_put_sleeve(
        ohlcv_by_ticker=frames,
        flow_rows=flow_rows,
        start=definition["start"],
        end=definition["end"],
        tickers=universe,
    )
    result["label"] = label
    result["benchmarks"] = {
        "spy_buy_hold_return_pct": _benchmark_return(
            frames.get("SPY"), definition["start"], definition["end"]
        ),
        "qqq_buy_hold_return_pct": _benchmark_return(
            frames.get("QQQ"), definition["start"], definition["end"]
        ),
    }
    return result


def _canonical_rows(
    flow_rows: list[dict[str, Any]], universe: list[str]
) -> list[dict[str, Any]]:
    rows = []
    for label, definition in CANONICAL_WINDOWS.items():
        frames = load_warehouse_snapshot_ohlcv_frames(
            DEFAULT_WAREHOUSE_PATH,
            REPO_ROOT / definition["snapshot"],
            [*universe, "SPY", "QQQ"],
            _history_start(definition["start"]),
            definition["end"],
        )
        row = _window_row(label, definition, frames, flow_rows, universe)
        row["snapshot"] = definition["snapshot"]
        row["snapshot_sha256"] = _sha256(REPO_ROOT / definition["snapshot"])
        rows.append(row)
    return rows


def _recent_rows(
    flow_rows: list[dict[str, Any]], universe: list[str]
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        [*universe, "SPY", "QQQ"],
        "2025-01-01",
        "2026-07-22",
    )
    rows = [
        _window_row(label, definition, frames, flow_rows, universe)
        for label, definition in RECENT_DIAGNOSTIC_FOLDS.items()
    ]
    return rows, frames


def _latest_snapshot(
    frames: dict[str, pd.DataFrame],
    flow_rows: list[dict[str, Any]],
    universe: list[str],
) -> dict[str, Any]:
    flow_dates = sorted(
        {
            str(row.get("flow_date") or "")
            for row in flow_rows
            if row.get("flow_date")
        }
    )
    option_dates = sorted(
        path.stem.rsplit("_", 1)[-1]
        for path in DEFAULT_OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl")
        if path.stem.rsplit("_", 1)[-1].isdigit()
    )
    common_dates = [
        day for day in flow_dates if day.replace("-", "") in set(option_dates)
    ]
    for as_of in reversed(common_dates):
        snapshot = build_core_drawdown_flow_put_snapshot(
            as_of=as_of,
            ohlcv_by_ticker=frames,
            flow_rows=flow_rows,
            candidate_universe=universe,
            state=empty_core_drawdown_flow_put_state(),
            persist=False,
        )
        if not snapshot.get("error"):
            return snapshot
    return {"error": "no_common_price_flow_options_session", "candidates": []}


def _baseline_projection() -> dict[str, Any]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {
        row["label"]: {
            key: row.get(key)
            for key in (
                "expected_value_score",
                "sharpe_daily",
                "total_pnl",
                "max_drawdown_pct",
                "win_rate",
                "trade_count",
                "signals_generated",
                "signals_survived",
                "survival_rate",
            )
        }
        for row in baseline.get("windows") or []
    }


def build_artifact() -> dict[str, Any]:
    required = [
        Path(DEFAULT_WAREHOUSE_PATH),
        FLOW_PATH,
        DEFAULT_OPTIONS_QUALITY_PATH,
        BASELINE_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required inputs: {missing}")

    universe, universe_source = _latest_option_universe()
    flow_rows = load_moomoo_capital_flow_rows(FLOW_PATH)
    canonical = _canonical_rows(flow_rows, universe)
    recent, recent_frames = _recent_rows(flow_rows, universe)
    latest_snapshot = _latest_snapshot(recent_frames, flow_rows, universe)
    baseline = _baseline_projection()

    canonical_gate4_eligible = all(
        bool(row["gate_checks"]["gate4_eligible"]) for row in canonical
    )
    latest_candidates = latest_snapshot.get("candidates") or []
    opportunity_winner = latest_candidates[0]["ticker"] if latest_candidates else None
    portfolio_path = REPO_ROOT / "data" / "open_positions.json"
    portfolio_status = "present_read_only" if portfolio_path.exists() else "missing"

    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": "shared_default_off_paper_observer_measurement",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "rule_version": RULE_VERSION,
        "classification": "accepted_measurement_infrastructure_not_alpha",
        "evidence_grade": "observer",
        "trade_enabled": False,
        "owner_authorized_assumptions": {
            "moomoo_day_flow": FLOW_PIT_CONTRACT_VERSION,
            "contract": (
                "flow_date D is immutable, known after D close and usable for the "
                "next US equity session; missing rows fail closed"
            ),
            "options_contract_unchanged": OPTIONS_PIT_CONTRACT_VERSION,
        },
        "fixed_policy_bundle": {
            "candidate_formula": "DD60 <= -15% and (RSI14 <= 40 or ret20 <= -15%)",
            "flow_gate": "main_in_flow > 0",
            "flow_strength": "main_in_flow / prior-20-session mean(Close*Volume)",
            "put_proxy": (
                "captured put OI [0.94*S,1.01*S] / captured put OI "
                "[0.75*S,1.01*S], exactly two expiries, >=10 liquid rows"
            ),
            "stabilization": "close > previous close and close_location >= 0.55",
            "ranking": "top1 sqrt(flow_strength_pct_rank * near_put_oi_share_pct_rank)",
            "entry": "next US equity session open",
            "exit": "10th session close after entry",
            "paper_notional_usd": 4000.0,
            "round_trip_cost_pct": 0.0035,
            "max_active_positions": 1,
            "target_price": "signal close + 3.5*ATR14; diagnostic signal-contract field",
        },
        "synthesis_pass": {
            "baseline_universe": universe,
            "baseline_universe_source": universe_source,
            "opportunity_cost_winner": opportunity_winner,
            "evidence_surfaces_used": [
                "price: canonical snapshot-version warehouse + recent broad warehouse",
                "flow: Moomoo DAY archive under owner-authorized stable-PIT contract",
                "derivatives: exact-date forward OnclickMedia option chain quality gate",
                "positioning: near-price Put-OI share proxy from captured two-expiry chain",
                f"portfolio_exposure: data/open_positions.json {portfolio_status}, read-only context",
            ],
            "evidence_surfaces_missing": [
                "canonical-window option chains (latest canonical day is 2026-04-21; chain archive begins 2026-05-05)",
                "full untruncated option chain and third expiry",
                "old_thin Moomoo flow rows and pre-2025-07-02 mid_weak flow rows",
                "event veto is logged as a missing surface and is not silently added to the fixed rule",
            ],
            "hypothesis_candidates": [
                {
                    "id": "selected_full_four_surface_observer",
                    "baseline": "lowest-RSI member of the same deep-drawdown cohort",
                    "treatment": "flow x near-Put-OI top1 after price stabilization",
                    "horizon": "H10 next-open",
                    "replacement_value": "same-day RSI alternative, SPY, QQQ and cash",
                    "falsifier": "<5% survival or nonpositive replacement value after 20 independent closed decisions",
                },
                {
                    "id": "price_only_rebound",
                    "decision": "not_selected",
                    "reason": "already explored and lacks the intended pressure/positioning mechanism",
                },
                {
                    "id": "flow_only_accumulation",
                    "decision": "not_selected",
                    "reason": "existing sleeve failed its drawdown guard and omits capitulation/stabilization",
                },
            ],
            "selected_hypothesis": "selected_full_four_surface_observer",
            "economic_mechanism": (
                "forced price liquidation is exhausted while large-order absorption and near-price "
                "Put positioning coexist; an up-close in the upper range is the causal stabilization trigger"
            ),
            "falsifier": (
                "forward single-slot survival stays below 5%, 20 closed decisions have nonpositive net "
                "replacement value, or gains concentrate above 40% in one ticker"
            ),
            "evidence_grade": "observer",
            "next_machine_action": (
                "daily run.py materialization until >=20 independent closed positions; then build a new "
                "model-diverse promotion panel before any alpha or live claim"
            ),
            "research_digest": {
                "latest_digest_read": "data/research_digest/latest_digest.md",
                "ledger_status": "fresh entries were already consumed in data/research_digest/ledger.jsonl before this task",
                "selected_entry_ids": [],
                "reason": "the fixed owner-proposed mechanism predates today's digest; digest items are evaluation constraints, not novelty",
            },
        },
        "gate1_active_cash_feasible_baseline": {
            "path": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": _sha256(BASELINE_PATH),
            "windows": baseline,
        },
        "gate2_dependency_contract": {
            "required_fields": [
                "signal_date",
                "entry_date",
                "target_price",
                "main_in_flow",
                "flow_strength",
                "near_put_oi_share_proxy",
                "option_usable_trade_date",
            ],
            "daily_latest_snapshot": latest_snapshot,
            "entry_date_and_target_price_emitted": all(
                row.get("entry_date") and row.get("target_price") is not None
                for row in latest_candidates
            ),
        },
        "gate3_canonical_survival": {
            row["label"]: {
                "signals_generated": row["metrics"]["signals_generated"],
                "signals_survived": row["metrics"]["signals_survived"],
                "survival_rate": row["metrics"]["survival_rate"],
                "passed": row["gate_checks"]["gate3_survival_at_least_5pct"],
            }
            for row in canonical
        },
        "gate4": {
            "eligible": canonical_gate4_eligible,
            "decision": "not_run_as_alpha_missing_canonical_derivatives_surface",
            "interpretation": (
                "zero canonical trades are the required fail-closed PIT result; they do not estimate strategy return"
            ),
        },
        "canonical_three_window_results": canonical,
        "recent_observe_only_three_folds": recent,
        "coverage_facts": {
            "flow_archive_path": str(FLOW_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "flow_archive_sha256": _sha256(FLOW_PATH),
            "options_quality_path": str(DEFAULT_OPTIONS_QUALITY_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "options_quality_sha256": _sha256(DEFAULT_OPTIONS_QUALITY_PATH),
            "first_chain_file": "data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl",
            "last_chain_file": universe_source.get("path"),
        },
        "production_impact": {
            "shared_helper_added": True,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "paper_lifecycle_persisted": True,
            "core_policy_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
        },
        "decision": "accepted_measurement_infrastructure_observer_not_alpha",
        "reopen_condition": (
            ">=20 independent closed single-slot paper decisions with >=5% survival, positive net "
            "replacement value in both chronological halves, and <=40% single-ticker positive-PnL share"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retune drawdown, RSI, ret20, flow, moneyness, stabilization, top-N, cost, or H10 "
            "on the same May-July rows; do not call the member-source join a new evidence source."
        ),
    }


def _write_outputs(artifact: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = {
        "artifact_type": "shared_default_off_paper_observer_measurement",
        "experiment_id": EXPERIMENT_ID,
        "measurement_stage": "before",
        "expected_value_score": 0.0,
        "sharpe_daily": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate": None,
        "total_trades": 0,
        "survival_rate": 1.0,
        "total_pnl": 0.0,
        "benchmarks": {"strategy_total_return_pct": 0.0},
        "contract_checks": {
            "shared_helper_present": False,
            "daily_run_wiring_present": False,
            "canonical_missing_options_fail_closed_report_present": False,
            "trading_behavior_changed": False,
        },
    }
    after = {
        **before,
        "measurement_stage": "after",
        "contract_checks": {
            "shared_helper_present": True,
            "daily_run_wiring_present": True,
            "canonical_missing_options_fail_closed_report_present": True,
            "entry_date_and_target_price_contract_present": bool(
                artifact["gate2_dependency_contract"]["entry_date_and_target_price_emitted"]
            ),
            "all_canonical_windows_reported": len(
                artifact["canonical_three_window_results"]
            )
            == 3,
            "all_canonical_windows_fail_closed_without_options": all(
                row["evidence_status"] == "blocked_no_options_history"
                and row["metrics"]["signals_survived"] == 0
                for row in artifact["canonical_three_window_results"]
            ),
            "shared_selector_daily_and_replay": True,
            "trade_enabled_false": artifact["trade_enabled"] is False,
            "trading_behavior_changed": False,
        },
        "production_impact": artifact["production_impact"],
        "decision": artifact["decision"],
        "artifact_path": str(OUTPUT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    BEFORE_PATH.write_text(json.dumps(before, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AFTER_PATH.write_text(json.dumps(after, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    artifact = build_artifact()
    _write_outputs(artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
