"""Shared default-off Hacker News issuer-attention paper policy.

The source contract is deliberately small: immutable Hacker News story IDs,
UTC creation timestamps, and outbound story URLs.  URLs are attributed only
when their host is the frozen issuer-owned domain itself or a dot-delimited
subdomain of it.  Historical replay and the daily snapshot call the same
weekly selector, so the policy cannot drift between research and paper use.

This module never fetches data and never creates orders.  The fixed notional
is an evidence unit only; ``trade_enabled`` remains false everywhere.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import (
        SLIPPAGE_BPS_ENTRY,
        SLIPPAGE_BPS_TARGET,
        apply_slippage,
    )


SLEEVE_NAME = "HACKER_NEWS_ATTENTION_PAPER"
RULE_VERSION = "hn_owned_domain_attention_top3_nextopen_h10_shared_v1"
SOURCE_RULE_VERSION = "hn_exact_owned_host_complete_week_prior4_acceleration_v1"
STATE_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = "hacker_news_attention_default_off_snapshot_v1"

PAPER_NOTIONAL_USD = 4_000.0
HOLD_SESSIONS = 10
MAX_WEEKLY_CANDIDATES = 3
MAX_ACTIVE_POSITIONS = 6
MIN_CURRENT_STORY_COUNT = 2
PRIOR_COMPLETE_WEEKS = 4
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5
TRADE_ENABLED = False

# All aliases were owned by the mapped public issuer before the source warmup
# for the three canonical windows.  Keeping the effective boundary explicit
# prevents this fixed map from being silently projected into earlier history.
ISSUER_DOMAIN_MAP_EFFECTIVE_FROM = "2024-01-01"
ISSUER_OWNED_DOMAINS: dict[str, tuple[str, ...]] = {
    "AAPL": ("apple.com",),
    "MSFT": ("microsoft.com", "github.com"),
    "GOOG": ("google.com", "youtube.com"),
    "AMZN": ("amazon.com",),
    "META": ("facebook.com", "instagram.com", "meta.com"),
    "NVDA": ("nvidia.com",),
    "TSLA": ("tesla.com",),
    "NFLX": ("netflix.com",),
    "ADBE": ("adobe.com",),
    "ORCL": ("oracle.com",),
    "IBM": ("ibm.com",),
    "CSCO": ("cisco.com",),
    "CRM": ("salesforce.com",),
    "NOW": ("servicenow.com",),
    "DDOG": ("datadoghq.com",),
    "SNOW": ("snowflake.com",),
    "PLTR": ("palantir.com",),
    "PANW": ("paloaltonetworks.com",),
    "CRWD": ("crowdstrike.com",),
    "AVGO": ("broadcom.com", "vmware.com"),
    "INTC": ("intel.com",),
    "AMD": ("amd.com",),
    "QCOM": ("qualcomm.com",),
    "MU": ("micron.com",),
    "TSM": ("tsmc.com",),
    "SHOP": ("shopify.com",),
    "COIN": ("coinbase.com",),
    "HOOD": ("robinhood.com",),
    "UBER": ("uber.com",),
    "ABNB": ("airbnb.com",),
    "SPOT": ("spotify.com",),
    "TEAM": ("atlassian.com",),
    "NET": ("cloudflare.com",),
    "MDB": ("mongodb.com",),
    "OKTA": ("okta.com",),
    "TWLO": ("twilio.com",),
    "ZS": ("zscaler.com",),
    "PATH": ("uipath.com",),
}

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "hacker_news_attention" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "hacker_news_attention" / "snapshots.jsonl"
)


class HackerNewsAttentionContractError(ValueError):
    """Raised when an immutable source identity or market input conflicts."""


def _domain_map() -> dict[str, str]:
    output: dict[str, str] = {}
    for ticker, aliases in ISSUER_OWNED_DOMAINS.items():
        for alias in aliases:
            domain = alias.strip().lower().rstrip(".")
            prior = output.get(domain)
            if prior is not None and prior != ticker:
                raise RuntimeError(f"ambiguous issuer-owned domain: {domain}")
            output[domain] = ticker
    return output


DOMAIN_TO_TICKER = _domain_map()
if len(ISSUER_OWNED_DOMAINS) != 38 or len(DOMAIN_TO_TICKER) != 43:
    raise RuntimeError("frozen Hacker News issuer-domain map must remain 38x43")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _payload_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _date10(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as error:
        raise HackerNewsAttentionContractError(f"invalid date: {value!r}") from error


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        text = str(value or "").strip()
        if not text:
            raise HackerNewsAttentionContractError("story timestamp missing")
        if text.isdigit():
            parsed = datetime.fromtimestamp(float(text), tz=timezone.utc)
        else:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError as error:
                raise HackerNewsAttentionContractError(
                    f"invalid story timestamp: {value!r}"
                ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _week_bounds(day: date) -> tuple[date, date]:
    week_start = day - timedelta(days=day.weekday())
    return week_start, week_start + timedelta(days=6)


def match_hacker_news_owned_domain(
    url: Any,
    *,
    on_date: Any | None = None,
) -> tuple[str, str] | None:
    """Return ``(ticker, alias)`` for a root host or real subdomain.

    The dot-boundary check admits ``developer.apple.com`` but rejects
    ``notapple.com`` and ``apple.com.evil.example``.  Path/title substring
    matches and redirect destinations are never used for attribution.
    """

    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    try:
        host = (parsed.hostname or "").encode("idna").decode("ascii")
    except UnicodeError:
        return None
    host = host.lower().rstrip(".")
    if not host:
        return None
    if on_date is not None and _date10(on_date) < ISSUER_DOMAIN_MAP_EFFECTIVE_FROM:
        return None
    for alias in sorted(DOMAIN_TO_TICKER, key=lambda value: (-len(value), value)):
        if host == alias or host.endswith("." + alias):
            return DOMAIN_TO_TICKER[alias], alias
    return None


def normalise_hacker_news_story_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Canonicalise, exact-map, and de-duplicate Hacker News story rows.

    Unmapped/invalid rows are excluded.  Repeated ``objectID`` rows are
    collapsed only when their immutable canonical identity agrees; a conflict
    fails closed because it would make the PIT archive non-reproducible.
    """

    by_object_id: dict[str, dict[str, Any]] = {}
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        object_id = str(
            raw.get("objectID") or raw.get("object_id") or raw.get("id") or ""
        ).strip()
        if not object_id:
            continue
        timestamp_raw = (
            raw.get("created_at_i")
            if raw.get("created_at_i") is not None
            else raw.get("created_at") or raw.get("story_created_at")
        )
        try:
            created_at = _utc_datetime(timestamp_raw)
        except HackerNewsAttentionContractError:
            continue
        story_url = str(raw.get("url") or raw.get("story_url") or "").strip()
        matched = match_hacker_news_owned_domain(
            story_url,
            on_date=created_at.date(),
        )
        if matched is None:
            continue
        ticker, owned_domain = matched
        host = (urlparse(story_url).hostname or "").lower().rstrip(".")
        week_start, week_end = _week_bounds(created_at.date())
        canonical = {
            "object_id": object_id,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
            "created_date": created_at.date().isoformat(),
            "story_url": story_url,
            "host": host,
            "owned_domain": owned_domain,
            "ticker": ticker,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "source_rule_version": SOURCE_RULE_VERSION,
        }
        canonical["source_record_sha256"] = _payload_sha256(canonical)
        prior = by_object_id.get(object_id)
        if prior is not None:
            comparable = ("created_at", "story_url", "ticker", "owned_domain")
            if any(prior[key] != canonical[key] for key in comparable):
                raise HackerNewsAttentionContractError(
                    f"conflicting duplicate objectID: {object_id}"
                )
            continue
        by_object_id[object_id] = canonical
    return sorted(
        by_object_id.values(),
        key=lambda row: (row["created_at"], row["object_id"]),
    )


def evaluate_hacker_news_attention_weekly_decisions(
    story_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    archive_start: Any | None = None,
) -> dict[str, Any]:
    """Evaluate and rank all eligible rows from complete UTC weeks.

    ``as_of`` is a PIT knowledge boundary.  A Monday-Sunday week is usable
    only when its Sunday is strictly before the ``as_of`` calendar date; this
    keeps a Sunday snapshot from seeing a not-yet-complete UTC week.
    """

    canonical = normalise_hacker_news_story_rows(story_rows)
    as_of_date = date.fromisoformat(_date10(as_of))
    start_date = date.fromisoformat(_date10(start)) if start is not None else None
    end_date = date.fromisoformat(_date10(end)) if end is not None else None
    coverage_start = date.fromisoformat(
        _date10(archive_start or ISSUER_DOMAIN_MAP_EFFECTIVE_FROM)
    )
    coverage_week_start, _ = _week_bounds(coverage_start)

    counts: Counter[tuple[str, str]] = Counter()
    object_ids: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for row in canonical:
        week_start = str(row["week_start"])
        ticker = str(row["ticker"])
        counts[(ticker, week_start)] += 1
        object_ids[(ticker, week_start)].append(str(row["object_id"]))

    eligible_by_week: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for (ticker, week_start_text), current_count in sorted(counts.items()):
        week_start_date = date.fromisoformat(week_start_text)
        week_end_date = week_start_date + timedelta(days=6)
        if week_end_date >= as_of_date:
            continue
        if start_date is not None and week_end_date < start_date:
            continue
        if end_date is not None and week_end_date > end_date:
            continue
        earliest_prior = week_start_date - timedelta(days=7 * PRIOR_COMPLETE_WEEKS)
        if earliest_prior < coverage_week_start:
            continue
        prior_counts = [
            counts[
                (
                    ticker,
                    (week_start_date - timedelta(days=7 * offset)).isoformat(),
                )
            ]
            for offset in range(PRIOR_COMPLETE_WEEKS, 0, -1)
        ]
        prior_mean = sum(prior_counts) / PRIOR_COMPLETE_WEEKS
        acceleration = float(current_count) - prior_mean
        if current_count < MIN_CURRENT_STORY_COUNT or acceleration <= 0.0:
            continue
        eligible_by_week[week_end_date.isoformat()].append(
            {
                "ticker": ticker,
                "week_start": week_start_date.isoformat(),
                "week_end": week_end_date.isoformat(),
                "signal_date": week_end_date.isoformat(),
                "current_story_count": int(current_count),
                "prior_four_week_counts": [int(value) for value in prior_counts],
                "prior_four_week_mean": round(prior_mean, 8),
                "attention_acceleration": round(acceleration, 8),
                "story_object_ids": sorted(object_ids[(ticker, week_start_text)]),
                "source_rule_version": SOURCE_RULE_VERSION,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
            }
        )

    eligible_rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for week_end, rows in sorted(eligible_by_week.items()):
        ranked = sorted(
            rows,
            key=lambda row: (
                -float(row["attention_acceleration"]),
                -int(row["current_story_count"]),
                str(row["ticker"]),
            ),
        )
        for rank, row in enumerate(ranked, start=1):
            decision = {
                **row,
                "weekly_rank": rank,
                "decision_id": (
                    f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{week_end}:"
                    f"{row['ticker']}"
                ),
                "selected": rank <= MAX_WEEKLY_CANDIDATES,
            }
            eligible_rows.append(decision)
            if decision["selected"]:
                selected.append(decision)
    return {
        "eligible_rows": eligible_rows,
        "decisions": selected,
        "signals_generated": len(eligible_rows),
        "signals_survived": len(selected),
        "survival_rate": (
            round(len(selected) / len(eligible_rows), 6) if eligible_rows else 0.0
        ),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
    }


def select_hacker_news_attention_weekly_decisions(
    story_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    archive_start: Any | None = None,
) -> list[dict[str, Any]]:
    """Return only the locked top-three rows from the shared evaluator."""

    return evaluate_hacker_news_attention_weekly_decisions(
        story_rows,
        as_of=as_of,
        start=start,
        end=end,
        archive_start=archive_start,
    )["decisions"]


def _normalise_bars(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        try:
            day = _date10(raw.get("date") or raw.get("Date"))
        except HackerNewsAttentionContractError:
            continue
        if date.fromisoformat(day).weekday() >= 5:
            continue
        values: dict[str, float] = {}
        valid = True
        for field in ("open", "high", "low", "close"):
            value = raw.get(field) if field in raw else raw.get(field.title())
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                valid = False
                break
            if not math.isfinite(parsed) or parsed <= 0.0:
                valid = False
                break
            values[field] = parsed
        if not valid or values["high"] < values["low"]:
            continue
        row = {"date": day, **values}
        prior = by_date.get(day)
        if prior is not None and prior != row:
            raise HackerNewsAttentionContractError(f"conflicting OHLCV date: {day}")
        by_date[day] = row
    return [by_date[day] for day in sorted(by_date)]


def _normalise_trading_dates(values: Iterable[Any]) -> list[str]:
    output: set[str] = set()
    for raw in values or []:
        value = raw
        if isinstance(raw, Mapping):
            if raw.get("is_regular_session") is False:
                continue
            session_type = str(raw.get("session_type") or "").strip().lower()
            if session_type and session_type not in {"regular", "regular_session"}:
                continue
            value = raw.get("date") or raw.get("session_date")
        day = _date10(value)
        if date.fromisoformat(day).weekday() >= 5:
            raise HackerNewsAttentionContractError(
                f"weekend cannot be a regular session: {day}"
            )
        output.add(day)
    return sorted(output)


def _prepare_market_inputs(
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    trading_dates: Iterable[Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if trading_dates is not None:
        calendar = _normalise_trading_dates(trading_dates)
    elif bars.get("SPY"):
        calendar = [row["date"] for row in bars["SPY"]]
    else:
        calendar = sorted(
            {row["date"] for ticker_rows in bars.values() for row in ticker_rows}
        )
    return bars, calendar


def _atr14_before_entry(
    rows: Sequence[Mapping[str, Any]],
    entry_date: str,
) -> float | None:
    prior = [row for row in rows if str(row["date"]) < entry_date]
    if len(prior) < ATR_PERIOD:
        return None
    sample = prior[-ATR_PERIOD:]
    prior_by_date = {str(row["date"]): index for index, row in enumerate(rows)}
    true_ranges: list[float] = []
    for row in sample:
        index = prior_by_date[str(row["date"])]
        previous_close = (
            float(rows[index - 1]["close"]) if index > 0 else float(row["close"])
        )
        true_ranges.append(
            max(
                float(row["high"]) - float(row["low"]),
                abs(float(row["high"]) - previous_close),
                abs(float(row["low"]) - previous_close),
            )
        )
    atr = sum(true_ranges) / len(true_ranges)
    return atr if math.isfinite(atr) and atr > 0.0 else None


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "production_signal_path_changed": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def build_hacker_news_attention_historical_trades(
    *,
    story_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: Any,
    end: Any,
    as_of: Any | None = None,
    trading_dates: Iterable[Any] | None = None,
    archive_start: Any | None = None,
) -> dict[str, Any]:
    """Replay the locked weekly candidate pool with PIT fills and costs."""

    start_iso = _date10(start)
    end_iso = _date10(end)
    as_of_iso = _date10(as_of or end_iso)
    if start_iso > end_iso:
        raise HackerNewsAttentionContractError("start is after end")
    canonical_stories = normalise_hacker_news_story_rows(story_rows)
    weekly_evaluation = evaluate_hacker_news_attention_weekly_decisions(
        canonical_stories,
        as_of=as_of_iso,
        archive_start=archive_start,
    )
    decisions = list(weekly_evaluation["decisions"])
    bars, calendar = _prepare_market_inputs(ohlcv_by_ticker, trading_dates)
    calendar_index = {day: index for index, day in enumerate(calendar)}
    bars_by_ticker_date = {
        ticker: {str(row["date"]): row for row in rows}
        for ticker, rows in bars.items()
    }

    rejects: Counter[str] = Counter()
    window_decisions: list[dict[str, Any]] = []
    trade_candidates: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    accepted_intervals: list[dict[str, Any]] = []

    for decision in sorted(
        decisions,
        key=lambda row: (row["week_end"], row["weekly_rank"], row["ticker"]),
    ):
        signal_date = str(decision["week_end"])
        entry_date = next((day for day in calendar if day > signal_date), None)
        if entry_date is None:
            rejects["next_regular_session_unavailable"] += 1
            continue
        if entry_date < start_iso or entry_date > end_iso:
            continue
        window_decisions.append(decision)
        entry_index = calendar_index[entry_date]
        ticker = str(decision["ticker"])

        same_ticker_active = any(
            row["ticker"] == ticker
            and row["entry_index"] <= entry_index
            and (row["exit_index"] is None or row["exit_index"] >= entry_index)
            for row in accepted_intervals
        )
        if same_ticker_active:
            rejects["same_ticker_active"] += 1
            continue
        active_count = sum(
            row["entry_index"] <= entry_index
            and (row["exit_index"] is None or row["exit_index"] >= entry_index)
            for row in accepted_intervals
        )
        if active_count >= MAX_ACTIVE_POSITIONS:
            rejects["max_active_positions"] += 1
            continue

        ticker_rows = bars.get(ticker) or []
        entry_row = bars_by_ticker_date.get(ticker, {}).get(entry_date)
        if entry_row is None:
            rejects["missing_exact_entry_open"] += 1
            continue
        atr14 = _atr14_before_entry(ticker_rows, entry_date)
        if atr14 is None:
            rejects["missing_prior_atr14"] += 1
            continue
        raw_entry_open = float(entry_row["open"])
        entry_price = float(
            apply_slippage(
                raw_entry_open,
                SLIPPAGE_BPS_ENTRY,
                "buy",
                notional=PAPER_NOTIONAL_USD,
            )
        )
        target_price = round(entry_price + ATR_TARGET_MULTIPLE * atr14, 4)
        exit_index = entry_index + HOLD_SESSIONS - 1
        planned_exit_date = (
            calendar[exit_index] if exit_index < len(calendar) else None
        )
        candidate = {
            **decision,
            "entry_date": entry_date,
            "entry_open_price_raw": round(raw_entry_open, 4),
            "entry_price": round(entry_price, 4),
            "atr14_as_of_entry": round(atr14, 8),
            "target_price": target_price,
            "target_price_role": (
                "3.5x_atr14_signal_contract_sentinel_not_exit_driver"
            ),
            "planned_exit_date": planned_exit_date,
            "hold_sessions": HOLD_SESSIONS,
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "trade_enabled": False,
            "alters_orders": False,
        }
        trade_candidates.append(candidate)
        accepted_intervals.append(
            {
                "ticker": ticker,
                "entry_index": entry_index,
                "exit_index": exit_index if planned_exit_date is not None else None,
            }
        )

        if planned_exit_date is None or planned_exit_date > end_iso:
            unsettled.append(
                {**candidate, "unsettled_reason": "incomplete_10_session_horizon"}
            )
            continue
        exit_row = bars_by_ticker_date.get(ticker, {}).get(planned_exit_date)
        if exit_row is None:
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_exact_exit_close"}
            )
            continue
        raw_exit_close = float(exit_row["close"])
        exit_price = float(
            apply_slippage(
                raw_exit_close,
                SLIPPAGE_BPS_TARGET,
                "sell",
                notional=PAPER_NOTIONAL_USD,
            )
        )
        pnl_pct_gross = exit_price / entry_price - 1.0
        pnl_pct_net = pnl_pct_gross - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "exit_date": planned_exit_date,
                "exit_close_price_raw": round(raw_exit_close, 4),
                "exit_price": round(exit_price, 4),
                "hold_sessions_realized": HOLD_SESSIONS,
                "exit_reason": "scheduled_10_session_horizon_close",
                "pnl_pct_gross": round(pnl_pct_gross, 10),
                "pnl_pct_net": round(pnl_pct_net, 10),
                "net_return": round(pnl_pct_net, 10),
                "pnl": round(PAPER_NOTIONAL_USD * pnl_pct_net, 2),
            }
        )

    window_eligible_rows = []
    for row in weekly_evaluation["eligible_rows"]:
        entry_date = next((day for day in calendar if day > row["week_end"]), None)
        if entry_date is not None and start_iso <= entry_date <= end_iso:
            window_eligible_rows.append(row)
    generated = len(window_eligible_rows)
    survived = len(trade_candidates)
    return {
        "schema": "hacker_news_attention_historical_replay_v1",
        "start": start_iso,
        "end": end_iso,
        "as_of": as_of_iso,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "paper_notional_usd": PAPER_NOTIONAL_USD,
        "weekly_decisions": decisions,
        "eligible_weekly_rows": weekly_evaluation["eligible_rows"],
        "window_eligible_rows": window_eligible_rows,
        "window_decisions": window_decisions,
        "trade_candidates": trade_candidates,
        "trades": trades,
        "unsettled": unsettled,
        "reject_totals": dict(sorted(rejects.items())),
        "normalised_story_count": len(canonical_stories),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "production_impact": _production_impact(),
    }


def empty_hacker_news_attention_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "processed_decision_ids": [],
    }


def load_hacker_news_attention_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_hacker_news_attention_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_hacker_news_attention_state()
    if isinstance(payload, Mapping):
        state.update(payload)
    return state


def save_hacker_news_attention_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def append_hacker_news_attention_snapshot(
    snapshot: Mapping[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")


def build_hacker_news_attention_snapshot(
    *,
    story_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    as_of: Any,
    start: Any | None = None,
    trading_dates: Iterable[Any] | None = None,
    archive_start: Any | None = None,
    state: dict[str, Any] | None = None,
    persist: bool = False,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    """Build one deterministic daily snapshot from the shared replay policy."""

    as_of_iso = _date10(as_of)
    start_iso = _date10(start or archive_start or ISSUER_DOMAIN_MAP_EFFECTIVE_FROM)
    bounded_bars = {
        ticker: [
            row
            for row in rows
            if _date10(row.get("date") or row.get("Date")) <= as_of_iso
        ]
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    bounded_calendar = None
    if trading_dates is not None:
        bounded_calendar = [
            raw
            for raw in trading_dates
            if _date10(
                raw.get("date") or raw.get("session_date")
                if isinstance(raw, Mapping)
                else raw
            )
            <= as_of_iso
        ]
    replay = build_hacker_news_attention_historical_trades(
        story_rows=story_rows,
        ohlcv_by_ticker=bounded_bars,
        start=start_iso,
        end=as_of_iso,
        as_of=as_of_iso,
        trading_dates=bounded_calendar,
        archive_start=archive_start,
    )

    working_state = deepcopy(
        state
        if state is not None
        else (
            load_hacker_news_attention_state(state_path)
            if persist
            else empty_hacker_news_attention_state()
        )
    )
    closed_by_id = {
        str(row.get("decision_id")): row
        for row in working_state.get("closed_positions") or []
        if row.get("decision_id")
    }
    closed_by_id.update(
        {str(row["decision_id"]): row for row in replay["trades"]}
    )
    working_state.update(
        {
            "schema_version": STATE_SCHEMA_VERSION,
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "pending_entries": [],
            "open_positions": list(replay["unsettled"]),
            "closed_positions": [closed_by_id[key] for key in sorted(closed_by_id)],
            "processed_decision_ids": sorted(
                {row["decision_id"] for row in replay["window_decisions"]}
            ),
        }
    )
    latest_week_end = max(
        (row["week_end"] for row in replay["weekly_decisions"]),
        default=None,
    )
    latest_decisions = [
        row
        for row in replay["weekly_decisions"]
        if row["week_end"] == latest_week_end
    ]
    snapshot = {
        "schema": SNAPSHOT_SCHEMA_VERSION,
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": as_of_iso,
        "generated_at": _utc_now_iso(),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "alters_orders": False,
        "orders": [],
        "paper_notional_usd": PAPER_NOTIONAL_USD,
        "candidate_count": len(replay["trade_candidates"]),
        "closed_trade_count": len(replay["trades"]),
        "unsettled_count": len(replay["unsettled"]),
        "latest_complete_week_end": latest_week_end,
        "latest_week_decisions": latest_decisions,
        "replay": replay,
        "state": working_state,
        "execution_envelope": {
            "max_position_notional_usd": PAPER_NOTIONAL_USD,
            "max_capital_pct": 0.24,
            "max_concurrent_positions": MAX_ACTIVE_POSITIONS,
            "one_active_position_per_ticker": True,
            "slippage": {
                "entry_bps": SLIPPAGE_BPS_ENTRY,
                "exit_bps": SLIPPAGE_BPS_TARGET,
            },
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "order_semantics": "paper next regular-session open only",
            "failure_policy": "skip missing exact-session bar; never chase",
            "kill_switch_drawdown_pct": None,
        },
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked_default_off_new_observer",
        },
        "production_impact": _production_impact(),
    }
    if persist:
        save_hacker_news_attention_state(working_state, state_path)
        append_hacker_news_attention_snapshot(snapshot, snapshot_log_path)
    return snapshot


__all__ = [
    "ATR_TARGET_MULTIPLE",
    "DEFAULT_SNAPSHOT_LOG_PATH",
    "DEFAULT_STATE_PATH",
    "DOMAIN_TO_TICKER",
    "HOLD_SESSIONS",
    "ISSUER_DOMAIN_MAP_EFFECTIVE_FROM",
    "ISSUER_OWNED_DOMAINS",
    "MAX_ACTIVE_POSITIONS",
    "MAX_WEEKLY_CANDIDATES",
    "PAPER_NOTIONAL_USD",
    "RULE_VERSION",
    "SNAPSHOT_SCHEMA_VERSION",
    "SOURCE_RULE_VERSION",
    "TRADE_ENABLED",
    "HackerNewsAttentionContractError",
    "append_hacker_news_attention_snapshot",
    "build_hacker_news_attention_historical_trades",
    "build_hacker_news_attention_snapshot",
    "empty_hacker_news_attention_state",
    "evaluate_hacker_news_attention_weekly_decisions",
    "load_hacker_news_attention_state",
    "match_hacker_news_owned_domain",
    "normalise_hacker_news_story_rows",
    "save_hacker_news_attention_state",
    "select_hacker_news_attention_weekly_decisions",
]
