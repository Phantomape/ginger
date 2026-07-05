"""Default-off SEC 8-K Item 1.01 issuer-self contract-relation paper sleeve.

Shared helper for exp-20260703-019. It promotes the fixed exp-20260703-018
observed-only rule into one reusable default-off paper boundary:

    Use the observer-only SEC Item 1.01 contract-relation provenance rows,
    keep only specific relation phrases, dedupe to one relation row per
    accession by fixed priority, select top-1 accession per usable trade date,
    enter at the first available open on or after the usable trade date, and
    exit at the 10th trading-session close.

The helper emits candidates, paper ledger state, and attribution metadata only.
It never emits live orders and never changes core signal generation, ranking,
sizing, exits, LLM, or news behavior (``trade_enabled=False``).
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT, atomic_write_text
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from volume_breadth_breakout_paper_sleeve import (
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT, atomic_write_text
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.volume_breadth_breakout_paper_sleeve import (
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "SEC_ITEM101_CONTRACT_RELATION_ISSUER_SELF_PAPER"
RULE_VERSION = "sec_item101_contract_relation_issuer_self_top1_v1"
SOURCE_RULE_VERSION = "sec_contract_relation_provenance_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_RELATION_ROWS_PATH = (
    DATA_ROOT / "non_ohlcv" / "sec_contract_relation_provenance" / "rows.jsonl"
)
DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "sec_item101_contract_relation_issuer_self" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "sec_item101_contract_relation_issuer_self"
    / "snapshots.jsonl"
)

RELATION_PRIORITY = {
    "customer_or_revenue_contract": 1,
    "supplier_or_supply_contract": 2,
    "license_or_collaboration_agreement": 3,
    "purchase_or_sales_agreement": 4,
    "credit_or_financing_agreement": 5,
    "lease_or_real_estate_agreement": 6,
    "general_material_agreement": 7,
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_sec_item101_contract_relation_rows(
    path: Path | str = DEFAULT_RELATION_ROWS_PATH,
) -> list[dict[str, Any]]:
    rows_path = Path(path)
    if not rows_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with rows_path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return normalise_relation_rows(rows)


def normalise_relation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("relation_quality") != "specific_relation_phrase":
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        accession = str(row.get("accession_number") or "").strip()
        usable = _date10(row.get("usable_trade_date") or row.get("filing_date"))
        bucket = str(row.get("relation_bucket") or "")
        if not ticker or not accession or not usable or bucket not in RELATION_PRIORITY:
            continue
        out.append(
            {
                **row,
                "ticker": ticker,
                "accession_number": accession,
                "usable_trade_date": usable,
                "relation_bucket": bucket,
                "relation_quality": "specific_relation_phrase",
                "evidence_phrase_count": int(row.get("evidence_phrase_count") or 0),
                "counterparty_candidates": list(row.get("counterparty_candidates") or []),
            }
        )
    out.sort(key=provenance_rank)
    return out


def provenance_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        RELATION_PRIORITY.get(str(row.get("relation_bucket") or ""), 99),
        -int(row.get("evidence_phrase_count") or 0),
        0 if row.get("counterparty_candidates") else 1,
        str(row.get("accepted_at") or ""),
        str(row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
    )


def dedupe_accessions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_accession: dict[str, dict[str, Any]] = {}
    for row in normalise_relation_rows(rows):
        accession = str(row.get("accession_number") or "")
        current = by_accession.get(accession)
        if current is None or provenance_rank(row) < provenance_rank(current):
            by_accession[accession] = row
    return sorted(by_accession.values(), key=provenance_rank)


def build_sec_item101_contract_relation_candidates(
    *,
    relation_rows: list[dict[str, Any]],
    as_of: str,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The ONE fixed candidate rule for this sleeve (rule_version above)."""
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rejects: dict[str, int] = {}
    day_rows = [
        row
        for row in dedupe_accessions(relation_rows)
        if row.get("usable_trade_date") == as_of_date
    ]
    if not day_rows:
        return [], {"no_relation_rows_asof": 1}
    selected = sorted(day_rows, key=provenance_rank)[: int(cfg["daily_entry_slots"])]
    candidates = []
    for row in selected:
        candidates.append(
            {
                "sleeve": SLEEVE_NAME,
                "ticker": row["ticker"],
                "date": as_of_date,
                "signal_date": as_of_date,
                "strategy": "sec_item101_contract_relation_issuer_self_candidate_pool",
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "score": 1.0 / RELATION_PRIORITY[row["relation_bucket"]],
                "relation_bucket": row["relation_bucket"],
                "relation_priority": RELATION_PRIORITY[row["relation_bucket"]],
                "relation_quality": row["relation_quality"],
                "evidence_phrase_count": row["evidence_phrase_count"],
                "counterparty_candidate_count": len(row.get("counterparty_candidates") or []),
                "counterparty_candidates": row.get("counterparty_candidates") or [],
                "accession_number": row.get("accession_number"),
                "accepted_at": row.get("accepted_at"),
                "filing_date": row.get("filing_date"),
                "usable_trade_date": row.get("usable_trade_date"),
                "source_text_hash16": row.get("source_text_hash16"),
                "pit_caveat": row.get("pit_caveat"),
                "known_at": "sec_accepted_at_mapped_to_usable_trade_date",
                "intended_notional": float(cfg["paper_notional_usd"]),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    rejects["daily_top1_limit"] = max(0, len(day_rows) - len(candidates))
    return candidates, rejects


def replay_sec_item101_contract_relation_paper_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    relation_rows: list[dict[str, Any]] | None = None,
    start: str,
    end: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    relation_rows = normalise_relation_rows(
        relation_rows if relation_rows is not None else load_sec_item101_contract_relation_rows()
    )
    selected_by_day: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for row in dedupe_accessions(relation_rows):
        day = str(row.get("usable_trade_date") or "")
        if not (start <= day <= end):
            continue
        candidate = {
            "date": day,
            "signal_date": day,
            **row,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "strategy": "sec_item101_contract_relation_issuer_self_candidate_pool",
            "trade_enabled": False,
            "alters_orders": False,
            "intended_notional": float(cfg["paper_notional_usd"]),
        }
        current = selected_by_day.get(day)
        if current is None or provenance_rank(candidate) < provenance_rank(current):
            if current is not None:
                rejected.append({**current, "filter_reason": "daily_top1_limit"})
            selected_by_day[day] = candidate
        else:
            rejected.append({**candidate, "filter_reason": "daily_top1_limit"})

    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for candidate in sorted(selected_by_day.values(), key=lambda row: row["signal_date"]):
        ticker = str(candidate.get("ticker") or "").upper()
        ticker_rows = rows_by_ticker.get(ticker) or []
        entry_idx = _first_index_on_or_after(ticker_rows, candidate["signal_date"])
        if entry_idx is None:
            unsettled.append({**candidate, "unsettled_reason": "no_entry_bar"})
            continue
        entry_bar = ticker_rows[entry_idx]
        entry_date = str(entry_bar.get("date") or "")
        if not (start <= entry_date <= end):
            unsettled.append({**candidate, "unsettled_reason": "entry_outside_window"})
            continue
        exit_idx = entry_idx + int(cfg["hold_days"]) - 1
        if exit_idx >= len(ticker_rows):
            unsettled.append({**candidate, "entry_date": entry_date, "unsettled_reason": "exit_outside_window"})
            continue
        exit_bar = ticker_rows[exit_idx]
        exit_date = str(exit_bar.get("date") or "")
        if exit_date > end:
            unsettled.append({**candidate, "entry_date": entry_date, "exit_date": exit_date, "unsettled_reason": "exit_outside_window"})
            continue
        entry_raw = _float_or_none(entry_bar.get("open"))
        exit_raw = _float_or_none(exit_bar.get("close"))
        if entry_raw is None or exit_raw is None or entry_raw <= 0 or exit_raw <= 0:
            unsettled.append({**candidate, "entry_date": entry_date, "exit_date": exit_date, "unsettled_reason": "missing_price"})
            continue
        entry_price = apply_entry_fill(entry_raw)
        exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
        pnl = float(cfg["paper_notional_usd"]) * pnl_pct_net
        trades.append(
            {
                **candidate,
                "ticker": ticker,
                "signal_date": candidate["signal_date"],
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_raw_open": round(entry_raw, 4),
                "exit_raw_close": round(exit_raw, 4),
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "hold_days": int(cfg["hold_days"]),
                "paper_notional_usd": float(cfg["paper_notional_usd"]),
                "pnl_pct_net": round(pnl_pct_net, 6),
                "pnl": round(pnl, 2),
            }
        )

    return {
        "rule_version": RULE_VERSION,
        "trades": trades,
        "unsettled": unsettled,
        "filtered": rejected,
        "signal_dates_with_candidates": len(selected_by_day),
        "max_daily_candidate_count": 1 if selected_by_day else 0,
        "reject_totals": _count_reasons(rejected),
        "source_row_count": len(relation_rows),
    }


def empty_sec_item101_contract_relation_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_sec_item101_contract_relation_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_sec_item101_contract_relation_paper_state()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return empty_sec_item101_contract_relation_paper_state()
    state = empty_sec_item101_contract_relation_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_sec_item101_contract_relation_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state["updated_at"] = utc_now_iso()
    atomic_write_text(json.dumps(_safe(state), indent=2, sort_keys=True) + "\n", Path(path))


def append_sec_item101_contract_relation_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_sec_item101_contract_relation_paper_sleeve_snapshot(
    as_of: str, reason: str
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "data_source": {"status": reason, "relation_row_count": 0},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_sec_item101_contract_relation_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    relation_rows: list[dict[str, Any]] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    try:
        from us_market_calendar import is_us_equity_session
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.us_market_calendar import is_us_equity_session

    if not is_us_equity_session(as_of_date):
        return empty_sec_item101_contract_relation_paper_sleeve_snapshot(
            as_of_date, "non_us_equity_session"
        )
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_sec_item101_contract_relation_paper_sleeve_snapshot(
            as_of_date, "missing_ohlcv"
        )

    relation_rows = normalise_relation_rows(
        relation_rows if relation_rows is not None else load_sec_item101_contract_relation_rows()
    )
    working_state = deepcopy(
        state
        if state is not None
        else load_sec_item101_contract_relation_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    closed_today = _advance_open_positions(
        working_state, as_of=as_of_date, current_prices=current, config=cfg
    )
    filled_today, skipped_today = _fill_pending_entries(
        working_state,
        as_of=as_of_date,
        open_prices=opens,
        current_prices=current,
        config=cfg,
    )

    candidates, reject_counts = build_sec_item101_contract_relation_candidates(
        relation_rows=relation_rows,
        as_of=as_of_date,
        config=cfg,
    )

    open_positions = working_state.get("open_positions") or []
    existing_open_tickers = {str(row.get("ticker") or "").upper() for row in open_positions}
    pending_entries = working_state.get("pending_entries") or []
    existing_decision_ids = {str(row.get("decision_id") or "") for row in pending_entries}
    pending_tickers = {str(row.get("ticker") or "").upper() for row in pending_entries}
    pending_for_asof = sum(
        1 for row in pending_entries if str(row.get("created_asof") or "") == as_of_date
    )
    slots_left = max(0, int(cfg["daily_entry_slots"]) - pending_for_asof)
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))

    new_pending: list[dict[str, Any]] = []
    for candidate in candidates:
        if slots_left <= 0 or room <= 0:
            break
        ticker = str(candidate.get("ticker") or "").upper()
        decision_id = f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of_date}:{ticker}:{candidate.get('accession_number')}"
        if decision_id in existing_decision_ids:
            _inc(reject_counts, "duplicate_same_day_decision")
            continue
        if ticker in existing_open_tickers or ticker in pending_tickers:
            _inc(reject_counts, "already_open_or_pending")
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "created_asof": as_of_date,
            "status": "pending_next_open",
            "notional": float(candidate.get("intended_notional") or cfg["paper_notional_usd"]),
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
            "alters_orders": False,
        }
        working_state["pending_entries"].append(entry)
        new_pending.append(entry)
        existing_decision_ids.add(decision_id)
        pending_tickers.add(ticker)
        slots_left -= 1
        room -= 1

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["paper_enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(candidates[: int(cfg["daily_entry_slots"])]),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": sum(reject_counts.values()),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2
        ),
        "data_source": {
            "status": "ok",
            "relation_row_count": len(relation_rows),
            "asof_relation_row_count": sum(
                1 for row in relation_rows if row.get("usable_trade_date") == as_of_date
            ),
        },
        "candidate_reject_counts": dict(sorted(reject_counts.items())),
        "candidates": _safe(candidates[: int(cfg["daily_entry_slots"])]),
        "new_pending_entries": _safe(new_pending),
        "filled_entries_today": _safe(filled_today),
        "skipped_entries_today": _safe(skipped_today),
        "closed_positions_today": _safe(closed_today),
        "open_positions": _safe(open_positions),
        "pending_entries": _safe(working_state.get("pending_entries") or []),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
    }

    if persist:
        save_sec_item101_contract_relation_paper_state(working_state, state_path)
        append_sec_item101_contract_relation_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def prep_and_build_sec_item101_contract_relation_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict,
    spy_ohlcv=None,
    open_prices=None,
    current_prices=None,
):
    ohlcv = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_sec_item101_contract_relation_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        open_prices=open_prices,
        current_prices=current_prices,
    )


def _first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date") or "") >= day:
            return index
    return None


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        current_price = current_prices.get(ticker)
        if current_price is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = current_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            exit_mark,
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_mark,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_mark,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                }
            )
            closed_today.append(closed)
            state["closed_positions"].append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return closed_today


def _fill_pending_entries(
    state: dict[str, Any],
    *,
    as_of: str,
    open_prices: dict[str, float],
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    still_pending: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sorted(
        state.get("pending_entries") or [],
        key=lambda row: (str(row.get("created_asof") or ""), str(row.get("ticker") or "")),
    ):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").upper()
        if str(entry.get("created_asof") or "") >= as_of:
            still_pending.append(entry)
            continue
        open_price = open_prices.get(ticker)
        if open_price is None:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_missing_next_open",
                    "skipped_asof": as_of,
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        entry_price = apply_entry_fill(open_price)
        notional = _float_or_none(entry.get("notional")) or float(config["paper_notional_usd"])
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "sec_item101_contract_relation_issuer_self_candidate_pool",
            "entry_date": as_of,
            "entry_price": entry_price,
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 0,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker) and entry_price:
            position["unrealized_pnl"] = _pnl(
                entry_price,
                apply_slippage(current_prices[ticker], SLIPPAGE_BPS_TARGET, "sell"),
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    top5_share = _top5_positive_share(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions)
        >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl", True)
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_top5_positive_share": top5_share is not None
        and top5_share <= float(config["forward_gate_max_top5_positive_share"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed_positions),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "top5_positive_share": top5_share,
        },
        "trade_enabled_after_gate": False,
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _count_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        _inc(counts, str(row.get("filter_reason") or "unknown"))
    return dict(sorted(counts.items()))


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "parity_rule": "shared_sec_item101_contract_relation_paper_adapter_v1",
    }
