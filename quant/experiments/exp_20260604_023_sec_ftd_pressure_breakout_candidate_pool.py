"""exp-20260604-023: SEC FTD pressure breakout candidate-pool scout.

This replay-only alpha search tests one new free, PIT-lagged data source:
official SEC fails-to-deliver rows. It selects liquid stock breakouts only when
the latest published FTD row shows material settlement-fail pressure.

Core signal generation, ranking, sizing, exits, LLM/news, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

import exp_20260601_010_gap_up_hold_high_close_candidate_pool as framework


EXPERIMENT_ID = "exp-20260604-023"
STEM = "sec_ftd_pressure_breakout_candidate_pool"
TRIAL_FAMILY = "sec_ftd_pressure_breakout_candidate_pool"
CHANGED_VARIABLE = "sec_ftd_pressure_breakout_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20 = 50_000_000.0
MIN_VOLUME_RATIO_20 = 1.00
MIN_CLOSE_LOCATION = 0.55
MIN_RET20_EXCESS_SPY = 0.0
MIN_FTD_SHARES = 100_000
MIN_FTD_NOTIONAL = 1_000_000.0
MIN_FTD_NOTIONAL_TO_ADV20 = 0.006
MAX_FTD_PUBLICATION_AGE_DAYS = 45

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

ROOT = framework.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FTD_ROWS_JSON = OUT_DIR / "sec_ftd_rows_summary.json"
FTD_FILES_JSON = OUT_DIR / "sec_ftd_source_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

SEC_FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{year}{month:02d}{half}.zip"
SEC_FTD_PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"

_FTD_CACHE: dict[str, Any] | None = None
_ORIGINAL_BUILD_PAYLOAD = framework._build_payload


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    framework.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    framework.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    framework.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_JSON = BEFORE_JSON
    framework.AFTER_JSON = AFTER_JSON
    framework.LOG_JSON = LOG_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.CARD_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._artifact = _artifact
    framework._build_payload = _build_payload


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


def _fetch_ftd_context(universe: set[str]) -> dict[str, Any]:
    global _FTD_CACHE
    tickers = sorted(universe.difference(framework.base.shadow.EXCLUDED_TICKERS))
    if _FTD_CACHE is not None and _FTD_CACHE.get("tickers") == tickers:
        return _FTD_CACHE

    starts = [
        datetime.strptime(cfg["start"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    ends = [
        datetime.strptime(cfg["end"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    first = min(starts) - timedelta(days=75)
    last = max(ends)

    cache_dir = ROOT / "data" / "tmp" / EXPERIMENT_ID / "sec_ftd_source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-sec-ftd-alpha-exp-20260604-023/1.0 "
                "research-only local workspace"
            )
        }
    )

    ticker_set = set(tickers)
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for year, month, half in _month_iter(first, last):
        url = SEC_FTD_URL.format(year=year, month=month, half=half)
        cache_path = cache_dir / f"cnsfails{year}{month:02d}{half}.zip"
        source = "cache"
        status_code: int | str | None = None
        try:
            if cache_path.exists():
                content = cache_path.read_bytes()
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
        except Exception as exc:  # pragma: no cover - network can vary.
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
                    "source_file": framework._repo_rel(cache_path),
                }
            )
        files.append(
            {
                "url": url,
                "status_code": status_code,
                "source": source,
                "cache_path": framework._repo_rel(cache_path),
                "parsed_rows": parsed,
                "matched_rows": matched,
            }
        )

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ticker.setdefault(row["ticker"], []).append(row)
    for ticker_rows in by_ticker.values():
        ticker_rows.sort(key=lambda row: (row["publication_date"], row["settlement_date"]))

    _FTD_CACHE = {
        "tickers": tickers,
        "rows": rows,
        "files": files,
        "rows_by_ticker": by_ticker,
        "source_page": SEC_FTD_PAGE,
        "publication_lag_note": (
            "SEC says first-half files are available at month end and second-half "
            "files around the 15th of the next month; this replay adds one "
            "calendar day before a row can be used."
        ),
    }
    return _FTD_CACHE


def _latest_ftd_row(rows_by_ticker: dict[str, list[dict[str, Any]]], ticker: str, signal_date: str) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if str(row["publication_date"]) <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


def _prepared_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = framework._prepared_frame(frame)
    out["prior_20_high"] = out["High"].shift(1).rolling(20).max()
    out["breakout_20"] = out["Close"] > out["prior_20_high"]
    return out


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = _prepared_frame(frames["SPY"]) if "SPY" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required for ret20 excess control")

    ftd_context = _fetch_ftd_context({ticker.upper() for ticker in frames})
    rows_by_ticker = ftd_context["rows_by_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    spy_closes = [float(value) for value in spy["Close"].tolist()]

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in framework.base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        fr = _prepared_frame(frame)
        closes = [float(value) for value in fr["Close"].tolist()]
        pos_by_date = {idx: pos for pos, idx in enumerate(fr.index)}
        for asof in fr.loc[start:end].index:
            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            signal_date = str(asof.date())
            ftd = _latest_ftd_row(rows_by_ticker, ticker, signal_date)
            if ftd is None:
                continue
            publication_age = (
                datetime.strptime(signal_date, "%Y-%m-%d").date()
                - datetime.strptime(str(ftd["publication_date"]), "%Y-%m-%d").date()
            ).days
            if publication_age < 0 or publication_age > MAX_FTD_PUBLICATION_AGE_DAYS:
                continue
            raw_pass_counts["publication_lag_passed"] += 1

            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            ret20 = framework._ret(closes, pos, 20)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret20_excess_spy": (ret20 - spy_ret20) if ret20 is not None and spy_ret20 is not None else None,
                "ftd_shares": float(ftd["ftd_shares"]),
                "ftd_notional": float(ftd["ftd_notional"]),
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if bool(row.get("breakout_20")) is not True:
                continue
            raw_pass_counts["breakout_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                continue
            raw_pass_counts["price_action_passed"] += 1
            if values["ftd_shares"] < MIN_FTD_SHARES:
                continue
            if values["ftd_notional"] < MIN_FTD_NOTIONAL:
                continue
            ftd_to_adv20 = values["ftd_notional"] / values["avg_dollar_volume_20"]
            if ftd_to_adv20 < MIN_FTD_NOTIONAL_TO_ADV20:
                continue
            raw_pass_counts["ftd_pressure_passed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                math.log1p(values["ftd_notional"]) * 0.45
                + min(ftd_to_adv20, 0.08) * 100.0
                + values["ret20_excess_spy"] * 2.0
                + min(values["volume_ratio_20"], 4.0) * 0.25
                + values["close_location"]
            )
            candidates_by_date.setdefault(signal_date, []).append(
                {
                    "ticker": ticker,
                    "date": signal_date,
                    "signal_date": signal_date,
                    "window": label,
                    "score": framework._round(score, 6),
                    "ftd_publication_date": ftd["publication_date"],
                    "ftd_settlement_date": ftd["settlement_date"],
                    "ftd_publication_age_days": publication_age,
                    "ftd_shares": int(values["ftd_shares"]),
                    "ftd_notional": framework._round(values["ftd_notional"], 2),
                    "ftd_notional_to_adv20": framework._round(ftd_to_adv20, 6),
                    "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                    "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                    "close_location": framework._round(values["close_location"], 6),
                    "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                    "same_day_core_entry_count": len(same_day_core),
                    "same_ticker_core_overlap": False,
                    "source_page": SEC_FTD_PAGE,
                    "rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    selected: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for signal_date, rows in sorted(candidates_by_date.items()):
        raw_candidate_count += len(rows)
        rows.sort(
            key=lambda item: (
                -float(item["score"]),
                -float(item["ftd_notional_to_adv20"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    ftd_context = _FTD_CACHE or {}
    framework._write_json(FTD_ROWS_JSON, _ftd_rows_summary(ftd_context.get("rows", [])))
    framework._write_json(FTD_FILES_JSON, ftd_context.get("files", []))

    passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_requires_sec_ftd_shared_adapter"
        if passed
        else "rejected_sec_ftd_pressure_breakout_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but SEC FTD remains replay-only until a shared default-off "
        "adapter uses the same publication-lag policy in production."
        if passed
        else "Gate 4 failed; no production or shared policy behavior is retained."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Publication-lagged SEC fails-to-deliver pressure combined with "
                "liquid breakout and relative strength confirmation may identify "
                "an independent default-off stock candidate pool."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "free_sec_ftd_candidate_pool",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260529-017",
                "exp-20260603-006",
                "exp-20260603-007",
            ],
            "new_evidence_type": "official_sec_fails_to_deliver_publication_lagged_free_data",
            "interpretation": rationale,
            "sec_ftd_source": {
                "source_page": SEC_FTD_PAGE,
                "row_count": len(ftd_context.get("rows", [])),
                "file_count": len(ftd_context.get("files", [])),
                "rows_artifact": framework._repo_rel(FTD_ROWS_JSON),
                "files_artifact": framework._repo_rel(FTD_FILES_JSON),
                "publication_lag_note": ftd_context.get("publication_lag_note"),
            },
            "parameters": {
                "source": "SEC fails-to-deliver half-month ZIP files",
                "source_page": SEC_FTD_PAGE,
                "publication_lag_policy": (
                    "first half usable on next calendar day after month end; "
                    "second half usable on next calendar day after the 15th of "
                    "the next month"
                ),
                "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
                "base_notional_usd": BASE_NOTIONAL_USD,
                "hold_days": HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "min_price": MIN_PRICE,
                "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
                "min_volume_ratio_20": MIN_VOLUME_RATIO_20,
                "min_close_location": MIN_CLOSE_LOCATION,
                "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
                "min_ftd_shares": MIN_FTD_SHARES,
                "min_ftd_notional": MIN_FTD_NOTIONAL,
                "min_ftd_notional_to_adv20": MIN_FTD_NOTIONAL_TO_ADV20,
                "max_ftd_publication_age_days": MAX_FTD_PUBLICATION_AGE_DAYS,
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "min_target_trades": MIN_TARGET_TRADES,
                    "min_target_windows": MIN_TARGET_WINDOWS,
                    "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "max_positive_hhi": MAX_POSITIVE_HHI,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry / candidate_pool: SEC FTD pressure is a free, "
                    "publication-lagged settlement-stress field that may add "
                    "information beyond accepted FINRA short-interest rows."
                ),
                "2_history_check": (
                    "No prior local experiment used SEC FTD rows. FINRA "
                    "short-pressure is accepted, but playbook explicitly asks "
                    "future retries to use a new PIT borrow-cost/FTD field."
                ),
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "docs/backtesting.md three windows; positive aggregate "
                    "EV/PnL, no unacceptable drawdown/survival regression, "
                    ">=20 target trades across >=2 windows, concentration pass."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260604_023_sec_ftd_pressure_breakout_candidate_pool.py"
                ),
            },
        }
    )
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "requires_shared_adapter_before_promotion": passed,
        }
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(FTD_ROWS_JSON),
        framework._repo_rel(FTD_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
    ]
    return payload


def _ftd_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_year_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    for row in rows:
        publication = str(row.get("publication_date") or "")
        if len(publication) >= 7:
            by_year_month[publication[:7]] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "publication_month_counts": dict(sorted(by_year_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "note": (
            "Raw SEC FTD ZIP files are fetched by the runner and cached under "
            "data/tmp; full raw rows are not committed as experiment artifacts."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC FTD Pressure Breakout Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- SEC FTD rows loaded: `{payload.get('sec_ftd_source', {}).get('row_count')}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "The rule uses only SEC FTD rows after the conservative publication-lag "
            "date plus same-day/prior OHLCV context. It is replay-only and "
            "default-off, so no production entry, ranking, sizing, exit, "
            "LLM/news, watchlist, or order behavior changed.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_framework()
    payload = framework.run(output)
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
                "aggregate": payload["aggregate"],
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
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
