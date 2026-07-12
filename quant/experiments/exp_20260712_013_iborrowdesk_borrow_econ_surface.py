"""exp-20260712-013: iBorrowDesk PIT borrow-economics surface + avoidance read.

Observer first-build packaged per AGENTS.md §2.4 (collection surface + daily
wiring in one ID): materialize the rolling ~1y iBorrowDesk (IBKR mirror) daily
borrow fee / rebate / availability history for the accepted-replay warehouse
universe, wire a sharded daily refresh into run.py, extend fingerprint keyword
coverage, and take one fixed observed-only avoidance read on the covered
windows. The source erodes daily, so materialization is time-critical.

Fixed observed-only policy (declared before looking at outcomes):

- Stress flag on session t: ``fee(t) >= 1.0`` OR (``fee(t) - fee(t-5) >= 0.25``
  AND ``available(t) <= 0.7 * available(t-5)``).
- Event = transition into stressed (not stressed at t-1) with a 10-session
  per-ticker cooldown; entry next open, exit 10th-session close, excess vs SPY
  over the same interval; comparator = same-date equal-weight universe mean.
- Coverage: late_strong (2025-10-23..2026-04-21, full) and the covered tail of
  mid_weak (2025-07-14..2025-10-22, partial). old_thin is not covered.
- Verdict floors: fewer than 20 events across covered windows -> observed_only
  (thin); >= 20 events with mean delta <= -50bp and same sign in both covered
  windows -> observed-only lead; otherwise observed_only_rejected for the
  avoidance read. No production, order, ranking, sizing, exit, or LLM change;
  the durable archive + refresh wiring is retained in every branch.

Usage:
  python exp_20260712_013_iborrowdesk_borrow_econ_surface.py materialize
  python exp_20260712_013_iborrowdesk_borrow_econ_surface.py analyze
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import iborrowdesk_data_source as ibd  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402
from ohlcv_warehouse_refresh import build_default_refresh_universe  # noqa: E402

EXPERIMENT_ID = "exp-20260712-013"
OWNER = "alpha-scheduled-20260712"
SLUG = "iborrowdesk_borrow_econ_surface"
RUNNER = f"quant/experiments/exp_20260712_013_{SLUG}.py"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "PIT borrow-fee/availability economics from the free iBorrowDesk (IBKR "
    "shortable-stock mirror) daily history: liquid warehouse-universe names "
    "with elevated or rising indicative borrow fee or shrinking lendable "
    "availability underperform SPY over the next 10 sessions, giving the "
    "accepted candidate stack a new avoidance/tilt context and the first "
    "universe-wide PIT borrow-economics surface (prior ORTEX sidecar was "
    "single-ticker AAPL)."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "observer_first_build_plus_observed_only_read"
MECHANISM_FAMILY = "iborrowdesk_borrow_economics_surface"
TRIAL_FAMILY = "iborrowdesk_borrow_fee_availability_avoidance_context"
TRIAL_VARIANT_ID = "iborrowdesk_stress_transition_avoidance_v1"
CHANGED_VARIABLE = "iborrowdesk_borrow_fee_availability_avoidance_context_v1"
NEW_EVIDENCE_TYPE = "new_data_source_iborrowdesk_ibkr_borrow_economics"
NEW_EVIDENCE_AXIS = (
    "New data source: iBorrowDesk mirror of the IBKR shortable-stock feed with "
    "~1 rolling year of per-ticker daily borrow fee, rebate, and availability. "
    "No prior family had universe-wide PIT borrow economics; ORTEX covered one "
    "AAPL sidecar and FINRA short interest is bi-monthly without fee/supply."
)
NEARBY_PRIORS = ["exp-20260628-004", "exp-20260627-023", "exp-20260625-018"]
CAUSAL_COMPONENTS = [
    "iBorrowDesk daily fee/rebate/available history",
    "resumable throttling-safe archive fetcher",
    "warehouse fresh-universe scope",
    "daily refresh wiring",
    "observed-only 10-session replacement-value read on covered windows",
]
PREDICTION = {
    "success_probability": 0.2,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "flat_gc_fee_no_cross_sectional_variance",
        "host_throttled_fetch",
        "thin_covered_window_sample",
        "not_incremental_vs_accepted_sources",
    ],
    "confidence_reason": (
        "Mechanism: high/rising borrow fee and shrinking availability proxy "
        "informed short demand and lending-supply stress, the keystone PIT "
        "borrow economics named missing on 2026-06-24 and required by the "
        "exp-20260625-018 informed-flow lead. Disconfirmers: megacap-liquid "
        "names may sit at flat GC fee with capped availability; rolling 1y "
        "history covers late_strong fully, mid_weak partially, old_thin not "
        "at all, so any positive read is observed-only."
    ),
    "recorded_at": "2026-07-12T16:15:27+00:00",
}
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "trade_enabled": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "scope": (
        "data-collection only: sharded iBorrowDesk archive refresh added to "
        "run.py; no order, ranking, sizing, exit, or LLM behavior changes"
    ),
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_013_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "quant/iborrowdesk_data_source.py",
    "quant/test_iborrowdesk_data_source.py",
    "data/non_ohlcv/iborrowdesk/",
    "quant/run.py",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    "docs/frozen_families.jsonl",
]
FINGERPRINT_CAVEAT = (
    "experiment.py new routed this hypothesis to data_source=ortex_borrow via "
    "the 'borrow fee' keywords. That is the correct borrow-economics evidence "
    "face for streak/saturation counting, and this experiment additionally "
    "adds 'iborrowdesk'/'shortable' keywords to that population so future "
    "iborrowdesk-only wording cannot escape to 'other'."
)

# Fixed observed-only policy constants (do not retune).
FEE_LEVEL_STRESS = 1.0
FEE_DELTA5_STRESS = 0.25
AVAIL_RATIO5_STRESS = 0.7
LOOKBACK_SESSIONS = 5
HOLD_SESSIONS = 10
COOLDOWN_SESSIONS = 10
MIN_EVENTS_FLOOR = 20
LEAD_MEAN_DELTA_BP = -50.0
WINDOWS = {
    "late_strong_full": ("2025-10-23", "2026-04-21"),
    "mid_weak_covered_tail": ("2025-07-14", "2025-10-22"),
}
PRICE_LOAD_START = "2025-06-20"
PRICE_LOAD_END = "2026-07-11"
BENCHMARK = "SPY"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def universe_tickers() -> list[str]:
    return build_default_refresh_universe()


def cmd_materialize(sleep_s: float = 0.35, max_fetches: int | None = None) -> int:
    tickers = universe_tickers()
    summary = ibd.refresh_archive(
        tickers,
        max_fetches=max_fetches if max_fetches is not None else len(tickers),
        min_age_days=0.5,
        sleep_s=sleep_s,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "not_found"}, indent=2))
    print(f"not_found_count: {len(summary['not_found'])}")
    return 0


def _load_borrow_series() -> dict[str, dict[str, dict[str, Any]]]:
    series: dict[str, dict[str, dict[str, Any]]] = {}
    for symbol in ibd.archived_symbols():
        history = ibd.load_history(symbol)
        rows = history.get("rows") or {}
        if rows:
            series[symbol] = rows
    return series


def _forward_return(closes: list[float], opens: list[float], idx: int) -> float | None:
    """Next-open entry after signal index ``idx``, exit HOLD_SESSIONS closes later."""
    entry_idx = idx + 1
    exit_idx = entry_idx + HOLD_SESSIONS - 1
    if entry_idx >= len(opens) or exit_idx >= len(closes):
        return None
    entry = opens[entry_idx]
    exit_ = closes[exit_idx]
    if not entry or not exit_ or entry <= 0:
        return None
    return exit_ / entry - 1.0


def cmd_analyze() -> int:
    borrow = _load_borrow_series()
    tickers = sorted(set(borrow) & set(universe_tickers()))
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        [*tickers, BENCHMARK],
        PRICE_LOAD_START,
        PRICE_LOAD_END,
    )
    spy = frames.get(BENCHMARK)
    if spy is None or spy.empty:
        raise RuntimeError("SPY warehouse rows unavailable")
    spy_dates = [str(d.date()) for d in spy.index]
    spy_opens = [float(v) for v in spy["Open"]]
    spy_closes = [float(v) for v in spy["Close"]]
    spy_pos = {d: i for i, d in enumerate(spy_dates)}

    # Coverage/variance audit: does the fee field vary at all in this pool?
    fee_variance_tickers = 0
    max_fee_seen = 0.0
    for symbol in tickers:
        fees = [row.get("fee") for row in borrow[symbol].values() if row.get("fee") is not None]
        if fees and max(fees) >= 0.5:
            fee_variance_tickers += 1
        if fees:
            max_fee_seen = max(max_fee_seen, max(fees))

    events: list[dict[str, Any]] = []
    date_universe_returns: dict[str, list[float]] = {}
    for symbol in tickers:
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            continue
        dates = [str(d.date()) for d in frame.index]
        opens = [float(v) for v in frame["Open"]]
        closes = [float(v) for v in frame["Close"]]
        rows = borrow[symbol]
        stressed_prev = False
        cooldown_until = -1
        for idx, date in enumerate(dates):
            row = rows.get(date)
            if row is None:
                stressed_prev = False
                continue
            fee = row.get("fee")
            avail = row.get("available")
            past_date = dates[idx - LOOKBACK_SESSIONS] if idx >= LOOKBACK_SESSIONS else None
            past = rows.get(past_date) if past_date else None
            fee_delta5 = (
                fee - past.get("fee")
                if fee is not None and past and past.get("fee") is not None
                else None
            )
            avail_ratio5 = (
                avail / past.get("available")
                if avail is not None and past and past.get("available")
                else None
            )
            stressed = bool(
                (fee is not None and fee >= FEE_LEVEL_STRESS)
                or (
                    fee_delta5 is not None
                    and avail_ratio5 is not None
                    and fee_delta5 >= FEE_DELTA5_STRESS
                    and avail_ratio5 <= AVAIL_RATIO5_STRESS
                )
            )
            window = next(
                (name for name, (lo, hi) in WINDOWS.items() if lo <= date <= hi), None
            )
            if window and idx > cooldown_until and stressed and not stressed_prev:
                fwd = _forward_return(closes, opens, idx)
                spy_idx = spy_pos.get(date)
                spy_fwd = (
                    _forward_return(spy_closes, spy_opens, spy_idx)
                    if spy_idx is not None
                    else None
                )
                if fwd is not None and spy_fwd is not None:
                    events.append(
                        {
                            "ticker": symbol,
                            "date": date,
                            "window": window,
                            "fee": fee,
                            "fee_delta5": fee_delta5,
                            "avail_ratio5": avail_ratio5,
                            "fwd10_excess_vs_spy": fwd - spy_fwd,
                        }
                    )
                    cooldown_until = idx + COOLDOWN_SESSIONS
            stressed_prev = stressed
            # Same-date universe means for the comparator baseline.
            if window:
                fwd = _forward_return(closes, opens, idx)
                spy_idx = spy_pos.get(date)
                spy_fwd = (
                    _forward_return(spy_closes, spy_opens, spy_idx)
                    if spy_idx is not None
                    else None
                )
                if fwd is not None and spy_fwd is not None:
                    date_universe_returns.setdefault(date, []).append(fwd - spy_fwd)

    for event in events:
        baseline = date_universe_returns.get(event["date"]) or []
        event["universe_mean_excess_same_date"] = (
            statistics.fmean(baseline) if baseline else None
        )
        event["delta_vs_universe"] = (
            event["fwd10_excess_vs_spy"] - event["universe_mean_excess_same_date"]
            if event["universe_mean_excess_same_date"] is not None
            else None
        )

    scored = [e for e in events if e["delta_vs_universe"] is not None]
    by_window: dict[str, dict[str, Any]] = {}
    for name in WINDOWS:
        rows = [e["delta_vs_universe"] for e in scored if e["window"] == name]
        by_window[name] = {
            "events": len(rows),
            "mean_delta_bp": round(statistics.fmean(rows) * 1e4, 2) if rows else None,
            "median_delta_bp": round(statistics.median(rows) * 1e4, 2) if rows else None,
            "negative_share": (
                round(sum(1 for r in rows if r < 0) / len(rows), 4) if rows else None
            ),
        }
    all_rows = [e["delta_vs_universe"] for e in scored]
    aggregate = {
        "events": len(all_rows),
        "mean_delta_bp": round(statistics.fmean(all_rows) * 1e4, 2) if all_rows else None,
        "median_delta_bp": round(statistics.median(all_rows) * 1e4, 2) if all_rows else None,
        "negative_share": (
            round(sum(1 for r in all_rows if r < 0) / len(all_rows), 4) if all_rows else None
        ),
    }

    # Predeclared verdict.
    if aggregate["events"] < MIN_EVENTS_FLOOR:
        decision = "observed_only_thin_stress_sample_surface_retained"
        observed_only_lead = False
    else:
        window_means = [
            by_window[name]["mean_delta_bp"]
            for name in WINDOWS
            if by_window[name]["events"] > 0
        ]
        lead = (
            aggregate["mean_delta_bp"] is not None
            and aggregate["mean_delta_bp"] <= LEAD_MEAN_DELTA_BP
            and len(window_means) == len(WINDOWS)
            and all(m is not None and m < 0 for m in window_means)
        )
        observed_only_lead = bool(lead)
        decision = (
            "observed_only_borrow_stress_avoidance_lead"
            if lead
            else "observed_only_rejected_borrow_stress_avoidance"
        )

    fetch_state = ibd.load_fetch_state()
    ticker_meta = fetch_state.get("tickers") or {}
    archive_summary = {
        "archived_ticker_count": len(ibd.archived_symbols()),
        "ok_count": sum(1 for m in ticker_meta.values() if m.get("status") == "ok"),
        "not_found_count": sum(
            1 for m in ticker_meta.values() if m.get("status") == "not_found"
        ),
        "analysis_intersection_count": len(tickers),
        "fee_ge_half_pct_ticker_count": fee_variance_tickers,
        "max_fee_seen_pct": round(max_fee_seen, 4),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "status": "observed_only",
        "decision": decision,
        "observed_only_lead": observed_only_lead,
        "hypothesis": HYPOTHESIS,
        "policy": {
            "fee_level_stress_pct": FEE_LEVEL_STRESS,
            "fee_delta5_stress_pp": FEE_DELTA5_STRESS,
            "avail_ratio5_stress": AVAIL_RATIO5_STRESS,
            "hold_sessions": HOLD_SESSIONS,
            "cooldown_sessions": COOLDOWN_SESSIONS,
            "entry": "next_open",
            "exit": "tenth_session_close",
            "benchmark": BENCHMARK,
            "comparator": "same_date_equal_weight_universe_mean_excess",
            "min_events_floor": MIN_EVENTS_FLOOR,
            "lead_mean_delta_bp": LEAD_MEAN_DELTA_BP,
        },
        "windows": {k: {"start": v[0], "end": v[1]} for k, v in WINDOWS.items()},
        "window_coverage_note": (
            "late_strong fully covered; mid_weak only from 2025-07-14 (rolling "
            "1y archive); old_thin not covered, so no Gate 4 promotion is "
            "possible from this read regardless of sign."
        ),
        "archive_summary": archive_summary,
        "by_window": by_window,
        "aggregate": aggregate,
        "events": sorted(
            scored, key=lambda e: e["delta_vs_universe"] or 0.0
        )[:200],
        "fingerprint_caveat": FINGERPRINT_CAVEAT,
        "gate1": {
            "applicable": False,
            "note": "observed-only read plus data-collection wiring; no strategy policy changed",
        },
        "gate2": {
            "applicable": False,
            "note": "no signal-contract fields touched; entry_date/target_price paths unchanged",
        },
        "gate3": {
            "applicable": False,
            "note": "no filter added to any production or backtest signal path",
        },
        "gate4": {
            "applicable": False,
            "note": "no before/after strategy delta; observed-only verdict per predeclared floors",
            "failed_reasons": [],
        },
        "production_impact": PRODUCTION_IMPACT,
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B {RUNNER.replace('/', chr(92))} materialize",
            f".\\.venv\\Scripts\\python.exe -B {RUNNER.replace('/', chr(92))} analyze",
        ],
        "related_files": [
            "quant/iborrowdesk_data_source.py",
            "quant/test_iborrowdesk_data_source.py",
            "data/non_ohlcv/iborrowdesk/fetch_state.json",
            "quant/run.py",
            "scripts/experiment_fingerprint.py",
        ],
    }

    stress_reason = (
        f"{aggregate['events']} stressed-transition events across covered "
        f"windows with mean delta {aggregate['mean_delta_bp']}bp vs same-date "
        f"universe mean; fee>=0.5% ever seen on "
        f"{archive_summary['fee_ge_half_pct_ticker_count']} of "
        f"{archive_summary['analysis_intersection_count']} analysis tickers."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": stress_reason,
        "forbidden_near_neighbor_retry": (
            "Do not retry by retuning fee level, fee 5-session delta, "
            "availability ratio, lookback, hold, cooldown, or the comparator "
            "on this same archived span. The archive grows daily; the only "
            "legal reopen axes are materially more archived/settled sessions "
            "(>= 60 new sessions or >= 20 additional stressed events), a "
            "genuinely different gate shape consuming this surface, or a "
            "different borrow-economics source with deeper history."
        ),
        "new_evidence_required": (
            ">=60 new archived sessions or >=20 additional stressed-transition "
            "events, or a historical borrow source covering old_thin."
        ),
    }
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "unresolved_failure_mode": (
            None
            if observed_only_lead
            else "thin_or_flat_borrow_stress_in_liquid_pool"
        ),
    }

    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "aggregate": aggregate,
                "by_window": by_window,
                "archive_summary": archive_summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis_inference": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "aggregate": payload["aggregate"],
        "by_window": payload["by_window"],
        "archive_summary": payload["archive_summary"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "calibration": payload["calibration"],
        "fingerprint_caveat": payload["fingerprint_caveat"],
        "related_files": payload["related_files"],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} iBorrowDesk Borrow-Economics Surface",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            f"- Archived tickers: `{payload['archive_summary']['archived_ticker_count']}`"
            f" (analysis intersection `{payload['archive_summary']['analysis_intersection_count']}`)",
            f"- Fee variance: `{payload['archive_summary']['fee_ge_half_pct_ticker_count']}` tickers ever >= 0.5%,"
            f" max fee `{payload['archive_summary']['max_fee_seen_pct']}%`",
            f"- Stressed-transition events: `{aggregate['events']}`",
            f"- Mean delta vs same-date universe: `{aggregate['mean_delta_bp']}bp`",
            f"- By window: `{payload['by_window']}`",
            "",
            "## Boundary",
            "",
            payload["window_coverage_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    CARD_MD.write_text(build_card(payload), encoding="utf-8")
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "fingerprint_caveat": payload["fingerprint_caveat"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": True,
        },
    )
    files = [REPO_ROOT / RUNNER, OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": utc_now(),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in files
            },
        },
    )


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    if command == "materialize":
        sleep_s = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
        max_fetches = int(sys.argv[3]) if len(sys.argv) > 3 else None
        return cmd_materialize(sleep_s=sleep_s, max_fetches=max_fetches)
    if command == "analyze":
        return cmd_analyze()
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
