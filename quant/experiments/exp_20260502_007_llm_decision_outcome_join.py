"""Read-only LLM decision to backtest outcome join manifest.

This helper does not change strategy behavior. It joins the narrow
production-aligned LLM ranking samples to accepted-stack replay trades so a
future LLM/event ranking test can distinguish scored candidates from missing
outcomes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260502-007"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"
DEFAULT_BASELINE = Path("data/backtest_results_20260430.json")
DEFAULT_COVERAGE_AUDIT = Path(
    "data/experiments/exp-20260501-014/"
    "exp_20260501_014_llm_replay_attribution_coverage.json"
)
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260502-007/"
    "exp_20260502_007_llm_decision_outcome_join.json"
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def ymd_to_iso(value: str) -> str:
    return datetime.strptime(value, "%Y%m%d").date().isoformat()


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def advice_body(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    parsed = raw.get("advice_parsed")
    if isinstance(parsed, dict):
        return parsed
    return raw


def approved_ticker(raw: Any) -> str | None:
    new_trade = advice_body(raw).get("new_trade")
    if isinstance(new_trade, dict):
        ticker = new_trade.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return ticker.strip().upper()
    return None


def candidate_rows(decision_log: dict[str, Any]) -> list[dict[str, Any]]:
    details = decision_log.get("signal_details")
    if isinstance(details, list):
        rows = [row for row in details if isinstance(row, dict)]
    else:
        rows = []
    if rows:
        return rows

    tickers = decision_log.get("signals_presented")
    if not isinstance(tickers, list):
        return []
    out: list[dict[str, Any]] = []
    for ticker in tickers:
        if isinstance(ticker, str) and ticker.strip():
            out.append({"ticker": ticker.strip().upper()})
    return out


def trade_index(trades: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        by_ticker.setdefault(ticker, []).append(trade)
    return by_ticker


def join_trade(
    ticker: str,
    decision_iso: str,
    by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision_day = parse_iso_date(decision_iso)
    matches = []
    for trade in by_ticker.get(ticker, []):
        entry_day = parse_iso_date(trade.get("entry_date"))
        exit_day = parse_iso_date(trade.get("exit_date"))
        if not decision_day or not entry_day:
            continue
        if entry_day == decision_day:
            match_type = "entry_same_day"
        elif exit_day and entry_day <= decision_day <= exit_day:
            match_type = "active_on_decision_day"
        elif entry_day > decision_day:
            match_type = "future_replay_entry"
        else:
            continue
        matches.append(
            {
                "match_type": match_type,
                "trade_key": trade.get("trade_key"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "pnl": trade.get("pnl"),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "exit_reason": trade.get("exit_reason"),
            }
        )
    priority = {"entry_same_day": 0, "active_on_decision_day": 1, "future_replay_entry": 2}
    matches.sort(key=lambda row: priority.get(str(row.get("match_type")), 99))
    if not matches:
        return {"outcome_status": "unscored_no_replay_trade", "trade_match": None}
    return {"outcome_status": "scored_from_replay_trade", "trade_match": matches[0]}


def metric_subset(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "win_rate",
        "total_trades",
        "survival_rate",
    ]
    out = {key: result.get(key) for key in keys if key in result}
    if "total_trades" not in out and "total_trades" not in result:
        out["trade_count"] = result.get("total_trades") or result.get("trade_count") or len(result.get("trades", []))
    return out


def build_manifest(
    start: str,
    end: str,
    data_dir: Path,
    baseline_path: Path,
    coverage_audit_path: Path,
) -> dict[str, Any]:
    baseline = load_json(baseline_path)
    coverage = load_json(coverage_audit_path) if coverage_audit_path.exists() else {}
    effective_dates = (
        coverage.get("date_sets", {}).get("effective_attribution_dates")
        if isinstance(coverage, dict)
        else None
    )
    if not isinstance(effective_dates, list):
        effective_dates = []

    by_ticker = trade_index(baseline.get("trades") or [])
    rows: list[dict[str, Any]] = []
    summary = Counter()
    approved_scored_pnl = 0.0
    non_approved_scored_pnl = 0.0

    for ymd in sorted(str(item) for item in effective_dates):
        decision_path = data_dir / f"llm_decision_log_{ymd}.json"
        response_path = data_dir / f"llm_prompt_resp_{ymd}.json"
        if not decision_path.exists() or not response_path.exists():
            continue
        decision = load_json(decision_path)
        response = load_json(response_path)
        approved = approved_ticker(response)
        decision_iso = ymd_to_iso(ymd)

        for candidate in candidate_rows(decision):
            ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").strip().upper()
            if not ticker:
                continue
            is_approved = ticker == approved
            joined = join_trade(ticker, decision_iso, by_ticker)
            status = joined["outcome_status"]
            role = "approved" if is_approved else "not_approved"
            summary[f"{role}_candidates"] += 1
            summary[f"{role}_{status}"] += 1
            trade_match = joined["trade_match"]
            if isinstance(trade_match, dict) and isinstance(trade_match.get("pnl"), (int, float)):
                if is_approved:
                    approved_scored_pnl += float(trade_match["pnl"])
                else:
                    non_approved_scored_pnl += float(trade_match["pnl"])

            rows.append(
                {
                    "date": decision_iso,
                    "ticker": ticker,
                    "approved_by_llm": is_approved,
                    "approved_ticker": approved,
                    "strategy": candidate.get("strategy"),
                    "trade_quality_score": candidate.get("trade_quality_score"),
                    "risk_reward_ratio": candidate.get("risk_reward_ratio"),
                    "entry_price": candidate.get("entry_price"),
                    "stop_price": candidate.get("stop_price"),
                    "target_price": candidate.get("target_price"),
                    **joined,
                }
            )

    total_candidates = len(rows)
    scored = summary["approved_scored_from_replay_trade"] + summary["not_approved_scored_from_replay_trade"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "LLM decision-to-backtest outcome join manifest",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start, "end": end},
        "baseline_result_file": str(baseline_path),
        "coverage_audit_file": str(coverage_audit_path),
        "alpha_hypothesis_blocked": (
            "LLM/event soft ranking could rank existing candidates before scarce-slot "
            "allocation, but only if approved and non-approved prompt-time candidates "
            "can be attributed to replay outcomes or explicitly marked unscored."
        ),
        "strategy_behavior_changed": False,
        "baseline_metrics": metric_subset(baseline),
        "summary": {
            "effective_dates_loaded": len(set(row["date"] for row in rows)),
            "candidate_rows": total_candidates,
            "scored_candidate_rows": scored,
            "scored_candidate_fraction": round(scored / total_candidates, 4) if total_candidates else 0.0,
            "approved_candidates": summary["approved_candidates"],
            "approved_scored_from_replay_trade": summary["approved_scored_from_replay_trade"],
            "approved_unscored_no_replay_trade": summary["approved_unscored_no_replay_trade"],
            "not_approved_candidates": summary["not_approved_candidates"],
            "not_approved_scored_from_replay_trade": summary["not_approved_scored_from_replay_trade"],
            "not_approved_unscored_no_replay_trade": summary["not_approved_unscored_no_replay_trade"],
            "approved_scored_pnl": round(approved_scored_pnl, 2),
            "not_approved_scored_pnl": round(non_approved_scored_pnl, 2),
        },
        "readiness_verdict": {
            "status": "partially_repaired_still_blocked",
            "reason": (
                "The manifest now separates scored from unscored LLM candidates, but "
                "the current effective replay sample has too few scored candidate "
                "outcomes for a reliable soft-ranking alpha judgement."
            ),
            "next_alpha_test_less_blocked": (
                "A default-off LLM/event ranking backtest can now consume this manifest "
                "as the audit source for candidate outcome availability instead of "
                "treating all prompt-time candidates as equally scored."
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--coverage-audit", default=str(DEFAULT_COVERAGE_AUDIT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    manifest = build_manifest(
        start=args.start,
        end=args.end,
        data_dir=Path(args.data_dir),
        baseline_path=Path(args.baseline),
        coverage_audit_path=Path(args.coverage_audit),
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "output": str(output),
                "summary": manifest["summary"],
                "readiness_verdict": manifest["readiness_verdict"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
