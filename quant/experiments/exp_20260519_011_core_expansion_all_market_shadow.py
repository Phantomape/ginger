"""exp-20260519-011: core expansion all-market coverage shadow.

Alpha-search scout for the user's broad core-expansion idea. The true US
all-market experiment is data-limited in this repository, so this script keeps
production behavior unchanged and does two things:

1. audit how much of the current "all-market" / governed observation universe
   has replayable OHLCV coverage; and
2. replay the current accepted core stack with the history-covered non-core
   governed equities that are already present in cached augmented snapshots.

Single causal variable family: candidate universe membership. Signal rules,
entry filters, ranking, sizing, exits, heat, slots, LLM/news, and live orders
remain locked.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260512_106_signal_day_sector_tape_risk as base
import risk_engine


EXPERIMENT_ID = "exp-20260519-011"
STEM = "exp_20260519_011_core_expansion_all_market_shadow"
SOURCE_HISTORY_EXPERIMENT_ID = "exp-20260501-008"
CORE_BASELINE_EXPERIMENT_ID = "exp-20260517-009"

OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = (
    base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
DOC_ARTIFACT = (
    base.REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_core_expansion_all_market_shadow.md"
)
EXPERIMENT_LOG_JSONL = base.REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "canonical_snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "augmented_snapshot": (
                    "data/experiments/exp-20260501-008/"
                    "ohlcv_aug_20251023_20260421.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "canonical_snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "augmented_snapshot": (
                    "data/experiments/exp-20260501-008/"
                    "ohlcv_aug_20250423_20251022.json"
                ),
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "canonical_snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "augmented_snapshot": (
                    "data/experiments/exp-20260501-008/"
                    "ohlcv_aug_20241002_20250422.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

# Production-visible sector tags reused from prior AI-infra universe scouts.
# These tags are metadata needed to exercise the existing shared stack; they are
# not tuned in this experiment.
CANDIDATE_SECTOR_MAP = {
    "APLD": "Technology",
    "BE": "Energy",
    "CIFR": "Financials",
    "CORZ": "Financials",
    "DBRG": "Real Estate",
    "INTC": "Technology",
    "IREN": "Financials",
    "LITE": "Technology",
    "MARA": "Financials",
    "RIOT": "Financials",
    "SNDK": "Technology",
    "TLN": "Energy",
    "VST": "Energy",
    "WULF": "Financials",
}

MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_TRADE_COUNT_SUM = 58
MIN_CANDIDATE_TRADE_COUNT = 3
MIN_CANDIDATE_WINDOW_COUNT = 2
MIN_EV_IMPROVED_WINDOWS = 2
INCLUDE_SINGLE_TICKER_VARIANTS = False

_EARNINGS_CALENDAR_CACHE: dict[tuple[str, ...], dict[str, Any]] = {}

ACCEPTED_CORE_BASELINE = {
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "trade_count": 18,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78110.11,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39667.96,
        "trade_count": 22,
        "survival_rate": 0.8667,
    },
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(base.REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot_tickers(path: Path) -> set[str]:
    payload = _load_json(path)
    ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
    return {str(ticker).upper() for ticker in (ohlcv or {})}


def _load_universe_state() -> dict[str, Any]:
    candidates = [
        base.REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260518.json",
        base.REPO_ROOT / "data" / "state" / "universe" / "universe_registry.json",
        base.REPO_ROOT / "data" / "universe_registry.json",
    ]
    for path in candidates:
        if path.exists():
            payload = _load_json(path)
            records = payload.get("records") or payload.get("tickers") or {}
            return {
                "path": _repo_rel(path),
                "payload": payload,
                "records": records,
            }
    return {"path": None, "payload": {}, "records": {}}


def _sec_reference_summary() -> dict[str, Any]:
    path = base.REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
    if not path.exists():
        return {"path": _repo_rel(path), "present": False, "ticker_count": 0}
    payload = _load_json(path)
    rows = payload.values() if isinstance(payload, dict) else payload
    tickers = {
        str(row.get("ticker") or row.get("symbol") or "").upper()
        for row in rows
        if isinstance(row, dict) and (row.get("ticker") or row.get("symbol"))
    }
    return {
        "path": _repo_rel(path),
        "present": True,
        "ticker_count": len(tickers),
        "sample": sorted(tickers)[:25],
    }


def _coverage_audit(core_universe: set[str]) -> dict[str, Any]:
    universe_state = _load_universe_state()
    records = {
        str(ticker).upper(): row
        for ticker, row in (universe_state.get("records") or {}).items()
        if isinstance(row, dict)
    }
    registry_tickers = set(records)
    payload = universe_state.get("payload") or {}
    observation_universe = {
        str(ticker).upper()
        for ticker in payload.get("observation_universe", [])
        if ticker
    } or registry_tickers
    pilot_trade_universe = {
        str(ticker).upper()
        for ticker in payload.get("pilot_trade_universe", [])
        if ticker
    }

    canonical_sets = {
        label: _snapshot_tickers(base.REPO_ROOT / spec["canonical_snapshot"])
        for label, spec in WINDOWS.items()
    }
    augmented_sets = {
        label: _snapshot_tickers(base.REPO_ROOT / spec["augmented_snapshot"])
        for label, spec in WINDOWS.items()
    }
    canonical_all = set.intersection(*canonical_sets.values())
    canonical_union = set.union(*canonical_sets.values())
    augmented_all = set.intersection(*augmented_sets.values())
    augmented_union = set.union(*augmented_sets.values())

    governed_noncore = registry_tickers - core_universe
    covered_candidates = sorted(
        ticker
        for ticker in governed_noncore
        if ticker in CANDIDATE_SECTOR_MAP and ticker in augmented_all
    )
    missing_observation_history = sorted(
        ticker
        for ticker in observation_universe - core_universe
        if ticker not in augmented_union
    )
    canonical_some = sorted(governed_noncore & canonical_union)

    return {
        "universe_state_path": universe_state["path"],
        "core_universe_size": len(core_universe),
        "registry_record_count": len(registry_tickers),
        "observation_universe_count": len(observation_universe),
        "pilot_trade_universe_count": len(pilot_trade_universe),
        "sec_reference": _sec_reference_summary(),
        "canonical_snapshot_ticker_counts": {
            label: len(tickers) for label, tickers in canonical_sets.items()
        },
        "canonical_all_window_ticker_count": len(canonical_all),
        "canonical_registry_noncore_all_window_covered": sorted(
            governed_noncore & canonical_all
        ),
        "canonical_registry_noncore_some_window_covered": canonical_some,
        "augmented_snapshot_source": SOURCE_HISTORY_EXPERIMENT_ID,
        "augmented_snapshot_ticker_counts": {
            label: len(tickers) for label, tickers in augmented_sets.items()
        },
        "augmented_registry_noncore_all_window_covered": covered_candidates,
        "augmented_registry_noncore_missing_history": missing_observation_history,
        "pilot_trade_history_covered": sorted(pilot_trade_universe & set(covered_candidates)),
        "history_coverage_boundary": (
            "This is not a true all-US point-in-time constituent replay. The "
            "repository has SEC reference tickers but no broad historical OHLCV "
            "archive for them. The executable scout is restricted to current "
            "governed non-core equities with cached all-window augmented OHLCV."
        ),
        "records": records,
        "pilot_trade_universe": sorted(pilot_trade_universe),
    }


def _run_window(label: str, universe: list[str]) -> dict[str, Any]:
    spec = WINDOWS[label]

    def _archived_earnings_calendar(tickers: tuple[str, ...]) -> dict[str, Any]:
        if tickers in _EARNINGS_CALENDAR_CACHE:
            return _EARNINGS_CALENDAR_CACHE[tickers]

        calendar: dict[str, set[Any]] = {ticker: set() for ticker in tickers}
        root = base.REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"
        for path in sorted(root.glob("earnings_snapshot_*.json")):
            try:
                payload = _load_json(path)
            except Exception:
                continue
            date_key = str(payload.get("date") or path.stem.replace("earnings_snapshot_", ""))
            try:
                asof = pd.Timestamp(date_key).date()
            except Exception:
                continue
            earnings = payload.get("earnings") if isinstance(payload, dict) else {}
            if not isinstance(earnings, dict):
                continue
            for ticker in tickers:
                row = earnings.get(ticker)
                if not isinstance(row, dict):
                    continue
                dte = row.get("days_to_earnings")
                if dte is None:
                    continue
                try:
                    days = int(dte)
                    event_date = (pd.Timestamp(asof) + pd.offsets.BDay(days)).date()
                except Exception:
                    continue
                if event_date > asof:
                    calendar[ticker].add(event_date)

        result = {ticker: sorted(dates) for ticker, dates in calendar.items()}
        _EARNINGS_CALENDAR_CACHE[tickers] = result
        return result

    def _cached_download_earnings_calendar(engine: base.BacktestEngine) -> dict[str, Any]:
        key = tuple(sorted(str(ticker).upper() for ticker in engine._backtest_data_universe()))
        return _archived_earnings_calendar(key)

    original_calendar = base.BacktestEngine._download_earnings_calendar
    base.BacktestEngine._download_earnings_calendar = _cached_download_earnings_calendar
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        try:
            engine = base.BacktestEngine(
                universe,
                start=spec["start"],
                end=spec["end"],
                config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
                ohlcv_snapshot_path=str(base.REPO_ROOT / spec["augmented_snapshot"]),
                include_entry_candidate_events=True,
            )
            result = engine.run()
        finally:
            base.BacktestEngine._download_earnings_calendar = original_calendar
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "entry_execution_attribution": result.get("entry_execution_attribution"),
    }


def _candidate_trade_summary(
    trades: list[dict[str, Any]],
    added: set[str],
) -> dict[str, Any]:
    rows = []
    by_ticker: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in added:
            continue
        pnl = float(trade.get("pnl") or 0.0)
        row = {
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": round(pnl, 2),
            "pnl_pct_net": base._round(trade.get("pnl_pct_net")),
            "shares": trade.get("shares"),
            "sizing_multipliers": trade.get("sizing_multipliers") or {},
        }
        rows.append(row)
        rec = by_ticker.setdefault(
            ticker,
            {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0},
        )
        rec["trades"] += 1
        rec["wins"] += 1 if pnl > 0 else 0
        rec["losses"] += 1 if pnl <= 0 else 0
        rec["pnl"] += pnl

    for rec in by_ticker.values():
        trades_n = int(rec["trades"])
        rec["pnl"] = round(float(rec["pnl"]), 2)
        rec["win_rate"] = round(rec["wins"] / trades_n, 4) if trades_n else None
    return {
        "candidate_trade_count": len(rows),
        "candidate_pnl": round(sum(float(row["pnl"]) for row in rows), 2),
        "by_ticker": dict(sorted(by_ticker.items())),
        "sample_trades": rows[:25],
    }


def _compact_changed_trades(changed: dict[str, Any]) -> dict[str, Any]:
    return {
        "added_count": changed.get("added_count", 0),
        "removed_count": changed.get("removed_count", 0),
        "common_pnl_changed_count": changed.get("common_pnl_changed_count", 0),
        "sample_added_keys": (changed.get("added_keys") or [])[:15],
        "sample_removed_keys": (changed.get("removed_keys") or [])[:15],
        "sample_common_pnl_changed": (changed.get("common_pnl_changed") or [])[:10],
    }


def _variant_definitions(
    candidates: list[str],
    coverage: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    records = coverage.get("records") or {}
    pilot_set = set(coverage.get("pilot_trade_universe") or [])
    variants: OrderedDict[str, list[str]] = OrderedDict()
    variants["add_all_history_covered_governed"] = list(candidates)
    pilot = [ticker for ticker in candidates if ticker in pilot_set]
    if pilot:
        variants["add_current_pilot_history_covered"] = pilot

    by_segment: dict[str, list[str]] = defaultdict(list)
    for ticker in candidates:
        row = records.get(ticker) or {}
        segment = row.get("theme_segment") or row.get("theme") or "ungrouped"
        by_segment[str(segment)].append(ticker)
    for segment, tickers in sorted(by_segment.items()):
        if len(tickers) >= 2:
            name = "segment_" + "".join(
                ch.lower() if ch.isalnum() else "_"
                for ch in segment
            ).strip("_")
            variants[name] = sorted(tickers)

    if INCLUDE_SINGLE_TICKER_VARIANTS:
        for ticker in candidates:
            variants[f"add_{ticker.lower()}"] = [ticker]
    return OrderedDict((name, sorted(set(tickers))) for name, tickers in variants.items() if tickers)


def _baseline_alignment(before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_window = {}
    passed = True
    for label, expected in ACCEPTED_CORE_BASELINE.items():
        actual = before_metrics.get(label) or {}
        diffs = {
            key: base._round((actual.get(key) or 0.0) - value)
            for key, value in expected.items()
        }
        checks = {
            "expected_value_score": abs(diffs["expected_value_score"]) <= 0.0001,
            "total_pnl": abs(diffs["total_pnl"]) <= 0.05,
            "trade_count": diffs["trade_count"] == 0,
            "survival_rate": abs(diffs["survival_rate"]) <= 0.0001,
        }
        by_window[label] = {
            "expected": expected,
            "actual": {key: actual.get(key) for key in expected},
            "diffs": diffs,
            "checks": checks,
            "passed": all(checks.values()),
        }
        passed = passed and by_window[label]["passed"]
    return {
        "accepted_core_baseline_experiment_id": CORE_BASELINE_EXPERIMENT_ID,
        "passed": passed,
        "by_window": by_window,
    }


def _variant_payload(
    name: str,
    added: list[str],
    baseline_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    universe = sorted(set(base.get_universe()) | set(added))
    after_runs = {label: _run_window(label, universe) for label in WINDOWS}

    before_metrics = {label: baseline_runs[label]["metrics"] for label in WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in WINDOWS}
    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    added_set = set(added)
    candidate_trades = {
        label: _candidate_trade_summary(after_runs[label]["trades"], added_set)
        for label in WINDOWS
    }
    candidate_trade_count = sum(
        row["candidate_trade_count"] for row in candidate_trades.values()
    )
    candidate_window_count = sum(
        1 for row in candidate_trades.values() if row["candidate_trade_count"] > 0
    )
    changed_trades = {
        label: _compact_changed_trades(
            base._changed_trades(
                baseline_runs[label]["trades"],
                after_runs[label]["trades"],
            )
        )
        for label in WINDOWS
    }
    passed = bool(
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= MIN_EV_IMPROVED_WINDOWS
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and aggregate_after["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and candidate_trade_count >= MIN_CANDIDATE_TRADE_COUNT
        and candidate_window_count >= MIN_CANDIDATE_WINDOW_COUNT
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )

    return {
        "variant": name,
        "added": added,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "candidate_trade_count": candidate_trade_count,
            "candidate_window_count": candidate_window_count,
            "min_candidate_trade_count": MIN_CANDIDATE_TRADE_COUNT,
            "min_candidate_window_count": MIN_CANDIDATE_WINDOW_COUNT,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "trade_count_sum_after": aggregate_after["trade_count_sum"],
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "survival_rate_min_after": aggregate_after["survival_rate_min"],
        },
        "candidate_trades": candidate_trades,
        "changed_trades": changed_trades,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _variant_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in variants:
        rows.append(
            {
                "variant": row["variant"],
                "added": row["added"],
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "candidate_trade_count": row["gate4"]["candidate_trade_count"],
                "candidate_window_count": row["gate4"]["candidate_window_count"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "survival_rate_min_after": row["gate4"]["survival_rate_min_after"],
            }
        )
    return rows


def _select_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not variants:
        return None
    return max(
        variants,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["expected_value_score_delta"],
            row["total_pnl_delta"],
            row["gate4"]["candidate_trade_count"],
            -len(row["gate4"]["regressed_windows"]),
        ),
    )


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Variant | Gate | Added | dEV | dPnL | Improved | Regressed | Candidate trades | Windows | Max DD worse |",
        "|---|:---:|---|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["variant_summary"]:
        rows.append(
            "| {variant} | {gate} | {added} | {ev:+.4f} | ${pnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {dd:+.4f} |".format(
                variant=row["variant"],
                gate="PASS" if row["passed"] else "FAIL",
                added=", ".join(row["added"]),
                ev=float(row["expected_value_score_delta"] or 0.0),
                pnl=float(row["total_pnl_delta"] or 0.0),
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                trades=row["candidate_trade_count"],
                windows=row["candidate_window_count"],
                dd=float(row["max_drawdown_worse"] or 0.0),
            )
        )
    selected = payload.get("selected_variant") or {}
    coverage = payload["coverage_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Expansion All-Market Shadow",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable family: candidate universe membership. No shared policy, sizing, ranking, exit, LLM/news, or live-order path changed.",
            "",
            "## Coverage Boundary",
            "",
            f"- SEC reference tickers: `{coverage['sec_reference']['ticker_count']}`.",
            f"- Canonical all-window non-core governed equities: `{len(coverage['canonical_registry_noncore_all_window_covered'])}`.",
            f"- Augmented all-window non-core governed equities tested: `{len(coverage['augmented_registry_noncore_all_window_covered'])}`.",
            f"- Missing current observation-universe history: `{len(coverage['augmented_registry_noncore_missing_history'])}`.",
            f"- Gate 1 accepted-baseline alignment: `{payload['gate1']['passed']}`.",
            "",
            "## Variant Scout",
            "",
            *rows,
            "",
            f"Selected variant: `{selected.get('variant')}`.",
            "",
            "Production impact: replay-only shadow. Promotion would require a default-off forward paper sleeve or a separate shared universe policy experiment.",
        ]
    )


def build_payload() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    core_universe = set(base.get_universe())
    coverage = _coverage_audit(core_universe)
    candidates = coverage["augmented_registry_noncore_all_window_covered"]
    variant_defs = _variant_definitions(candidates, coverage)

    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(CANDIDATE_SECTOR_MAP)
    try:
        baseline_runs = {
            label: _run_window(label, sorted(core_universe))
            for label in WINDOWS
        }
        before_metrics = {label: baseline_runs[label]["metrics"] for label in WINDOWS}
        baseline_alignment = _baseline_alignment(before_metrics)
        variants = [
            _variant_payload(name, added, baseline_runs)
            for name, added in variant_defs.items()
        ]
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    selected = _select_variant(variants)
    accepted = [row for row in variants if row["passed"]]
    decision = (
        "promising_default_off_core_expansion_candidate_found"
        if accepted
        else "rejected_available_history_core_expansion_shadow"
    )
    interpretation = (
        "At least one history-covered governed non-core candidate-pool variant cleared the replay scout gate. Treat it as a default-off paper/universe-governance lead, not an immediate core promotion."
        if accepted
        else "No tested history-covered governed non-core candidate-pool variant cleared the three-window replacement-value gate. True all-market expansion remains blocked by missing broad PIT OHLCV history."
    )
    variant_summary = _variant_summary(variants)
    selected_summary = selected or {
        "variant": None,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "gate4": {"passed": False},
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "observed_only" if accepted else "rejected",
        "decision": decision,
        "hypothesis": (
            "The current event-enhanced trend/breakout system may have better "
            "replacement value if core candidates are expanded beyond the current "
            "watchlist, but broad admission should be proved first as a default-off "
            "candidate-pool shadow using replayable history-covered equities."
        ),
        "change_type": "candidate_pool_shadow",
        "changed_variable": "core_expansion_candidate_universe_membership",
        "single_causal_variable": (
            "candidate universe membership from history-covered governed non-core equities"
        ),
        "parameters": {
            "source_history_experiment_id": SOURCE_HISTORY_EXPERIMENT_ID,
            "candidate_sector_map": CANDIDATE_SECTOR_MAP,
            "tested_candidates": candidates,
            "tested_variants": variant_defs,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk enrichment",
                "position sizing",
                "all sizing multipliers",
                "stops and targets",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "event sleeves",
                "pilot sleeve live behavior",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE_GUARDRAIL,
                "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
                "min_candidate_trade_count": MIN_CANDIDATE_TRADE_COUNT,
                "min_candidate_window_count": MIN_CANDIDATE_WINDOW_COUNT,
                "min_survival_rate": 0.05,
            },
            "anti_js": "No JavaScript was used.",
            "earnings_calendar_replay_source": (
                "derived from data/daily/snapshots/earnings days_to_earnings; "
                "no live yfinance calendar calls"
            ),
            "single_ticker_variants_included": INCLUDE_SINGLE_TICKER_VARIANTS,
            "variant_scope_note": (
                "First pass runs source-level all/pilot/segment candidate-pool "
                "variants. Single-ticker sweeps are intentionally deferred to a "
                "follow-up on tickers that actually trade in this pass."
            ),
        },
        "historical_experiment_check": {
            "nearby_prior_results": {
                "exp-20260430-027": "Curated snapshot extras mostly added ETF/commodity noise or one-window exposure.",
                "exp-20260501-008": "AI power/infra broad expansion was rejected/deferred on older stack; this run retests the history-covered governed subset on the current accepted core stack.",
                "exp-20260501-015": "INTC/LITE clean optical/storage subset was not stable enough for production promotion.",
                "exp-20260515-017": "Single ETF/proxy additions did not beat core; ETFs are not retested here.",
            },
            "why_this_is_not_duplicate": (
                "The current baseline is exp-20260517-009 and the current governed "
                "observation universe is audited first. This run also separates "
                "data coverage from replayable candidate-pool value."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool: some non-core governed US equities may fit the "
                "current trend/breakout engine better than incumbent marginal slots"
            ),
            "2_history_check": (
                "Broad ETF/universe expansion and raw AI-infra watchlist promotion "
                "were previously rejected; this run uses latest accepted stack and "
                "requires replacement-value evidence before any forward sleeve"
            ),
            "3_single_causal_variable": (
                "candidate universe membership; all strategy rules and sizing constants stay fixed"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows where replayable; aggregate "
                "EV/PnL positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, trade_count_sum >= 58, candidate trades "
                ">= 3 across >= 2 windows, and max DD worse <= 0.5pp"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260519_011_core_expansion_all_market_shadow.py"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md fixed windows, using cached augmented OHLCV "
                "only for non-core candidate coverage from exp-20260501-008"
            ),
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "coverage_audit": {
            key: value
            for key, value in coverage.items()
            if key not in {"records", "pilot_trade_universe"}
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": base._aggregate(before_metrics),
            "baseline_alignment": baseline_alignment,
            "passed": baseline_alignment["passed"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "cached augmented OHLCV snapshot ohlcv[ticker]",
                "risk_engine.SECTOR_MAP candidate classification",
                "shared signal/risk/sizing fields",
            ],
            "candidate_history_coverage": {
                ticker: {
                    label: ticker
                    in _snapshot_tickers(base.REPO_ROOT / spec["augmented_snapshot"])
                    for label, spec in WINDOWS.items()
                }
                for ticker in candidates
            },
            "passed": gate2["passed"] and bool(candidates),
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_expansion": True,
            "minimum_after_survival_rate": min(
                (
                    row["delta_metrics"]["aggregate_after"]["survival_rate_min"]
                    for row in variants
                ),
                default=None,
            ),
            "passed": all(
                row["delta_metrics"]["aggregate_after"]["survival_rate_min"] >= 0.05
                for row in variants
            )
            if variants
            else False,
        },
        "gate4": {
            "passed": bool(accepted),
            "accepted_variants": [row["variant"] for row in accepted],
            "selected_variant": selected_summary.get("variant"),
            "selected_gate4": selected_summary.get("gate4"),
        },
        "variant_summary": variant_summary,
        "selected_variant": selected,
        "variants": variants,
        "before_metrics": before_metrics,
        "after_metrics": selected_summary.get("after_metrics"),
        "delta_metrics": selected_summary.get("delta_metrics"),
        "expected_value_score_delta": selected_summary.get("expected_value_score_delta"),
        "total_pnl_delta": selected_summary.get("total_pnl_delta"),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM ranking is not changed; the all-market expansion problem is "
                "currently a candidate-pool and historical-data coverage question."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a variant is pursued, add it first as a default-off paper "
                "sleeve / universe-governance candidate with forward replacement "
                "value. A live core promotion would require a separate shared "
                "universe policy, production adapter exposure, parity tests, and "
                "canonical replay with the final PIT data source."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "decision_reason": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "Build or connect a survivorship-aware broad OHLCV universe and run a "
            "default-off forward paper sleeve. Do not promote broad core expansion "
            "from a cached thematic subset alone."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "selected_variant": payload["gate4"]["selected_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
    }
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_markdown(payload) + "\n", encoding="utf-8")
    jsonl_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"variants", "artifact_markdown"}
    }
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, jsonl_payload)


if __name__ == "__main__":
    result = build_payload()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "gate1_passed": result["gate1"]["passed"],
                "gate4_passed": result["gate4"]["passed"],
                "selected_variant": result["gate4"]["selected_variant"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "tested_candidates": result["parameters"]["tested_candidates"],
                "variant_summary": result["variant_summary"],
                "coverage_boundary": result["coverage_audit"]["history_coverage_boundary"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
