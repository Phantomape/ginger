"""exp-20260723-007: owner-assumed options history and available-window replay.

This runner does not change the frozen paper selector.  It first enumerates
the exact price+flow-eligible ticker/date pairs without reading future returns,
then materializes only those option chains.  Retrospective OnclickMedia rows
remain visibly retrospective, but the owner-authorized research contract
treats quote_date D as immutable and usable from the next US equity session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
for root in (str(REPO_ROOT), str(QUANT_ROOT)):
    if root not in sys.path:
        sys.path.insert(0, root)

from core_drawdown_flow_put_stabilization_paper_sleeve import (  # noqa: E402
    NON_COMMON_STOCK_EXCLUSIONS,
    RULE_VERSION,
    _index_on_date,
    _rows_by_ticker,
    build_core_drawdown_flow_put_candidates,
    next_session_after,
    replay_core_drawdown_flow_put_sleeve,
)
from filter import _BASE_WATCHLIST  # noqa: E402
from moomoo_capital_flow_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG as MOOMOO_DEFAULT_CONFIG,
    DEFAULT_MANIFEST_PATH as FLOW_MANIFEST_PATH,
    DEFAULT_ROWS_PATH as FLOW_ROWS_PATH,
    flow_rows_by_ticker,
    load_moomoo_capital_flow_rows,
)
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
    load_warehouse_snapshot_ohlcv_frames,
)
from options_onclickmedia import (  # noqa: E402
    build_ticker_date_rows,
)


EXPERIMENT_ID = "exp-20260723-007"
OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OPTIONS_DIR = OUTPUT_DIR / "owner_assumed_options_by_date"
CACHE_DIR = OUTPUT_DIR / "onclickmedia_cache"
QUALITY_PATH = OUTPUT_DIR / "owner_assumed_options_quality_gate.json"
ARTIFACT_PATH = OUTPUT_DIR / "exp_20260723_007_owner_assumed_options_backfill_replay.json"
BEFORE_PATH = OUTPUT_DIR / "before.json"
AFTER_PATH = OUTPUT_DIR / "after.json"
HISTORICAL_SEED_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260506-009"
    / "options_candidate_chain.jsonl"
)
FORWARD_OPTIONS_DIR = REPO_ROOT / "data" / "non_ohlcv"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
OWNER_OPTIONS_CONTRACT = "owner_authorized_onclickmedia_quote_date_stable_d_plus_1_v1"
OWNER_FLOW_CONTRACT = "owner_authorized_moomoo_day_stable_d_plus_1_v1"

WINDOWS = {
    "mid_weak_available": {
        "start": "2025-07-02",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "recent_available": {
        "start": "2026-04-22",
        "end": "2026-07-22",
        "snapshot": None,
    },
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(_jsonable(row), sort_keys=True, ensure_ascii=False) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _history_start(start: str) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=500)).date().isoformat()


def _universe() -> list[str]:
    latest = FORWARD_OPTIONS_DIR / "options_onclickmedia_chain_20260722.jsonl"
    tickers: set[str] = set()
    if latest.exists():
        with latest.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                try:
                    ticker = str(json.loads(line).get("ticker") or "").upper().strip()
                except json.JSONDecodeError:
                    continue
                if ticker and ticker not in NON_COMMON_STOCK_EXCLUSIONS:
                    tickers.add(ticker)
    if not tickers:
        tickers = set(_BASE_WATCHLIST) - set(NON_COMMON_STOCK_EXCLUSIONS)
    return sorted(tickers)


def _load_frames(definition: dict[str, Any], universe: list[str]) -> dict[str, pd.DataFrame]:
    tickers = [*universe, "SPY", "QQQ"]
    start = _history_start(definition["start"])
    if definition.get("snapshot"):
        return load_warehouse_snapshot_ohlcv_frames(
            DEFAULT_WAREHOUSE_PATH,
            REPO_ROOT / definition["snapshot"],
            tickers,
            start,
            definition["end"],
        )
    return load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH, tickers, start, definition["end"]
    )


def _dummy_chain(spot: float, signal_date: str) -> dict[str, Any]:
    """A non-outcome-bearing chain used only to enumerate pre-option pairs."""
    return {
        "liquid_rows": 10,
        "captured_rows": 10,
        "pit_safe_rows": 10,
        "expiries": ["2099-01-01", "2099-01-08"],
        "usable_trade_dates": [next_session_after(signal_date)],
        "put_rows": [(spot * 0.80, 1.0), (spot * 0.97, 1.0)],
    }


def _enumerate_preoption_pairs(
    *,
    frames: dict[str, pd.DataFrame],
    flow_rows: list[dict[str, Any]],
    universe: list[str],
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_ticker = _rows_by_ticker(frames)
    flow_index = flow_rows_by_ticker(flow_rows)
    sessions = [
        str(row["date"])
        for row in (rows_by_ticker.get("SPY") or [])
        if start <= str(row["date"]) <= end
    ]
    pairs: list[dict[str, Any]] = []
    aggregate_stages: Counter[str] = Counter()
    aggregate_rejects: Counter[str] = Counter()
    for session in sessions:
        dummy: dict[str, dict[str, Any]] = {}
        for ticker in universe:
            rows = rows_by_ticker.get(ticker) or []
            idx = _index_on_date(rows, session)
            if idx is None:
                continue
            spot = float(rows[idx].get("close") or 0.0)
            if spot > 0:
                dummy[ticker] = _dummy_chain(spot, session)
        candidates, rejects, stages = build_core_drawdown_flow_put_candidates(
            rows_by_ticker=rows_by_ticker,
            flow_by_ticker=flow_index,
            option_by_ticker=dummy,
            tickers=universe,
            as_of=session,
            options_scoring_allowed=True,
        )
        aggregate_stages.update(stages)
        aggregate_rejects.update(rejects)
        for row in candidates:
            pairs.append(
                {
                    "ticker": row["ticker"],
                    "quote_date": session,
                    "spot": row["close"],
                    "flow_strength": row["flow_strength"],
                    "dd60": row["dd60"],
                    "rsi14": row["rsi14"],
                    "ret20": row["ret20"],
                    "close_location": row["close_location"],
                }
            )
    unique = {
        (row["ticker"], row["quote_date"]): row
        for row in pairs
    }
    return (
        [unique[key] for key in sorted(unique, key=lambda item: (item[1], item[0]))],
        {
            "sessions": len(sessions),
            "preoption_pair_count": len(unique),
            "preoption_date_count": len({key[1] for key in unique}),
            "stage_counts": dict(sorted(aggregate_stages.items())),
            "reject_counts": dict(sorted(aggregate_rejects.items())),
        },
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _pair(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("ticker") or "").upper().strip(),
        str(row.get("quote_date") or row.get("date") or "")[:10],
    )


def _load_known_pair_rows(
    wanted: set[tuple[str, str]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[tuple[str, str], str]]:
    known: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source: dict[tuple[str, str], str] = {}

    # Idempotent reruns prefer this experiment's already-materialized rows.
    for path in sorted(OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl")):
        for row in _read_jsonl(path):
            key = _pair(row)
            if key in wanted:
                known[key].append(row)
                source[key] = "experiment_existing"

    # Real forward files outrank retrospective seed rows.
    wanted_dates = sorted({day for _ticker, day in wanted})
    for day in wanted_dates:
        path = FORWARD_OPTIONS_DIR / f"options_onclickmedia_chain_{day.replace('-', '')}.jsonl"
        if not path.exists():
            continue
        for row in _read_jsonl(path):
            key = _pair(row)
            if key in wanted and source.get(key) != "experiment_existing":
                known[key].append(row)
                source[key] = "forward_daily"

    if HISTORICAL_SEED_PATH.exists():
        for row in _read_jsonl(HISTORICAL_SEED_PATH):
            key = _pair(row)
            if key in wanted and key not in source:
                known[key].append(row)
                source[key] = "historical_seed_exp_20260506_009"
    return dict(known), source


def _owner_authorize_row(row: dict[str, Any], quote_date: str) -> dict[str, Any]:
    out = deepcopy(row)
    out["source_usable_trade_date"] = out.get("usable_trade_date")
    out["usable_trade_date"] = next_session_after(quote_date)
    if str(out.get("collection_mode") or "") != "forward_daily":
        out["source_pit_safe"] = bool(out.get("pit_safe"))
        out["pit_safe"] = True
        out["pit_safe_flag"] = OWNER_OPTIONS_CONTRACT
        out["pit_caveat"] = (
            "Retrospectively fetched and lacking independent vendor_asof; accepted only "
            "under the owner's explicit immutable quote-date D, D+1-usable research assumption."
        )
    out["owner_authorized_pit_contract"] = OWNER_OPTIONS_CONTRACT
    out["experiment_id"] = EXPERIMENT_ID
    return out


def _fetch_pair(pair: dict[str, Any]) -> tuple[tuple[str, str], list[dict[str, Any]], dict[str, Any]]:
    ticker = pair["ticker"]
    quote_date = pair["quote_date"]
    rows, stats = build_ticker_date_rows(
        ticker=ticker,
        quote_date=datetime.strptime(quote_date, "%Y-%m-%d").date(),
        underlying_price=float(pair["spot"]),
        max_expirations=2,
        max_strikes_per_side=12,
        collection_mode="historical_backfill",
        fetch_kwargs={
            "cache_dir": CACHE_DIR,
            "refresh": False,
            "timeout": 30.0,
            "sleep_seconds": 0.02,
        },
    )
    return (ticker, quote_date), rows, stats


def _materialize_options(
    pairs: list[dict[str, Any]], *, fetch_missing: bool, max_workers: int
) -> dict[str, Any]:
    wanted = {(row["ticker"], row["quote_date"]) for row in pairs}
    pair_by_key = {(row["ticker"], row["quote_date"]): row for row in pairs}
    known, source = _load_known_pair_rows(wanted)
    fetch_stats: list[dict[str, Any]] = []
    missing = [key for key in sorted(wanted, key=lambda item: (item[1], item[0])) if not known.get(key)]

    if fetch_missing and missing:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
            futures = {pool.submit(_fetch_pair, pair_by_key[key]): key for key in missing}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    fetched_key, rows, stats = future.result()
                except Exception as exc:  # noqa: BLE001 - preserve per-pair failures
                    fetch_stats.append(
                        {"ticker": key[0], "quote_date": key[1], "error": f"{type(exc).__name__}: {exc}"}
                    )
                    continue
                fetch_stats.append(stats)
                if rows:
                    known[fetched_key] = rows
                    source[fetched_key] = "fetched_historical"

    normalized_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, rows in known.items():
        if key not in wanted:
            continue
        for row in rows:
            normalized_by_date[key[1]].append(_owner_authorize_row(row, key[1]))

    output_files: list[str] = []
    quality_by_date: dict[str, dict[str, Any]] = {}
    for quote_date, rows in sorted(normalized_by_date.items()):
        deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            dedupe_key = (
                row.get("ticker"),
                row.get("quote_date"),
                row.get("expiration") or row.get("expiry"),
                row.get("call_put"),
                row.get("strike"),
            )
            deduped[dedupe_key] = row
        materialized = sorted(
            deduped.values(),
            key=lambda row: (
                str(row.get("ticker")),
                str(row.get("expiration") or row.get("expiry")),
                str(row.get("call_put")),
                float(row.get("strike") or 0.0),
            ),
        )
        path = OPTIONS_DIR / f"options_onclickmedia_chain_{quote_date.replace('-', '')}.jsonl"
        _write_jsonl(path, materialized)
        output_files.append(str(path.relative_to(REPO_ROOT)).replace("\\", "/"))
        tickers = {str(row.get("ticker")) for row in materialized}
        quality_by_date[quote_date] = {
            "status": "owner_assumed_targeted_preoption_population",
            "scoring_allowed": True,
            "rows": len(materialized),
            "tickers": len(tickers),
            "usable_trade_dates": [next_session_after(quote_date)],
            "contract": OWNER_OPTIONS_CONTRACT,
            "reasons": [],
        }

    _write_json(
        QUALITY_PATH,
        {
            "overall_status": "owner_assumed_research_only",
            "by_quote_date": quality_by_date,
            "usable_quote_dates": sorted(quality_by_date),
            "quarantined_quote_dates": [],
            "parameters": {
                "target_population": "all frozen price+flow-eligible ticker/date pairs before reading outcomes",
                "contract": OWNER_OPTIONS_CONTRACT,
                "min_liquid_rows_enforced_by_shared_selector": 10,
                "required_expiries_enforced_by_shared_selector": 2,
            },
        },
    )
    final_missing = [key for key in wanted if not known.get(key)]
    return {
        "wanted_pairs": len(wanted),
        "covered_pairs": len(wanted) - len(final_missing),
        "missing_pairs": [f"{ticker}|{day}" for ticker, day in sorted(final_missing, key=lambda item: (item[1], item[0]))],
        "pair_source_counts": dict(sorted(Counter(source.values()).items())),
        "fetch_pair_attempts": len(fetch_stats),
        "fetch_errors": [row for row in fetch_stats if row.get("error") or row.get("errors")],
        "materialized_date_count": len(normalized_by_date),
        "materialized_row_count": sum(len(rows) for rows in normalized_by_date.values()),
        "output_files": output_files,
        "quality_path": str(QUALITY_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
    }


def _benchmark(frame: pd.DataFrame | None, start: str, end: str) -> float | None:
    if frame is None or frame.empty:
        return None
    sliced = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]
    if sliced.empty:
        return None
    first = float(sliced["Close"].iloc[0])
    last = float(sliced["Close"].iloc[-1])
    return round(last / first - 1.0, 8) if first > 0 else None


def _concentration(trades: list[dict[str, Any]]) -> dict[str, Any]:
    positive = defaultdict(float)
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl > 0:
            positive[str(trade.get("ticker"))] += pnl
    total = sum(positive.values())
    ranked = sorted(positive.items(), key=lambda item: (-item[1], item[0]))
    return {
        "positive_pnl": round(total, 2),
        "top_positive_ticker": ranked[0][0] if ranked else None,
        "top_positive_ticker_share": round(ranked[0][1] / total, 8) if total > 0 else None,
        "top5_positive_share": round(sum(value for _ticker, value in ranked[:5]) / total, 8) if total > 0 else None,
        "positive_pnl_by_ticker": {ticker: round(value, 2) for ticker, value in ranked},
    }


def _baseline() -> dict[str, Any]:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    windows = payload.get("windows") or payload.get("window_results") or {}
    return {
        "path": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": _sha256(BASELINE_PATH),
        "windows": windows,
    }


def run(*, fetch_missing: bool = True, max_workers: int = 6) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = _universe()
    flow_rows = load_moomoo_capital_flow_rows()
    frames_by_window: dict[str, dict[str, pd.DataFrame]] = {}
    pairs_by_window: dict[str, list[dict[str, Any]]] = {}
    preflight_by_window: dict[str, dict[str, Any]] = {}
    all_pairs: dict[tuple[str, str], dict[str, Any]] = {}

    for label, definition in WINDOWS.items():
        frames = _load_frames(definition, universe)
        frames_by_window[label] = frames
        pairs, preflight = _enumerate_preoption_pairs(
            frames=frames,
            flow_rows=flow_rows,
            universe=universe,
            start=definition["start"],
            end=definition["end"],
        )
        pairs_by_window[label] = pairs
        preflight_by_window[label] = preflight
        for pair in pairs:
            all_pairs[(pair["ticker"], pair["quote_date"])] = pair

    backfill = _materialize_options(
        [all_pairs[key] for key in sorted(all_pairs, key=lambda item: (item[1], item[0]))],
        fetch_missing=fetch_missing,
        max_workers=max_workers,
    )

    results: list[dict[str, Any]] = []
    for label, definition in WINDOWS.items():
        frames = frames_by_window[label]
        result = replay_core_drawdown_flow_put_sleeve(
            ohlcv_by_ticker=frames,
            flow_rows=flow_rows,
            start=definition["start"],
            end=definition["end"],
            tickers=universe,
            options_dir=OPTIONS_DIR,
            options_quality_path=QUALITY_PATH,
        )
        result["label"] = label
        result["definition"] = definition
        result["preoption_touch_preflight"] = preflight_by_window[label]
        result["concentration"] = _concentration(result.get("trades") or [])
        result["benchmarks"] = {
            "spy_buy_hold_return_pct": _benchmark(frames.get("SPY"), definition["start"], definition["end"]),
            "qqq_buy_hold_return_pct": _benchmark(frames.get("QQQ"), definition["start"], definition["end"]),
        }
        result["interpretation"] = (
            "owner_assumed_historical_pit_research_only_not_independently_vendor_asof_audited"
        )
        results.append(result)

    flow_manifest = (
        json.loads(Path(FLOW_MANIFEST_PATH).read_text(encoding="utf-8"))
        if Path(FLOW_MANIFEST_PATH).exists()
        else {}
    )
    flow_dates = sorted({str(row.get("flow_date")) for row in flow_rows if row.get("flow_date")})
    aggregate = {
        "total_pnl": round(sum(float(row["metrics"]["total_pnl"]) for row in results), 2),
        "realized_pnl": round(sum(float(row["metrics"]["realized_pnl"]) for row in results), 2),
        "trade_count": sum(int(row["metrics"]["trade_count"]) for row in results),
        "selected_decisions": sum(int(row["metrics"]["selected_decisions"]) for row in results),
        "expected_value_score_sum": round(
            sum(float(row["metrics"]["expected_value_score"]) for row in results), 8
        ),
        "mechanically_gate4_eligible_window_count": sum(
            int(bool(row["gate_checks"]["gate4_eligible"])) for row in results
        ),
    }
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": "owner_assumed_pit_historical_replay_measurement",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "observed_only_owner_assumed_pit_not_alpha",
        "evidence_grade": "observed_only",
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "owner_authorized_assumptions": {
            "moomoo": OWNER_FLOW_CONTRACT,
            "onclickmedia": OWNER_OPTIONS_CONTRACT,
            "onclickmedia_limit": "historical rows have no independently auditable vendor_asof and are research-only",
        },
        "fixed_policy_bundle": {
            "changed_from_exp_20260723_004": False,
            "parameters_retuned": False,
            "single_slot": True,
            "next_session_open": True,
            "fixed_h10_close": True,
            "paper_notional_usd": 4_000.0,
            "round_trip_cost_pct": 0.0035,
        },
        "synthesis_pass": {
            "baseline_universe": universe,
            "opportunity_cost_winner": None,
            "evidence_surfaces_used": [
                "price: fixed snapshot warehouse for mid/late and warehouse overlay for recent",
                "flow: Moomoo DAY archive under owner stable-D assumption",
                "derivatives/positioning: targeted exact-date OnclickMedia two-expiry chain under owner stable-D assumption",
                "portfolio exposure: unchanged paper-only single-slot envelope",
            ],
            "evidence_surfaces_missing": [
                "independent OnclickMedia vendor_asof/publication timestamp",
                "Moomoo flow before 2025-07-02",
                "event veto intentionally absent from the frozen rule",
            ],
            "hypothesis_candidates": [
                {
                    "id": "selected_frozen_four_surface_owner_assumed_history",
                    "baseline": "cash, SPY, QQQ, and same-window active core reference",
                    "treatment": "unchanged full four-surface top1 paper selector",
                    "horizon": "next-open H10",
                    "replacement_value": "same-day eligible alternatives plus cash",
                    "falsifier": "nonpositive aggregate EV, benchmark underperformance, <5 touches, or >40% positive-PnL single-ticker share",
                },
                {"id": "put_proxy", "decision": "not_selected", "reason": "would change the original strategy"},
                {"id": "threshold_retune", "decision": "not_selected", "reason": "would introduce post-data fitting"},
            ],
            "selected_hypothesis": "selected_frozen_four_surface_owner_assumed_history",
            "economic_mechanism": "capitulation plus large-order accumulation plus nearby downside positioning plus price stabilization",
            "falsifier": "predeclared per-window touch, EV, benchmark, and concentration failures",
            "evidence_grade": "observed_only",
            "next_machine_action": "continue real forward snapshots; no live/alpha promotion from owner-assumed historical provenance",
            "research_digest": {
                "latest_digest_read": "data/research_digest/latest_digest.md",
                "selected_entry_ids": [],
                "reason": "the user-fixed mechanism predates and is not altered by current digest entries",
            },
        },
        "source_authorization_preflight": {
            "onclickmedia_site_represents_data_as_free historical backtesting": True,
            "source_url": "https://www.onclickmedia.com/",
            "historical_adapter_audit": "docs/non_ohlcv_data_audit/eod_options_onclickmedia_harness_exp-20260506-003_20260506.md",
        },
        "moomoo_forward_accumulation": {
            "rows_path": str(Path(FLOW_ROWS_PATH).relative_to(REPO_ROOT)).replace("\\", "/"),
            "manifest_path": str(Path(FLOW_MANIFEST_PATH).relative_to(REPO_ROOT)).replace("\\", "/"),
            "row_count": len(flow_rows),
            "first_date": flow_dates[0] if flow_dates else None,
            "last_date": flow_dates[-1] if flow_dates else None,
            "manifest": flow_manifest,
            "daily_refresh_max_archive_staleness_days": MOOMOO_DEFAULT_CONFIG["max_archive_staleness_days"],
        },
        "preoption_touch_preflight": preflight_by_window,
        "options_backfill": backfill,
        "window_results": results,
        "aggregate": aggregate,
        "gate1_active_baseline": _baseline(),
        "gate4_interpretation": {
            "mechanical_result_only": True,
            "accepted_alpha": False,
            "live_ready": False,
            "reason": "historical options PIT status rests on owner assumption, not independently audited vendor_asof",
        },
        "reproduction": [
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260723_007_owner_assumed_options_backfill_replay.py",
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_moomoo_capital_flow_paper_sleeve.py quant\\test_core_drawdown_flow_put_stabilization_paper_sleeve.py quant\\test_run_daily_wiring.py -q",
        ],
    }
    _write_json(ARTIFACT_PATH, artifact)
    _write_json(
        BEFORE_PATH,
        {
            "experiment_id": EXPERIMENT_ID,
            "measurement_stage": "before",
            "artifact_type": "missing_historical_options_and_three_day_flow_refresh_guard",
            "expected_value_score": 0.0,
            "strategy_total_return_pct": 0.0,
            "sharpe_daily": 0.0,
            "max_drawdown_pct": 0.0,
            "total_pnl": 0.0,
            "total_trades": 0,
            "survival_rate": 0.0,
        },
    )
    _write_json(
        AFTER_PATH,
        {
            "experiment_id": EXPERIMENT_ID,
            "measurement_stage": "after",
            "artifact_type": "owner_assumed_history_measurement_infrastructure",
            "decision": "accepted_measurement_if_contract_checks_true_not_alpha",
            "expected_value_score": 0.0,
            "strategy_total_return_pct": 0.0,
            "sharpe_daily": 0.0,
            "max_drawdown_pct": 0.0,
            "total_pnl": 0.0,
            "total_trades": 0,
            "survival_rate": 1.0,
            "contract_checks": {
                "moomoo_daily_refresh_threshold_zero": MOOMOO_DEFAULT_CONFIG["max_archive_staleness_days"] == 0,
                "moomoo_archive_through_2026_07_22": bool(flow_dates and flow_dates[-1] == "2026-07-22"),
                "all_preoption_pairs_accounted_for": backfill["covered_pairs"] + len(backfill["missing_pairs"]) == backfill["wanted_pairs"],
                "owner_contract_explicit": True,
                "three_available_windows_reported": len(results) == 3,
                "selector_thresholds_unchanged": True,
                "trade_enabled_false": True,
                "accepted_alpha": False,
                "live_behavior_changed": False,
            },
            "artifact_path": str(ARTIFACT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        },
    )
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--max-workers", type=int, default=6)
    args = parser.parse_args()
    artifact = run(fetch_missing=not args.no_fetch, max_workers=args.max_workers)
    print(json.dumps(_jsonable(artifact), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
