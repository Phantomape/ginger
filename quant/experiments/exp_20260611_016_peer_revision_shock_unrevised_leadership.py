"""exp-20260611-016: peer revision shock unrevised leadership scout.

Replay-only alpha search. This tests one relation-aware free-data candidate
source: a PIT EPS-estimate upward revision in a correlated same-sector peer may
transfer information to an unrevised liquid peer that is beginning to lead
SPY on the signal day.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_029_analyst_revision_velocity_candidate_pool as revision_base  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import rolling_corr_peer_shock_paper_sleeve as rolling_peer  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260611-016"
STEM = "peer_revision_shock_unrevised_leadership"
TRIAL_FAMILY = "peer_revision_shock_unrevised_leadership_candidate_pool"
TRIAL_VARIANT_ID = "peer_revision_shock_unrevised_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "peer_revision_shock_unrevised_correlated_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_016_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = framework.BASE_NOTIONAL_USD
HOLD_DAYS = framework.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

REVISION_LOOKBACK_TRADING_DAYS = 20
MIN_PEER_EPS_ESTIMATE_REVISION_20D_PCT = 0.03
MIN_PEER_DAYS_TO_EARNINGS = 7.0
MAX_PEER_DAYS_TO_EARNINGS = 60.0
MIN_PEER_SURPRISE_HISTORY_COUNT = 4
MIN_PEER_POSITIVE_SURPRISE_COUNT = 3
MIN_PEER_POSITIVE_SURPRISE_RATIO = 0.75
MIN_PEER_AVG_HISTORICAL_SURPRISE_PCT = 0.0

MAX_CANDIDATE_OWN_REVISION_20D_PCT = 0.01
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MAX_CANDIDATE_SIGNAL_RETURN = 0.045
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.012
MIN_CANDIDATE_CLOSE_LOCATION = 0.55
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.03
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.30
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.75
MAX_CANDIDATE_REALIZED_VOL_20D = 0.09

CORRELATION_LOOKBACK_DAYS = 60
MIN_ROLLING_CORRELATION = 0.58
MAX_PEER_REVISION_ROWS_PER_DAY = 12
MAX_CANDIDATE_ROWS_PER_DAY = 60

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_REVISION_COMPARATOR = {
    "experiment_id": "exp-20260609-011",
    "aggregate_ev_delta": 0.1846,
    "aggregate_pnl_delta": 2893.75,
    "by_window": {
        "late_strong": {"ev": 0.1460, "pnl": 1425.44},
        "mid_weak": {"ev": 0.0189, "pnl": 689.36},
        "old_thin": {"ev": 0.0197, "pnl": 778.95},
    },
}

ACCEPTED_ROLLING_PEER_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "aggregate_ev_delta": 0.3845,
    "aggregate_pnl_delta": 6107.66,
    "by_window": {
        "late_strong": {"ev": 0.2167, "pnl": 2734.23},
        "mid_weak": {"ev": 0.1445, "pnl": 2622.62},
        "old_thin": {"ev": 0.0233, "pnl": 750.81},
    },
}

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "thin_revision_sample",
        "peer_relation_redundant_with_price_shock",
        "window_regression",
        "drawdown_drift",
        "accepted_relation_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Direct same-ticker revision persistence/acceleration failed or was sparse, "
        "while rolling-correlation peer shock is accepted; this tests a distinct "
        "revision-driven relation shock rather than another OHLCV or same-ticker "
        "revision threshold."
    ),
    "recorded_at": "2026-06-11T13:08:50+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_free_non_ohlcv": True,
    "uses_free_ohlcv_only": False,
    "uses_llm": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing OHLCV, revision snapshot, peer relation, or future bars rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result would need "
        "a shared default-off helper that computes the same PIT earnings-snapshot "
        "peer revision rows, sector/correlation relation, unrevised-candidate "
        "gate, next-open paper entry, 10-day exit, costs, cooldown, and "
        "concentration controls in both historical replay and daily snapshots "
        "before any report queue, paper ledger, ranking, sizing, watchlist, or "
        "order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _float(value: Any) -> float | None:
    return revision_base._float(value)


def _positive_surprise_stats(row: dict[str, Any]) -> dict[str, Any]:
    history = row.get("historical_surprise_pct") or []
    if not isinstance(history, list):
        history = []
    values = [_float(value) for value in history]
    valid = [value for value in values if value is not None]
    positive = [value for value in valid if value > 0.0]
    ratio = len(positive) / len(valid) if valid else 0.0
    return {
        "history_count": len(valid),
        "positive_count": len(positive),
        "positive_ratio": round(ratio, 6),
        "avg_historical_surprise_pct": _round(row.get("avg_historical_surprise_pct"), 6),
    }


def _snapshot_dates() -> list[str]:
    dates: set[str] = set()
    for directory in (revision_base.SNAPSHOT_DIR, revision_base.LEGACY_SNAPSHOT_DIR):
        for path in directory.glob("earnings_snapshot_*.json"):
            tag = path.stem[-8:]
            if len(tag) == 8 and tag.isdigit():
                dates.add(f"{tag[:4]}-{tag[4:6]}-{tag[6:]}")
    return sorted(dates)


def _load_revision_context(
    *,
    signal_dates: list[str],
    eligible_tickers: set[str],
) -> dict[str, Any]:
    all_dates = _snapshot_dates()
    path_by_date = {date: revision_base._snapshot_path(date) for date in all_dates}
    snapshot_by_date: dict[str, dict[str, Any]] = {}
    date_pos = {date: pos for pos, date in enumerate(all_dates)}
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    file_audit: list[dict[str, Any]] = []
    ticker_set = {ticker.upper() for ticker in eligible_tickers}

    for signal_date in signal_dates:
        pos = date_pos.get(signal_date)
        current_path = path_by_date.get(signal_date) or revision_base._snapshot_path(signal_date)
        if pos is None or current_path is None:
            file_audit.append(
                {
                    "date": signal_date,
                    "status": "missing_signal_snapshot",
                    "matched_revision_rows": 0,
                }
            )
            continue
        if pos < REVISION_LOOKBACK_TRADING_DAYS:
            file_audit.append(
                {
                    "date": signal_date,
                    "status": "missing_prior_snapshot_window",
                    "matched_revision_rows": 0,
                }
            )
            continue
        prior_date = all_dates[pos - REVISION_LOOKBACK_TRADING_DAYS]
        prior_path = path_by_date.get(prior_date) or revision_base._snapshot_path(prior_date)
        if prior_path is None:
            file_audit.append(
                {
                    "date": signal_date,
                    "prior_date": prior_date,
                    "status": "missing_prior_snapshot",
                    "matched_revision_rows": 0,
                }
            )
            continue
        current = snapshot_by_date.setdefault(signal_date, revision_base._load_snapshot(current_path))
        prior = snapshot_by_date.setdefault(prior_date, revision_base._load_snapshot(prior_path))
        matched = 0
        for ticker, current_row in current.items():
            ticker_u = str(ticker).upper()
            if ticker_u not in ticker_set:
                continue
            prior_row = prior.get(ticker_u)
            if not prior_row:
                continue
            current_estimate = _float(current_row.get("eps_estimate"))
            prior_estimate = _float(prior_row.get("eps_estimate"))
            if current_estimate is None or prior_estimate is None or prior_estimate == 0:
                continue
            revision = (current_estimate - prior_estimate) / abs(prior_estimate)
            if not math.isfinite(revision):
                continue
            stats = _positive_surprise_stats(current_row)
            matched += 1
            rows_by_date_ticker.setdefault(signal_date, {})[ticker_u] = {
                "ticker": ticker_u,
                "signal_date": signal_date,
                "current_snapshot": _repo_rel(current_path),
                "prior_snapshot": _repo_rel(prior_path),
                "prior_snapshot_date": prior_date,
                "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_current": _round(current_estimate, 6),
                "eps_estimate_prior": _round(prior_estimate, 6),
                "eps_estimate_revision_20d_pct": _round(revision, 6),
                "days_to_earnings": _round(current_row.get("days_to_earnings"), 2),
                **stats,
            }
        file_audit.append(
            {
                "date": signal_date,
                "prior_date": prior_date,
                "status": "ok",
                "snapshot_path": _repo_rel(current_path),
                "prior_snapshot_path": _repo_rel(prior_path),
                "matched_revision_rows": matched,
            }
        )
    return {
        "rows_by_date_ticker": rows_by_date_ticker,
        "files": file_audit,
    }


def _peer_revision_pass(row: dict[str, Any]) -> bool:
    revision = _float(row.get("eps_estimate_revision_20d_pct"))
    days_to_earnings = _float(row.get("days_to_earnings"))
    avg_surprise = _float(row.get("avg_historical_surprise_pct"))
    if revision is None or revision < MIN_PEER_EPS_ESTIMATE_REVISION_20D_PCT:
        return False
    if days_to_earnings is None:
        return False
    if not (MIN_PEER_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_PEER_DAYS_TO_EARNINGS):
        return False
    if int(row.get("history_count") or 0) < MIN_PEER_SURPRISE_HISTORY_COUNT:
        return False
    if int(row.get("positive_count") or 0) < MIN_PEER_POSITIVE_SURPRISE_COUNT:
        return False
    if float(row.get("positive_ratio") or 0.0) < MIN_PEER_POSITIVE_SURPRISE_RATIO:
        return False
    if avg_surprise is None or avg_surprise < MIN_PEER_AVG_HISTORICAL_SURPRISE_PCT:
        return False
    return True


def _daily_return(snapshot: dict[str, list[dict[str, Any]]], ticker: str, date: str) -> float | None:
    rows = framework.shadow._series(snapshot, ticker)
    idx = framework.shadow._row_index(rows).get(date)
    if idx is None:
        return None
    return framework._daily_return(rows, idx)


def _peer_rows_for_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    revision_rows: dict[str, dict[str, Any]],
    signal_date: str,
) -> list[dict[str, Any]]:
    spy_ret = _daily_return(snapshot, "SPY", signal_date)
    if spy_ret is None:
        return []
    peers: list[dict[str, Any]] = []
    for ticker, rev_row in revision_rows.items():
        if ticker not in sector_entries or ticker not in snapshot:
            continue
        if not _peer_revision_pass(rev_row):
            continue
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        close = framework._value(rows[idx], "Close")
        if close is None or close < MIN_PRICE:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        signal_return = framework._daily_return(rows, idx)
        if signal_return is None:
            continue
        ret20 = framework._ret(rows, idx, 20)
        spy_rows = snapshot.get("SPY") or []
        spy_idx = indices.get("SPY", {}).get(signal_date)
        spy_ret20 = framework._ret(spy_rows, spy_idx, 20) if spy_idx is not None else None
        ret20_excess_spy = (ret20 - spy_ret20) if ret20 is not None and spy_ret20 is not None else 0.0
        volume_ratio = framework._volume_ratio(rows, idx) or 0.0
        meta = sector_entries[ticker]
        peer_score = (
            12.0 * float(rev_row["eps_estimate_revision_20d_pct"])
            + 0.15 * float(rev_row.get("positive_ratio") or 0.0)
            + 1.4 * (signal_return - spy_ret)
            + 0.20 * ret20_excess_spy
            + 0.03 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        )
        peers.append(
            {
                "peer_ticker": ticker,
                "peer_score": _round(peer_score, 6),
                "peer_signal_day_return": _round(signal_return, 6),
                "peer_relative_vs_spy": _round(signal_return - spy_ret, 6),
                "peer_ret20_excess_spy": _round(ret20_excess_spy, 6),
                "peer_volume_ratio_20d": _round(volume_ratio, 6),
                "peer_avg_dollar_volume_20d": _round(adv20, 2),
                "peer_sector": meta.get("sector"),
                "peer_industry": meta.get("industry"),
                "peer_revision": rev_row,
            }
        )
    peers.sort(
        key=lambda row: (
            -float(row["peer_score"]),
            -float(row["peer_revision"]["eps_estimate_revision_20d_pct"]),
            -float(row["peer_avg_dollar_volume_20d"]),
            row["peer_ticker"],
        )
    )
    return peers[:MAX_PEER_REVISION_ROWS_PER_DAY]


def _candidate_for_peer(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    revision_rows: dict[str, dict[str, Any]],
    all_dates: list[str],
    signal_date: str,
    peer: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    peer_ticker = str(peer["peer_ticker"])
    if ticker == peer_ticker or ticker not in snapshot:
        return None
    meta = sector_entries.get(ticker)
    if not meta:
        return None
    if meta.get("sector") != peer.get("peer_sector"):
        return None
    candidate_revision = revision_rows.get(ticker)
    own_revision = _float(
        candidate_revision.get("eps_estimate_revision_20d_pct")
        if candidate_revision
        else None
    )
    if own_revision is not None and own_revision > MAX_CANDIDATE_OWN_REVISION_20D_PCT:
        return None

    date_pos = {date_value: pos for pos, date_value in enumerate(all_dates)}
    pos = date_pos.get(signal_date)
    if pos is None or pos < CORRELATION_LOOKBACK_DAYS:
        return None
    prior_dates = all_dates[pos - CORRELATION_LOOKBACK_DAYS : pos]
    peer_vector = rolling_peer._prior_return_vector_for_dates(
        rows_by_ticker=snapshot,
        indices=indices,
        ticker=peer_ticker,
        prior_dates=prior_dates,
    )
    candidate_vector = rolling_peer._prior_return_vector_for_dates(
        rows_by_ticker=snapshot,
        indices=indices,
        ticker=ticker,
        prior_dates=prior_dates,
    )
    if peer_vector is None or candidate_vector is None:
        return None
    corr = rolling_peer._pearson_corr(peer_vector, candidate_vector)
    if corr is None or corr < MIN_ROLLING_CORRELATION:
        return None

    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 20 or spy_idx < 20:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_return is None:
        return None
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    relative_vs_spy = signal_return - spy_return
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    close_location = framework._close_location(rows[idx])
    if close_location is None or close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret20_excess_spy > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None

    same_industry = bool(meta.get("industry") and meta.get("industry") == peer.get("peer_industry"))
    own_revision_penalty = max(own_revision or 0.0, 0.0)
    score = (
        1.70 * corr
        + 10.0 * float(peer["peer_revision"]["eps_estimate_revision_20d_pct"])
        + 1.90 * relative_vs_spy
        + 0.55 * close_location
        + 0.30 * ret20_excess_spy
        + 0.05 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        + (0.08 if same_industry else 0.0)
        - 3.0 * own_revision_penalty
        - 0.35 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "PEER_REVISION_SHOCK_UNREVISED_LEADERSHIP_PAPER",
        "candidate_score": _round(score, 6),
        "candidate_signal_day_return": _round(signal_return, 6),
        "candidate_relative_vs_spy": _round(relative_vs_spy, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_own_revision_20d_pct": _round(own_revision, 6),
        "candidate_revision_bucket": (
            "missing_or_uncovered_revision_row"
            if candidate_revision is None
            else "flat_or_negative_revision"
            if (own_revision or 0.0) <= 0.0
            else "small_positive_below_peer_gate"
        ),
        "rolling_corr_60d": _round(corr, 6),
        "same_sector_as_peer": True,
        "same_industry_as_peer": same_industry,
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "peer_ticker": peer_ticker,
        "peer_score": peer["peer_score"],
        "peer_signal_day_return": peer["peer_signal_day_return"],
        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
        "peer_sector": peer.get("peer_sector"),
        "peer_industry": peer.get("peer_industry"),
        "peer_revision": peer["peer_revision"],
        "rule_version": RULE_VERSION,
        "uses_free_non_ohlcv": True,
        "uses_free_ohlcv_only": False,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    revision_context = _load_revision_context(
        signal_dates=dates,
        eligible_tickers=set(snapshot).intersection(sector_entries),
    )
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    all_dates = framework.shadow._trading_dates(snapshot)

    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_revision_context": 0,
        "days_with_peer_revision_shock": 0,
        "days_with_candidate_rows": 0,
        "raw_peer_revision_rows": 0,
        "raw_candidate_rows": 0,
        "revision_file_audit_sample": revision_context["files"][:50],
        "peer_revision_threshold": MIN_PEER_EPS_ESTIMATE_REVISION_20D_PCT,
        "candidate_unrevised_max_revision": MAX_CANDIDATE_OWN_REVISION_20D_PCT,
        "min_rolling_correlation": MIN_ROLLING_CORRELATION,
    }
    for signal_date in dates:
        revision_rows = rows_by_date_ticker.get(signal_date, {})
        if not revision_rows:
            continue
        scan["days_with_revision_context"] += 1
        peer_rows = _peer_rows_for_date(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            revision_rows=revision_rows,
            signal_date=signal_date,
        )
        if not peer_rows:
            continue
        scan["days_with_peer_revision_shock"] += 1
        scan["raw_peer_revision_rows"] += len(peer_rows)
        day_rows: list[dict[str, Any]] = []
        core_entries = entries_by_date.get(signal_date, [])
        for peer in peer_rows:
            for ticker in sector_entries:
                row = _candidate_for_peer(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    revision_rows=revision_rows,
                    all_dates=all_dates,
                    signal_date=signal_date,
                    peer=peer,
                    ticker=ticker,
                )
                if row is None:
                    continue
                row["same_day_ab_entry_count"] = len(core_entries)
                row["same_day_ab_overlap"] = bool(core_entries)
                row["same_ticker_ab_overlap"] = any(
                    str(entry.get("ticker") or "").upper() == row["ticker"]
                    for entry in core_entries
                )
                if core_entries:
                    row["candidate_score"] = _round(float(row["candidate_score"]) + 0.04, 6)
                    row["core_flow_anchor_present"] = True
                else:
                    row["core_flow_anchor_present"] = False
                day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                row["date"],
                -float(row["candidate_score"]),
                -float(row["rolling_corr_60d"]),
                -float(row["candidate_relative_vs_spy"]),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_CANDIDATE_ROWS_PER_DAY]
        candidates.extend(day_rows)
        scan["days_with_candidate_rows"] += 1
        scan["raw_candidate_rows"] += len(day_rows)
        contexts.append(
            {
                "date": signal_date,
                "peer_revision_rows": len(peer_rows),
                "candidate_rows": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_peer_revision_20d_pct": day_rows[0]["peer_revision"][
                    "eps_estimate_revision_20d_pct"
                ],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "core_flow_anchor_present": day_rows[0]["core_flow_anchor_present"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["rolling_corr_60d"]),
            -float(row["candidate_relative_vs_spy"]),
            row["ticker"],
        )
    )
    return candidates, contexts, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    framework.sleeve.STEM = STEM
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = framework.sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _comparator_gate(delta_by_window: dict[str, dict[str, Any]], aggregate: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    for name, comparator in (
        ("accepted_revision", ACCEPTED_REVISION_COMPARATOR),
        ("accepted_rolling_peer", ACCEPTED_ROLLING_PEER_COMPARATOR),
    ):
        if aggregate["expected_value_score_delta_sum"] <= comparator["aggregate_ev_delta"]:
            failed.append(f"{name}_aggregate_ev_not_beaten")
        if aggregate["total_pnl_delta_sum"] <= comparator["aggregate_pnl_delta"]:
            failed.append(f"{name}_aggregate_pnl_not_beaten")
        for label, comp in comparator["by_window"].items():
            delta = delta_by_window.get(label, {})
            if float(delta.get("expected_value_score") or 0.0) <= float(comp["ev"]):
                failed.append(f"{name}_{label}_ev_not_beaten")
            if float(delta.get("total_pnl") or 0.0) <= float(comp["pnl"]):
                failed.append(f"{name}_{label}_pnl_not_beaten")
    return {
        "passed": not failed,
        "failed_reasons": failed,
        "accepted_revision_comparator": ACCEPTED_REVISION_COMPARATOR,
        "accepted_rolling_peer_comparator": ACCEPTED_ROLLING_PEER_COMPARATOR,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    delta_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    comparator = _comparator_gate(delta_by_window, aggregate)
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_regressed"] > 0:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"] > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if not comparator["passed"]:
        failed.extend(comparator["failed_reasons"])
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_peer_revision_shock_unrevised_leadership"
            if passed
            else "rejected_peer_revision_shock_unrevised_leadership_candidate_pool"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "comparator_gate": comparator,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries_all = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and peer-revision relation replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        contexts_by_window[label] = contexts
        scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": len({row["date"] for row in candidates}),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    delta_by_window = OrderedDict((label, row["delta"]) for label, row in window_rows.items())
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        delta_by_window=delta_by_window,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Positive PIT EPS-estimate revisions in a correlated same-sector peer "
            "may transfer information to unrevised liquid peers that start showing "
            "SPY-relative leadership, creating a replayable free-data candidate-pool "
            "edge without adding noise tickers."
        ),
        "change_type": "replay_only_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260609-011",
            "exp-20260610-025",
            "exp-20260606-025",
            "exp-20260529-011",
            "exp-20260602-019",
            "exp-20260609-024",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_pit_estimate_revision_peer_relation",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only peer-revision relation default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "earnings_snapshot_source": _repo_rel(revision_base.SNAPSHOT_DIR),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only PIT earnings snapshots and signal-date close OHLCV "
                "available before next open. Paper entry is next available open with "
                "existing entry slippage; exit is the close 10 trading days after the "
                "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
            "min_peer_eps_estimate_revision_20d_pct": MIN_PEER_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_peer_days_to_earnings": MIN_PEER_DAYS_TO_EARNINGS,
            "max_peer_days_to_earnings": MAX_PEER_DAYS_TO_EARNINGS,
            "max_candidate_own_revision_20d_pct": MAX_CANDIDATE_OWN_REVISION_20D_PCT,
            "min_rolling_correlation": MIN_ROLLING_CORRELATION,
            "correlation_lookback_days": CORRELATION_LOOKBACK_DAYS,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/relation alpha: a peer's PIT upward EPS estimate "
                "revision can be a fresh expectation shock. A same-sector, "
                "rolling-correlated peer that has not itself revised but is starting "
                "to outperform SPY may underreact into the next 10 trading days."
            ),
            "2_history_check": {
                "exp-20260609-011": (
                    "Accepted same-ticker revision+surprise low-extension helper: "
                    "EV +0.1846, PnL +$2,893.75. This run must beat it."
                ),
                "exp-20260610-025": (
                    "Rejected 7d acceleration/residual-leadership same-ticker "
                    "revision variant: EV -0.0487, PnL -$1,186.35, 16 trades."
                ),
                "exp-20260606-025": (
                    "Accepted rolling-correlation peer shock helper: EV +0.3845, "
                    "PnL +$6,107.66. This run must beat it as the relation comparator."
                ),
                "exp-20260529-011/exp-20260602-019": (
                    "SEC/earnings same-sector peer-transfer variants failed or were "
                    "not sufficient. This run uses PIT analyst-revision shock plus "
                    "rolling correlation instead of generic same-sector transfer."
                ),
                "exp-20260609-024": (
                    "Early peer earnings sympathy was rejected; this run avoids an "
                    "earnings-calendar timing retry and uses revision shock rows."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Must improve "
                "aggregate EV/PnL, have no EV/PnL regression window, pass "
                "sample/survival/drawdown/concentration gates, and beat both "
                "accepted revision and accepted rolling-peer comparators aggregate "
                "and per-window."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260611_016_peer_revision_shock_unrevised_leadership.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "data/daily/snapshots/earnings/*.json eps_estimate",
                "data/daily/snapshots/earnings/*.json days_to_earnings",
                "data/daily/snapshots/earnings/*.json historical_surprise_pct",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The peer-revision "
                "candidate source is additive default-off paper, so core signals "
                "generated/survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": delta_by_window,
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": scan_by_window,
        "peer_revision_contexts_by_window": contexts_by_window,
        "peer_revision_context_samples_by_window": OrderedDict(
            (label, rows[:25]) for label, rows in contexts_by_window.items()
        ),
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The peer-revision relation source cleared the strict comparator gate "
            "as a replay-only/default-off lead; no production surface was promoted."
            if gate4["passed"]
            else (
                "The peer-revision relation source did not clear Gate 4 or the "
                "accepted revision/rolling-peer comparators. Do not promote or "
                "retune this fixed peer-revision relation on the same frozen windows."
            )
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "If rejected, likely causes are sparse PIT revision shocks, "
                "revision information already captured by same-ticker revision or "
                "price peer-shock helpers, or candidate rows displacing stronger "
                "accepted relation rows after costs."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping peer revision threshold, own-revision "
                "threshold, correlation, relative-strength, top-N, notional, hold, "
                "or cooldown on the same frozen windows."
            ),
            "new_evidence_required": (
                "Retry only with materially richer PIT analyst fields such as "
                "analyst-count trajectory, revenue revision, broker breadth, or "
                "closed forward replacement-value rows."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Context days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {ctx} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                ctx=len(payload["peer_revision_contexts_by_window"][label]),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Peer Revision Shock Unrevised Leadership",
            "",
            f"- decision: `{payload['decision']}`",
            "- aggregate EV: `{:.4f}` -> `{:.4f}` ({:+.4f})".format(
                aggregate["baseline_expected_value_score_sum"],
                aggregate["after_expected_value_score_sum"],
                aggregate["expected_value_score_delta_sum"],
            ),
            "- aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- failed gates: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "- numeric Gate 4 passed: `{}`".format(payload["gate4"]["passed"]),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Conclusion",
            "",
            payload["interpretation"],
            "",
            "Production impact: replay-only/default-off paper. No shared helper, production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "mechanism_family": "analyst_revision_expectation_trajectory",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "peer_revision_context_day_count": len(
                    payload["peer_revision_contexts_by_window"][label]
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": payload["pre_run_questions"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "analyst_revision_expectation_trajectory",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )

    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
