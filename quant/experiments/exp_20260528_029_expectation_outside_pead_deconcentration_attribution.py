"""exp-20260528-029: outside-PEAD short-horizon deconcentration audit.

Observed-only alpha attribution. This follows exp-20260528-013, which found
primary-positive expectation revision rows outside the T+2..T+15 PEAD window
looked stronger than the inside-PEAD short-horizon bucket at 1d/2d. This script
tests whether that apparent outside-PEAD edge survives removing the largest
positive ticker contributor and a first-row-per-ticker de-duplication.

No strategy, ranking, sizing, exits, LLM prompts, paper sleeves, or orders are
changed. No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260528_013_expectation_pead_short_horizon_repaired_attribution import (  # noqa: E402
    attach_short_outcomes,
    is_primary_positive,
    is_residual_leader,
    outcome_for,
    _float,
)


EXPERIMENT_ID = "exp-20260528-029"
STEM = "expectation_outside_pead_deconcentration_attribution"
MECHANISM_FAMILY = "expectation_revision_pead"
TRIAL_FAMILY = "expectation_outside_pead_deconcentration_attribution"
CHANGED_VARIABLE = "outside_pead_primary_positive_short_horizon_deconcentration_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EXPERIMENT_ID = "exp-20260527-908"
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

HORIZONS = ("1d", "2d", "3d")
GATE_HORIZONS = ("1d", "2d")
PAPER_NOTIONAL_USD = 10_000.0
ANTI_JS = "No JavaScript was used."

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}

MIN_CLOSED_OUTCOMES = {
    ("outside_all_rows", "1d"): 15,
    ("outside_all_rows", "2d"): 15,
    ("outside_ex_top_positive_ticker", "1d"): 10,
    ("outside_ex_top_positive_ticker", "2d"): 10,
    ("outside_ticker_first_dedup", "1d"): 6,
    ("outside_ticker_first_dedup", "2d"): 6,
}
MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE = 0.60
MAX_TOP5_POSITIVE_PNL_SHARE = 0.80


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _compact_jsonl_fallback(payload: dict[str, Any]) -> str:
    jsonl_payload = dict(payload)
    jsonl_payload.pop("sample_rows", None)
    jsonl_payload["sample_rows_omitted_from_jsonl"] = True
    return json.dumps(_safe(jsonl_payload), ensure_ascii=True, sort_keys=True)


def _replace_jsonl_line_in_place(path: Path, compact: str) -> bool:
    target = EXPERIMENT_ID.encode("utf-8")
    replacement_body = compact.encode("utf-8")
    offset = 0
    with path.open("rb") as src:
        while True:
            line = src.readline()
            if not line:
                return False
            if target in line:
                old_len = len(line)
                break
            offset += len(line)
    if len(replacement_body) + 1 > old_len:
        return False
    replacement = replacement_body + (b" " * (old_len - len(replacement_body) - 1)) + b"\n"
    with path.open("r+b") as dst:
        dst.seek(offset)
        dst.write(replacement)
    return True


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(compact + "\n", encoding="utf-8")
        return

    found = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                found = True
                break

    if not found:
        with path.open("a", encoding="utf-8", newline="\n") as dst:
            dst.write(compact + "\n")
        return

    tmp_path = path.with_name(f"{path.name}.{EXPERIMENT_ID}.tmp")
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src, tmp_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line if line.endswith("\n") else line + "\n")
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    dst.write(compact + "\n")
                    replaced = True
                continue
            dst.write(line if line.endswith("\n") else line + "\n")
    try:
        tmp_path.replace(path)
    except PermissionError:
        compact = _compact_jsonl_fallback(payload)
        if not _replace_jsonl_line_in_place(path, compact):
            with path.open("a", encoding="utf-8", newline="\n") as dst:
                dst.write(compact + "\n")
        try:
            tmp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


def load_source(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing source artifact: {_repo_rel(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("enriched_watchlist_rows"), list):
        raise ValueError("source artifact does not contain enriched_watchlist_rows")
    return payload


def _closed_pairs(
    rows: Iterable[dict[str, Any]],
    horizon: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs = []
    for row in rows:
        outcome = outcome_for(row, horizon)
        if outcome["closed"]:
            pairs.append((row, outcome))
    return pairs


def positive_pnl_contribution(
    rows: list[dict[str, Any]],
    horizon: str,
) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row, outcome in _closed_pairs(rows, horizon):
        pnl = _float(outcome.get("pnl_proxy"))
        if pnl is not None and pnl > 0:
            by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl_proxy": pnl,
            "share": pnl / total if total > 0 else None,
        }
        for ticker, pnl in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_pnl_total": total,
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_pnl_proxy": ranked[0]["positive_pnl_proxy"] if ranked else 0.0,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked,
    }


def combined_positive_pnl_contribution(
    rows: list[dict[str, Any]],
    horizons: Iterable[str] = GATE_HORIZONS,
) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for horizon in horizons:
        for row, outcome in _closed_pairs(rows, horizon):
            pnl = _float(outcome.get("pnl_proxy"))
            if pnl is not None and pnl > 0:
                by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl_proxy": pnl,
            "share": pnl / total if total > 0 else None,
        }
        for ticker, pnl in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "horizons": list(horizons),
        "positive_pnl_total": total,
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_pnl_proxy": ranked[0]["positive_pnl_proxy"] if ranked else 0.0,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked,
    }


def horizon_stats(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    pairs = _closed_pairs(rows, horizon)
    returns = [
        _float(outcome.get("return"))
        for _row, outcome in pairs
        if _float(outcome.get("return")) is not None
    ]
    pnls = [
        _float(outcome.get("pnl_proxy"))
        for _row, outcome in pairs
        if _float(outcome.get("pnl_proxy")) is not None
    ]
    positive_pairs = [
        (row, _float(outcome.get("pnl_proxy")) or 0.0)
        for row, outcome in pairs
        if (_float(outcome.get("pnl_proxy")) or 0.0) > 0
    ]
    positive_total = sum(pnl for _row, pnl in positive_pairs)
    top5_positive = sum(
        pnl for _row, pnl in sorted(positive_pairs, key=lambda item: item[1], reverse=True)[:5]
    )
    by_ticker_positive: defaultdict[str, float] = defaultdict(float)
    for row, pnl in positive_pairs:
        by_ticker_positive[str(row.get("ticker") or "")] += pnl
    max_single = max(by_ticker_positive.values()) if by_ticker_positive else 0.0
    contribution = positive_pnl_contribution(rows, horizon)

    return {
        "closed_count": len(pairs),
        "missing_count": len(rows) - len(pairs),
        "avg_return": sum(returns) / len(returns) if returns else None,
        "win_rate": sum(1 for value in returns if value > 0) / len(returns) if returns else None,
        "total_pnl_proxy": sum(pnls) if pnls else 0.0,
        "positive_pnl_total": positive_total,
        "top5_positive_pnl_share": top5_positive / positive_total if positive_total > 0 else None,
        "single_ticker_positive_pnl_share": max_single / positive_total if positive_total > 0 else None,
        "top_positive_ticker": contribution["top_ticker"],
        "top_positive_ticker_share": contribution["top_ticker_positive_share"],
        "tail_loss": min(returns) if returns else None,
    }


def phase_bucket_for(row: dict[str, Any]) -> str:
    days = _float(row.get("days_since_last_earnings"))
    if days is None:
        return "missing_days_since_last_earnings"
    if days < 0:
        return "pre_earnings_or_future_date"
    if days <= 1:
        return "post_earnings_t0_t1"
    if 16 <= days <= 30:
        return "post_earnings_t16_t30"
    if 31 <= days <= 60:
        return "post_earnings_t31_t60"
    if days > 60:
        return "post_earnings_gt60"
    return "other_outside"


def summarize_scenario(rows: list[dict[str, Any]]) -> dict[str, Any]:
    days_since = [
        value
        for value in (_float(row.get("days_since_last_earnings")) for row in rows)
        if value is not None
    ]
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    return {
        "row_count": len(rows),
        "ticker_count": len(ticker_counts),
        "max_rows_per_ticker": max(ticker_counts.values()) if ticker_counts else 0,
        "ticker_row_counts": dict(ticker_counts.most_common()),
        "residual_leader_count": sum(1 for row in rows if is_residual_leader(row)),
        "residual_state_counts": dict(Counter(str(row.get("residual_state") or "") for row in rows)),
        "sector_counts": dict(Counter(str(row.get("sector") or "") for row in rows)),
        "phase_counts": dict(Counter(phase_bucket_for(row) for row in rows)),
        "days_since_last_earnings": {
            "min": min(days_since) if days_since else None,
            "avg": sum(days_since) / len(days_since) if days_since else None,
            "max": max(days_since) if days_since else None,
        },
        "short_forward_outcomes": {
            horizon: horizon_stats(rows, horizon) for horizon in HORIZONS
        },
    }


def _effective_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(
            row.get("watchlist_effective_trade_date")
            or row.get("as_of_date")
            or row.get("feature_context_date")
            or ""
        ),
        str(row.get("ticker") or ""),
    )


def dedupe_first_by_ticker(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=_effective_sort_key):
        ticker = str(row.get("ticker") or "")
        if ticker and ticker not in kept:
            kept[ticker] = row
    return list(kept.values())


def group_by_phase(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[phase_bucket_for(row)].append(row)
    return dict(grouped)


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "as_of_date": row.get("as_of_date"),
        "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
        "last_earnings_date": row.get("last_earnings_date"),
        "days_since_last_earnings": row.get("days_since_last_earnings"),
        "pead_status": row.get("pead_status"),
        "phase_bucket": phase_bucket_for(row),
        "residual_state": row.get("residual_state"),
        "sector": row.get("sector"),
        "short_forward_outcomes": {
            horizon: outcome_for(row, horizon) for horizon in HORIZONS
        },
    }


def _scenario_horizon(
    scenario_summary: dict[str, Any],
    scenario: str,
    horizon: str,
) -> dict[str, Any]:
    return (
        ((scenario_summary.get(scenario) or {}).get("short_forward_outcomes") or {})
        .get(horizon)
        or {}
    )


def _positive_on_gate_horizons(
    scenario_summary: dict[str, Any],
    scenario: str,
) -> bool:
    for horizon in GATE_HORIZONS:
        stats = _scenario_horizon(scenario_summary, scenario, horizon)
        avg_return = _float(stats.get("avg_return"))
        total_pnl = _float(stats.get("total_pnl_proxy"))
        if avg_return is None or avg_return <= 0:
            return False
        if total_pnl is None or total_pnl <= 0:
            return False
    return True


def build_gate(scenario_summary: dict[str, Any]) -> dict[str, Any]:
    data_gaps = []
    for (scenario, horizon), minimum in MIN_CLOSED_OUTCOMES.items():
        closed = int(_scenario_horizon(scenario_summary, scenario, horizon).get("closed_count") or 0)
        if closed < minimum:
            data_gaps.append(
                {
                    "scenario": scenario,
                    "horizon": horizon,
                    "closed_count": closed,
                    "minimum": minimum,
                }
            )

    concentration_flags = []
    for horizon in GATE_HORIZONS:
        stats = _scenario_horizon(scenario_summary, "outside_all_rows", horizon)
        single_share = _float(stats.get("single_ticker_positive_pnl_share"))
        top5_share = _float(stats.get("top5_positive_pnl_share"))
        if single_share is not None and single_share > MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE:
            concentration_flags.append(
                {
                    "horizon": horizon,
                    "metric": "single_ticker_positive_pnl_share",
                    "value": single_share,
                    "maximum": MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE,
                }
            )
        if top5_share is not None and top5_share > MAX_TOP5_POSITIVE_PNL_SHARE:
            concentration_flags.append(
                {
                    "horizon": horizon,
                    "metric": "top5_positive_pnl_share",
                    "value": top5_share,
                    "maximum": MAX_TOP5_POSITIVE_PNL_SHARE,
                }
            )

    row_level_positive = _positive_on_gate_horizons(scenario_summary, "outside_all_rows")
    ex_top_positive = _positive_on_gate_horizons(
        scenario_summary,
        "outside_ex_top_positive_ticker",
    )
    dedup_positive = _positive_on_gate_horizons(
        scenario_summary,
        "outside_ticker_first_dedup",
    )
    dedup_ex_top_positive = _positive_on_gate_horizons(
        scenario_summary,
        "outside_ticker_first_dedup_ex_top",
    )

    if data_gaps:
        decision = "observed_only_data_gap"
        reason = "minimum closed short-horizon outcome counts were not met"
    elif not row_level_positive:
        decision = "rejected_no_outside_pead_row_level_edge"
        reason = "outside-PEAD row-level 1d/2d returns were not both positive"
    elif not ex_top_positive or not dedup_positive or not dedup_ex_top_positive:
        decision = "observed_only_no_promotable_edge"
        reason = "outside_pead_edge_collapses_after_top_ticker_or_ticker_dedup"
    elif concentration_flags:
        decision = "observed_only_no_promotable_edge"
        reason = "outside_pead_edge_fails_positive_pnl_concentration_guardrail"
    else:
        decision = "observed_only_deconcentrated_candidate_requires_strategy_replay"
        reason = "outside_pead_edge_survived_deconcentration_precheck"

    return {
        "passed": decision == "observed_only_deconcentrated_candidate_requires_strategy_replay",
        "decision": decision,
        "reason": reason,
        "data_gaps": data_gaps,
        "row_level_positive": row_level_positive,
        "ex_top_positive": ex_top_positive,
        "dedup_positive": dedup_positive,
        "dedup_ex_top_positive": dedup_ex_top_positive,
        "concentration_flags": concentration_flags,
    }


def build_payload(source_path: Path, data_dir: Path) -> dict[str, Any]:
    timestamp = _utc_now()
    source_payload = load_source(source_path)
    rows = attach_short_outcomes(source_payload["enriched_watchlist_rows"], data_dir)
    outside_rows = [
        row
        for row in rows
        if row.get("pead_attribution_bucket") == "primary_positive_outside_t2_t15"
    ]
    inside_non_rows = [
        row
        for row in rows
        if row.get("pead_attribution_bucket") == "eligible_t2_t15_non_overextended"
    ]
    inside_residual_rows = [
        row
        for row in rows
        if row.get("pead_attribution_bucket") == "eligible_t2_t15_residual_leader"
    ]

    combined_contribution = combined_positive_pnl_contribution(outside_rows)
    top_ticker = str(combined_contribution.get("top_ticker") or "")
    outside_ex_top = [row for row in outside_rows if str(row.get("ticker") or "") != top_ticker]
    outside_dedup = dedupe_first_by_ticker(outside_rows)
    outside_dedup_ex_top = [
        row for row in outside_dedup if str(row.get("ticker") or "") != top_ticker
    ]

    scenarios = {
        "outside_all_rows": outside_rows,
        "outside_ex_top_positive_ticker": outside_ex_top,
        "outside_ticker_first_dedup": outside_dedup,
        "outside_ticker_first_dedup_ex_top": outside_dedup_ex_top,
        "inside_non_overextended_reference": inside_non_rows,
        "inside_residual_leader_reference": inside_residual_rows,
    }
    scenario_summary = {
        name: summarize_scenario(scenario_rows) for name, scenario_rows in scenarios.items()
    }
    phase_summary = {
        phase: summarize_scenario(phase_rows)
        for phase, phase_rows in sorted(group_by_phase(outside_rows).items())
    }
    ticker_contribution = {
        horizon: positive_pnl_contribution(outside_rows, horizon) for horizon in HORIZONS
    }
    gate = build_gate(scenario_summary)
    as_of_dates = sorted(str(row.get("as_of_date")) for row in rows if row.get("as_of_date"))

    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(source_path),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]

    coverage = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "rows_total": len(rows),
        "as_of_date_range": f"{as_of_dates[0]} .. {as_of_dates[-1]}" if as_of_dates else None,
        "primary_positive_rows": sum(1 for row in rows if is_primary_positive(row)),
        "outside_pead_rows": len(outside_rows),
        "outside_pead_ticker_count": len({str(row.get("ticker") or "") for row in outside_rows}),
        "bucket_counts": dict(Counter(str(row.get("pead_attribution_bucket") or "") for row in rows)),
        "primary_positive_pead_status_counts": dict(
            Counter(str(row.get("pead_status") or "") for row in rows if is_primary_positive(row))
        ),
        "closed_short_forward_outcomes": {
            horizon: sum(1 for row in rows if outcome_for(row, horizon)["closed"])
            for horizon in HORIZONS
        },
    }

    after_metrics = {
        "strategy_behavior_changed": False,
        "outside_all_1d_avg_return": _scenario_horizon(
            scenario_summary,
            "outside_all_rows",
            "1d",
        ).get("avg_return"),
        "outside_all_1d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_all_rows",
            "1d",
        ).get("total_pnl_proxy"),
        "outside_all_2d_avg_return": _scenario_horizon(
            scenario_summary,
            "outside_all_rows",
            "2d",
        ).get("avg_return"),
        "outside_all_2d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_all_rows",
            "2d",
        ).get("total_pnl_proxy"),
        "outside_ex_top_1d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_ex_top_positive_ticker",
            "1d",
        ).get("total_pnl_proxy"),
        "outside_ex_top_2d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_ex_top_positive_ticker",
            "2d",
        ).get("total_pnl_proxy"),
        "outside_ticker_first_dedup_1d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_ticker_first_dedup",
            "1d",
        ).get("total_pnl_proxy"),
        "outside_ticker_first_dedup_2d_total_pnl_proxy": _scenario_horizon(
            scenario_summary,
            "outside_ticker_first_dedup",
            "2d",
        ).get("total_pnl_proxy"),
        "top_positive_ticker": top_ticker,
        "top_positive_ticker_combined_share": combined_contribution.get(
            "top_ticker_positive_share"
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": gate["decision"],
        "lane": "alpha_search",
        "hypothesis": (
            "If the exp-20260528-013 outside-PEAD primary-positive 1d/2d "
            "strength is real alpha rather than concentrated repeat exposure, "
            "it should remain positive after removing the top positive ticker "
            "contributor and after first-row-per-ticker de-duplication."
        ),
        "change_summary": (
            "Observed-only deconcentration audit of primary-positive expectation "
            "revision rows outside the T+2..T+15 PEAD window. Reuses the "
            "corrected weekday close outcome construction from exp-20260528-013 "
            "and compares all outside-PEAD rows, ex-top-ticker rows, first-row-"
            "per-ticker rows, and first-row-per-ticker ex-top rows."
        ),
        "change_type": "observed_only_outside_pead_deconcentration_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 8,
        "nearby_prior_experiments": [
            {
                "experiment_id": "exp-20260528-013",
                "finding": (
                    "Outside-PEAD primary-positive rows beat inside-PEAD "
                    "non-overextended rows at 1d/2d, but concentration was high."
                ),
            },
            {
                "experiment_id": "exp-20260528-027",
                "finding": "Residual leadership inside PEAD failed as a 5d discriminator.",
            },
            {
                "experiment_id": "exp-20260528-028",
                "finding": "The PEAD window itself failed to show 5d lift across three positive-revision tiers.",
            },
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "outside_pead_short_horizon_deconcentration_audit",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(source_path),
            "data_dir": _repo_rel(data_dir),
            "outside_pead_bucket": "primary_positive_outside_t2_t15",
            "top_ticker_selection": "largest combined positive pnl proxy across 1d and 2d",
            "dedupe_rule": "earliest watchlist_effective_trade_date per ticker",
            "short_forward_horizons": list(HORIZONS),
            "gate_horizons": list(GATE_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "min_closed_outcomes": {
                f"{scenario}:{horizon}": minimum
                for (scenario, horizon), minimum in MIN_CLOSED_OUTCOMES.items()
            },
            "max_single_ticker_positive_pnl_share": MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE,
            "max_top5_positive_pnl_share": MAX_TOP5_POSITIVE_PNL_SHARE,
            "anti_js": ANTI_JS,
        },
        "date_range": source_payload.get("date_range")
        or {"source_watchlist_as_of_dates": coverage["as_of_date_range"]},
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Outside-PEAD primary-positive expectation revision rows may "
                "be a short-horizon ranking candidate, but only if the 1d/2d "
                "edge survives deconcentration."
            ),
            "2_history_check": (
                "exp-20260528-013 found outside-PEAD 1d/2d strength with high "
                "concentration; exp-20260528-027/028 rejected PEAD-window "
                "residual and no-residual 5d variants."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only precheck passes only if all-row, ex-top-ticker, "
                "ticker-dedup, and ticker-dedup ex-top 1d/2d avg return and "
                "PnL remain positive, minimum closed counts are met, and "
                "positive-PnL concentration is below guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_029_expectation_outside_pead_deconcentration_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Observed-only attribution; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "ticker",
                "watchlist_effective_trade_date",
                "primary_expectation_positive",
                "last_earnings_date",
                "pead_status",
                "days_since_last_earnings",
                "local weekday close snapshots",
            ],
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
            "passed": bool(gate["passed"]),
            "note": "Observed-only result can only unlock a later default-off Gate 1-4 strategy experiment.",
        },
        "coverage": coverage,
        "top_positive_contributor": combined_contribution,
        "ticker_positive_pnl_contribution_by_horizon": ticker_contribution,
        "scenario_summary": scenario_summary,
        "outside_phase_summary": phase_summary,
        "gate": gate,
        "sample_rows": {
            name: [compact_row(row) for row in scenario_rows[:80]]
            for name, scenario_rows in scenarios.items()
        },
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": after_metrics,
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
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": gate["reason"],
        "next_evidence_needed": (
            "Do not promote the outside-PEAD short-horizon bucket from this "
            "frozen sample. If revisited, require new non-MU forward rows, "
            "ticker-deduplicated replacement-value evidence, or a different "
            "stable phase/ranking interaction that survives concentration checks."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return ""
    return f"{number:.6f}"


def artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "# exp-20260528-029 Outside-PEAD Deconcentration Attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Strategy behavior changed: `false`",
        "",
        "## Scenario Outcomes",
        "",
        "| scenario | rows | tickers | 1d closed | 1d avg | 1d pnl | 2d closed | 2d avg | 2d pnl | 3d closed | 3d avg | 3d pnl |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario in [
        "outside_all_rows",
        "outside_ex_top_positive_ticker",
        "outside_ticker_first_dedup",
        "outside_ticker_first_dedup_ex_top",
        "inside_non_overextended_reference",
        "inside_residual_leader_reference",
    ]:
        summary = payload["scenario_summary"].get(scenario, {})
        outcomes = summary.get("short_forward_outcomes", {})
        h1 = outcomes.get("1d", {})
        h2 = outcomes.get("2d", {})
        h3 = outcomes.get("3d", {})
        rows.append(
            "| {scenario} | {row_count} | {ticker_count} | {c1} | {a1} | {p1} | {c2} | {a2} | {p2} | {c3} | {a3} | {p3} |".format(
                scenario=scenario,
                row_count=summary.get("row_count", 0),
                ticker_count=summary.get("ticker_count", 0),
                c1=h1.get("closed_count", 0),
                a1=_fmt(h1.get("avg_return")),
                p1=_fmt(h1.get("total_pnl_proxy")),
                c2=h2.get("closed_count", 0),
                a2=_fmt(h2.get("avg_return")),
                p2=_fmt(h2.get("total_pnl_proxy")),
                c3=h3.get("closed_count", 0),
                a3=_fmt(h3.get("avg_return")),
                p3=_fmt(h3.get("total_pnl_proxy")),
            )
        )
    rows.extend(
        [
            "",
            "## Top Contributor",
            "",
            f"- Top ticker: `{payload['top_positive_contributor'].get('top_ticker')}`",
            f"- Combined 1d/2d positive-PnL share: `{_fmt(payload['top_positive_contributor'].get('top_ticker_positive_share'))}`",
            "",
            "## Gate Details",
            "",
            f"- Data gaps: `{json.dumps(payload['gate']['data_gaps'], ensure_ascii=True)}`",
            f"- Row-level positive: `{payload['gate']['row_level_positive']}`",
            f"- Ex-top positive: `{payload['gate']['ex_top_positive']}`",
            f"- Dedup positive: `{payload['gate']['dedup_positive']}`",
            f"- Dedup ex-top positive: `{payload['gate']['dedup_ex_top_positive']}`",
            f"- Concentration flags: `{json.dumps(payload['gate']['concentration_flags'], ensure_ascii=True)}`",
            "",
            "## Interpretation",
            "",
            "The all-row outside-PEAD bucket remains positive at 1d/2d, but the edge is not deconcentrated. Removing the largest positive contributor or de-duplicating to first row per ticker breaks the 1d signal, so this is not promotion evidence for an outside-PEAD ranking or allocation rule.",
            "",
            "## Related Files",
            "",
        ]
    )
    rows.extend(f"- `{path}`" for path in payload["related_files"])
    rows.append("")
    return "\n".join(rows)


def update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = row
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    registry["updated_at"] = payload["timestamp"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "artifact_file": _repo_rel(OUT_JSON),
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "owner": "codex-expectation-outside-pead-deconcentration",
        "result_file": _repo_rel(DOC_LOG),
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    update_registry(payload, ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", default=str(SOURCE_ARTIFACT))
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"))
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.source_artifact), Path(args.data_dir))
    if not args.no_persist:
        persist_payload(payload)

    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate": payload["gate"],
                "top_positive_contributor": payload["top_positive_contributor"],
                "scenario_summary": {
                    name: {
                        horizon: (
                            summary.get("short_forward_outcomes", {}).get(horizon, {})
                        )
                        for horizon in GATE_HORIZONS
                    }
                    for name, summary in payload["scenario_summary"].items()
                    if name.startswith("outside_")
                },
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
