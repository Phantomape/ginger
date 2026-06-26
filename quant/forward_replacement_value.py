"""Cost-adjusted replacement-value enrichment for closed forward paper-sleeve rows.

exp-20260608-021 found that every default-off paper sleeve fails the
``replacement_value_rows_present`` activation check because closed forward rows
never record what the same notional would have earned in a cash or liquid ETF
substitute over the same holding window. This module repairs that measurement
surface only. It is read-side enrichment: it never creates, removes, ranks,
sizes, or exits a position, and it never changes orders.

Comparator convention (fixed, recorded on every enriched row):

- comparator deploys the same notional in SPY and QQQ;
- comparator entry fill is the ETF open on ``entry_date`` with buy-side
  ``SLIPPAGE_BPS_ENTRY`` slippage (matching the sleeves' next-open entry);
- comparator exit fill is the ETF close on ``exit_date`` with sell-side
  ``SLIPPAGE_BPS_TARGET`` slippage;
- ``ROUND_TRIP_COST_PCT`` of notional is subtracted, matching sleeve cost
  handling;
- cash comparator earns zero, so replacement value versus cash equals the
  recorded paper pnl.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from datetime import date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT, atomic_write_json
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )
    from regime_chop_state import (
        RULE_VERSION as REGIME_CHOP_RULE_VERSION,
        regime_chop_from_spy_universe,
    )
except ImportError:  # pragma: no cover - package-style import fallback
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT, atomic_write_json
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from quant.ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )
    from quant.regime_chop_state import (
        RULE_VERSION as REGIME_CHOP_RULE_VERSION,
        regime_chop_from_spy_universe,
    )


RULE_VERSION = "forward_replacement_value_v1"
ENTRY_REGIME_TAG_RULE_VERSION = "forward_replacement_entry_regime_tag_v1"
ENTRY_SHORT_VOLUME_TAG_RULE_VERSION = "forward_replacement_entry_short_volume_tag_v1"
COMPARATOR_TICKERS = ("SPY", "QQQ")
ARTIFACT_RELPATH = Path("paper_sleeves") / "forward_replacement_value.jsonl"

# Entry-time moomoo daily short_volume_ratio percentile tag (informed-flow
# avoidance signal, Diether-Lee-Werner 2009). Constants mirror exp-20260625-018
# exactly so the forward tag is parity-consistent with the attribution that
# established the lead; do not retune these here. The broad 51-name archive was
# built by exp-20260623-008. The tag is read-only PIT context: it never creates,
# ranks, sizes, or exits a position, and the only admissible use is validating a
# soft short-flow tilt on closed forward rows out of sample (exp-20260625-019).
SHORT_VOLUME_ARCHIVE_RELPATH = (
    Path("non_ohlcv") / "moomoo_daily_short_volume_broad" / "rows.jsonl"
)
SHORT_VOLUME_MIN_TRAILING_OBS = 30
SHORT_VOLUME_QUINTILES = 5
SHORT_VOLUME_TOXIC_QUINTILE_INDEX = 4  # 0-based; Q5 (>= 0.80 percentile) is toxic

# Plausible bounds for a derived paper notional; outside this range the
# derivation is treated as failed rather than silently recorded.
MIN_PLAUSIBLE_NOTIONAL_USD = 500.0
MAX_PLAUSIBLE_NOTIONAL_USD = 2_000_000.0
MAX_COMPARATOR_SESSION_RESOLUTION_GAP_DAYS = 4

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "default_off_attribution_only": True,
    "entry_regime_tagging_only": True,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}


def _to_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_comparator_bars(warehouse_path=None, tickers=COMPARATOR_TICKERS):
    """Load daily open/close bars for comparator ETFs from the OHLCV warehouse."""
    path = Path(warehouse_path) if warehouse_path else Path(DEFAULT_WAREHOUSE_PATH)
    bars = {ticker: {} for ticker in tickers}
    if not path.exists() and not hot_path_for(path).exists():
        return bars
    # Overlay-aware: comparator ETFs are refreshed daily into the hot tier, so
    # recent open/close bars live there rather than in the cold base.
    con = connect_overlay_reader(path)
    try:
        cur = con.cursor()
        marks = ",".join("?" for _ in tickers)
        cur.execute(
            "SELECT ticker, date, open, close FROM ohlcv_overlay WHERE ticker IN ("
            + marks
            + ")",
            list(tickers),
        )
        for ticker, date, open_px, close_px in cur.fetchall():
            open_f = _to_float(open_px)
            close_f = _to_float(close_px)
            if open_f is None or close_f is None:
                continue
            bars[str(ticker)][str(date)] = {"open": open_f, "close": close_f}
    finally:
        con.close()
    return bars


def load_regime_spy_bars(warehouse_path=None):
    """Load PIT SPY bars used only for entry-time regime attribution."""
    path = Path(warehouse_path) if warehouse_path else Path(DEFAULT_WAREHOUSE_PATH)
    if not path.exists() and not hot_path_for(path).exists():
        return []
    con = connect_overlay_reader(path)
    rows = []
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT date, high, close FROM ohlcv_overlay "
            "WHERE ticker = ? ORDER BY date",
            ["SPY"],
        )
        for bar_date, high_px, close_px in cur.fetchall():
            close_f = _to_float(close_px)
            if close_f is None:
                continue
            high_f = _to_float(high_px)
            rows.append(
                {
                    "Date": str(bar_date),
                    "Close": close_f,
                    "High": high_f if high_f is not None else close_f,
                }
            )
    finally:
        con.close()
    return rows


def load_short_volume_percentile_index(archive_path=None):
    """Build an expanding (strictly-prior) per-ticker percentile index of moomoo
    daily ``short_volume_ratio`` from the broad archive.

    Returns ``{ticker: (sorted_activity_dates, percentiles)}`` where ``percentiles[i]``
    is the fraction of strictly-prior observations for that ticker whose
    ``short_volume_ratio`` was below ``short_volume_ratio[i]`` (or ``None`` until
    ``SHORT_VOLUME_MIN_TRAILING_OBS`` history exists). This reproduces the PIT
    percentile construction of exp-20260625-018 so the entry-time tag matches the
    attribution surface. Returns ``{}`` if the archive is absent.
    """
    path = (
        Path(archive_path)
        if archive_path
        else DATA_ROOT / SHORT_VOLUME_ARCHIVE_RELPATH
    )
    if not path.exists():
        return {}
    by_ticker: dict[str, list[tuple[str, float]]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ticker = str(row.get("ticker") or "").upper()
        svr = _to_float(row.get("short_volume_ratio"))
        activity_date = str(row.get("activity_date") or "")[:10]
        if not ticker or svr is None or not activity_date:
            continue
        by_ticker.setdefault(ticker, []).append((activity_date, svr))

    index: dict[str, tuple[list[str], list[float | None]]] = {}
    for ticker, seq in by_ticker.items():
        seq.sort()
        dates = [d for d, _ in seq]
        pcts: list[float | None] = []
        hist: list[float] = []
        for _, svr in seq:
            if len(hist) >= SHORT_VOLUME_MIN_TRAILING_OBS:
                pcts.append(sum(1 for h in hist if h < svr) / len(hist))
            else:
                pcts.append(None)
            hist.append(svr)
        index[ticker] = (dates, pcts)
    return index


def _short_volume_percentile_asof(index, ticker, entry_date):
    """Most recent formed short_volume_ratio percentile from an activity_date
    STRICTLY before ``entry_date`` (the moomoo activity is published after the US
    close, so an activity_date equal to the next-open entry date is not yet known).
    """
    series = index.get(str(ticker or "").upper())
    if not series:
        return None
    dates, pcts = series
    i = bisect_left(dates, str(entry_date)) - 1
    while i >= 0:
        if pcts[i] is not None:
            return pcts[i]
        i -= 1
    return None


def _short_volume_quintile(pct):
    return min(
        SHORT_VOLUME_QUINTILES - 1, int(float(pct) * SHORT_VOLUME_QUINTILES)
    )


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _resolve_bar(bars, requested_date, *, prefer="exact_or_next"):
    requested = str(requested_date or "")
    if not requested:
        return None, None, "missing_requested_date"
    if requested in bars:
        return requested, bars[requested], "exact"

    requested_dt = _parse_date(requested)
    if requested_dt is None:
        return None, None, "invalid_requested_date"

    dates = sorted(bars)
    if not dates:
        return None, None, "missing_bars"

    idx = bisect_left(dates, requested)
    candidates = []
    if prefer in ("exact_or_previous", "nearest") and idx > 0:
        candidates.append(("previous_session", dates[idx - 1]))
    if prefer in ("exact_or_next", "nearest") and idx < len(dates):
        candidates.append(("next_session", dates[idx]))
    if prefer == "exact_or_next" and idx > 0:
        candidates.append(("previous_session_fallback", dates[idx - 1]))
    if prefer == "exact_or_previous" and idx < len(dates):
        candidates.append(("next_session_fallback", dates[idx]))

    best = None
    for resolution, resolved in candidates:
        resolved_dt = _parse_date(resolved)
        if resolved_dt is None:
            continue
        gap_days = abs((resolved_dt - requested_dt).days)
        if gap_days > MAX_COMPARATOR_SESSION_RESOLUTION_GAP_DAYS:
            continue
        candidate = (gap_days, resolution, resolved)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return None, None, "missing_nearby_session"
    gap_days, resolution, resolved = best
    return resolved, bars[resolved], resolution


def _row_needs_replacement_refresh(row):
    if not row.get("replacement_value_rule_version"):
        return True
    if row.get("replacement_value_status") != "missing_comparator_bars":
        return False
    return any(
        row.get("replacement_value_vs_" + ticker.lower() + "_usd") is None
        for ticker in COMPARATOR_TICKERS
    )


def _row_needs_entry_regime_tag(row):
    if row.get("entry_regime_tag_rule_version") != ENTRY_REGIME_TAG_RULE_VERSION:
        return True
    return row.get("entry_regime_status") in {
        "missing_spy_bars",
        "insufficient_lookback",
    }


def _apply_entry_regime_tag(row, regime_spy_bars):
    entry_date = str(row.get("entry_date") or "")[:10]
    if not entry_date:
        tag = {
            "rule_version": REGIME_CHOP_RULE_VERSION,
            "regime_label": "unknown",
            "coverage": "missing_entry_date",
            "exposure_scalar": 1.0,
        }
    elif not regime_spy_bars:
        tag = {
            "rule_version": REGIME_CHOP_RULE_VERSION,
            "regime_label": "unknown",
            "coverage": "missing_spy_bars",
            "exposure_scalar": 1.0,
        }
    else:
        tag = regime_chop_from_spy_universe(regime_spy_bars, entry_date)

    row["entry_regime_tag_rule_version"] = ENTRY_REGIME_TAG_RULE_VERSION
    row["entry_regime_rule_version"] = REGIME_CHOP_RULE_VERSION
    row["entry_regime_asof_date"] = entry_date or None
    row["entry_regime_status"] = tag.get("coverage")
    row["entry_regime_label"] = tag.get("regime_label")
    row["entry_regime_p_risk_on_trend"] = tag.get("p_risk_on_trend")
    row["entry_regime_p_choppy_range"] = tag.get("p_choppy_range")
    row["entry_regime_p_risk_off_stress"] = tag.get("p_risk_off_stress")
    row["entry_regime_exposure_scalar"] = tag.get("exposure_scalar")
    row["entry_regime_detail"] = tag


def _row_needs_short_volume_tag(row):
    if row.get("entry_short_volume_tag_rule_version") != ENTRY_SHORT_VOLUME_TAG_RULE_VERSION:
        return True
    # Refresh rows that previously had no joinable history once the archive grows
    # coverage (a new ticker or backfilled earlier dates can form a percentile).
    return row.get("entry_short_volume_status") in {
        "no_short_volume_history",
        "missing_index",
    }


def _apply_short_volume_tag(row, sv_percentile_index):
    entry_date = str(row.get("entry_date") or "")[:10]
    ticker = str(row.get("ticker") or "")
    percentile = None
    quintile = None
    toxic = None
    if not entry_date:
        status = "missing_entry_date"
    elif not sv_percentile_index:
        status = "missing_index"
    else:
        percentile = _short_volume_percentile_asof(
            sv_percentile_index, ticker, entry_date
        )
        if percentile is None:
            status = "no_short_volume_history"
        else:
            status = "ok"
            quintile = _short_volume_quintile(percentile) + 1  # 1-based for readers
            toxic = (quintile - 1) == SHORT_VOLUME_TOXIC_QUINTILE_INDEX

    row["entry_short_volume_tag_rule_version"] = ENTRY_SHORT_VOLUME_TAG_RULE_VERSION
    row["entry_short_volume_asof_date"] = entry_date or None
    row["entry_short_volume_status"] = status
    row["entry_short_volume_ratio_percentile"] = (
        round(percentile, 6) if percentile is not None else None
    )
    row["entry_short_volume_quintile"] = quintile
    row["entry_short_volume_toxic_flag"] = toxic


def _notional_for_row(row):
    """Best-effort recovery of the paper notional behind a closed row."""
    for key in ("notional_usd", "paper_notional_usd"):
        explicit = _to_float(row.get(key))
        if explicit and explicit > 0:
            return explicit, "explicit"

    pnl = _to_float(row.get("pnl"))
    entry_price = _to_float(row.get("entry_price"))
    exit_price = _to_float(row.get("exit_price"))
    price_net_ret = None
    if entry_price and exit_price and entry_price > 0:
        price_net_ret = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT

    net_return = _to_float(row.get("net_return_pct"))
    if pnl is not None and pnl != 0 and net_return not in (None, 0.0):
        candidates = []  # (|interpretation - price reference|, notional, label)
        for interp_ret, label in ((net_return / 100.0, "percent"), (net_return, "fraction")):
            if interp_ret == 0:
                continue
            notional = pnl / interp_ret
            if not (MIN_PLAUSIBLE_NOTIONAL_USD <= notional <= MAX_PLAUSIBLE_NOTIONAL_USD):
                continue
            if price_net_ret is not None:
                distance = abs(interp_ret - price_net_ret)
            else:
                # Without prices prefer the percent interpretation, the
                # dominant convention across event sleeves.
                distance = 0.0 if label == "percent" else 1.0
            candidates.append((distance, notional, label))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            _, notional, label = candidates[0]
            return round(notional, 2), "derived_from_net_return_" + label

    if pnl is not None and pnl != 0 and price_net_ret is not None:
        if abs(price_net_ret) > 1e-6:
            notional = pnl / price_net_ret
            if MIN_PLAUSIBLE_NOTIONAL_USD <= notional <= MAX_PLAUSIBLE_NOTIONAL_USD:
                return round(notional, 2), "derived_from_prices"

    return None, "missing"


def _comparator_pnl(
    bars,
    entry_date,
    exit_date,
    notional,
    *,
    entry_prefer="exact_or_next",
    exit_prefer="exact_or_previous",
):
    entry_resolved, entry_bar, entry_resolution = _resolve_bar(
        bars, entry_date, prefer=entry_prefer
    )
    exit_resolved, exit_bar, exit_resolution = _resolve_bar(
        bars, exit_date, prefer=exit_prefer
    )
    if not entry_bar or not exit_bar:
        return None
    entry_fill = apply_slippage(entry_bar["open"], SLIPPAGE_BPS_ENTRY, "buy")
    exit_fill = apply_slippage(exit_bar["close"], SLIPPAGE_BPS_TARGET, "sell")
    if not entry_fill or entry_fill <= 0 or exit_fill is None:
        return None
    gross = (exit_fill / entry_fill) - 1.0
    pnl = notional * gross - notional * ROUND_TRIP_COST_PCT
    return {
        "requested_entry_date": entry_date,
        "entry_date": entry_resolved,
        "entry_date_resolution": entry_resolution,
        "entry_fill": round(entry_fill, 4),
        "requested_exit_date": exit_date,
        "exit_date": exit_resolved,
        "exit_date_resolution": exit_resolution,
        "exit_fill": round(exit_fill, 4),
        "net_pnl_usd": round(pnl, 2),
    }


def _closed_rows(state):
    for key in ("closed_positions", "closed_trades"):
        rows = state.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def replacement_artifact_key(record):
    """Stable identity for one closed forward replacement-value row."""
    return (
        str(record.get("sleeve_key") or ""),
        str(record.get("decision_id") or ""),
        str(record.get("ticker") or ""),
        str(record.get("entry_date") or ""),
        str(record.get("exit_date") or ""),
    )


def _state_row_key(sleeve_key, row):
    return (
        str(sleeve_key or ""),
        str(row.get("decision_id") or ""),
        str(row.get("ticker") or ""),
        str(row.get("entry_date") or ""),
        str(row.get("exit_date") or row.get("entry_date") or ""),
    )


def _record_from_state_row(row, sleeve_key):
    if not row.get("replacement_value_rule_version"):
        return None
    pnl = _to_float(row.get("pnl_usd") if row.get("pnl_usd") is not None else row.get("pnl"))
    entry_date = str(row.get("entry_date") or "")
    exit_date = str(row.get("exit_date") or row.get("entry_date") or "")
    return {
        "rule_version": row.get("replacement_value_rule_version") or RULE_VERSION,
        "asof_date": row.get("replacement_value_asof"),
        "sleeve_key": sleeve_key,
        "decision_id": row.get("decision_id"),
        "ticker": row.get("ticker"),
        "entry_date": entry_date or None,
        "exit_date": exit_date or None,
        "pnl_usd": round(pnl, 2) if pnl is not None else None,
        "notional_usd": row.get("replacement_value_notional_usd"),
        "notional_method": row.get("replacement_value_notional_method"),
        "status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
        "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
        "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
        "comparator_detail": row.get("replacement_value_comparator_detail"),
        "entry_regime_tag_rule_version": row.get("entry_regime_tag_rule_version"),
        "entry_regime_rule_version": row.get("entry_regime_rule_version"),
        "entry_regime_asof_date": row.get("entry_regime_asof_date"),
        "entry_regime_status": row.get("entry_regime_status"),
        "entry_regime_label": row.get("entry_regime_label"),
        "entry_regime_p_risk_on_trend": row.get("entry_regime_p_risk_on_trend"),
        "entry_regime_p_choppy_range": row.get("entry_regime_p_choppy_range"),
        "entry_regime_p_risk_off_stress": row.get("entry_regime_p_risk_off_stress"),
        "entry_regime_exposure_scalar": row.get("entry_regime_exposure_scalar"),
        "entry_regime_detail": row.get("entry_regime_detail"),
        "entry_short_volume_tag_rule_version": row.get(
            "entry_short_volume_tag_rule_version"
        ),
        "entry_short_volume_asof_date": row.get("entry_short_volume_asof_date"),
        "entry_short_volume_status": row.get("entry_short_volume_status"),
        "entry_short_volume_ratio_percentile": row.get(
            "entry_short_volume_ratio_percentile"
        ),
        "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
        "entry_short_volume_toxic_flag": row.get("entry_short_volume_toxic_flag"),
    }


def _read_jsonl_records(path):
    rows = []
    path = Path(path)
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def current_state_replacement_records(sleeves_root=None):
    """Return canonical replacement-value rows from current sleeve state files."""
    root = Path(sleeves_root) if sleeves_root else DATA_ROOT / "paper_sleeves"
    records = []
    skipped_missing_replacement = []
    if not root.is_dir():
        return records, skipped_missing_replacement
    for state_path in sorted(root.glob("*/state.json")):
        sleeve_key = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in _closed_rows(state):
            record = _record_from_state_row(row, sleeve_key)
            if record is None:
                skipped_missing_replacement.append(
                    {
                        "sleeve_key": sleeve_key,
                        "decision_id": row.get("decision_id"),
                        "ticker": row.get("ticker"),
                        "entry_date": row.get("entry_date"),
                        "exit_date": row.get("exit_date"),
                    }
                )
                continue
            records.append(record)
    records.sort(key=replacement_artifact_key)
    return records, skipped_missing_replacement


def _write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def rebuild_current_state_artifact(
    *,
    sleeves_root=None,
    artifact_path=None,
    archive_path=None,
):
    """Materialize the shared artifact from current sleeve state.

    This keeps ``forward_replacement_value.jsonl`` as the canonical current
    per-sleeve accumulation surface instead of an append-only file that can
    retain rows later quarantined from state.
    """
    root = Path(sleeves_root) if sleeves_root else DATA_ROOT / "paper_sleeves"
    artifact = Path(artifact_path) if artifact_path else DATA_ROOT / ARTIFACT_RELPATH
    previous_records = _read_jsonl_records(artifact)
    if archive_path and artifact.exists():
        archive = Path(archive_path)
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")

    current_records, skipped_missing_replacement = current_state_replacement_records(root)
    current_keys = {replacement_artifact_key(record) for record in current_records}
    previous_rows_not_in_current_state = [
        {
            "sleeve_key": record.get("sleeve_key"),
            "decision_id": record.get("decision_id"),
            "ticker": record.get("ticker"),
            "entry_date": record.get("entry_date"),
            "exit_date": record.get("exit_date"),
            "status": record.get("status"),
        }
        for record in previous_records
        if replacement_artifact_key(record) not in current_keys
    ]

    _write_jsonl(artifact, current_records)

    rows_by_status = {}
    rows_by_sleeve = {}
    rows_by_entry_regime_label = {}
    rows_with_entry_regime = 0
    rows_with_entry_short_volume = 0
    rows_by_entry_short_volume_quintile = {}
    rows_entry_short_volume_toxic = 0
    for record in current_records:
        status = str(record.get("status") or "unknown")
        sleeve_key = str(record.get("sleeve_key") or "unknown")
        rows_by_status[status] = rows_by_status.get(status, 0) + 1
        rows_by_sleeve[sleeve_key] = rows_by_sleeve.get(sleeve_key, 0) + 1
        label = record.get("entry_regime_label")
        if label:
            rows_with_entry_regime += 1
            rows_by_entry_regime_label[str(label)] = (
                rows_by_entry_regime_label.get(str(label), 0) + 1
            )
        if record.get("entry_short_volume_status") == "ok":
            rows_with_entry_short_volume += 1
            quintile = record.get("entry_short_volume_quintile")
            if quintile is not None:
                key = f"Q{quintile}"
                rows_by_entry_short_volume_quintile[key] = (
                    rows_by_entry_short_volume_quintile.get(key, 0) + 1
                )
            if record.get("entry_short_volume_toxic_flag"):
                rows_entry_short_volume_toxic += 1

    return {
        "status": "ok",
        "artifact_path": str(artifact),
        "previous_rows": len(previous_records),
        "rows_written": len(current_records),
        "rows_by_status": rows_by_status,
        "rows_by_sleeve": rows_by_sleeve,
        "rows_with_entry_regime": rows_with_entry_regime,
        "rows_by_entry_regime_label": rows_by_entry_regime_label,
        "rows_with_entry_short_volume": rows_with_entry_short_volume,
        "rows_by_entry_short_volume_quintile": rows_by_entry_short_volume_quintile,
        "rows_entry_short_volume_toxic": rows_entry_short_volume_toxic,
        "previous_rows_not_in_current_state": previous_rows_not_in_current_state,
        "skipped_missing_replacement": skipped_missing_replacement,
    }


def enrich_state_closed_rows(
    state,
    bars_by_ticker,
    asof_date,
    sleeve_key="",
    *,
    regime_spy_bars=None,
    sv_percentile_index=None,
):
    """Add replacement-value fields to closed rows that lack them.

    Mutates ``state`` in place and returns one artifact record per newly
    updated row. Rows already carrying replacement-value, entry-regime, and
    entry-short-volume tag fields are left untouched, so the pass is idempotent.
    """
    records = []
    for row in _closed_rows(state):
        updated = False
        if _row_needs_replacement_refresh(row):
            pnl = _to_float(row.get("pnl"))
            entry_date = str(row.get("entry_date") or "")
            exit_date = str(row.get("exit_date") or row.get("entry_date") or "")
            notional, notional_method = _notional_for_row(row)
            entry_prefer = (
                "exact_or_previous" if row.get("non_session_entry_fill") else "exact_or_next"
            )

            status = "enriched"
            comparators = {}
            if pnl is None or not entry_date or not exit_date:
                status = "missing_row_fields"
            elif notional is None:
                status = "missing_notional"
            else:
                for ticker in COMPARATOR_TICKERS:
                    comparators[ticker] = _comparator_pnl(
                        bars_by_ticker.get(ticker, {}),
                        entry_date,
                        exit_date,
                        notional,
                        entry_prefer=entry_prefer,
                    )
                if any(detail is None for detail in comparators.values()):
                    status = "missing_comparator_bars"

            row["replacement_value_rule_version"] = RULE_VERSION
            row["replacement_value_asof"] = asof_date
            row["replacement_value_status"] = status
            row["replacement_value_notional_usd"] = notional
            row["replacement_value_notional_method"] = notional_method
            row["replacement_value_vs_cash_usd"] = round(pnl, 2) if pnl is not None else None
            for ticker in COMPARATOR_TICKERS:
                detail = comparators.get(ticker)
                field = "replacement_value_vs_" + ticker.lower() + "_usd"
                if pnl is not None and detail is not None:
                    row[field] = round(pnl - detail["net_pnl_usd"], 2)
                else:
                    row[field] = None
            row["replacement_value_comparator_detail"] = comparators
            updated = True

        if regime_spy_bars is not None and _row_needs_entry_regime_tag(row):
            _apply_entry_regime_tag(row, regime_spy_bars)
            updated = True

        if sv_percentile_index is not None and _row_needs_short_volume_tag(row):
            _apply_short_volume_tag(row, sv_percentile_index)
            updated = True

        if updated:
            record = _record_from_state_row(row, sleeve_key)
            if record is not None:
                records.append(record)
    return records


def enrich_all_sleeve_states(
    asof_date,
    *,
    sleeves_root=None,
    bars_by_ticker=None,
    regime_spy_bars=None,
    sv_percentile_index=None,
    warehouse_path=None,
    artifact_path=None,
):
    """Enrich every ``data/paper_sleeves/*/state.json`` closed row in place.

    The shared JSONL artifact is then rebuilt from current state so rows later
    quarantined from a sleeve cannot remain in activation evidence. Safe to
    call repeatedly per day.
    """
    root = Path(sleeves_root) if sleeves_root else DATA_ROOT / "paper_sleeves"
    artifact = Path(artifact_path) if artifact_path else DATA_ROOT / ARTIFACT_RELPATH
    load_from_warehouse = bars_by_ticker is None
    if bars_by_ticker is None:
        bars_by_ticker = load_comparator_bars(warehouse_path)
    if regime_spy_bars is None and load_from_warehouse:
        regime_spy_bars = load_regime_spy_bars(warehouse_path)
    if sv_percentile_index is None and load_from_warehouse:
        sv_percentile_index = load_short_volume_percentile_index()

    summary = {
        "rule_version": RULE_VERSION,
        "entry_regime_tag_rule_version": ENTRY_REGIME_TAG_RULE_VERSION,
        "entry_short_volume_tag_rule_version": ENTRY_SHORT_VOLUME_TAG_RULE_VERSION,
        "asof_date": asof_date,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_impact": dict(PRODUCTION_IMPACT),
        "entry_regime_tagging_enabled": regime_spy_bars is not None,
        "entry_short_volume_tagging_enabled": sv_percentile_index is not None,
        "sleeves_scanned": 0,
        "rows_enriched": 0,
        "rows_enriched_by_status": {},
        "sleeves": {},
    }
    if not root.is_dir():
        summary["status"] = "no_sleeves_root"
        return summary

    new_records = []
    for state_path in sorted(root.glob("*/state.json")):
        sleeve_key = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary["sleeves"][sleeve_key] = {"status": "unreadable_state"}
            continue
        summary["sleeves_scanned"] += 1
        records = enrich_state_closed_rows(
            state,
            bars_by_ticker,
            asof_date,
            sleeve_key,
            regime_spy_bars=regime_spy_bars,
            sv_percentile_index=sv_percentile_index,
        )
        if records:
            atomic_write_json(state, state_path)
            new_records.extend(records)
        summary["sleeves"][sleeve_key] = {
            "rows_enriched": len(records),
            "statuses": sorted({record["status"] for record in records}),
        }

    artifact_summary = rebuild_current_state_artifact(
        sleeves_root=root,
        artifact_path=artifact,
    )
    summary["rows_enriched"] = len(new_records)
    by_status = {}
    for record in new_records:
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
    summary["rows_enriched_by_status"] = by_status
    summary["artifact_rows"] = artifact_summary["rows_written"]
    summary["artifact_rows_by_status"] = artifact_summary["rows_by_status"]
    summary["artifact_rows_with_entry_regime"] = artifact_summary[
        "rows_with_entry_regime"
    ]
    summary["artifact_rows_by_entry_regime_label"] = artifact_summary[
        "rows_by_entry_regime_label"
    ]
    summary["artifact_rows_with_entry_short_volume"] = artifact_summary[
        "rows_with_entry_short_volume"
    ]
    summary["artifact_rows_by_entry_short_volume_quintile"] = artifact_summary[
        "rows_by_entry_short_volume_quintile"
    ]
    summary["artifact_rows_entry_short_volume_toxic"] = artifact_summary[
        "rows_entry_short_volume_toxic"
    ]
    summary["artifact_previous_rows_not_in_current_state"] = len(
        artifact_summary["previous_rows_not_in_current_state"]
    )
    summary["artifact_path"] = str(artifact)
    summary["status"] = "ok"
    return summary
