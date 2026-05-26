"""Build a default-off forward ledger for EOD options structure tags.

The ledger is deliberately shadow-only. It joins already-existing Ginger
candidate snapshots from organized or legacy ``quant_signals_YYYYMMDD.json``
files to local
OnClickMedia option-chain snapshots collected for the same EOD quote date.
Rows carry the option ``usable_trade_date`` so downstream research cannot
silently use EOD option data before it was available.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_paths import resolve_daily_artifact_path  # noqa: E402

EXPERIMENT_ID = "exp-20260507-091"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
DEFAULT_CHAIN_DIR = REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_SIGNAL_DIR = REPO_ROOT / "data"
DEFAULT_HORIZONS = (5, 10, 20, 60)
DEFAULT_MIN_LIQUIDITY_PASS_RATE = 0.05
DEFAULT_MIN_LIQUID_TICKERS = 10
DEFAULT_MIN_MARKET_ROWS_RATE = 0.50


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def _repo_rel(path: str | Path) -> str:
    value = _repo_path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _read_json(path: str | Path) -> Any:
    return json.loads(_repo_path(path).read_text(encoding="utf-8"))


def _quant_signal_path(signal_dir: str | Path, date_tag: str) -> Path:
    return resolve_daily_artifact_path("quant_signals", date_tag, _repo_path(signal_dir))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = _repo_path(path)
    rows: list[dict[str, Any]] = []
    if not source.exists():
        return rows
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_text(value: Any) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _int(value: Any) -> int:
    number = _float(value)
    return int(number) if number is not None else 0


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper().replace(".", "-")


def _chain_date_from_path(path: Path) -> str | None:
    stem = path.stem
    suffix = stem.replace("options_onclickmedia_chain_", "")
    if len(suffix) != 8 or not suffix.isdigit():
        return None
    return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"


def discover_chain_files(chain_dir: Path, selected_dates: set[str] | None) -> list[Path]:
    files = sorted(chain_dir.glob("options_onclickmedia_chain_*.jsonl"))
    out = []
    for path in files:
        chain_date = _chain_date_from_path(path)
        if selected_dates and chain_date not in selected_dates:
            continue
        out.append(path)
    return out


def _nearest_by_delta(rows: list[dict[str, Any]], target_delta: float) -> dict[str, Any] | None:
    candidates = [
        row for row in rows
        if _float(row.get("delta")) is not None and _float(row.get("implied_vol")) is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs((_float(row.get("delta")) or 0.0) - target_delta))


def _atm_iv(rows: list[dict[str, Any]], underlying_price: float | None) -> float | None:
    if underlying_price is None:
        return None
    candidates = [
        row for row in rows
        if _float(row.get("strike")) is not None and _float(row.get("implied_vol")) is not None
    ]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda row: abs((_float(row.get("strike")) or 0.0) - underlying_price))
    iv = _float(nearest.get("implied_vol"))
    return round(iv, 6) if iv is not None else None


def summarize_option_structure(rows: list[dict[str, Any]], underlying_price: float | None) -> dict[str, Any]:
    if not rows:
        return {
            "has_options_coverage": False,
            "options_rows": 0,
            "option_liquidity_pass_rows": 0,
            "option_liquidity_pass_rate": 0.0,
        }

    calls = [row for row in rows if row.get("call_put") == "call"]
    puts = [row for row in rows if row.get("call_put") == "put"]
    liquid_rows = [row for row in rows if row.get("option_liquidity_pass")]
    expiries = sorted({str(row.get("expiry")) for row in rows if row.get("expiry")})

    call_volume = sum(_int(row.get("volume")) for row in calls)
    put_volume = sum(_int(row.get("volume")) for row in puts)
    call_oi = sum(_int(row.get("open_interest")) for row in calls)
    put_oi = sum(_int(row.get("open_interest")) for row in puts)

    near_expiry = expiries[0] if expiries else None
    far_expiry = expiries[-1] if len(expiries) >= 2 else None
    near_rows = [row for row in rows if row.get("expiry") == near_expiry]
    far_rows = [row for row in rows if row.get("expiry") == far_expiry]

    near_call_25 = _nearest_by_delta([row for row in near_rows if row.get("call_put") == "call"], 0.25)
    near_put_25 = _nearest_by_delta([row for row in near_rows if row.get("call_put") == "put"], -0.25)
    skew_25delta = None
    if near_call_25 and near_put_25:
        skew_25delta = round(
            (_float(near_put_25.get("implied_vol")) or 0.0)
            - (_float(near_call_25.get("implied_vol")) or 0.0),
            6,
        )

    near_atm_iv = _atm_iv(near_rows, underlying_price)
    far_atm_iv = _atm_iv(far_rows, underlying_price) if far_expiry else None
    term_structure_slope = (
        round(far_atm_iv - near_atm_iv, 6)
        if far_atm_iv is not None and near_atm_iv is not None else None
    )

    call_concentration = (
        round(max(_int(row.get("open_interest")) for row in calls) / call_oi, 6)
        if calls and call_oi else None
    )
    put_concentration = (
        round(max(_int(row.get("open_interest")) for row in puts) / put_oi, 6)
        if puts and put_oi else None
    )

    put_call_volume_ratio = round(put_volume / call_volume, 6) if call_volume else None
    put_call_oi_ratio = round(put_oi / call_oi, 6) if call_oi else None
    liquidity_pass_rate = round(len(liquid_rows) / len(rows), 6) if rows else 0.0

    squeeze_overlay = bool(
        len(liquid_rows) >= 10
        and call_oi > put_oi
        and (call_concentration or 0.0) >= 0.12
    )
    downside_risk_overlay = bool(
        len(liquid_rows) >= 10
        and (
            (put_call_oi_ratio is not None and put_call_oi_ratio >= 1.25)
            or (skew_25delta is not None and skew_25delta >= 0.05)
        )
    )

    return {
        "has_options_coverage": True,
        "options_rows": len(rows),
        "option_liquidity_pass_rows": len(liquid_rows),
        "option_liquidity_pass_rate": liquidity_pass_rate,
        "option_liquidity_filter": len(liquid_rows) >= 10,
        "expiry_count": len(expiries),
        "expiries": expiries,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_open_interest": call_oi,
        "put_open_interest": put_oi,
        "put_call_volume_ratio": put_call_volume_ratio,
        "put_call_oi_ratio": put_call_oi_ratio,
        "call_oi_concentration": call_concentration,
        "put_oi_concentration": put_concentration,
        "near_atm_iv": near_atm_iv,
        "far_atm_iv": far_atm_iv,
        "term_structure_slope": term_structure_slope,
        "skew_25delta_approx": skew_25delta,
        "squeeze_overlay": squeeze_overlay,
        "downside_risk_overlay": downside_risk_overlay,
        "earnings_vol_overlay": None,
        "earnings_vol_overlay_note": "Not computed until a PIT earnings-date join is explicitly wired.",
        "pit_safe_rows": sum(1 for row in rows if row.get("pit_safe")),
        "pit_unsafe_rows": sum(1 for row in rows if not row.get("pit_safe")),
        "vendor_asof_available_rows": sum(1 for row in rows if row.get("vendor_asof_available")),
        "usable_trade_dates": sorted({str(row.get("usable_trade_date")) for row in rows if row.get("usable_trade_date")}),
        "retrieved_at_values": sorted({str(row.get("retrieved_at")) for row in rows if row.get("retrieved_at")}),
    }


def load_option_rows(chain_files: list[Path]) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any]]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    diagnostics: dict[str, Any] = {
        "chain_files": [_repo_rel(path) for path in chain_files],
        "by_quote_date": {},
        "schema_fields": [],
    }
    all_fields: set[str] = set()
    for path in chain_files:
        rows = _read_jsonl(path)
        quote_dates = Counter()
        tickers = set()
        for row in rows:
            ticker = normalize_ticker(row.get("ticker"))
            quote_date = _date_text(row.get("quote_date") or row.get("date"))
            if not ticker or not quote_date:
                continue
            all_fields.update(row.keys())
            quote_dates[quote_date] += 1
            tickers.add(ticker)
            by_key[(quote_date, ticker)].append(row)

        for quote_date, count in quote_dates.items():
            date_rows = [row for row in rows if _date_text(row.get("quote_date") or row.get("date")) == quote_date]
            rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in date_rows:
                rows_by_ticker[normalize_ticker(row.get("ticker"))].append(row)
            per_ticker_liquid = {
                ticker: sum(1 for row in ticker_rows if row.get("option_liquidity_pass"))
                for ticker, ticker_rows in rows_by_ticker.items()
            }
            diagnostics["by_quote_date"][quote_date] = {
                "rows": count,
                "tickers": len({normalize_ticker(row.get("ticker")) for row in date_rows}),
                "option_liquidity_pass_rows": sum(1 for row in date_rows if row.get("option_liquidity_pass")),
                "option_liquidity_score_counts": dict(
                    Counter(str(row.get("option_liquidity_score")) for row in date_rows)
                ),
                "bid_gt_0_rows": sum(1 for row in date_rows if (_float(row.get("bid")) or 0.0) > 0),
                "ask_gt_bid_rows": sum(
                    1 for row in date_rows
                    if _float(row.get("bid")) is not None
                    and _float(row.get("ask")) is not None
                    and (_float(row.get("ask")) or 0.0) > (_float(row.get("bid")) or 0.0)
                ),
                "mid_gt_0_rows": sum(1 for row in date_rows if (_float(row.get("mid")) or 0.0) > 0),
                "volume_gt_0_rows": sum(1 for row in date_rows if _int(row.get("volume")) > 0),
                "volume_ge_10_rows": sum(1 for row in date_rows if _int(row.get("volume")) >= 10),
                "volume_ge_100_rows": sum(1 for row in date_rows if _int(row.get("volume")) >= 100),
                "open_interest_gt_0_rows": sum(1 for row in date_rows if _int(row.get("open_interest")) > 0),
                "open_interest_ge_100_rows": sum(1 for row in date_rows if _int(row.get("open_interest")) >= 100),
                "open_interest_ge_500_rows": sum(1 for row in date_rows if _int(row.get("open_interest")) >= 500),
                "delta_nonzero_rows": sum(1 for row in date_rows if abs(_float(row.get("delta")) or 0.0) > 1e-9),
                "implied_vol_gt_0_rows": sum(1 for row in date_rows if (_float(row.get("implied_vol")) or 0.0) > 0),
                "zero_liquid_tickers": sum(1 for liquid_count in per_ticker_liquid.values() if liquid_count == 0),
                "liquid_tickers_ge_10_rows": sum(1 for liquid_count in per_ticker_liquid.values() if liquid_count >= 10),
                "pit_safe_rows": sum(1 for row in date_rows if row.get("pit_safe")),
                "vendor_asof_available_rows": sum(1 for row in date_rows if row.get("vendor_asof_available")),
                "usable_trade_dates": sorted({str(row.get("usable_trade_date")) for row in date_rows if row.get("usable_trade_date")}),
                "path": _repo_rel(path),
            }
    diagnostics["schema_fields"] = sorted(all_fields)
    return by_key, diagnostics


def _feature_close(features: dict[str, Any], ticker: str) -> float | None:
    payload = features.get(ticker) if isinstance(features, dict) else None
    if not isinstance(payload, dict):
        return None
    for key in ("close", "Close", "current_price", "price"):
        number = _float(payload.get(key))
        if number is not None:
            return number
    return None


def _candidate_action_date(row: dict[str, Any], source_date: str) -> str:
    for key in ("entry_date", "trade_date", "usable_trade_date", "signal_date", "date"):
        text = _date_text(row.get(key))
        if text:
            return text
    return source_date


def _candidate_base(
    *,
    row: dict[str, Any],
    source_date: str,
    source_file: Path,
    source_section: str,
    source_index: int,
) -> dict[str, Any] | None:
    ticker = normalize_ticker(row.get("ticker") or row.get("symbol"))
    if not ticker:
        return None
    strategy = (
        row.get("strategy")
        or row.get("rule_version")
        or row.get("source")
        or row.get("sleeve")
        or source_section
    )
    return {
        "ticker": ticker,
        "candidate_source_date": source_date,
        "candidate_action_date": _candidate_action_date(row, source_date),
        "candidate_source_file": _repo_rel(source_file),
        "candidate_source_section": source_section,
        "candidate_source_index": source_index,
        "candidate_source": row.get("source") or source_section,
        "strategy": strategy,
        "decision": row.get("decision") or row.get("status") or "candidate_snapshot",
        "candidate_rank": row.get("candidate_rank") or row.get("rank"),
        "dedupe_key": row.get("dedupe_key"),
        "enabled": row.get("enabled"),
        "trade_enabled": row.get("trade_enabled"),
        "raw_candidate_keys": sorted(row.keys()),
    }


def collect_candidates(signal_file: Path, source_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not signal_file.exists():
        return [], {"signal_file_found": False, "path": _repo_rel(signal_file)}

    payload = _read_json(signal_file)
    candidates: list[dict[str, Any]] = []
    section_counts: Counter[str] = Counter()

    direct_sections = (
        "signals",
        "pilot_signals",
        "heat_blocked_signals",
        "heat_blocked_pilot_signals",
    )
    for section in direct_sections:
        rows = payload.get(section) or []
        if not isinstance(rows, list):
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            candidate = _candidate_base(
                row=row,
                source_date=source_date,
                source_file=signal_file,
                source_section=section,
                source_index=idx,
            )
            if candidate:
                candidates.append(candidate)
                section_counts[section] += 1

    queue_sections = (
        "form4_event_queue",
        "sec_event_queue",
        "sec_governance_event_queue",
        "sec_leadership_event_queue",
        "event_sleeve_bundle",
    )
    for section in queue_sections:
        container = payload.get(section) or {}
        if not isinstance(container, dict):
            continue
        rows = container.get("candidates") or []
        if not isinstance(rows, list):
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            candidate = _candidate_base(
                row=row,
                source_date=source_date,
                source_file=signal_file,
                source_section=section,
                source_index=idx,
            )
            if candidate:
                candidate["container_enabled"] = container.get("enabled")
                candidate["container_trade_enabled"] = container.get("trade_enabled")
                candidates.append(candidate)
                section_counts[section] += 1

    seen = set()
    deduped: list[dict[str, Any]] = []
    for candidate in candidates:
        key = (
            candidate.get("ticker"),
            candidate.get("candidate_source_date"),
            candidate.get("candidate_action_date"),
            candidate.get("candidate_source_section"),
            candidate.get("strategy"),
            candidate.get("dedupe_key"),
            candidate.get("candidate_source_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    diagnostics = {
        "signal_file_found": True,
        "path": _repo_rel(signal_file),
        "section_counts": dict(section_counts),
        "candidate_count_raw": len(candidates),
        "candidate_count_deduped": len(deduped),
        "features_count": len(payload.get("features") or {}),
    }
    return deduped, diagnostics


def _pit_join_status(candidate_action_date: str | None, usable_dates: list[str]) -> dict[str, Any]:
    if not usable_dates:
        return {
            "pit_candidate_join_safe": False,
            "pit_candidate_join_status": "no_options_usable_trade_date",
        }
    min_usable = min(usable_dates)
    action_date = _date_text(candidate_action_date)
    if action_date is None:
        return {
            "pit_candidate_join_safe": False,
            "pit_candidate_join_status": "candidate_action_date_missing",
            "options_usable_from": min_usable,
        }
    safe = action_date >= min_usable
    return {
        "pit_candidate_join_safe": safe,
        "pit_candidate_join_status": (
            "safe_for_candidate_action_date"
            if safe else "options_only_usable_after_candidate_action_date"
        ),
        "options_usable_from": min_usable,
    }


def _load_ohlcv_snapshot(path: str | Path | None) -> dict[str, list[dict[str, Any]]]:
    if not path:
        return {}
    source = _repo_path(path)
    if not source.exists():
        return {}
    payload = _read_json(source)
    rows_by_ticker = payload.get("ohlcv", payload) if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(rows_by_ticker, dict):
        return out
    for ticker, rows in rows_by_ticker.items():
        if not isinstance(rows, list):
            continue
        clean = [row for row in rows if isinstance(row, dict) and (row.get("Date") or row.get("date"))]
        out[normalize_ticker(ticker)] = sorted(clean, key=lambda row: str(row.get("Date") or row.get("date"))[:10])
    return out


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close") if row.get("Close") is not None else row.get("close"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low") if row.get("Low") is not None else row.get("low"))


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def forward_stats(
    ohlcv_rows: list[dict[str, Any]],
    signal_date: str,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    if not ohlcv_rows:
        return {
            "outcome_status": "ohlcv_snapshot_missing",
            "forward_returns": {f"{h}d": None for h in horizons},
            "future_drawdown_20d": None,
            "future_realized_vol_20d": None,
            "entry_close": None,
        }
    index = {_row_date(row): idx for idx, row in enumerate(ohlcv_rows)}
    if signal_date not in index:
        return {
            "outcome_status": "signal_date_missing_in_ohlcv",
            "forward_returns": {f"{h}d": None for h in horizons},
            "future_drawdown_20d": None,
            "future_realized_vol_20d": None,
            "entry_close": None,
        }
    start_idx = index[signal_date]
    entry_close = _close(ohlcv_rows[start_idx])
    if not entry_close:
        return {
            "outcome_status": "entry_close_missing",
            "forward_returns": {f"{h}d": None for h in horizons},
            "future_drawdown_20d": None,
            "future_realized_vol_20d": None,
            "entry_close": None,
        }

    returns: dict[str, float | None] = {}
    complete_horizons = 0
    for horizon in horizons:
        target_idx = start_idx + horizon
        if target_idx >= len(ohlcv_rows):
            returns[f"{horizon}d"] = None
            continue
        future_close = _close(ohlcv_rows[target_idx])
        returns[f"{horizon}d"] = round(future_close / entry_close - 1.0, 6) if future_close else None
        if returns[f"{horizon}d"] is not None:
            complete_horizons += 1

    end_idx = min(len(ohlcv_rows) - 1, start_idx + 20)
    future_slice = ohlcv_rows[start_idx + 1 : end_idx + 1]
    lows = [_low(row) for row in future_slice]
    lows = [value for value in lows if value is not None]
    drawdown = round(min(lows) / entry_close - 1.0, 6) if lows else None

    daily_returns = []
    prev = entry_close
    for row in future_slice:
        close = _close(row)
        if close is not None and prev:
            daily_returns.append(close / prev - 1.0)
            prev = close
    realized_vol = (
        round(statistics.pstdev(daily_returns) * math.sqrt(252), 6)
        if len(daily_returns) >= 2 else None
    )
    return {
        "outcome_status": "complete" if complete_horizons == len(horizons) else "partial_or_pending",
        "forward_returns": returns,
        "future_drawdown_20d": drawdown,
        "future_realized_vol_20d": realized_vol,
        "entry_close": round(entry_close, 6),
    }


def _candidate_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(row.get("candidate_source_section") for row in rows)
    covered = [row for row in rows if row.get("has_options_coverage")]
    liquid = [row for row in rows if row.get("option_liquidity_filter")]
    safe = [row for row in rows if row.get("pit_candidate_join_safe")]
    quality_usable = [
        row for row in rows
        if row.get("options_collection_quality_status") == "usable_for_shadow"
    ]
    quality_quarantined = [
        row for row in rows
        if row.get("options_collection_quality_status") == "quarantined"
    ]
    scoring_allowed = [row for row in rows if row.get("options_scoring_allowed")]
    squeeze = [row for row in rows if row.get("squeeze_overlay")]
    downside = [row for row in rows if row.get("downside_risk_overlay")]
    outcome_status = Counter(row.get("outcome_status") for row in rows)
    return {
        "candidate_count": len(rows),
        "source_section_counts": dict(source_counts),
        "options_covered_candidates": len(covered),
        "options_candidate_coverage_rate": round(len(covered) / len(rows), 6) if rows else 0.0,
        "option_liquidity_eligible_candidates": len(liquid),
        "pit_join_safe_candidates": len(safe),
        "pit_join_safe_rate": round(len(safe) / len(rows), 6) if rows else 0.0,
        "quality_usable_candidates": len(quality_usable),
        "quality_quarantined_candidates": len(quality_quarantined),
        "options_scoring_allowed_candidates": len(scoring_allowed),
        "squeeze_overlay_candidates": len(squeeze),
        "downside_risk_overlay_candidates": len(downside),
        "earnings_vol_overlay_candidates": sum(1 for row in rows if row.get("earnings_vol_overlay")),
        "outcome_status_counts": dict(outcome_status),
    }


def _quality_ratio(numerator: Any, denominator: Any) -> float:
    denominator_number = _float(denominator) or 0.0
    if denominator_number <= 0:
        return 0.0
    return round((_float(numerator) or 0.0) / denominator_number, 6)


def _collection_quality_gate(
    option_diagnostics: dict[str, Any],
    *,
    min_liquidity_pass_rate: float,
    min_liquid_tickers: int,
    min_market_rows_rate: float,
) -> dict[str, Any]:
    by_quote_date: dict[str, Any] = {}
    for quote_date, payload in (option_diagnostics.get("by_quote_date") or {}).items():
        rows = payload.get("rows") or 0
        tickers = payload.get("tickers") or 0
        pass_rate = _quality_ratio(payload.get("option_liquidity_pass_rows"), rows)
        bid_rate = _quality_ratio(payload.get("bid_gt_0_rows"), rows)
        ask_rate = _quality_ratio(payload.get("ask_gt_bid_rows"), rows)
        mid_rate = _quality_ratio(payload.get("mid_gt_0_rows"), rows)
        oi_rate = _quality_ratio(payload.get("open_interest_gt_0_rows"), rows)
        delta_rate = _quality_ratio(payload.get("delta_nonzero_rows"), rows)
        liquid_tickers = int(payload.get("liquid_tickers_ge_10_rows") or 0)

        reasons = []
        if rows <= 0:
            reasons.append("no_option_rows")
        if pass_rate < min_liquidity_pass_rate:
            reasons.append("liquidity_pass_rate_below_floor")
        if liquid_tickers < min_liquid_tickers:
            reasons.append("too_few_tickers_with_10_liquid_rows")
        if ask_rate < min_market_rows_rate or mid_rate < min_market_rows_rate:
            reasons.append("bid_ask_mid_market_rows_sparse")
        if oi_rate < min_market_rows_rate:
            reasons.append("open_interest_rows_sparse")
        if delta_rate < min_market_rows_rate:
            reasons.append("delta_rows_sparse")

        status = "quarantined" if reasons else "usable_for_shadow"
        by_quote_date[quote_date] = {
            "status": status,
            "scoring_allowed": status == "usable_for_shadow",
            "rows": rows,
            "tickers": tickers,
            "option_liquidity_pass_rows": payload.get("option_liquidity_pass_rows") or 0,
            "option_liquidity_pass_rate": pass_rate,
            "liquid_tickers_ge_10_rows": liquid_tickers,
            "bid_gt_0_rate": bid_rate,
            "ask_gt_bid_rate": ask_rate,
            "mid_gt_0_rate": mid_rate,
            "open_interest_gt_0_rate": oi_rate,
            "delta_nonzero_rate": delta_rate,
            "usable_trade_dates": payload.get("usable_trade_dates") or [],
            "reasons": reasons,
        }
    usable_dates = [
        quote_date for quote_date, payload in by_quote_date.items()
        if payload.get("status") == "usable_for_shadow"
    ]
    quarantined_dates = [
        quote_date for quote_date, payload in by_quote_date.items()
        if payload.get("status") == "quarantined"
    ]
    return {
        "parameters": {
            "min_liquidity_pass_rate": min_liquidity_pass_rate,
            "min_liquid_tickers": min_liquid_tickers,
            "min_market_rows_rate": min_market_rows_rate,
        },
        "by_quote_date": by_quote_date,
        "usable_quote_dates": usable_dates,
        "quarantined_quote_dates": quarantined_dates,
        "overall_status": "needs_more_forward_data" if not usable_dates else "usable_shadow_dates_present",
    }


def _liquidity_anomaly_report(option_diagnostics: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for quote_date, payload in (option_diagnostics.get("by_quote_date") or {}).items():
        rows = payload.get("rows") or 0
        liquid = payload.get("option_liquidity_pass_rows") or 0
        pass_rate = round(liquid / rows, 6) if rows else 0.0
        status = "ok"
        if rows and pass_rate < 0.05:
            status = "quarantine_recommended"
        report[quote_date] = {
            "rows": rows,
            "option_liquidity_pass_rows": liquid,
            "option_liquidity_pass_rate": pass_rate,
            "status": status,
            "reason": (
                "Liquidity pass rate below 5%; do not use overlay tags for candidate scoring."
                if status == "quarantine_recommended" else "Liquidity coverage is usable for shadow tagging."
            ),
        }
    return report


def _candidate_join_date_for_quote(
    quote_date: str,
    option_diagnostics: dict[str, Any],
    *,
    mode: str,
) -> str:
    if mode == "quote_date":
        return quote_date
    payload = (option_diagnostics.get("by_quote_date") or {}).get(quote_date) or {}
    usable_dates = payload.get("usable_trade_dates") or []
    return min(usable_dates) if usable_dates else quote_date


def _mean(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 6) if clean else None


def _win_rate(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(1 for value in clean if value > 0) / len(clean), 6) if clean else None


def _bucket_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "closed_5d_count": sum(1 for row in rows if row.get("forward_returns", {}).get("5d") is not None),
        "closed_10d_count": sum(1 for row in rows if row.get("forward_returns", {}).get("10d") is not None),
        "closed_20d_count": sum(1 for row in rows if row.get("forward_returns", {}).get("20d") is not None),
        "closed_60d_count": sum(1 for row in rows if row.get("forward_returns", {}).get("60d") is not None),
        "forward_5d_mean": _mean([row.get("forward_returns", {}).get("5d") for row in rows]),
        "forward_10d_mean": _mean([row.get("forward_returns", {}).get("10d") for row in rows]),
        "forward_20d_mean": _mean([row.get("forward_returns", {}).get("20d") for row in rows]),
        "forward_60d_mean": _mean([row.get("forward_returns", {}).get("60d") for row in rows]),
        "forward_20d_win_rate": _win_rate([row.get("forward_returns", {}).get("20d") for row in rows]),
        "future_drawdown_20d_mean": _mean([row.get("future_drawdown_20d") for row in rows]),
        "future_realized_vol_20d_mean": _mean([row.get("future_realized_vol_20d") for row in rows]),
    }


def _slot_conflict_value(rows: list[dict[str, Any]], tag_key: str) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("options_scoring_allowed"):
            by_day[str(row.get("candidate_action_date"))].append(row)

    diffs = []
    examples = []
    for day, day_rows in by_day.items():
        entered = [
            row for row in day_rows
            if row.get("decision") == "entered"
            and row.get("forward_returns", {}).get("20d") is not None
        ]
        tagged_not_entered = [
            row for row in day_rows
            if row.get("decision") != "entered"
            and row.get(tag_key)
            and row.get("forward_returns", {}).get("20d") is not None
        ]
        if not entered or not tagged_not_entered:
            continue
        entered_mean = _mean([row["forward_returns"]["20d"] for row in entered])
        if entered_mean is None:
            continue
        for row in tagged_not_entered:
            diff = round(row["forward_returns"]["20d"] - entered_mean, 6)
            diffs.append(diff)
            examples.append({
                "date": day,
                "ticker": row.get("ticker"),
                "tag": tag_key,
                "candidate_forward_20d": row.get("forward_returns", {}).get("20d"),
                "same_day_entered_forward_20d_mean": entered_mean,
                "slot_conflict_value_20d": diff,
            })
    return {
        "conflict_count": len(examples),
        "avg_slot_conflict_value_20d": _mean(diffs),
        "positive_conflict_fraction": _win_rate(diffs),
        "examples": examples[:20],
    }


def _outcome_close_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoring_allowed = [row for row in rows if row.get("options_scoring_allowed")]
    squeeze = [row for row in scoring_allowed if row.get("squeeze_overlay")]
    no_squeeze = [
        row for row in scoring_allowed
        if row.get("has_options_coverage") and not row.get("squeeze_overlay")
    ]
    downside = [row for row in scoring_allowed if row.get("downside_risk_overlay")]
    no_downside = [
        row for row in scoring_allowed
        if row.get("has_options_coverage") and not row.get("downside_risk_overlay")
    ]
    squeeze_metrics = _bucket_metrics(squeeze)
    no_squeeze_metrics = _bucket_metrics(no_squeeze)
    downside_metrics = _bucket_metrics(downside)
    no_downside_metrics = _bucket_metrics(no_downside)
    return {
        "all_scoring_allowed": _bucket_metrics(scoring_allowed),
        "squeeze_overlay": squeeze_metrics,
        "no_squeeze_overlay": no_squeeze_metrics,
        "downside_risk_overlay": downside_metrics,
        "no_downside_risk_overlay": no_downside_metrics,
        "squeeze_minus_no_squeeze_forward_20d": (
            round(squeeze_metrics["forward_20d_mean"] - no_squeeze_metrics["forward_20d_mean"], 6)
            if squeeze_metrics["forward_20d_mean"] is not None
            and no_squeeze_metrics["forward_20d_mean"] is not None else None
        ),
        "downside_minus_no_downside_forward_20d": (
            round(downside_metrics["forward_20d_mean"] - no_downside_metrics["forward_20d_mean"], 6)
            if downside_metrics["forward_20d_mean"] is not None
            and no_downside_metrics["forward_20d_mean"] is not None else None
        ),
        "slot_conflict": {
            "squeeze_overlay": _slot_conflict_value(rows, "squeeze_overlay"),
            "downside_risk_overlay": _slot_conflict_value(rows, "downside_risk_overlay"),
        },
    }


def build_ledger(args: argparse.Namespace) -> dict[str, Any]:
    selected_dates = {date_value for date_value in (args.date or [])}
    chain_files = discover_chain_files(_repo_path(args.chain_dir), selected_dates or None)
    option_rows_by_key, option_diagnostics = load_option_rows(chain_files)
    collection_quality_gate = _collection_quality_gate(
        option_diagnostics,
        min_liquidity_pass_rate=args.min_liquidity_pass_rate,
        min_liquid_tickers=args.min_liquid_tickers,
        min_market_rows_rate=args.min_market_rows_rate,
    )
    quote_dates = sorted({key[0] for key in option_rows_by_key})
    ohlcv = _load_ohlcv_snapshot(args.ohlcv_snapshot)

    ledger_rows: list[dict[str, Any]] = []
    candidate_diagnostics: dict[str, Any] = {}
    for quote_date in quote_dates:
        candidate_join_date = _candidate_join_date_for_quote(
            quote_date,
            option_diagnostics,
            mode=args.candidate_join_date_mode,
        )
        date_tag = candidate_join_date.replace("-", "")
        signal_file = _quant_signal_path(args.quant_signal_dir, date_tag)
        candidates, diagnostics = collect_candidates(signal_file, candidate_join_date)
        candidate_diagnostics[quote_date] = {
            **diagnostics,
            "options_quote_date": quote_date,
            "candidate_join_date": candidate_join_date,
            "candidate_join_date_mode": args.candidate_join_date_mode,
        }
        features = {}
        if signal_file.exists():
            features_payload = _read_json(signal_file).get("features") or {}
            features = features_payload if isinstance(features_payload, dict) else {}

        quality = (
            collection_quality_gate.get("by_quote_date", {}).get(quote_date)
            or {"status": "missing_quality_gate", "scoring_allowed": False, "reasons": ["missing_quality_gate"]}
        )
        for candidate in candidates:
            ticker = candidate["ticker"]
            rows = option_rows_by_key.get((quote_date, ticker), [])
            underlying_price = _feature_close(features, ticker)
            option_summary = summarize_option_structure(rows, underlying_price)
            pit_status = _pit_join_status(
                candidate.get("candidate_action_date"),
                option_summary.get("usable_trade_dates") or [],
            )
            stats = forward_stats(ohlcv.get(ticker, []), candidate["candidate_action_date"])
            options_scoring_allowed = bool(
                quality.get("scoring_allowed")
                and pit_status.get("pit_candidate_join_safe")
                and option_summary.get("option_liquidity_filter")
            )
            ledger_rows.append({
                "experiment_id": args.experiment_id,
                "ledger_schema_version": 2,
                "overlay_mode": "default_off_shadow_only",
                "options_source": "onclickmedia_options",
                "options_quote_date": quote_date,
                "candidate_join_date": candidate_join_date,
                "candidate_join_date_mode": args.candidate_join_date_mode,
                "options_collection_quality_status": quality.get("status"),
                "options_collection_quality_reasons": quality.get("reasons") or [],
                "options_collection_quality_gate": {
                    "min_liquidity_pass_rate": args.min_liquidity_pass_rate,
                    "min_liquid_tickers": args.min_liquid_tickers,
                    "min_market_rows_rate": args.min_market_rows_rate,
                },
                "underlying_price_from_quant_features": underlying_price,
                **candidate,
                **option_summary,
                **pit_status,
                **stats,
                "options_scoring_allowed": options_scoring_allowed,
                "production_impact": {
                    "shared_policy_changed": False,
                    "backtester_adapter_changed": False,
                    "run_adapter_changed": False,
                    "replay_only": True,
                    "production_signal_path_changed": False,
                },
            })

    output_dir = _repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "options_forward_candidate_ledger.jsonl"
    report_path = output_dir / "options_forward_candidate_ledger_report.json"
    quality_gate_path = output_dir / "options_collection_quality_gate.json"
    quarantined_path = output_dir / "options_quarantined_quote_dates.json"
    _write_jsonl(ledger_path, ledger_rows)
    _write_json(quality_gate_path, collection_quality_gate)
    _write_json(
        quarantined_path,
        {
            "experiment_id": args.experiment_id,
            "quarantined_quote_dates": collection_quality_gate.get("quarantined_quote_dates", []),
            "usable_quote_dates": collection_quality_gate.get("usable_quote_dates", []),
            "by_quote_date": collection_quality_gate.get("by_quote_date", {}),
        },
    )
    outcome_close_summary = _outcome_close_summary(ledger_rows)

    report = {
        "experiment_id": args.experiment_id,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "mode": "default_off_forward_options_candidate_tag_ledger",
        "hypothesis": (
            "Forward PIT-safe EOD options structure tags may explain candidate quality or slot "
            "conflicts only when attached to existing Ginger candidates."
        ),
        "single_causal_variable": "forward options ledger quality gate and usable-date outcome close only",
        "source_files": {
            "chain_files": option_diagnostics.get("chain_files", []),
            "quant_signal_dir": _repo_rel(args.quant_signal_dir),
            "ohlcv_snapshot": _repo_rel(args.ohlcv_snapshot) if args.ohlcv_snapshot else None,
        },
        "join_policy": {
            "candidate_join_date_mode": args.candidate_join_date_mode,
            "note": (
                "Default joins candidates on option usable_trade_date, not option quote_date, "
                "because EOD rows are not usable until the next trade date."
            ),
        },
        "option_diagnostics": option_diagnostics,
        "candidate_diagnostics": candidate_diagnostics,
        "collection_quality_gate": collection_quality_gate,
        "liquidity_anomaly_report": _liquidity_anomaly_report(option_diagnostics),
        "candidate_summary": _candidate_summary(ledger_rows),
        "by_options_quote_date": {
            quote_date: _candidate_summary([row for row in ledger_rows if row.get("options_quote_date") == quote_date])
            for quote_date in quote_dates
        },
        "outcome_close_summary": outcome_close_summary,
        "required_metrics": {
            "expected_value_score": None,
            "total_return": None,
            "total_pnl": None,
            "sharpe_daily": None,
            "max_drawdown": None,
            "win_rate": None,
            "trade_count": None,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "vs_spy": None,
            "vs_qqq": None,
            "candidate_count": len(ledger_rows),
            "overlap_with_existing_signals": len(ledger_rows),
            "scarce_slot_opportunity_cost": outcome_close_summary.get("slot_conflict"),
            "forward_return_of_tagged_candidates": {
                "squeeze_overlay": outcome_close_summary.get("squeeze_overlay"),
                "downside_risk_overlay": outcome_close_summary.get("downside_risk_overlay"),
            },
            "production_impact": "none_default_off_shadow_artifact_only",
        },
        "artifacts": {
            "ledger": _repo_rel(ledger_path),
            "report": _repo_rel(report_path),
            "quality_gate": _repo_rel(quality_gate_path),
            "quarantined_quote_dates": _repo_rel(quarantined_path),
        },
        "decision": "shadow_only",
        "next_minimum_action": (
            "Accumulate PIT-safe daily rows with nonzero candidate overlap and compute closed 5/10/20/60d outcomes."
        ),
    }
    _write_json(report_path, report)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", default=EXPERIMENT_ID)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--chain-dir", default=str(DEFAULT_CHAIN_DIR))
    parser.add_argument("--quant-signal-dir", default=str(DEFAULT_SIGNAL_DIR))
    parser.add_argument("--ohlcv-snapshot")
    parser.add_argument(
        "--candidate-join-date-mode",
        choices=("usable_trade_date", "quote_date"),
        default="usable_trade_date",
        help=(
            "Join options quote dates to candidate files by option usable_trade_date "
            "(default, PIT-safe) or quote_date (diagnostic legacy mode)."
        ),
    )
    parser.add_argument(
        "--min-liquidity-pass-rate",
        type=float,
        default=DEFAULT_MIN_LIQUIDITY_PASS_RATE,
        help="Minimum per-quote-date option_liquidity_pass row fraction before tags may be scored.",
    )
    parser.add_argument(
        "--min-liquid-tickers",
        type=int,
        default=DEFAULT_MIN_LIQUID_TICKERS,
        help="Minimum tickers with at least ten liquid option rows before a quote date may be scored.",
    )
    parser.add_argument(
        "--min-market-rows-rate",
        type=float,
        default=DEFAULT_MIN_MARKET_ROWS_RATE,
        help="Minimum row fraction with market/OI/Greek fields before a quote date may be scored.",
    )
    parser.add_argument(
        "--date",
        action="append",
        help="Option quote date to include as YYYY-MM-DD. May be repeated. Defaults to all local chain files.",
    )
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_arg_parser().parse_args(argv)
    report = build_ledger(args)
    print(json.dumps(report, indent=2, sort_keys=True, default=_json_default))
    return report


if __name__ == "__main__":
    main()
