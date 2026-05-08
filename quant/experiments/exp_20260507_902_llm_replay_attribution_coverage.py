"""Current LLM replay attribution coverage audit.

This experiment is read-only. It measures whether persisted LLM prompt/response
archives, decision logs, production quant signal snapshots, and the current
backtest result can support a future default-off LLM/event ranking alpha test.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260507-902"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"
DEFAULT_BASELINE = Path("data/backtest_results_20260507.json")
DEFAULT_PREVIOUS_MANIFEST = Path(
    "data/experiments/exp-20260506-027/"
    "exp_20260506_027_llm_event_replay_readiness_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260507-902/"
    "exp_20260507_902_llm_replay_attribution_coverage.json"
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception as exc:  # keep audit reproducible even with one bad file
        return {"_parse_error": str(exc)}


def date_token(path: Path) -> str | None:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def token_to_iso(token: str | None) -> str | None:
    if not token:
        return None
    return datetime.strptime(token, "%Y%m%d").date().isoformat()


def iso_to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def collect_dated_files(data_dir: Path, pattern: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(data_dir.glob(pattern)):
        token = date_token(path)
        if token:
            out[token] = path
    return out


def archive_context(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("archive_context"), dict):
        return payload["archive_context"]
    return {}


def count_context_signals(context: dict[str, Any]) -> int:
    value = context.get("signals_presented_count")
    if isinstance(value, int):
        return value
    signals = context.get("signals_presented")
    if isinstance(signals, list):
        return len(signals)
    return 0


def candidate_tickers_from_quant_signals(payload: Any) -> set[str]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("signals", "quant_signals", "candidates", "signal_details"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        else:
            rows = []
    else:
        rows = []
    tickers: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            ticker = row.get("ticker") or row.get("symbol")
        else:
            ticker = row
        if isinstance(ticker, str) and ticker.strip():
            tickers.add(ticker.strip().upper())
    return tickers


def candidate_tickers_from_decision_log(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    rows = payload.get("signal_details")
    tickers: set[str] = set()
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                ticker = row.get("ticker") or row.get("symbol")
                if isinstance(ticker, str) and ticker.strip():
                    tickers.add(ticker.strip().upper())
    presented = payload.get("signals_presented")
    if isinstance(presented, list):
        for row in presented:
            if isinstance(row, str) and row.strip():
                tickers.add(row.strip().upper())
            elif isinstance(row, dict):
                ticker = row.get("ticker") or row.get("symbol")
                if isinstance(ticker, str) and ticker.strip():
                    tickers.add(ticker.strip().upper())
    return tickers


def trade_index(trades: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").strip().upper()
        if ticker:
            by_ticker.setdefault(ticker, []).append(trade)
    return by_ticker


def find_trade_match(
    ticker: str,
    decision_iso: str,
    by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision_day = iso_to_date(decision_iso)
    if decision_day is None:
        return {"outcome_status": "unscored_bad_decision_date", "trade_match": None}
    matches: list[dict[str, Any]] = []
    for trade in by_ticker.get(ticker, []):
        entry_day = iso_to_date(trade.get("entry_date"))
        exit_day = iso_to_date(trade.get("exit_date"))
        if entry_day is None:
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


def approved_ticker_from_response(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    new_trade = payload.get("new_trade")
    if isinstance(new_trade, dict):
        ticker = new_trade.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            text = ticker.strip().upper()
            if text not in {"NO NEW TRADE", "NONE", "NO_TRADE", "N/A"}:
                return text
    return None


def metric_subset(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "total_return_pct",
        "win_rate",
        "total_trades",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]
    out = {key: result.get(key) for key in keys if key in result}
    if "trade_count" not in out and "total_trades" in out:
        out["trade_count"] = out["total_trades"]
    return out


def previous_summary(path: Path) -> dict[str, Any]:
    payload = maybe_load_json(path)
    if not isinstance(payload, dict):
        return {"exists": False, "file": str(path).replace("\\", "/")}
    summary = (payload.get("llm_replay_coverage") or {}).get("summary") or {}
    event_totals = (payload.get("event_forward_paper_readiness") or {}).get("totals") or {}
    return {
        "exists": True,
        "file": str(path).replace("\\", "/"),
        "generated_at": payload.get("generated_at") or payload.get("timestamp"),
        "primary_window_archive_days": summary.get("primary_window_archive_days"),
        "primary_window_days_with_archive_context": summary.get("primary_window_days_with_archive_context"),
        "primary_window_ranking_eligible_candidate_days": summary.get("primary_window_ranking_eligible_candidate_days"),
        "primary_window_signals_presented": summary.get("primary_window_signals_presented"),
        "all_archive_days": summary.get("all_archive_days"),
        "all_days_with_archive_context": summary.get("all_days_with_archive_context"),
        "all_ranking_eligible_candidate_days": summary.get("all_ranking_eligible_candidate_days"),
        "event_snapshot_rows": event_totals.get("snapshot_rows"),
        "event_closed_positions": event_totals.get("closed_positions"),
    }


def summarize_event_paper(data_dir: Path) -> dict[str, Any]:
    state_files = {
        "form4_meaningful_purchase": data_dir / "form4_event_sleeve_paper_state.json",
        "sec_negative_reaction": data_dir / "sec_negative_event_sleeve_paper_state.json",
        "sec_governance_procedural": data_dir / "sec_governance_event_sleeve_paper_state.json",
        "sec_leadership_change": data_dir / "sec_leadership_event_sleeve_paper_state.json",
    }
    totals = Counter()
    sources: dict[str, Any] = {}
    for source, path in state_files.items():
        payload = maybe_load_json(path)
        payload = payload if isinstance(payload, dict) else {}
        pending = payload.get("pending_entries") if isinstance(payload.get("pending_entries"), list) else []
        open_positions = payload.get("open_positions") if isinstance(payload.get("open_positions"), list) else []
        closed = payload.get("closed_positions") if isinstance(payload.get("closed_positions"), list) else []
        skipped = payload.get("skipped_entries") if isinstance(payload.get("skipped_entries"), list) else []
        snapshot_path = Path(str(path).replace("_state.json", "_snapshots.jsonl"))
        snapshot_rows = 0
        if snapshot_path.exists():
            snapshot_rows = sum(1 for line in snapshot_path.read_text(encoding="utf-8-sig").splitlines() if line.strip())
        totals["pending_entries"] += len(pending)
        totals["open_positions"] += len(open_positions)
        totals["closed_positions"] += len(closed)
        totals["skipped_entries"] += len(skipped)
        totals["snapshot_rows"] += snapshot_rows
        totals["sources_with_closed_outcomes"] += int(bool(closed))
        totals["sources_with_pending_or_open"] += int(bool(pending or open_positions))
        sources[source] = {
            "state_file": str(path).replace("\\", "/"),
            "exists": path.exists(),
            "updated_at": payload.get("updated_at"),
            "schema_version": payload.get("schema_version"),
            "pending_entries": len(pending),
            "open_positions": len(open_positions),
            "closed_positions": len(closed),
            "skipped_entries": len(skipped),
            "snapshot_file": str(snapshot_path).replace("\\", "/"),
            "snapshot_rows": snapshot_rows,
            "has_closed_replacement_value_sample": bool(closed),
        }
    return {
        "sources": sources,
        "totals": {
            "source_count": len(state_files),
            "pending_entries": totals["pending_entries"],
            "open_positions": totals["open_positions"],
            "closed_positions": totals["closed_positions"],
            "skipped_entries": totals["skipped_entries"],
            "snapshot_rows": totals["snapshot_rows"],
            "sources_with_closed_outcomes": totals["sources_with_closed_outcomes"],
            "sources_with_pending_or_open": totals["sources_with_pending_or_open"],
        },
    }


def build_manifest(
    data_dir: Path,
    baseline_path: Path,
    previous_manifest_path: Path,
    start: str,
    end: str,
) -> dict[str, Any]:
    baseline = load_json(baseline_path)
    prompt_resp_files = collect_dated_files(data_dir, "llm_prompt_resp_*.json")
    decision_logs = collect_dated_files(data_dir, "llm_decision_log_*.json")
    quant_signals = collect_dated_files(data_dir, "quant_signals_*.json")
    prompts = collect_dated_files(data_dir, "llm_prompt_*.txt")
    raw_outputs = collect_dated_files(data_dir, "llm_output_*.json")
    all_dates = sorted(set(prompt_resp_files) | set(decision_logs) | set(quant_signals))
    by_ticker = trade_index(baseline.get("trades") or [])

    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    totals = Counter()
    for token in all_dates:
        iso = token_to_iso(token)
        in_window = bool(iso and start <= iso <= end)
        response_payload = maybe_load_json(prompt_resp_files[token]) if token in prompt_resp_files else None
        decision_payload = maybe_load_json(decision_logs[token]) if token in decision_logs else None
        quant_payload = maybe_load_json(quant_signals[token]) if token in quant_signals else None
        context = archive_context(response_payload)
        signals_presented_count = count_context_signals(context)
        ranking_eligible = context.get("ranking_eligible") if context else None
        new_trade_locked = context.get("new_trade_locked") if context else None
        effective_candidate_day = bool(
            context and ranking_eligible is True and new_trade_locked is not True and signals_presented_count > 0
        )
        decision_tickers = candidate_tickers_from_decision_log(decision_payload)
        quant_tickers = candidate_tickers_from_quant_signals(quant_payload)
        overlap_tickers = sorted(decision_tickers & quant_tickers)
        approved_ticker = approved_ticker_from_response(response_payload)

        totals["days_with_any_llm_or_quant_artifact"] += 1
        totals["prompt_resp_days"] += int(token in prompt_resp_files)
        totals["decision_log_days"] += int(token in decision_logs)
        totals["quant_signals_days"] += int(token in quant_signals)
        totals["prompt_days"] += int(token in prompts)
        totals["raw_output_days"] += int(token in raw_outputs)
        totals["archive_context_days"] += int(bool(context))
        totals["ranking_eligible_days"] += int(ranking_eligible is True)
        totals["effective_candidate_days"] += int(effective_candidate_day)
        totals["signals_presented"] += signals_presented_count
        totals["production_quant_overlap_days"] += int(bool(overlap_tickers))
        if in_window:
            totals["primary_prompt_resp_days"] += int(token in prompt_resp_files)
            totals["primary_archive_context_days"] += int(bool(context))
            totals["primary_ranking_eligible_days"] += int(ranking_eligible is True)
            totals["primary_effective_candidate_days"] += int(effective_candidate_day)
            totals["primary_signals_presented"] += signals_presented_count

        for ticker in sorted(decision_tickers):
            joined = find_trade_match(ticker, iso or "", by_ticker)
            trade_match = joined["trade_match"]
            if isinstance(trade_match, dict):
                totals["candidate_rows_scored_from_replay_trade"] += 1
            candidate_rows.append(
                {
                    "date": iso,
                    "ticker": ticker,
                    "approved_by_llm": ticker == approved_ticker,
                    "in_primary_window": in_window,
                    "has_quant_signal_same_day": ticker in quant_tickers,
                    **joined,
                }
            )

        rows.append(
            {
                "date": iso,
                "in_primary_window": in_window,
                "has_prompt_resp": token in prompt_resp_files,
                "has_archive_context": bool(context),
                "has_decision_log": token in decision_logs,
                "has_quant_signals": token in quant_signals,
                "has_prompt_text": token in prompts,
                "has_raw_output": token in raw_outputs,
                "ranking_eligible": ranking_eligible,
                "new_trade_locked": new_trade_locked,
                "signals_presented_count": signals_presented_count,
                "effective_candidate_day": effective_candidate_day,
                "approved_ticker": approved_ticker,
                "decision_log_tickers": sorted(decision_tickers),
                "quant_signal_tickers": sorted(quant_tickers),
                "decision_quant_overlap_tickers": overlap_tickers,
            }
        )

    previous = previous_summary(previous_manifest_path)
    current_summary = {
        "all_archive_days": totals["prompt_resp_days"],
        "all_days_with_archive_context": totals["archive_context_days"],
        "all_ranking_eligible_candidate_days": totals["effective_candidate_days"],
        "all_signals_presented": totals["signals_presented"],
        "primary_window_archive_days": totals["primary_prompt_resp_days"],
        "primary_window_days_with_archive_context": totals["primary_archive_context_days"],
        "primary_window_ranking_eligible_candidate_days": totals["primary_effective_candidate_days"],
        "primary_window_signals_presented": totals["primary_signals_presented"],
        "production_quant_overlap_days": totals["production_quant_overlap_days"],
        "candidate_rows_from_decision_logs": len(candidate_rows),
        "candidate_rows_scored_from_current_backtest": totals["candidate_rows_scored_from_replay_trade"],
        "candidate_row_score_fraction": (
            round(totals["candidate_rows_scored_from_replay_trade"] / len(candidate_rows), 4)
            if candidate_rows
            else 0.0
        ),
        "ranking_ready_for_soft_alpha": totals["primary_effective_candidate_days"] >= 5,
    }
    coverage_delta = {}
    for key, value in current_summary.items():
        if isinstance(value, (int, float)) and isinstance(previous.get(key), (int, float)):
            coverage_delta[key] = value - previous[key]

    event_paper = summarize_event_paper(data_dir)
    blockers = []
    if not current_summary["ranking_ready_for_soft_alpha"]:
        blockers.append(
            "LLM soft-ranking remains blocked: fewer than 5 production-aligned ranking-eligible candidate days exist in the primary replay window."
        )
    if current_summary["candidate_rows_scored_from_current_backtest"] == 0:
        blockers.append(
            "LLM candidate outcome attribution remains blocked against the current checkpoint: no decision-log candidates join to current backtest trades."
        )
    if event_paper["totals"]["closed_positions"] == 0:
        blockers.append(
            "Event/LLM grading promotion remains blocked by zero closed default-off paper outcomes with replacement value."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "LLM replay attribution coverage",
        "date_range": {"start": start, "end": end},
        "baseline_result_file": str(baseline_path).replace("\\", "/"),
        "baseline_metrics": metric_subset(baseline),
        "after_metrics": metric_subset(baseline),
        "expected_value_score_delta": 0.0,
        "alpha_hypothesis_blocked": (
            "A future default-off LLM/event ranking alpha could grade same-day A/B candidates, "
            "but only when prompt-time LLM candidate sets can be joined to replay or forward outcomes."
        ),
        "why_not_alpha_now": blockers,
        "historical_constraints": {
            "related_measurement_experiments": [
                "exp-20260427-007 archive_context helper",
                "exp-20260427-009 legacy archive_context backfill audit",
                "exp-20260502-007 LLM decision outcome join",
                "exp-20260506-027 LLM/event replay readiness manifest",
            ],
            "why_this_is_not_a_repeat": (
                "This run compares the latest available files to the previous manifest, adds a current checkpoint "
                "decision-log-to-trade join score fraction, and leaves all strategy behavior unchanged."
            ),
        },
        "llm_replay_coverage": {
            "source_files": {
                "prompt_resp_days": totals["prompt_resp_days"],
                "decision_log_days": totals["decision_log_days"],
                "quant_signals_days": totals["quant_signals_days"],
                "prompt_days": totals["prompt_days"],
                "raw_output_days": totals["raw_output_days"],
                "latest_prompt_resp_date": token_to_iso(max(prompt_resp_files) if prompt_resp_files else None),
                "latest_decision_log_date": token_to_iso(max(decision_logs) if decision_logs else None),
                "latest_quant_signals_date": token_to_iso(max(quant_signals) if quant_signals else None),
            },
            "summary": current_summary,
            "previous_summary": previous,
            "coverage_delta_vs_previous_manifest": coverage_delta,
            "date_rows": rows,
            "candidate_outcome_rows": candidate_rows,
        },
        "event_forward_paper_readiness": event_paper,
        "readiness_verdict": {
            "status": "blocked_but_audited",
            "blockers": blockers,
            "minimum_next_step": (
                "Keep persisting archive_context in llm_prompt_resp files and close default-off paper outcomes; "
                "rerun only after candidate rows can join to replay/forward outcomes."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "strategy_behavior_changed": False,
            "production_impact": "read_only_measurement_artifact_no_strategy_behavior_change",
        },
        "gate4": {
            "applicable": False,
            "reason": "Observed-only measurement artifact; no entries, exits, ranking, sizing, thresholds, orders, or strategy files changed.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--previous-manifest", default=str(DEFAULT_PREVIOUS_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()

    manifest = build_manifest(
        data_dir=Path(args.data_dir),
        baseline_path=Path(args.baseline),
        previous_manifest_path=Path(args.previous_manifest),
        start=args.start,
        end=args.end,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "output": str(output).replace("\\", "/"),
                "baseline_metrics": manifest["baseline_metrics"],
                "llm_source_files": manifest["llm_replay_coverage"]["source_files"],
                "llm_summary": manifest["llm_replay_coverage"]["summary"],
                "coverage_delta_vs_previous_manifest": manifest["llm_replay_coverage"][
                    "coverage_delta_vs_previous_manifest"
                ],
                "event_totals": manifest["event_forward_paper_readiness"]["totals"],
                "readiness_verdict": manifest["readiness_verdict"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
