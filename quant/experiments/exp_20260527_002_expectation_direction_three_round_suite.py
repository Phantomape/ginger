"""exp-20260527-002..010: three-round expectation direction suite.

Observed-only alpha research for the three sub-directions in
docs/alpha_direction_expectation_residual_leadership.md:

1. Expectation revision velocity.
2. Post-earnings drift continuation.
3. Residual leadership.

Each payload changes exactly one attribution variable and keeps strategy
behavior unchanged: no entries, exits, ranking, sizing, LLM/news prompts,
paper sleeves, or orders are altered.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    build_price_lookup,
)
from exp_20260526_030_expectation_direction_untried_ideas_suite import (  # noqa: E402
    build_context,
    field_coverage,
)


MECHANISM_FAMILY = "expectation_drift_residual_pead"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
ANTI_JS = "No JavaScript was used."
BASELINE = {
    "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
    "baseline_artifact": "data/experiments/exp-20260517-009/",
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
}
NEARBY_PRIORS = [
    "exp-20260525-017",
    "exp-20260525-021",
    "exp-20260525-031",
    "exp-20260525-034",
    "exp-20260526-006",
    "exp-20260526-030",
    "exp-20260526-031",
    "exp-20260526-032",
    "exp-20260526-033",
    "exp-20260526-034",
    "exp-20260526-035",
    "exp-20260526-036",
]
MIN_BUCKET_CLOSED_5D = 8
MIN_BUCKET_CLOSED_10D = 5
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50


EXPERIMENT_SPECS = [
    {
        "experiment_id": "exp-20260527-002",
        "direction": "expectation_revision_velocity",
        "round": 1,
        "stem": "eps_7d_magnitude_attribution",
        "title": "EPS 7d Magnitude Attribution",
        "trial_family": "expectation_revision_velocity_three_round",
        "changed_variable": "eps_7d_revision_magnitude_bucket_v1",
        "hypothesis": "Larger PIT 7d EPS estimate revisions should beat smaller positive revisions if revision velocity is an investable alpha clue.",
        "bucket_key": "eps_7d_revision_magnitude_bucket",
        "preferred_bucket": "primary_7d_high_magnitude",
        "comparison_bucket": "primary_7d_low_magnitude",
        "next_evidence_needed": "If high magnitude is not monotonic, persist richer revenue/analyst velocity fields instead of retuning EPS-only thresholds.",
    },
    {
        "experiment_id": "exp-20260527-003",
        "direction": "expectation_revision_velocity",
        "round": 2,
        "stem": "eps_prev_confirmation_attribution",
        "title": "EPS Previous-Delta Confirmation Attribution",
        "trial_family": "expectation_revision_velocity_three_round",
        "changed_variable": "eps_prev_delta_confirmation_bucket_v1",
        "hypothesis": "A positive 7d EPS revision should be stronger when the prior same-event delta was already positive rather than flat.",
        "bucket_key": "eps_prev_delta_confirmation_bucket",
        "preferred_bucket": "primary_7d_with_prev_positive",
        "comparison_bucket": "primary_7d_prev_flat",
        "next_evidence_needed": "Persist daily same-event revision paths so acceleration can be measured directly rather than inferred from prev-delta only.",
    },
    {
        "experiment_id": "exp-20260527-004",
        "direction": "expectation_revision_velocity",
        "round": 3,
        "stem": "same_event_history_depth_attribution",
        "title": "Same-Event History Depth Attribution",
        "trial_family": "expectation_revision_velocity_three_round",
        "changed_variable": "same_event_history_depth_bucket_v1",
        "hypothesis": "Revision rows with deeper same-event history should be more reliable than shallow-history rows.",
        "bucket_key": "same_event_history_depth_bucket",
        "preferred_bucket": "primary_7d_history_ge_10",
        "comparison_bucket": "primary_7d_history_lt_10",
        "next_evidence_needed": "Keep de-duplicated PIT expectation snapshots; shallow history should stay data-accumulation only.",
    },
    {
        "experiment_id": "exp-20260527-005",
        "direction": "pead_continuation",
        "round": 1,
        "stem": "pead_earnings_date_readiness",
        "title": "PEAD Earnings-Date Readiness",
        "trial_family": "pead_continuation_three_round",
        "changed_variable": "pead_last_earnings_date_coverage_v1",
        "hypothesis": "A T+2 to T+15 PEAD sleeve is blocked unless PIT rows carry a last earnings date and enough eligible positive-revision residual leaders.",
        "bucket_key": "pead_readiness_bucket",
        "preferred_bucket": "eligible_t2_t15_primary_residual",
        "comparison_bucket": "blocked_missing_last_earnings_date",
        "next_evidence_needed": "Persist last reported earnings date and report-time semantics in the PIT revision ledger before any PEAD paper sleeve.",
    },
    {
        "experiment_id": "exp-20260527-006",
        "direction": "pead_continuation",
        "round": 2,
        "stem": "post_revision_immediate_failure_proxy",
        "title": "Post-Revision Immediate Failure Proxy",
        "trial_family": "pead_continuation_three_round",
        "changed_variable": "post_revision_2d_failure_proxy_v1",
        "hypothesis": "Positive-revision rows that avoid a fast 2-day close-to-close failure should have better 5d/10d continuation.",
        "bucket_key": "post_revision_2d_failure_proxy_bucket",
        "preferred_bucket": "primary_7d_no_fast_2d_failure",
        "comparison_bucket": "primary_7d_fast_2d_failure",
        "next_evidence_needed": "Replace this close-to-close proxy with true post-earnings gap and T+2/T+5 context once earnings dates are PIT-joined.",
    },
    {
        "experiment_id": "exp-20260527-007",
        "direction": "pead_continuation",
        "round": 3,
        "stem": "post_revision_candidate_conversion_lag",
        "title": "Post-Revision Candidate Conversion Lag",
        "trial_family": "pead_continuation_three_round",
        "changed_variable": "post_revision_candidate_hit_lag_v1",
        "hypothesis": "Primary positive revision rows that convert into Ginger candidates within 3 to 10 trading days should be stronger PEAD watchlist rows.",
        "bucket_key": "post_revision_candidate_conversion_bucket",
        "preferred_bucket": "primary_7d_candidate_hit_10td",
        "comparison_bucket": "primary_7d_no_candidate_hit_10td",
        "next_evidence_needed": "Keep candidate-hit lag as read-only until it has enough positive revision conversions and earnings-date context.",
    },
    {
        "experiment_id": "exp-20260527-008",
        "direction": "residual_leadership",
        "round": 1,
        "stem": "residual_strength_magnitude_attribution",
        "title": "Residual Strength Magnitude Attribution",
        "trial_family": "residual_leadership_three_round",
        "changed_variable": "residual_strength_magnitude_bucket_v1",
        "hypothesis": "Residual leadership should improve as residual strength rises, but extreme residual scores may reveal overextension rather than confirmation.",
        "bucket_key": "residual_strength_magnitude_bucket",
        "preferred_bucket": "primary_7d_residual_mid",
        "comparison_bucket": "primary_7d_residual_extreme",
        "next_evidence_needed": "Treat extreme residual leadership as overextension context unless mid-strength residuals beat it across horizons.",
    },
    {
        "experiment_id": "exp-20260527-009",
        "direction": "residual_leadership",
        "round": 2,
        "stem": "spy_qqq_residual_agreement_attribution",
        "title": "SPY/QQQ Residual Agreement Attribution",
        "trial_family": "residual_leadership_three_round",
        "changed_variable": "spy_qqq_residual_agreement_bucket_v1",
        "hypothesis": "Names leading both SPY and QQQ should be cleaner residual leaders than names leading only one benchmark.",
        "bucket_key": "spy_qqq_residual_agreement_bucket",
        "preferred_bucket": "primary_7d_leads_spy_and_qqq",
        "comparison_bucket": "primary_7d_leads_only_one_benchmark",
        "next_evidence_needed": "Persist sector/theme residuals so residual leadership is not reduced to a SPY/QQQ-only proxy.",
    },
    {
        "experiment_id": "exp-20260527-010",
        "direction": "residual_leadership",
        "round": 3,
        "stem": "residual_state_quality_attribution",
        "title": "Residual State Quality Attribution",
        "trial_family": "residual_leadership_three_round",
        "changed_variable": "residual_state_quality_bucket_v1",
        "hypothesis": "Strong residual leaders should beat neutral and beta-lagging positive-revision rows if residual leadership is additive.",
        "bucket_key": "residual_state_quality_bucket",
        "preferred_bucket": "primary_7d_strong_residual_leader",
        "comparison_bucket": "primary_7d_neutral_or_beta_lagging",
        "next_evidence_needed": "If strong residual leadership does not beat neutral/beta-lagging rows, do not use residual leadership as a confirmation top-up.",
    },
]

SPEC_BY_ID = {spec["experiment_id"]: spec for spec in EXPERIMENT_SPECS}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _paths(spec: dict[str, Any]) -> dict[str, Path]:
    exp_id = spec["experiment_id"]
    stem = spec["stem"]
    return {
        "json": REPO_ROOT / "data" / "experiments" / exp_id / f"{stem}.json",
        "log": REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json",
        "ticket": REPO_ROOT / "experiments" / "tickets" / f"{exp_id}.json",
        "doc_ticket": REPO_ROOT / "docs" / "experiments" / "tickets" / f"{exp_id}.json",
        "artifact": REPO_ROOT / "experiments" / "artifacts" / f"{exp_id}_{stem}.md",
    }


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    exp_id = payload["experiment_id"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(compact + "\n", encoding="utf-8")
        return

    rows: list[str] = []
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line.rstrip("\n"))
                continue
            if row.get("experiment_id") == exp_id:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line.rstrip("\n"))
    if not replaced:
        rows.append(compact)
    tmp = path.with_suffix(path.suffix + f".{exp_id}.tmp")
    tmp.write_text("\n".join(rows) + "\n", encoding="utf-8")
    try:
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        with path.open("a", encoding="utf-8") as dst:
            dst.write(compact + "\n")


def _upsert_registry(payload: dict[str, Any], paths: dict[str, Path]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-expectation-three-round-suite",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(paths["ticket"]),
        "log_file": _repo_rel(paths["log"]),
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(paths["artifact"]),
            "json": _repo_rel(paths["json"]),
            "summary": payload["gate"].get("reason"),
        },
    }
    experiments = registry.setdefault("experiments", [])
    for idx, row in enumerate(experiments):
        if row.get("experiment_id") == payload["experiment_id"]:
            experiments[idx] = {**row, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    EXPERIMENT_REGISTRY.write_text(
        json.dumps(_safe(registry), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _closed_values(rows: list[dict[str, Any]], horizon_key: str) -> list[tuple[dict[str, Any], float, float]]:
    values = []
    for row in rows:
        outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
        if not outcome.get("closed"):
            continue
        ret = _float(outcome.get("return"))
        pnl = _float(outcome.get("pnl_proxy"))
        if ret is None or pnl is None:
            continue
        values.append((row, ret, pnl))
    return values


def summarize_rows(rows: list[dict[str, Any]], horizon_key: str) -> dict[str, Any]:
    values = _closed_values(rows, horizon_key)
    returns = [ret for _row, ret, _pnl in values]
    positive = [(row, pnl) for row, _ret, pnl in values if pnl > 0]
    positive_total = sum(pnl for _row, pnl in positive)
    top5_positive = sum(pnl for _row, pnl in sorted(positive, key=lambda item: item[1], reverse=True)[:5])
    by_ticker_positive: Counter[str] = Counter()
    for row, pnl in positive:
        by_ticker_positive[str(row.get("ticker") or "missing")] += pnl
    worst = min(values, key=lambda item: item[1], default=None)
    return {
        "closed_outcomes": len(values),
        "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6) if returns else None,
        "tail_loss": round(min(returns), 6) if returns else None,
        "total_pnl_proxy": round(sum(pnl for _row, _ret, pnl in values), 2) if values else None,
        "avg_pnl_proxy": round(sum(pnl for _row, _ret, pnl in values) / len(values), 2) if values else None,
        "top5_positive_contribution_share": (
            round(top5_positive / positive_total, 6) if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            round(max(by_ticker_positive.values()) / positive_total, 6)
            if positive_total > 0 and by_ticker_positive
            else None
        ),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2) for ticker, value in sorted(by_ticker_positive.items())
        },
        "worst_row": compact_row(worst[0], horizon_key) if worst else None,
    }


def summarize_buckets(
    rows: list[dict[str, Any]],
    bucket_key: str,
    bucket_order: list[str],
    horizons: tuple[str, ...] = ("1d", "2d", "5d", "10d", "20d"),
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(bucket_key) or "missing")].append(row)
    ordered = list(bucket_order)
    for bucket in sorted(grouped):
        if bucket not in ordered:
            ordered.append(bucket)
    summary = {}
    for bucket in ordered:
        members = grouped.get(bucket, [])
        summary[bucket] = {
            "row_count": len(members),
            "ticker_count": len({row.get("ticker") for row in members}),
            "ticker_row_counts": dict(Counter(str(row.get("ticker") or "missing") for row in members)),
            "horizons": {horizon: summarize_rows(members, horizon) for horizon in horizons},
        }
    return summary


def compact_row(row: dict[str, Any], horizon_key: str | None = None) -> dict[str, Any]:
    out = {
        "as_of_date": row.get("as_of_date"),
        "ticker": row.get("ticker"),
        "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
        "primary_expectation_positive": row.get("primary_expectation_positive"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "same_event_history_count": row.get("same_event_history_count"),
        "residual_state": row.get("residual_state"),
        "residual_strength_score": row.get("residual_strength_score"),
        "ret20_excess_spy": row.get("ret20_excess_spy"),
        "ret20_excess_qqq": row.get("ret20_excess_qqq"),
        "pead_status": row.get("pead_status"),
        "candidate_hit_3td": row.get("candidate_hit_3td"),
        "candidate_hit_10td": row.get("candidate_hit_10td"),
    }
    if horizon_key:
        outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
        out.update(
            {
                "forward_return": outcome.get("return"),
                "pnl_proxy": outcome.get("pnl_proxy"),
                "future_date": outcome.get("future_date"),
            }
        )
    return out


def with_short_forward_outcomes(rows: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    prices = build_price_lookup(data_dir)
    enriched = []
    for row in rows:
        next_row = dict(row)
        forward = dict(row.get("forward_outcomes") or {})
        effective = row.get("watchlist_effective_trade_date")
        ticker = row.get("ticker")
        for horizon in (1, 2):
            key = f"{horizon}d"
            if key not in forward:
                if effective and ticker:
                    forward[key] = prices.forward_return(str(ticker), str(effective), horizon)
                else:
                    forward[key] = {
                        "closed": False,
                        "return": None,
                        "pnl_proxy": None,
                        "future_date": None,
                        "gap_reason": "missing_effective_trade_date",
                    }
        next_row["forward_outcomes"] = forward
        enriched.append(next_row)
    return enriched


def is_primary(row: dict[str, Any]) -> bool:
    return row.get("primary_expectation_positive") is True


def bucket_eps_7d_magnitude(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    delta = _float(row.get("eps_estimate_delta_7d"))
    if delta is None:
        return "primary_7d_missing_delta"
    if delta >= 0.10:
        return "primary_7d_high_magnitude"
    if delta >= 0.03:
        return "primary_7d_mid_magnitude"
    return "primary_7d_low_magnitude"


def bucket_prev_confirmation(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    prev = _float(row.get("eps_estimate_delta_prev"))
    if prev is None:
        return "primary_7d_prev_missing"
    if prev > 0:
        return "primary_7d_with_prev_positive"
    if prev < 0:
        return "primary_7d_prev_negative_reversal"
    return "primary_7d_prev_flat"


def bucket_history_depth(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    count = _float(row.get("same_event_history_count"))
    if count is None:
        return "primary_7d_history_missing"
    if count >= 10:
        return "primary_7d_history_ge_10"
    return "primary_7d_history_lt_10"


def bucket_pead_readiness(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    status = str(row.get("pead_status") or "missing_pead_status")
    if status == "inside_t2_t15_after_earnings" and row.get("residual_leader"):
        return "eligible_t2_t15_primary_residual"
    if status == "inside_t2_t15_after_earnings":
        return "eligible_t2_t15_primary_non_residual"
    return f"blocked_{status}"


def bucket_fast_failure(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    outcome = (row.get("forward_outcomes") or {}).get("2d") or {}
    ret = _float(outcome.get("return"))
    if ret is None:
        return "primary_7d_missing_2d_outcome"
    if ret <= -0.02:
        return "primary_7d_fast_2d_failure"
    return "primary_7d_no_fast_2d_failure"


def bucket_candidate_conversion(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    if row.get("candidate_hit_3td") is True:
        return "primary_7d_candidate_hit_3td"
    if row.get("candidate_hit_10td") is True:
        return "primary_7d_candidate_hit_10td"
    if row.get("candidate_hit_10td") is False:
        return "primary_7d_no_candidate_hit_10td"
    return "primary_7d_candidate_hit_unknown"


def bucket_residual_magnitude(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    score = _float(row.get("residual_strength_score"))
    if score is None:
        return "primary_7d_residual_missing"
    if score >= 0.35:
        return "primary_7d_residual_extreme"
    if score > 0:
        return "primary_7d_residual_mid"
    return "primary_7d_residual_nonpositive"


def bucket_spy_qqq_agreement(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    spy = _float(row.get("ret20_excess_spy"))
    qqq = _float(row.get("ret20_excess_qqq"))
    if spy is None or qqq is None:
        return "primary_7d_missing_spy_or_qqq"
    if spy > 0 and qqq > 0:
        return "primary_7d_leads_spy_and_qqq"
    if spy > 0 or qqq > 0:
        return "primary_7d_leads_only_one_benchmark"
    return "primary_7d_leads_neither_benchmark"


def bucket_residual_state_quality(row: dict[str, Any]) -> str:
    if not is_primary(row):
        return "not_primary_7d_positive"
    state = str(row.get("residual_state") or "missing")
    if state == "strong_residual_leader":
        return "primary_7d_strong_residual_leader"
    if state == "residual_leader":
        return "primary_7d_residual_leader"
    if state in {"neutral", "beta_lagging"}:
        return "primary_7d_neutral_or_beta_lagging"
    return f"primary_7d_{state}"


BUCKETERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "eps_7d_revision_magnitude_bucket": bucket_eps_7d_magnitude,
    "eps_prev_delta_confirmation_bucket": bucket_prev_confirmation,
    "same_event_history_depth_bucket": bucket_history_depth,
    "pead_readiness_bucket": bucket_pead_readiness,
    "post_revision_2d_failure_proxy_bucket": bucket_fast_failure,
    "post_revision_candidate_conversion_bucket": bucket_candidate_conversion,
    "residual_strength_magnitude_bucket": bucket_residual_magnitude,
    "spy_qqq_residual_agreement_bucket": bucket_spy_qqq_agreement,
    "residual_state_quality_bucket": bucket_residual_state_quality,
}

BUCKET_ORDERS = {
    "eps_7d_revision_magnitude_bucket": [
        "primary_7d_high_magnitude",
        "primary_7d_mid_magnitude",
        "primary_7d_low_magnitude",
        "primary_7d_missing_delta",
        "not_primary_7d_positive",
    ],
    "eps_prev_delta_confirmation_bucket": [
        "primary_7d_with_prev_positive",
        "primary_7d_prev_flat",
        "primary_7d_prev_negative_reversal",
        "primary_7d_prev_missing",
        "not_primary_7d_positive",
    ],
    "same_event_history_depth_bucket": [
        "primary_7d_history_ge_10",
        "primary_7d_history_lt_10",
        "primary_7d_history_missing",
        "not_primary_7d_positive",
    ],
    "pead_readiness_bucket": [
        "eligible_t2_t15_primary_residual",
        "eligible_t2_t15_primary_non_residual",
        "blocked_missing_last_earnings_date",
        "blocked_missing_effective_trade_date",
        "blocked_outside_t2_t15_after_earnings",
        "not_primary_7d_positive",
    ],
    "post_revision_2d_failure_proxy_bucket": [
        "primary_7d_no_fast_2d_failure",
        "primary_7d_fast_2d_failure",
        "primary_7d_missing_2d_outcome",
        "not_primary_7d_positive",
    ],
    "post_revision_candidate_conversion_bucket": [
        "primary_7d_candidate_hit_3td",
        "primary_7d_candidate_hit_10td",
        "primary_7d_no_candidate_hit_10td",
        "primary_7d_candidate_hit_unknown",
        "not_primary_7d_positive",
    ],
    "residual_strength_magnitude_bucket": [
        "primary_7d_residual_mid",
        "primary_7d_residual_extreme",
        "primary_7d_residual_nonpositive",
        "primary_7d_residual_missing",
        "not_primary_7d_positive",
    ],
    "spy_qqq_residual_agreement_bucket": [
        "primary_7d_leads_spy_and_qqq",
        "primary_7d_leads_only_one_benchmark",
        "primary_7d_leads_neither_benchmark",
        "primary_7d_missing_spy_or_qqq",
        "not_primary_7d_positive",
    ],
    "residual_state_quality_bucket": [
        "primary_7d_strong_residual_leader",
        "primary_7d_residual_leader",
        "primary_7d_neutral_or_beta_lagging",
        "primary_7d_missing",
        "not_primary_7d_positive",
    ],
}


def evaluate_gate(
    spec: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    preferred_key = spec["preferred_bucket"]
    comparison_key = spec["comparison_bucket"]
    preferred = summary.get(preferred_key, {})
    comparison = summary.get(comparison_key, {})
    preferred_5d = (preferred.get("horizons") or {}).get("5d") or {}
    preferred_10d = (preferred.get("horizons") or {}).get("10d") or {}
    comparison_5d = (comparison.get("horizons") or {}).get("5d") or {}
    comparison_10d = (comparison.get("horizons") or {}).get("10d") or {}
    preferred_enough = (
        (preferred_5d.get("closed_outcomes") or 0) >= MIN_BUCKET_CLOSED_5D
        and (preferred_10d.get("closed_outcomes") or 0) >= MIN_BUCKET_CLOSED_10D
    )
    comparison_enough = (
        (comparison_5d.get("closed_outcomes") or 0) >= MIN_BUCKET_CLOSED_5D
        and (comparison_10d.get("closed_outcomes") or 0) >= MIN_BUCKET_CLOSED_10D
    )
    comparable = (
        preferred_5d.get("avg_return") is not None
        and comparison_5d.get("avg_return") is not None
        and preferred_10d.get("avg_return") is not None
        and comparison_10d.get("avg_return") is not None
    )
    beats = (
        comparable
        and preferred_5d["avg_return"] > comparison_5d["avg_return"]
        and preferred_10d["avg_return"] > comparison_10d["avg_return"]
    )
    concentration_passed = (
        preferred_5d.get("top5_positive_contribution_share") is not None
        and preferred_5d.get("max_single_ticker_positive_share") is not None
        and preferred_5d["top5_positive_contribution_share"] <= MAX_TOP5_POSITIVE_SHARE
        and preferred_5d["max_single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    data_gap_reasons = []
    if not preferred_enough:
        data_gap_reasons.append("preferred_bucket_closed_outcomes_below_minimum")
    if not comparison_enough:
        data_gap_reasons.append("comparison_bucket_closed_outcomes_below_minimum")
    if not comparable:
        data_gap_reasons.append("preferred_or_comparison_bucket_not_comparable")
    if preferred_key.startswith("eligible_t2_t15") and (preferred.get("row_count") or 0) == 0:
        data_gap_reasons.append("no_pit_eligible_pead_rows")
    if data_gap_reasons:
        return {
            "promotion_gate_passed": False,
            "decision": "observed_only_data_gap",
            "reason": "insufficient_comparable_bucket_evidence",
            "data_gap_reasons": data_gap_reasons,
            "preferred_bucket": preferred_key,
            "comparison_bucket": comparison_key,
            "preferred_5d": preferred_5d,
            "comparison_5d": comparison_5d,
            "preferred_10d": preferred_10d,
            "comparison_10d": comparison_10d,
        }
    if beats and concentration_passed:
        return {
            "promotion_gate_passed": False,
            "decision": "observed_only_promising_requires_forward_confirmation",
            "reason": "preferred_bucket_beats_comparison_but_no_strategy_change",
            "preferred_bucket": preferred_key,
            "comparison_bucket": comparison_key,
            "preferred_5d": preferred_5d,
            "comparison_5d": comparison_5d,
            "preferred_10d": preferred_10d,
            "comparison_10d": comparison_10d,
            "concentration_passed": concentration_passed,
        }
    return {
        "promotion_gate_passed": False,
        "decision": "observed_only_no_promotable_edge",
        "reason": "preferred_bucket_failed_outperformance_or_concentration",
        "preferred_bucket": preferred_key,
        "comparison_bucket": comparison_key,
        "preferred_5d": preferred_5d,
        "comparison_5d": comparison_5d,
        "preferred_10d": preferred_10d,
        "comparison_10d": comparison_10d,
        "beats_comparison": beats,
        "concentration_passed": concentration_passed,
    }


def build_payload(
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
    watchlist_payload: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    bucket_key = spec["bucket_key"]
    bucketer = BUCKETERS[bucket_key]
    annotated = []
    for row in rows:
        next_row = dict(row)
        next_row[bucket_key] = bucketer(row)
        annotated.append(next_row)
    summary = summarize_buckets(
        annotated,
        bucket_key,
        BUCKET_ORDERS[bucket_key],
    )
    gate = evaluate_gate(spec, summary)
    status = "observed_only_data_gap" if gate["decision"] == "observed_only_data_gap" else "observed_only"
    primary_rows = [row for row in annotated if is_primary(row)]
    coverage = {
        "direction": spec["direction"],
        "round": spec["round"],
        "rows_total": len(annotated),
        "primary_positive_7d_rows": len(primary_rows),
        "bucket_counts": dict(Counter(str(row.get(bucket_key) or "missing") for row in annotated)),
        "field_coverage": field_coverage(
            annotated,
            [
                "eps_estimate_delta_7d",
                "eps_estimate_delta_prev",
                "eps_estimate_delta_30d",
                "same_event_history_count",
                "watchlist_effective_trade_date",
                "pead_status",
                "candidate_hit_3td",
                "candidate_hit_10td",
                "residual_strength_score",
                "ret20_excess_spy",
                "ret20_excess_qqq",
                "ret20_excess_theme",
                "ret20_excess_sector",
            ],
        ),
        "closed_forward_outcomes": {
            f"{horizon}d": sum(
                1
                for row in annotated
                if ((row.get("forward_outcomes") or {}).get(f"{horizon}d") or {}).get("closed")
            )
            for horizon in (1, 2, *FORWARD_HORIZONS)
        },
    }
    return {
        "experiment_id": spec["experiment_id"],
        "timestamp": timestamp,
        "status": status,
        "decision": gate["decision"],
        "lane": "alpha_search",
        "hypothesis": spec["hypothesis"],
        "change_summary": (
            f"Round {spec['round']} read-only attribution for "
            f"{spec['direction']} using {bucket_key}."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": spec["trial_family"],
        "trial_variant_id": spec["changed_variable"],
        "changed_variable": spec["changed_variable"],
        "single_causal_variable": spec["changed_variable"],
        "prior_trial_count": 12,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "three_round_expectation_direction_observed_only_attribution",
        "component": "quant/experiments/exp_20260527_002_expectation_direction_three_round_suite.py",
        "parameters": {
            "direction": spec["direction"],
            "round": spec["round"],
            "bucket_key": bucket_key,
            "preferred_bucket": spec["preferred_bucket"],
            "comparison_bucket": spec["comparison_bucket"],
            "forward_horizons": [1, 2, *FORWARD_HORIZONS],
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "gate_thresholds": {
                "min_bucket_closed_5d": MIN_BUCKET_CLOSED_5D,
                "min_bucket_closed_10d": MIN_BUCKET_CLOSED_10D,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "source_experiment": "exp-20260525-034",
            "source_rows": "PIT-usable estimate revision watchlist rows",
            "anti_js": ANTI_JS,
        },
        "date_range": {
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "ohlcv_sources": [
                "data/ohlcv/ohlcv_snapshot_*.json",
                "data/daily/signals/trend/trend_signals_*.json",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": spec["hypothesis"],
            "2_history_check": (
                "Previous nearby expectation-direction runs include "
                "exp-20260525-017, exp-20260525-034, and exp-20260526-030..036; "
                "this suite adds explicit three-round coverage per sub-direction."
            ),
            "3_single_causal_variable": spec["changed_variable"],
            "4_acceptance_standard": (
                "Observed-only gate: preferred bucket must have enough closed "
                "5d/10d outcomes, beat the comparison bucket on both horizons, "
                "and pass concentration guardrails. Passing only unlocks later "
                "forward or paper-sleeve research."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260527_002_expectation_direction_three_round_suite.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Read-only attribution; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "exp-20260525-034 PIT-safe annotated watchlist rows",
                "local OHLCV forward outcomes",
                "estimate revision ledger fields",
                "residual strength feature context",
            ],
            "source_gate2": watchlist_payload.get("gate2"),
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "No strategy behavior changed; this cannot be promoted without a later Gate 1-4 experiment.",
        },
        "coverage": coverage,
        "bucket_summary": summary,
        "gate": gate,
        "sample_rows": [compact_row(row) | {bucket_key: row.get(bucket_key)} for row in annotated[:80]],
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "rows_total": len(annotated),
            "primary_positive_7d_rows": len(primary_rows),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": (
            None
            if gate["decision"] == "observed_only_promising_requires_forward_confirmation"
            else gate["reason"]
        ),
        "next_evidence_needed": spec["next_evidence_needed"],
        "related_files": [
            "quant/experiments/exp_20260527_002_expectation_direction_three_round_suite.py",
            f"data/experiments/{spec['experiment_id']}/{spec['stem']}.json",
            f"experiments/logs/{spec['experiment_id']}.json",
            f"experiments/tickets/{spec['experiment_id']}.json",
            f"experiments/artifacts/{spec['experiment_id']}_{spec['stem']}.md",
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "anti_js": ANTI_JS,
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "coverage",
        "bucket_summary",
        "gate",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keep_keys if key in payload}


def _artifact_markdown(payload: dict[str, Any]) -> str:
    spec = SPEC_BY_ID[payload["experiment_id"]]
    lines = [
        f"# {payload['experiment_id']} {spec['title']}",
        "",
        f"Direction: `{spec['direction']}` round `{spec['round']}`.",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.",
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(_safe(payload["coverage"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Bucket Summary",
        "",
        "```json",
        json.dumps(_safe(payload["bucket_summary"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Next Evidence Needed",
        "",
        payload["next_evidence_needed"],
        "",
        ANTI_JS,
        "",
    ]
    return "\n".join(lines)


def persist_payload(payload: dict[str, Any]) -> None:
    paths = _paths(SPEC_BY_ID[payload["experiment_id"]])
    _write_json(paths["json"], payload)
    _write_json(paths["log"], payload)
    ticket = {
        "experiment_id": payload["experiment_id"],
        "lane": "alpha_search",
        "owner": "codex-expectation-three-round-suite",
        "status": payload["status"],
        "decision": payload["decision"],
        "single_causal_variable": payload["single_causal_variable"],
        "artifact_file": _repo_rel(paths["json"]),
        "result_file": _repo_rel(paths["log"]),
        "updated_at": payload["timestamp"],
    }
    _write_json(paths["ticket"], ticket)
    _write_json(paths["doc_ticket"], ticket)
    paths["artifact"].parent.mkdir(parents=True, exist_ok=True)
    paths["artifact"].write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))
    _upsert_registry(payload, paths)


def build_all_payloads(data_dir: Path | None = None) -> list[dict[str, Any]]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    context = build_context(data_dir)
    rows = with_short_forward_outcomes(context["rows"], data_dir)
    return [
        build_payload(
            spec,
            rows,
            context["watchlist_payload"],
            timestamp,
        )
        for spec in EXPERIMENT_SPECS
    ]


def main() -> int:
    payloads = build_all_payloads()
    for payload in payloads:
        persist_payload(payload)
    print(
        json.dumps(
            _safe(
                {
                    "suite": "expectation_direction_three_round_suite",
                    "experiment_ids": [payload["experiment_id"] for payload in payloads],
                    "directions": {
                        direction: [
                            payload["experiment_id"]
                            for payload in payloads
                            if SPEC_BY_ID[payload["experiment_id"]]["direction"] == direction
                        ]
                        for direction in sorted({spec["direction"] for spec in EXPERIMENT_SPECS})
                    },
                    "results": [
                        {
                            "experiment_id": payload["experiment_id"],
                            "direction": SPEC_BY_ID[payload["experiment_id"]]["direction"],
                            "round": SPEC_BY_ID[payload["experiment_id"]]["round"],
                            "status": payload["status"],
                            "decision": payload["decision"],
                            "reason": payload["gate"].get("reason"),
                            "output": _repo_rel(_paths(SPEC_BY_ID[payload["experiment_id"]])["json"]),
                        }
                        for payload in payloads
                    ],
                    "anti_js": ANTI_JS,
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
