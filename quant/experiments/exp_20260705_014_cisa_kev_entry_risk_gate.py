"""exp-20260705-014: CISA KEV mapped-issuer entry risk window attribution.

Alpha-search source validation on a genuinely new free PIT event source: the
CISA Known Exploited Vulnerabilities catalog (dateAdded is the official
append-only catalog add date). Predeclared issuer map (from the 2026-07-03
web-scan debate): MSFT, AAPL, GOOG, META only; other vendor matches are
reported as diagnostics and do not enter the decision.

Two evidence layers, both machine-checkable:
1. Event study: next-session-open entry after each mapped KEV addition,
   5/10-session forward returns vs the same ticker's unconditional
   same-mechanics drift in the same canonical window.
2. Baseline trade attribution: canonical three-window core replay trades on
   the four tickers, flagged by entry inside the 5-session post-KEV window.

No strategy behavior changes. A positive result is only a lead (a core entry
gate would still need a shared helper plus full Gate 4 before/after).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260630_012_close_confirmed_static_stop as replay_base


EXPERIMENT_ID = "exp-20260705-014"
OWNER = "alpha-explore"
SLUG = "cisa_kev_entry_risk_gate"
RUNNER = f"quant/experiments/exp_20260705_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = replay_base.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260705_014_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

KEV_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/"
    "known_exploited_vulnerabilities.json"
)

# Predeclared decision scope (2026-07-03 web-scan debate P2). Vendor match is
# a lowercase prefix on vendorProject; anything else is diagnostics only.
DECISION_VENDOR_MAP = {
    "microsoft": "MSFT",
    "apple": "AAPL",
    "google": "GOOG",
    "meta": "META",
}
DIAGNOSTIC_VENDOR_MAP = {
    "cisco": "CSCO",
    "oracle": "ORCL",
    "adobe": "ADBE",
    "fortinet": "FTNT",
    "palo alto": "PANW",
    "broadcom": "AVGO",
    "vmware": "AVGO",
    "sap": "SAP",
    "atlassian": "TEAM",
}

KEV_WINDOW_SESSIONS = 5
EVENT_HORIZONS = (5, 10)
MIN_EVENTS_PER_SUPPORTING_WINDOW = 10
MIN_KEV_FLAGGED_TRADES = 5

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

HYPOTHESIS = (
    "CISA KEV catalog additions (dateAdded, PIT, credential-free) mapping to "
    "core-universe issuers MSFT/AAPL/GOOG/META mark elevated near-term "
    "operational/headline risk; core entries within 5 trading days after a "
    "mapped KEV addition should show worse forward returns, supporting an "
    "entry risk gate."
)
CHANGE_TYPE = "entry_filter"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "external_event_entry_risk_gate"
TRIAL_FAMILY = "cisa_kev_mapped_issuer_entry_risk_window"
TRIAL_VARIANT_ID = "cisa_kev_mapped_issuer_5d_entry_risk_window_v1"
CHANGED_VARIABLE = "cisa_kev_mapped_issuer_5d_entry_risk_window"
NEW_EVIDENCE_TYPE = "new_free_pit_event_data_source_cisa_kev"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260702-027", "exp-20260702-010"]
CAUSAL_COMPONENTS = [
    "pit kev archive materialization",
    "vendor ticker map",
    "event study forward returns",
    "baseline trade attribution",
    "gate verdict",
]


def repo_rel(path: Path | str) -> str:
    return replay_base.repo_rel(path)


def rounded(value: Any, digits: int = 6) -> Any:
    return replay_base.rounded(value, digits)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def fetch_kev_catalog() -> dict[str, Any]:
    import requests

    response = requests.get(KEV_URL, timeout=90)
    response.raise_for_status()
    payload = response.json()
    return {
        "catalog_version": payload.get("catalogVersion"),
        "date_released": payload.get("dateReleased"),
        "entry_count": len(payload.get("vulnerabilities") or []),
        "content_sha256": hashlib.sha256(response.content).hexdigest(),
        "vulnerabilities": payload.get("vulnerabilities") or [],
    }


def map_events(
    vulnerabilities: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """Return ({ticker: sorted unique dateAdded}, mapping diagnostics)."""
    decision_events: dict[str, set[str]] = {t: set() for t in DECISION_VENDOR_MAP.values()}
    decision_cve_counts: Counter[str] = Counter()
    diagnostic_counts: Counter[str] = Counter()
    unmapped_vendors: Counter[str] = Counter()
    for row in vulnerabilities:
        vendor = str(row.get("vendorProject") or "").strip().lower()
        date_added = str(row.get("dateAdded") or "")
        if len(date_added) != 10:
            continue
        matched = False
        for prefix, ticker in DECISION_VENDOR_MAP.items():
            if vendor.startswith(prefix):
                decision_events[ticker].add(date_added)
                decision_cve_counts[ticker] += 1
                matched = True
                break
        if matched:
            continue
        for prefix, ticker in DIAGNOSTIC_VENDOR_MAP.items():
            if vendor.startswith(prefix):
                diagnostic_counts[ticker] += 1
                matched = True
                break
        if not matched and date_added >= "2024-10-01":
            unmapped_vendors[vendor] += 1
    events = {ticker: sorted(dates) for ticker, dates in decision_events.items()}
    diagnostics = {
        "decision_cve_counts": dict(decision_cve_counts),
        "decision_unique_event_days": {t: len(v) for t, v in events.items()},
        "diagnostic_vendor_cve_counts_not_in_decision": dict(diagnostic_counts),
        "top_unmapped_vendors_since_2024_10": unmapped_vendors.most_common(10),
    }
    return events, diagnostics


def load_window_ohlcv(label: str) -> dict[str, list[dict[str, Any]]]:
    snapshot = json.loads(WINDOWS[label]["snapshot"].read_text(encoding="utf-8"))
    return snapshot.get("ohlcv") or {}


def _session_dates(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("Date")) for row in rows]


def _first_session_after(dates: list[str], day: str) -> int | None:
    for idx, session in enumerate(dates):
        if session > day:
            return idx
    return None


def kev_window_sessions(
    dates: list[str], event_days: list[str], width: int
) -> set[str]:
    """Union of the first `width` sessions strictly after each event day."""
    covered: set[str] = set()
    for day in event_days:
        idx = _first_session_after(dates, day)
        if idx is None:
            continue
        covered.update(dates[idx : idx + width])
    return covered


def event_study_for_window(
    label: str,
    ohlcv: dict[str, list[dict[str, Any]]],
    events: dict[str, list[str]],
) -> dict[str, Any]:
    start = WINDOWS[label]["start"]
    end = WINDOWS[label]["end"]
    per_ticker: dict[str, Any] = {}
    pooled_excess: dict[int, list[float]] = {h: [] for h in EVENT_HORIZONS}
    pooled_event_counts: dict[int, int] = {h: 0 for h in EVENT_HORIZONS}
    coverage: dict[str, Any] = {}

    for ticker, event_days in events.items():
        rows = ohlcv.get(ticker) or []
        if not rows:
            per_ticker[ticker] = {"error": "ticker_missing_from_snapshot"}
            continue
        dates = _session_dates(rows)
        in_window_idx = [i for i, d in enumerate(dates) if start <= d <= end]
        if not in_window_idx:
            per_ticker[ticker] = {"error": "no_sessions_in_window"}
            continue

        unconditional: dict[int, list[float]] = {h: [] for h in EVENT_HORIZONS}
        for i in in_window_idx:
            open_px = rows[i].get("Open")
            if not open_px:
                continue
            for horizon in EVENT_HORIZONS:
                j = i + horizon - 1
                if j < len(rows) and rows[j].get("Close"):
                    unconditional[horizon].append(
                        float(rows[j]["Close"]) / float(open_px) - 1.0
                    )

        event_returns: dict[int, list[float]] = {h: [] for h in EVENT_HORIZONS}
        used_events = 0
        for day in event_days:
            idx = _first_session_after(dates, day)
            if idx is None or not (start <= dates[idx] <= end):
                continue
            open_px = rows[idx].get("Open")
            if not open_px:
                continue
            used_events += 1
            for horizon in EVENT_HORIZONS:
                j = idx + horizon - 1
                if j < len(rows) and rows[j].get("Close"):
                    event_returns[horizon].append(
                        float(rows[j]["Close"]) / float(open_px) - 1.0
                    )

        window_sessions = [dates[i] for i in in_window_idx]
        covered = kev_window_sessions(dates, event_days, KEV_WINDOW_SESSIONS)
        covered_in_window = sorted(set(window_sessions) & covered)
        coverage[ticker] = {
            "window_sessions": len(window_sessions),
            "kev_window_sessions": len(covered_in_window),
            "kev_window_share": rounded(
                len(covered_in_window) / len(window_sessions), 4
            ),
        }

        ticker_out: dict[str, Any] = {"events_in_window": used_events}
        for horizon in EVENT_HORIZONS:
            ev_mean = _mean(event_returns[horizon])
            un_mean = _mean(unconditional[horizon])
            excess = (
                ev_mean - un_mean if ev_mean is not None and un_mean is not None else None
            )
            ticker_out[f"h{horizon}"] = {
                "event_n": len(event_returns[horizon]),
                "event_mean": rounded(ev_mean),
                "event_median": rounded(_median(event_returns[horizon])),
                "unconditional_mean": rounded(un_mean),
                "excess_mean": rounded(excess),
            }
            if ev_mean is not None and un_mean is not None:
                pooled_excess[horizon].extend(
                    ret - un_mean for ret in event_returns[horizon]
                )
                pooled_event_counts[horizon] += len(event_returns[horizon])
        per_ticker[ticker] = ticker_out

    pooled = {}
    for horizon in EVENT_HORIZONS:
        pooled[f"h{horizon}"] = {
            "event_n": pooled_event_counts[horizon],
            "pooled_excess_mean": rounded(_mean(pooled_excess[horizon])),
            "pooled_excess_median": rounded(_median(pooled_excess[horizon])),
        }
    return {"per_ticker": per_ticker, "pooled": pooled, "coverage": coverage}


def attribute_baseline_trades(
    label: str,
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
    events: dict[str, list[str]],
) -> dict[str, Any]:
    mapped_tickers = set(events)
    flagged: list[dict[str, Any]] = []
    unflagged_mapped: list[dict[str, Any]] = []
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in mapped_tickers:
            continue
        rows = ohlcv.get(ticker) or []
        dates = _session_dates(rows)
        covered = kev_window_sessions(dates, events[ticker], KEV_WINDOW_SESSIONS)
        entry_date = str(trade.get("entry_date") or "")
        row = {
            "ticker": ticker,
            "entry_date": entry_date,
            "pnl": trade.get("pnl"),
            "return_pct": trade.get("return_pct") or trade.get("pnl_pct"),
        }
        if entry_date in covered:
            flagged.append(row)
        else:
            unflagged_mapped.append(row)

    def _stats(rows_in: list[dict[str, Any]]) -> dict[str, Any]:
        pnls = [float(r["pnl"]) for r in rows_in if r.get("pnl") is not None]
        return {
            "n": len(rows_in),
            "pnl_sum": rounded(sum(pnls), 2),
            "pnl_mean": rounded(_mean(pnls), 2),
            "win_rate": rounded(
                (sum(1 for p in pnls if p > 0) / len(pnls)) if pnls else None, 4
            ),
        }

    return {
        "window": label,
        "kev_flagged": _stats(flagged),
        "mapped_ticker_unflagged": _stats(unflagged_mapped),
        "flagged_rows": flagged,
    }


def make_payload() -> dict[str, Any]:
    catalog = fetch_kev_catalog()
    events, mapping_diagnostics = map_events(catalog["vulnerabilities"])

    before_runs = {
        label: replay_base.run_window(label, dict(replay_base.BASE_CONFIG))
        for label in WINDOWS
    }
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    aggregate_before = replay_base.aggregate(before_metrics)

    event_study: dict[str, Any] = {}
    attribution: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv = load_window_ohlcv(label)
        event_study[label] = event_study_for_window(label, ohlcv, events)
        attribution[label] = attribute_baseline_trades(
            label, before_runs[label]["trades"], ohlcv, events
        )

    # Predeclared decision rule.
    supporting_windows: list[str] = []
    for label in WINDOWS:
        pooled = event_study[label]["pooled"]
        h5 = pooled["h5"]
        h10 = pooled["h10"]
        if (
            h5["pooled_excess_mean"] is not None
            and h10["pooled_excess_mean"] is not None
            and h5["pooled_excess_mean"] < 0
            and h10["pooled_excess_mean"] < 0
            and h5["event_n"] >= MIN_EVENTS_PER_SUPPORTING_WINDOW
        ):
            supporting_windows.append(label)

    flagged_n = sum(attribution[label]["kev_flagged"]["n"] for label in WINDOWS)
    flagged_means = [
        attribution[label]["kev_flagged"]["pnl_mean"]
        for label in WINDOWS
        if attribution[label]["kev_flagged"]["n"] > 0
        and attribution[label]["kev_flagged"]["pnl_mean"] is not None
    ]
    unflagged_means = [
        attribution[label]["mapped_ticker_unflagged"]["pnl_mean"]
        for label in WINDOWS
        if attribution[label]["mapped_ticker_unflagged"]["n"] > 0
        and attribution[label]["mapped_ticker_unflagged"]["pnl_mean"] is not None
    ]
    flagged_pooled_mean = _mean([m for m in flagged_means if m is not None])
    unflagged_pooled_mean = _mean([m for m in unflagged_means if m is not None])
    trades_support = (
        flagged_n >= MIN_KEV_FLAGGED_TRADES
        and flagged_pooled_mean is not None
        and unflagged_pooled_mean is not None
        and flagged_pooled_mean < unflagged_pooled_mean
    )

    support_lead = len(supporting_windows) >= 2 and trades_support

    failed_reasons: list[str] = []
    if len(supporting_windows) < 2:
        failed_reasons.append("event_drift_not_negative_in_two_windows")
    if flagged_n < MIN_KEV_FLAGGED_TRADES:
        failed_reasons.append("thin_vetoed_trade_sample")
    elif not trades_support:
        failed_reasons.append("kev_flagged_trades_not_worse")
    max_coverage = max(
        (
            info["kev_window_share"]
            for label in WINDOWS
            for info in event_study[label]["coverage"].values()
            if info.get("kev_window_share") is not None
        ),
        default=None,
    )
    if max_coverage is not None and max_coverage > 0.8:
        failed_reasons.append("kev_window_near_always_on_for_msft")

    decision = (
        "observed_positive_lead_cisa_kev_entry_risk_gate"
        if support_lead
        else "rejected_cisa_kev_entry_risk_gate"
    )
    status = "observed_only_positive_lead" if support_lead else "rejected"

    trades = [row for run in before_runs.values() for row in run["trades"]]
    missing_entry = [row for row in trades if not row.get("entry_date")]
    missing_target = [row for row in trades if row.get("target_price") in (None, "")]

    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    prediction = ticket.get("prediction") or {}
    predicted_p = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if support_lead else 0

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": replay_base.utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": support_lead,
        "accepted_alpha": False,
        "observed_only_lead": support_lead,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": round((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
        },
        "parameters": {
            "kev_url": KEV_URL,
            "kev_catalog_version": catalog["catalog_version"],
            "kev_catalog_sha256": catalog["content_sha256"],
            "kev_entry_count": catalog["entry_count"],
            "decision_vendor_map": DECISION_VENDOR_MAP,
            "kev_window_sessions": KEV_WINDOW_SESSIONS,
            "event_horizons": list(EVENT_HORIZONS),
            "decision_rule": (
                "Lead only if pooled 5- and 10-session post-KEV excess drift "
                "is negative in >=2 canonical windows with >=10 events each, "
                "AND >=5 baseline trades enter inside the 5-session KEV window "
                "with worse mean PnL than mapped-ticker non-KEV trades. "
                "Otherwise rejected; no strategy behavior changes either way."
            ),
            "windows": {
                label: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "snapshot": repo_rel(spec["snapshot"]),
                }
                for label, spec in WINDOWS.items()
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new accepted the proposal without override; "
                    "cisa_kev is a new data source with no prior family."
                ),
                "exp-20260702-027": (
                    "S-1/F-1 overhang core entry veto rejected on zero core "
                    "intersection; KEV maps directly to four core megacaps so "
                    "the intersection risk is coverage saturation instead."
                ),
                "exp-20260702-010": (
                    "Entry risk cap rejected at the materiality hurdle; this "
                    "test validates the source before proposing any gate."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Predeclared two-layer rule in parameters.decision_rule; "
                "docs/backtesting.md canonical windows and baselines."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "rerun_before_aggregate": aggregate_before,
            "accepted_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
            },
        },
        "gate2": {
            "fields_checked": ["entry_date", "target_price"],
            "missing_entry_date": len(missing_entry),
            "missing_target_price_on_trade_rows": len(missing_target),
            "target_price_relevance": (
                "target_price lives on generated signals and drives exits "
                "inside the engine; closed-trade rows do not carry it and "
                "this read-only attribution does not consume it (same "
                "semantics as exp-20260702-010 gate2)."
            ),
            "passed": not missing_entry,
        },
        "gate3": {
            "new_entry_filter_added": False,
            "note": (
                "Attribution only; no filter applied, so survival is the "
                "unchanged baseline."
            ),
            "minimum_before_survival_rate": min(
                float(before_metrics[label].get("survival_rate") or 0.0)
                for label in WINDOWS
            ),
            "passed": True,
        },
        "gate4": {
            "applicable": False,
            "note": (
                "No before/after strategy change proposed; the predeclared "
                "source-validation rule decides. A positive lead would still "
                "need a shared-helper Gate 4 veto experiment."
            ),
            "passed": support_lead,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "supporting_windows": supporting_windows,
            "kev_flagged_trade_count": flagged_n,
            "kev_flagged_pooled_pnl_mean": rounded(flagged_pooled_mean, 2),
            "mapped_unflagged_pooled_pnl_mean": rounded(unflagged_pooled_mean, 2),
            "max_ticker_kev_window_coverage": max_coverage,
        },
        "kev_mapping_diagnostics": mapping_diagnostics,
        "event_study": event_study,
        "baseline_trade_attribution": attribution,
        "before_metrics": before_metrics,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only attribution over canonical replay trades and OHLCV "
                "snapshots plus a live KEV catalog fetch; no production or "
                "backtest behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": None,  # filled in main()
            "forbidden_near_neighbor_retry": (
                "Do not retune the 5-session window, the horizon pair, the "
                "vendor prefix map, or re-slice the same KEV events by CVE "
                "attributes (ransomware flag, CWE, product line) on the same "
                "fixed windows. Do not expand to weak vendor mappings to pad "
                "the sample."
            ),
            "new_evidence_required": (
                "A legal retry needs settled forward rows recorded after a "
                "future mapped KEV addition, a genuinely different external "
                "event source, or a shared-helper Gate 4 experiment if this "
                "lead is positive."
            ),
        },
        "rejection_reason": None if support_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "forward rows after future mapped KEV additions",
            "or a shared-helper Gate 4 veto experiment on a positive lead",
        ],
        "before_after_strategy_behavior_changed": False,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} CISA KEV mapped-issuer entry risk window",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "| Window | h5 excess | h5 n | h10 excess | h10 n | KEV-flagged trades | flagged mean PnL | unflagged mean PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        pooled = payload["event_study"][label]["pooled"]
        attr = payload["baseline_trade_attribution"][label]
        lines.append(
            f"| {label} | {pooled['h5']['pooled_excess_mean']} | "
            f"{pooled['h5']['event_n']} | {pooled['h10']['pooled_excess_mean']} | "
            f"{pooled['h10']['event_n']} | {attr['kev_flagged']['n']} | "
            f"{attr['kev_flagged']['pnl_mean']} | "
            f"{attr['mapped_ticker_unflagged']['pnl_mean']} |"
        )
    gate4 = payload["gate4"]
    lines += [
        "",
        f"Supporting windows: {gate4['supporting_windows']}; "
        f"failed reasons: {gate4['failed_reasons']}; "
        f"max ticker KEV-window coverage: {gate4['max_ticker_kev_window_coverage']}.",
        "",
        "Coverage per ticker/window is in the artifact. No strategy behavior "
        "changed; a positive lead still requires a shared-helper Gate 4 veto "
        "experiment before any production-visible change.",
    ]
    return "\n".join(lines) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [Path(RUNNER), OUT_JSON, LOG_JSON, CARD_MD, MANIFEST_JSON, TICKET_JSON]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": replay_base.utc_now(),
        "files": [
            {
                "path": repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": replay_base.sha256(
                    REPO_ROOT / path if not path.is_absolute() else path
                ),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    replay_base.write_json(OUT_JSON, payload)
    replay_base.write_text(CARD_MD, make_card(payload))
    replay_base.save_experiment_log_entry(payload, allow_duplicate=True)
    replay_base.write_json(MANIFEST_JSON, make_manifest(payload))
    replay_base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = make_payload()
    if payload["observed_only_lead"]:
        payload["post_run_reflection"]["why_result_happened"] = (
            "Post-KEV drift was negative across windows and KEV-window "
            "baseline entries underperformed, so the source earned a "
            "shared-helper Gate 4 follow-up."
        )
    else:
        payload["post_run_reflection"]["why_result_happened"] = (
            "Mapped mega-cap issuers absorb KEV headlines without "
            "systematic near-term underperformance, or the flagged sample "
            "was too thin/saturated for a deployable gate: "
            + (payload["rejection_reason"] or "")
        )
    persist(payload)
    print(
        json.dumps(
            replay_base.safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "gate4": payload["gate4"],
                    "artifact": payload["artifact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
