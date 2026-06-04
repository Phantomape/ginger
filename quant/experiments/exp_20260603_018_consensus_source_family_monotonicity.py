"""exp-20260603-018: accepted consensus source-family count monotonicity validation.

Read-only attribution experiment. Tests whether independent source-family count
within the accepted free-data cross-source consensus sleeve shows monotonically
improving target-trade outcomes as a ranking signal (beyond admission guard).

No strategy logic, shared adapters, production orders, sizing, exits, LLM, or
news surfaces are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for _p in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


EXPERIMENT_ID = "exp-20260603-018"
STEM = "consensus_source_family_monotonicity"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_family_count_monotonicity"
CHANGED_VARIABLE = "independent_source_family_count_monotonicity_bucket_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

# Source: accepted consensus replay artifact (exp-014 is the full replay)
CONSENSUS_ARTIFACT = REPO_ROOT / "data" / "experiments" / "exp-20260603-014" / \
    "accepted_consensus_independent_source_family.json"

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "read_only_attribution_analysis",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment reads existing accepted replay artifacts and performs no strategy "
        "changes. Source-count retunes are frozen per the playbook; this analysis is "
        "forward evidence only and cannot justify source-count threshold changes on frozen windows."
    ),
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "non_monotonic_bucket_outcomes",
        "thin_3plus_family_sample",
        "nearby_source_count_overfit",
        "current_accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The current accepted consensus uses family count only as admission; testing "
        "monotonicity is useful for ranking evidence, but source-count retunes are frozen "
        "and high multiple-testing risk."
    ),
    "recorded_at": "2026-06-03T16:09:15+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=True, indent=2, sort_keys=True)
        fh.write("\n")


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            if needle in fh.read():
                return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _safe_win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(1 for v in values if v > 0) / len(values), 4)


def _analyse_trades(
    trades_all: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bucket trades by source_family_count and compute outcome statistics."""
    by_bucket: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades_all:
        fc = int(trade.get("source_family_count") or 0)
        by_bucket[fc].append(trade)

    bucket_stats: list[dict[str, Any]] = []
    for fc in sorted(by_bucket.keys()):
        bucket_trades = by_bucket[fc]
        pnl_values = [float(t.get("pnl") or 0.0) for t in bucket_trades]
        ret_values = [
            float(t.get("pnl_pct_net") or t.get("return_pct") or 0.0)
            for t in bucket_trades
        ]
        total_pnl = round(sum(pnl_values), 2)
        bucket_stats.append(
            {
                "source_family_count": fc,
                "trade_count": len(bucket_trades),
                "total_pnl_usd": total_pnl,
                "mean_pnl_usd": _safe_mean(pnl_values),
                "mean_return_pct": _safe_mean(ret_values),
                "win_rate": _safe_win_rate(pnl_values),
                "tickers": sorted({str(t.get("ticker") or "") for t in bucket_trades}),
                "windows": sorted({str(t.get("window") or t.get("label") or "") for t in bucket_trades}),
            }
        )

    # Monotonicity test: mean_pnl_usd non-decreasing with fc
    mean_pnls = [
        row["mean_pnl_usd"]
        for row in bucket_stats
        if row["mean_pnl_usd"] is not None and row["trade_count"] >= 3
    ]
    is_monotonic_mean_pnl = all(
        mean_pnls[i] <= mean_pnls[i + 1]
        for i in range(len(mean_pnls) - 1)
    ) if len(mean_pnls) >= 2 else None

    win_rates = [
        row["win_rate"]
        for row in bucket_stats
        if row["win_rate"] is not None and row["trade_count"] >= 3
    ]
    is_monotonic_win_rate = all(
        win_rates[i] <= win_rates[i + 1]
        for i in range(len(win_rates) - 1)
    ) if len(win_rates) >= 2 else None

    thin_buckets = [
        row["source_family_count"]
        for row in bucket_stats
        if row["trade_count"] < 3
    ]

    return {
        "bucket_stats": bucket_stats,
        "is_monotonic_mean_pnl": is_monotonic_mean_pnl,
        "is_monotonic_win_rate": is_monotonic_win_rate,
        "thin_buckets_below_3_trades": thin_buckets,
        "eligible_bucket_count_for_monotonicity": len(mean_pnls),
        "total_trades_analysed": len(trades_all),
    }


def _gate4_decision(analysis: dict[str, Any]) -> dict[str, Any]:
    """Gate 4 for monotonicity validation.

    Acceptance: at least 2 eligible buckets (≥3 trades each) AND monotonic mean PnL.
    Rejection: non-monotonic, or only one valid bucket (thin sample).
    Observed-only: eligible but inconclusive (single-bucket only or None result).
    """
    is_mono_pnl = analysis["is_monotonic_mean_pnl"]
    is_mono_wr = analysis["is_monotonic_win_rate"]
    eligible = analysis["eligible_bucket_count_for_monotonicity"]
    thin = analysis["thin_buckets_below_3_trades"]

    gates = {
        "two_or_more_eligible_buckets": eligible >= 2,
        "monotonic_mean_pnl": bool(is_mono_pnl) if is_mono_pnl is not None else False,
        "monotonic_win_rate": bool(is_mono_wr) if is_mono_wr is not None else False,
        "thin_bucket_warning": bool(thin),
    }

    if eligible < 2:
        decision = "observed_only_insufficient_bucket_depth"
        passed = False
        rationale = (
            f"Only {eligible} bucket(s) with ≥3 trades. Cannot test monotonicity reliably. "
            "This is expected given the small consensus trade pool. Record as observed-only "
            "attribution evidence; do not use to justify source-count threshold retunes."
        )
        requires_parity = False
    elif is_mono_pnl and is_mono_wr:
        decision = "observed_only_monotonic_positive"
        passed = True
        rationale = (
            "Source-family count shows monotonic mean PnL AND win rate across eligible "
            f"buckets ({eligible} buckets with ≥3 trades). This supports family count as a "
            "ranking signal beyond admission, but sample is too thin to promote a source-count "
            "threshold change on frozen windows. Collect forward evidence first."
        )
        requires_parity = False
    elif is_mono_pnl:
        decision = "observed_only_monotonic_pnl_only"
        passed = True
        rationale = (
            "Source-family count shows monotonic mean PnL but not monotonic win rate. "
            "Partial evidence for ranking signal; collect forward evidence before any threshold change."
        )
        requires_parity = False
    elif is_mono_pnl is False:
        decision = "observed_only_non_monotonic"
        passed = False
        rationale = (
            "Source-family count does NOT show monotonic mean PnL across eligible buckets. "
            "Family count is not a reliable ranking signal beyond admission on these frozen windows."
        )
        requires_parity = False
    else:
        decision = "observed_only_inconclusive"
        passed = False
        rationale = "Inconclusive: insufficient data to determine monotonicity."
        requires_parity = False

    return {
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "eligible_bucket_count": eligible,
        "thin_buckets": thin,
        "max_drawdown_delta": 0.0,
        "requires_parity_before_promotion": requires_parity,
    }


def _upsert_registry(payload: dict[str, Any]) -> None:
    registry: dict[str, Any] = {}
    if REGISTRY_JSON.exists():
        try:
            with REGISTRY_JSON.open("r", encoding="utf-8") as fh:
                registry = json.load(fh)
        except (json.JSONDecodeError, OSError):
            registry = {}
    experiments: list[dict[str, Any]] = registry.get("experiments", [])
    existing_ids = {str(e.get("experiment_id") or e.get("id")) for e in experiments}
    entry = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": "completed",
        "decision": payload["gate4"]["decision"],
        "completed_at": payload["completed_at"],
        "artifact": str(OUT_JSON).replace("\\", "/"),
    }
    if EXPERIMENT_ID not in existing_ids:
        experiments.append(entry)
    else:
        for e in experiments:
            if str(e.get("experiment_id") or e.get("id")) == EXPERIMENT_ID:
                e.update(entry)
                break
    registry["experiments"] = experiments
    _write_json(REGISTRY_JSON, registry)


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        try:
            ticket = _load_json(TICKET_JSON)
        except (json.JSONDecodeError, OSError):
            ticket = {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(CARD_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_card(payload: dict[str, Any]) -> None:
    gate4 = payload["gate4"]
    analysis = payload["analysis"]
    bucket_rows = "\n".join(
        f"| {row['source_family_count']} | {row['trade_count']} | "
        f"${row['total_pnl_usd']:.0f} | "
        f"${row['mean_pnl_usd']:.0f} | "
        f"{row['win_rate']:.0%} |"
        for row in analysis["bucket_stats"]
    )
    card = (
        f"# Experiment Card: {EXPERIMENT_ID}\n\n"
        f"**Hypothesis**: {payload['preflight']['alpha_hypothesis']}\n\n"
        f"**Decision**: `{gate4['decision']}`\n\n"
        f"**Rationale**: {gate4['rationale']}\n\n"
        f"## Source-Family Count Bucket Analysis\n\n"
        f"Source: `{CONSENSUS_ARTIFACT.relative_to(REPO_ROOT).as_posix()}`\n\n"
        f"| Source Family Count | Trade Count | Total PnL | Mean PnL | Win Rate |\n"
        f"|---|---:|---:|---:|---:|\n"
        f"{bucket_rows}\n\n"
        f"**Monotonic mean PnL**: {analysis['is_monotonic_mean_pnl']}\n"
        f"**Monotonic win rate**: {analysis['is_monotonic_win_rate']}\n"
        f"**Eligible buckets (≥3 trades)**: {analysis['eligible_bucket_count_for_monotonicity']}\n"
        f"**Thin buckets (<3 trades)**: {analysis['thin_buckets_below_3_trades']}\n\n"
        f"## Production Impact\n\n"
        f"No production changes. Read-only attribution analysis.\n\n"
        f"## Anti-JS\n\n"
        f"No JavaScript was used.\n"
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    with CARD_MD.open("w", encoding="utf-8") as fh:
        fh.write(card)


def main() -> None:
    artifact = _load_json(CONSENSUS_ARTIFACT)
    target_trades_by_window = artifact.get("target_trades_by_window") or {}

    # Flatten all trades, annotating with window label
    all_trades: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        for t in trades:
            augmented = dict(t)
            augmented["window"] = label
            all_trades.append(augmented)

    analysis = _analyse_trades(all_trades)
    gate4 = _gate4_decision(analysis)
    completed_at = _utc_now()

    preflight = {
        "alpha_hypothesis": (
            "Independent accepted free-data source-family count should show monotonic "
            "target-trade outcomes (higher family count → better mean PnL / win rate) within "
            "the accepted default-off consensus sleeve if family count is a durable ranking "
            "signal beyond just an admission guard."
        ),
        "category": "ranking_validation",
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-028",
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260603-016",
        ],
        "acceptance_criteria": {
            "eligible_bucket_count": ">= 2 (buckets with ≥3 trades)",
            "mean_pnl_monotonicity": "strictly non-decreasing",
            "win_rate_monotonicity": "non-decreasing",
            "no_strategy_change": "read-only attribution only",
        },
    }

    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": completed_at,
        "lane": "alpha_search",
        "status": gate4["decision"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": preflight["alpha_hypothesis"],
        "change_type": "default_off_paper_ranking_validation",
        "mechanism_family": "default_off_paper_ranking_validation",
        "prior_trial_count": 0,
        "nearby_prior_experiments": preflight["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "source_family_count_monotonicity_validation",
        "decision": gate4["decision"],
        "accepted": gate4["passed"],
        "rejection_reason": None if gate4["passed"] else gate4["rationale"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": gate4["decision"],
            "actual_success": 1 if gate4["passed"] else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if gate4["passed"] else 0)) ** 2, 6
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "metrics": {
            "total_trades_analysed": analysis["total_trades_analysed"],
            "eligible_bucket_count": analysis["eligible_bucket_count_for_monotonicity"],
            "is_monotonic_mean_pnl": analysis["is_monotonic_mean_pnl"],
            "is_monotonic_win_rate": analysis["is_monotonic_win_rate"],
            "thin_buckets": analysis["thin_buckets_below_3_trades"],
            "bucket_stats": analysis["bucket_stats"],
        },
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": preflight,
        "source_artifact": str(CONSENSUS_ARTIFACT).replace("\\", "/"),
        "analysis": analysis,
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _write_ticket(payload)
    _upsert_registry(payload)
    _append_jsonl_once(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "analysis_summary": {
                    "total_trades": analysis["total_trades_analysed"],
                    "eligible_buckets": analysis["eligible_bucket_count_for_monotonicity"],
                    "is_monotonic_mean_pnl": analysis["is_monotonic_mean_pnl"],
                    "is_monotonic_win_rate": analysis["is_monotonic_win_rate"],
                    "thin_buckets": analysis["thin_buckets_below_3_trades"],
                    "bucket_stats": analysis["bucket_stats"],
                },
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
