"""exp-20260507-030: META/NFLX entry timing oracle overlap audit.

Observed-only oracle bridge. exp-20260507-028 found promising META/NFLX daily
entry-state surfaces, especially pre-earnings 0-7 days, but those rows are not
the same as the live candidate stream. This audit joins the timing surface back
to persisted entry_candidate_events and asks whether the top timing states have
enough real candidate overlap for a replay.

No production path, oracle_diagnostics module, signal generation, ranking,
sizing, exits, universe, LLM/news, or orders are changed.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260507-030"
SOURCE_EXPERIMENT_ID = "exp-20260507-028"
STEM = "meta_nflx_entry_timing_oracle_overlap"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEED_TICKERS = ("META", "NFLX")
PEER_TICKERS = ("GOOG", "AMZN", "SPOT", "DIS", "APP")
PLATFORM_TICKERS = SEED_TICKERS + PEER_TICKERS
TOP_TIMING_TAGS = (
    "pre_earnings_0_7",
    "pre_earnings_46_plus",
    "gap_up_3pct",
    "post_earnings_drift_1_10",
)
FORWARD_HORIZONS = (5, 10, 20, 40)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_late_strong.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_old_thin.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

_EARNINGS_CACHE: dict[str, dict[str, Any]] = {}


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {snapshot_path}")
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean = [row for row in rows if isinstance(row, dict) and row.get("Date")]
        out[str(ticker).upper()] = sorted(clean, key=lambda row: str(row["Date"]))
    return out


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _idx_for_date(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    target = str(date_str)[:10]
    for idx, row in enumerate(rows):
        if _date_value(row) == target:
            return idx
    return None


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _open(row: dict[str, Any]) -> float | None:
    return _float(row.get("Open"))


def _high(row: dict[str, Any]) -> float | None:
    return _float(row.get("High"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low"))


def _earnings_payload(date_str: str) -> dict[str, Any]:
    key = str(date_str)[:10].replace("-", "")
    if key not in _EARNINGS_CACHE:
        path = REPO_ROOT / "data" / f"earnings_snapshot_{key}.json"
        if not path.exists():
            _EARNINGS_CACHE[key] = {}
        else:
            payload = _load_json(path)
            earnings = payload.get("earnings") if isinstance(payload, dict) else {}
            _EARNINGS_CACHE[key] = earnings if isinstance(earnings, dict) else {}
    return _EARNINGS_CACHE[key]


def _dte_for(ticker: str, date_str: str) -> int | None:
    row = _earnings_payload(date_str).get(ticker.upper())
    if not isinstance(row, dict):
        return None
    try:
        return int(row.get("days_to_earnings"))
    except (TypeError, ValueError):
        return None


def _days_since_earnings(ticker: str, rows: list[dict[str, Any]], idx: int) -> int | None:
    last_idx = None
    prev_dte = None
    for i in range(0, idx + 1):
        dte = _dte_for(ticker, _date_value(rows[i]))
        if dte == 0:
            last_idx = i
        elif prev_dte is not None and prev_dte <= 1 and dte is not None and dte >= 20:
            last_idx = i
        prev_dte = dte
    return idx - last_idx if last_idx is not None else None


def _timing_tags(ticker: str, rows: list[dict[str, Any]], idx: int) -> dict[str, Any]:
    date_str = _date_value(rows[idx])
    dte = _dte_for(ticker, date_str)
    since = _days_since_earnings(ticker, rows, idx)
    opn = _open(rows[idx])
    prev_close = _close(rows[idx - 1]) if idx > 0 else None
    gap_pct = opn / prev_close - 1.0 if opn is not None and prev_close else None
    tags = []
    if dte is not None and 0 <= dte <= 7:
        tags.append("pre_earnings_0_7")
    if dte is not None and dte >= 46:
        tags.append("pre_earnings_46_plus")
    if gap_pct is not None and gap_pct >= 0.03:
        tags.append("gap_up_3pct")
    if since is not None and 1 <= since <= 10:
        tags.append("post_earnings_drift_1_10")
    return {
        "dte": dte,
        "days_since_earnings": since,
        "gap_pct": _round(gap_pct, 6),
        "tags": tags,
    }


def _forward_packet(rows: list[dict[str, Any]], idx: int) -> dict[str, Any]:
    entry_idx = idx + 1
    if entry_idx >= len(rows):
        return {"entry_status": "no_next_open"}
    entry_open = _open(rows[entry_idx])
    if entry_open is None or entry_open <= 0:
        return {"entry_status": "missing_next_open"}
    out: dict[str, Any] = {
        "entry_status": "ok",
        "entry_date": _date_value(rows[entry_idx]),
        "entry_open": _round(entry_open, 4),
    }
    for horizon in FORWARD_HORIZONS:
        end_idx = entry_idx + horizon
        if end_idx >= len(rows):
            out[f"return_{horizon}d"] = None
            out[f"mfe_{horizon}d"] = None
            out[f"mae_{horizon}d"] = None
            continue
        end_close = _close(rows[end_idx])
        highs = [_high(row) for row in rows[entry_idx : end_idx + 1]]
        lows = [_low(row) for row in rows[entry_idx : end_idx + 1]]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        out[f"return_{horizon}d"] = (
            end_close / entry_open - 1.0 if end_close is not None else None
        )
        out[f"mfe_{horizon}d"] = max(highs) / entry_open - 1.0 if highs else None
        out[f"mae_{horizon}d"] = min(lows) / entry_open - 1.0 if lows else None
    return out


def _trade_key(date_str: str, ticker: str, strategy: str) -> str:
    return f"{date_str}|{ticker.upper()}|{strategy}"


def _baseline_trade_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "")
        entry_date = str(trade.get("entry_date") or "")[:10]
        # Candidate date is not stored on trades. Entry is next open, so use the
        # previous matching candidate during row construction instead of here.
        out[f"{entry_date}|{ticker}|{strategy}"] = trade
    return out


def _event_row(
    event: dict[str, Any],
    rows: list[dict[str, Any]],
    baseline_by_entry: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    ticker = str(event.get("ticker") or "").upper()
    if ticker not in PLATFORM_TICKERS:
        return None
    idx = _idx_for_date(rows, event.get("date"))
    if idx is None:
        return None
    timing = _timing_tags(ticker, rows, idx)
    forward = _forward_packet(rows, idx)
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    fill_date = str(details.get("fill_date") or forward.get("entry_date") or "")[:10]
    strategy = str(event.get("strategy") or "")
    baseline_trade = baseline_by_entry.get(f"{fill_date}|{ticker}|{strategy}")
    return {
        "date": str(event.get("date"))[:10],
        "ticker": ticker,
        "cohort": "seed" if ticker in SEED_TICKERS else "peer",
        "strategy": strategy,
        "decision": event.get("decision"),
        "candidate_rank": event.get("candidate_rank"),
        "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
        "timing": timing,
        "forward": forward,
        "baseline_trade": {
            "matched": bool(baseline_trade),
            "entry_date": baseline_trade.get("entry_date") if baseline_trade else None,
            "exit_date": baseline_trade.get("exit_date") if baseline_trade else None,
            "exit_reason": baseline_trade.get("exit_reason") if baseline_trade else None,
            "pnl": _round(baseline_trade.get("pnl"), 2) if baseline_trade else None,
            "pnl_pct_net": _round(baseline_trade.get("pnl_pct_net"), 6)
            if baseline_trade
            else None,
        },
    }


def _stats(values: list[float | None]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "win_rate": None, "best": None, "worst": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": _round(sum(clean) / len(clean), 6),
        "median": _round(ordered[len(ordered) // 2], 6),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best": _round(max(clean), 6),
        "worst": _round(min(clean), 6),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups["all_platform"].append(row)
        groups[row["cohort"]].append(row)
        groups[f"ticker:{row['ticker']}"].append(row)
        for tag in row["timing"].get("tags") or []:
            groups[f"all_platform|{tag}"].append(row)
            groups[f"{row['cohort']}|{tag}"].append(row)
            groups[f"ticker:{row['ticker']}|{tag}"].append(row)

    out = {}
    for name, items in sorted(groups.items()):
        entered = [row for row in items if row.get("decision") == "entered"]
        pnl_values = [
            _float((row.get("baseline_trade") or {}).get("pnl"))
            for row in items
            if (row.get("baseline_trade") or {}).get("matched")
        ]
        out[name] = {
            "candidate_count": len(items),
            "entered_count": len(entered),
            "decision_counts": dict(sorted(Counter(row.get("decision") for row in items).items())),
            "baseline_entered_pnl": _round(sum(value for value in pnl_values if value is not None), 2),
            "return_20d": _stats([
                _float((row.get("forward") or {}).get("return_20d")) for row in items
            ]),
            "return_40d": _stats([
                _float((row.get("forward") or {}).get("return_40d")) for row in items
            ]),
            "mfe_20d": _stats([
                _float((row.get("forward") or {}).get("mfe_20d")) for row in items
            ]),
            "mae_20d": _stats([
                _float((row.get("forward") or {}).get("mae_20d")) for row in items
            ]),
        }
    return out


def _analyze_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    candidate_payload = _load_json(REPO_ROOT / spec["candidate_events"])
    result = _load_json(REPO_ROOT / spec["backtest_results"])
    baseline_by_entry = _baseline_trade_map(result)
    rows = []
    for event in candidate_payload.get("candidate_events") or []:
        ticker = str(event.get("ticker") or "").upper()
        ticker_rows = ohlcv.get(ticker)
        if not ticker_rows:
            continue
        row = _event_row(event, ticker_rows, baseline_by_entry)
        if row:
            row["window"] = name
            rows.append(row)
    return {
        "window": name,
        "window_spec": spec,
        "candidate_rows": rows,
        "summary": _summarize(rows),
        "candidate_artifact_validation": {
            "persisted_candidate_events": len(candidate_payload.get("candidate_events") or []),
            "entered_candidate_events": sum(
                1
                for event in candidate_payload.get("candidate_events") or []
                if event.get("decision") == "entered"
            ),
            "result_total_trades": result.get("total_trades"),
        },
    }


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for window in by_window.values():
        rows.extend(window["candidate_rows"])
    summary = _summarize(rows)
    tag_overlap = {
        tag: {
            "seed": summary.get(f"seed|{tag}", {"candidate_count": 0, "entered_count": 0}),
            "meta": summary.get(f"ticker:META|{tag}", {"candidate_count": 0, "entered_count": 0}),
            "nflx": summary.get(f"ticker:NFLX|{tag}", {"candidate_count": 0, "entered_count": 0}),
            "all_platform": summary.get(f"all_platform|{tag}", {"candidate_count": 0, "entered_count": 0}),
        }
        for tag in TOP_TIMING_TAGS
    }
    seed_candidates = summary.get("seed", {})
    pre_earnings_seed = tag_overlap["pre_earnings_0_7"]["seed"]
    candidate_replay_ready = (
        pre_earnings_seed.get("candidate_count", 0) >= 8
        and pre_earnings_seed.get("entered_count", 0) >= 3
    )
    if candidate_replay_ready:
        status = "ready_for_candidate_replay"
        next_action = "pre_register_seed_pre_earnings_entry_replay"
        reason = "Top timing tag has enough persisted seed-candidate overlap."
    else:
        status = "underpowered_oracle_overlap"
        next_action = "do_not_replay_yet_accumulate_oracle_feature"
        reason = (
            "The top daily timing tag has insufficient META/NFLX candidate overlap; "
            "treat it as an oracle feature to monitor, not a replayable strategy."
        )
    return {
        "candidate_count": len(rows),
        "summary": summary,
        "tag_overlap": tag_overlap,
        "decision_read": {
            "status": status,
            "next_action": next_action,
            "reason": reason,
            "seed_candidate_count": seed_candidates.get("candidate_count", 0),
            "seed_entered_count": seed_candidates.get("entered_count", 0),
            "pre_earnings_0_7_seed_candidate_count": pre_earnings_seed.get("candidate_count", 0),
            "pre_earnings_0_7_seed_entered_count": pre_earnings_seed.get("entered_count", 0),
        },
    }


def _compact_window_payload(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {
            "summary": window["summary"],
            "candidate_artifact_validation": window["candidate_artifact_validation"],
            "sample_seed_rows": [
                row for row in window["candidate_rows"] if row["cohort"] == "seed"
            ][:8],
        }
        for name, window in by_window.items()
    }


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "entry_oracle_overlap",
        "change_type": "observed_only_oracle_overlap_audit",
        "mechanism_family": "meta_nflx_platform_entry_timing",
        "single_causal_variable": "entry_timing_oracle_candidate_overlap",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "observed_metrics": payload["aggregate"],
        "gate4": {
            "passed": None,
            "basis": "Observed-only oracle overlap audit; no replay after-metrics.",
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news is outside this oracle-overlap audit.",
        },
        "next_action": payload["aggregate"]["decision_read"]["next_action"],
        "related_files": payload["related_files"],
    }


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    read = payload["aggregate"]["decision_read"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "META/NFLX entry timing oracle overlap",
        "decision": payload["decision"],
        "surface_status": read["status"],
        "next_action": read["next_action"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    read = payload["aggregate"]["decision_read"]
    overlap = payload["aggregate"]["tag_overlap"]
    lines = [
        f"# {EXPERIMENT_ID} META/NFLX Entry Timing Oracle Overlap",
        "",
        f"Decision: `{payload['decision']}`",
        f"Overlap status: `{read['status']}`",
        "",
        "## Read",
        "",
        read["reason"],
        "",
        "## Candidate Overlap",
        "",
        "| Tag | Seed candidates | Seed entered | META candidates | NFLX candidates | Platform candidates |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tag, item in overlap.items():
        seed = item["seed"]
        meta = item["meta"]
        nflx = item["nflx"]
        platform = item["all_platform"]
        lines.append(
            "| {tag} | {seed_c} | {seed_e} | {meta_c} | {nflx_c} | {platform_c} |".format(
                tag=tag,
                seed_c=seed.get("candidate_count", 0),
                seed_e=seed.get("entered_count", 0),
                meta_c=meta.get("candidate_count", 0),
                nflx_c=nflx.get("candidate_count", 0),
                platform_c=platform.get("candidate_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Oracle Implication",
            "",
            "- Existing oracle tooling already has candidate-forward and selection oracles, not only perfect exit.",
            "- What is missing is a reusable entry-state oracle layer that tags candidates with pre-entry lifecycle states.",
            "- `pre_earnings_0_7` is promising in daily surface data, but has zero META/NFLX candidate overlap here.",
            "- Do not replay or promote until candidate overlap or forward evidence exists.",
            "",
            "## Guardrails",
            "",
            "- No production path changed.",
            "- No oracle_diagnostics shared module changed in this experiment.",
            "- No entry, exit, ranking, sizing, universe, LLM/news, or order behavior changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict((name, _analyze_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    decision = "observed_only_underpowered"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "The META/NFLX entry timing surface can become an entry-state oracle "
            "only if its top tags overlap persisted real candidate events enough "
            "to support candidate-level replay."
        ),
        "source_experiment": SOURCE_EXPERIMENT_ID,
        "history_check": {
            "exp-20260507-028": "Found promising daily entry surfaces, especially seed pre_earnings_0_7.",
            "exp-20260507-008": "Rejected mechanical platform pullback timing.",
            "exp-20260507-014": "Rejected post-target platform runner exits.",
            "exp-20260507-027": "Rejected cap-aware platform sizing due immaterial and APP-concentrated lift.",
            "oracle_diagnostics": (
                "Already includes perfect_exit, candidate_forward, candidate_selection, "
                "and no_trade attribution oracles. Missing piece is state-conditioned entry tagging."
            ),
        },
        "parameters": {
            "seed_tickers": list(SEED_TICKERS),
            "peer_tickers": list(PEER_TICKERS),
            "top_timing_tags_from_exp028": list(TOP_TIMING_TAGS),
            "candidate_sources": [
                spec["candidate_events"] for spec in WINDOWS.values()
            ],
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "by_window": _compact_window_payload(by_window),
        "aggregate": aggregate,
        "decision": decision,
        "production_impact": {
            "shared_policy_changed": False,
            "oracle_diagnostics_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_exits": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }
    log_record = _log_record(payload)
    ticket = _ticket(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "decision_read": aggregate["decision_read"],
                "tag_overlap": aggregate["tag_overlap"],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
