from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_EVENTS = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
DEFAULT_TRADES = DATA_DIR / "experiments" / "current_accepted_trades_20260502_alpha_search.json"
DEFAULT_OUTPUT = DATA_DIR / "non_ohlcv" / "form4_accepted_trade_overlap_20241002_20260421.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "form4_accepted_trade_overlap_20260503.md"
LOOKBACK_DAYS = (5, 10, 20, 60, 90)


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


def _parse_date(text: str) -> datetime:
    return datetime.strptime(str(text)[:10], "%Y-%m-%d")


def _days_between(start: str, end: str) -> int:
    return (_parse_date(end) - _parse_date(start)).days


def _flatten_trades(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for window, window_payload in payload.items():
        if not isinstance(window_payload, dict):
            continue
        for trade in window_payload.get("trades") or []:
            if not isinstance(trade, dict):
                continue
            rows.append({**trade, "window": window})
    return sorted(rows, key=lambda row: (row.get("entry_date") or "", row.get("ticker") or ""))


def _event_index(events_payload: dict[str, Any], *, flag: str = "meaningful_purchase_v1") -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for event in events_payload.get("events") or []:
        if not isinstance(event, dict) or not event.get(flag):
            continue
        ticker = str(event.get("ticker") or "").upper()
        if not ticker:
            continue
        index.setdefault(ticker, []).append(event)
    for rows in index.values():
        rows.sort(key=lambda row: row["usable_trade_date"])
    return index


def matching_prior_events(
    events_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    lookback_days: int,
) -> list[dict[str, Any]]:
    matches = []
    for event in events_by_ticker.get(str(ticker).upper(), []):
        event_date = event.get("usable_trade_date")
        if not event_date or event_date > entry_date:
            continue
        age_days = _days_between(event_date, entry_date)
        if 0 <= age_days <= lookback_days:
            matches.append({**event, "days_before_entry": age_days})
    return matches


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [float(row["pnl_pct_net"]) * 100.0 for row in trades if row.get("pnl_pct_net") is not None]
    return {
        "trade_count": len(trades),
        "avg_pnl_pct_net": _avg(pnl),
        "win_rate": round(sum(1 for value in pnl if value > 0) / len(pnl), 4) if pnl else None,
        "total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "tickers": sorted({str(row.get("ticker") or "").upper() for row in trades if row.get("ticker")}),
    }


def _overlap_summary(trades: list[dict[str, Any]], events_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for lookback in LOOKBACK_DAYS:
        with_events = []
        without_events = []
        matches = []
        for trade in trades:
            prior = matching_prior_events(
                events_by_ticker,
                str(trade.get("ticker") or "").upper(),
                str(trade.get("entry_date") or ""),
                lookback,
            )
            if prior:
                best = max(prior, key=lambda event: float(event.get("total_purchase_value") or 0.0))
                with_events.append({**trade, "form4_match_count": len(prior), "form4_best_event": best})
                matches.append({
                    "window": trade.get("window"),
                    "ticker": trade.get("ticker"),
                    "strategy": trade.get("strategy"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl_pct_net": trade.get("pnl_pct_net"),
                    "pnl": trade.get("pnl"),
                    "matched_event_count": len(prior),
                    "best_event_date": best.get("usable_trade_date"),
                    "days_before_entry": best.get("days_before_entry"),
                    "best_event_purchase_value": best.get("total_purchase_value"),
                    "best_event_owner_count": best.get("owner_count"),
                    "best_event_owner_names": best.get("sample_owner_names"),
                })
            else:
                without_events.append(trade)
        summary[str(lookback)] = {
            "with_prior_form4": _summarize_trades(with_events),
            "without_prior_form4": _summarize_trades(without_events),
            "matches": matches,
        }
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    events_payload = _load_json(Path(args.events))
    trades_payload = _load_json(Path(args.trades))
    trades = _flatten_trades(trades_payload)
    events_by_ticker = _event_index(events_payload)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment_id": "exp-20260503-048",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_impact": "shadow_overlap_analysis_only",
        },
        "events_input": _repo_rel(args.events),
        "trades_input": _repo_rel(args.trades),
        "event_flag": "meaningful_purchase_v1",
        "trade_count": len(trades),
        "event_ticker_count": len(events_by_ticker),
        "lookbacks": _overlap_summary(trades, events_by_ticker),
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


def _write_report(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Form 4 Accepted Trade Overlap",
        "",
        f"- experiment_id: `{summary['experiment_id']}`",
        f"- generated_at: `{summary['generated_at']}`",
        f"- production_impact: `{summary['production_impact']['production_impact']}`",
        f"- event_flag: `{summary['event_flag']}`",
        f"- trades: `{summary['trade_count']}`",
        "",
        "| Lookback | Matched trades | Matched avg PnL | Matched win rate | Unmatched avg PnL | Unmatched win rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lookback, row in summary["lookbacks"].items():
        with_prior = row["with_prior_form4"]
        without_prior = row["without_prior_form4"]
        lines.append(
            f"| {lookback}d | {with_prior['trade_count']} | {_fmt(with_prior['avg_pnl_pct_net'])}% | "
            f"{_fmt(with_prior['win_rate'])} | {_fmt(without_prior['avg_pnl_pct_net'])}% | "
            f"{_fmt(without_prior['win_rate'])} |"
        )
    lines.extend([
        "",
        "## Read",
        "",
        "This measures whether prior meaningful Form 4 event-days overlap with already",
        "accepted trades. It does not test skipped candidates or alter entry logic.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Join Form 4 meaningful purchase event-days to accepted trades.")
    parser.add_argument("--events", default=str(DEFAULT_EVENTS))
    parser.add_argument("--trades", default=str(DEFAULT_TRADES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run(args)
    compact = {
        "trade_count": summary["trade_count"],
        "lookbacks": {
            lookback: {
                "matched_trades": row["with_prior_form4"]["trade_count"],
                "matched_avg_pnl_pct_net": row["with_prior_form4"]["avg_pnl_pct_net"],
                "unmatched_avg_pnl_pct_net": row["without_prior_form4"]["avg_pnl_pct_net"],
            }
            for lookback, row in summary["lookbacks"].items()
        },
        "output": _repo_rel(args.output),
        "report": _repo_rel(args.report),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
