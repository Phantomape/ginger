from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from low_deployment_etf_overlay import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION,
    SLEEVE_NAME,
    build_low_deployment_etf_overlay_snapshot,
    empty_low_deployment_etf_overlay_state,
    save_low_deployment_etf_overlay_state,
)


SNAPSHOT_PATH = REPO_ROOT / "data/paper_sleeves/low_deployment_etf/snapshots.jsonl"
STATE_PATH = REPO_ROOT / "data/paper_sleeves/low_deployment_etf/state.json"
SIGNAL_DIR = REPO_ROOT / "data/daily/signals/quant"
SUMMARY_PATH = REPO_ROOT / "data/paper_sleeves/low_deployment_etf/backfill_summary_20260604.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _read_git_jsonl(rel_path: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return []
    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _date_from_signal_path(path: Path) -> str:
    raw = path.stem.removeprefix("quant_signals_")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _positive_float(value: Any) -> float | None:
    number = _float_or_none(value)
    return number if number is not None and number > 0 else None


def _feature_open(row: dict[str, Any]) -> float | None:
    close = _positive_float(row.get("close"))
    open_close_return = _float_or_none(row.get("signal_day_ticker_open_close_return_pct"))
    if close is None or open_close_return is None or open_close_return <= -0.99:
        return None
    return close / (1.0 + open_close_return)


def _previous_signal_date(signal_dates: list[str], as_of: str) -> str | None:
    previous = [item for item in signal_dates if item < as_of]
    return previous[-1] if previous else None


def _synth_rows(
    *,
    ticker: str,
    as_of: str,
    trade_feature: dict[str, Any],
    prior_date: str,
    prior_feature: dict[str, Any],
) -> list[dict[str, Any]]:
    trade_open = _feature_open(trade_feature)
    trade_close = _positive_float(trade_feature.get("close"))
    prior_close = _positive_float(prior_feature.get("close"))
    prior_momentum = _float_or_none(prior_feature.get("momentum_20d_pct"))
    prior_vs_sma = _float_or_none(prior_feature.get("price_vs_200ma_pct"))
    if (
        trade_open is None
        or trade_close is None
        or prior_close is None
        or prior_momentum is None
        or prior_vs_sma is None
        or prior_momentum <= 0.0
        or prior_vs_sma <= 0.0
    ):
        return []

    prior_sma = prior_close / (1.0 + prior_vs_sma)
    momentum_base = prior_close / (1.0 + prior_momentum)
    filler = (prior_sma * 200.0 - prior_close - momentum_base) / 198.0
    if filler <= 0.0:
        return []

    prior_day = date.fromisoformat(prior_date)
    rows = []
    for idx in range(200):
        row_date = prior_day - timedelta(days=200 - idx)
        close = momentum_base if idx == 180 else filler
        rows.append(
            {
                "date": row_date.isoformat(),
                "open": round(close, 4),
                "close": round(close, 4),
            }
        )
    rows.append(
        {
            "date": prior_date,
            "open": round(prior_close, 4),
            "close": round(prior_close, 4),
        }
    )
    rows.append(
        {
            "date": as_of,
            "open": round(trade_open, 4),
            "close": round(trade_close, 4),
        }
    )
    return rows


def _active_core_positions_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    by_date: dict[str, int] = {}
    for row in rows:
        as_of = str(row.get("asof_date") or "")[:10]
        if not as_of or as_of in by_date:
            continue
        value = _float_or_none(row.get("active_core_positions"))
        if value is not None:
            by_date[as_of] = int(value)
    return by_date


def _blocked_dates_from_snapshots(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("asof_date") or "")[:10]
            for row in rows
            if any(
                (skip or {}).get("reason") == "active_core_positions_above_threshold"
                for skip in (row.get("skipped_today") or [])
                if isinstance(skip, dict)
            )
        }
    )


def _core_positions_payload(count: int) -> dict[str, list[dict[str, Any]]]:
    return {
        "positions": [
            {
                "ticker": f"CORE{idx:02d}",
                "shares": 1,
                "opened_by_strategy": "trend_long",
            }
            for idx in range(max(0, count))
        ]
    }


def main() -> None:
    existing_snapshots = _read_jsonl(SNAPSHOT_PATH)
    active_by_date = _active_core_positions_by_date(existing_snapshots)
    blocked_dates = _blocked_dates_from_snapshots(existing_snapshots)
    blocked_date_source = "working_tree_low_deployment_snapshots"
    if not blocked_dates:
        rel_path = "data/paper_sleeves/low_deployment_etf/snapshots.jsonl"
        git_snapshots = _read_git_jsonl(rel_path)
        blocked_dates = _blocked_dates_from_snapshots(git_snapshots)
        active_by_date = _active_core_positions_by_date(git_snapshots)
        blocked_date_source = "git_head_tracked_low_deployment_snapshots"
    if not blocked_dates and SUMMARY_PATH.exists():
        summary = _read_json(SUMMARY_PATH)
        summary_dates = [
            str(item)[:10] for item in summary.get("source_blocked_dates") or []
        ]
        summary_active = summary.get("active_core_positions_by_date") or {}
        if summary_dates:
            blocked_dates = sorted(set(summary_dates))
            active_by_date = {
                str(key)[:10]: int(value) for key, value in summary_active.items()
            }
            blocked_date_source = "existing_low_deployment_backfill_summary"
    signal_payloads = {
        _date_from_signal_path(path): _read_json(path)
        for path in sorted(SIGNAL_DIR.glob("quant_signals_*.json"))
    }
    signal_blocked_dates = []
    for as_of, payload in signal_payloads.items():
        overlay = payload.get("low_deployment_etf_overlay") or {}
        if not isinstance(overlay, dict):
            continue
        has_old_core_skip = any(
            (skip or {}).get("reason") == "active_core_positions_above_threshold"
            for skip in overlay.get("skipped_today") or []
            if isinstance(skip, dict)
        )
        if not has_old_core_skip:
            continue
        signal_blocked_dates.append(as_of)
        active = _float_or_none(overlay.get("active_core_positions"))
        if active is not None:
            active_by_date[as_of] = int(active)
    if signal_blocked_dates:
        blocked_dates = sorted(set(blocked_dates).union(signal_blocked_dates))
        blocked_date_source = f"{blocked_date_source}+daily_quant_signal_overlay_snapshots"
    signal_dates = sorted(signal_payloads)
    replay_dates = [item for item in blocked_dates if item in signal_payloads]
    missing_signal_dates = [item for item in blocked_dates if item not in signal_payloads]

    state = empty_low_deployment_etf_overlay_state()
    snapshots: list[dict[str, Any]] = []
    skipped_feature_dates: list[str] = []
    config = deepcopy(DEFAULT_CONFIG)
    config["paper_enabled"] = True
    config["trade_enabled"] = False

    for as_of in replay_dates:
        prior_date = _previous_signal_date(signal_dates, as_of)
        if prior_date is None:
            skipped_feature_dates.append(as_of)
            continue
        trade_features = signal_payloads[as_of].get("features") or {}
        prior_features = signal_payloads[prior_date].get("features") or {}
        ohlcv_by_ticker = {}
        for ticker in config["candidate_tickers"]:
            ticker = str(ticker).upper()
            rows = _synth_rows(
                ticker=ticker,
                as_of=as_of,
                trade_feature=trade_features.get(ticker) or {},
                prior_date=prior_date,
                prior_feature=prior_features.get(ticker) or {},
            )
            if rows:
                ohlcv_by_ticker[ticker] = rows
        if not ohlcv_by_ticker:
            skipped_feature_dates.append(as_of)
            continue

        snapshot = build_low_deployment_etf_overlay_snapshot(
            as_of=as_of,
            ohlcv_by_ticker=ohlcv_by_ticker,
            open_positions=_core_positions_payload(active_by_date.get(as_of, 0)),
            portfolio_value=None,
            state=state,
            config=config,
            persist=False,
        )
        snapshot["backfill_source"] = (
            "daily_quant_signal_feature_replay_from_persisted_etf_features"
        )
        if snapshot.get("candidate"):
            snapshot["candidate"]["backfill_source"] = snapshot["backfill_source"]
        for row in snapshot.get("closed_today") or []:
            row["backfill_source"] = snapshot["backfill_source"]
        state["closed_positions"].extend(snapshot.get("closed_today") or [])
        state["skipped_days"].extend(snapshot.get("skipped_today") or [])
        snapshots.append(snapshot)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_low_deployment_etf_overlay_state(state, STATE_PATH)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as handle:
        for snapshot in snapshots:
            handle.write(json.dumps(snapshot, sort_keys=True) + "\n")

    summary = {
        "backfill": "low_deployment_etf_overlay_independent_slot_history",
        "rule_version": RULE_VERSION,
        "sleeve": SLEEVE_NAME,
        "source_snapshot_path": str(SNAPSHOT_PATH.relative_to(REPO_ROOT)),
        "source_signal_dir": str(SIGNAL_DIR.relative_to(REPO_ROOT)),
        "blocked_date_source": blocked_date_source,
        "blocked_date_count_before": len(blocked_dates),
        "source_blocked_dates": blocked_dates,
        "active_core_positions_by_date": active_by_date,
        "replay_date_count": len(replay_dates),
        "snapshot_count_after": len(snapshots),
        "closed_position_count_after": len(state.get("closed_positions") or []),
        "skipped_day_count_after": len(state.get("skipped_days") or []),
        "missing_signal_dates": missing_signal_dates,
        "skipped_feature_dates": skipped_feature_dates,
        "candidate_dates": [
            row.get("asof_date") for row in snapshots if row.get("candidate_count")
        ],
        "candidate_tickers": [
            (row.get("candidate") or {}).get("ticker")
            for row in snapshots
            if row.get("candidate_count")
        ],
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "replay_only": True,
        },
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
