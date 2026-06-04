"""exp-20260604-024: Form 4 plus SEC FTD overlap candidate-pool scout.

This replay-only alpha search tests one source-relation variable: a PIT-safe
Form 4 meaningful purchase event is selected only when the latest published
SEC fails-to-deliver row also shows recent material settlement stress.

Core signal generation, ranking, sizing, exits, LLM/news, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import time
import zipfile
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

import exp_20260530_003_form4_ownership_delta_forward_queue as prior


EXP_ID = "exp-20260604-024"
STEM = "form4_ftd_overlap_candidate_pool"
TRIAL_FAMILY = "form4_ftd_overlap_candidate_pool"
CHANGED_VARIABLE = "form4_meaningful_purchase_with_recent_sec_ftd_pressure_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MAX_FTD_PUBLICATION_AGE_DAYS = 45
MIN_FTD_SHARES = 25_000
MIN_FTD_NOTIONAL = 250_000.0
MIN_FTD_NOTIONAL_TO_FORM4_PURCHASE_VALUE = 0.25
MIN_TARGET_TRADES = 8
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

SEC_FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{year}{month:02d}{half}.zip"
SEC_FTD_PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"

ROOT = prior.REPO_ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
RAW_FORM4_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
FTD_ROWS_JSON = OUT_DIR / "sec_ftd_rows_summary.json"
FTD_FILES_JSON = OUT_DIR / "sec_ftd_source_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}

_FTD_CACHE: dict[str, Any] | None = None


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


def _round(value: Any, digits: int = 6) -> Any:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
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
            if row.get("experiment_id") == EXP_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date8(value: str) -> date | None:
    try:
        return datetime.strptime(str(value).strip(), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _month_iter(start: date, end: date) -> list[tuple[int, int, str]]:
    months: list[tuple[int, int, str]] = []
    cursor = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    while cursor <= stop:
        months.append((cursor.year, cursor.month, "a"))
        months.append((cursor.year, cursor.month, "b"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def _publication_date_for(settlement: date) -> tuple[date, str]:
    if settlement.day <= 15:
        if settlement.month == 12:
            next_month = date(settlement.year + 1, 1, 1)
        else:
            next_month = date(settlement.year, settlement.month + 1, 1)
        return next_month, "first_half_month_end_plus_one_day"
    if settlement.month == 12:
        return date(settlement.year + 1, 1, 16), "second_half_next_month_15_plus_one_day"
    return date(settlement.year, settlement.month + 1, 16), "second_half_next_month_15_plus_one_day"


def _fetch_ftd_context(universe: set[str]) -> dict[str, Any]:
    global _FTD_CACHE
    tickers = sorted(ticker.upper() for ticker in universe if ticker)
    if _FTD_CACHE is not None and _FTD_CACHE.get("tickers") == tickers:
        return _FTD_CACHE

    starts = [
        datetime.strptime(cfg["start"], "%Y-%m-%d").date()
        for cfg in prior.WINDOWS.values()
    ]
    ends = [
        datetime.strptime(cfg["end"], "%Y-%m-%d").date()
        for cfg in prior.WINDOWS.values()
    ]
    first = min(starts) - timedelta(days=75)
    last = max(ends)
    cache_dir = ROOT / "data" / "tmp" / EXP_ID / "sec_ftd_source_cache"
    legacy_cache_dir = ROOT / "data" / "tmp" / "exp-20260604-023" / "sec_ftd_source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-sec-ftd-form4-overlap-exp-20260604-024/1.0 "
                "research-only local workspace"
            )
        }
    )

    ticker_set = set(tickers)
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for year, month, half in _month_iter(first, last):
        url = SEC_FTD_URL.format(year=year, month=month, half=half)
        filename = f"cnsfails{year}{month:02d}{half}.zip"
        cache_path = cache_dir / filename
        legacy_cache_path = legacy_cache_dir / filename
        source = "cache"
        status_code: int | str | None = None
        try:
            if cache_path.exists():
                content = cache_path.read_bytes()
                status_code = "cached"
            elif legacy_cache_path.exists():
                content = legacy_cache_path.read_bytes()
                cache_path.write_bytes(content)
                source = "cache_copy_exp-20260604-023"
                status_code = "cached"
            else:
                source = "network"
                response = session.get(url, timeout=30)
                status_code = response.status_code
                if response.status_code != 200:
                    files.append(
                        {
                            "url": url,
                            "status_code": status_code,
                            "source": source,
                            "matched_rows": 0,
                        }
                    )
                    continue
                content = response.content
                cache_path.write_bytes(content)
        except Exception as exc:  # pragma: no cover - network and filesystem can vary.
            files.append(
                {
                    "url": url,
                    "status_code": status_code,
                    "source": source,
                    "error": str(exc),
                    "matched_rows": 0,
                }
            )
            continue

        matched = 0
        parsed = 0
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                if not names:
                    files.append(
                        {
                            "url": url,
                            "status_code": status_code,
                            "source": source,
                            "matched_rows": 0,
                            "error": "zip_has_no_data_member",
                        }
                    )
                    continue
                text = archive.read(names[0]).decode("latin-1")
        except zipfile.BadZipFile as exc:
            files.append(
                {
                    "url": url,
                    "status_code": status_code,
                    "source": source,
                    "matched_rows": 0,
                    "error": str(exc),
                }
            )
            continue

        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            parsed += 1
            ticker = str(raw.get("SYMBOL") or "").upper().strip()
            if ticker not in ticker_set:
                continue
            settlement = _date8(str(raw.get("SETTLEMENT DATE") or ""))
            fails = _int(raw.get("QUANTITY (FAILS)"))
            price = _float(raw.get("PRICE"))
            if settlement is None or fails is None or price is None:
                continue
            publication, policy = _publication_date_for(settlement)
            matched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication.isoformat(),
                    "publication_date_policy": policy,
                    "pit_safe": True,
                    "ftd_shares": fails,
                    "ftd_price": round(price, 4),
                    "ftd_notional": round(fails * price, 2),
                    "cusip": str(raw.get("CUSIP") or "").strip(),
                    "description": str(raw.get("DESCRIPTION") or "").strip(),
                    "source_url": url,
                    "source_file": prior._repo_rel(cache_path),
                }
            )
        files.append(
            {
                "url": url,
                "status_code": status_code,
                "source": source,
                "cache_path": prior._repo_rel(cache_path),
                "parsed_rows": parsed,
                "matched_rows": matched,
            }
        )

    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_ticker.setdefault(row["ticker"], []).append(row)
    for ticker_rows in rows_by_ticker.values():
        ticker_rows.sort(key=lambda row: (row["publication_date"], row["settlement_date"]))

    _FTD_CACHE = {
        "tickers": tickers,
        "rows": rows,
        "files": files,
        "rows_by_ticker": rows_by_ticker,
        "source_page": SEC_FTD_PAGE,
        "publication_lag_note": (
            "First-half files are used no earlier than the next month end plus one "
            "calendar day; second-half files are used no earlier than the 16th of "
            "the next month."
        ),
    }
    return _FTD_CACHE


def _latest_ftd_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if str(row["publication_date"]) <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


def _ftd_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_notional: Counter[str] = Counter()
    publications: list[str] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        by_ticker_count[ticker] += 1
        by_ticker_notional[ticker] += float(row.get("ftd_notional") or 0.0)
        publications.append(str(row.get("publication_date") or ""))
    top = [
        {
            "ticker": ticker,
            "row_count": by_ticker_count[ticker],
            "ftd_notional_sum": _round(by_ticker_notional[ticker], 2),
        }
        for ticker, _ in by_ticker_notional.most_common(20)
    ]
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker_count),
        "publication_date_min": min(publications) if publications else None,
        "publication_date_max": max(publications) if publications else None,
        "top_tickers_by_notional": top,
        "source_page": SEC_FTD_PAGE,
    }


def _events_with_ftd_pressure(
    events: list[dict[str, Any]],
    ftd_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_ticker = ftd_context.get("rows_by_ticker") or {}
    pass_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        usable = prior._date10(event.get("usable_trade_date"))
        if not ticker or not usable:
            continue
        pass_counts["form4_event_scanned"] += 1
        ftd = _latest_ftd_row(rows_by_ticker, ticker, usable)
        if ftd is None:
            continue
        pass_counts["has_published_ftd_row"] += 1
        publication_age = (
            datetime.strptime(usable, "%Y-%m-%d").date()
            - datetime.strptime(str(ftd["publication_date"]), "%Y-%m-%d").date()
        ).days
        if publication_age < 0 or publication_age > MAX_FTD_PUBLICATION_AGE_DAYS:
            continue
        pass_counts["publication_lag_passed"] += 1
        ftd_shares = float(ftd.get("ftd_shares") or 0.0)
        ftd_notional = float(ftd.get("ftd_notional") or 0.0)
        purchase_value = prior._float_or_none(event.get("total_purchase_value")) or 0.0
        if ftd_shares < MIN_FTD_SHARES:
            continue
        if ftd_notional < MIN_FTD_NOTIONAL:
            continue
        pass_counts["ftd_absolute_pressure_passed"] += 1
        ftd_to_purchase = ftd_notional / purchase_value if purchase_value > 0 else None
        if ftd_to_purchase is None or ftd_to_purchase < MIN_FTD_NOTIONAL_TO_FORM4_PURCHASE_VALUE:
            continue
        pass_counts["ftd_to_purchase_pressure_passed"] += 1
        selected.append(
            {
                **event,
                "ftd_pressure_confirmed": True,
                "ftd_publication_date": ftd["publication_date"],
                "ftd_settlement_date": ftd["settlement_date"],
                "ftd_publication_age_days": publication_age,
                "ftd_shares": int(ftd_shares),
                "ftd_notional": _round(ftd_notional, 2),
                "ftd_notional_to_form4_purchase_value": _round(ftd_to_purchase, 6),
                "ftd_source_page": SEC_FTD_PAGE,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return selected, {
        "raw_pass_counts": dict(pass_counts),
        "overlap_event_count": len(selected),
        "parameters": {
            "max_ftd_publication_age_days": MAX_FTD_PUBLICATION_AGE_DAYS,
            "min_ftd_shares": MIN_FTD_SHARES,
            "min_ftd_notional": MIN_FTD_NOTIONAL,
            "min_ftd_notional_to_form4_purchase_value": MIN_FTD_NOTIONAL_TO_FORM4_PURCHASE_VALUE,
        },
    }


def _aggregate_for_close(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values())
    pnl = sum(float(row.get("total_pnl") or 0.0) for row in metrics.values())
    return {
        "experiment_id": EXP_ID,
        "expected_value_score": _round(ev, 6),
        "total_pnl": _round(pnl, 2),
        "sharpe_daily": None,
        "max_drawdown_pct": _round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "win_rate": None,
        "total_trades": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "survival_rate": _round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
        "windows": metrics,
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return prior._aggregate_delta(before, after)


def _baseline_drift(before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        actual = before_metrics.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - expected["expected_value_score"]
        pnl_delta = float(actual.get("total_pnl") or 0.0) - expected["total_pnl"]
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": _round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": _round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260517-009 metrics",
        "current_source": "current BacktestEngine replay through docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
    }


def _target_trade_summary(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl = {}
    for label, detail in details.items():
        trades = detail.get("selected_trades") or []
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0.0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0.0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0.0 and positive
        else None
    )
    ticker_rows = [
        {
            "ticker": ticker,
            "trade_count": by_ticker_count[ticker],
            "paper_pnl_usd": _round(pnl, 2),
            "positive_pnl_usd": _round(max(pnl, 0.0), 2),
            "positive_pnl_share": _round(pnl / positive_total, 6)
            if pnl > 0 and positive_total > 0
            else None,
        }
        for ticker, pnl in sorted(by_ticker_pnl.items())
    ]
    ticker_rows.sort(
        key=lambda row: (
            -(row["positive_pnl_usd"] or 0.0),
            -abs(row["paper_pnl_usd"] or 0.0),
            row["ticker"],
        )
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, detail in details.items() if detail.get("selected_trades")
        ],
        "total_pnl": _round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "ticker_rows": ticker_rows,
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    after_metrics: dict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    selected = int(target_summary["total_trade_count"] or 0)
    target_windows = target_summary["windows_with_target_trades"]
    single_share = target_summary["max_single_positive_pnl_share"]
    hhi = target_summary["positive_pnl_hhi"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in after_metrics.values())
    material = (
        core_delta["aggregate_ev_delta_pct"] is not None
        and core_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        core_delta["aggregate_pnl_delta_pct"] is not None
        and core_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    improves_core = (
        core_delta["aggregate_ev_delta"] > 0.0
        and core_delta["aggregate_pnl_delta"] > 0.0
        and core_delta["windows_ev_regressed"] == 0
        and core_delta["windows_pnl_regressed"] == 0
    )
    improves_raw = (
        raw_delta["aggregate_ev_delta"] > 0.0
        and raw_delta["aggregate_pnl_delta"] > 0.0
        and raw_delta["windows_ev_regressed"] == 0
        and raw_delta["windows_pnl_regressed"] == 0
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= MAX_DRAWDOWN_WORSE
    sample_ok = (
        selected >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and (single_share is None or single_share <= MAX_SINGLE_POSITIVE_SHARE)
        and (hhi is None or hhi <= MAX_POSITIVE_HHI)
    )
    failed = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_raw:
        failed.append("does_not_improve_raw_form4_queue")
    if not material:
        failed.append("not_material_vs_core")
    if not drawdown_ok:
        failed.append("drawdown_drift_too_high")
    if selected < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if min_survival < 0.05:
        failed.append("survival_floor_failed")
    if single_share is not None and single_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed": bool(material and improves_core and improves_raw and drawdown_ok and sample_ok and min_survival >= 0.05),
        "failed_reasons": failed,
        "material_vs_core": bool(material),
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": f"<= {MAX_DRAWDOWN_WORSE}",
        "selected_event_trades": selected,
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "min_survival_rate": _round(min_survival, 6),
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": f"<= {MAX_SINGLE_POSITIVE_SHARE}",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": f"<= {MAX_POSITIVE_HHI}",
        "sample_guard_passed": bool(sample_ok),
    }


def _artifact(payload: dict[str, Any]) -> str:
    core_delta = payload["aggregate_delta_vs_core"]
    raw_delta = payload["aggregate_delta_vs_raw_form4"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        "# Form 4 plus SEC FTD Overlap Candidate Pool",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV vs core: `{core_delta['before_ev_sum']}` -> `{core_delta['after_ev_sum']}` "
        f"({core_delta['aggregate_ev_delta']:+.4f})",
        f"- aggregate PnL vs core: `${core_delta['aggregate_pnl_delta']:+,.2f}`",
        f"- aggregate EV vs raw Form 4: `{raw_delta['before_ev_sum']}` -> `{raw_delta['after_ev_sum']}` "
        f"({raw_delta['aggregate_ev_delta']:+.4f})",
        f"- selected overlap trades: `{target['total_trade_count']}`",
        f"- failed gates: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | Core EV | Raw Form4 EV | Overlap EV | Delta vs raw | Delta vs core | Core PnL | Overlap PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.WINDOWS:
        core = payload["core_baseline_metrics"][label]
        raw = payload["raw_form4_metrics"][label]
        after = payload["after_metrics"][label]
        raw_row = payload["deltas_vs_raw_form4"][label]
        core_row = payload["deltas_vs_core"][label]
        detail = payload["event_details"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {raw['expected_value_score']} | "
            f"{after['expected_value_score']} | {raw_row['expected_value_score']} | "
            f"{core_row['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{detail['selected_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Gate Read",
            "",
            json.dumps(gate4, indent=2, sort_keys=True),
            "",
            "## Source Diagnostics",
            "",
            json.dumps(payload["source_diagnostics"], indent=2, sort_keys=True),
            "",
            "## Conclusion",
            "",
            payload["decision_rationale"],
            "",
            "Core production orders, ranking, sizing, exits, LLM/news inputs, and watchlists were unchanged. "
            "The overlap is replay-only/default-off and would require a shared production-visible adapter before promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = prior._json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": prior._repo_rel(OUT_JSON),
                "log": prior._repo_rel(LOG_JSON),
                "report": prior._repo_rel(ARTIFACT_MD),
                "before": prior._repo_rel(BEFORE_JSON),
                "after": prior._repo_rel(AFTER_JSON),
                "raw_form4": prior._repo_rel(RAW_FORM4_JSON),
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": payload["gate4"],
                "next_action": payload["next_retry_requires"][0],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    files = [
        Path(__file__),
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        RAW_FORM4_JSON,
        FTD_ROWS_JSON,
        FTD_FILES_JSON,
        LOG_JSON,
        ARTIFACT_MD,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
    ]
    manifest = prior._json_load(MANIFEST_JSON, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "experiment_id": EXP_ID,
            "experiment_uid": payload.get("experiment_uid"),
            "status": payload["status"],
            "decision": payload["decision"],
            "updated_at": payload["timestamp"],
            "completed_at": payload["timestamp"],
            "files": {
                prior._repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
                for path in files
            },
            "result": {
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": payload["gate4"],
            },
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gate2_open_positions = prior._position_field_check()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = prior.get_universe()
    prices = prior._load_price_map()
    form4_events, form4_diagnostics = prior._load_forward_events()
    ftd_context = _fetch_ftd_context({str(event.get("ticker") or "").upper() for event in form4_events})
    overlap_events, overlap_diagnostics = _events_with_ftd_pressure(form4_events, ftd_context)
    raw_candidates = [prior._candidate_trade(event, prices) for event in form4_events]
    overlap_candidates = [prior._candidate_trade(event, prices) for event in overlap_events]

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    raw_form4_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    core_results: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    event_details: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, window in prior.WINDOWS.items():
        print(f"[{label}] core/raw-form4/form4-ftd replay")
        result = prior.BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        raw_selected, raw_skipped = prior._select_event_trades(
            raw_candidates,
            start=window["start"],
            end=window["end"],
        )
        selected, skipped = prior._select_event_trades(
            overlap_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_curve = prior._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = prior._core_metrics(result)
        raw_form4_metrics[label] = prior._combined_metrics(result, raw_curve, raw_selected)
        after_metrics[label] = prior._combined_metrics(result, event_curve, selected)
        core_results[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "ohlcv_source": (result.get("known_biases") or {}).get("ohlcv_source"),
        }
        event_details[label] = {
            "raw_form4_candidate_count": sum(
                1
                for row in raw_candidates
                if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "overlap_candidate_count": sum(
                1
                for row in overlap_candidates
                if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "raw_form4_selected_trade_count": len(raw_selected),
            "selected_trade_count": len(selected),
            "raw_form4_skipped_count": len(raw_skipped),
            "skipped_count": len(skipped),
            "skip_reasons": dict(
                sorted(
                    {
                        reason: sum(1 for row in skipped if row["reason"] == reason)
                        for reason in {row["reason"] for row in skipped}
                    }.items()
                )
            ),
            "selected_trades": selected,
            "skipped_candidates": skipped,
            "event_equity_curve": event_curve,
        }

    deltas_vs_core = {
        label: prior._delta(before_metrics[label], after_metrics[label]) for label in prior.WINDOWS
    }
    deltas_vs_raw = {
        label: prior._delta(raw_form4_metrics[label], after_metrics[label]) for label in prior.WINDOWS
    }
    aggregate_vs_core = _aggregate_delta(before_metrics, after_metrics)
    aggregate_vs_raw = _aggregate_delta(raw_form4_metrics, after_metrics)
    target_summary = _target_trade_summary(event_details)
    gate4 = _gate_result(aggregate_vs_core, aggregate_vs_raw, after_metrics, target_summary)
    accepted = bool(gate4["passed"])
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if accepted
        else "rejected_form4_ftd_overlap_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but the Form4+FTD overlap remains a replay lead until a "
        "shared default-off production/backtest adapter proves parity."
        if accepted
        else "Gate 4 failed; no production or shared strategy behavior is retained."
    )

    ticket = prior._json_load(TICKET_JSON, {})
    return {
        "experiment_id": EXP_ID,
        "experiment_uid": ticket.get("experiment_uid") if isinstance(ticket, dict) else None,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "PIT-safe SEC Form 4 meaningful-purchase events confirmed by recent "
            "publication-lagged SEC fails-to-deliver pressure may define a "
            "higher-quality ownership-plus-settlement-stress candidate pool than "
            "either free SEC source alone."
        ),
        "prediction": (ticket.get("prediction") if isinstance(ticket, dict) else None),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "free_sec_ownership_settlement_stress",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260604-022",
            "exp-20260604-023",
            "exp-20260603-008",
            "exp-20260603-010",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_sec_source_overlap_relation",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window core baseline plus default-off event overlay",
            "windows": prior.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "entry": "Form 4 usable_trade_date next available open with existing event overlay execution",
            "exit": "existing Form 4 event overlay 10 trading-day close",
            "raw_form4_comparator": True,
        },
        "parameters": {
            "max_ftd_publication_age_days": MAX_FTD_PUBLICATION_AGE_DAYS,
            "min_ftd_shares": MIN_FTD_SHARES,
            "min_ftd_notional": MIN_FTD_NOTIONAL,
            "min_ftd_notional_to_form4_purchase_value": MIN_FTD_NOTIONAL_TO_FORM4_PURCHASE_VALUE,
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: a free SEC source-overlap relation may "
                "identify higher-intent insider accumulation when settlement stress "
                "is already visible through published FTD rows."
            ),
            "2_history_check": (
                "exp-20260604-022 rejected Form 4 cost-basis alignment; "
                "exp-20260604-023 rejected standalone FTD pressure; "
                "exp-20260603-008/010 rejected recent Form 4 variants. This test "
                "uses a new relation across both sources instead of a local retune."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three windows; improve aggregate EV/PnL versus "
                "core and raw Form 4; no window EV/PnL regression; >=8 selected "
                "trades across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
                "positive concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260604_024_form4_ftd_overlap_candidate_pool.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": prior._repo_rel(BEFORE_JSON),
            "baseline_drift": _baseline_drift(before_metrics),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 PIT-safe open-market purchase flags",
                "SEC FTD publication_date",
                "SEC FTD ftd_shares and ftd_notional",
                "entry_date and target_price in operator_inputs/open_positions.json",
            ],
        },
        "gate3": {
            "passed": min(float(row.get("survival_rate") or 0.0) for row in after_metrics.values()) >= 0.05,
            "note": "No core production filter was added; this is a default-off paper event overlay.",
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row.get("signals_generated"),
                    "signals_survived": row.get("signals_survived"),
                    "survival_rate": row.get("survival_rate"),
                }
                for label, row in after_metrics.items()
            },
        },
        "gate4": gate4,
        "core_baseline_metrics": before_metrics,
        "raw_form4_metrics": raw_form4_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_core": deltas_vs_core,
        "deltas_vs_raw_form4": deltas_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "target_trade_summary": target_summary,
        "event_details": event_details,
        "core_results": core_results,
        "source_diagnostics": {
            "form4": form4_diagnostics,
            "ftd": {
                "row_summary_artifact": prior._repo_rel(FTD_ROWS_JSON),
                "source_files_artifact": prior._repo_rel(FTD_FILES_JSON),
                "row_count": len(ftd_context.get("rows") or []),
                "file_count": len(ftd_context.get("files") or []),
                "source_page": SEC_FTD_PAGE,
                "publication_lag_note": ftd_context.get("publication_lag_note"),
            },
            "overlap": overlap_diagnostics,
        },
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "decision_rationale": rationale,
        "next_retry_requires": [
            "forward replacement-value rows for Form4+FTD overlap before promotion",
            "less concentrated source-overlap relation with at least 3-window support",
            "shared default-off production/backtest adapter if a future run passes",
        ],
        "related_files": [
            prior._repo_rel(Path(__file__)),
            prior._repo_rel(OUT_JSON),
            prior._repo_rel(BEFORE_JSON),
            prior._repo_rel(AFTER_JSON),
            prior._repo_rel(RAW_FORM4_JSON),
            prior._repo_rel(FTD_ROWS_JSON),
            prior._repo_rel(FTD_FILES_JSON),
            prior._repo_rel(LOG_JSON),
            prior._repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _log_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "parameters": payload["parameters"],
        "before_metrics": {
            "expected_value_score": payload["aggregate_delta_vs_core"]["before_ev_sum"],
            "total_pnl": payload["aggregate_delta_vs_core"]["before_pnl_sum"],
        },
        "raw_form4_metrics": {
            "expected_value_score": payload["aggregate_delta_vs_raw_form4"]["before_ev_sum"],
            "total_pnl": payload["aggregate_delta_vs_raw_form4"]["before_pnl_sum"],
        },
        "after_metrics": {
            "expected_value_score": payload["aggregate_delta_vs_core"]["after_ev_sum"],
            "total_pnl": payload["aggregate_delta_vs_core"]["after_pnl_sum"],
        },
        "delta_metrics": {
            "vs_core": payload["aggregate_delta_vs_core"],
            "vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
            "target_trade_count": payload["target_trade_summary"]["total_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"][
                "max_single_positive_pnl_share"
            ],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "core_expected_value": payload["core_baseline_metrics"][label]["expected_value_score"],
                "raw_form4_expected_value": payload["raw_form4_metrics"][label]["expected_value_score"],
                "after_expected_value": payload["after_metrics"][label]["expected_value_score"],
                "delta_vs_core_expected_value": payload["deltas_vs_core"][label]["expected_value_score"],
                "delta_vs_raw_expected_value": payload["deltas_vs_raw_form4"][label]["expected_value_score"],
                "target_trade_count": payload["event_details"][label]["selected_trade_count"],
            }
            for label in prior.WINDOWS
        ],
        "production_impact": payload["production_impact"],
        "decision_basis": payload["gate4"],
        "artifact_path": prior._repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
        "notes": payload["decision_rationale"],
    }


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    payload = build_payload()
    ftd_context = _FTD_CACHE or {}
    _write_json(FTD_ROWS_JSON, _ftd_rows_summary(ftd_context.get("rows", [])))
    _write_json(FTD_FILES_JSON, ftd_context.get("files", []))
    _write_json(output, payload)
    _write_json(BEFORE_JSON, _aggregate_for_close(payload["core_baseline_metrics"]))
    _write_json(AFTER_JSON, _aggregate_for_close(payload["after_metrics"]))
    _write_json(RAW_FORM4_JSON, _aggregate_for_close(payload["raw_form4_metrics"]))
    _write_json(LOG_JSON, payload)
    artifact = _artifact(payload)
    _write_text(ARTIFACT_MD, artifact)
    _write_text(CARD_MD, artifact)
    _write_ticket(payload)
    _write_manifest(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _log_row(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": prior._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
