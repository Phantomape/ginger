from __future__ import annotations

import argparse
import gzip
import json
import math
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from data_paths import resolve_daily_artifact_path
from sec_ticker_map import normalize_cik


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_CACHE_DIR = DATA_DIR / "sec_companyfacts_cache"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv"
DEFAULT_START = "2024-10-02"
DEFAULT_END = "2026-04-21"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
NON_COMPANY_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}
DEFAULT_FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A"}

SELECTED_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "gross_profit": ("GrossProfit",),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "eps_basic": ("EarningsPerShareBasic",),
    "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "inventory": ("InventoryNet", "InventoryFinishedGoodsNet"),
    "receivables": ("AccountsReceivableNetCurrent", "AccountsReceivableNet"),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
}

CONCEPT_TO_CANONICAL = {
    concept: canonical
    for canonical, concepts in SELECTED_CONCEPTS.items()
    for concept in concepts
}


def _repo_path(path: Path | str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _repo_rel(path: Path | str) -> str:
    value = _repo_path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        out = float(value)
        if math.isfinite(out):
            return out
    return None


def companyfacts_cache_path(cik: str, cache_dir: Path | str | None = None) -> Path:
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        raise ValueError(f"invalid cik: {cik!r}")
    return Path(cache_dir or DEFAULT_CACHE_DIR) / f"CIK{cik_norm}.json"


def fetch_companyfacts(
    cik: str,
    *,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = 0.11,
) -> dict[str, Any]:
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        raise ValueError(f"invalid cik: {cik!r}")
    path = companyfacts_cache_path(cik_norm, cache_dir)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    request = urllib.request.Request(
        SEC_COMPANYFACTS_URL.format(cik=cik_norm),
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return payload


def _ticker_to_cik_map() -> dict[str, str]:
    payload = _load_json(DATA_DIR / "sec_company_tickers.json", {})
    rows = payload.values() if isinstance(payload, dict) else payload
    out: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = normalize_cik(row.get("cik_str") or row.get("cik"))
        if ticker and cik:
            out.setdefault(ticker, cik)
    return out


def _universe_tickers(segments: tuple[str, ...]) -> list[str]:
    state = _load_json(resolve_daily_artifact_path("universe_state", "20260501", DATA_DIR), {})
    segment_to_key = {
        "core": "core_trade_universe",
        "pilot": "pilot_trade_universe",
        "observation": "observation_universe",
    }
    tickers: set[str] = set()
    for segment in segments:
        tickers.update(str(ticker).upper() for ticker in state.get(segment_to_key[segment], []) or [])
    return sorted(tickers)


def _resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        tickers = {
            ticker.strip().upper()
            for item in args.tickers
            for ticker in item.split(",")
            if ticker.strip()
        }
    else:
        tickers = set(_universe_tickers(tuple(args.segments)))
    if not args.include_etfs:
        tickers -= NON_COMPANY_TICKERS
    out = sorted(tickers)
    if args.max_ciks:
        out = out[: args.max_ciks]
    return out


def iter_selected_fact_rows(
    payload: dict[str, Any],
    *,
    ticker: str,
    cik: str,
    forms: set[str],
    min_period_end: str,
    max_filed: str,
) -> list[dict[str, Any]]:
    cik_norm = normalize_cik(cik or payload.get("cik"))
    company_name = payload.get("entityName")
    facts = payload.get("facts") if isinstance(payload, dict) else {}
    us_gaap = facts.get("us-gaap") if isinstance(facts, dict) else {}
    rows: list[dict[str, Any]] = []
    for concept, data in (us_gaap or {}).items():
        canonical = CONCEPT_TO_CANONICAL.get(concept)
        if not canonical or not isinstance(data, dict):
            continue
        units = data.get("units") if isinstance(data.get("units"), dict) else {}
        for unit, facts_for_unit in units.items():
            if not isinstance(facts_for_unit, list):
                continue
            for fact in facts_for_unit:
                if not isinstance(fact, dict):
                    continue
                form = str(fact.get("form") or "").upper()
                if form not in forms:
                    continue
                end = str(fact.get("end") or "")[:10]
                filed = str(fact.get("filed") or "")[:10]
                if not end or not filed or end < min_period_end or filed > max_filed:
                    continue
                value = _float_or_none(fact.get("val"))
                if value is None:
                    continue
                start = str(fact.get("start") or "")[:10] or None
                duration_days = None
                start_dt = _parse_date(start)
                end_dt = _parse_date(end)
                if start_dt and end_dt:
                    duration_days = (end_dt - start_dt).days + 1
                accession = fact.get("accn")
                rows.append({
                    "ticker": str(ticker).upper(),
                    "cik": cik_norm,
                    "company_name": company_name,
                    "canonical": canonical,
                    "concept": concept,
                    "taxonomy": "us-gaap",
                    "unit": unit,
                    "value": value,
                    "start": start,
                    "end": end,
                    "filed": filed,
                    "form": form,
                    "fp": fact.get("fp"),
                    "fy": fact.get("fy"),
                    "frame": fact.get("frame"),
                    "accession_number": str(accession) if accession else None,
                    "duration_days": duration_days,
                    "pit_source": "sec_companyfacts",
                    "pit_caveat": (
                        "SEC companyfacts filed date is used as public-availability PIT proxy; "
                        "it does not prove the local production pipeline observed this fact."
                    ),
                })
    return sorted(rows, key=lambda row: (row["filed"], row["ticker"], row["canonical"], row["end"], row.get("accession_number") or ""))


def backfill_companyfacts(args: argparse.Namespace) -> dict[str, Any]:
    tickers = _resolve_tickers(args)
    ticker_to_cik = _ticker_to_cik_map()
    forms = {str(form).upper() for form in args.forms}
    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    min_period_end = (start_dt - timedelta(days=args.prior_period_days)).strftime("%Y-%m-%d")
    cache_dir = _repo_path(args.cache_dir)
    output = _repo_path(args.output)
    summary_output = _repo_path(args.summary_output)

    rows_written = 0
    errors = []
    missing_cik = []
    ticker_counts: dict[str, int] = {}
    canonical_counts: dict[str, int] = {}
    form_counts: dict[str, int] = {}

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for ticker in tickers:
            cik = ticker_to_cik.get(ticker)
            if not cik:
                missing_cik.append(ticker)
                continue
            try:
                payload = fetch_companyfacts(
                    cik,
                    cache_dir=cache_dir,
                    refresh=args.refresh,
                    user_agent=args.user_agent,
                    sleep_seconds=args.sleep_seconds,
                )
                rows = iter_selected_fact_rows(
                    payload,
                    ticker=ticker,
                    cik=cik,
                    forms=forms,
                    min_period_end=min_period_end,
                    max_filed=args.end,
                )
            except Exception as exc:  # pragma: no cover - exercised in real network runs
                errors.append({"ticker": ticker, "cik": cik, "error": str(exc)})
                continue
            ticker_counts[ticker] = len(rows)
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                rows_written += 1
                canonical_counts[row["canonical"]] = canonical_counts.get(row["canonical"], 0) + 1
                form_counts[row["form"]] = form_counts.get(row["form"], 0) + 1

    summary = {
        "start": args.start,
        "end": args.end,
        "min_period_end": min_period_end,
        "output": _repo_rel(output),
        "cache_dir": _repo_rel(cache_dir),
        "tickers_requested": len(tickers),
        "tickers_with_cik": len(tickers) - len(missing_cik),
        "missing_cik": missing_cik,
        "rows_written": rows_written,
        "error_count": len(errors),
        "errors": errors,
        "forms": sorted(forms),
        "selected_canonical_fields": sorted(SELECTED_CONCEPTS),
        "row_counts_by_ticker": dict(sorted(ticker_counts.items())),
        "row_counts_by_canonical": dict(sorted(canonical_counts.items())),
        "row_counts_by_form": dict(sorted(form_counts.items())),
        "pit_caveat": "SEC companyfacts filed date is a public-availability PIT proxy.",
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill selected SEC Companyfacts rows.")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUT_DIR / f"sec_companyfacts_selected_{DEFAULT_START.replace('-', '')}_{DEFAULT_END.replace('-', '')}.jsonl"),
    )
    parser.add_argument(
        "--summary-output",
        default=str(DEFAULT_OUT_DIR / f"sec_companyfacts_backfill_summary_{DEFAULT_START.replace('-', '')}_{DEFAULT_END.replace('-', '')}.json"),
    )
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--segments", nargs="+", default=["core", "pilot", "observation"], choices=["core", "pilot", "observation"])
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--max-ciks", type=int, default=None)
    parser.add_argument("--include-etfs", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--forms", nargs="+", default=sorted(DEFAULT_FORMS))
    parser.add_argument("--prior-period-days", type=int, default=550)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = backfill_companyfacts(args)
    print(json.dumps({
        "rows_written": summary["rows_written"],
        "tickers_requested": summary["tickers_requested"],
        "tickers_with_cik": summary["tickers_with_cik"],
        "missing_cik": summary["missing_cik"],
        "error_count": summary["error_count"],
        "row_counts_by_canonical": summary["row_counts_by_canonical"],
        "output": summary["output"],
    }, indent=2, ensure_ascii=False))
    return 0 if summary["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
