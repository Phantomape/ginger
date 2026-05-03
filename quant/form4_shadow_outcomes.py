from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
DEFAULT_OUTPUT = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "form4_purchase_shadow_outcomes_20260503.md"
SNAPSHOT_FILES = [
    DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260501_with_pilot.json",
]
WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
HORIZONS = (5, 10, 20, 60)
MIN_MEANINGFUL_VALUE = 50_000.0


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _owner_is_issuer(row: dict[str, Any]) -> bool:
    owner = _norm_text(row.get("owner_name"))
    issuer = _norm_text(row.get("issuer_name"))
    symbol = _norm_text(row.get("issuer_trading_symbol") or row.get("ticker"))
    if not owner:
        return False
    if issuer and (owner == issuer or issuer in owner or owner in issuer):
        return True
    if symbol and owner == symbol:
        return True
    return False


def _is_ceo_cfo(title: Any) -> bool:
    text = str(title or "").lower()
    return any(token in text for token in (
        "chief executive",
        "chief financial",
        "ceo",
        "cfo",
        "president",
    ))


def _load_price_map(snapshot_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in snapshot_paths:
        if not path.exists():
            continue
        payload = _load_json(path)
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                by_ticker_date[ticker_key][str(row["Date"])[:10]] = {
                    "date": str(row["Date"])[:10],
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "volume": _float_or_none(row.get("Volume")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _forward_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_trade_date: str,
    horizon: int,
) -> dict[str, Any] | None:
    rows = prices.get(str(ticker).upper())
    spy_rows = prices.get("SPY")
    if not rows or not spy_rows:
        return None
    start_idx = _first_index_on_or_after(rows, usable_trade_date)
    spy_start_idx = _first_index_on_or_after(spy_rows, usable_trade_date)
    if start_idx is None or spy_start_idx is None:
        return None
    exit_idx = start_idx + horizon
    spy_exit_idx = spy_start_idx + horizon
    if exit_idx >= len(rows) or spy_exit_idx >= len(spy_rows):
        return None
    entry = rows[start_idx]
    exit_row = rows[exit_idx]
    spy_entry = spy_rows[spy_start_idx]
    spy_exit = spy_rows[spy_exit_idx]
    if not entry["open"] or not exit_row["close"] or not spy_entry["open"] or not spy_exit["close"]:
        return None
    ret = exit_row["close"] / entry["open"] - 1.0
    spy_ret = spy_exit["close"] / spy_entry["open"] - 1.0
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": entry["open"],
        "exit_close": exit_row["close"],
        "return_pct": round(ret * 100.0, 4),
        "spy_return_pct": round(spy_ret * 100.0, 4),
        "excess_vs_spy_pct": round((ret - spy_ret) * 100.0, 4),
    }


def _window_name(usable_trade_date: str) -> str | None:
    for name, (start, end) in WINDOWS.items():
        if start <= usable_trade_date <= end:
            return name
    return None


def _load_purchase_events(path: Path, *, start: str, end: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("open_market_purchase_flag"):
                continue
            usable = str(row.get("usable_trade_date") or "")
            ticker = str(row.get("ticker") or "").upper()
            if not ticker or not usable or usable < start or usable > end:
                continue
            key = (ticker, usable)
            event = grouped.setdefault(key, {
                "ticker": ticker,
                "usable_trade_date": usable,
                "window": _window_name(usable),
                "purchase_transaction_count": 0,
                "filing_count": 0,
                "owner_count": 0,
                "total_purchase_value": 0.0,
                "max_purchase_value": 0.0,
                "any_10b5_1_flag": False,
                "any_option_exercise_flag": False,
                "any_owner_is_issuer": False,
                "any_ceo_cfo_or_president": False,
                "any_officer": False,
                "any_director": False,
                "any_10pct_owner": False,
                "accessions": set(),
                "owners": set(),
                "sample_owner_names": [],
                "sample_officer_titles": [],
            })
            value = _float_or_none(row.get("transaction_value")) or 0.0
            event["purchase_transaction_count"] += 1
            event["total_purchase_value"] += value
            event["max_purchase_value"] = max(event["max_purchase_value"], value)
            event["any_10b5_1_flag"] = event["any_10b5_1_flag"] or bool(row.get("10b5_1_flag"))
            event["any_option_exercise_flag"] = event["any_option_exercise_flag"] or bool(row.get("option_exercise_flag"))
            event["any_owner_is_issuer"] = event["any_owner_is_issuer"] or _owner_is_issuer(row)
            event["any_ceo_cfo_or_president"] = event["any_ceo_cfo_or_president"] or _is_ceo_cfo(row.get("officer_title"))
            event["any_officer"] = event["any_officer"] or bool(row.get("is_officer"))
            event["any_director"] = event["any_director"] or bool(row.get("is_director"))
            event["any_10pct_owner"] = event["any_10pct_owner"] or bool(row.get("is_10pct_owner"))
            if row.get("accession_number"):
                event["accessions"].add(str(row["accession_number"]))
            if row.get("owner_cik"):
                event["owners"].add(str(row["owner_cik"]))
            owner_name = row.get("owner_name")
            if owner_name and owner_name not in event["sample_owner_names"] and len(event["sample_owner_names"]) < 4:
                event["sample_owner_names"].append(owner_name)
            title = row.get("officer_title")
            if title and title not in event["sample_officer_titles"] and len(event["sample_officer_titles"]) < 4:
                event["sample_officer_titles"].append(title)

    events = []
    for event in grouped.values():
        accessions = event.pop("accessions")
        owners = event.pop("owners")
        event["filing_count"] = len(accessions)
        event["owner_count"] = len(owners)
        event["total_purchase_value"] = round(event["total_purchase_value"], 2)
        event["meaningful_purchase_v1"] = (
            event["total_purchase_value"] >= MIN_MEANINGFUL_VALUE
            and not event["any_10b5_1_flag"]
            and not event["any_option_exercise_flag"]
            and not event["any_owner_is_issuer"]
            and (event["any_officer"] or event["any_director"] or event["any_10pct_owner"])
        )
        event["ceo_cfo_purchase_v1"] = event["meaningful_purchase_v1"] and event["any_ceo_cfo_or_president"]
        events.append(event)
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"]))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 4)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 4)


def _summarize(events: list[dict[str, Any]], flag_name: str) -> dict[str, Any]:
    selected = [event for event in events if flag_name == "all_open_market_purchase" or event.get(flag_name)]
    out: dict[str, Any] = {
        "event_count": len(selected),
        "ticker_count": len({event["ticker"] for event in selected}),
        "total_purchase_value": round(sum(event["total_purchase_value"] for event in selected), 2),
        "by_window": {},
        "horizons": {},
    }
    for window in WINDOWS:
        rows = [event for event in selected if event.get("window") == window]
        out["by_window"][window] = {
            "event_count": len(rows),
            "ticker_count": len({event["ticker"] for event in rows}),
            "total_purchase_value": round(sum(event["total_purchase_value"] for event in rows), 2),
        }
    for horizon in HORIZONS:
        returns = []
        excess = []
        for event in selected:
            outcome = event.get("outcomes", {}).get(str(horizon))
            if not outcome:
                continue
            returns.append(outcome["return_pct"])
            excess.append(outcome["excess_vs_spy_pct"])
        out["horizons"][str(horizon)] = {
            "count": len(returns),
            "avg_return_pct": _mean(returns),
            "median_return_pct": _median(returns),
            "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
            "avg_excess_vs_spy_pct": _mean(excess),
            "median_excess_vs_spy_pct": _median(excess),
            "excess_win_rate": round(sum(1 for value in excess if value > 0) / len(excess), 4) if excess else None,
        }
    return out


def _add_outcomes(events: list[dict[str, Any]], prices: dict[str, list[dict[str, Any]]]) -> None:
    for event in events:
        outcomes = {}
        for horizon in HORIZONS:
            outcome = _forward_return(prices, event["ticker"], event["usable_trade_date"], horizon)
            if outcome:
                outcomes[str(horizon)] = outcome
        event["outcomes"] = outcomes


def _top_examples(events: list[dict[str, Any]], flag_name: str, horizon: int, *, best: bool) -> list[dict[str, Any]]:
    selected = [
        event for event in events
        if (flag_name == "all_open_market_purchase" or event.get(flag_name))
        and str(horizon) in event.get("outcomes", {})
    ]
    selected.sort(key=lambda event: event["outcomes"][str(horizon)]["excess_vs_spy_pct"], reverse=best)
    out = []
    for event in selected[:10]:
        outcome = event["outcomes"][str(horizon)]
        out.append({
            "ticker": event["ticker"],
            "usable_trade_date": event["usable_trade_date"],
            "window": event["window"],
            "total_purchase_value": event["total_purchase_value"],
            "owner_count": event["owner_count"],
            "sample_owner_names": event["sample_owner_names"],
            "sample_officer_titles": event["sample_officer_titles"],
            "return_pct": outcome["return_pct"],
            "excess_vs_spy_pct": outcome["excess_vs_spy_pct"],
        })
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    events = _load_purchase_events(Path(args.input), start=args.start, end=args.end)
    prices = _load_price_map([Path(path) for path in args.snapshots])
    _add_outcomes(events, prices)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment_id": "exp-20260503-046",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_impact": "shadow_outcome_analysis_only",
        },
        "input": _repo_rel(args.input),
        "price_snapshots": [_repo_rel(path) for path in args.snapshots],
        "date_range": {"start": args.start, "end": args.end},
        "event_definition": {
            "unit": "ticker + usable_trade_date",
            "entry_price": "next available trading session open on or after usable_trade_date",
            "exit_price": "horizon trading-day close",
            "benchmark": "SPY same entry/exit open-to-close window",
            "meaningful_purchase_v1": {
                "min_total_purchase_value": MIN_MEANINGFUL_VALUE,
                "requires_not_10b5_1_text": True,
                "requires_not_option_exercise": True,
                "requires_not_owner_is_issuer": True,
                "requires_owner_role": "officer_or_director_or_10pct_owner",
            },
        },
        "coverage": {
            "purchase_event_days": len(events),
            "tickers": sorted({event["ticker"] for event in events}),
            "ticker_count": len({event["ticker"] for event in events}),
            "events_with_any_outcome": sum(1 for event in events if event.get("outcomes")),
            "events_without_outcome": sum(1 for event in events if not event.get("outcomes")),
        },
        "cohorts": {
            "all_open_market_purchase": _summarize(events, "all_open_market_purchase"),
            "meaningful_purchase_v1": _summarize(events, "meaningful_purchase_v1"),
            "ceo_cfo_purchase_v1": _summarize(events, "ceo_cfo_purchase_v1"),
        },
        "top_20d_excess_winners": _top_examples(events, "meaningful_purchase_v1", 20, best=True),
        "top_20d_excess_losers": _top_examples(events, "meaningful_purchase_v1", 20, best=False),
        "events": events,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.report:
        _write_report(summary, Path(args.report))
    return summary


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _cohort_lines(summary: dict[str, Any], cohort_name: str) -> list[str]:
    cohort = summary["cohorts"][cohort_name]
    lines = [
        f"### {cohort_name}",
        "",
        f"- event_count: `{cohort['event_count']}`",
        f"- ticker_count: `{cohort['ticker_count']}`",
        f"- total_purchase_value: `${cohort['total_purchase_value']:,.2f}`",
        "",
        "| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for horizon, row in cohort["horizons"].items():
        lines.append(
            f"| {horizon}d | {row['count']} | {_fmt(row['avg_return_pct'])}% | "
            f"{_fmt(row['median_return_pct'])}% | {_fmt(row['win_rate'])} | "
            f"{_fmt(row['avg_excess_vs_spy_pct'])}% | {_fmt(row['excess_win_rate'])} |"
        )
    lines.append("")
    return lines


def _write_report(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Form 4 Purchase Shadow Outcomes",
        "",
        f"- experiment_id: `{summary['experiment_id']}`",
        f"- generated_at: `{summary['generated_at']}`",
        f"- production_impact: `{summary['production_impact']['production_impact']}`",
        f"- input: `{summary['input']}`",
        f"- output: `data/non_ohlcv/form4_purchase_shadow_outcomes_20241002_20260421.json`",
        "",
        "## Coverage",
        "",
        f"- purchase event-days: `{summary['coverage']['purchase_event_days']}`",
        f"- tickers: `{summary['coverage']['ticker_count']}`",
        f"- events with at least one forward outcome: `{summary['coverage']['events_with_any_outcome']}`",
        "",
        "## Cohorts",
        "",
    ]
    lines.extend(_cohort_lines(summary, "all_open_market_purchase"))
    lines.extend(_cohort_lines(summary, "meaningful_purchase_v1"))
    lines.extend(_cohort_lines(summary, "ceo_cfo_purchase_v1"))
    lines.extend([
        "## Initial Read",
        "",
        "This is shadow-only evidence. The result should be used to decide whether a",
        "Form 4 confirmation overlay deserves a controlled multi-window backtest, not",
        "to directly add entries or sizing rules.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate shadow forward outcomes after Form 4 open-market purchase events.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--start", default="2024-10-02")
    parser.add_argument("--end", default="2026-04-21")
    parser.add_argument("--snapshots", nargs="+", default=[str(path) for path in SNAPSHOT_FILES])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run(args)
    compact = {
        "event_days": summary["coverage"]["purchase_event_days"],
        "meaningful_event_days": summary["cohorts"]["meaningful_purchase_v1"]["event_count"],
        "ceo_cfo_event_days": summary["cohorts"]["ceo_cfo_purchase_v1"]["event_count"],
        "meaningful_20d": summary["cohorts"]["meaningful_purchase_v1"]["horizons"]["20"],
        "output": _repo_rel(args.output),
        "report": _repo_rel(args.report),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
