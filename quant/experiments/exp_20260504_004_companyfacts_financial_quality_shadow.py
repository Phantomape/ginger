"""exp-20260504-004 SEC Companyfacts financial-quality shadow replay.

Shadow-only alpha search. It tests whether newly backfilled PIT-safe SEC
Companyfacts fields add information beyond raw filing type or price reaction.
No production/backtest entry, ranking, sizing, or exit logic is changed.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EXPERIMENT_ID = "exp-20260504-004"
COMPANYFACTS_PATH = DATA_DIR / "non_ohlcv" / "sec_companyfacts_selected_20241002_20260421.jsonl"
SEC_EVENTS_PATH = DATA_DIR / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "companyfacts_financial_quality_shadow.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "companyfacts_financial_quality_shadow_20260504.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
BASELINE_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / "exp-20260503-051.json"

SNAPSHOT_FILES = {
    "old_thin": DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    "late_strong": DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
}
WINDOWS = OrderedDict([
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
])

HORIZONS = (5, 10, 20)
FLOW_FIELDS = {
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps_diluted",
    "eps_basic",
    "operating_cash_flow",
    "capex",
}
INSTANT_FIELDS = {"inventory", "receivables", "assets", "liabilities", "equity"}
EVENT_FORMS = {"8-K", "10-Q", "10-K"}


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        out = float(value)
        if math.isfinite(out):
            return out
    return None


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or abs(start) <= 1e-9:
        return None
    return end / abs(start) - (1.0 if start > 0 else -1.0)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) <= 1e-9:
        return None
    return numerator / denominator


def _safe_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe_payload(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path, {})
    raw = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        converted = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            converted.append({
                "date": date_value,
                "open": _as_float(row.get("Open") if "Open" in row else row.get("open")),
                "close": _as_float(row.get("Close") if "Close" in row else row.get("close")),
                "volume": _as_float(row.get("Volume") if "Volume" in row else row.get("volume")),
            })
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _idx_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] > target:
            return idx
    return None


def load_companyfacts(path: Path = COMPANYFACTS_PATH) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], list[dict[str, Any]]]]:
    by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_ticker_canonical: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _load_jsonl(path):
        ticker = str(row.get("ticker") or "").upper()
        canonical = str(row.get("canonical") or "")
        accession = row.get("accession_number")
        if not ticker or not canonical:
            continue
        normalized = dict(row)
        normalized["ticker"] = ticker
        normalized["value"] = _as_float(row.get("value"))
        if accession:
            by_accession[str(accession)].append(normalized)
        by_ticker_canonical[(ticker, canonical)].append(normalized)
    for rows in by_accession.values():
        rows.sort(key=lambda item: (item.get("end") or "", item.get("canonical") or "", item.get("duration_days") or -1))
    for rows in by_ticker_canonical.values():
        rows.sort(key=lambda item: (item.get("end") or "", item.get("filed") or ""))
    return dict(by_accession), dict(by_ticker_canonical)


def _duration_target(form_base: str) -> tuple[int, int] | None:
    if form_base == "10-K":
        return (330, 390)
    if form_base in {"10-Q", "8-K"}:
        return (70, 110)
    return None


def select_current_fact(rows: list[dict[str, Any]], canonical: str, form_base: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get("canonical") == canonical and row.get("value") is not None]
    if not candidates:
        return None
    if canonical in INSTANT_FIELDS:
        return sorted(candidates, key=lambda row: (row.get("end") or "", row.get("filed") or ""), reverse=True)[0]

    target = _duration_target(form_base)
    if target:
        lo, hi = target
        in_range = [
            row for row in candidates
            if isinstance(row.get("duration_days"), int) and lo <= row["duration_days"] <= hi
        ]
        if in_range:
            return sorted(in_range, key=lambda row: (row.get("end") or "", -(row.get("duration_days") or 0)), reverse=True)[0]

    return sorted(
        candidates,
        key=lambda row: (
            row.get("end") or "",
            -(abs((row.get("duration_days") or 365) - 365)),
        ),
        reverse=True,
    )[0]


def _duration_compatible(current: dict[str, Any], prior: dict[str, Any]) -> bool:
    current_duration = current.get("duration_days")
    prior_duration = prior.get("duration_days")
    if current_duration is None and prior_duration is None:
        return True
    if not isinstance(current_duration, int) or not isinstance(prior_duration, int):
        return False
    tolerance = 20 if current_duration <= 130 else 55
    return abs(current_duration - prior_duration) <= tolerance


def find_prior_fact(
    current: dict[str, Any],
    all_by_ticker_canonical: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    ticker = current["ticker"]
    canonical = current["canonical"]
    current_end = _parse_date(current.get("end"))
    current_filed = str(current.get("filed") or "")
    if current_end is None:
        return None
    target = current_end - timedelta(days=365)
    candidates = []
    for row in all_by_ticker_canonical.get((ticker, canonical), []):
        row_end = _parse_date(row.get("end"))
        if row_end is None or row_end >= current_end:
            continue
        if current_filed and str(row.get("filed") or "") > current_filed:
            continue
        if row.get("unit") != current.get("unit"):
            continue
        if not _duration_compatible(current, row):
            continue
        gap_days = abs((row_end - target).days)
        if gap_days > 80:
            continue
        candidates.append((gap_days, str(row.get("filed") or ""), row))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[1]), reverse=False)[0][2]


def _metric_pair(
    current_by_field: dict[str, dict[str, Any]],
    all_by_ticker_canonical: dict[tuple[str, str], list[dict[str, Any]]],
    field: str,
) -> tuple[float | None, float | None, float | None]:
    current = current_by_field.get(field)
    if not current:
        return None, None, None
    prior = find_prior_fact(current, all_by_ticker_canonical)
    current_value = _as_float(current.get("value"))
    prior_value = _as_float(prior.get("value")) if prior else None
    return current_value, prior_value, _pct_change(prior_value, current_value)


def quality_features(
    accession_rows: list[dict[str, Any]],
    all_by_ticker_canonical: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    form_base: str,
) -> dict[str, Any]:
    current_by_field = {
        field: fact
        for field in sorted(FLOW_FIELDS | INSTANT_FIELDS)
        if (fact := select_current_fact(accession_rows, field, form_base)) is not None
    }

    metrics: dict[str, Any] = {}
    for field in ["revenue", "gross_profit", "operating_income", "net_income", "eps_diluted", "operating_cash_flow", "capex", "inventory", "receivables"]:
        current_value, prior_value, yoy = _metric_pair(current_by_field, all_by_ticker_canonical, field)
        metrics[f"{field}_current"] = _round(current_value)
        metrics[f"{field}_prior"] = _round(prior_value)
        metrics[f"{field}_yoy"] = _round(yoy)

    current_fcf = None
    prior_fcf = None
    if metrics.get("operating_cash_flow_current") is not None and metrics.get("capex_current") is not None:
        current_fcf = metrics["operating_cash_flow_current"] - abs(metrics["capex_current"])
    if metrics.get("operating_cash_flow_prior") is not None and metrics.get("capex_prior") is not None:
        prior_fcf = metrics["operating_cash_flow_prior"] - abs(metrics["capex_prior"])
    metrics["fcf_current"] = _round(current_fcf)
    metrics["fcf_prior"] = _round(prior_fcf)
    metrics["fcf_yoy"] = _round(_pct_change(prior_fcf, current_fcf))

    gross_margin_current = _ratio(metrics.get("gross_profit_current"), metrics.get("revenue_current"))
    gross_margin_prior = _ratio(metrics.get("gross_profit_prior"), metrics.get("revenue_prior"))
    metrics["gross_margin_current"] = _round(gross_margin_current)
    metrics["gross_margin_prior"] = _round(gross_margin_prior)
    metrics["gross_margin_delta"] = _round(
        gross_margin_current - gross_margin_prior
        if gross_margin_current is not None and gross_margin_prior is not None
        else None
    )

    score = 0
    components = []
    revenue_yoy = metrics.get("revenue_yoy")
    gross_margin_delta = metrics.get("gross_margin_delta")
    operating_income_yoy = metrics.get("operating_income_yoy")
    net_income_yoy = metrics.get("net_income_yoy")
    eps_yoy = metrics.get("eps_diluted_yoy")
    fcf_yoy = metrics.get("fcf_yoy")
    inventory_yoy = metrics.get("inventory_yoy")
    receivables_yoy = metrics.get("receivables_yoy")

    if isinstance(revenue_yoy, (int, float)):
        if revenue_yoy >= 0.05:
            score += 1
            components.append("revenue_yoy_positive")
        elif revenue_yoy <= -0.05:
            score -= 1
            components.append("revenue_yoy_negative")
    if isinstance(gross_margin_delta, (int, float)):
        if gross_margin_delta >= 0:
            score += 1
            components.append("gross_margin_stable_or_up")
        elif gross_margin_delta <= -0.02:
            score -= 1
            components.append("gross_margin_down_gt_2pp")
    if isinstance(operating_income_yoy, (int, float)):
        if operating_income_yoy >= 0:
            score += 1
            components.append("operating_income_yoy_positive")
        elif operating_income_yoy <= -0.10:
            score -= 1
            components.append("operating_income_yoy_negative")
    if isinstance(net_income_yoy, (int, float)):
        if net_income_yoy >= 0:
            score += 1
            components.append("net_income_yoy_positive")
        elif net_income_yoy <= -0.10:
            score -= 1
            components.append("net_income_yoy_negative")
    if isinstance(eps_yoy, (int, float)):
        if eps_yoy >= 0:
            score += 1
            components.append("eps_yoy_positive")
        elif eps_yoy <= -0.10:
            score -= 1
            components.append("eps_yoy_negative")
    if isinstance(fcf_yoy, (int, float)):
        if fcf_yoy >= 0:
            score += 1
            components.append("fcf_yoy_positive")
        elif fcf_yoy <= -0.10:
            score -= 1
            components.append("fcf_yoy_negative")

    if isinstance(revenue_yoy, (int, float)) and isinstance(inventory_yoy, (int, float)) and inventory_yoy > revenue_yoy + 0.20:
        score -= 1
        components.append("inventory_growth_outpaces_revenue")
    if isinstance(revenue_yoy, (int, float)) and isinstance(receivables_yoy, (int, float)) and receivables_yoy > revenue_yoy + 0.20:
        score -= 1
        components.append("receivables_growth_outpaces_revenue")

    if score >= 3:
        bucket = "high_quality"
    elif score >= 1:
        bucket = "positive_quality"
    elif score == 0:
        bucket = "neutral_quality"
    else:
        bucket = "warning_quality"

    return {
        "financial_quality_score": score,
        "financial_quality_bucket": bucket,
        "financial_quality_components": components,
        "financial_metrics": metrics,
        "fact_field_count": len(current_by_field),
        "fact_fields_present": sorted(current_by_field),
        "fact_period_end": max((fact.get("end") or "" for fact in current_by_field.values()), default=None),
    }


def _filing_category(row: dict[str, Any]) -> str:
    form = row.get("form_base")
    items = set(row.get("eight_k_item_codes") or [])
    if form == "8-K" and "2.02" in items:
        return "8k_2_02_results"
    if form in {"10-Q", "10-K"}:
        return "periodic_10q_10k"
    return "other_financial_filing"


def load_financial_filing_events(
    by_accession: dict[str, list[dict[str, Any]]],
    path: Path = SEC_EVENTS_PATH,
) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for row in _load_jsonl(path):
        ticker = str(row.get("ticker") or "").upper()
        accession = row.get("accession_number")
        form_base = str(row.get("form_base") or "").upper()
        if not ticker or not accession or accession not in by_accession:
            continue
        if form_base not in EVENT_FORMS:
            continue
        if form_base == "8-K" and "2.02" not in (row.get("eight_k_item_codes") or []):
            continue
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable:
            continue
        key = (ticker, accession, usable)
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(row)
        normalized["ticker"] = ticker
        normalized["form_base"] = form_base
        normalized["filing_category"] = _filing_category(normalized)
        rows.append(normalized)
    return sorted(rows, key=lambda item: (item["usable_trade_date"], item["ticker"], item["accession_number"]))


def evaluate_price(
    event: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    window_label: str,
) -> dict[str, Any]:
    row = dict(event)
    row["window"] = window_label
    ticker_rows = snapshot.get(event["ticker"])
    spy_rows = snapshot.get("SPY")
    qqq_rows = snapshot.get("QQQ")
    if not ticker_rows or not spy_rows:
        row["price_status"] = "missing_ticker_or_spy_price"
        return row
    reaction_idx = _idx_on_or_after(ticker_rows, str(event.get("usable_trade_date") or "")[:10])
    spy_reaction_idx = _idx_on_or_after(spy_rows, str(event.get("usable_trade_date") or "")[:10])
    if reaction_idx is None or spy_reaction_idx is None:
        row["price_status"] = "no_reaction_day"
        return row
    if reaction_idx == 0 or spy_reaction_idx == 0:
        row["price_status"] = "no_previous_close"
        return row
    entry_idx = _idx_after(ticker_rows, ticker_rows[reaction_idx]["date"])
    spy_entry_idx = _idx_after(spy_rows, spy_rows[spy_reaction_idx]["date"])
    if entry_idx is None or spy_entry_idx is None:
        row["price_status"] = "no_entry_day"
        return row

    reaction_return = _pct_change(ticker_rows[reaction_idx - 1]["close"], ticker_rows[reaction_idx]["close"])
    spy_reaction_return = _pct_change(spy_rows[spy_reaction_idx - 1]["close"], spy_rows[spy_reaction_idx]["close"])
    reaction_excess = (
        reaction_return - spy_reaction_return
        if reaction_return is not None and spy_reaction_return is not None
        else None
    )
    qqq_entry_idx = None
    if qqq_rows:
        qqq_reaction_idx = _idx_on_or_after(qqq_rows, str(event.get("usable_trade_date") or "")[:10])
        if qqq_reaction_idx is not None:
            qqq_entry_idx = _idx_after(qqq_rows, qqq_rows[qqq_reaction_idx]["date"])

    row.update({
        "price_status": "covered",
        "reaction_date": ticker_rows[reaction_idx]["date"],
        "entry_date": ticker_rows[entry_idx]["date"],
        "reaction_return": _round(reaction_return),
        "spy_reaction_return": _round(spy_reaction_return),
        "reaction_excess_return": _round(reaction_excess),
        "horizons": {},
    })
    entry_open = ticker_rows[entry_idx]["open"]
    spy_entry_open = spy_rows[spy_entry_idx]["open"]
    qqq_entry_open = qqq_rows[qqq_entry_idx]["open"] if qqq_rows and qqq_entry_idx is not None else None
    for horizon in HORIZONS:
        key = f"{horizon}d"
        end_idx = entry_idx + horizon
        spy_end_idx = spy_entry_idx + horizon
        if end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
            row["horizons"][key] = {"status": "pending"}
            continue
        ticker_return = _pct_change(entry_open, ticker_rows[end_idx]["close"])
        spy_return = _pct_change(spy_entry_open, spy_rows[spy_end_idx]["close"])
        if ticker_return is None or spy_return is None:
            row["horizons"][key] = {"status": "bad_price"}
            continue
        horizon_payload = {
            "status": "valid",
            "return": _round(ticker_return),
            "spy_return": _round(spy_return),
            "excess_return": _round(ticker_return - spy_return),
            "end_date": ticker_rows[end_idx]["date"],
        }
        if qqq_rows and qqq_entry_idx is not None and qqq_entry_open is not None:
            qqq_end_idx = qqq_entry_idx + horizon
            if qqq_end_idx < len(qqq_rows):
                qqq_return = _pct_change(qqq_entry_open, qqq_rows[qqq_end_idx]["close"])
                horizon_payload["qqq_return"] = _round(qqq_return)
                horizon_payload["excess_vs_qqq"] = (
                    _round(ticker_return - qqq_return)
                    if qqq_return is not None
                    else None
                )
        row["horizons"][key] = horizon_payload
    return row


def _valid_values(rows: list[dict[str, Any]], horizon_key: str, field: str = "excess_return") -> list[float]:
    values = []
    for row in rows:
        data = (row.get("horizons") or {}).get(horizon_key) or {}
        value = data.get(field)
        if data.get("status") == "valid" and isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _summary(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "win_rate": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"{horizon}d": {
            "return": _summary(_valid_values(rows, f"{horizon}d", "return")),
            "excess_return": _summary(_valid_values(rows, f"{horizon}d", "excess_return")),
            "excess_vs_qqq": _summary(_valid_values(rows, f"{horizon}d", "excess_vs_qqq")),
        }
        for horizon in HORIZONS
    }


def summarize_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {
        group_key: {
            "event_count": len(group_rows),
            "forward_distribution": summarize_forward(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def _load_baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_LOG, {})
    return payload.get("before_metrics") or {}


def _compact_event(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("financial_metrics") or {}
    return {
        "ticker": row.get("ticker"),
        "window": row.get("window"),
        "form_base": row.get("form_base"),
        "filing_category": row.get("filing_category"),
        "usable_trade_date": row.get("usable_trade_date"),
        "reaction_date": row.get("reaction_date"),
        "entry_date": row.get("entry_date"),
        "accession_number": row.get("accession_number"),
        "financial_quality_score": row.get("financial_quality_score"),
        "financial_quality_bucket": row.get("financial_quality_bucket"),
        "financial_quality_components": row.get("financial_quality_components"),
        "revenue_yoy": metrics.get("revenue_yoy"),
        "gross_margin_delta": metrics.get("gross_margin_delta"),
        "net_income_yoy": metrics.get("net_income_yoy"),
        "eps_diluted_yoy": metrics.get("eps_diluted_yoy"),
        "fcf_yoy": metrics.get("fcf_yoy"),
        "inventory_yoy": metrics.get("inventory_yoy"),
        "receivables_yoy": metrics.get("receivables_yoy"),
        "reaction_excess_return": row.get("reaction_excess_return"),
        "horizons": row.get("horizons"),
    }


def build_payload() -> dict[str, Any]:
    by_accession, by_ticker_canonical = load_companyfacts(COMPANYFACTS_PATH)
    raw_events = load_financial_filing_events(by_accession, SEC_EVENTS_PATH)
    snapshots = {label: load_snapshot(path) for label, path in SNAPSHOT_FILES.items()}

    evaluated = []
    for event in raw_events:
        accession_rows = by_accession.get(str(event.get("accession_number"))) or []
        quality = quality_features(accession_rows, by_ticker_canonical, form_base=event["form_base"])
        enriched = dict(event)
        enriched.update(quality)
        for label, cfg in WINDOWS.items():
            usable = str(event.get("usable_trade_date") or "")[:10]
            if cfg["start"] <= usable <= cfg["end"]:
                evaluated.append(evaluate_price(enriched, snapshots[label], label))
                break

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    high_quality = [row for row in covered if row.get("financial_quality_bucket") == "high_quality"]
    warning_quality = [row for row in covered if row.get("financial_quality_bucket") == "warning_quality"]
    high_10d = _valid_values(high_quality, "10d")
    warning_10d = _valid_values(warning_quality, "10d")
    high_positive_window_count = 0
    for label in WINDOWS:
        values = _valid_values([row for row in high_quality if row.get("window") == label], "10d")
        if values and mean(values) > 0:
            high_positive_window_count += 1

    if len(high_10d) >= 20 and mean(high_10d) > 0:
        if (
            high_positive_window_count >= 2
            and (not warning_10d or mean(high_10d) > mean(warning_10d))
        ):
            status = "shadow_promising_not_promoted"
            decision = "shadow_promising_not_promoted"
            decision_rationale = (
                "The high-quality XBRL/companyfacts cohort has enough valid samples and positive "
                "10d excess drift in at least two windows, but it remains shadow-only until tested "
                "as a shared production/backtest ranking feature against accepted A/B slot opportunity cost."
            )
            next_action = (
                "Freeze this companyfacts quality definition and test it only as a default-off "
                "existing-candidate ranking/confirmation overlay with slot replacement attribution."
            )
        else:
            status = "observed_only_not_promoted"
            decision = "observed_only_not_promoted"
            decision_rationale = (
                "The simple XBRL/companyfacts quality score is not promotion-quality: high-quality "
                "events are only mildly positive on aggregate and the warning-quality bucket performs "
                "as well or better, so the score is not a reliable monotonic ranking signal."
            )
            next_action = (
                "Do not tune nearby point weights. A valid retry needs LLM filing-text grading, "
                "analyst revisions, or a cleaner same-quarter XBRL extraction for earnings releases."
            )
    else:
        status = "observed_only_not_promoted"
        decision = "observed_only_not_promoted"
        decision_rationale = (
            "The XBRL/companyfacts financial-quality grade did not produce a promotion-quality "
            "multi-window drift result with the current simple scoring definition."
        )
        next_action = (
            "Do not tune nearby point weights. A valid retry needs LLM filing-text grading, "
            "analyst revisions, or a cleaner same-quarter XBRL extraction for earnings releases."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "sec_companyfacts_financial_quality_alpha",
        "change_type": "shadow_financial_quality_replay",
        "hypothesis": (
            "Newly backfilled PIT-safe SEC Companyfacts fields can grade financial-statement "
            "quality shocks and identify post-filing drift better than form type or first reaction alone."
        ),
        "alpha_hypothesis_category": "entry_ranking_event_confirmation",
        "history_check": {
            "mechanism_insight_guardrail": (
                "Prior SEC/earnings retries were blocked by missing normalized XBRL/companyfacts fields. "
                "This run adds those fields and does not repeat raw reaction thresholds or simple SEC checklists."
            ),
            "similar_experiments": {
                "exp-20260503-016/019/022/024/027/029/031/035/036": "Same family reached data_gap because companyfacts_or_xbrl_rows were zero.",
                "exp-20260503-051": "Raw SEC filing reaction drift was rejected.",
                "exp-20260504-002": "Earnings + results 8-K + positive reaction packet was observed-only and not promoted.",
            },
            "why_not_simple_repeat": (
                "The new input is the normalized SEC Companyfacts table with revenue, margin, income, cash-flow, inventory, and receivables fields."
            ),
        },
        "parameters": {
            "single_causal_variable": "SEC Companyfacts financial-quality grade",
            "quality_score_components": [
                "revenue_yoy",
                "gross_margin_delta",
                "operating_income_yoy",
                "net_income_yoy",
                "eps_diluted_yoy",
                "fcf_yoy",
                "inventory_growth_outpaces_revenue",
                "receivables_growth_outpaces_revenue",
            ],
            "event_forms": sorted(EVENT_FORMS),
            "entry_timing": "next trading-day open after SEC public-PIT usable trade date reaction close",
            "forward_horizons": list(HORIZONS),
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": _load_baseline_metrics(),
        "after_metrics": _load_baseline_metrics(),
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
        },
        "gate4": {
            "passed": False,
            "basis": "No promoted strategy change; fixed-window baseline metrics are unchanged by design.",
        },
        "coverage": {
            "companyfacts_accession_count": len(by_accession),
            "financial_filing_event_count": len(raw_events),
            "evaluated_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "high_quality_event_count": len(high_quality),
            "high_quality_valid_10d_count": len(high_10d),
            "high_quality_positive_10d_window_count": high_positive_window_count,
            "warning_quality_valid_10d_count": len(warning_10d),
            "warning_quality_event_count": len(warning_quality),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
            "by_form_base": dict(Counter(row.get("form_base") for row in covered)),
            "by_quality_bucket": dict(Counter(row.get("financial_quality_bucket") for row in covered)),
            "by_window": dict(Counter(row.get("window") for row in covered)),
        },
        "shadow_metrics": {
            "all_financial_filing_events": {
                "forward_distribution": summarize_forward(covered),
                "by_window": summarize_group(covered, "window"),
                "by_form_base": summarize_group(covered, "form_base"),
                "by_filing_category": summarize_group(covered, "filing_category"),
                "by_quality_bucket": summarize_group(covered, "financial_quality_bucket"),
            },
            "high_quality": {
                "event_count": len(high_quality),
                "forward_distribution": summarize_forward(high_quality),
                "by_window": summarize_group(high_quality, "window"),
                "sample_events": [_compact_event(row) for row in high_quality[:60]],
            },
            "warning_quality": {
                "event_count": len(warning_quality),
                "forward_distribution": summarize_forward(warning_quality),
                "by_window": summarize_group(warning_quality, "window"),
            },
            "top_10d_excess": [
                _compact_event(row)
                for row in sorted(
                    [
                        row for row in covered
                        if isinstance(((row.get("horizons") or {}).get("10d") or {}).get("excess_return"), (int, float))
                    ],
                    key=lambda item: ((item.get("horizons") or {}).get("10d") or {}).get("excess_return"),
                    reverse=True,
                )[:25]
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if decision != "observed_only_not_promoted" else decision_rationale,
        "next_retry_requires": [
            "Do not tune nearby quality-score point weights without new information.",
            "A valid retry should add LLM filing-text grading, analyst revisions, or cleaner XBRL extraction from earnings-release 8-Ks.",
            "Any production use must be implemented in a shared production/backtest feature module.",
        ],
        "next_action": next_action,
        "related_files": [
            "data/non_ohlcv/sec_companyfacts_selected_20241002_20260421.jsonl",
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
            "quant/sec_companyfacts_backfill.py",
            "quant/experiments/exp_20260504_004_companyfacts_financial_quality_shadow.py",
            "data/experiments/exp-20260504-004/companyfacts_financial_quality_shadow.json",
            "docs/experiments/logs/exp-20260504-004.json",
            "docs/non_ohlcv_data_audit/companyfacts_financial_quality_shadow_20260504.md",
        ],
    }
    return _safe_payload(payload)


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _table(title: str, rows: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", "", "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |", "|---|---:|---:|---:|---:|---:|"]
    for key, data in rows.items():
        forward = data.get("forward_distribution") or {}
        d10 = ((forward.get("10d") or {}).get("excess_return") or {})
        d20 = ((forward.get("20d") or {}).get("excess_return") or {})
        lines.append(
            f"| {key} | {data.get('event_count')} | "
            f"{_format_pct(d10.get('avg'))} | {_format_pct(d10.get('win_rate'))} | "
            f"{_format_pct(d20.get('avg'))} | {_format_pct(d20.get('win_rate'))} |"
        )
    lines.append("")
    return lines


def build_report(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    high = payload["shadow_metrics"]["high_quality"]
    high_10d = high["forward_distribution"]["10d"]["excess_return"]
    high_20d = high["forward_distribution"]["20d"]["excess_return"]
    lines = [
        "# SEC Companyfacts financial-quality shadow replay",
        "",
        f"- Experiment: `{EXPERIMENT_ID}`",
        f"- Status: `{payload['status']}`",
        "- Production impact: shadow-only; no strategy logic changed.",
        "",
        "## Headline",
        "",
        payload["decision_rationale"],
        "",
        "## Coverage",
        "",
        f"- Companyfacts accessions: `{coverage['companyfacts_accession_count']}`",
        f"- Financial filing events: `{coverage['financial_filing_event_count']}`",
        f"- Price-covered events: `{coverage['price_covered_count']}`",
        f"- High-quality events: `{coverage['high_quality_event_count']}`",
        f"- High-quality valid 10d outcomes: `{coverage['high_quality_valid_10d_count']}`",
        "",
        "## High Quality",
        "",
        "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| high_quality | {high['event_count']} | "
            f"{_format_pct(high_10d.get('avg'))} | {_format_pct(high_10d.get('win_rate'))} | "
            f"{_format_pct(high_20d.get('avg'))} | {_format_pct(high_20d.get('win_rate'))} |"
        ),
        "",
    ]
    lines.extend(_table("By Quality Bucket", payload["shadow_metrics"]["all_financial_filing_events"]["by_quality_bucket"]))
    lines.extend(_table("By Window", payload["shadow_metrics"]["all_financial_filing_events"]["by_window"]))
    lines.extend([
        "## Gate / Caveat",
        "",
        "- Gate 4 is intentionally not passed because this is not a promoted strategy change.",
        "- SEC Companyfacts `filed` date is a public-availability PIT proxy; it does not prove local production observation.",
        "- This first score is deliberately simple; nearby point-weight tuning is not a valid next step.",
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC Companyfacts financial quality",
        "summary": payload["decision_rationale"],
        "best_variant": "high_quality",
        "best_variant_gate4": False,
        "delta_metrics": {
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "coverage": payload["coverage"],
            "high_quality": payload["shadow_metrics"]["high_quality"]["forward_distribution"],
        },
        "production_impact": payload["production_impact"],
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_text(REPORT_MD, build_report(payload))

    compact = dict(payload)
    compact.pop("shadow_metrics", None)
    compact["shadow_metrics_summary"] = {
        "high_quality": payload["shadow_metrics"]["high_quality"],
        "warning_quality": payload["shadow_metrics"]["warning_quality"],
        "by_quality_bucket": payload["shadow_metrics"]["all_financial_filing_events"]["by_quality_bucket"],
    }
    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "coverage": payload["coverage"],
        "high_quality_10d_excess": payload["shadow_metrics"]["high_quality"]["forward_distribution"]["10d"]["excess_return"],
        "high_quality_by_window": payload["shadow_metrics"]["high_quality"]["by_window"],
        "by_quality_bucket": payload["shadow_metrics"]["all_financial_filing_events"]["by_quality_bucket"],
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
