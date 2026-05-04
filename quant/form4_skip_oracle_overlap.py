from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
ORACLE_DIR = DATA_DIR / "experiments" / "oracle_standard_3window_20260501_220042"
DEFAULT_EVENTS = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
DEFAULT_OUTPUT = DATA_DIR / "non_ohlcv" / "form4_entry_skip_oracle_overlap_20241002_20260421.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "form4_entry_skip_oracle_overlap_20260503.md"
LOOKBACK_DAYS = (20, 60, 90, 120)
WINDOW_FILES = {
    "old_thin": ORACLE_DIR / "old_thin_entry_skip_oracle.json",
    "mid_weak": ORACLE_DIR / "mid_weak_entry_skip_oracle.json",
    "late_strong": ORACLE_DIR / "late_strong_entry_skip_oracle.json",
}


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


def _load_top_skipped_rows(window_files: dict[str, Path]) -> list[dict[str, Any]]:
    rows = []
    for window, path in window_files.items():
        payload = _load_json(path)
        oracle = payload.get("entry_skip_oracle", {})
        for row in oracle.get("top_skipped_opportunities") or []:
            if not isinstance(row, dict):
                continue
            rows.append({
                **row,
                "window": window,
                "source_path": _repo_rel(path),
            })
    return sorted(rows, key=lambda row: (row.get("date") or "", row.get("ticker") or ""))


def matching_prior_events(
    events_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    candidate_date: str,
    lookback_days: int,
) -> list[dict[str, Any]]:
    matches = []
    for event in events_by_ticker.get(str(ticker).upper(), []):
        event_date = event.get("usable_trade_date")
        if not event_date or event_date > candidate_date:
            continue
        age_days = _days_between(event_date, candidate_date)
        if 0 <= age_days <= lookback_days:
            matches.append({**event, "days_before_candidate": age_days})
    return matches


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 6)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 6)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(row["max_forward_return_pct"]) * 100.0 for row in rows if row.get("max_forward_return_pct") is not None]
    return {
        "candidate_count": len(rows),
        "avg_max_forward_return_pct": _avg(returns),
        "median_max_forward_return_pct": _median(returns),
        "positive_fraction": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
        "by_window": _count_by(rows, "window"),
        "by_decision": _count_by(rows, "decision"),
        "tickers": sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}),
    }


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "UNKNOWN")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _overlap_summary(skipped_rows: list[dict[str, Any]], events_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lookback in LOOKBACK_DAYS:
        matched = []
        unmatched = []
        examples = []
        for row in skipped_rows:
            prior = matching_prior_events(events_by_ticker, str(row.get("ticker") or ""), str(row.get("date") or ""), lookback)
            if not prior:
                unmatched.append(row)
                continue
            best = max(prior, key=lambda event: float(event.get("total_purchase_value") or 0.0))
            enriched = {
                **row,
                "form4_match_count": len(prior),
                "best_form4_event": best,
            }
            matched.append(enriched)
            examples.append({
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "decision": row.get("decision"),
                "candidate_date": row.get("date"),
                "entry_date": row.get("entry_date"),
                "max_forward_return_pct": row.get("max_forward_return_pct"),
                "best_form4_date": best.get("usable_trade_date"),
                "days_before_candidate": best.get("days_before_candidate"),
                "best_form4_purchase_value": best.get("total_purchase_value"),
                "best_form4_owner_count": best.get("owner_count"),
                "best_form4_owner_names": best.get("sample_owner_names"),
            })
        examples.sort(key=lambda item: item.get("max_forward_return_pct") or 0.0, reverse=True)
        out[str(lookback)] = {
            "matched": _summarize(matched),
            "unmatched": _summarize(unmatched),
            "examples": examples[:20],
        }
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    events_payload = _load_json(Path(args.events))
    events_by_ticker = _event_index(events_payload)
    skipped_rows = _load_top_skipped_rows(WINDOW_FILES)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment_id": "exp-20260503-049",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_impact": "shadow_oracle_overlap_analysis_only",
        },
        "events_input": _repo_rel(args.events),
        "oracle_inputs": {window: _repo_rel(path) for window, path in WINDOW_FILES.items()},
        "event_flag": "meaningful_purchase_v1",
        "candidate_scope": "top_skipped_opportunities from entry_skip_oracle, 15 per window",
        "top_skipped_candidate_count": len(skipped_rows),
        "top_skipped_summary": _summarize(skipped_rows),
        "lookbacks": _overlap_summary(skipped_rows, events_by_ticker),
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
        "# Form 4 Entry-Skip Oracle Overlap",
        "",
        f"- experiment_id: `{summary['experiment_id']}`",
        f"- generated_at: `{summary['generated_at']}`",
        f"- production_impact: `{summary['production_impact']['production_impact']}`",
        f"- candidate_scope: `{summary['candidate_scope']}`",
        f"- top skipped candidates: `{summary['top_skipped_candidate_count']}`",
        "",
        "| Lookback | Matched candidates | Matched avg max forward | Unmatched avg max forward | Matched tickers |",
        "|---|---:|---:|---:|---|",
    ]
    for lookback, row in summary["lookbacks"].items():
        matched = row["matched"]
        unmatched = row["unmatched"]
        tickers = ", ".join(matched["tickers"]) if matched["tickers"] else "none"
        lines.append(
            f"| {lookback}d | {matched['candidate_count']} | {_fmt(matched['avg_max_forward_return_pct'])}% | "
            f"{_fmt(unmatched['avg_max_forward_return_pct'])}% | {tickers} |"
        )
    lines.extend([
        "",
        "## Read",
        "",
        "This is an oracle triage join over the saved top skipped opportunities.",
        "It uses future upper-bound returns from the oracle diagnostic, so it is not",
        "a tradable rule. A sparse overlap means Form 4 is not currently explaining",
        "most known high-value skipped opportunities.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Join meaningful Form 4 event-days to entry-skip oracle opportunities.")
    parser.add_argument("--events", default=str(DEFAULT_EVENTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run(args)
    compact = {
        "top_skipped_candidate_count": summary["top_skipped_candidate_count"],
        "lookbacks": {
            lookback: {
                "matched_candidates": row["matched"]["candidate_count"],
                "matched_avg_max_forward_return_pct": row["matched"]["avg_max_forward_return_pct"],
                "unmatched_avg_max_forward_return_pct": row["unmatched"]["avg_max_forward_return_pct"],
                "matched_tickers": row["matched"]["tickers"],
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
