"""Round-1 free-source earnings + SEC + surprise exploration."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from event_shocks import build_event_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-20260503-002"
OUT_DIR = os.path.join(REPO_ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(OUT_DIR, "earnings_sec_surprise_round1.json")
LOG_JSON = os.path.join(REPO_ROOT, "docs", "experiments", "logs", f"{EXPERIMENT_ID}.json")
TICKET_JSON = os.path.join(REPO_ROOT, "docs", "experiments", "tickets", f"{EXPERIMENT_ID}.json")

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
FORWARD_DAYS = (5, 10, 20)
MIN_CONFIRM_RETURN = 0.02
MIN_CONFIRM_RS = 0.0


def _load_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_snapshot(path: str) -> dict:
    raw = _load_json(os.path.join(REPO_ROOT, path))
    return raw.get("ohlcv", raw)


def _series(snapshot: dict, ticker: str) -> list[dict]:
    rows = snapshot.get(ticker) or []
    return sorted(rows, key=lambda row: str(row.get("Date") or row.get("date")))


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _close(row: dict) -> float | None:
    value = row.get("Close")
    return float(value) if isinstance(value, (int, float)) else None


def _row_index(rows: list[dict]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _trading_dates(snapshot: dict) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY")]


def _run_baseline(universe: list[str], cfg: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    ).run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
    }


def _forward_return(rows: list[dict], start_idx: int, horizon: int) -> float | None:
    end_idx = start_idx + horizon
    if end_idx >= len(rows):
        return None
    start_close = _close(rows[start_idx])
    end_close = _close(rows[end_idx])
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _summarize(values: list[float]) -> dict:
    clean = [value for value in values if isinstance(value, (int, float))]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
        }
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def _baseline_entries(result: dict) -> dict[str, list[dict]]:
    by_date = defaultdict(list)
    for trade in result.get("trades", []):
        if trade.get("strategy") in {"trend_long", "breakout_long"}:
            by_date[str(trade.get("entry_date"))[:10]].append(trade)
    return by_date


def _trade_pnl_summary(trades: list[dict]) -> dict:
    returns = [
        float(trade.get("pnl_pct_net"))
        for trade in trades
        if isinstance(trade.get("pnl_pct_net"), (int, float))
    ]
    pnls = [
        float(trade.get("pnl"))
        for trade in trades
        if isinstance(trade.get("pnl"), (int, float))
    ]
    return {
        "trade_count": len(trades),
        "avg_pnl_pct_net": round(mean(returns), 6) if returns else None,
        "median_pnl_pct_net": round(median(returns), 6) if returns else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
        "total_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
    }


def _quality_cohort(event: dict) -> str:
    flags = event.get("quality_flags") or {}
    if flags.get("warning"):
        return "quality_warning"
    if flags.get("positive"):
        return "quality_positive"
    return "unclassified"


def _context_bucket(events: list[dict]) -> str:
    if any(event.get("event_type") in {"8k", "10q", "10k"} for event in events):
        if any(event.get("surprise_direction") == "negative" for event in events):
            return "negative_guidance_or_filing"
        if any(event.get("surprise_direction") == "positive" for event in events):
            return "positive_guidance_or_filing"
        return "neutral_filing_context"
    if any((event.get("attributes") or {}).get("guidance_signal") == "cut" for event in events):
        return "negative_guidance_or_filing"
    if any((event.get("attributes") or {}).get("guidance_signal") == "raise" for event in events):
        return "positive_guidance_or_filing"
    if events:
        return "neutral_event_context"
    return "no_event_context"


def _window_env(universe: list[str], cfg: dict) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    spy_rows = _series(snapshot, "SPY")
    baseline = _run_baseline(universe, cfg)
    return {
        "snapshot": snapshot,
        "spy_rows": spy_rows,
        "spy_index": _row_index(spy_rows),
        "baseline": baseline,
        "entries_by_date": _baseline_entries(baseline),
        "trading_dates": [
            date for date in _trading_dates(snapshot)
            if cfg["start"] <= date <= cfg["end"]
        ],
    }


def _window_cache_builder(universe: list[str]):
    @lru_cache(maxsize=None)
    def _cached(date_key: str):
        return build_event_snapshot(
            date_key,
            data_dir=os.path.join(REPO_ROOT, "data"),
            universe=universe,
            persist=False,
        )
    return _cached


def _hypothesis_a(window_label: str, cfg: dict, env: dict, get_event_snapshot) -> dict:
    snapshot = env["snapshot"]
    spy_rows = env["spy_rows"]
    spy_index = env["spy_index"]
    entries_by_date = env["entries_by_date"]
    candidates = []
    event_days = 0
    for date in env["trading_dates"]:
        payload = get_event_snapshot(date.replace("-", ""))
        if payload["coverage"]["event_rows_total"] == 0:
            continue
        event_days += 1
        for ticker, events in payload["events_by_ticker"].items():
            earnings_events = [
                event for event in events
                if event.get("event_type") == "earnings"
                and event.get("surprise_direction") == "positive"
            ]
            if not earnings_events:
                continue
            rows = _series(snapshot, ticker)
            idx_by_date = _row_index(rows)
            event_idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if event_idx is None or spy_idx is None or event_idx + 1 >= len(rows) or spy_idx + 1 >= len(spy_rows):
                continue
            event_close = _close(rows[event_idx])
            confirm_close = _close(rows[event_idx + 1])
            spy_event_close = _close(spy_rows[spy_idx])
            spy_confirm_close = _close(spy_rows[spy_idx + 1])
            if not event_close or confirm_close is None or not spy_event_close or spy_confirm_close is None:
                continue
            ticker_ret = (confirm_close / event_close) - 1.0
            spy_ret = (spy_confirm_close / spy_event_close) - 1.0
            rs_vs_spy = ticker_ret - spy_ret
            if ticker_ret < MIN_CONFIRM_RETURN or rs_vs_spy <= MIN_CONFIRM_RS:
                continue
            confirm_date = _date(rows[event_idx + 1])
            same_day_entries = entries_by_date.get(confirm_date, [])
            main_event = earnings_events[0]
            candidate = {
                "ticker": ticker,
                "event_date": date,
                "candidate_date": confirm_date,
                "event_subtype": main_event.get("event_subtype"),
                "surprise_strength": main_event.get("surprise_strength"),
                "guidance_signal": (main_event.get("attributes") or {}).get("guidance_signal"),
                "sue_proxy": (main_event.get("attributes") or {}).get("sue_proxy"),
                "quality_positive_flags": (main_event.get("quality_flags") or {}).get("positive"),
                "quality_warning_flags": (main_event.get("quality_flags") or {}).get("warning"),
                "ticker_next_day_return": round(ticker_ret, 6),
                "spy_next_day_return": round(spy_ret, 6),
                "rs_vs_spy": round(rs_vs_spy, 6),
                "same_day_ab_entry_count": len(same_day_entries),
                "same_day_ab_overlap": bool(same_day_entries),
                "same_ticker_ab_overlap": any(trade.get("ticker") == ticker for trade in same_day_entries),
            }
            for horizon in FORWARD_DAYS:
                fwd = _forward_return(rows, event_idx + 1, horizon)
                candidate[f"fwd_{horizon}d"] = round(fwd, 6) if isinstance(fwd, float) else None
            candidates.append(candidate)

    forward_summary = {
        f"fwd_{horizon}d": _summarize([
            row[f"fwd_{horizon}d"] for row in candidates
            if isinstance(row.get(f"fwd_{horizon}d"), (int, float))
        ])
        for horizon in FORWARD_DAYS
    }
    overlap_count = sum(1 for row in candidates if row["same_day_ab_overlap"])
    return {
        "window": window_label,
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "baseline_metrics": _metrics(env["baseline"]),
        "event_days_seen": event_days,
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "same_day_ab_overlap_count": overlap_count,
        "same_day_ab_overlap_rate": round(overlap_count / len(candidates), 4) if candidates else None,
        "same_ticker_ab_overlap_count": sum(1 for row in candidates if row["same_ticker_ab_overlap"]),
        "scarce_slot_proxy": {
            "candidate_days": len({row["candidate_date"] for row in candidates}),
            "candidate_days_with_ab_entries": len({row["candidate_date"] for row in candidates if row["same_day_ab_overlap"]}),
            "avg_ab_entries_on_candidate_day": (
                round(mean([row["same_day_ab_entry_count"] for row in candidates]), 4)
                if candidates else None
            ),
        },
        "forward_return_distribution": forward_summary,
        "candidates": candidates,
        "sample_candidates": candidates[:30],
    }


def _hypothesis_b(window_label: str, cfg: dict, env: dict, get_event_snapshot) -> dict:
    trading_dates = env["trading_dates"]
    trade_rows = []
    for trade in env["baseline"].get("trades", []):
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry_date = str(trade.get("entry_date"))[:10]
        if entry_date not in trading_dates:
            continue
        idx = trading_dates.index(entry_date)
        context_dates = [entry_date]
        if idx > 0:
            context_dates.append(trading_dates[idx - 1])
        matched_events = []
        for ctx_date in context_dates:
            payload = get_event_snapshot(ctx_date.replace("-", ""))
            matched_events.extend(payload["events_by_ticker"].get(str(trade.get("ticker")), []))
        bucket = _context_bucket(matched_events)
        trade_rows.append({
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "entry_date": entry_date,
            "pnl": round(float(trade.get("pnl") or 0.0), 2),
            "pnl_pct_net": float(trade.get("pnl_pct_net") or 0.0),
            "context_bucket": bucket,
            "matched_event_types": sorted({event.get("event_type") for event in matched_events}),
            "matched_event_subtypes": sorted({event.get("event_subtype") for event in matched_events}),
        })

    by_bucket = {}
    for bucket in [
        "positive_guidance_or_filing",
        "negative_guidance_or_filing",
        "neutral_filing_context",
        "neutral_event_context",
        "no_event_context",
    ]:
        bucket_rows = [row for row in trade_rows if row["context_bucket"] == bucket]
        by_bucket[bucket] = _trade_pnl_summary(bucket_rows)
    sec_backed = [
        row for row in trade_rows
        if any(kind in {"8k", "10q", "10k"} for kind in row["matched_event_types"])
    ]
    return {
        "window": window_label,
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "baseline_metrics": _metrics(env["baseline"]),
        "trade_count": len(trade_rows),
        "sec_backed_trade_count": len(sec_backed),
        "context_bucket_counts": dict(Counter(row["context_bucket"] for row in trade_rows)),
        "by_context_bucket": by_bucket,
        "coverage_blocked": len(sec_backed) == 0,
        "sample_trade_rows": trade_rows[:30],
    }


def _hypothesis_c(window_label: str, cfg: dict, env: dict, get_event_snapshot) -> dict:
    snapshot = env["snapshot"]
    spy_rows = env["spy_rows"]
    spy_index = env["spy_index"]
    entries_by_date = env["entries_by_date"]
    cohort_rows = defaultdict(list)
    for date in env["trading_dates"]:
        payload = get_event_snapshot(date.replace("-", ""))
        for ticker, events in payload["events_by_ticker"].items():
            earnings_events = [
                event for event in events
                if event.get("event_type") == "earnings"
                and event.get("surprise_direction") in {"positive", "mixed"}
            ]
            if not earnings_events:
                continue
            rows = _series(snapshot, ticker)
            idx_by_date = _row_index(rows)
            event_idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if event_idx is None or spy_idx is None or event_idx + 1 >= len(rows) or spy_idx + 1 >= len(spy_rows):
                continue
            event_close = _close(rows[event_idx])
            confirm_close = _close(rows[event_idx + 1])
            spy_event_close = _close(spy_rows[spy_idx])
            spy_confirm_close = _close(spy_rows[spy_idx + 1])
            if not event_close or confirm_close is None or not spy_event_close or spy_confirm_close is None:
                continue
            ticker_ret = (confirm_close / event_close) - 1.0
            spy_ret = (spy_confirm_close / spy_event_close) - 1.0
            rs_vs_spy = ticker_ret - spy_ret
            main_event = earnings_events[0]
            cohort = _quality_cohort(main_event)
            row = {
                "ticker": ticker,
                "event_date": date,
                "candidate_date": _date(rows[event_idx + 1]),
                "cohort": cohort,
                "event_subtype": main_event.get("event_subtype"),
                "surprise_strength": main_event.get("surprise_strength"),
                "same_day_ab_overlap": bool(entries_by_date.get(_date(rows[event_idx + 1]), [])),
                "quality_positive_flags": (main_event.get("quality_flags") or {}).get("positive"),
                "quality_warning_flags": (main_event.get("quality_flags") or {}).get("warning"),
                "next_day_return": round(ticker_ret, 6),
                "next_day_rs_vs_spy": round(rs_vs_spy, 6),
            }
            for horizon in FORWARD_DAYS:
                fwd = _forward_return(rows, event_idx + 1, horizon)
                row[f"fwd_{horizon}d"] = round(fwd, 6) if isinstance(fwd, float) else None
            cohort_rows[cohort].append(row)

    cohort_summary = {}
    for cohort, rows in cohort_rows.items():
        cohort_summary[cohort] = {
            "count": len(rows),
            "same_day_ab_overlap_rate": (
                round(sum(1 for row in rows if row["same_day_ab_overlap"]) / len(rows), 4)
                if rows else None
            ),
            "fwd_5d": _summarize([row["fwd_5d"] for row in rows if isinstance(row.get("fwd_5d"), (int, float))]),
            "fwd_10d": _summarize([row["fwd_10d"] for row in rows if isinstance(row.get("fwd_10d"), (int, float))]),
            "fwd_20d": _summarize([row["fwd_20d"] for row in rows if isinstance(row.get("fwd_20d"), (int, float))]),
        }
    return {
        "window": window_label,
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "baseline_metrics": _metrics(env["baseline"]),
        "cohort_counts": {key: len(value) for key, value in cohort_rows.items()},
        "cohort_summary": cohort_summary,
        "sample_rows": [row for rows in cohort_rows.values() for row in rows[:10]],
    }


def _aggregate_hypothesis_a(results: OrderedDict) -> dict:
    total_candidates = sum(rec["candidate_count"] for rec in results.values())
    overlap = sum(rec["same_day_ab_overlap_count"] for rec in results.values())
    windows_positive = 0
    for rec in results.values():
        avg_10d = rec["forward_return_distribution"]["fwd_10d"]["avg"]
        if isinstance(avg_10d, (int, float)) and avg_10d > 0:
            windows_positive += 1
    decision = (
        "replay_candidate"
        if total_candidates >= 5 and windows_positive >= 2 and (overlap / total_candidates if total_candidates else 1.0) <= 0.5
        else "observed_only"
    )
    return {
        "candidate_count": total_candidates,
        "same_day_ab_overlap_count": overlap,
        "same_day_ab_overlap_rate": round(overlap / total_candidates, 4) if total_candidates else None,
        "windows_with_positive_fwd10_avg": windows_positive,
        "decision": decision,
    }


def _aggregate_hypothesis_b(results: OrderedDict) -> dict:
    sec_backed = sum(rec["sec_backed_trade_count"] for rec in results.values())
    decision = "coverage_blocked" if sec_backed == 0 else "observed_only"
    return {
        "trade_count": sum(rec["trade_count"] for rec in results.values()),
        "sec_backed_trade_count": sec_backed,
        "decision": decision,
    }


def _aggregate_hypothesis_c(results: OrderedDict) -> dict:
    counts = Counter()
    for rec in results.values():
        counts.update(rec["cohort_counts"])
    populated = sum(1 for value in counts.values() if value >= 3)
    return {
        "cohort_counts": dict(counts),
        "decision": "observed_only" if populated >= 2 else "coverage_blocked",
    }


def main() -> int:
    universe = get_universe()
    get_event_snapshot = _window_cache_builder(universe)
    window_env = OrderedDict((label, _window_env(universe, cfg)) for label, cfg in WINDOWS.items())

    hypothesis_a = OrderedDict()
    hypothesis_b = OrderedDict()
    hypothesis_c = OrderedDict()
    for label, cfg in WINDOWS.items():
        env = window_env[label]
        hypothesis_a[label] = _hypothesis_a(label, cfg, env, get_event_snapshot)
        hypothesis_b[label] = _hypothesis_b(label, cfg, env, get_event_snapshot)
        hypothesis_c[label] = _hypothesis_c(label, cfg, env, get_event_snapshot)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "observed_only",
        "lane": "alpha_discovery",
        "change_type": "earnings_sec_surprise_shadow_round1",
        "hypothesis": "Free-source earnings + SEC event shocks may yield replayable continuation and quality-ranking candidates before paying for analyst revisions.",
        "alpha_hypothesis_category": "event_driven_alpha_discovery",
        "why_not_llm_soft_ranking": "This round expands point-in-time event features without depending on thin production-aligned LLM outcome joins.",
        "parameters": {
            "single_causal_variable": "structured replayable event-shock schema plus three shadow evaluations",
            "locked_variables": [
                "production signal_engine",
                "portfolio sizing rules",
                "entry filters",
                "candidate ordering",
                "add-ons",
                "exits",
                "LLM/news replay switches",
            ],
            "confirm_next_day_return_min": MIN_CONFIRM_RETURN,
            "confirm_rs_vs_spy_min": MIN_CONFIRM_RS,
            "forward_horizons": list(FORWARD_DAYS),
            "free_source_only": True,
            "paid_analyst_revision_data_used": False,
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "schema": {
            "event_fields": [
                "event_date",
                "event_type",
                "event_subtype",
                "surprise_direction",
                "surprise_strength",
                "source_confidence",
                "point_in_time_complete",
                "field_availability",
                "attributes",
            ],
            "notes": [
                "Revenue/margin/FCF/inventory/receivables are headline-proxy fields in round 1, not XBRL-complete truth.",
                "SEC filing support is schema-ready but may remain coverage-blocked until raw SEC items map to tickers.",
            ],
        },
        "hypotheses": {
            "post_earnings_confirmed_drift": {
                "window_results": hypothesis_a,
                "aggregate_summary": _aggregate_hypothesis_a(hypothesis_a),
            },
            "guidance_and_filing_severity_filter": {
                "window_results": hypothesis_b,
                "aggregate_summary": _aggregate_hypothesis_b(hypothesis_b),
            },
            "quality_of_surprise_discriminator": {
                "window_results": hypothesis_c,
                "aggregate_summary": _aggregate_hypothesis_c(hypothesis_c),
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": True,
        },
        "decision": "observed_only",
        "rejection_reason": None,
        "next_action": "Do not promote any branch yet. First improve earnings/news archive density and SEC-to-ticker mapping, then rerun the same round-1 schema before attempting second-round replay.",
        "related_files": [
            "quant/event_shocks.py",
            "quant/backfill_event_shocks.py",
            "quant/experiments/exp_20260503_002_earnings_sec_surprise_round1.py",
            "data/experiments/exp-20260503-002/earnings_sec_surprise_round1.json",
        ],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_JSON), exist_ok=True)
    os.makedirs(os.path.dirname(TICKET_JSON), exist_ok=True)
    for path in (OUT_JSON, LOG_JSON):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Round-1 earnings + SEC surprise exploration",
        "summary": payload["hypothesis"],
        "best_variant": payload["hypotheses"]["post_earnings_confirmed_drift"]["aggregate_summary"]["decision"],
        "best_variant_gate4": False,
        "delta_metrics": {
            "post_earnings_confirmed_drift": payload["hypotheses"]["post_earnings_confirmed_drift"]["aggregate_summary"],
            "guidance_and_filing_severity_filter": payload["hypotheses"]["guidance_and_filing_severity_filter"]["aggregate_summary"],
            "quality_of_surprise_discriminator": payload["hypotheses"]["quality_of_surprise_discriminator"]["aggregate_summary"],
        },
        "next_action": payload["next_action"],
    }
    with open(TICKET_JSON, "w", encoding="utf-8") as handle:
        json.dump(ticket, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "post_earnings_confirmed_drift": payload["hypotheses"]["post_earnings_confirmed_drift"]["aggregate_summary"],
        "guidance_and_filing_severity_filter": payload["hypotheses"]["guidance_and_filing_severity_filter"]["aggregate_summary"],
        "quality_of_surprise_discriminator": payload["hypotheses"]["quality_of_surprise_discriminator"]["aggregate_summary"],
    }, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
