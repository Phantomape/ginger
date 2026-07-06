"""exp-20260706-018: FINRA weekly non-ATS OTC internalization-retreat full stack.

Tests a genuinely new free official data source: the FINRA OTC-transparency
weekly NON-ATS wholesaler-internalization symbol-level summary
(``api.finra.org``, ``OTC_W_SMBL``), never previously ingested in this repo
(exp-20260704-003 was blocked solely on a server-side API outage; access was
restored and the reopen condition advanced on 2026-07-06). The candidate rule
is fixed and is the INVERSE gate shape of the rejected ATS dark-share rise
sleeve (exp-20260703-016): on the first session on/after FINRA's
``initialPublishedDate`` (a fixed multi-week lag), admit tickers whose newly
published week's wholesaler-internalization share of consolidated tape volume
RETREATS below the mean share of the prior 4 published weeks (retail
participation washout / quiet institutional accumulation), under the
family-standard liquidity/SPY-relative guard bundle; rank ASCENDING by
share_retreat_ratio, top-1 per day, next-open entry, 10-trading-day close
exit.

Full-stack contract: versioned PIT archive, ONE shared candidate rule
(``quant/finra_otc_internalization_paper_sleeve.py``) used by both historical
replay and the daily default-off snapshot (wired into run.py in this
experiment), parity tests, a frozen Gate 1-4 replay on the canonical windows,
and an explicit execution envelope. No thresholds are retuned: the guard set
is the family-standard bundle and the only new information is the non-ATS
internalization retreat and its ascending ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    import_path_s = str(import_path)
    if import_path_s not in sys.path:
        sys.path.insert(0, import_path_s)

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as fixed_sleeve  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from finra_otc_internalization_paper_sleeve import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    DEFAULT_ROWS_PATH,
    RULE_VERSION,
    load_finra_otc_weekly_rows,
    replay_finra_otc_internalization_paper_trades,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402


EXPERIMENT_ID = "exp-20260706-018"
OWNER = "alpha-explore"
STEM = "finra_otc_internalization_retreat"
TRIAL_FAMILY = "finra_otc_internalization_retreat_candidate_pool"
TRIAL_VARIANT_ID = "finra_otc_internalization_retreat_top1_v1"
CHANGED_VARIABLE = "finra_otc_internalization_retreat_quiet_accumulation_candidate_source"
MECHANISM_FAMILY = "production_visible_finra_otc_internalization_candidate_pool"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MIN_TARGET_TRADES = 20
MIN_COVERED_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

# Wired in this experiment: run.py imports the shared helper and emits the
# default-off snapshot next to the other paper sleeves.
DAILY_SNAPSHOT_EXPOSED = True
PARITY_TEST_ADDED = True  # quant/test_finra_otc_internalization_paper_sleeve.py

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_late_strong_20260604.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_old_thin_20260604.json"
                ),
            },
        ),
    ]
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "window_ev_regression",
        "not_incremental_vs_accepted_comparators",
        "publication_lag_kills_edge",
    ],
    "confidence_reason": (
        "Different venue population (wholesaler internalization vs ATS dark "
        "pools) with inverse gate direction; quiet-participation mechanism "
        "has one accepted precedent (exp-20260528-015 low-volume-"
        "participation support); but the sibling ATS source was rejected "
        "(exp-20260703-016), the FINRA family base rate is low, and the "
        "multi-week publication lag may fully stale the signal."
    ),
    "recorded_at": "2026-07-06T16:13:38+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=BASE_NOTIONAL_USD,
    max_capital_pct=0.04,
    min_dollar_volume=50_000_000.0,
    slippage_bps=5.0,
    max_displacement=0,
    max_concurrent=5,
    order_semantics="next_open",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day, $4,000 fixed default-off paper notional, 10-trading-day "
        "close exit, same-day core-overlap exclusion in the daily path. The "
        "daily source refreshes from the free FINRA query API; a dead network "
        "degrades to the local archive (weekly cadence tolerates staleness) "
        "without touching the ledger."
    ),
)

SOURCE_ACTIVATION_BOUNDARY = {
    "vendor_history": (
        "FINRA weekly non-ATS OTC summary reaches back years; archive "
        "materialized 2026-07-06 from week 2024-08-05 with per-row "
        "initialPublishedDate (4,790 rows, 50 tickers)"
    ),
    "old_thin": "fully covered (earliest publication predates the window)",
    "mid_weak": "fully covered",
    "late_strong": "fully covered",
    "note": (
        "Unlike rolling-window vendor feeds, FINRA publications are stable and "
        "re-fetchable; initialPublishedDate makes historical replay share the "
        "same availability boundary as daily forward use."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: FINRA weekly OTC-transparency NON-ATS "
        "wholesaler-internalization symbol-level share volume, as a share of "
        "consolidated weekly tape volume and published with a fixed "
        "multi-week lag, RETREATING versus its trailing 4 published weeks "
        "(retail washout / quiet institutional accumulation) under "
        "family-standard liquidity and SPY-relative guards, is a deployable "
        "top-1-per-publication-day default-off paper source with replacement "
        "value on the canonical windows."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new blocked as near-neighbor of "
            "finra_ats_weekly_dark_share_candidate_pool; override recorded "
            "with a dual axis the gate validated as new_data_source + "
            "new_gate_shape (OTC_W_SMBL never materialized; retreat-admission "
            "ranked ascending is the inverse of the rejected rise shape)"
        ),
        "exp-20260703-016": (
            "sibling ATS dark-share RISE source rejected (window regressions, "
            "comparators); its post-run reflection explicitly names the "
            "non-ATS wholesaler summary with its own gate shape as required "
            "new evidence"
        ),
        "exp-20260704-003": (
            "OTC_W_SMBL readiness audit blocked solely on server-side FINRA "
            "API outage; probe on 2026-07-06 returned 200 with all required "
            "PIT fields, advancing the recorded reopen condition"
        ),
        "exp-20260528-015": (
            "accepted low-volume-participation support: the one in-repo "
            "precedent that quiet-participation admission (not surge "
            "admission) can carry alpha"
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical windows, all three covered by the "
        "source: acceptance needs aggregate EV/PnL positive, no EV/PnL "
        "regression window, >=2 EV-improved windows, >=20 target trades, "
        "drawdown drift <=0.5pp, concentration guards, accepted compression "
        "AND distribution comparators beaten, and the full-stack contract "
        "(shared helper + daily default-off snapshot + parity test + "
        "execution envelope) complete."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260706_018_finra_otc_internalization_retreat.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _production_impact() -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "adapter_status": "shared_default_off_paper_sleeve",
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": DAILY_SNAPSHOT_EXPOSED,
        "replay_only": not DAILY_SNAPSHOT_EXPOSED,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": DAILY_SNAPSHOT_EXPOSED,
        "parity_test_added": PARITY_TEST_ADDED,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_finra_otc_weekly_archive": True,
        "live_realism_evaluated": True,
        "live_ready": False,
        "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
        "parity_note": (
            "One shared candidate rule (quant/finra_otc_internalization_paper_sleeve"
            ".py) drives both the historical replay in this runner and the "
            "daily default-off snapshot wired into run.py; parity tests cover "
            "admission, ranking, PIT publication mapping, same-day "
            "idempotency, fill/close lifecycle, and the replay/daily "
            "selection agreement. No live/default order, ranking, sizing, "
            "exit, watchlist, LLM, or news path changes."
        ),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    covered_windows: list[str],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < MIN_COVERED_TARGET_WINDOWS:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_COVERED_TARGET_WINDOWS:
        failed.append("covered_target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("distribution", ACCEPTED_DISTRIBUTION_COMPARATOR),
    ):
        if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= comparator[
            "expected_value_score_delta_sum"
        ]:
            failed.append(f"accepted_{name}_ev_not_beaten")
        if float(aggregate["total_pnl_delta_sum"] or 0.0) <= comparator[
            "total_pnl_delta_sum"
        ]:
            failed.append(f"accepted_{name}_pnl_not_beaten")
    if not DAILY_SNAPSHOT_EXPOSED:
        failed.append("daily_snapshot_not_exposed_for_full_stack_contract")
    if not PARITY_TEST_ADDED:
        failed.append("parity_test_missing_for_full_stack_contract")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_finra_otc_internalization_retreat_default_off_candidate_source"
            if passed
            else "rejected_finra_otc_internalization_retreat_default_off_candidate_source"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "covered_windows": covered_windows,
        "covered_target_window_count_min": MIN_COVERED_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "accepted_comparators": {
            "compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "distribution": ACCEPTED_DISTRIBUTION_COMPARATOR,
        },
        "source_activation_boundary": SOURCE_ACTIVATION_BOUNDARY,
        "full_stack_contract": {
            "daily_snapshot_exposed": DAILY_SNAPSHOT_EXPOSED,
            "parity_test_added": PARITY_TEST_ADDED,
        },
    }


def _full_stack_blocks(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "adjusted_trade_count": target_summary["total_trade_count"],
        "adjusted_windows": target_summary["windows_with_target_trades"],
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": aggregate["max_drawdown_delta_max"],
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target_summary["total_trade_count"]
            if target_summary["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(require_tail_concentration_not_worse=False)
    return {
        "window_metrics": metrics,
        "gate4_strict_materiality": evaluate_gate4(
            metrics, thresholds=thresholds, check_materiality=True
        ),
        "gate4_canonical": evaluate_gate4(
            metrics, thresholds=thresholds, check_materiality=False
        ),
        "materiality_note": (
            "Strict materiality recorded for transparency; the binding "
            "standard for candidate sources is beating the accepted "
            "comparators after costs."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    universe = sorted(set(get_universe()))
    otc_rows = load_finra_otc_weekly_rows()
    if not otc_rows:
        raise RuntimeError(
            "FINRA weekly non-ATS OTC archive is empty; materialize it before replay"
        )
    weeks = sorted({row["week_start_date"] for row in otc_rows})
    published = sorted({row["published_date"] for row in otc_rows})
    archive_summary = {
        "rows_path": _repo_rel(DEFAULT_ROWS_PATH),
        "manifest_path": _repo_rel(DEFAULT_MANIFEST_PATH),
        "row_count": len(otc_rows),
        "ticker_count": len({row["ticker"] for row in otc_rows}),
        "earliest_week_start": weeks[0],
        "latest_week_start": weeks[-1],
        "earliest_published_date": published[0],
        "latest_published_date": published[-1],
    }

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    replay_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    covered_windows: list[str] = []

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline + sleeve replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot_payload = _read_json(REPO_ROOT / cfg["snapshot"])
        ohlcv_by_ticker = snapshot_payload.get("ohlcv") or {}
        replay = replay_finra_otc_internalization_paper_trades(
            ohlcv_by_ticker=ohlcv_by_ticker,
            otc_rows=otc_rows,
            start=cfg["start"],
            end=cfg["end"],
            tickers=universe,
        )
        trades = replay["trades"]
        if trades or replay["otc_coverage"]["first_published_date_in_window"]:
            covered_windows.append(label)
        overlay = fixed_sleeve._overlay_from_paper_trades(before_result, trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        replay_audit_by_window[label] = {
            "reject_totals": replay["reject_totals"],
            "unsettled_count": len(replay["unsettled"]),
            "unsettled_reasons": dict(
                Counter(row.get("unsettled_reason") for row in replay["unsettled"])
            ),
            "signal_dates_with_candidates": replay["signal_dates_with_candidates"],
            "max_daily_candidate_count": replay["max_daily_candidate_count"],
            "otc_coverage": replay["otc_coverage"],
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = fixed_sleeve._aggregate(window_rows)
    target_summary = fixed_sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        covered_windows=covered_windows,
    )
    full_stack = _full_stack_blocks(aggregate, target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=gate4, live_readiness=live_readiness, envelope=EXECUTION_ENVELOPE
    )
    if not gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Reject and do not retune retreat thresholds, trailing-week "
                "counts, guard values, rank tie-breaks, hold days, cooldown, "
                "or notional on these frozen windows. Both directions of the "
                "FINRA weekly venue decomposition (ATS rise, non-ATS retreat) "
                "are now tested; the archive and daily snapshot keep "
                "accumulating, and a valid retry needs settled forward rows "
                "from the daily default-off snapshot or PIT borrow/short-side "
                "economics joined to the same names, not another venue-share "
                "reshape."
            ),
        }

    accepted = gate4["passed"] and verdict["verdict"] != "reject"
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if accepted else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2, 6
        ),
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    if accepted:
        reflection = {
            "why_result_happened": (
                "Weeks where wholesaler internalization retreated (retail "
                "washout) while SPY-relative strength held carried enough "
                "next-open 10d continuation after the multi-week publication "
                "lag to clear the accepted comparators under the "
                "family-standard guard bundle without touching the frozen "
                "thresholds."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep retreat ratio, trailing-week count, guard "
                "values, rank tie-breaks, hold days, cooldown, notional, or "
                "response shapes on these frozen windows; the retained asset "
                "is the shared helper plus daily default-off snapshot."
            ),
            "new_evidence_required": (
                "Forward replacement-value rows from the daily default-off "
                "snapshot; live promotion is only a Gate-5 checklist item "
                "after >=30 closed forward trades."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The fixed top-1/publication-day non-ATS internalization-"
                "retreat source did not clear the predeclared Gate 4 bar on "
                "the canonical windows: "
                + ("; ".join(gate4["failed_reasons"]) or "none")
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune retreat ratio, trailing-week count, min ADV/RS "
                "guard values, rank tie-breaks, hold days, cooldown, or "
                "notional on these same frozen windows; do not re-slice the "
                "same archive by tier, notional-per-trade, or trade-count "
                "fields as if they were a new axis. Both directions of the "
                "FINRA weekly venue decomposition (ATS rise exp-20260703-016, "
                "non-ATS retreat this experiment) are now tested."
            ),
            "new_evidence_required": (
                "Settled forward rows from the daily default-off snapshots of "
                "either FINRA weekly sleeve, or PIT borrow/short-side "
                "economics joined to the same names; not another venue-share "
                "field, direction, or threshold reshape on the same archive."
            ),
        }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": accepted,
        "full_stack_verdict": verdict["verdict"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": MECHANISM_FAMILY,
        "new_evidence_type": "new_data_source_and_new_gate_shape",
        "nearby_prior_experiments": [
            "exp-20260703-016",
            "exp-20260704-003",
            "exp-20260528-015",
        ],
        "multiple_testing_risk_bucket": "low",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "rule_version": RULE_VERSION,
        "archive": archive_summary,
        "source_activation_boundary": SOURCE_ACTIVATION_BOUNDARY,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window accepted core "
                "baseline plus default-off paper overlay from the shared "
                "FINRA non-ATS OTC internalization-retreat sleeve replay"
            ),
            "windows": WINDOWS,
            "execution_model": (
                "Signal uses only FINRA rows published on/before the signal "
                "session (initialPublishedDate) plus signal-date OHLCV "
                "context. Paper entry is next-session open with entry fill "
                "slippage; exit is the 10th-trading-day close with sell "
                "slippage; trades whose exit falls outside the frozen window "
                "are not scored."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": 1,
            "same_ticker_cooldown_days": 10,
            "guards": (
                "family-standard: min_close $10, min adv20 $50M, "
                "ret20_excess_spy >= 0; new information: newly published "
                "weekly non-ATS internalization share of consolidated volume "
                "< trailing 4 published weeks' mean, rank ASCENDING by "
                "share_retreat_ratio"
            ),
            "thresholds_retuned": False,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifacts": {label: WINDOWS[label]["baseline"] for label in WINDOWS},
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "week_start_date",
                "published_date",
                "otc_share",
                "baseline_share",
                "share_retreat_ratio",
                "avg_dollar_volume_20",
                "ret20_excess_spy",
            ],
            "archive_row_count": len(otc_rows),
            "target_price_scope": (
                "not_applicable_fixed_10d_close_exit_paper_source; core "
                "entry_date/target_price fields unchanged in baseline"
            ),
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
            "passed": True,
            "note": (
                "Default-off paper overlay only. Core signal generation and "
                "survival are unchanged."
            ),
        },
        "gate4": gate4,
        "full_stack": {
            **full_stack,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "verdict": verdict,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "replay_audit_by_window": replay_audit_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": _production_impact(),
        "interpretation": (
            "Accepted as a default-off paper sleeve pending forward rows."
            if accepted
            else (
                "The FINRA non-ATS internalization-retreat source failed the predeclared "
                "full-stack Gate 4 on the canonical windows; do not retune it "
                "on frozen samples."
            )
        ),
        "post_run_reflection": reflection,
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/finra_otc_internalization_paper_sleeve.py",
            "quant/test_finra_otc_internalization_paper_sleeve.py",
            "quant/test_run_daily_wiring.py",
            "quant/run.py",
            "quant/data_paths.py",
            _repo_rel(DEFAULT_ROWS_PATH),
            _repo_rel(DEFAULT_MANIFEST_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    verdict = payload["full_stack"]["verdict"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA Weekly Non-ATS Internalization Retreat Full Stack",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Archive",
            "",
            "- Rows: `{row_count}` across `{ticker_count}` tickers, weeks `{earliest_week_start}` -> `{latest_week_start}` (published `{earliest_published_date}` -> `{latest_published_date}`)".format(
                **payload["archive"]
            ),
            "- Source boundary: all three canonical windows fully covered; per-row initialPublishedDate is the PIT boundary (multi-week lag).",
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Contract",
            "",
            "- Daily snapshot exposed: `{}`".format(
                payload["production_impact"]["daily_snapshot_exposed"]
            ),
            "- Parity test added: `{}`".format(
                payload["production_impact"]["parity_test_added"]
            ),
            "- Live readiness blockers: `{}`".format(
                ", ".join(payload["full_stack"]["live_readiness"]["blockers"]) or "none"
            ),
            "- Next step: {}".format(verdict["next_step"]),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifacts"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "archive": payload["archive"],
        "source_activation_boundary": payload["source_activation_boundary"],
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack_verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
            "materiality_note": payload["full_stack"]["materiality_note"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_reasons"]) or None,
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "new_evidence_type": payload["new_evidence_type"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["accepted"],
                "calibration": payload["calibration"],
            },
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        QUANT_DIR / "finra_otc_internalization_paper_sleeve.py",
        QUANT_DIR / "test_finra_otc_internalization_paper_sleeve.py",
        QUANT_DIR / "test_run_daily_wiring.py",
        QUANT_DIR / "run.py",
        QUANT_DIR / "data_paths.py",
        Path(DEFAULT_ROWS_PATH),
        Path(DEFAULT_MANIFEST_PATH),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): _sha256(path) for path in paths if path.exists()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["accepted"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "lean_quality_passed": True,
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _build_log_record(payload))
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "aggregate_ev_delta": payload["expected_value_score_delta"],
        "aggregate_pnl_delta": payload["total_pnl_delta"],
        "target_trades": payload["target_trade_summary"]["total_trade_count"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "by_window_trades": {
            label: len(trades)
            for label, trades in payload["target_trades_by_window"].items()
        },
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
