"""exp-20260527-015: Kova fundamental + RS proxy shadow ranking.

This experiment reads the accepted default-off VCP top-2 rank-notional paper
sleeve from exp-20260526-007 and joins two Kova/CANSLIM-style PIT surfaces:

- SEC Companyfacts quarterly EPS and revenue YoY growth.
- Ginger daily-OHLCV RS proxy percentiles versus SPY.

The single causal metadata field is ``kova_fundamental_rs_proxy_score_v1``.
No entry, exit, universe, VCP rule, rank-notional profile, LLM/news path, live
orders, or production trade enablement changes here.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _flatten,
    _load_json,
    _load_snapshot,
    _now,
    _num,
    _repo_rel,
    _round,
    _safe,
    _write_json,
    _write_text,
)

QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from kova_data_sidecar import compute_rs_proxy_rows, load_selected_companyfacts_rows  # noqa: E402


EXPERIMENT_ID = "exp-20260527-015"
STEM = "kova_fundamental_rs_proxy_shadow_ranking"
TRIAL_FAMILY = "kova_canslim_proxy_shadow_ranking"
CHANGED_VARIABLE = "kova_fundamental_rs_proxy_score_v1"
RULE_VERSION = "kova_fundamental_rs_proxy_score_v1"

SOURCE_VARIANT = "rank2_125"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

EPS_GROWTH_THRESHOLD = 0.25
REVENUE_GROWTH_THRESHOLD = 0.20
RS_LEADER_THRESHOLD = 0.90
RS_WINDOWS = (20, 60, 120)
QUARTERLY_DURATION_MIN = 60
QUARTERLY_DURATION_MAX = 130

BUCKET_STRONG = "fundamental_growth_and_rs_leader_proxy"
BUCKET_FUND_ONLY = "fundamental_growth_without_rs_leader_proxy"
BUCKET_RS_ONLY = "rs_leader_without_fundamental_growth"
BUCKET_BELOW = "below_kova_growth_rs_proxy"
BUCKET_UNAVAILABLE = "unavailable"
BUCKET_ORDER = [
    BUCKET_STRONG,
    BUCKET_FUND_ONLY,
    BUCKET_RS_ONLY,
    BUCKET_BELOW,
    BUCKET_UNAVAILABLE,
]


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _ticker_set(source: dict[str, Any]) -> list[str]:
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in source["target_trades_by_window"].values()
        for row in rows
        if row.get("ticker")
    }
    return sorted(tickers)


def _float(value: Any) -> float | None:
    number = _num(value)
    return number if number is not None and math.isfinite(number) else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_quarterly_fact(row: dict[str, Any]) -> bool:
    duration = _float(row.get("duration_days"))
    if duration is None:
        return False
    if duration < QUARTERLY_DURATION_MIN or duration > QUARTERLY_DURATION_MAX:
        return False
    fp = str(row.get("fp") or "").upper()
    return fp in {"Q1", "Q2", "Q3", "Q4"}


def _fact_sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
    duration = _float(row.get("duration_days"))
    duration_proximity = -abs((duration or 999.0) - 91.0)
    form = str(row.get("form") or "").upper()
    form_priority = 1 if form == "10-Q" else 0
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        form_priority,
        duration_proximity,
    )


class CompanyfactsGrowthIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or "")[:10]
            value = _float(raw.get("value"))
            if canonical not in {"eps_diluted", "eps_basic", "revenue"}:
                continue
            if not ticker or not filed or value is None or not _is_quarterly_fact(raw):
                continue
            row = {
                **raw,
                "ticker": ticker,
                "canonical": canonical,
                "filed": filed,
                "value": value,
                "fy_int": _int(raw.get("fy")),
                "fp_norm": str(raw.get("fp") or "").upper(),
            }
            by_key[(ticker, canonical)].append(row)
        for bucket in by_key.values():
            bucket.sort(key=_fact_sort_key)
        self.by_key = by_key

    def growth(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any]:
        ticker_u = ticker.upper()
        rows = [
            row
            for row in self.by_key.get((ticker_u, canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not rows:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_current_quarter_fact",
            }
        current = rows[-1]
        fy = current.get("fy_int")
        fp = current.get("fp_norm")
        if fy is None or not fp:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_fiscal_period_key",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
            }
        priors = [
            row
            for row in self.by_key.get((ticker_u, canonical), [])
            if row.get("fy_int") == fy - 1
            and row.get("fp_norm") == fp
            and str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not priors:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_prior_year_same_quarter_fact",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
                "current_value": _round(current.get("value"), 6),
                "current_fp": fp,
                "current_fy": fy,
            }
        prior = sorted(priors, key=_fact_sort_key)[-1]
        current_value = _float(current.get("value"))
        prior_value = _float(prior.get("value"))
        if current_value is None or prior_value is None:
            status = "missing_current_or_prior_value"
            growth = None
        elif prior_value <= 0:
            status = "non_positive_prior_value"
            growth = None
        else:
            growth = current_value / prior_value - 1.0
            status = "ok"
        return {
            "canonical": canonical,
            "available": growth is not None,
            "status": status,
            "yoy_growth": _round(growth, 6),
            "current_value": _round(current_value, 6),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_form": current.get("form"),
            "current_fp": fp,
            "current_fy": fy,
            "current_duration_days": current.get("duration_days"),
            "prior_value": _round(prior_value, 6),
            "prior_filed": prior.get("filed"),
            "prior_period_end": prior.get("end"),
            "known_at": "SEC Companyfacts filed date <= signal_date",
        }


def _fundamental_context(
    index: CompanyfactsGrowthIndex,
    *,
    ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    diluted = index.growth(ticker, "eps_diluted", signal_date)
    basic = index.growth(ticker, "eps_basic", signal_date)
    eps = diluted if diluted.get("available") else basic
    revenue = index.growth(ticker, "revenue", signal_date)
    eps_growth = _float(eps.get("yoy_growth"))
    revenue_growth = _float(revenue.get("yoy_growth"))
    eps_pass = eps_growth is not None and eps_growth >= EPS_GROWTH_THRESHOLD
    revenue_pass = revenue_growth is not None and revenue_growth >= REVENUE_GROWTH_THRESHOLD
    pair_available = eps_growth is not None and revenue_growth is not None
    points = int(eps_pass) + int(revenue_pass)
    return {
        "kova_fundamental_rule_version": RULE_VERSION,
        "kova_fundamental_known_at": "after_signal_date_close_before_next_open_paper_entry",
        "kova_fundamental_alters_orders": False,
        "kova_fundamental_trade_enabled": False,
        "kova_eps_growth_threshold": EPS_GROWTH_THRESHOLD,
        "kova_revenue_growth_threshold": REVENUE_GROWTH_THRESHOLD,
        "kova_fundamental_quarterly_duration_min": QUARTERLY_DURATION_MIN,
        "kova_fundamental_quarterly_duration_max": QUARTERLY_DURATION_MAX,
        "kova_eps_growth_source": eps.get("canonical"),
        "kova_eps_growth_status": eps.get("status"),
        "kova_eps_yoy_growth": _round(eps_growth, 6),
        "kova_eps_growth_pass": eps_pass,
        "kova_eps_current_filed": eps.get("current_filed"),
        "kova_eps_current_period_end": eps.get("current_period_end"),
        "kova_eps_prior_filed": eps.get("prior_filed"),
        "kova_revenue_growth_status": revenue.get("status"),
        "kova_revenue_yoy_growth": _round(revenue_growth, 6),
        "kova_revenue_growth_pass": revenue_pass,
        "kova_revenue_current_filed": revenue.get("current_filed"),
        "kova_revenue_current_period_end": revenue.get("current_period_end"),
        "kova_revenue_prior_filed": revenue.get("prior_filed"),
        "kova_fundamental_growth_pair_available": pair_available,
        "kova_fundamental_growth_points_v1": points,
        "kova_fundamental_growth_pass_v1": points == 2,
    }


def _compute_rs_rows_by_window(
    source_rows_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    out: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        dates = sorted(
            {
                _date10(row.get("signal_date") or row.get("date"))
                for row in source_rows_by_window.get(label, [])
                if _date10(row.get("signal_date") or row.get("date"))
            }
        )
        by_date: dict[str, dict[str, dict[str, Any]]] = {}
        for signal_date in dates:
            rows = compute_rs_proxy_rows(
                snapshot,
                asof_date=signal_date,
                benchmark="SPY",
                windows=RS_WINDOWS,
                source_snapshot=cfg["snapshot"],
            )
            by_date[signal_date] = {
                str(row.get("ticker") or "").upper(): row for row in rows
            }
        out[label] = by_date
    return out


def _rs_context(
    rs_rows: dict[str, dict[str, dict[str, dict[str, Any]]]],
    *,
    label: str,
    ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    row = rs_rows.get(label, {}).get(signal_date, {}).get(ticker.upper())
    shell = {
        "kova_rs_proxy_rule_version": RULE_VERSION,
        "kova_rs_proxy_known_at": "daily OHLCV rows with date <= signal_date",
        "kova_rs_proxy_alters_orders": False,
        "kova_rs_proxy_trade_enabled": False,
        "kova_rs_proxy_leader_threshold": RS_LEADER_THRESHOLD,
        "kova_rs_proxy_windows": list(RS_WINDOWS),
    }
    if not row:
        return {
            **shell,
            "kova_rs_proxy_status": "missing_rs_proxy_row",
            "kova_rs_proxy_score_v1": None,
            "kova_rs_proxy_leader_pass_v1": False,
            "kova_rs_proxy_available_window_count": 0,
        }
    ranks = [
        _float(row.get(f"rs_proxy_rank_pct_{window}d"))
        for window in RS_WINDOWS
        if _float(row.get(f"rs_proxy_rank_pct_{window}d")) is not None
    ]
    score = sum(ranks) / len(ranks) if ranks else None
    return {
        **shell,
        "kova_rs_proxy_status": row.get("status"),
        "kova_rs_proxy_score_v1": _round(score, 6),
        "kova_rs_proxy_leader_pass_v1": score is not None and score >= RS_LEADER_THRESHOLD,
        "kova_rs_proxy_available_window_count": len(ranks),
        "kova_rs_proxy_asof_price_date": row.get("asof_price_date"),
        "kova_rs_proxy_row_count": row.get("row_count"),
        "kova_rs_proxy_rank_pct_20d": row.get("rs_proxy_rank_pct_20d"),
        "kova_rs_proxy_rank_pct_60d": row.get("rs_proxy_rank_pct_60d"),
        "kova_rs_proxy_rank_pct_120d": row.get("rs_proxy_rank_pct_120d"),
        "kova_rs_proxy_excess_ret_20d_vs_spy": row.get("excess_ret_20d_vs_spy"),
        "kova_rs_proxy_excess_ret_60d_vs_spy": row.get("excess_ret_60d_vs_spy"),
        "kova_rs_proxy_excess_ret_120d_vs_spy": row.get("excess_ret_120d_vs_spy"),
    }


def _score_context(fundamental: dict[str, Any], rs: dict[str, Any]) -> dict[str, Any]:
    rs_score = _float(rs.get("kova_rs_proxy_score_v1"))
    rs_available = rs_score is not None
    rs_pass = bool(rs.get("kova_rs_proxy_leader_pass_v1"))
    points = int(fundamental.get("kova_fundamental_growth_points_v1") or 0)
    fundamental_available = bool(fundamental.get("kova_fundamental_growth_pair_available"))
    fundamental_pass = bool(fundamental.get("kova_fundamental_growth_pass_v1"))
    if not rs_available and not fundamental_available:
        score = None
        bucket = BUCKET_UNAVAILABLE
    else:
        score = 0.5 * (rs_score or 0.0) + 0.25 * points
        if fundamental_pass and rs_pass:
            bucket = BUCKET_STRONG
        elif fundamental_pass:
            bucket = BUCKET_FUND_ONLY
        elif rs_pass:
            bucket = BUCKET_RS_ONLY
        else:
            bucket = BUCKET_BELOW
    return {
        "kova_fundamental_rs_proxy_rule_version": RULE_VERSION,
        CHANGED_VARIABLE: _round(score, 6),
        "kova_fundamental_rs_proxy_bucket_v1": bucket,
        "kova_fundamental_rs_proxy_known_at": (
            "after_signal_date_close_before_next_open_paper_entry"
        ),
        "kova_fundamental_rs_proxy_alters_orders": False,
        "kova_fundamental_rs_proxy_trade_enabled": False,
        "kova_fundamental_rs_proxy_formula": (
            "0.5 * average RS proxy percentile + 0.25 * EPS YoY pass + "
            "0.25 * revenue YoY pass; missing components score as zero"
        ),
    }


def _enrich_trades(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    source_rows = source["target_trades_by_window"]
    tickers = _ticker_set(source)
    max_window_end = max(cfg["end"] for cfg in WINDOWS.values())
    fact_rows = load_selected_companyfacts_rows(max_filed=max_window_end, tickers=tickers)
    fact_index = CompanyfactsGrowthIndex(fact_rows)
    rs_rows = _compute_rs_rows_by_window(source_rows)

    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        enriched: list[dict[str, Any]] = []
        for trade in source_rows.get(label, []):
            ticker = str(trade.get("ticker") or "").upper()
            signal_date = _date10(trade.get("signal_date") or trade.get("date"))
            fundamental = _fundamental_context(
                fact_index,
                ticker=ticker,
                signal_date=signal_date,
            )
            rs = _rs_context(
                rs_rows,
                label=label,
                ticker=ticker,
                signal_date=signal_date,
            )
            score = _score_context(fundamental, rs)
            enriched.append({**trade, "window": label, **fundamental, **rs, **score})
        out[label] = enriched
    return out


def _pct_sample(rows: list[dict[str, Any]], field: str) -> list[float]:
    return [
        float(value)
        for row in rows
        for value in [_num(row.get(field))]
        if value is not None
    ]


def _trade_samples(rows: list[dict[str, Any]], *, pnl_field: str = "pnl") -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date") or row.get("date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "rank": row.get("vcp_candidate_rank_on_signal_date"),
                "bucket": row.get("kova_fundamental_rs_proxy_bucket_v1"),
                CHANGED_VARIABLE: row.get(CHANGED_VARIABLE),
                "rs_score": row.get("kova_rs_proxy_score_v1"),
                "eps_yoy_growth": row.get("kova_eps_yoy_growth"),
                "revenue_yoy_growth": row.get("kova_revenue_yoy_growth"),
                "fundamental_points": row.get("kova_fundamental_growth_points_v1"),
                "pnl": _round(row.get(pnl_field), 2),
                "source_pnl": _round(row.get("pnl"), 2),
                "pnl_pct_net": _round(row.get("pnl_pct_net"), 6),
                "rank_notional_scalar": row.get("rank_notional_scalar"),
                "shadow_rank_notional_scalar": row.get(
                    "kova_score_bonus_shadow_rank_notional_scalar"
                ),
            }
        )
    return out


def _trade_summary(rows: list[dict[str, Any]], *, pnl_field: str = "pnl") -> dict[str, Any]:
    pnl_values = [float(row.get(pnl_field) or 0.0) for row in rows]
    pnl_pct_values = _pct_sample(rows, "pnl_pct_net")
    score_values = _pct_sample(rows, CHANGED_VARIABLE)
    rs_values = _pct_sample(rows, "kova_rs_proxy_score_v1")
    eps_values = _pct_sample(rows, "kova_eps_yoy_growth")
    revenue_values = _pct_sample(rows, "kova_revenue_yoy_growth")
    by_ticker_pnl: Counter[str] = Counter()
    by_window_count: Counter[str] = Counter()
    by_rank_count: Counter[str] = Counter()
    for row, pnl in zip(rows, pnl_values):
        by_ticker_pnl[str(row.get("ticker") or "").upper()] += pnl
        by_window_count[str(row.get("window") or "")] += 1
        by_rank_count[str(row.get("vcp_candidate_rank_on_signal_date") or "")] += 1
    positive_by_ticker = {
        ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0
    }
    positive_total = sum(positive_by_ticker.values())
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "win_rate": _round(
            sum(1 for value in pnl_values if value > 0) / len(pnl_values),
            6,
        )
        if pnl_values
        else None,
        "avg_pnl_pct_net": _round(
            sum(pnl_pct_values) / len(pnl_pct_values),
            6,
        )
        if pnl_pct_values
        else None,
        "avg_score": _round(sum(score_values) / len(score_values), 6)
        if score_values
        else None,
        "avg_rs_score": _round(sum(rs_values) / len(rs_values), 6)
        if rs_values
        else None,
        "avg_eps_yoy_growth": _round(sum(eps_values) / len(eps_values), 6)
        if eps_values
        else None,
        "avg_revenue_yoy_growth": _round(sum(revenue_values) / len(revenue_values), 6)
        if revenue_values
        else None,
        "by_window_count": dict(sorted(by_window_count.items())),
        "by_rank_count": dict(sorted(by_rank_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: _round(pnl, 2)
            for ticker, pnl in sorted(positive_by_ticker.items())
        },
        "max_single_positive_pnl_share": _round(
            max(positive_by_ticker.values()) / positive_total,
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "positive_pnl_hhi": _round(
            sum((pnl / positive_total) ** 2 for pnl in positive_by_ticker.values()),
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "worst_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get(pnl_field) or 0.0)[:5],
            pnl_field=pnl_field,
        ),
        "best_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get(pnl_field) or 0.0, reverse=True)[:5],
            pnl_field=pnl_field,
        ),
    }


def _group_by_bucket(
    rows: list[dict[str, Any]],
    *,
    pnl_field: str = "pnl",
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = str(row.get("kova_fundamental_rs_proxy_bucket_v1") or BUCKET_UNAVAILABLE)
        grouped[bucket].append(row)
    return OrderedDict(
        (bucket, _trade_summary(grouped.get(bucket, []), pnl_field=pnl_field))
        for bucket in BUCKET_ORDER
    )


def _group_by_window_bucket(
    rows_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    out: "OrderedDict[str, Any]" = OrderedDict()
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        out[label] = {
            "all_top2_rank_profile_trades": _trade_summary(rows),
            "by_bucket": _group_by_bucket(rows),
        }
    return out


def _group_by_rank_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = sorted(
        {
            str(row.get("vcp_candidate_rank_on_signal_date") or "")
            for row in rows
            if row.get("vcp_candidate_rank_on_signal_date") not in (None, "")
        },
        key=lambda value: int(value),
    )
    return OrderedDict(
        (
            rank,
            _group_by_bucket(
                [row for row in rows if str(row.get("vcp_candidate_rank_on_signal_date")) == rank]
            ),
        )
        for rank in ranks
    )


def _score_value(row: dict[str, Any]) -> float | None:
    return _float(row.get(CHANGED_VARIABLE))


def _apply_score_bonus_shadow(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label, rows in rows_by_window.items():
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[_date10(row.get("signal_date") or row.get("date"))].append(row)
        enriched: list[dict[str, Any]] = []
        for _, group in sorted(grouped.items()):
            group_sorted = sorted(
                group,
                key=lambda row: int(row.get("vcp_candidate_rank_on_signal_date") or 99),
            )
            scores = [_score_value(row) for row in group_sorted]
            current_scalars = [_float(row.get("rank_notional_scalar")) or 1.0 for row in group_sorted]
            score_values = [score for score in scores if score is not None]
            can_reassign = len(group_sorted) >= 2 and len(set(score_values)) >= 2
            scalar_by_id: dict[int, float] = {
                id(row): current_scalars[idx] for idx, row in enumerate(group_sorted)
            }
            reason = "unchanged_single_trade_or_tied_missing_score"
            if can_reassign:
                sorted_by_score = sorted(
                    group_sorted,
                    key=lambda row: (
                        _score_value(row) is not None,
                        _score_value(row) if _score_value(row) is not None else -1.0,
                        _float(row.get("candidate_day_rs_vs_spy")) or -999.0,
                        -int(row.get("vcp_candidate_rank_on_signal_date") or 99),
                    ),
                    reverse=True,
                )
                for row, scalar in zip(sorted_by_score, sorted(current_scalars, reverse=True)):
                    scalar_by_id[id(row)] = scalar
                reason = "highest_kova_score_receives_largest_existing_rank_notional_scalar"
            for row in group_sorted:
                scalar = scalar_by_id[id(row)]
                base_notional = _float(row.get("base_paper_notional_usd")) or 10000.0
                pnl_pct = _float(row.get("pnl_pct_net")) or 0.0
                shadow_pnl = pnl_pct * base_notional * scalar
                source_pnl = _float(row.get("pnl")) or 0.0
                enriched.append(
                    {
                        **row,
                        "kova_score_bonus_shadow_rule_version": RULE_VERSION,
                        "kova_score_bonus_shadow_alters_orders": False,
                        "kova_score_bonus_shadow_trade_enabled": False,
                        "kova_score_bonus_shadow_rank_notional_scalar": _round(scalar, 6),
                        "kova_score_bonus_shadow_paper_notional_usd": _round(
                            base_notional * scalar,
                            2,
                        ),
                        "kova_score_bonus_shadow_pnl": _round(shadow_pnl, 2),
                        "kova_score_bonus_shadow_pnl_delta_vs_source": _round(
                            shadow_pnl - source_pnl,
                            2,
                        ),
                        "kova_score_bonus_shadow_reassigned": (
                            _round(scalar, 6)
                            != _round(row.get("rank_notional_scalar"), 6)
                        ),
                        "kova_score_bonus_shadow_reason": reason,
                    }
                )
        out[label] = enriched
    return out


def _shadow_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_window: "OrderedDict[str, Any]" = OrderedDict()
    all_rows = _flatten(rows_by_window)
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        source_pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
        shadow_pnl = sum(float(row.get("kova_score_bonus_shadow_pnl") or 0.0) for row in rows)
        by_window[label] = {
            "trade_count": len(rows),
            "source_total_pnl": _round(source_pnl, 2),
            "shadow_total_pnl": _round(shadow_pnl, 2),
            "shadow_pnl_delta_vs_source": _round(shadow_pnl - source_pnl, 2),
            "reassigned_trade_count": sum(
                1 for row in rows if row.get("kova_score_bonus_shadow_reassigned")
            ),
        }
    source_total = sum(float(row.get("pnl") or 0.0) for row in all_rows)
    shadow_total = sum(float(row.get("kova_score_bonus_shadow_pnl") or 0.0) for row in all_rows)
    return {
        "aggregate": {
            "trade_count": len(all_rows),
            "source_total_pnl": _round(source_total, 2),
            "shadow_total_pnl": _round(shadow_total, 2),
            "shadow_pnl_delta_vs_source": _round(shadow_total - source_total, 2),
            "reassigned_trade_count": sum(
                1 for row in all_rows if row.get("kova_score_bonus_shadow_reassigned")
            ),
            "windows_pnl_improved": sum(
                1
                for row in by_window.values()
                if (row.get("shadow_pnl_delta_vs_source") or 0) > 0
            ),
            "windows_pnl_regressed": sum(
                1
                for row in by_window.values()
                if (row.get("shadow_pnl_delta_vs_source") or 0) < 0
            ),
        },
        "by_window": by_window,
        "summary_by_shadow_bucket": _group_by_bucket(
            all_rows,
            pnl_field="kova_score_bonus_shadow_pnl",
        ),
    }


def _coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trade_count": len(rows),
        "score_available_count": sum(1 for row in rows if row.get(CHANGED_VARIABLE) is not None),
        "fundamental_pair_available_count": sum(
            1 for row in rows if row.get("kova_fundamental_growth_pair_available")
        ),
        "fundamental_pass_count": sum(
            1 for row in rows if row.get("kova_fundamental_growth_pass_v1")
        ),
        "rs_available_count": sum(
            1 for row in rows if row.get("kova_rs_proxy_score_v1") is not None
        ),
        "rs_leader_count": sum(
            1 for row in rows if row.get("kova_rs_proxy_leader_pass_v1")
        ),
        "strong_bucket_count": sum(
            1 for row in rows if row.get("kova_fundamental_rs_proxy_bucket_v1") == BUCKET_STRONG
        ),
        "eps_growth_available_count": sum(
            1 for row in rows if row.get("kova_eps_yoy_growth") is not None
        ),
        "revenue_growth_available_count": sum(
            1 for row in rows if row.get("kova_revenue_yoy_growth") is not None
        ),
    }


def _decision(
    *,
    all_rows: list[dict[str, Any]],
    by_bucket: dict[str, Any],
    by_window_bucket: dict[str, Any],
    shadow: dict[str, Any],
    coverage: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    strong = by_bucket[BUCKET_STRONG]
    rest_rows = [
        row
        for row in all_rows
        if row.get("kova_fundamental_rs_proxy_bucket_v1") != BUCKET_STRONG
    ]
    rest = _trade_summary(rest_rows)
    strong_pnls_by_window = {
        label: by_window_bucket[label]["by_bucket"][BUCKET_STRONG]["total_pnl"]
        for label in WINDOWS
    }
    positive_strong_windows = [
        label for label, pnl in strong_pnls_by_window.items() if pnl is not None and pnl > 0
    ]
    concentration_passed = (
        strong["max_single_positive_pnl_share"] is not None
        and strong["positive_pnl_hhi"] is not None
        and strong["max_single_positive_pnl_share"] < 0.40
        and strong["positive_pnl_hhi"] < 0.30
    )
    shadow_agg = shadow["aggregate"]
    no_shadow_window_regression = shadow_agg["windows_pnl_regressed"] == 0
    promising = (
        strong["trade_count"] >= 20
        and strong["total_pnl"] is not None
        and strong["total_pnl"] > 0
        and strong["avg_pnl"] is not None
        and rest["avg_pnl"] is not None
        and strong["avg_pnl"] > rest["avg_pnl"]
        and len(positive_strong_windows) >= 2
        and concentration_passed
        and shadow_agg["shadow_pnl_delta_vs_source"] > 0
        and no_shadow_window_regression
    )
    evidence = {
        "coverage": coverage,
        "strong_trade_count_min_20": strong["trade_count"] >= 20,
        "strong_positive_aggregate": strong["total_pnl"] is not None
        and strong["total_pnl"] > 0,
        "strong_positive_windows": positive_strong_windows,
        "strong_avg_pnl": _round(strong["avg_pnl"], 2),
        "non_strong_avg_pnl": _round(rest["avg_pnl"], 2),
        "strong_beats_non_strong_avg_pnl": (
            strong["avg_pnl"] is not None
            and rest["avg_pnl"] is not None
            and strong["avg_pnl"] > rest["avg_pnl"]
        ),
        "strong_concentration_passed": concentration_passed,
        "strong_max_single_positive_pnl_share": strong["max_single_positive_pnl_share"],
        "strong_positive_pnl_hhi": strong["positive_pnl_hhi"],
        "shadow_pnl_delta_vs_source": shadow_agg["shadow_pnl_delta_vs_source"],
        "shadow_windows_pnl_improved": shadow_agg["windows_pnl_improved"],
        "shadow_windows_pnl_regressed": shadow_agg["windows_pnl_regressed"],
        "shadow_no_window_pnl_regression": no_shadow_window_regression,
    }
    if coverage["fundamental_pair_available_count"] < 20:
        return (
            "observed_only_data_gap_insufficient_kova_fundamental_rs_context",
            (
                "The Kova fundamental+RS proxy surface is not promotion-ready: fewer "
                "than 20 closed paper trades have both EPS and revenue YoY context. "
                "Keep the VCP top-2 rank-notional sleeve unchanged."
            ),
            evidence,
        )
    if promising:
        return (
            "observed_only_promising_kova_fundamental_rs_proxy_shadow_split",
            (
                "The full Kova fundamental+RS proxy bucket cleared the observed-only "
                "readout, but this run still makes no allocation or ranking change. "
                "A later closed replacement-value Gate 1-4 replay is required."
            ),
            evidence,
        )
    return (
        "observed_only_no_actionable_kova_fundamental_rs_proxy_split",
        (
            "The Kova fundamental+RS proxy score did not clear the observed-only "
            "promotion bar. Keep the VCP top-2 rank-notional sleeve unchanged and "
            "do not convert the split into a filter or rank rule."
        ),
        evidence,
    )


def _build_payload() -> dict[str, Any]:
    source = _load_source_rank_profile()
    rows_by_window = _enrich_trades(source)
    rows_by_window = _apply_score_bonus_shadow(rows_by_window)
    all_rows = _flatten(rows_by_window)
    by_bucket = _group_by_bucket(all_rows)
    by_window_bucket = _group_by_window_bucket(rows_by_window)
    by_rank_bucket = _group_by_rank_bucket(all_rows)
    coverage = _coverage_summary(all_rows)
    shadow = _shadow_summary(rows_by_window)
    decision, interpretation, decision_evidence = _decision(
        all_rows=all_rows,
        by_bucket=by_bucket,
        by_window_bucket=by_window_bucket,
        shadow=shadow,
        coverage=coverage,
    )
    source_variant = source["variant"]
    source_trade_count = sum(len(rows) for rows in source["target_trades_by_window"].values())
    bucket_counts = {
        bucket: by_bucket[bucket]["trade_count"]
        for bucket in BUCKET_ORDER
        if by_bucket[bucket]["trade_count"]
    }
    open_positions_audit = _audit_open_positions()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "created_at": _now(),
        "lane": "alpha_search",
        "registry_lane": "alpha_discovery",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "summary": interpretation,
        "alpha_hypothesis": (
            "Kova/CANSLIM-style quarterly EPS and revenue growth, combined with a "
            "Ginger OHLCV RS proxy, may identify better candidates inside the "
            "accepted default-off VCP top-2 rank-notional paper sleeve."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Ranking/candidate-pool alpha: a fixed Kova fundamental+RS proxy "
                "score may separate higher replacement-value VCP candidates."
            ),
            "2_history_check": {
                "exp-20260504-004": "Companyfacts financial-quality shadow was not promotion-quality.",
                "exp-20260504-014": "Companyfacts context did not discriminate SEC negative reactions.",
                "exp-20260525-037": "Accepted default-off VCP top-2 candidate expansion.",
                "exp-20260526-007": "Accepted VCP top-2 rank-notional profile [1.0, 1.25].",
                "exp-20260526-037": "Kova readiness audit flagged fundamentals/RS as previously unavailable.",
                "exp-20260527-001": "Accepted default-off Kova free data sidecar.",
                "exp-20260527-013": "RS-line new-high paper sleeve was rejected.",
                "exp-20260527-014": "Kova sidecar production wiring accepted default-off.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only only. Promotion would require >=20 strong-bucket "
                "trades, positive aggregate PnL, at least two positive windows, "
                "better average PnL than the rest, concentration guardrails, and "
                "positive no-regression shadow score-bonus PnL."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "single_causal_variable_definition": {
            "name": CHANGED_VARIABLE,
            "formula": (
                "0.5 * average RS proxy percentile across 20/60/120 trading days "
                "+ 0.25 if quarterly EPS YoY >= 25% + 0.25 if quarterly revenue "
                "YoY >= 20%; missing components score as zero."
            ),
            "thresholds_from_kova_pdf": {
                "eps_yoy_growth": EPS_GROWTH_THRESHOLD,
                "revenue_yoy_growth": REVENUE_GROWTH_THRESHOLD,
                "rs_proxy_leader_percentile": RS_LEADER_THRESHOLD,
            },
            "buckets": BUCKET_ORDER,
            "date_boundary": (
                "SEC facts require filed <= signal_date; OHLCV rows require "
                "Date <= signal_date."
            ),
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": (
                "This run tests a fixed metadata score and frozen-sample shadow "
                "ranking only. It does not change strategy, ranking, sizing, or "
                "orders."
            ),
            "observed_only_gate": (
                "Strong bucket has >=20 trades, positive aggregate PnL, positive "
                "PnL in at least two windows, better average PnL than the rest, "
                "max single positive contribution <40%, positive PnL HHI <0.30, "
                "and score-bonus shadow PnL improves with no window regression."
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "paper_exit": "10 trading days after signal from exp007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
        },
        "gate1": {
            "passed": True,
            "baseline_core_stack": "exp-20260517-009 accepted core stack",
            "source_paper_baseline": "exp-20260526-007 rank2_125 VCP top-2 paper sleeve",
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get(
                    "expected_value_score_delta"
                ),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "target_trade_summary": source_variant.get("target_trade_summary"),
                "source_exp037_comparison": source_variant.get("source_exp037_comparison"),
            },
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_open_position_fields": ["entry_date", "target_price"],
            "required_source_trade_fields": [
                "ticker",
                "signal_date",
                "entry_date",
                "entry_price",
                "pnl",
                "pnl_pct_net",
                "base_paper_notional_usd",
                "rank_notional_scalar",
            ],
            "required_companyfacts_fields": [
                "ticker",
                "canonical",
                "value",
                "filed",
                "fy",
                "fp",
                "duration_days",
            ],
            "required_rs_proxy_fields": ["Date", "Close", "SPY benchmark rows"],
            "field_completeness": coverage,
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "source_paper_survival_changed": False,
            "note": (
                "This is read-only attribution on already selected exp007 paper "
                "trades. It cannot reduce core survival or paper candidate survival."
            ),
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": (
                "Observed-only metadata and frozen-sample shadow ranking. A later "
                "closed replacement replay is required before any rule can be kept."
            ),
            "decision_evidence": decision_evidence,
        },
        "source_trade_count": source_trade_count,
        "enriched_trade_count": len(all_rows),
        "coverage": coverage,
        "bucket_counts": bucket_counts,
        "by_bucket": by_bucket,
        "by_window_bucket": by_window_bucket,
        "by_rank_bucket": by_rank_bucket,
        "score_bonus_shadow": shadow,
        "target_trades_by_window": rows_by_window,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "metadata_surface_changed": False,
            "read_only_attribution": True,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_015_kova_fundamental_rs_proxy_shadow_ranking.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "related_files": [
            _repo_rel(SOURCE_EXP007_JSON),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "why_not_other_changes": (
            "Did not retune VCP compression/breakout, QQQ/SPY, top-N count, "
            "rank-notional profile, sizing, exits, hold days, universe, LLM/news, "
            "intraday timing, 13F ownership, pocket-pivot, weekly tightness, or "
            "live/default orders."
        ),
    }
    return payload


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | trades | total pnl | avg pnl | win rate | avg score | avg RS |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, summary in payload["by_bucket"].items():
        lines.append(
            "| {bucket} | {trades} | {pnl} | {avg} | {win} | {score} | {rs} |".format(
                bucket=bucket,
                trades=summary["trade_count"],
                pnl=summary["total_pnl"],
                avg=summary["avg_pnl"],
                win=summary["win_rate"],
                score=summary["avg_score"],
                rs=summary["avg_rs_score"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | bucket | trades | total pnl | avg pnl | win rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, row in payload["by_window_bucket"].items():
        for bucket, summary in row["by_bucket"].items():
            if summary["trade_count"] == 0:
                continue
            lines.append(
                "| {label} | {bucket} | {trades} | {pnl} | {avg} | {win} |".format(
                    label=label,
                    bucket=bucket,
                    trades=summary["trade_count"],
                    pnl=summary["total_pnl"],
                    avg=summary["avg_pnl"],
                    win=summary["win_rate"],
                )
            )
    return lines


def _shadow_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | trades | reassigned | source pnl | shadow pnl | delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["score_bonus_shadow"]["by_window"].items():
        lines.append(
            "| {label} | {trades} | {reassigned} | {source} | {shadow} | {delta} |".format(
                label=label,
                trades=row["trade_count"],
                reassigned=row["reassigned_trade_count"],
                source=row["source_total_pnl"],
                shadow=row["shadow_total_pnl"],
                delta=row["shadow_pnl_delta_vs_source"],
            )
        )
    agg = payload["score_bonus_shadow"]["aggregate"]
    lines.append(
        "| aggregate | {trades} | {reassigned} | {source} | {shadow} | {delta} |".format(
            trades=agg["trade_count"],
            reassigned=agg["reassigned_trade_count"],
            source=agg["source_total_pnl"],
            shadow=agg["shadow_total_pnl"],
            delta=agg["shadow_pnl_delta_vs_source"],
        )
    )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    shadow_agg = payload["score_bonus_shadow"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Kova Fundamental + RS Proxy Shadow Ranking",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Source",
        "",
        "- Source population: `exp-20260526-007` `rank2_125` selected paper trades.",
        "- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.",
        f"- Tested field: `{CHANGED_VARIABLE}`.",
        "",
        "## Coverage",
        "",
        f"- Closed paper trades: `{coverage['trade_count']}`.",
        f"- Score available: `{coverage['score_available_count']}`.",
        f"- EPS+revenue pair available: `{coverage['fundamental_pair_available_count']}`.",
        f"- Fundamental pass: `{coverage['fundamental_pass_count']}`.",
        f"- RS proxy available: `{coverage['rs_available_count']}`.",
        f"- RS leader proxy count: `{coverage['rs_leader_count']}`.",
        f"- Strong Kova bucket count: `{coverage['strong_bucket_count']}`.",
        "",
        "## Aggregate Buckets",
        "",
        *_bucket_table(payload),
        "",
        "## Window Buckets",
        "",
        *_window_table(payload),
        "",
        "## Score-Bonus Shadow",
        "",
        "This read-only audit gives the largest existing scalar to the higher Kova score inside same-day top-2 pairs. It is not promoted.",
        "",
        *_shadow_table(payload),
        "",
        f"- Aggregate shadow PnL delta vs source: `{shadow_agg['shadow_pnl_delta_vs_source']}`.",
        f"- Reassigned trades: `{shadow_agg['reassigned_trade_count']}`.",
        "",
        "## Gate 4",
        "",
        "No strategy promotion was possible in this experiment because this is read-only attribution and shadow ranking only.",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": row.get("lane") or payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    existing = _existing_ticket()
    ticket_payload = {
        **existing,
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": "kova_fundamental_rs_proxy_shadow_ranking",
        "mechanism_family": "kova_canslim_proxy_candidate_ranking",
        "trial_family": payload["trial_family"],
        "trial_variant_id": "kova_fundamental_rs_proxy_score_v1",
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 9),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": (
            "new_production_visible_companyfacts_growth_plus_ginger_rs_proxy_sidecar"
        ),
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_015_kova_fundamental_rs_proxy_shadow_ranking.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "must_not_touch": [
            "quant/backtester.py",
            "quant/run.py",
            "quant/volatility_contraction_paper_sleeve.py",
            "operator_inputs/open_positions.json",
        ],
        "locked_variables": [
            "core entries",
            "VCP compression and breakout",
            "QQQ/SPY gate",
            "top2 selection",
            "rank-notional profile",
            "sizing",
            "exits",
            "LLM/news",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "coverage": payload["coverage"],
                "bucket_counts": payload["bucket_counts"],
                "shadow_aggregate": payload["score_bonus_shadow"]["aggregate"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
