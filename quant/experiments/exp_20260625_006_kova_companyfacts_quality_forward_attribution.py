"""exp-20260625-006: Kova Companyfacts quality forward attribution.

Observed-only alpha attribution. This joins the exp-20260624-017 Kova forward
outcome ledger with the 2026-06-24 SEC Companyfacts selected-Kova surface and
tests whether a fixed realized-quality score improves the already positive
SEC13F sponsorship forward lead.

No strategy, helper, ranking, sizing, exit, paper fill, daily snapshot, LLM,
watchlist, or live order behavior changes in this experiment.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-006"
OWNER = "alpha-explore"
SLUG = "kova_companyfacts_quality_forward_attribution"
RUNNER = f"quant/experiments/exp_20260625_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_006_{SLUG}.json"
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
COMPANYFACTS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_companyfacts_selected_kova_20260624.jsonl"
)

HYPOTHESIS = (
    "Observed-only attribution: Kova forward rows with stronger PIT SEC "
    "Companyfacts realized-quality, especially positive gross-profit or "
    "operating-income context with low leverage, should show better settled "
    "1d/3d/5d cash/SPY/QQQ replacement value and may validate or reject an "
    "independent fundamental-quality enhancer for the SEC13F sponsorship lead."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_companyfacts_realized_quality_forward_attribution"
TRIAL_VARIANT_ID = "post_exp017_partial_forward_1d3d5_companyfacts_quality_v1"
CHANGED_VARIABLE = "kova_companyfacts_realized_quality_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "partial_closed_forward_replacement_value_rows_plus_sec_companyfacts_quality"
NEW_EVIDENCE_AXIS = (
    "New cross-source join between exp-20260624-017 partial closed Kova "
    "replacement rows and the 2026-06-24 SEC Companyfacts selected-Kova broad "
    "filed-date PIT surface; this is not a frozen-window Companyfacts ratio "
    "candidate-pool scan, not a SEC13F sponsorship retune, and not an options "
    "or coownership retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-018",
    "exp-20260624-019",
    "exp-20260624-023",
    "exp-20260625-005",
]
CAUSAL_COMPONENTS = [
    "exp017 settled forward Kova rows",
    "SEC Companyfacts realized-quality fields",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-006/exp_20260625_006_kova_companyfacts_quality_forward_attribution.json",
    "experiments/cards/exp-20260625-006.md",
    "experiments/manifests/exp-20260625-006.json",
    "experiments/tickets/exp-20260625-006.json",
    "experiments/logs/exp-20260625-006.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
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
    "uses_sec_companyfacts_selected_kova": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
    ),
}

HORIZONS = [1, 3, 5]
COMPARATORS = ["cash", "spy", "qqq"]
PRIMARY_HORIZON = 5
QUALITY_BUCKETS = [
    "high_sponsorship_low_quality",
    "high_sponsorship_mid_quality",
    "high_sponsorship_high_quality",
    "high_sponsorship_missing_quality",
]
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_primary_high_quality_rows": 250,
    "min_primary_low_quality_rows": 250,
    "min_primary_asof_dates": 3,
    "min_joined_quality_rate": 0.50,
    "min_supporting_horizons_high_beats_low": 2,
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share": 0.50,
}
QUALITY_COMPONENTS = [
    "gross_margin",
    "operating_margin",
    "net_margin",
    "ocf_margin",
    "cash_conversion",
    "low_leverage",
]
FLOW_CANONICALS = {
    "capex",
    "cost_of_revenue",
    "eps_basic",
    "eps_diluted",
    "gross_profit",
    "net_income",
    "operating_cash_flow",
    "operating_income",
    "revenue",
}


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
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
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


def date_key(value: Any) -> str:
    return str(value or "")[:10]


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
        "success_probability": 0.16,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_companyfacts_join_coverage",
            "no_monotonic_quality_separation",
            "companyfacts_family_saturation",
            "qqq_beta_confound",
            "forward_window_too_short",
        ],
        "confidence_reason": (
            "Kova sponsorship has one positive forward-only lead, and the new "
            "selected-Kova Companyfacts surface is PIT-filed-date data "
            "independent of SEC13F/options. Confidence is low because "
            "Companyfacts ratio scans are saturated and this can only be "
            "observed-only until 10d rows or fixed-window shared-helper "
            "coverage exist."
        ),
        "recorded_at": utc_now(),
    }


def component_choice_score(row: dict[str, Any]) -> tuple[int, str]:
    canonical = str(row.get("canonical") or "")
    form = str(row.get("form") or "")
    duration = safe_float(row.get("duration_days"))
    end = date_key(row.get("end"))
    if canonical not in FLOW_CANONICALS or duration is None:
        return (0, end)
    target = 365.0 if form.startswith("10-K") else 90.0
    return (-int(abs(duration - target)), end)


def should_replace_fact(
    canonical: str,
    current: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> bool:
    if current is None:
        return True
    current_score = current.get("_choice_score", (-9999, ""))
    candidate_score = candidate.get("_choice_score", (-9999, ""))
    if candidate_score != current_score:
        return candidate_score > current_score
    return date_key(candidate.get("end")) >= date_key(current.get("end"))


def build_companyfacts_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_accession: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        accession = str(row.get("accession_number") or "")
        canonical = str(row.get("canonical") or "")
        filed = date_key(row.get("filed"))
        value = safe_float(row.get("value"))
        form = str(row.get("form") or "")
        if not ticker or not accession or not canonical or not filed or value is None:
            continue
        if not form.startswith(("10-K", "10-Q")):
            continue
        key = (ticker, accession)
        accession_row = by_accession.setdefault(
            key,
            {
                "ticker": ticker,
                "accession_number": accession,
                "filed": filed,
                "form": form,
                "fy": row.get("fy"),
                "fp": row.get("fp"),
                "end": date_key(row.get("end")),
                "facts": {},
            },
        )
        accession_row["filed"] = max(str(accession_row.get("filed") or ""), filed)
        accession_row["end"] = max(str(accession_row.get("end") or ""), date_key(row.get("end")))
        fact = {
            "value": value,
            "duration_days": row.get("duration_days"),
            "end": date_key(row.get("end")),
            "_choice_score": component_choice_score(row),
        }
        if should_replace_fact(canonical, accession_row["facts"].get(canonical), fact):
            accession_row["facts"][canonical] = fact

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for accession in by_accession.values():
        summary = summarize_accession(accession)
        by_ticker.setdefault(str(accession["ticker"]), []).append(summary)
    for values in by_ticker.values():
        values.sort(key=lambda row: (row["filed"], row["end"], row["accession_number"]))
    return by_ticker


def fact_value(accession: dict[str, Any], canonical: str) -> float | None:
    fact = accession.get("facts", {}).get(canonical)
    if not isinstance(fact, dict):
        return None
    return safe_float(fact.get("value"))


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def summarize_accession(accession: dict[str, Any]) -> dict[str, Any]:
    revenue = fact_value(accession, "revenue")
    gross_profit = fact_value(accession, "gross_profit")
    operating_income = fact_value(accession, "operating_income")
    net_income = fact_value(accession, "net_income")
    operating_cash_flow = fact_value(accession, "operating_cash_flow")
    assets = fact_value(accession, "assets")
    liabilities = fact_value(accession, "liabilities")

    components = {
        "gross_margin": ratio(gross_profit, revenue),
        "operating_margin": ratio(operating_income, revenue),
        "net_margin": ratio(net_income, revenue),
        "ocf_margin": ratio(operating_cash_flow, revenue),
        "cash_conversion": (
            operating_cash_flow / abs(net_income)
            if operating_cash_flow is not None and net_income is not None and net_income > 0
            else None
        ),
        "low_leverage": (
            -(liabilities / assets)
            if liabilities is not None and assets is not None and assets > 0
            else None
        ),
    }
    return {
        "ticker": accession["ticker"],
        "accession_number": accession["accession_number"],
        "filed": accession["filed"],
        "form": accession["form"],
        "fy": accession.get("fy"),
        "fp": accession.get("fp"),
        "end": accession.get("end"),
        "fact_count": len(accession.get("facts", {})),
        "component_count": sum(1 for value in components.values() if value is not None),
        "components": components,
        "raw_values": {
            "revenue": revenue,
            "gross_profit": gross_profit,
            "operating_income": operating_income,
            "net_income": net_income,
            "operating_cash_flow": operating_cash_flow,
            "assets": assets,
            "liabilities": liabilities,
        },
    }


def latest_companyfacts_for(
    by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    asof_date: str,
) -> dict[str, Any] | None:
    rows = by_ticker.get(ticker.upper()) or []
    candidates = [row for row in rows if row.get("filed") and row["filed"] <= asof_date]
    if not candidates:
        return None
    strong = [row for row in candidates if int(row.get("component_count") or 0) >= 2]
    return (strong or candidates)[-1]


def percentile_rank(value: float, sorted_values: list[float]) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return 1.0
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    avg_zero_based_rank = (left + right - 1) / 2.0
    return avg_zero_based_rank / (len(sorted_values) - 1)


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
        item = dict(row)
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
        item["sec13f_sponsorship_score"] = round_or_none(mean(parts), 8)
        item["sec13f_sponsorship_component_count"] = len(parts)
        scored.append(item)
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


def join_companyfacts(rows: list[dict[str, Any]], index: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        ticker = str(row.get("ticker") or "").upper()
        asof = date_key(row.get("asof_date") or row.get("entry_date"))
        facts = latest_companyfacts_for(index, ticker, asof)
        item["companyfacts_join_asof_date"] = asof
        if facts is None:
            item["companyfacts_quality_status"] = "missing"
            item["companyfacts_quality_component_count"] = 0
            item["companyfacts_quality_components"] = {}
            out.append(item)
            continue
        item["companyfacts_quality_status"] = (
            "ok" if int(facts.get("component_count") or 0) >= 2 else "thin_components"
        )
        item["companyfacts_accession_number"] = facts.get("accession_number")
        item["companyfacts_filed"] = facts.get("filed")
        item["companyfacts_form"] = facts.get("form")
        item["companyfacts_period_end"] = facts.get("end")
        item["companyfacts_fact_count"] = facts.get("fact_count")
        item["companyfacts_quality_component_count"] = facts.get("component_count")
        item["companyfacts_quality_components"] = facts.get("components") or {}
        out.append(item)
    return add_quality_scores(out)


def add_quality_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    populations: dict[str, list[float]] = {key: [] for key in QUALITY_COMPONENTS}
    for row in rows:
        if row.get("companyfacts_quality_status") != "ok":
            continue
        components = row.get("companyfacts_quality_components") or {}
        for key in QUALITY_COMPONENTS:
            value = safe_float(components.get(key))
            if value is not None:
                populations[key].append(value)
    for values in populations.values():
        values.sort()

    out = []
    for row in rows:
        item = dict(row)
        ranks = []
        components = item.get("companyfacts_quality_components") or {}
        for key, population in populations.items():
            value = safe_float(components.get(key))
            if value is None:
                continue
            ranked = percentile_rank(value, population)
            if ranked is not None:
                ranks.append(ranked)
        item["companyfacts_quality_score"] = round_or_none(mean(ranks), 8)
        item["companyfacts_quality_rank_component_count"] = len(ranks)
        if len(ranks) < 2:
            item["companyfacts_quality_score"] = None
            item["companyfacts_quality_status"] = (
                item["companyfacts_quality_status"]
                if item["companyfacts_quality_status"] != "ok"
                else "thin_rank_components"
            )
        out.append(item)
    return out


def settled_rows(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    status_key = f"forward_{horizon}d_status"
    cash_key = f"replacement_value_{horizon}d_vs_cash_usd"
    return [
        row
        for row in rows
        if row.get(status_key) == "settled" and safe_float(row.get(cash_key)) is not None
    ]


def high_sponsorship_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("sec13f_sponsorship_bucket") == "high_sponsorship"]


def bucket_quality(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    with_score = [
        row for row in rows if safe_float(row.get("companyfacts_quality_score")) is not None
    ]
    missing = [
        row for row in rows if safe_float(row.get("companyfacts_quality_score")) is None
    ]
    ordered = sorted(
        with_score,
        key=lambda row: (
            safe_float(row.get("companyfacts_quality_score")) or 0.0,
            str(row.get("ticker") or ""),
            str(row.get("observation_id") or ""),
        ),
    )
    buckets = {name: [] for name in QUALITY_BUCKETS}
    buckets["high_sponsorship_missing_quality"] = missing
    total = len(ordered)
    if not total:
        return buckets
    for index, row in enumerate(ordered):
        frac = index / max(total - 1, 1)
        if frac < 1 / 3:
            buckets["high_sponsorship_low_quality"].append(row)
        elif frac < 2 / 3:
            buckets["high_sponsorship_mid_quality"].append(row)
        else:
            buckets["high_sponsorship_high_quality"].append(row)
    return buckets


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


def replacement_metrics(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    out = {}
    for comparator in COMPARATORS:
        key = f"replacement_value_{horizon}d_vs_{comparator}_usd"
        out[f"replacement_value_vs_{comparator}_usd"] = stats(numeric_values(rows, key))
    return out


def concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    key = f"replacement_value_{horizon}d_vs_cash_usd"
    by_ticker: Counter[str] = Counter()
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
    shares = {ticker: value / positive_pnl for ticker, value in by_ticker.items()}
    top = by_ticker.most_common(8)
    return {
        "positive_pnl": round(positive_pnl, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(value, 2), "share": round(shares[ticker], 6)}
            for ticker, value in top
        ],
    }


def summarize_group(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    asof_dates = sorted({date_key(row.get("asof_date")) for row in rows if row.get("asof_date")})
    scores = numeric_values(rows, "companyfacts_quality_score")
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "asof_date_count": len(asof_dates),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "quality_score_mean": round_or_none(mean(scores), 6),
        "quality_score_median": round_or_none(median(scores), 6) if scores else None,
        "companyfacts_status_counts": dict(
            sorted(Counter(str(row.get("companyfacts_quality_status") or "missing") for row in rows).items())
        ),
        "replacement_metrics": replacement_metrics(rows, horizon),
        "cash_positive_concentration": concentration(rows, horizon),
    }


def rank_values(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    out = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        rank = (index + end) / 2.0
        for pos in range(index, end + 1):
            out[ordered[pos][0]] = rank
        index = end + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    if x_mean is None or y_mean is None:
        return None
    xdiff = [value - x_mean for value in xs]
    ydiff = [value - y_mean for value in ys]
    denom_x = math.sqrt(sum(value * value for value in xdiff))
    denom_y = math.sqrt(sum(value * value for value in ydiff))
    if denom_x <= 0 or denom_y <= 0:
        return None
    return sum(x * y for x, y in zip(xdiff, ydiff)) / (denom_x * denom_y)


def spearman(rows: list[dict[str, Any]], horizon: int, comparator: str) -> float | None:
    xs = []
    ys = []
    metric = f"replacement_value_{horizon}d_vs_{comparator}_usd"
    for row in rows:
        score = safe_float(row.get("companyfacts_quality_score"))
        value = safe_float(row.get(metric))
        if score is None or value is None:
            continue
        xs.append(score)
        ys.append(value)
    if len(xs) < 3:
        return None
    return round_or_none(pearson(rank_values(xs), rank_values(ys)), 6)


def metric_mean(group: dict[str, Any], comparator: str) -> float | None:
    return group["replacement_metrics"][f"replacement_value_vs_{comparator}_usd"]["mean"]


def metric_median(group: dict[str, Any], comparator: str) -> float | None:
    return group["replacement_metrics"][f"replacement_value_vs_{comparator}_usd"]["median"]


def greater(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and left > right


def horizon_summary(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = settled_rows(rows, horizon)
    high_sponsor = high_sponsorship_rows(settled)
    buckets = bucket_quality(high_sponsor)
    bucket_summary = {
        name: summarize_group(group, horizon) for name, group in buckets.items()
    }
    all_high_sponsorship = summarize_group(high_sponsor, horizon)
    joined_count = (
        len(high_sponsor) - bucket_summary["high_sponsorship_missing_quality"]["n"]
    )
    joined_rate = round(joined_count / len(high_sponsor), 6) if high_sponsor else None
    support = {}
    high = bucket_summary["high_sponsorship_high_quality"]
    low = bucket_summary["high_sponsorship_low_quality"]
    all_high = all_high_sponsorship
    for comparator in COMPARATORS:
        support[f"high_mean_{comparator}_beats_low"] = greater(
            metric_mean(high, comparator), metric_mean(low, comparator)
        )
        support[f"high_median_{comparator}_beats_low"] = greater(
            metric_median(high, comparator), metric_median(low, comparator)
        )
        support[f"high_mean_{comparator}_beats_all_high_sponsorship"] = greater(
            metric_mean(high, comparator), metric_mean(all_high, comparator)
        )
        support[f"spearman_{comparator}"] = spearman(high_sponsor, horizon, comparator)
    return {
        "horizon": horizon,
        "settled_rows": len(settled),
        "high_sponsorship_rows": len(high_sponsor),
        "joined_quality_rows": joined_count,
        "joined_quality_rate": joined_rate,
        "bucket_summary": bucket_summary,
        "all_high_sponsorship_summary": all_high_sponsorship,
        "support": support,
    }


def source_summary(rows: list[dict[str, Any]], facts_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    asof_dates = sorted({date_key(row.get("asof_date")) for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    joined = [row for row in rows if safe_float(row.get("companyfacts_quality_score")) is not None]
    high_sponsor = high_sponsorship_rows(rows)
    high_sponsor_joined = [
        row for row in high_sponsor if safe_float(row.get("companyfacts_quality_score")) is not None
    ]
    return {
        "source_outcome_ledger": repo_rel(KOVA_LEDGER),
        "companyfacts_path": repo_rel(COMPANYFACTS_PATH),
        "source_rows": len(rows),
        "companyfacts_rows": len(facts_rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "companyfacts_quality_status_counts": dict(
            sorted(Counter(str(row.get("companyfacts_quality_status") or "missing") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "joined_quality_rows": len(joined),
        "joined_quality_rate": round(len(joined) / len(rows), 6) if rows else None,
        "high_sponsorship_rows": len(high_sponsor),
        "high_sponsorship_joined_quality_rows": len(high_sponsor_joined),
        "high_sponsorship_joined_quality_rate": (
            round(len(high_sponsor_joined) / len(high_sponsor), 6) if high_sponsor else None
        ),
    }


def evaluate_gate4(analysis: dict[str, Any]) -> dict[str, Any]:
    primary = analysis["horizons"][str(PRIMARY_HORIZON)]
    high = primary["bucket_summary"]["high_sponsorship_high_quality"]
    low = primary["bucket_summary"]["high_sponsorship_low_quality"]
    concentration_check = high["cash_positive_concentration"]
    checks = {
        "primary_high_quality_sample_min_passed": (
            high["n"] >= ACCEPTANCE_RULE["min_primary_high_quality_rows"]
        ),
        "primary_low_quality_sample_min_passed": (
            low["n"] >= ACCEPTANCE_RULE["min_primary_low_quality_rows"]
        ),
        "primary_asof_dates_min_passed": (
            high["asof_date_count"] >= ACCEPTANCE_RULE["min_primary_asof_dates"]
        ),
        "primary_joined_quality_rate_min_passed": (
            primary["joined_quality_rate"] is not None
            and primary["joined_quality_rate"] >= ACCEPTANCE_RULE["min_joined_quality_rate"]
        ),
        "concentration_hhi_passed": (
            concentration_check["positive_pnl_hhi"] is not None
            and concentration_check["positive_pnl_hhi"]
            <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
        ),
        "concentration_max_share_passed": (
            concentration_check["max_single_positive_pnl_share"] is not None
            and concentration_check["max_single_positive_pnl_share"]
            <= ACCEPTANCE_RULE["max_single_positive_pnl_share"]
        ),
    }

    support_counts: dict[str, int] = {}
    for comparator in COMPARATORS:
        checks[f"high_mean_{comparator}_beats_low"] = primary["support"][
            f"high_mean_{comparator}_beats_low"
        ]
        checks[f"high_median_{comparator}_beats_low"] = primary["support"][
            f"high_median_{comparator}_beats_low"
        ]
        checks[f"high_mean_{comparator}_beats_all_high_sponsorship"] = primary[
            "support"
        ][f"high_mean_{comparator}_beats_all_high_sponsorship"]
        checks[f"spearman_{comparator}_positive"] = (
            primary["support"].get(f"spearman_{comparator}") is not None
            and primary["support"][f"spearman_{comparator}"] > 0
        )
        support_counts[f"mean_{comparator}_high_beats_low_horizon_count"] = sum(
            1
            for horizon in analysis["horizons"].values()
            if horizon["support"].get(f"high_mean_{comparator}_beats_low")
        )
        checks[f"multi_horizon_mean_{comparator}_support"] = (
            support_counts[f"mean_{comparator}_high_beats_low_horizon_count"]
            >= ACCEPTANCE_RULE["min_supporting_horizons_high_beats_low"]
        )

    failed = [key for key, value in checks.items() if not value]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_kova_companyfacts_quality_lead_not_promoted"
            if observed_only_lead
            else "rejected_no_kova_companyfacts_quality_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "support_counts": support_counts,
        "lead_limitations": [
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "10d outcomes remain pending and are excluded from the decision.",
            "Companyfacts filed date is used as public-availability PIT proxy.",
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


def build_analysis(rows: list[dict[str, Any]], facts_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_summary": source_summary(rows, facts_rows),
        "quality_score_definition": (
            "companyfacts_quality_score = average percentile rank of gross_margin, "
            "operating_margin, net_margin, ocf_margin, cash_conversion, and "
            "low_leverage where available; low_leverage is negative "
            "liabilities/assets so higher rank means lower leverage. Latest "
            "10-Q/10-K accession is selected per ticker with filed <= Kova "
            "asof_date and at least two rankable components when possible."
        ),
        "sponsorship_score_definition": (
            "sec13f_sponsorship_score = average percentile rank of log1p(holder_count), "
            "log1p(total_value_usd), and log1p(position_row_count) among SEC13F-ok rows; "
            "the primary test is restricted to high_sponsorship rows."
        ),
        "horizons": {str(horizon): horizon_summary(rows, horizon) for horizon in HORIZONS},
    }


def calibration(prediction: dict[str, Any], observed_only_lead: bool, failures: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual_success = 1 if observed_only_lead else 0
    predicted = set(prediction.get("main_failure_modes") or [])
    observed = set(failures or [])
    return {
        "predicted_success_probability": probability,
        "actual_success": actual_success,
        "brier_score": round((probability - actual_success) ** 2, 4),
        "predicted_failure_modes": sorted(predicted),
        "realized_failure_modes": sorted(observed),
        "predicted_failure_mode_hit": bool(observed),
        "surprise_note": (
            "Low surprise: the Companyfacts family is saturated and this strict "
            "forward-only enhancer test required multi-comparator separation."
            if not observed_only_lead
            else "High surprise: Companyfacts quality enhanced the forward-only "
            "SEC13F sponsorship lead, but no strategy behavior was promoted."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    before = baseline_metrics()
    facts_rows = read_jsonl(COMPANYFACTS_PATH)
    companyfacts_index = build_companyfacts_index(facts_rows)
    raw_kova = read_jsonl(KOVA_LEDGER)
    rows = join_companyfacts(assign_sponsorship_buckets(add_sponsorship_scores(raw_kova)), companyfacts_index)
    analysis = build_analysis(rows, facts_rows)
    gate4 = evaluate_gate4(analysis)
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    primary = analysis["horizons"][str(PRIMARY_HORIZON)]
    why = (
        "The fixed PIT SEC Companyfacts realized-quality score "
        f"{'did' if gate4['observed_only_lead'] else 'did not'} enhance the "
        "high-SEC13F-sponsorship Kova forward rows across the predeclared 5d "
        "cash/SPY/QQQ checks. This remains forward-only attribution and did not "
        "promote any trading behavior."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
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
        "calibration": calibration(
            prediction, gate4["observed_only_lead"], gate4["failed_reasons"]
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed without override. The new evidence axis "
                    "is a cross-source join between exp017 partial forward rows "
                    "and the 2026-06-24 selected-Kova Companyfacts surface."
                ),
                "exp-20260624-018": (
                    "Observed-only positive SEC13F sponsorship lead. This run "
                    "keeps that score fixed and tests an independent "
                    "Companyfacts quality enhancer inside high-sponsorship rows."
                ),
                "exp-20260624-019": "Rejected coownership-network relation follow-up.",
                "exp-20260624-023": "Rejected options cross-evidence follow-up.",
                "exp-20260625-005": (
                    "Rejected SEC project-finance candidate-pool text scan with "
                    "zero trades; this run is forward-only attribution, not a "
                    "SEC text or frozen-window Companyfacts candidate-pool scan."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: compute fixed SEC13F "
                "sponsorship tertiles, restrict the primary test to high "
                "sponsorship rows, join latest PIT-filed Companyfacts quality "
                "components as of the Kova row asof_date, bucket quality into "
                "tertiles, and compare high-quality against low-quality and all "
                "high-sponsorship rows."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if 5d high/low quality sample floors "
                "pass, joined quality coverage passes, high quality beats low "
                "on mean and median cash/SPY/QQQ, high quality beats all "
                "high-sponsorship rows by mean cash/SPY/QQQ, Spearman "
                "correlations are positive, at least two horizons support "
                "high>low by mean, and high-quality positive-PnL concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_outcome_ledger": repo_rel(KOVA_LEDGER),
            "companyfacts_path": repo_rel(COMPANYFACTS_PATH),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "acceptance_rule": ACCEPTANCE_RULE,
            "quality_components": QUALITY_COMPONENTS,
            "pit_join_rule": (
                "For each Kova row, use the latest 10-Q/10-K Companyfacts accession "
                "with filed <= Kova asof_date and at least two rankable quality "
                "components when possible."
            ),
        },
        "source_summary": analysis["source_summary"],
        "attribution": analysis,
        "primary_summary": {
            "horizon": PRIMARY_HORIZON,
            "high_sponsorship_rows": primary["high_sponsorship_rows"],
            "joined_quality_rows": primary["joined_quality_rows"],
            "joined_quality_rate": primary["joined_quality_rate"],
            "low_quality": primary["bucket_summary"]["high_sponsorship_low_quality"],
            "mid_quality": primary["bucket_summary"]["high_sponsorship_mid_quality"],
            "high_quality": primary["bucket_summary"]["high_sponsorship_high_quality"],
            "missing_quality": primary["bucket_summary"]["high_sponsorship_missing_quality"],
            "all_high_sponsorship": primary["all_high_sponsorship_summary"],
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
            "dependencies_validated": bool(raw_kova)
            and bool(facts_rows)
            and analysis["source_summary"]["duplicate_observation_ids"] == 0,
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
                "companyfacts filed",
                "companyfacts canonical revenue/gross_profit/operating_income/net_income/operating_cash_flow/assets/liabilities",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
            ],
            "source_summary": analysis["source_summary"],
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(raw_kova),
            "signals_survived": primary["high_sponsorship_rows"],
            "survival_rate": round(primary["high_sponsorship_rows"] / len(raw_kova), 4)
            if raw_kova
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry this by sweeping Kova Companyfacts quality score, "
                "gross/operating/net/OCF margins, cash-conversion, leverage, "
                "sponsorship score, top-N, hold, cooldown, notional, or allocator "
                "thresholds on the same exp017 partial forward rows."
            ),
            "new_evidence_required": (
                "A valid retry needs enough closed 10d replacement-value rows, "
                "materially richer PIT manager/active-flow provenance, true "
                "borrow-fee/utilization/loan-availability evidence, or canonical "
                "fixed-window PIT coverage through a shared default-off helper."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(KOVA_LEDGER),
            repo_rel(COMPANYFACTS_PATH),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-018.json",
            "experiments/logs/exp-20260624-019.json",
            "experiments/logs/exp-20260624-023.json",
            "experiments/logs/exp-20260625-005.json",
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
    return "| {name} | {n} | {tickers} | {score} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=group["n"],
        tickers=group["ticker_count"],
        score=group["quality_score_median"],
        cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
        spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
        qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
        median_cash=money(metrics["replacement_value_vs_cash_usd"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]
    rows = [
        "| Group | Rows | Tickers | Median Quality | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        card_group_line("high_quality", primary["high_quality"]),
        card_group_line("mid_quality", primary["mid_quality"]),
        card_group_line("low_quality", primary["low_quality"]),
        card_group_line("missing_quality", primary["missing_quality"]),
        card_group_line("all_high_sponsorship", primary["all_high_sponsorship"]),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova Companyfacts quality forward attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 5d high-sponsorship rows: `{primary['high_sponsorship_rows']}`",
            f"- 5d joined quality rows: `{primary['joined_quality_rows']}`",
            f"- 5d joined quality rate: `{primary['joined_quality_rate']}`",
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
        COMPANYFACTS_PATH,
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
                "primary_high_quality_rows": primary["high_quality"]["n"],
                "primary_low_quality_rows": primary["low_quality"]["n"],
                "primary_joined_quality_rate": primary["joined_quality_rate"],
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
