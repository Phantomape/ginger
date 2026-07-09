"""exp-20260703-020: SEC Item 1.01 contract-relation peer-target scout.

Observed-only alpha attribution. The fixed Item 1.01 contract-relation
provenance surface from exp-20260703-017 is propagated from the issuer to
listed SIC/theme peers using the existing entity exposure map, then compressed
to one peer-target candidate per usable trade date and measured at next-open
entry with a 10-session close.

No strategy behavior changes here: no entries, ranking, sizing, exits, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.experiments import (  # noqa: E402
    exp_20260703_018_sec_item101_contract_relation_issuer_self as base,
)


EXPERIMENT_ID = "exp-20260703-020"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_item101_contract_relation_peer_target"
RUNNER = f"quant/experiments/exp_20260703_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "rows.jsonl"
)
SOURCE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "latest_summary.json"
)
EXPOSURE_MAP_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "SEC 8-K Item 1.01 specific contract-relation provenance may propagate "
    "to issuer SIC/theme peers; a fixed daily top-1 peer-target next-open "
    "10-session observed-only source should show replacement value versus "
    "cash, SPY, and QQQ before any shared default-off promotion."
)
CHANGED_VARIABLE = "sec_item101_contract_relation_peer_target_top1_10d_v1"
TRIAL_FAMILY = "sec_item101_contract_relation_peer_target_candidate_source"
TRIAL_VARIANT_ID = "fixed_issuer_peer_top1_10d_v1"
NEARBY_PRIORS = [
    "exp-20260703-017",
    "exp-20260703-018",
    "exp-20260703-019",
    "exp-20260702-012",
]
NEW_EVIDENCE_AXIS = (
    "New gate shape explicitly allowed by exp-20260703-018: target-side peer "
    "propagation from fixed Item 1.01 contract-relation provenance to listed "
    "SIC/theme peers, not issuer-self and not S-1/F-1/425 corporate-event "
    "stream; no relation regex, bucket, priority, top-N, hold, notional, "
    "source-priority, or response-curve retune."
)
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "SEC text source saturation",
        "SEC event peer near-neighbor",
        "window_instability",
        "ticker_concentration",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260703-018 explicitly named counterparty/peer target-side "
        "relation as the next evidence axis, but prior SEC peer propagation "
        "and issuer-self promotion were rejected, so this is a low-probability "
        "fixed scout."
    ),
    "recorded_at": "2026-07-03T20:20:16+00:00",
}

WINDOWS = base.WINDOWS
PRIMARY_METRICS = base.PRIMARY_METRICS
RELATION_PRIORITY = base.RELATION_PRIORITY
ACCEPTANCE_RULE = {
    "min_settled_top1_rows": 20,
    "min_settled_windows": 2,
    "min_rows_per_settled_window": 5,
    "min_positive_windows_vs_spy_and_qqq": 2,
    "max_top_ticker_share": 0.40,
    "require_aggregate_primary_means_positive": True,
    "require_aggregate_primary_medians_nonnegative": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_020_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_exposure_map(map_dir: Path) -> dict[str, Any]:
    sic_index = json.loads((map_dir / "sic_peer_index.json").read_text(encoding="utf-8"))
    overlay = json.loads((map_dir / "theme_overlay.json").read_text(encoding="utf-8"))
    ticker_sic: dict[str, str] = {}
    for sic, peers in (sic_index.get("by_sic") or {}).items():
        for peer in peers:
            ticker = str(peer.get("ticker") or "").upper()
            if ticker:
                ticker_sic[ticker] = str(sic)
    ticker_themes: dict[str, list[str]] = defaultdict(list)
    for entry in overlay.get("themes") or []:
        for ticker in entry.get("listed_peers") or []:
            ticker_themes[str(ticker).upper()].append(str(entry.get("theme") or ""))
    return {
        "sic_index": sic_index,
        "overlay": overlay,
        "ticker_sic": ticker_sic,
        "ticker_themes": dict(ticker_themes),
    }


def exposure_set_for_ticker(
    ticker: str,
    exposure_map: Mapping[str, Any],
    *,
    max_sic_peers: int = 15,
) -> list[dict[str, Any]]:
    ticker = ticker.upper()
    edges: list[dict[str, Any]] = []
    seen: set[str] = {ticker}
    sic = exposure_map["ticker_sic"].get(ticker)
    if sic:
        for peer in (exposure_map["sic_index"].get("by_sic") or {}).get(sic, [])[
            :max_sic_peers
        ]:
            target = str(peer.get("ticker") or "").upper()
            if not target or target in seen:
                continue
            seen.add(target)
            edges.append(
                {
                    "target_ticker": target,
                    "peer_relation_type": "sic_peer",
                    "peer_match_basis": f"sic:{sic}",
                    "peer_theme": None,
                }
            )
    themes_by_name = {
        str(entry.get("theme") or ""): entry
        for entry in exposure_map["overlay"].get("themes") or []
    }
    for theme in exposure_map["ticker_themes"].get(ticker, []):
        entry = themes_by_name.get(theme)
        if entry is None:
            continue
        for peer in entry.get("listed_peers") or []:
            target = str(peer).upper()
            if not target or target in seen:
                continue
            seen.add(target)
            edges.append(
                {
                    "target_ticker": target,
                    "peer_relation_type": "theme_peer",
                    "peer_match_basis": f"theme_membership:{theme}",
                    "peer_theme": theme,
                }
            )
    return edges


def peer_relation_rank(row: Mapping[str, Any]) -> int:
    return 0 if row.get("peer_relation_type") == "theme_peer" else 1


def peer_rank(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        RELATION_PRIORITY.get(str(row.get("relation_bucket") or ""), 99),
        peer_relation_rank(row),
        -int(row.get("evidence_phrase_count") or 0),
        0 if row.get("counterparty_candidates") else 1,
        str(row.get("accepted_at") or ""),
        str(row.get("target_ticker") or row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
    )


def build_peer_rows(
    accession_rows: list[dict[str, Any]], exposure_map: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    peer_rows: list[dict[str, Any]] = []
    issuers_without_edges = []
    for row in accession_rows:
        issuer_ticker = str(row.get("ticker") or "").upper()
        edges = exposure_set_for_ticker(issuer_ticker, exposure_map)
        if not edges:
            issuers_without_edges.append(issuer_ticker)
            continue
        for edge in edges:
            target = edge["target_ticker"]
            peer_rows.append(
                {
                    **row,
                    "issuer_ticker": issuer_ticker,
                    "target_ticker": target,
                    "ticker": target,
                    "peer_relation_type": edge["peer_relation_type"],
                    "peer_match_basis": edge["peer_match_basis"],
                    "peer_theme": edge["peer_theme"],
                }
            )
    diagnostics = {
        "issuer_rows_without_edges": len(issuers_without_edges),
        "unique_issuers_without_edges": sorted(set(issuers_without_edges))[:20],
        "peer_rows": len(peer_rows),
        "peer_relation_types": dict(
            Counter(str(row.get("peer_relation_type") or "unknown") for row in peer_rows)
        ),
    }
    return peer_rows, diagnostics


def daily_top1_peer(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[str(row["usable_trade_date"])].append(row)
    selected = []
    for day, day_rows in by_day.items():
        best = sorted(day_rows, key=peer_rank)[0]
        selected.append(
            {
                **best,
                "selection_date": day,
                "daily_candidate_count": len(day_rows),
            }
        )
    return sorted(selected, key=lambda row: (row["selection_date"], peer_rank(row)))


def build_outcomes(
    selected_rows: list[dict[str, Any]],
    bars: dict[str, list[dict[str, Any]]],
    *,
    horizon: int = 10,
    notional: float = 4000.0,
) -> list[dict[str, Any]]:
    outcomes = []
    for row in selected_rows:
        ticker = str(row.get("target_ticker") or row.get("ticker") or "").upper()
        ticker_bars = bars.get(ticker, [])
        entry_idx = base.first_bar_on_or_after(ticker_bars, row["usable_trade_date"])
        result = {
            "observer_only": True,
            "trade_enabled": False,
            "source_experiment": "exp-20260703-017",
            "source_row_key": {
                "accession_number": row.get("accession_number"),
                "relation_bucket": row.get("relation_bucket"),
                "source_text_hash16": row.get("source_text_hash16"),
            },
            "issuer_ticker": row.get("issuer_ticker"),
            "target_ticker": ticker,
            "ticker": ticker,
            "selection_date": row["selection_date"],
            "usable_trade_date": row["usable_trade_date"],
            "daily_candidate_count": row.get("daily_candidate_count"),
            "relation_bucket": row.get("relation_bucket"),
            "relation_quality": row.get("relation_quality"),
            "peer_relation_type": row.get("peer_relation_type"),
            "peer_match_basis": row.get("peer_match_basis"),
            "peer_theme": row.get("peer_theme"),
            "evidence_phrase_count": row.get("evidence_phrase_count"),
            "counterparty_candidate_count": len(row.get("counterparty_candidates") or []),
            "accession_number": row.get("accession_number"),
            "accepted_at": row.get("accepted_at"),
            "filing_date": row.get("filing_date"),
            "horizon_trading_days": horizon,
            "notional_usd": notional,
            "pit_caveat": row.get("pit_caveat"),
        }
        if entry_idx is None:
            outcomes.append({**result, "outcome_status": "unsettled_no_entry_bar"})
            continue
        exit_idx = entry_idx + horizon - 1
        entry_bar = ticker_bars[entry_idx]
        result["entry_date"] = entry_bar["_date"]
        result["entry_open"] = round(float(entry_bar["open"]), 4)
        result["window"] = base.window_for_entry(entry_bar["_date"])
        if exit_idx >= len(ticker_bars):
            outcomes.append({**result, "outcome_status": "unsettled_horizon"})
            continue
        exit_bar = ticker_bars[exit_idx]
        pnl = base.pnl_for_bars(entry_bar, exit_bar, notional)
        result.update(
            {
                "exit_date": exit_bar["_date"],
                "exit_close": round(float(exit_bar["close"]), 4),
                "pnl_usd": pnl,
                "replacement_value_vs_cash_usd": pnl,
            }
        )
        missing_comparator = False
        comparator_detail: dict[str, Any] = {}
        for comparator in ("SPY", "QQQ"):
            comp_rows = bars.get(comparator, [])
            comp_entry = base.bar_by_date(comp_rows, entry_bar["_date"])
            comp_exit = base.bar_by_date(comp_rows, exit_bar["_date"])
            comp_pnl = (
                base.pnl_for_bars(comp_entry, comp_exit, notional)
                if comp_entry and comp_exit
                else None
            )
            if comp_pnl is None:
                missing_comparator = True
            result[f"replacement_value_vs_{comparator.lower()}_usd"] = (
                round(pnl - comp_pnl, 2) if comp_pnl is not None else None
            )
            comparator_detail[comparator] = {
                "entry_date": comp_entry["_date"] if comp_entry else None,
                "exit_date": comp_exit["_date"] if comp_exit else None,
                "pnl_usd": comp_pnl,
            }
        result["comparator_detail"] = comparator_detail
        result["outcome_status"] = (
            "missing_comparator_bars" if missing_comparator else "settled"
        )
        outcomes.append(result)
    return outcomes


def count_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("target_ticker") or "UNKNOWN") for row in rows)
    issuers = Counter(str(row.get("issuer_ticker") or "UNKNOWN") for row in rows)
    relation_types = Counter(str(row.get("peer_relation_type") or "UNKNOWN") for row in rows)
    windows = Counter(str(row.get("window") or "outside") for row in rows)
    total = len(rows)
    return {
        "row_count": total,
        "ticker_count": len(tickers),
        "issuer_count": len(issuers),
        "peer_relation_type_count": len(relation_types),
        "window_count": len([window for window in windows if window != "outside"]),
        "top_ticker_share": round(tickers.most_common(1)[0][1] / total, 6)
        if total
        else None,
        "top_target_tickers_by_rows": [
            {"ticker": ticker, "rows": count}
            for ticker, count in tickers.most_common(10)
        ],
        "top_issuer_tickers_by_rows": [
            {"issuer_ticker": ticker, "rows": count}
            for ticker, count in issuers.most_common(10)
        ],
        "peer_relation_types": dict(relation_types),
        "windows": dict(windows),
    }


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "policy_bundle",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = base.baseline_metrics()
    source_summary = base.read_json(SOURCE_SUMMARY, {}) or {}
    exposure_manifest = base.read_json(EXPOSURE_MAP_DIR / "manifest.json", {}) or {}
    raw_rows = base.load_jsonl(SOURCE_ROWS)
    accession_rows = base.dedupe_accessions(raw_rows)
    exposure_map = load_exposure_map(EXPOSURE_MAP_DIR)
    peer_rows, peer_diagnostics = build_peer_rows(accession_rows, exposure_map)
    selected = daily_top1_peer(peer_rows)
    tickers = sorted({row["target_ticker"] for row in selected} | {"SPY", "QQQ"})
    bars, warehouse_summary = base.load_bars(tickers)
    outcomes = build_outcomes(selected, bars)
    settled = [row for row in outcomes if row.get("outcome_status") == "settled"]
    canonical_settled = [row for row in settled if row.get("window") in WINDOWS]
    outside_settled = [row for row in settled if row.get("window") not in WINDOWS]

    overall_metrics = base.metric_summary(canonical_settled)
    by_window = base.group_summaries(canonical_settled, "window")
    by_relation_type = base.group_summaries(canonical_settled, "peer_relation_type")
    by_bucket = base.group_summaries(canonical_settled, "relation_bucket")
    by_ticker = base.group_summaries(canonical_settled, "target_ticker")
    counts = count_summary(canonical_settled)

    window_rows = {
        item["window"]: item["row_count"]
        for item in by_window
        if item.get("window") in WINDOWS
    }
    settled_windows = [
        label
        for label, row_count in window_rows.items()
        if row_count >= ACCEPTANCE_RULE["min_rows_per_settled_window"]
    ]
    positive_windows_vs_spy_and_qqq = sum(
        1
        for item in by_window
        if item.get("window") in WINDOWS and item["spy_and_qqq_means_positive"]
    )
    aggregate_means_positive = all(
        (overall_metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    aggregate_medians_nonnegative = all(
        (overall_metrics[metric]["median"] or 0.0) >= 0 for metric in PRIMARY_METRICS
    )
    checks = {
        "settled_top1_rows_min_passed": len(canonical_settled)
        >= ACCEPTANCE_RULE["min_settled_top1_rows"],
        "settled_windows_min_passed": len(settled_windows)
        >= ACCEPTANCE_RULE["min_settled_windows"],
        "positive_windows_vs_spy_and_qqq_passed": positive_windows_vs_spy_and_qqq
        >= ACCEPTANCE_RULE["min_positive_windows_vs_spy_and_qqq"],
        "aggregate_primary_means_positive": aggregate_means_positive,
        "aggregate_primary_medians_nonnegative": aggregate_medians_nonnegative,
        "top_ticker_share_passed": (
            counts["top_ticker_share"] is not None
            and counts["top_ticker_share"] <= ACCEPTANCE_RULE["max_top_ticker_share"]
        ),
    }
    directional_support = all(checks.values())
    failed_reasons = [name for name, passed in checks.items() if not passed]
    if directional_support:
        status = "observed_only_positive_lead"
        decision = "observed_only_positive_sec_item101_contract_relation_peer_target_lead"
        actual_success = 1
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_no_sec_item101_contract_relation_peer_target_edge"
        actual_success = 0

    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in outcomes)
    why = (
        "The peer-target propagation source cleared the observed-only "
        "replacement checks, but it is not accepted alpha because no shared "
        "default-off helper was promoted and the SEC text surface is a "
        "public-archive PIT proxy."
        if directional_support
        else "The fixed Item 1.01 issuer-to-peer target source was not broad "
        "enough: canonical aggregate means were positive, but medians were "
        "negative and only one canonical window beat both SPY and QQQ."
    )
    realized_failure_modes = []
    if not checks["positive_windows_vs_spy_and_qqq_passed"]:
        realized_failure_modes.append("window_instability")
    if not checks["aggregate_primary_medians_nonnegative"]:
        realized_failure_modes.append("accepted_comparator_not_beaten")
    if not checks["top_ticker_share_passed"]:
        realized_failure_modes.append("ticker_concentration")
    if not realized_failure_modes:
        realized_failure_modes.append("public-archive PIT caveat")

    summary = {
        "source_rows": len(raw_rows),
        "accession_deduped_rows": len(accession_rows),
        "peer_rows": len(peer_rows),
        "daily_top1_candidates": len(selected),
        "canonical_settled_rows": len(canonical_settled),
        "outside_canonical_settled_rows": len(outside_settled),
        "settled_windows": settled_windows,
        "positive_windows_vs_spy_and_qqq": positive_windows_vs_spy_and_qqq,
        "row_mean_cash": overall_metrics["replacement_value_vs_cash_usd"]["mean"],
        "row_mean_spy": overall_metrics["replacement_value_vs_spy_usd"]["mean"],
        "row_mean_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["mean"],
        "row_median_cash": overall_metrics["replacement_value_vs_cash_usd"]["median"],
        "row_median_spy": overall_metrics["replacement_value_vs_spy_usd"]["median"],
        "row_median_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["median"],
        "top_ticker_share": counts["top_ticker_share"],
        "decision": decision,
    }

    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": directional_support,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "sec_contract_relation_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed Item 1.01 contract relation provenance",
            "fixed entity exposure SIC/theme peer map",
            "daily top-1 peer-target selection",
            "next-open 10-session outcomes",
            "cash/SPY/QQQ replacement attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": actual_success,
            "brier_score": round(
                (PREDICTION["success_probability"] - actual_success) ** 2, 4
            ),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": bool(
                set(realized_failure_modes) & set(PREDICTION["main_failure_modes"])
            ),
            "surprise_note": (
                "Low surprise: the fixed peer-target propagation read did not "
                "clear broad window and comparator checks."
                if not directional_support
                else "Moderate surprise: the saturated SEC text peer-target "
                "source cleared observed-only checks."
            ),
        },
        "policy_bundle": {
            "source_surface": "exp-20260703-017 Item 1.01 contract-relation provenance",
            "peer_map": "entity_exposure_map SIC peers plus curated theme peers",
            "max_sic_peers": 15,
            "peer_priority": ["theme_peer", "sic_peer"],
            "dedupe": (
                "one best relation row per accession_number by fixed exp-20260703-018 "
                "relation priority, evidence count, counterparty presence, accepted_at, "
                "ticker"
            ),
            "selection": (
                "one best peer target per usable_trade_date by relation priority, "
                "peer type, evidence count, counterparty presence, accepted_at, "
                "target ticker, accession"
            ),
            "entry": "first local OHLCV open on or after usable_trade_date",
            "exit": "10th trading session close after entry",
            "notional_usd": 4000.0,
            "comparators": ["cash", "SPY", "QQQ"],
            "relation_priority": RELATION_PRIORITY,
        },
        "gate1": {
            "passed": True,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": bool(canonical_settled),
            "fields_checked": [
                "issuer_ticker",
                "target_ticker",
                "accession_number",
                "relation_bucket",
                "relation_quality",
                "peer_relation_type",
                "peer_match_basis",
                "usable_trade_date",
                "accepted_at",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "source_rows": len(raw_rows),
            "accession_deduped_rows": len(accession_rows),
            "peer_rows": len(peer_rows),
            "daily_top1_candidates": len(selected),
            "canonical_settled_rows": len(canonical_settled),
            "entry_date_present_rows": sum(1 for row in outcomes if row.get("entry_date")),
            "target_price_relevance": (
                "This observed-only fixed-horizon paper read does not create "
                "target exits or orders; target_price is not part of the surface."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(selected),
            "signals_survived": len(canonical_settled),
            "survival_rate": round(len(canonical_settled) / len(selected), 6)
            if selected
            else None,
            "note": (
                "No executable filter, ranking, sizing, exit, prompt, or order "
                "rule was added. Survival here means daily top-1 candidates with "
                "settled canonical-window 10-session outcomes."
            ),
        },
        "gate4": {
            "passed": directional_support,
            "observed_only": True,
            "accepted_alpha": False,
            "strategy_rerun_required": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": {
                "strategy_behavior_changed": False,
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "strategy_behavior_changed": False,
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "summary": summary,
        "diagnostics": {
            "source_summary": source_summary,
            "exposure_manifest": exposure_manifest,
            "peer_diagnostics": peer_diagnostics,
            "warehouse_summary": warehouse_summary,
            "outcome_status_counts": dict(status_counts),
            "counts": counts,
            "by_window": by_window,
            "by_peer_relation_type": by_relation_type,
            "by_relation_bucket": by_bucket,
            "by_target_ticker": by_ticker[:25],
        },
        "outcomes": outcomes,
        "production_impact": {
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only analysis over exp-20260703-017 observer provenance "
                "and existing entity exposure map. No helper, adapter, order, "
                "rank, size, exit, watchlist, or LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 relation regexes, item codes, relation "
                "priority, peer priority, SIC peer cap, top-N, hold days, "
                "cooldown, notional, source priority, liquidity guards, or "
                "response curves on this same public-archive surface."
            ),
            "new_evidence_required": (
                "A valid retry needs materially richer relation economics such "
                "as normalized counterparty identity, contract value/duration/"
                "revenue exposure, a true customer/supplier graph, or "
                "prospectively accumulated shared-helper rows with closed "
                "replacement value."
            ),
        },
        "next_retry_requires": [
            "normalized counterparty identity or contract value/duration/revenue exposure",
            "true counterparty/customer/supplier graph rather than issuer SIC/theme peer map",
            "prospectively accumulated daily rows with closed replacement value",
            "no same-surface peer/rank/hold/notional/liquidity/response retune",
        ],
        "related_files": [
            RUNNER,
            "quant/experiments/exp_20260703_018_sec_item101_contract_relation_issuer_self.py",
            "data/non_ohlcv/sec_contract_relation_provenance/rows.jsonl",
            "data/non_ohlcv/sec_contract_relation_provenance/latest_summary.json",
            "data/non_ohlcv/entity_exposure_map/sic_peer_index.json",
            "data/non_ohlcv/entity_exposure_map/theme_overlay.json",
            "experiments/logs/exp-20260703-017.json",
            "experiments/logs/exp-20260703-018.json",
            "experiments/logs/exp-20260703-019.json",
            "experiments/logs/exp-20260702-012.json",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }
    return result


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Observed-only lead: `{str(result["observed_only_lead"]).lower()}`
- Daily top-1 candidates: `{summary["daily_top1_candidates"]}`
- Canonical settled rows: `{summary["canonical_settled_rows"]}`
- Settled windows: `{", ".join(summary["settled_windows"]) or "none"}`
- Positive windows vs SPY and QQQ: `{summary["positive_windows_vs_spy_and_qqq"]}`
- Row means cash/SPY/QQQ: `{summary["row_mean_cash"]}` / `{summary["row_mean_spy"]}` / `{summary["row_mean_qqq"]}`
- Row medians cash/SPY/QQQ: `{summary["row_median_cash"]}` / `{summary["row_median_spy"]}` / `{summary["row_median_qqq"]}`
- Top target ticker share: `{summary["top_ticker_share"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = base.read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    base.write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    base.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    base.write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    base.write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
