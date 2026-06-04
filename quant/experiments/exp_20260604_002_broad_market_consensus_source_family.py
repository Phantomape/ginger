"""exp-20260604-002: broad-market source family for accepted consensus.

Replay-only alpha search. This tests one variable: whether the accepted,
production-visible BROAD_MARKET_LEADERSHIP_PAPER sleeve can act as a genuinely
independent source family inside the accepted free-data cross-source consensus.

No shared adapter, production order path, ranking, sizing, exits, LLM, news,
watchlists, source thresholds, hold period, cooldown, or notional policy is
changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260520_004_broad_market_trend_persistence_notional as broad_market  # noqa: E402
import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402


EXPERIMENT_ID = "exp-20260604-002"
STEM = "broad_market_consensus_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
CHANGED_VARIABLE = "broad_market_leadership_source_family_added_to_accepted_free_data_consensus_v1"
RULE_VERSION = "accepted_consensus_with_broad_market_source_family_v1"

BROAD_MARKET_SOURCE = "BROAD_MARKET_LEADERSHIP_PAPER"
BROAD_MARKET_EXPERIMENT_ID = "exp-20260520-004"
BROAD_MARKET_FAMILY = "broad_market_leadership"
BROAD_MARKET_RULE_VERSION = "broad_market_trend_persistence_notional_v1"

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_002_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
ACCEPTED_COMPARATOR_JSON = OUT_DIR / f"{STEM}_accepted_comparator_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = Path("docs/experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = Path("experiments/artifacts") / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

BROAD_MARKET_SOURCE_ARTIFACT = Path(
    "data/experiments/exp-20260520-004/broad_market_trend_persistence_notional.json"
)
CURRENT_ACCEPTED_COMPARATOR_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)

SOURCE_FILES = {
    **consensus.SOURCE_FILES,
    BROAD_MARKET_SOURCE: BROAD_MARKET_SOURCE_ARTIFACT,
}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    BROAD_MARKET_SOURCE: BROAD_MARKET_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    BROAD_MARKET_SOURCE: BROAD_MARKET_FAMILY,
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained broad-market "
        "source-family lead would need the shared free-data consensus adapter to "
        "consume BROAD_MARKET_LEADERSHIP_PAPER source rows from the same "
        "broad_market_paper_sleeve.py path in both daily run and replay before "
        "any candidate queue or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.SOURCE_FILES = SOURCE_FILES
    consensus.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    consensus.SOURCE_FAMILIES = SOURCE_FAMILIES
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.BEFORE_JSON = BEFORE_JSON
    consensus.AFTER_JSON = AFTER_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()


def _source_family(source_name: str) -> str:
    return SOURCE_FAMILIES.get(source_name, source_name)


def _source_row_from_broad_market_trade(trade: dict[str, Any]) -> dict[str, Any]:
    signal_date = str(trade.get("decision_date") or "")[:10]
    ticker = str(trade.get("ticker") or "").upper()
    return {
        "source_name": BROAD_MARKET_SOURCE,
        "source_experiment_id": BROAD_MARKET_EXPERIMENT_ID,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": BROAD_MARKET_FAMILY,
        "source_rule_version": BROAD_MARKET_RULE_VERSION,
        "known_at": f"{signal_date}T21:00:00Z",
        "paper_pnl": trade.get("pnl"),
        "pnl_usd": trade.get("pnl"),
        "return_pct": trade.get("net_return_pct"),
        "broad_market_score": trade.get("score"),
        "broad_market_rank": trade.get("rank"),
        "ret20_excess_spy": trade.get("ret20_excess_spy"),
        "ret60": trade.get("ret60"),
        "ret5": trade.get("ret5"),
        "near_high_60": trade.get("near_high_60"),
        "volume_ratio_20": trade.get("volume_ratio_20"),
        "realized_volatility_20": trade.get("realized_volatility_20"),
        "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
        "low_extension_support_applied": trade.get("low_extension_support_applied"),
        "high_volatility_support_applied": trade.get("high_volatility_support_applied"),
        "trend_persistence_support_applied": trade.get("trend_persistence_support_applied"),
        "broad_market_entry_date": trade.get("entry_date"),
        "broad_market_exit_date": trade.get("exit_date"),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _broad_market_source_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    universe_state = broad_market.p35._load_tradeable_universe()
    tradeable_universe = set(
        universe_state.get("excluded_tradeable_universe")
        or universe_state.get("tradeable_universe")
        or []
    )
    candidate_universe = broad_market.p35._candidate_universe(tradeable_universe)
    prices = broad_market.p35._load_price_rows(candidate_universe["tickers"])
    indexes = broad_market.p35._index_by_date(prices)

    rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = {}
    diagnostics: dict[str, Any] = {
        "source": BROAD_MARKET_SOURCE,
        "source_experiment_id": BROAD_MARKET_EXPERIMENT_ID,
        "source_artifact": str(BROAD_MARKET_SOURCE_ARTIFACT).replace("\\", "/"),
        "source_family": BROAD_MARKET_FAMILY,
        "candidate_universe_count": len(candidate_universe["tickers"]),
        "accepted_broad_market_profile": {
            "positive_day_ratio_20_min": broad_market.DEFAULT_CONFIG[
                "trend_persistence_positive_day_ratio_20_min"
            ],
            "trend_persistence_notional_scalar": broad_market.DEFAULT_CONFIG[
                "trend_persistence_notional_scalar"
            ],
            "ret20_excess_spy_min": broad_market.PROFILE_CONFIG["ret20_excess_spy_min"],
            "ret60_min": broad_market.PROFILE_CONFIG["ret60_min"],
            "near_high_60_min": broad_market.PROFILE_CONFIG["near_high_60_min"],
            "volume_ratio_20_min": broad_market.PROFILE_CONFIG["volume_ratio_20_min"],
            "decision_close_price_min": broad_market.PROFILE_CONFIG["decision_close_price_min"],
            "hold_days": broad_market.PROFILE_CONFIG["hold_days"],
        },
        "windows": {},
    }
    for label in broad_market.WINDOWS:
        scout = broad_market._simulate_window(
            label=label,
            positive_day_ratio_20_min=broad_market.DEFAULT_CONFIG[
                "trend_persistence_positive_day_ratio_20_min"
            ],
            scalar=broad_market.DEFAULT_CONFIG["trend_persistence_notional_scalar"],
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
        )
        keyed_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for trade in scout["trades"]:
            row = _source_row_from_broad_market_trade(trade)
            signal_date = str(row["signal_date"])
            ticker = str(row["ticker"])
            if not signal_date or not ticker:
                continue
            keyed_rows.setdefault((signal_date, ticker), []).append(row)
        rows_by_window[label] = keyed_rows
        diagnostics["windows"][label] = {
            "trade_count": len(scout["trades"]),
            "source_row_count": sum(len(rows) for rows in keyed_rows.values()),
            "candidate_signal_days": scout["candidate_signal_days"],
            "candidate_signal_count": scout["candidate_signal_count"],
            "max_daily_candidate_count": scout["max_daily_candidate_count"],
            "unique_tickers": len({key[1] for key in keyed_rows}),
        }
    return rows_by_window, diagnostics


def _merged_source_rows() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    existing = consensus.prior._source_rows_by_window()
    merged: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = {
        label: {key: list(rows) for key, rows in keyed.items()}
        for label, keyed in existing.items()
    }
    broad_rows, diagnostics = _broad_market_source_rows_by_window()
    for label, keyed in broad_rows.items():
        target = merged.setdefault(label, {})
        for key, rows in keyed.items():
            target.setdefault(key, []).extend(rows)
    diagnostics["same_date_overlap_with_existing_source_rows"] = {
        label: sum(
            1
            for key in keyed
            if key in existing.get(label, {}) and existing.get(label, {}).get(key)
        )
        for label, keyed in broad_rows.items()
    }
    diagnostics["all_source_row_counts_after_merge"] = {
        label: sum(len(rows) for rows in keyed.values()) for label, keyed in merged.items()
    }
    return merged, diagnostics


def _source_family_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    family_combo_counts = Counter("+".join(trade.get("source_families") or []) for trade in all_trades)
    raw_combo_counts = Counter("+".join(trade.get("source_names") or []) for trade in all_trades)
    broad_confirmed = [
        trade for trade in all_trades if BROAD_MARKET_FAMILY in (trade.get("source_families") or [])
    ]
    broad_only = [
        trade for trade in all_trades if set(trade.get("source_families") or []) == {BROAD_MARKET_FAMILY}
    ]
    return {
        "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
        "source_families": SOURCE_FAMILIES,
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "selected_raw_source_combo_counts": dict(sorted(raw_combo_counts.items())),
        "broad_market_confirmed_trade_count": len(broad_confirmed),
        "broad_market_only_trade_count": len(broad_only),
        "total_trade_count": len(all_trades),
        "all_selected_have_min_family_count": all(
            len(trade.get("source_families") or []) >= consensus.MIN_SOURCE_FAMILY_COUNT
            for trade in all_trades
        ),
    }


def _accepted_comparator(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    artifact = _load_json(REPO_ROOT / CURRENT_ACCEPTED_COMPARATOR_ARTIFACT)
    accepted_after = artifact["aggregate"]["after"]
    accepted_results = {
        str(row["label"]): row["after"] for row in artifact.get("results", []) if isinstance(row, dict)
    }
    after = aggregate["after"]
    by_window: dict[str, dict[str, Any]] = {}
    ev_regression_windows: list[str] = []
    pnl_regression_windows: list[str] = []
    for row in results:
        label = str(row["label"])
        accepted_window = accepted_results.get(label, {})
        candidate_after = row["after"]
        ev_delta = round(
            float(candidate_after.get("expected_value_score") or 0.0)
            - float(accepted_window.get("expected_value_score") or 0.0),
            6,
        )
        pnl_delta = round(
            float(candidate_after.get("total_pnl") or 0.0)
            - float(accepted_window.get("total_pnl") or 0.0),
            2,
        )
        if ev_delta < 0:
            ev_regression_windows.append(label)
        if pnl_delta < 0:
            pnl_regression_windows.append(label)
        by_window[label] = {
            "accepted_expected_value_score": accepted_window.get("expected_value_score"),
            "candidate_expected_value_score": candidate_after.get("expected_value_score"),
            "expected_value_score_delta_vs_accepted": ev_delta,
            "accepted_total_pnl": accepted_window.get("total_pnl"),
            "candidate_total_pnl": candidate_after.get("total_pnl"),
            "total_pnl_delta_vs_accepted": pnl_delta,
        }
    aggregate_ev_delta = round(
        float(after.get("expected_value_score") or 0.0)
        - float(accepted_after.get("expected_value_score") or 0.0),
        6,
    )
    aggregate_pnl_delta = round(
        float(after.get("strategy_total_pnl") or after.get("total_pnl") or 0.0)
        - float(accepted_after.get("strategy_total_pnl") or accepted_after.get("total_pnl") or 0.0),
        2,
    )
    passed = aggregate_ev_delta > 0 and aggregate_pnl_delta > 0 and not ev_regression_windows
    return {
        "artifact": str(CURRENT_ACCEPTED_COMPARATOR_ARTIFACT).replace("\\", "/"),
        "accepted_after": accepted_after,
        "candidate_after": after,
        "aggregate_expected_value_delta_vs_accepted": aggregate_ev_delta,
        "aggregate_total_pnl_delta_vs_accepted": aggregate_pnl_delta,
        "ev_regression_windows_vs_accepted": ev_regression_windows,
        "pnl_regression_windows_vs_accepted": pnl_regression_windows,
        "by_window": by_window,
        "passed": passed,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted broad-market leadership paper candidates may improve the "
            "free-data cross-source consensus when used as an independent "
            "production-visible source family, expanding the candidate pool "
            "without adding noisy tickers."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Meta research prioritizes default-off paper adapters and candidate "
            "pool alpha. Broad-market leadership is already a shared, "
            "default-off paper adapter; this tests it as a new source family "
            "rather than retuning source counts or thresholds."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-016 VCP source-family addition rejected",
            "exp-20260603-017 SEC credible reaction source-family addition rejected",
            "exp-20260603-023 AI optical source-family addition rejected",
            "exp-20260520-004 accepted broad-market trend-persistence paper adapter",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_current_core": "> 0",
            "aggregate_pnl_delta_vs_current_core": "> 0",
            "accepted_comparator": "exp-20260603-014 after aggregate",
            "aggregate_expected_value_delta_vs_accepted": "> 0",
            "aggregate_pnl_delta_vs_accepted": "> 0",
            "per_window_expected_value_vs_accepted": "no regression windows",
            "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
            "survival_rate_floor": 0.05,
            "production_retention": "requires shared adapter parity before promotion",
        },
        "reproducibility": (
            "The runner rebuilds broad-market source rows from the accepted "
            "shared broad-market helper and persists source diagnostics, "
            "target trades, window metrics, and accepted-comparator deltas."
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    accepted = payload["accepted_comparator"]
    prediction = {
        "success_probability": 0.16,
        "expected_ev_delta": 0.25,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "same_date_overlap_sparse",
            "accepted_comparator_not_beaten",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Broad-market sleeve is accepted and production-visible, but recent "
            "source-family additions have usually failed against the strong "
            "accepted consensus comparator."
        ),
        "recorded_at": "2026-06-04T01:12:00+00:00",
    }
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "broad_market_leadership_consensus_source_family_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_source_family_addition",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 4,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "accepted_shared_broad_market_paper_source_family",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_ev_delta_vs_accepted": accepted["aggregate_expected_value_delta_vs_accepted"],
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "actual_pnl_delta_vs_accepted": accepted["aggregate_total_pnl_delta_vs_accepted"],
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else "accepted_comparator_or_gate4_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "aggregate_expected_value_delta_vs_accepted": accepted[
                "aggregate_expected_value_delta_vs_accepted"
            ],
            "aggregate_total_pnl_delta_vs_accepted": accepted["aggregate_total_pnl_delta_vs_accepted"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "broad_market_confirmed_trade_count": payload["source_family_summary"][
                "broad_market_confirmed_trade_count"
            ],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "expected_value_delta_vs_accepted": accepted["by_window"][row["label"]][
                    "expected_value_score_delta_vs_accepted"
                ],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "strategy_total_pnl_delta_vs_accepted": accepted["by_window"][row["label"]][
                    "total_pnl_delta_vs_accepted"
                ],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            str(OUT_JSON).replace("\\", "/"),
            str(ARTIFACT_MD).replace("\\", "/"),
            str(LOG_JSON).replace("\\", "/"),
            str(TICKET_JSON).replace("\\", "/"),
            str(DOC_TICKET_JSON).replace("\\", "/"),
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    accepted = payload["accepted_comparator"]
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Consensus Source Family",
        "",
        f"Decision: `{payload['gate4']['decision']}`.",
        "",
        "Single causal variable: add `BROAD_MARKET_LEADERSHIP_PAPER` as one independent source family to the accepted free-data consensus replay.",
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Accepted EV | dEV vs Accepted | dPnL | dPnL vs Accepted | Targets |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        label = row["label"]
        accepted_row = accepted["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {acev:.4f} | {dacev:+.4f} | ${dpnl:+,.2f} | ${dacpnl:+,.2f} | {targets} |".format(
                label=label,
                bev=float(row["before"]["expected_value_score"]),
                aev=float(row["after"]["expected_value_score"]),
                dev=float(row["comparison"]["expected_value_score_delta"]),
                acev=float(accepted_row["accepted_expected_value_score"]),
                dacev=float(accepted_row["expected_value_score_delta_vs_accepted"]),
                dpnl=float(row["comparison"]["strategy_total_pnl_delta"]),
                dacpnl=float(accepted_row["total_pnl_delta_vs_accepted"]),
                targets=int(row["target_trade_count"]),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core baseline: `{payload['aggregate']['comparison']['expected_value_score_delta']}`",
            f"- PnL delta vs core baseline: `${payload['aggregate']['comparison']['strategy_total_pnl_delta']:,.2f}`",
            f"- EV delta vs accepted comparator: `{accepted['aggregate_expected_value_delta_vs_accepted']}`",
            f"- PnL delta vs accepted comparator: `${accepted['aggregate_total_pnl_delta_vs_accepted']:,.2f}`",
            f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
            f"- Broad-market confirmed target trades: `{payload['source_family_summary']['broad_market_confirmed_trade_count']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(PRODUCTION_IMPACT, indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_artifacts(payload: dict[str, Any]) -> None:
    markdown = _artifact_markdown(payload)
    _write_text(REPO_ROOT / CARD_MD, markdown)
    _write_text(REPO_ROOT / ARTIFACT_MD, markdown)


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    abs_path = REPO_ROOT / path
    ticket = _load_json(abs_path) if abs_path.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(ARTIFACT_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(abs_path, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    path = REPO_ROOT / REGISTRY_JSON
    if not path.exists():
        return
    registry = _load_json(path)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON).replace("\\", "/")
            item["log"] = str(LOG_JSON).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    _write_json(path, registry)


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows, source_diagnostics = _merged_source_rows()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = consensus._run_windows(baselines, source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = _source_family_summary(target_trades_by_window)
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    accepted_comparator = _accepted_comparator(aggregate, results)

    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_broad_market_source_family_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the independent source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True

    gate4["accepted_comparator"] = {
        "passed": accepted_comparator["passed"],
        "aggregate_expected_value_delta_vs_accepted": accepted_comparator[
            "aggregate_expected_value_delta_vs_accepted"
        ],
        "aggregate_total_pnl_delta_vs_accepted": accepted_comparator[
            "aggregate_total_pnl_delta_vs_accepted"
        ],
        "ev_regression_windows_vs_accepted": accepted_comparator[
            "ev_regression_windows_vs_accepted"
        ],
    }
    gate4["gates"]["accepted_comparator_beaten"] = bool(accepted_comparator["passed"])
    if gate4["passed"] and not accepted_comparator["passed"]:
        gate4["passed"] = False
        gate4["decision"] = "rejected_broad_market_consensus_source_family_underperformed_accepted_comparator"
        gate4["rationale"] = (
            "The candidate improved versus the core baseline but failed the current accepted "
            "free-data consensus comparator from exp-20260603-014."
        )
        gate4["requires_parity_before_promotion"] = False
    elif gate4["passed"]:
        gate4["decision"] = "positive_broad_market_consensus_source_family_lead_requires_shared_adapter"
        gate4["rationale"] = (
            "Canonical three-window replay beat both the core baseline and the current accepted "
            "consensus comparator. No production behavior changed; promotion requires shared "
            "live/backtest consensus adapter parity first."
        )
        gate4["requires_parity_before_promotion"] = True

    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
        "source_diagnostics": source_diagnostics,
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "broad_market_source": BROAD_MARKET_SOURCE,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
        },
        "aggregate": aggregate,
        "accepted_comparator": accepted_comparator,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(REPO_ROOT / OUT_JSON, payload)
    _write_json(REPO_ROOT / BEFORE_JSON, aggregate["before"])
    _write_json(REPO_ROOT / AFTER_JSON, aggregate["after"])
    _write_json(REPO_ROOT / ACCEPTED_COMPARATOR_JSON, accepted_comparator)
    record = _experiment_log_record(payload)
    _write_json(REPO_ROOT / LOG_JSON, record)
    _write_artifacts(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_ticket(DOC_TICKET_JSON, payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(REPO_ROOT / EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "accepted_comparator": gate4["accepted_comparator"],
                "source_family_summary": source_family_summary,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
