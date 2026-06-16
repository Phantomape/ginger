"""exp-20260615-024: CEO/CFO Form 4 buys plus low-liability confirmation.

Replay-only private scout. This tests a fixed role-quality + fundamental
confirmation bundle after broad clustered Form 4 and owner-conviction Form 4
variants failed. No production path, live orders, ranking, sizing, exits,
shared policy, or LLM/news path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)


EXP_ID = "exp-20260615-024"
STEM = "form4_ceo_cfo_low_liability"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
ROLE_JSON = OUT_DIR / f"{STEM}_role_only_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
CANDIDATES_JSONL = OUT_DIR / f"{STEM}_candidates.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

BROAD_FORM4_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260614-018"
    / "form4_open_market_purchases_broad_20240802_20260615.jsonl"
)
COMPANYFACTS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_companyfacts_selected_kova_20260614.jsonl"

LOW_LIABILITY_ASSETS_MAX = 0.35
MIN_ROLE_PURCHASE_VALUE = 0.0
EXCLUDE_10B5_1 = True

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _date10(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else ""


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _window_name(day: str) -> str | None:
    day = _date10(day)
    for label, window in WINDOWS.items():
        if window["start"] <= day <= window["end"]:
            return label
    return None


def _price_map_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in frames.items():
        rows: list[dict[str, Any]] = []
        for day, row in frame.iterrows():
            rows.append(
                {
                    "date": str(day.date()),
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        prices[ticker] = rows
    return prices


def _is_president_title(title: str) -> bool:
    text = title.lower()
    if "president" not in text:
        return False
    if re.search(r"\b(vp|svp|evp)\b", text):
        return False
    return "vice president" not in text and "senior vice president" not in text


def _is_ceo_cfo_or_president(row: dict[str, Any]) -> bool:
    title = str(row.get("officer_title") or row.get("owner_title") or "")
    lowered = title.lower()
    return bool(
        row.get("is_ceo")
        or row.get("is_cfo")
        or re.search(r"\bceo\b", lowered)
        or re.search(r"\bcfo\b", lowered)
        or "chief executive" in lowered
        or "chief financial" in lowered
        or _is_president_title(title)
    )


def _role_label(row: dict[str, Any]) -> str:
    title = str(row.get("officer_title") or row.get("owner_title") or "").strip()
    lowered = title.lower()
    if row.get("is_ceo") or re.search(r"\bceo\b", lowered) or "chief executive" in lowered:
        return "ceo"
    if row.get("is_cfo") or re.search(r"\bcfo\b", lowered) or "chief financial" in lowered:
        return "cfo"
    if _is_president_title(title):
        return "president"
    return "other"


def _owner_key(row: dict[str, Any]) -> str:
    for key in ("owner_cik", "reporting_owner_cik", "owner_name", "reporting_owner_name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _transaction_value(row: dict[str, Any]) -> float:
    value = _float_or_none(row.get("transaction_value"))
    if value is not None:
        return value
    shares = _float_or_none(row.get("shares"))
    price = _float_or_none(row.get("price"))
    if shares is None or price is None:
        return 0.0
    return shares * price


def _load_balance_sheet_index() -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    if not COMPANYFACTS_PATH.exists():
        return {}
    with COMPANYFACTS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            canonical = str(row.get("canonical") or "").lower()
            if canonical not in {"assets", "liabilities"}:
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            filed = _date10(row.get("filed"))
            value = _float_or_none(row.get("value"))
            if not ticker or not filed or value is None or value <= 0.0:
                continue
            index[ticker][canonical].append(
                {
                    "filed": filed,
                    "end": _date10(row.get("end")),
                    "value": value,
                    "form": row.get("form"),
                    "fp": row.get("fp"),
                    "fy": row.get("fy"),
                    "accession_number": row.get("accession_number"),
                }
            )
    for ticker_rows in index.values():
        for rows in ticker_rows.values():
            rows.sort(key=lambda row: (row["filed"], row.get("end") or ""))
    return index


def _latest_known(rows: list[dict[str, Any]], day: str) -> dict[str, Any] | None:
    known = [row for row in rows if row["filed"] <= day]
    return known[-1] if known else None


def _balance_sheet_for_event(
    balance_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    day: str,
) -> dict[str, Any]:
    rows = balance_index.get(str(ticker).upper(), {})
    assets = _latest_known(rows.get("assets", []), day)
    if not assets:
        return {
            "balance_sheet_status": "missing_assets",
            "low_liability_pass_v1": False,
            "liabilities_assets_ratio": None,
        }
    liability_rows = [row for row in rows.get("liabilities", []) if row["filed"] <= day]
    same_end = [row for row in liability_rows if row.get("end") == assets.get("end")]
    liabilities = same_end[-1] if same_end else (liability_rows[-1] if liability_rows else None)
    if not liabilities:
        return {
            "balance_sheet_status": "missing_liabilities",
            "low_liability_pass_v1": False,
            "assets_current_value": round(float(assets["value"]), 6),
            "assets_current_filed": assets["filed"],
            "assets_current_period_end": assets.get("end"),
            "liabilities_assets_ratio": None,
        }
    ratio = float(liabilities["value"]) / float(assets["value"])
    return {
        "balance_sheet_status": "ready",
        "assets_current_value": round(float(assets["value"]), 6),
        "assets_current_filed": assets["filed"],
        "assets_current_period_end": assets.get("end"),
        "liabilities_current_value": round(float(liabilities["value"]), 6),
        "liabilities_current_filed": liabilities["filed"],
        "liabilities_current_period_end": liabilities.get("end"),
        "liabilities_assets_ratio": round(ratio, 6),
        "low_liability_assets_max": LOW_LIABILITY_ASSETS_MAX,
        "low_liability_pass_v1": ratio <= LOW_LIABILITY_ASSETS_MAX,
        "low_liability_known_at": "SEC Companyfacts assets/liabilities filed date <= usable_trade_date",
    }


def _raw_row_qualifies(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip()
    usable = _date10(row.get("usable_trade_date"))
    if not ticker or not usable or not _window_name(usable):
        return False, {"reason": "outside_window_or_missing_ticker"}
    if not _truthy(row.get("open_market_purchase_flag")):
        return False, {"reason": "not_open_market_purchase"}
    if not _truthy(row.get("pit_safe_flag")):
        return False, {"reason": "not_pit_safe"}
    if str(row.get("acquired_disposed_code") or "").upper() not in {"A", ""}:
        return False, {"reason": "not_acquisition"}
    if str(row.get("transaction_code") or "").upper() not in {"P", ""}:
        return False, {"reason": "not_purchase_code"}
    if EXCLUDE_10B5_1 and _truthy(row.get("10b5_1_flag")):
        return False, {"reason": "rule_10b5_1"}
    if _truthy(row.get("option_exercise_flag")):
        return False, {"reason": "option_exercise"}
    if not _is_ceo_cfo_or_president(row):
        return False, {"reason": "not_ceo_cfo_president"}
    value = _transaction_value(row)
    if value <= MIN_ROLE_PURCHASE_VALUE:
        return False, {"reason": "non_positive_transaction_value"}
    return True, {
        "ticker": ticker,
        "usable_trade_date": usable,
        "transaction_value": value,
        "role_label": _role_label(row),
        "owner": _owner_key(row),
        "compact_row": {
            "owner": _owner_key(row),
            "owner_name": row.get("owner_name"),
            "owner_title": row.get("officer_title") or row.get("owner_title"),
            "role_label": _role_label(row),
            "transaction_value": round(value, 2),
            "shares": _float_or_none(row.get("shares")),
            "price": _float_or_none(row.get("price")),
            "shares_owned_following_transaction": _float_or_none(
                row.get("shares_owned_following_transaction")
            ),
            "accepted_at": row.get("accepted_at"),
            "accession_number": row.get("accession_number"),
        },
    }


def _event_from_group(
    key: tuple[str, str],
    rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    balance_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    ticker, usable = key
    total_value = sum(float(row["transaction_value"]) for row in rows)
    roles = sorted({str(row["role_label"]) for row in rows})
    owners = sorted({str(row["owner"]) for row in rows})
    balance = _balance_sheet_for_event(balance_index, ticker, usable)
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "window": _window_name(usable),
        "status": "event_ready" if ticker in prices else "missing_price_history",
        "total_purchase_value": round(total_value, 2),
        "top_purchase_value": round(max(float(row["transaction_value"]) for row in rows), 2),
        "row_count": len(rows),
        "owner_count": len(owners),
        "roles": roles,
        "has_ceo": "ceo" in roles,
        "has_cfo": "cfo" in roles,
        "has_president": "president" in roles,
        "owners": owners[:10],
        "source_rows": [row["compact_row"] for row in rows[:8]],
        **balance,
    }


def _load_events(
    prices: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not BROAD_FORM4_PATH.exists():
        raise FileNotFoundError(f"missing broad Form 4 archive: {BROAD_FORM4_PATH}")
    balance_index = _load_balance_sheet_index()
    raw_rows = 0
    qualified_rows = 0
    skip_reasons: defaultdict[str, int] = defaultdict(int)
    groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    with BROAD_FORM4_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw_rows += 1
            row = json.loads(line)
            qualifies, payload = _raw_row_qualifies(row)
            if not qualifies:
                skip_reasons[str(payload["reason"])] += 1
                continue
            qualified_rows += 1
            groups[(str(payload["ticker"]), str(payload["usable_trade_date"]))].append(payload)
    events = [
        _event_from_group(key, rows, prices, balance_index)
        for key, rows in groups.items()
    ]
    events.sort(
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            -int(bool(row.get("has_ceo"))),
            -int(bool(row.get("has_cfo"))),
            float(row.get("liabilities_assets_ratio") or 999.0),
            -float(row.get("total_purchase_value") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    CANDIDATES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_JSONL.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in events)
        + ("\n" if events else ""),
        encoding="utf-8",
    )
    return events, {
        "form4_source": _repo_rel(BROAD_FORM4_PATH),
        "companyfacts_source": _repo_rel(COMPANYFACTS_PATH),
        "raw_form4_rows": raw_rows,
        "role_qualified_raw_rows": qualified_rows,
        "role_event_count": len(events),
        "low_liability_role_event_count": sum(1 for row in events if row.get("low_liability_pass_v1")),
        "balance_sheet_ready_event_count": sum(
            1 for row in events if row.get("balance_sheet_status") == "ready"
        ),
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "candidate_snapshot": _repo_rel(CANDIDATES_JSONL),
        "pit_status": (
            "uses Form 4 usable_trade_date plus Companyfacts filed date <= usable_trade_date; "
            "entry/exit prices come after signal formation"
        ),
    }


def _select_event_trades(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    ready = [row for row in scoped if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            row["entry_date"],
            -int(bool(row.get("has_ceo"))),
            -int(bool(row.get("has_cfo"))),
            float(row.get("liabilities_assets_ratio") or 999.0),
            -float(row.get("total_purchase_value") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = [
        {
            "ticker": row.get("ticker"),
            "usable_trade_date": row.get("usable_trade_date"),
            "window": row.get("window"),
            "reason": row.get("status"),
        }
        for row in scoped
        if row.get("status") != "price_ready"
    ]
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = row["entry_date"]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= overlay.MAX_EVENT_POSITIONS:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_date": entry_date,
                    "window": row.get("window"),
                    "reason": "event_sleeve_capacity_full",
                    "active_tickers": [trade.get("ticker") for trade in active],
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trades = sum(int(row.get("trade_count") or 0) for row in metrics.values())
    wins = sum(int(row.get("winning_trades") or 0) for row in metrics.values())
    pnl = sum(float(row.get("total_pnl") or 0.0) for row in metrics.values())
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl": round(pnl, 2),
        "total_return_pct": round(pnl / 100_000.0, 6),
        "trade_count": trades,
        "event_trade_count": sum(int(row.get("event_trade_count") or 0) for row in metrics.values()),
        "win_rate": round(wins / trades, 6) if trades else None,
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
        "survival_rate": min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_agg = _aggregate_metrics(before)
    after_agg = _aggregate_metrics(after)
    before_ev = float(before_agg["expected_value_score"])
    before_pnl = float(before_agg["total_pnl"])
    after_ev = float(after_agg["expected_value_score"])
    after_pnl = float(after_agg["total_pnl"])
    return {
        "before_ev_sum": before_agg["expected_value_score"],
        "after_ev_sum": after_agg["expected_value_score"],
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "before_pnl_sum": before_agg["total_pnl"],
        "after_pnl_sum": after_agg["total_pnl"],
        "aggregate_pnl_delta": round(after_pnl - before_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "before_trade_count": before_agg["trade_count"],
        "after_trade_count": after_agg["trade_count"],
        "event_trade_count": after_agg["event_trade_count"],
        "windows_ev_improved": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            > float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            < float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            > float(before[label].get("total_pnl") or 0.0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            < float(before[label].get("total_pnl") or 0.0)
        ),
        "max_drawdown_drift": round(
            max(
                float(after[label].get("max_drawdown_pct") or 0.0)
                - float(before[label].get("max_drawdown_pct") or 0.0)
                for label in before
            ),
            6,
        ),
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0.0:
        return {"single_ticker_positive_share": None, "positive_pnl_hhi": None, "positive_pnl_by_ticker": {}}
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "single_ticker_positive_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(value * value for value in shares.values()), 6),
        "positive_pnl_by_ticker": {ticker: round(value, 2) for ticker, value in sorted(by_ticker.items())},
    }


def _gate_result(
    core_delta: dict[str, Any],
    role_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label for label, row in details.items() if int(row.get("selected_trade_count") or 0) > 0
    ]
    concentration = _positive_pnl_concentration(details)
    single_share = concentration["single_ticker_positive_share"]
    hhi = concentration["positive_pnl_hhi"]
    improves_core = (
        core_delta["aggregate_ev_delta"] > 0.0
        and core_delta["aggregate_pnl_delta"] > 0.0
        and int(core_delta["windows_ev_regressed"]) <= 1
        and int(core_delta["windows_pnl_regressed"]) <= 1
    )
    improves_role = (
        role_delta["aggregate_ev_delta"] > 0.0
        and role_delta["aggregate_pnl_delta"] > 0.0
        and int(role_delta["windows_ev_regressed"]) <= 1
        and int(role_delta["windows_pnl_regressed"]) <= 1
    )
    material = (
        core_delta["aggregate_ev_delta_pct"] is not None
        and core_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        core_delta["aggregate_pnl_delta_pct"] is not None
        and core_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= 0.005
    sample_ok = (
        selected >= 8
        and len(target_windows) >= 2
        and (single_share is None or single_share <= 0.50)
        and (hhi is None or hhi <= 0.35)
    )
    failed = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_role:
        failed.append("does_not_improve_role_only_comparator")
    if not material:
        failed.append("not_material_vs_core")
    if not drawdown_ok:
        failed.append("drawdown_drift_too_high")
    if selected < 8:
        failed.append("target_sample_too_small")
    if len(target_windows) < 2:
        failed.append("target_window_coverage_too_small")
    if single_share is not None and single_share > 0.50:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > 0.35:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed_replay_lead": bool(improves_core and improves_role and material and drawdown_ok and sample_ok),
        "failed_reasons": failed,
        "improves_core_cleanly": bool(improves_core),
        "improves_role_only_comparator": bool(improves_role),
        "material_vs_core": bool(material),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": "<= 0.005",
        "selected_event_trades": selected,
        "target_trade_count_min": 8,
        "target_windows": target_windows,
        "target_window_count_min": 2,
        "sample_guard_passed": bool(sample_ok),
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": "<= 0.35",
        "positive_pnl_by_ticker": concentration["positive_pnl_by_ticker"],
    }


def _strip_curve(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "combined_equity_curve"}


def _position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = _json_load(OPEN_POSITIONS_JSON, {})
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        return {"passed": False, "reason": "open_positions payload is not a list/object with positions"}
    missing = []
    for idx, position in enumerate(positions):
        if not isinstance(position, dict):
            missing.append({"index": idx, "reason": "not_object"})
            continue
        absent = [field for field in ("entry_date", "target_price") if position.get(field) in (None, "")]
        if absent:
            missing.append({"index": idx, "ticker": position.get("ticker"), "missing_fields": absent})
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _skip_reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    reasons = sorted({str(row.get("reason") or "") for row in rows if row.get("reason")})
    return {reason: sum(1 for row in rows if row.get("reason") == reason) for reason in reasons}


def _decision(gate: dict[str, Any], core_delta: dict[str, Any]) -> tuple[str, str, str, str]:
    if gate["passed_replay_lead"]:
        return (
            "observed_only",
            "positive_replay_lead_requires_shared_default_off_helper",
            "The fixed CEO/CFO/President + low-liability Form 4 bundle passed the replay-lead gate, but this run intentionally changed no shared production/backtest helper or daily paper snapshot. It remains a lead only.",
            "Implement one shared default-off helper/daily snapshot for this exact bundle, then rerun Gate 1-4 before any accepted-alpha claim.",
        )
    if core_delta["aggregate_ev_delta"] > 0.0 or core_delta["aggregate_pnl_delta"] > 0.0:
        return (
            "rejected",
            "rejected_directional_but_unstable",
            "The bundle showed partial positive evidence but failed stability, materiality, sample, concentration, or role-only comparator gates.",
            "Do not sweep role title, low-liability, value, notional, hold, or capacity thresholds on this archive.",
        )
    return (
        "rejected",
        "rejected_no_alpha",
        "The bundle did not improve aggregate EV/PnL against the core baseline under the canonical three-window replay.",
        "Do not retry nearby Form 4 role/fundamental confirmation without a new non-threshold evidence source or forward closed paper outcomes.",
    )


def build_payload() -> dict[str, Any]:
    overlay.WINDOWS = WINDOWS
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    frames = load_warehouse_frames()
    prices = _price_map_from_frames(frames)
    events, source = _load_events(prices)
    role_candidates = [overlay._candidate_trade(event, prices) for event in events]
    low_liability_candidates = [
        overlay._candidate_trade(event, prices)
        for event in events
        if event.get("low_liability_pass_v1")
    ]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    role_only_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_role: dict[str, dict[str, Any]] = OrderedDict()
    gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
    event_details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        role_selected, role_skipped = _select_event_trades(
            role_candidates, start=window["start"], end=window["end"]
        )
        selected, skipped = _select_event_trades(
            low_liability_candidates, start=window["start"], end=window["end"]
        )
        role_curve = overlay._event_equity_curve(
            role_selected, prices=prices, start=window["start"], end=window["end"]
        )
        event_curve = overlay._event_equity_curve(
            selected, prices=prices, start=window["start"], end=window["end"]
        )
        before_metrics[label] = _strip_curve(overlay._core_metrics(result))
        role_only_metrics[label] = _strip_curve(
            overlay._combined_metrics(result, role_curve, role_selected)
            if role_selected
            else dict(before_metrics[label])
        )
        after_metrics[label] = _strip_curve(
            overlay._combined_metrics(result, event_curve, selected)
            if selected
            else dict(before_metrics[label])
        )
        deltas_vs_core[label] = overlay._delta(before_metrics[label], after_metrics[label])
        deltas_vs_role[label] = overlay._delta(role_only_metrics[label], after_metrics[label])
        gate_by_window[label] = overlay._gate4(before_metrics[label], after_metrics[label])
        event_details[label] = {
            "role_event_count": sum(
                1 for row in role_candidates if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "role_price_ready_count": sum(
                1
                for row in role_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "low_liability_event_count": sum(
                1
                for row in low_liability_candidates
                if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "low_liability_price_ready_count": sum(
                1
                for row in low_liability_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "role_selected_trade_count": len(role_selected),
            "selected_trade_count": len(selected),
            "role_skipped_count": len(role_skipped),
            "skipped_count": len(skipped),
            "skip_reasons": _skip_reason_counts(skipped),
            "role_selected_trades": role_selected,
            "selected_trades": selected,
            "skipped_candidates": skipped[:30],
        }

    aggregate_vs_core = _aggregate_delta(before_metrics, after_metrics)
    aggregate_vs_role = _aggregate_delta(role_only_metrics, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_role, event_details)
    status, decision, rationale, next_action = _decision(gate, aggregate_vs_core)
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    actual_success = 1 if gate["passed_replay_lead"] else 0
    prediction = {
        "success_probability": 0.16,
        "expected_ev_delta": 0.12,
        "expected_pnl_delta": 2000.0,
        "main_failure_modes": [
            "sample_too_small",
            "CEO_CFO_buys_still_weak_standalone",
            "low_liability_overlaps_frozen_companyfacts",
            "window_regression",
            "positive_pnl_concentration",
        ],
        "confidence_reason": (
            "Broad clustered Form4 and owner-conviction failed, but their reflections "
            "allowed CEO/CFO non-plan buys paired with fundamental confirmation."
        ),
        "actual_success": actual_success,
        "brier_score": round((0.16 - actual_success) ** 2, 6),
        "realized_ev_delta": aggregate_vs_core["aggregate_ev_delta"],
        "realized_pnl_delta": aggregate_vs_core["aggregate_pnl_delta"],
        "realized_failure_modes": gate["failed_reasons"],
    }
    if gate["passed_replay_lead"]:
        why = (
            "Role quality plus filed-date-safe low-liability confirmation selected a "
            "cleaner subset than role-only Form 4 buys and improved the core replay."
        )
        forbidden = "Do not sweep thresholds; next step must keep the exact bundle and add shared default-off parity."
        new_evidence = "Shared helper, daily paper snapshot, parity tests, and closed forward paper replacement value."
    else:
        why = (
            "The role/fundamental bundle was not enough to overcome the broad Form 4 "
            "failure pattern. Either executive open-market buys remain mostly reactive, "
            "or low liabilities/assets overlaps already accepted Companyfacts quality "
            "without adding enough event timing value."
        )
        forbidden = (
            "Do not retune CEO/CFO/President title parsing, liabilities/assets threshold, "
            "purchase value floor, hold days, notional, capacity, or sort order on this archive."
        )
        new_evidence = (
            "A valid retry needs forward closed paper outcomes or a genuinely new evidence "
            "source such as buy-size relative to executive compensation/holdings from a "
            "shared daily surface."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT SEC Form 4 CEO/CFO/President non-plan open-market purchases, when paired "
            "with already-known SEC Companyfacts low-liability confirmation, may isolate "
            "informed insider demand with better replacement value than broad clustered or "
            "owner-conviction Form 4 buys."
        ),
        "change_type": "candidate_pool_private_replay_scout",
        "mechanism_family": "form4_role_fundamental_confirmation_event_sleeve",
        "trial_family": "form4_ceo_cfo_low_liability_candidate_pool",
        "trial_variant_id": "form4_ceo_cfo_low_liability_top1_10d_v1",
        "changed_variable": "CEO/CFO/President Form4 purchases require filed-date-safe low-liability Companyfacts confirmation",
        "single_causal_variable": "form4_ceo_cfo_low_liability_confirmation_candidate_source_v1",
        "prior_trial_count": 7,
        "nearby_prior_experiments": [
            "exp-20260614-018",
            "exp-20260614-019",
            "exp-20260605-001",
            "exp-20260604-022",
            "exp-20260503-053",
        ],
        "historical_experiment_check": {
            "exp-20260614-018": "Broad clustered Form 4 open-market buys failed; reflection allowed timing or cluster-quality edge before retry.",
            "exp-20260614-019": "Owner-conviction ratio failed; reflection allowed CEO/CFO non-plan buys paired with fundamental confirmation.",
            "exp-20260605-001": "Liquidity-intensity was positive only versus core and failed raw replacement/sample gates.",
            "exp-20260604-022": "Cost-basis entry alignment did not beat raw Form4 replacement sufficiently.",
            "exp-20260503-053": "Old role discriminator used narrow data; this uses broad archive plus low-liability confirmation.",
            "why_not_repeat": "This is not cluster count, owner count, liquidity intensity, cost basis, or low-liability threshold tuning; it tests one fixed role + accepted-fundamental confirmation bundle.",
        },
        "parameters": {
            "form4_role_rule": "CEO/CFO/President from issuer officer title or explicit is_ceo/is_cfo flags; excludes vice-president titles unless CEO/CFO also present",
            "exclude_10b5_1": EXCLUDE_10B5_1,
            "open_market_purchase_flag_required": True,
            "pit_safe_flag_required": True,
            "min_role_purchase_value": MIN_ROLE_PURCHASE_VALUE,
            "low_liability_assets_max": LOW_LIABILITY_ASSETS_MAX,
            "low_liability_rule_source": "accepted fundamental_growth_rs_low_liability_support_v1 threshold; reused as context, not retuned",
            "event_notional_usd": overlay.EVENT_NOTIONAL,
            "max_event_positions": overlay.MAX_EVENT_POSITIONS,
            "hold_days": overlay.HOLD_DAYS,
            "round_trip_cost_pct": overlay.ROUND_TRIP_COST_PCT,
            "selection_order": "entry_date asc, CEO/CFO first, lower liabilities/assets, total_purchase_value desc, ticker asc",
            "locked_variables": [
                "core universe",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "event notional",
                "event hold days",
                "event capacity",
                "accepted low-liability threshold",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "gate1": {
            "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "core_baseline_metrics": before_metrics,
        },
        "gate2": _position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_overlay_only": True,
            "min_survival_rate": min_survival,
            "passed": min_survival >= 0.05,
        },
        "before_metrics": before_metrics,
        "role_only_metrics": role_only_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_core": deltas_vs_core,
        "deltas_vs_role_only": deltas_vs_role,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "aggregate_delta_vs_role_only": aggregate_vs_role,
        "gate4": {**gate, "by_window": gate_by_window},
        "event_details": event_details,
        "decision_rationale": rationale,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": forbidden,
            "new_evidence_required": new_evidence,
        },
        "prediction": prediction,
        "next_action": next_action,
        "source_diagnostics": {**source, "warehouse_price_frames": len(frames)},
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "The tested fields are deterministic, free SEC data plus OHLCV; LLM soft-ranking remains sample-limited.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_exits": False,
            "production_consistency_read": (
                "No live/default production surface changed. A positive replay result is "
                "only a lead until this exact bundle is moved to a shared default-off helper "
                "used by historical replay and daily paper snapshots with parity tests."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(ROLE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(CANDIDATES_JSONL),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 CEO/CFO Low-Liability Confirmation",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- status: `{payload['status']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Core EV | Role-only EV | After EV | Delta vs core | Delta vs role | Core PnL | After PnL | Event PnL | Events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["before_metrics"][label]
        role = payload["role_only_metrics"][label]
        after = payload["after_metrics"][label]
        core_delta = payload["deltas_vs_core"][label]
        role_delta = payload["deltas_vs_role_only"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {role['expected_value_score']} | "
            f"{after['expected_value_score']} | {core_delta['expected_value_score']} | "
            f"{role_delta['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{int(after.get('event_trade_count') or 0)} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate vs Core",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_core"], indent=2, sort_keys=True),
            "```",
            "",
            "## Aggregate vs Role-Only",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_role_only"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps({k: v for k, v in payload["gate4"].items() if k != "by_window"}, indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Post-Run Reflection",
            "",
            f"- why_result_happened: {payload['post_run_reflection']['why_result_happened']}",
            f"- forbidden_near_neighbor_retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- new_evidence_required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:70]) + "\n", encoding="utf-8")


def _update_ticket_and_manifest(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "before_aggregate": _repo_rel(BEFORE_JSON),
                "role_only_aggregate": _repo_rel(ROLE_JSON),
                "after_aggregate": _repo_rel(AFTER_JSON),
                "candidate_snapshot": _repo_rel(CANDIDATES_JSONL),
                "log": _repo_rel(LOG_JSON),
                "report": _repo_rel(ARTIFACT_MD),
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_role_only": payload["aggregate_delta_vs_role_only"],
                "gate4": {k: v for k, v in payload["gate4"].items() if k != "by_window"},
                "decision": payload["decision"],
                "post_run_reflection": payload["post_run_reflection"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)
    manifest = _json_load(MANIFEST_JSON, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "experiment_id": EXP_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "updated_at": payload["timestamp"],
            "result_files": [
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(ROLE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(CANDIDATES_JSONL),
                _repo_rel(LOG_JSON),
                _repo_rel(ARTIFACT_MD),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(BEFORE_JSON, _aggregate_metrics(payload["before_metrics"]))
    _write_json(ROLE_JSON, _aggregate_metrics(payload["role_only_metrics"]))
    _write_json(AFTER_JSON, _aggregate_metrics(payload["after_metrics"]))
    _write_report(payload)
    _update_ticket_and_manifest(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_role_only": payload["aggregate_delta_vs_role_only"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed_replay_lead",
                        "improves_core_cleanly",
                        "improves_role_only_comparator",
                        "material_vs_core",
                        "selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                        "failed_reasons",
                    )
                },
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
