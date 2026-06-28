"""Run a free regulatory short-pressure proxy shadow experiment.

The experiment is default-off and measurement-only. It tags existing Ginger
candidate events with:

* FINRA biweekly short interest / days-to-cover.
* SEC fails-to-deliver balances using conservative availability dates.
* Nasdaq Reg SHO threshold flags where historical text files are available.

It does not create standalone entries or touch production signal/risk paths.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_short_interest_shadow_experiment as base


REPO_ROOT = Path(__file__).resolve().parents[1]
SEC_FTD_PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
SEC_FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{yyyymm}{half}.zip"
NASDAQ_REGSHO_PAGE = "https://nasdaqtrader.com/trader.aspx?id=RegSHOThreshold"
NASDAQ_REGSHO_URL = "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{yyyymmdd}.txt"
HORIZONS = base.HORIZONS
SCARCE_SLOT_DECISIONS = base.SCARCE_SLOT_DECISIONS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument(
        "--backtest-result",
        default=str(
            REPO_ROOT
            / "data"
            / "experiments"
            / "exp-20260505-024"
            / "backtest_results_snapshot.json"
        ),
    )
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "data" / "experiments"))
    parser.add_argument("--status", default="observed_only")
    return parser.parse_args()


def sec_half_publication_date(year: int, month: int, half: str) -> date:
    if half == "a":
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)
    if month == 12:
        day = date(year + 1, 1, 15)
    else:
        day = date(year, month + 1, 15)
    while not base.is_business_day(day):
        day += timedelta(days=1)
    return day


def month_halves(start: date, end: date) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        out.append((cursor.year, cursor.month, "a"))
        out.append((cursor.year, cursor.month, "b"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return out


def fetch_sec_ftd_rows(
    tickers: set[str], start: date, end: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-free-short-pressure-shadow/1.0 "
                "research-only local workspace"
            )
        }
    )
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for year, month, half in month_halves(start, end):
        yyyymm = f"{year}{month:02d}"
        url = SEC_FTD_URL.format(yyyymm=yyyymm, half=half)
        publication_date = sec_half_publication_date(year, month, half)
        status = None
        matched = 0
        try:
            response = session.get(url, timeout=30)
            status = response.status_code
            if status != 200:
                files.append(
                    {
                        "period": f"{yyyymm}{half}",
                        "publication_date": publication_date.isoformat(),
                        "url": url,
                        "status_code": status,
                        "matched_rows": 0,
                    }
                )
                continue
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = archive.namelist()
                if not names:
                    raise ValueError("empty SEC FTD zip")
                text = archive.read(names[0]).decode("latin-1")
        except Exception as exc:  # pragma: no cover - network can vary.
            files.append(
                {
                    "period": f"{yyyymm}{half}",
                    "publication_date": publication_date.isoformat(),
                    "url": url,
                    "status_code": status,
                    "error": str(exc),
                    "matched_rows": 0,
                }
            )
            continue

        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            ticker = (raw.get("SYMBOL") or raw.get("Symbol") or "").upper().strip()
            if ticker not in tickers:
                continue
            settlement_raw = raw.get("SETTLEMENT DATE") or raw.get("SETTLEMENT_DATE")
            if not settlement_raw:
                continue
            try:
                settlement = datetime.strptime(settlement_raw.strip(), "%Y%m%d").date()
            except ValueError:
                continue
            qty = base.to_int(raw.get("QUANTITY (FAILS)") or raw.get("QUANTITY_FAILS"))
            price = base.to_float(raw.get("PRICE") or raw.get("Price"))
            matched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication_date.isoformat(),
                    "usable_trade_date": publication_date.isoformat(),
                    "publication_date_method": "conservative_sec_availability_window",
                    "pit_safe_for_shadow": True,
                    "production_pit_risk": "medium_posting_date_not_exact",
                    "ftd_quantity": qty,
                    "ftd_price": price,
                    "description": raw.get("DESCRIPTION") or raw.get("Description"),
                    "source_url": url,
                    "source_note": (
                        "SEC FTD is an aggregate balance as of settlement date, "
                        "not daily new short selling and not proof of naked shorting."
                    ),
                }
            )
        files.append(
            {
                "period": f"{yyyymm}{half}",
                "publication_date": publication_date.isoformat(),
                "url": url,
                "status_code": status,
                "matched_rows": matched,
            }
        )
    return rows, files


def prior_business_day(day: date) -> date:
    day -= timedelta(days=1)
    while not base.is_business_day(day):
        day -= timedelta(days=1)
    return day


def fetch_nasdaq_threshold_flags(
    tickers: set[str], candidate_dates: list[date]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "ginger-free-short-pressure-shadow/1.0 research-only"}
    )
    dates = sorted({prior_business_day(day) for day in candidate_dates})
    flags: dict[tuple[str, str], dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    for day in dates:
        url = NASDAQ_REGSHO_URL.format(yyyymmdd=day.strftime("%Y%m%d"))
        matched = 0
        status = None
        try:
            response = session.get(url, timeout=15)
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            if status != 200 or "text/plain" not in content_type:
                files.append(
                    {
                        "trade_date": day.isoformat(),
                        "url": url,
                        "status_code": status,
                        "content_type": content_type,
                        "matched_rows": 0,
                    }
                )
                continue
            reader = csv.DictReader(io.StringIO(response.text), delimiter="|")
            for raw in reader:
                ticker = (raw.get("Symbol") or "").upper().strip()
                if ticker not in tickers:
                    continue
                matched += 1
                flags[(ticker, day.isoformat())] = {
                    "ticker": ticker,
                    "threshold_trade_date": day.isoformat(),
                    "usable_trade_date": (day + timedelta(days=1)).isoformat(),
                    "threshold_security_flag": raw.get("Reg SHO Threshold Flag") == "Y",
                    "rule_3210": raw.get("Rule 3210") == "Y",
                    "market_category": raw.get("Market Category"),
                    "security_name": raw.get("Security Name"),
                    "source_url": url,
                    "coverage_note": "Nasdaq historical threshold file only; NYSE/Arca/Cboe candidates are not covered here.",
                }
        except Exception as exc:  # pragma: no cover - network can vary.
            files.append(
                {
                    "trade_date": day.isoformat(),
                    "url": url,
                    "status_code": status,
                    "error": str(exc),
                    "matched_rows": 0,
                }
            )
            continue
        files.append(
            {
                "trade_date": day.isoformat(),
                "url": url,
                "status_code": status,
                "matched_rows": matched,
            }
        )
    return flags, files


def latest_ftd_tag(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    candidate_date: date,
    average_daily_volume: int | None,
) -> dict[str, Any]:
    rows = [
        row
        for row in rows_by_ticker.get(ticker.upper(), [])
        if base.parse_date(row["publication_date"]) <= candidate_date
        and base.parse_date(row["settlement_date"]) <= candidate_date
    ]
    recent = [
        row
        for row in rows
        if base.parse_date(row["settlement_date"]) >= candidate_date - timedelta(days=30)
    ]
    latest = max(rows, key=lambda row: row["settlement_date"]) if rows else None
    recent_max = max((row.get("ftd_quantity") or 0 for row in recent), default=0)
    ratio = None
    if average_daily_volume and average_daily_volume > 0:
        ratio = round(recent_max / average_daily_volume, 6)
    return {
        "latest_ftd_quantity": latest.get("ftd_quantity") if latest else 0,
        "latest_ftd_settlement_date": latest.get("settlement_date") if latest else None,
        "latest_ftd_publication_date": latest.get("publication_date") if latest else None,
        "ftd_recent_max_30d": recent_max,
        "ftd_recent_days_present_30d": len(recent),
        "ftd_recent_max_adv_ratio": ratio,
        "source_url": latest.get("source_url") if latest else SEC_FTD_PAGE,
        "pit_safe_for_shadow": True,
        "production_pit_risk": "medium_sec_posting_date_not_exact",
    }


def percentile(values: list[float | None]) -> list[float | None]:
    return base.percentile_scores(values)


def attach_free_proxy_tags(
    candidates: list[dict[str, Any]],
    ftd_rows: list[dict[str, Any]],
    threshold_flags: dict[tuple[str, str], dict[str, Any]],
) -> None:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ftd_rows:
        by_ticker[row["ticker"]].append(row)
    for rows in by_ticker.values():
        rows.sort(key=lambda row: (row["publication_date"], row["settlement_date"]))

    for candidate in candidates:
        cdate = base.parse_date(candidate["date"])
        short_tag = candidate.get("short_interest_tag") or {}
        ftd_tag = latest_ftd_tag(
            by_ticker,
            candidate["ticker"],
            cdate,
            short_tag.get("average_daily_volume"),
        )
        threshold_day = prior_business_day(cdate).isoformat()
        threshold = threshold_flags.get((candidate["ticker"], threshold_day))
        candidate["free_short_pressure_tag"] = {
            "ftd": ftd_tag,
            "nasdaq_threshold": threshold
            or {
                "threshold_security_flag": False,
                "threshold_trade_date": threshold_day,
                "usable_trade_date": cdate.isoformat(),
                "coverage_note": "No Nasdaq threshold match; may be non-Nasdaq or not threshold-listed.",
            },
        }

    tagged = [c for c in candidates if c.get("short_interest_tag")]
    ftd_ratios = [
        (c.get("free_short_pressure_tag") or {})
        .get("ftd", {})
        .get("ftd_recent_max_adv_ratio")
        for c in tagged
    ]
    ftd_scores = percentile(ftd_ratios)
    for candidate, ftd_score in zip(tagged, ftd_scores):
        short_tag = candidate["short_interest_tag"]
        free_tag = candidate["free_short_pressure_tag"]
        threshold_flag = bool(
            free_tag.get("nasdaq_threshold", {}).get("threshold_security_flag")
        )
        short_score = short_tag.get("short_crowding_score")
        change_score = short_tag.get("short_change_score")
        short_score = 0.0 if short_score is None else short_score
        change_score = 0.0 if change_score is None else change_score
        ftd_score = 0.0 if ftd_score is None else ftd_score
        composite = round(
            0.45 * short_score
            + 0.25 * change_score
            + 0.25 * ftd_score
            + 0.05 * (1.0 if threshold_flag else 0.0),
            4,
        )
        free_tag["ftd"]["ftd_stress_score"] = ftd_score
        free_tag["free_regulatory_short_pressure_proxy_score"] = composite
        free_tag["score_components"] = {
            "short_crowding_score": short_score,
            "short_change_score": change_score,
            "ftd_stress_score": ftd_score,
            "nasdaq_threshold_flag": threshold_flag,
            "weights": {
                "short_crowding": 0.45,
                "short_change": 0.25,
                "ftd_stress": 0.25,
                "nasdaq_threshold": 0.05,
            },
        }
        free_tag["score_note"] = (
            "Observation-only composite of free regulatory proxy fields; "
            "not a production rule and not a borrow-fee substitute."
        )


def finite_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value: Any = row
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, (int, float)) and not math.isnan(value):
            values.append(float(value))
    return values


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows)}
    for horizon in HORIZONS:
        vals = finite_values(rows, f"forward_returns.{horizon}d")
        out[f"forward_{horizon}d_count"] = len(vals)
        out[f"forward_{horizon}d_mean"] = round(mean(vals), 6) if vals else None
        out[f"forward_{horizon}d_median"] = round(median(vals), 6) if vals else None
    pnl = finite_values(rows, "pnl_pct_net")
    out["realized_trade_count"] = len(pnl)
    out["realized_pnl_pct_mean"] = round(mean(pnl), 6) if pnl else None
    out["realized_win_rate"] = (
        round(sum(1 for value in pnl if value > 0) / len(pnl), 6) if pnl else None
    )
    return out


def build_summary(candidates: list[dict[str, Any]], finra_only: dict[str, Any] | None) -> dict[str, Any]:
    tagged = [
        c
        for c in candidates
        if c.get("short_interest_tag") and c.get("free_short_pressure_tag")
    ]
    scores = finite_values(
        tagged, "free_short_pressure_tag.free_regulatory_short_pressure_proxy_score"
    )
    threshold = sorted(scores)[max(0, math.ceil(0.75 * len(scores)) - 1)] if scores else None
    high = [
        c
        for c in tagged
        if threshold is not None
        and c["free_short_pressure_tag"]["free_regulatory_short_pressure_proxy_score"] >= threshold
    ]
    rest = [c for c in tagged if c not in high]
    high_breakout = [c for c in high if c.get("strategy") == "breakout_long"]
    other_breakout = [
        c for c in tagged if c.get("strategy") == "breakout_long" and c not in high_breakout
    ]
    slot_conflicts = [c for c in tagged if c.get("decision") in SCARCE_SLOT_DECISIONS]
    high_slot_conflicts = [c for c in high if c.get("decision") in SCARCE_SLOT_DECISIONS]
    high_20 = finite_values(high, "forward_returns.20d")
    rest_20 = finite_values(rest, "forward_returns.20d")
    slot_20 = finite_values(high_slot_conflicts, "forward_returns.20d")
    entered_rest_20 = finite_values(
        [c for c in rest if c.get("decision") == "entered"], "forward_returns.20d"
    )
    threshold_matches = [
        c
        for c in tagged
        if c["free_short_pressure_tag"]["nasdaq_threshold"].get(
            "threshold_security_flag"
        )
    ]
    ftd_positive = [
        c
        for c in tagged
        if c["free_short_pressure_tag"]["ftd"].get("ftd_recent_max_30d", 0) > 0
    ]
    return {
        "high_free_proxy_definition": {
            "method": "top_quartile_of_free_regulatory_short_pressure_proxy_score",
            "threshold": threshold,
            "note": "Observation-only stratification threshold, not a proposed production rule.",
        },
        "all_tagged": summarize(tagged),
        "high_free_proxy": summarize(high),
        "non_high_free_proxy": summarize(rest),
        "high_free_proxy_breakout_long": summarize(high_breakout),
        "other_breakout_long": summarize(other_breakout),
        "ftd_positive_candidates": summarize(ftd_positive),
        "nasdaq_threshold_candidates": summarize(threshold_matches),
        "slot_conflict_audit": {
            "slot_conflict_count": len(slot_conflicts),
            "high_free_proxy_slot_conflict_count": len(high_slot_conflicts),
            "high_free_proxy_slot_conflict_forward_20d_mean": (
                round(mean(slot_20), 6) if slot_20 else None
            ),
            "entered_non_high_forward_20d_mean": (
                round(mean(entered_rest_20), 6) if entered_rest_20 else None
            ),
            "scarce_slot_opportunity_cost_20d": (
                round(mean(slot_20) - mean(entered_rest_20), 6)
                if slot_20 and entered_rest_20
                else None
            ),
        },
        "delta_observations": {
            "high_minus_non_high_forward_20d": (
                round(mean(high_20) - mean(rest_20), 6) if high_20 and rest_20 else None
            ),
            "expected_value_score_delta": None,
            "reason_ev_delta_null": "No production replay or portfolio ordering change was made.",
        },
        "comparison_to_finra_only": finra_only.get("shadow_metrics", {}).get(
            "delta_observations"
        )
        if finra_only
        else None,
        "false_positive_examples": [
            {
                "window": c.get("window"),
                "date": c.get("date"),
                "ticker": c.get("ticker"),
                "strategy": c.get("strategy"),
                "decision": c.get("decision"),
                "proxy_score": c["free_short_pressure_tag"].get(
                    "free_regulatory_short_pressure_proxy_score"
                ),
                "ftd_recent_max_adv_ratio": c["free_short_pressure_tag"]["ftd"].get(
                    "ftd_recent_max_adv_ratio"
                ),
                "threshold_flag": c["free_short_pressure_tag"][
                    "nasdaq_threshold"
                ].get("threshold_security_flag"),
                "pnl_pct_net": c.get("pnl_pct_net"),
                "forward_20d": (c.get("forward_returns") or {}).get("20d"),
            }
            for c in sorted(
                [
                    c
                    for c in high
                    if (c.get("pnl_pct_net") is not None and c["pnl_pct_net"] < 0)
                    or (
                        (c.get("forward_returns") or {}).get("20d") is not None
                        and c["forward_returns"]["20d"] < -0.05
                    )
                ],
                key=lambda c: c.get("pnl_pct_net")
                if c.get("pnl_pct_net") is not None
                else (c.get("forward_returns") or {}).get("20d")
                or 0,
            )[:8]
        ],
    }


def write_audit(path: Path, payload: dict[str, Any]) -> None:
    coverage = payload["data_coverage"]
    shadow = payload["shadow_metrics"]
    lines = [
        "# Free Regulatory Short Pressure Proxy Shadow Experiment",
        "",
        f"- Experiment: `{payload['experiment_id']}`",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Production impact: `{payload['production_impact']}`",
        "",
        "## Sources",
        "",
        f"- FINRA short interest: {base.FINRA_SOURCE_URL}",
        f"- SEC fails-to-deliver: {SEC_FTD_PAGE}",
        f"- Nasdaq Reg SHO threshold: {NASDAQ_REGSHO_PAGE}",
        "",
        "## Coverage",
        "",
        f"- Candidates tagged: `{coverage['tagged_candidate_count']}` / `{coverage['candidate_count']}`",
        f"- SEC FTD files OK: `{coverage['sec_ftd_files_ok']}` / `{coverage['sec_ftd_files_attempted']}`",
        f"- SEC FTD candidates with recent positive FTD: `{coverage['ftd_positive_candidate_count']}`",
        f"- Nasdaq threshold files OK: `{coverage['nasdaq_threshold_files_ok']}` / `{coverage['nasdaq_threshold_files_attempted']}`",
        f"- Nasdaq threshold candidate matches: `{coverage['nasdaq_threshold_candidate_count']}`",
        "",
        "## Shadow Result",
        "",
        f"- High free proxy: `{shadow['high_free_proxy']}`",
        f"- Non-high free proxy: `{shadow['non_high_free_proxy']}`",
        f"- High free proxy + breakout_long: `{shadow['high_free_proxy_breakout_long']}`",
        f"- Other breakout_long: `{shadow['other_breakout_long']}`",
        f"- Slot conflict audit: `{shadow['slot_conflict_audit']}`",
        f"- Delta observations: `{shadow['delta_observations']}`",
        "",
        "## Decision",
        "",
        payload["decision_reason"],
        "",
        "## Next Minimal Action",
        "",
        payload["next_minimal_action"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = base.load_json(path)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "production_impact": payload["production_impact"],
        "expected_value_score_delta": None,
        "data_coverage": payload["data_coverage"],
        "artifact": payload["related_files"]["artifact"],
        "audit": payload["related_files"]["audit"],
        "log": payload["related_files"]["log"],
    }
    base.dump_json(path, ticket)


def main() -> None:
    args = parse_args()
    experiment_id = args.experiment_id
    result_path = Path(args.backtest_result).resolve()
    result = base.load_json(result_path)
    candidates = base.extract_candidates(result)
    candidate_dates = [base.parse_date(c["date"]) for c in candidates]
    tickers = sorted({c["ticker"] for c in candidates})

    settlements = base.settlement_dates(min(candidate_dates) - timedelta(days=45), max(candidate_dates))
    finra_rows, finra_files = base.fetch_finra_rows(set(tickers), settlements)
    base.attach_short_tags(candidates, finra_rows)
    base.add_forward_returns(candidates)

    ftd_rows, ftd_files = fetch_sec_ftd_rows(
        set(tickers),
        min(candidate_dates) - timedelta(days=80),
        max(candidate_dates),
    )
    threshold_flags, threshold_files = fetch_nasdaq_threshold_flags(
        set(tickers), candidate_dates
    )
    attach_free_proxy_tags(candidates, ftd_rows, threshold_flags)

    finra_only_path = (
        REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260505-024"
        / "short_interest_shadow_results.json"
    )
    finra_only = base.load_json(finra_only_path) if finra_only_path.exists() else None
    shadow = build_summary(candidates, finra_only)

    tagged = [
        c
        for c in candidates
        if c.get("short_interest_tag") and c.get("free_short_pressure_tag")
    ]
    ftd_positive = [
        c
        for c in tagged
        if c["free_short_pressure_tag"]["ftd"].get("ftd_recent_max_30d", 0) > 0
    ]
    threshold_matches = [
        c
        for c in tagged
        if c["free_short_pressure_tag"]["nasdaq_threshold"].get(
            "threshold_security_flag"
        )
    ]
    coverage = {
        "candidate_count": len(candidates),
        "candidate_ticker_count": len(tickers),
        "tagged_candidate_count": len(tagged),
        "tagged_candidate_coverage_pct": len(tagged) / len(candidates),
        "finra_files_ok": sum(1 for f in finra_files if f.get("status_code") == 200),
        "finra_files_attempted": len(finra_files),
        "sec_ftd_rows_filtered": len(ftd_rows),
        "sec_ftd_files_ok": sum(1 for f in ftd_files if f.get("status_code") == 200),
        "sec_ftd_files_attempted": len(ftd_files),
        "ftd_positive_candidate_count": len(ftd_positive),
        "nasdaq_threshold_files_ok": sum(
            1 for f in threshold_files if f.get("status_code") == 200
        ),
        "nasdaq_threshold_files_attempted": len(threshold_files),
        "nasdaq_threshold_candidate_count": len(threshold_matches),
        "nasdaq_threshold_coverage_note": (
            "Nasdaq historical files only; non-Nasdaq listed candidates are not covered by this source."
        ),
    }
    baseline_metrics = {
        window_name: base.metric_snapshot(window)
        for window_name, window in base.result_windows(result)
    }
    window_ranges = base.candidate_date_ranges(candidates)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    output_dir = Path(args.output_dir) / experiment_id
    artifact_path = output_dir / "free_short_pressure_shadow_results.json"
    snapshot_path = output_dir / "backtest_results_snapshot.json"
    audit_path = (
        REPO_ROOT
        / "docs"
        / "non_ohlcv_data_audit"
        / f"free_short_pressure_proxy_{experiment_id}_20260506.md"
    )
    log_path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(result_path.read_text(encoding="utf-8"), encoding="utf-8")
    related_files = {
        "artifact": base.repo_rel(artifact_path),
        "audit": base.repo_rel(audit_path),
        "log": base.repo_rel(log_path),
        "backtest_result": base.repo_rel(snapshot_path),
    }
    decision_reason = (
        "Shadow-only: the free regulatory proxy bundle adds SEC FTD and Nasdaq "
        "threshold flags to FINRA short interest, but these are indirect stress "
        "proxies rather than true borrow fee / availability data. No production "
        "rule is justified without multi-window replay and a stronger slot-value edge."
    )
    next_minimal_action = (
        "If the shadow bucket improves versus FINRA-only, run the same proxy over "
        "the fixed three-window snapshot set; otherwise stop at audit/shadow."
    )
    payload = {
        "experiment_id": experiment_id,
        "timestamp": timestamp,
        "status": args.status,
        "hypothesis": (
            "A free regulatory short-pressure proxy score may outperform FINRA "
            "days-to-cover alone by adding SEC FTD balances and Nasdaq Reg SHO "
            "threshold flags to existing Ginger candidates."
        ),
        "non_ohlcv_data_source": [
            "FINRA official equity short-interest CSV",
            "SEC fails-to-deliver zip files",
            "Nasdaq historical Reg SHO threshold text files",
        ],
        "source_urls": [base.FINRA_SOURCE_URL, SEC_FTD_PAGE, NASDAQ_REGSHO_PAGE],
        "mechanism_family": "free_regulatory_short_pressure_proxy_overlay",
        "single_causal_variable": "free_regulatory_short_pressure_proxy_score",
        "data_availability_pit_status": {
            "short_interest_days_to_cover": "available_pit_safe_with_publication_date_lag",
            "sec_ftd": "available_with_conservative_availability_date; posting date not exact",
            "nasdaq_threshold_flag": "available_for_nasdaq_historical_files_only",
            "borrow_fee": "missing",
            "shares_available": "missing",
            "hard_to_borrow": "missing",
            "short_interest_float": "missing",
        },
        "baseline_metrics": baseline_metrics,
        "candidate_date_ranges": window_ranges,
        "data_coverage": coverage,
        "shadow_metrics": shadow,
        "candidate_overlap_and_slot_value": {
            "overlap_with_existing_signals": 1.0,
            "standalone_entries_generated": 0,
            "candidate_count": len(candidates),
            **shadow["slot_conflict_audit"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
        },
        "decision": "shadow_only",
        "decision_reason": decision_reason,
        "next_minimal_action": next_minimal_action,
        "related_files": related_files,
        "finra_files": finra_files,
        "sec_ftd_files": ftd_files,
        "nasdaq_threshold_files": threshold_files,
        "sec_ftd_rows_sample": ftd_rows[:20],
        "tagged_candidates": candidates,
    }
    base.dump_json(artifact_path, payload)

    log_row = {
        "experiment_id": experiment_id,
        "timestamp": timestamp,
        "status": args.status,
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Ran a free-source regulatory short-pressure proxy shadow join "
            "(FINRA short interest + SEC FTD + Nasdaq threshold) against existing candidates."
        ),
        "change_type": "shadow_non_ohlcv_overlay",
        "component": "scripts/run_free_short_pressure_shadow_experiment.py",
        "parameters": {
            "single_causal_variable": payload["single_causal_variable"],
            "standalone_entries_generated": 0,
            "sources": payload["non_ohlcv_data_source"],
            "score_weights": {
                "short_crowding": 0.45,
                "short_change": 0.25,
                "ftd_stress": 0.25,
                "nasdaq_threshold": 0.05,
            },
        },
        "date_range": window_ranges.get("primary"),
        "secondary_windows": [
            window_ranges[name] for name in sorted(window_ranges) if name != "primary"
        ],
        "market_regime_summary": {
            "primary": "same snapshot as exp-20260505-024",
            "secondary": "same snapshot as exp-20260505-024",
        },
        "before_metrics": baseline_metrics.get("primary"),
        "after_metrics": baseline_metrics.get("primary"),
        "delta_metrics": {
            "expected_value_score_delta": None,
            "production_portfolio_delta": None,
            "shadow_high_minus_non_high_forward_20d": shadow["delta_observations"][
                "high_minus_non_high_forward_20d"
            ],
        },
        "shadow_metrics": shadow,
        "data_coverage": coverage,
        "llm_metrics": {"used_llm": False},
        "decision": "shadow_only",
        "rejection_reason": None,
        "next_retry_requires": [
            "Three-window shadow/replay only if free proxy beats FINRA-only on slot value",
            "True borrow fee / availability source for production-grade squeeze pressure",
        ],
        "related_files": list(related_files.values()),
        "notes": decision_reason,
        "production_impact": payload["production_impact"],
    }
    base.dump_json(log_path, log_row)
    # Per-experiment shard (above) is the source of truth; the monolithic
    # docs/experiment_log.jsonl is a derived view rebuilt via
    # `experiment.py rebuild-log`, not written here.
    write_audit(audit_path, payload)
    update_ticket(
        REPO_ROOT / "experiments" / "tickets" / f"{experiment_id}.json",
        payload,
    )
    base.update_registry(
        REPO_ROOT / "docs" / "experiment_registry.json", experiment_id, args.status
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
