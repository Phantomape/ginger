"""exp-20260624-023: Kova SEC13F + options forward attribution.

Observed-only alpha attribution. This joins the exp-20260624-017 Kova forward
outcome ledger with the OnclickMedia options forward observation ledgers and
tests whether options bullish-pressure cross-evidence improves the already
positive SEC13F sponsorship lead.

No strategy, helper, ranking, sizing, exit, paper fill, daily snapshot, LLM,
watchlist, or live order behavior changes in this experiment.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-023"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_options_cross_evidence_forward_attribution"
RUNNER = f"quant/experiments/exp_20260624_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_023_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
KOVA_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-017"
    / "kova_sec13f_forward_outcome_settlement_ledger.jsonl"
)
OPTIONS_LEDGERS = [
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-009"
    / "options_forward_observation_ledger.jsonl",
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-020"
    / "options_forward_observation_ledger_delta_20260623.jsonl",
]

HYPOTHESIS = (
    "Observed-only attribution: Kova forward rows with high PIT SEC13F "
    "sponsorship plus same-date options bullish-pressure cross-evidence should "
    "show better settled 1d/3d/5d cash/SPY/QQQ replacement value than "
    "high-sponsorship rows without options confirmation."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_options_cross_evidence_forward_attribution"
TRIAL_VARIANT_ID = "post_exp017_partial_forward_1d3d5_options_x_sec13f_v1"
CHANGED_VARIABLE = "kova_sec13f_options_cross_evidence_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "partial_closed_forward_replacement_value_rows_plus_options_cross_evidence"
NEW_EVIDENCE_AXIS = (
    "New cross-source join between exp-20260624-017 partial closed Kova "
    "replacement rows and exp-20260623-009/20260624-020 options observation "
    "ledgers; this is not a SEC13F holder/value, coownership, RS, Companyfacts, "
    "top-N, hold, cooldown, notional, or allocator threshold retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-018",
    "exp-20260624-019",
    "exp-20260624-020",
    "exp-20260623-010",
]
CAUSAL_COMPONENTS = [
    "exp017 settled forward Kova rows",
    "SEC13F sponsorship score",
    "options forward observation cross-evidence",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "uses_kova_forward_snapshots": True,
    "uses_sec13f_forward_context": True,
    "uses_options_forward_context": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
    ),
}
ACCEPTANCE_RULE = {
    "primary_horizon": 5,
    "min_primary_confirmed_rows": 20,
    "min_primary_matched_not_confirmed_rows": 20,
    "min_primary_missing_options_rows": 100,
    "min_primary_asof_dates": 2,
    "min_supporting_horizons_confirmed_beats_matched": 2,
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share": 0.50,
}
HORIZONS = [1, 3, 5]
COMPARATORS = ["cash", "spy", "qqq"]
OPTION_BUCKETS = [
    "high_sponsorship_options_confirmed",
    "high_sponsorship_options_not_confirmed",
    "high_sponsorship_missing_options",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def round_or_none(value: Any, digits: int = 6) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def percentile_rank(value: float, sorted_values: list[float]) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return 1.0
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    avg_zero_based_rank = (left + right - 1) / 2.0
    return avg_zero_based_rank / (len(sorted_values) - 1)


def numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        parsed = safe_float(row.get(key))
        if parsed is not None:
            values.append(parsed)
    return values


def stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round_or_none(mean(clean), 4),
        "median": round_or_none(median(clean), 4),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.17,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_options_overlap",
            "no_cross_evidence_separation",
            "qqq_beta_confound",
            "options_rows_pending_or_lagged",
            "forward_window_too_short",
        ],
        "confidence_reason": (
            "Kova SEC13F sponsorship has a positive forward-only lead and options "
            "cross-evidence is an allowed new axis, but overlap and horizon "
            "maturity are likely thin."
        ),
        "recorded_at": utc_now(),
    }


def log_feature(row: dict[str, Any], key: str) -> float | None:
    value = safe_float(row.get(key))
    if value is None or value <= 0:
        return None
    return math.log1p(value)


def add_sponsorship_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    holder_values = []
    total_values = []
    position_values = []
    for row in rows:
        if row.get("sec13f_status") != "ok":
            continue
        holder = log_feature(row, "sec13f_holder_count")
        total = log_feature(row, "sec13f_total_value_usd")
        position = log_feature(row, "sec13f_position_row_count")
        if holder is not None:
            holder_values.append(holder)
        if total is not None:
            total_values.append(total)
        if position is not None:
            position_values.append(position)
    holder_values.sort()
    total_values.sort()
    position_values.sort()
    scored = []
    for row in rows:
        out = dict(row)
        parts = []
        for value, population in (
            (log_feature(row, "sec13f_holder_count"), holder_values),
            (log_feature(row, "sec13f_total_value_usd"), total_values),
            (log_feature(row, "sec13f_position_row_count"), position_values),
        ):
            if value is None:
                continue
            ranked = percentile_rank(value, population)
            if ranked is not None:
                parts.append(ranked)
        out["sec13f_sponsorship_score"] = round_or_none(mean(parts), 8)
        out["sec13f_sponsorship_component_count"] = len(parts)
        scored.append(out)
    return scored


def assign_sponsorship_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ok_rows = [
        row
        for row in rows
        if row.get("sec13f_status") == "ok"
        and safe_float(row.get("sec13f_sponsorship_score")) is not None
    ]
    ordered_ids = [
        str(row.get("observation_id"))
        for row in sorted(
            ok_rows,
            key=lambda row: (
                safe_float(row.get("sec13f_sponsorship_score")) or 0.0,
                str(row.get("ticker") or ""),
                str(row.get("observation_id") or ""),
            ),
        )
    ]
    bucket_by_id: dict[str, str] = {}
    total = len(ordered_ids)
    for index, observation_id in enumerate(ordered_ids):
        bucket_index = min(2, int(index * 3 / total)) if total else 0
        bucket_by_id[observation_id] = [
            "low_sponsorship",
            "mid_sponsorship",
            "high_sponsorship",
        ][bucket_index]
    out = []
    for row in rows:
        item = dict(row)
        item["sec13f_sponsorship_bucket"] = bucket_by_id.get(
            str(row.get("observation_id")),
            "missing_or_skipped_sponsorship",
        )
        out.append(item)
    return out


def option_signal_components(row: dict[str, Any]) -> dict[str, float | None]:
    pcr_volume = safe_float(row.get("put_call_volume_ratio"))
    iv_skew = safe_float(row.get("put_minus_call_volume_weighted_iv"))
    liquid_rate = safe_float(row.get("liquid_contract_rate"))
    median_spread = safe_float(row.get("median_spread_pct"))
    return {
        "low_put_call_volume_ratio": -math.log1p(max(pcr_volume, 0.0))
        if pcr_volume is not None
        else None,
        "low_put_minus_call_iv": -iv_skew if iv_skew is not None else None,
        "high_liquid_contract_rate": liquid_rate,
        "low_median_spread_pct": -math.log1p(max(median_spread, 0.0))
        if median_spread is not None
        else None,
    }


def load_options_by_ticker_date() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    raw_rows = []
    file_rows: dict[str, int] = {}
    for path in OPTIONS_LEDGERS:
        rows = read_jsonl(path)
        file_rows[repo_rel(path)] = len(rows)
        raw_rows.extend(rows)

    scored_input = []
    component_values: dict[str, list[float]] = defaultdict(list)
    for row in raw_rows:
        components = option_signal_components(row)
        item = dict(row)
        item["_option_components"] = components
        scored_input.append(item)
        for key, value in components.items():
            if value is not None:
                component_values[key].append(value)
    for values in component_values.values():
        values.sort()

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_key_count = 0
    for row in scored_input:
        ranks = []
        for key, value in row["_option_components"].items():
            if value is None:
                continue
            ranked = percentile_rank(value, component_values[key])
            if ranked is not None:
                ranks.append(ranked)
        item = dict(row)
        item.pop("_option_components", None)
        item["options_bullish_pressure_score"] = round_or_none(mean(ranks), 8)
        item["options_bullish_component_count"] = len(ranks)
        ticker = str(item.get("ticker") or "").upper()
        usable_date = str(item.get("usable_trade_date") or "")[:10]
        if not ticker or not usable_date:
            continue
        key = (ticker, usable_date)
        if key in by_key:
            duplicate_key_count += 1
            prior = by_key[key]
            prior_retrieved = str(prior.get("last_retrieved_at") or "")
            next_retrieved = str(item.get("last_retrieved_at") or "")
            if next_retrieved <= prior_retrieved:
                continue
        by_key[key] = item

    scored_rows = list(by_key.values())
    score_values = sorted(
        value
        for value in (safe_float(row.get("options_bullish_pressure_score")) for row in scored_rows)
        if value is not None
    )
    cutoff = None
    if score_values:
        cutoff = score_values[int((len(score_values) - 1) * 2 / 3)]
    for row in scored_rows:
        score = safe_float(row.get("options_bullish_pressure_score"))
        row["options_bullish_pressure_top_tertile"] = (
            score is not None
            and cutoff is not None
            and score >= cutoff
            and int(row.get("options_bullish_component_count") or 0) >= 2
        )

    dates = sorted({key[1] for key in by_key})
    return by_key, {
        "options_ledgers": file_rows,
        "raw_option_rows": len(raw_rows),
        "deduped_ticker_date_rows": len(by_key),
        "duplicate_ticker_date_rows": duplicate_key_count,
        "usable_date_start": dates[0] if dates else None,
        "usable_date_end": dates[-1] if dates else None,
        "usable_date_count": len(dates),
        "bullish_score_cutoff_top_tertile": round_or_none(cutoff, 8),
    }


def join_options(
    rows: list[dict[str, Any]],
    options_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        ticker = str(row.get("ticker") or "").upper()
        entry_date = str(
            row.get("entry_date") or row.get("planned_entry_date") or row.get("asof_date") or ""
        )[:10]
        option = options_by_key.get((ticker, entry_date))
        item["options_join_key"] = {"ticker": ticker, "usable_trade_date": entry_date}
        item["options_context_available"] = option is not None
        if option:
            item["options_observation_id"] = option.get("observation_id")
            item["options_quote_date"] = option.get("quote_date")
            item["options_usable_trade_date"] = option.get("usable_trade_date")
            item["options_bullish_pressure_score"] = option.get("options_bullish_pressure_score")
            item["options_bullish_component_count"] = option.get(
                "options_bullish_component_count"
            )
            item["options_bullish_pressure_top_tertile"] = option.get(
                "options_bullish_pressure_top_tertile"
            )
            item["options_put_call_volume_ratio"] = option.get("put_call_volume_ratio")
            item["options_put_minus_call_iv"] = option.get("put_minus_call_volume_weighted_iv")
            item["options_liquid_contract_rate"] = option.get("liquid_contract_rate")
            item["options_median_spread_pct"] = option.get("median_spread_pct")
            item["options_quality_flags"] = option.get("quality_flags") or []
        else:
            item["options_observation_id"] = None
            item["options_bullish_pressure_score"] = None
            item["options_bullish_component_count"] = 0
            item["options_bullish_pressure_top_tertile"] = False
            item["options_quality_flags"] = []
        out.append(item)
    return out


def replacement_key(horizon: int, comparator: str) -> str:
    return f"replacement_value_{horizon}d_vs_{comparator}_usd"


def settled_rows(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    status_key = f"forward_{horizon}d_status"
    return [
        row
        for row in rows
        if row.get(status_key) == "settled"
        and safe_float(row.get(replacement_key(horizon, "cash"))) is not None
    ]


def concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    key = replacement_key(horizon, "cash")
    for row in rows:
        pnl = safe_float(row.get(key))
        ticker = str(row.get("ticker") or "").upper()
        if pnl is not None and pnl > 0 and ticker:
            by_ticker[ticker] += pnl
    positive_pnl = sum(by_ticker.values())
    if positive_pnl <= 0:
        return {
            "positive_pnl": 0.0,
            "positive_ticker_count": 0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: pnl / positive_pnl for ticker, pnl in by_ticker.items()}
    top = sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "positive_pnl": round(positive_pnl, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 2), "share": round(shares[ticker], 6)}
            for ticker, pnl in top
        ],
    }


def summarize_group(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    scores = numeric_values(rows, "options_bullish_pressure_score")
    sponsor_scores = numeric_values(rows, "sec13f_sponsorship_score")
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    replacement = {
        f"replacement_value_vs_{comparator}_usd": stats(
            [
                safe_float(row.get(replacement_key(horizon, comparator)))
                for row in rows
                if safe_float(row.get(replacement_key(horizon, comparator))) is not None
            ]
        )
        for comparator in COMPARATORS
    }
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "asof_date_count": len(asof_dates),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "options_score_mean": round_or_none(mean(scores), 6),
        "options_score_median": round_or_none(median(scores), 6),
        "sponsorship_score_mean": round_or_none(mean(sponsor_scores), 6),
        "sponsorship_score_median": round_or_none(median(sponsor_scores), 6),
        "replacement_metrics": replacement,
        "cash_positive_concentration": concentration(rows, horizon),
    }


def bucket_high_sponsorship_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {bucket: [] for bucket in OPTION_BUCKETS}
    for row in rows:
        if row.get("sec13f_sponsorship_bucket") != "high_sponsorship":
            continue
        if row.get("options_context_available") and row.get("options_bullish_pressure_top_tertile"):
            buckets["high_sponsorship_options_confirmed"].append(row)
        elif row.get("options_context_available"):
            buckets["high_sponsorship_options_not_confirmed"].append(row)
        else:
            buckets["high_sponsorship_missing_options"].append(row)
    return buckets


def compare(summary: dict[str, Any], a: str, b: str, comparator: str, metric: str) -> bool:
    left = summary["bucket_summary"][a]["replacement_metrics"][
        f"replacement_value_vs_{comparator}_usd"
    ][metric]
    right = summary["bucket_summary"][b]["replacement_metrics"][
        f"replacement_value_vs_{comparator}_usd"
    ][metric]
    return left is not None and right is not None and left > right


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = settled_rows(rows, horizon)
    high_sponsor = [
        row for row in settled if row.get("sec13f_sponsorship_bucket") == "high_sponsorship"
    ]
    option_buckets = bucket_high_sponsorship_rows(settled)
    summary = {
        "horizon": horizon,
        "settled_rows": len(settled),
        "high_sponsorship_rows": len(high_sponsor),
        "option_matched_high_sponsorship_rows": len(
            [
                row
                for row in high_sponsor
                if row.get("options_context_available")
            ]
        ),
        "bucket_summary": {
            bucket: summarize_group(bucket_rows, horizon)
            for bucket, bucket_rows in option_buckets.items()
        },
    }
    support: dict[str, Any] = {}
    for comparator in COMPARATORS:
        support[f"confirmed_mean_{comparator}_beats_matched_not_confirmed"] = compare(
            summary,
            "high_sponsorship_options_confirmed",
            "high_sponsorship_options_not_confirmed",
            comparator,
            "mean",
        )
        support[f"confirmed_median_{comparator}_beats_matched_not_confirmed"] = compare(
            summary,
            "high_sponsorship_options_confirmed",
            "high_sponsorship_options_not_confirmed",
            comparator,
            "median",
        )
        support[f"confirmed_mean_{comparator}_beats_missing_options"] = compare(
            summary,
            "high_sponsorship_options_confirmed",
            "high_sponsorship_missing_options",
            comparator,
            "mean",
        )
    summary["support"] = support
    return summary


def source_summary(
    rows: list[dict[str, Any]],
    options_summary: dict[str, Any],
) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    matched_rows = [row for row in rows if row.get("options_context_available")]
    return {
        "source_outcome_ledger": repo_rel(KOVA_LEDGER),
        "source_exists": KOVA_LEDGER.exists(),
        "source_rows": len(rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "option_matched_rows": len(matched_rows),
        "option_matched_ticker_count": len(
            {str(row.get("ticker") or "").upper() for row in matched_rows if row.get("ticker")}
        ),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "options_summary": options_summary,
    }


def evaluate_gate4(attribution: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = attribution[ACCEPTANCE_RULE["primary_horizon"]]
    confirmed = primary["bucket_summary"]["high_sponsorship_options_confirmed"]
    matched_not_confirmed = primary["bucket_summary"][
        "high_sponsorship_options_not_confirmed"
    ]
    missing = primary["bucket_summary"]["high_sponsorship_missing_options"]
    concentration_report = confirmed["cash_positive_concentration"]
    checks: dict[str, bool] = {
        "primary_confirmed_sample_min_passed": confirmed["n"]
        >= ACCEPTANCE_RULE["min_primary_confirmed_rows"],
        "primary_matched_not_confirmed_sample_min_passed": matched_not_confirmed["n"]
        >= ACCEPTANCE_RULE["min_primary_matched_not_confirmed_rows"],
        "primary_missing_options_sample_min_passed": missing["n"]
        >= ACCEPTANCE_RULE["min_primary_missing_options_rows"],
        "primary_confirmed_asof_dates_min_passed": confirmed["asof_date_count"]
        >= ACCEPTANCE_RULE["min_primary_asof_dates"],
        "concentration_hhi_passed": (
            concentration_report["positive_pnl_hhi"] is not None
            and concentration_report["positive_pnl_hhi"]
            <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
        ),
        "concentration_max_share_passed": (
            concentration_report["max_single_positive_pnl_share"] is not None
            and concentration_report["max_single_positive_pnl_share"]
            <= ACCEPTANCE_RULE["max_single_positive_pnl_share"]
        ),
    }
    support_counts: dict[str, int] = {}
    for comparator in COMPARATORS:
        checks[f"confirmed_mean_{comparator}_beats_matched_not_confirmed"] = primary[
            "support"
        ][f"confirmed_mean_{comparator}_beats_matched_not_confirmed"]
        checks[f"confirmed_median_{comparator}_beats_matched_not_confirmed"] = primary[
            "support"
        ][f"confirmed_median_{comparator}_beats_matched_not_confirmed"]
        checks[f"confirmed_mean_{comparator}_beats_missing_options"] = primary["support"][
            f"confirmed_mean_{comparator}_beats_missing_options"
        ]
        support_counts[f"mean_{comparator}_confirmed_beats_matched_horizon_count"] = sum(
            1
            for summary in attribution.values()
            if summary["support"].get(
                f"confirmed_mean_{comparator}_beats_matched_not_confirmed"
            )
        )
        checks[f"multi_horizon_mean_{comparator}_support"] = (
            support_counts[f"mean_{comparator}_confirmed_beats_matched_horizon_count"]
            >= ACCEPTANCE_RULE["min_supporting_horizons_confirmed_beats_matched"]
        )

    failed = [key for key, value in checks.items() if not value]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_kova_sec13f_options_cross_evidence_lead_not_promoted"
            if observed_only_lead
            else "rejected_no_kova_sec13f_options_cross_evidence_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "support_counts": support_counts,
        "lead_limitations": [
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "10d outcomes remain pending and are excluded from the decision.",
            "Options rows are forward-observation context with vendor-asof and open-interest lag caveats.",
            "No shared helper, daily adapter, ranking rule, sizing rule, or live behavior was promoted.",
        ],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
    }


def calibration(prediction: dict[str, Any], observed_only_lead: bool, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1 if observed_only_lead else 0
    expected_modes = prediction.get("main_failure_modes") or []
    return {
        "predicted_success_probability": probability,
        "actual_success": actual,
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": expected_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(set(expected_modes).intersection(failed)),
        "surprise_note": (
            "The options cross-evidence split passed all observed-only checks, but remains lead-only."
            if observed_only_lead
            else "The options cross-evidence did not add enough separation beyond the SEC13F sponsorship lead."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    before = baseline_metrics()
    kova_rows = assign_sponsorship_buckets(add_sponsorship_scores(read_jsonl(KOVA_LEDGER)))
    options_by_key, options_summary = load_options_by_ticker_date()
    rows = join_options(kova_rows, options_by_key)
    attribution = {horizon: summarize_horizon(rows, horizon) for horizon in HORIZONS}
    gate4 = evaluate_gate4(attribution)
    status = "observed_only_positive_lead" if gate4["observed_only_lead"] else "observed_only_rejected"
    decision = gate4["decision"]
    primary = attribution[ACCEPTANCE_RULE["primary_horizon"]]
    why_result_happened = (
        "The fixed options bullish-pressure cross-evidence "
        f"{'did' if gate4['observed_only_lead'] else 'did not'} improve the "
        "high-SEC13F-sponsorship Kova forward rows across the predeclared 5d "
        "cash/SPY/QQQ checks. This remains forward-only attribution and did "
        "not promote any trading behavior."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": gate4["observed_only_lead"],
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, gate4["observed_only_lead"], gate4["failed_reasons"]),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed without override. The nearest family was "
                    "Kova SEC13F sponsorship, whose reopen condition explicitly "
                    "allows options cross-evidence."
                ),
                "exp-20260624-018": (
                    "Observed-only positive SEC13F sponsorship lead. This run "
                    "does not retune holder/value/position-count sponsorship; it "
                    "tests the allowed options cross-evidence interaction."
                ),
                "exp-20260624-019": (
                    "Rejected coownership-network relation follow-up on the same "
                    "partial forward rows."
                ),
                "exp-20260624-020": (
                    "Accepted options forward ledger refresh through the 2026-06-23 "
                    "quote date. Options outcomes are still pending, so this run "
                    "uses options only as decision-time context."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: compute fixed SEC13F "
                "sponsorship tertiles, compute fixed options bullish-pressure "
                "tertiles from same-entry-date option context, and compare "
                "high-sponsorship confirmed rows against high-sponsorship "
                "matched/not-confirmed and missing-options rows."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if primary 5d sample floors pass, "
                "confirmed rows beat matched/not-confirmed rows on mean and "
                "median cash/SPY/QQQ, confirmed rows beat missing-options rows "
                "by mean cash/SPY/QQQ, at least two horizons support confirmed "
                "> matched by mean, and confirmed positive-PnL concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_outcome_ledger": repo_rel(KOVA_LEDGER),
            "options_ledgers": [repo_rel(path) for path in OPTIONS_LEDGERS],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizons": HORIZONS,
            "primary_horizon": ACCEPTANCE_RULE["primary_horizon"],
            "acceptance_rule": ACCEPTANCE_RULE,
            "sponsorship_score_definition": (
                "Average percentile rank of log1p(sec13f_holder_count), "
                "log1p(sec13f_total_value_usd), and "
                "log1p(sec13f_position_row_count) among SEC13F-ok rows."
            ),
            "options_score_definition": (
                "Average percentile rank of low put/call volume ratio, low "
                "put-minus-call volume-weighted IV, high liquid-contract rate, "
                "and low median spread among available option observation rows. "
                "Open interest is excluded from the score because the ledger "
                "marks same-day OI as lagged/caveated."
            ),
            "join_rule": (
                "Join option context by ticker and options usable_trade_date == "
                "Kova entry_date/planned_entry_date, so option observations are "
                "decision-time context for the Kova forward entry date."
            ),
        },
        "source_summary": source_summary(rows, options_summary),
        "attribution": {str(key): value for key, value in attribution.items()},
        "primary_summary": {
            "horizon": ACCEPTANCE_RULE["primary_horizon"],
            "high_sponsorship_rows": primary["high_sponsorship_rows"],
            "option_matched_high_sponsorship_rows": primary[
                "option_matched_high_sponsorship_rows"
            ],
            "confirmed": primary["bucket_summary"][
                "high_sponsorship_options_confirmed"
            ],
            "matched_not_confirmed": primary["bucket_summary"][
                "high_sponsorship_options_not_confirmed"
            ],
            "missing_options": primary["bucket_summary"][
                "high_sponsorship_missing_options"
            ],
            "support": primary["support"],
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows) and bool(options_by_key),
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "entry_date",
                "target_price",
                "sec13f_status",
                "sec13f_holder_count",
                "sec13f_total_value_usd",
                "sec13f_position_row_count",
                "options usable_trade_date",
                "put_call_volume_ratio",
                "put_minus_call_volume_weighted_iv",
                "liquid_contract_rate",
                "median_spread_pct",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
            ],
            "source_summary": source_summary(rows, options_summary),
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(rows),
            "signals_survived": attribution[ACCEPTANCE_RULE["primary_horizon"]][
                "settled_rows"
            ],
            "survival_rate": round(
                attribution[ACCEPTANCE_RULE["primary_horizon"]]["settled_rows"] / len(rows),
                4,
            )
            if rows
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why_result_happened,
            "forbidden_near_neighbor_retry": (
                "Do not retry this by sweeping Kova SEC13F sponsorship score, "
                "options put/call volume, IV skew, liquidity, spread, open "
                "interest, option-score threshold, top-N, hold, cooldown, or "
                "notional on the same partial forward rows."
            ),
            "new_evidence_required": (
                "A valid retry needs enough closed 10d replacement-value rows, "
                "materially richer PIT manager/active-flow provenance, true "
                "borrow-fee/utilization/loan-availability evidence, or historical "
                "PIT options-chain coverage with vendor-as-of controls."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(KOVA_LEDGER),
            *[repo_rel(path) for path in OPTIONS_LEDGERS],
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-018.json",
            "experiments/logs/exp-20260624-019.json",
            "experiments/logs/exp-20260624-020.json",
            "experiments/logs/exp-20260623-010.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(LOG_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "source_summary",
        "primary_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def card_group_line(name: str, group: dict[str, Any]) -> str:
    metrics = group["replacement_metrics"]
    return "| {name} | {n} | {tickers} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=group["n"],
        tickers=group["ticker_count"],
        cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
        spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
        qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
        median_cash=money(metrics["replacement_value_vs_cash_usd"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]
    rows = [
        "| Group | Rows | Tickers | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|",
        card_group_line("confirmed", primary["confirmed"]),
        card_group_line("matched_not_confirmed", primary["matched_not_confirmed"]),
        card_group_line("missing_options", primary["missing_options"]),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F + options cross-evidence attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 5d high-sponsorship rows: `{primary['high_sponsorship_rows']}`",
            f"- 5d option-matched high-sponsorship rows: `{primary['option_matched_high_sponsorship_rows']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 5d Groups",
            "",
            *rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        KOVA_LEDGER,
        *OPTIONS_LEDGERS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": payload["allowed_write_scope"],
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    primary = payload["primary_summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "primary_confirmed_rows": primary["confirmed"]["n"],
                "primary_matched_not_confirmed_rows": primary["matched_not_confirmed"]["n"],
                "primary_missing_options_rows": primary["missing_options"]["n"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
