"""Cash-tender spread-over-carry paper sleeve (exp-20260719-003).

The helper is deliberately pure and data-injected.  It accepts normalized SEC
cash-tender episodes plus point-in-time daily OHLCV and produces both a
historical replay and a daily, default-off paper snapshot.  It never fetches
data, writes files, asks an LLM to make a decision, or creates an order.

The historical and daily paths share the same candidate preparation, sizing,
cash ledger, carry accrual, and lifecycle transitions.  An open deal at a
historical window boundary is marked to the exact final-session close and
reported as right-censored; it is not converted into an actual exit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
import math
from statistics import mean, stdev
from typing import Any

try:
    from convergence import compute_expected_value_score
    from us_market_calendar import is_us_equity_session as _base_is_us_equity_session
except ModuleNotFoundError:  # package-style imports in repository-root tests
    from quant.convergence import compute_expected_value_score
    from quant.us_market_calendar import is_us_equity_session as _base_is_us_equity_session


RULE_VERSION = "sec_cash_tender_spread_over_carry_v2"
SCHEMA_VERSION = "sec_cash_tender_spread_paper_snapshot_v1"

TOTAL_ACCOUNT_CAPITAL_USD = 100_000.0
SLEEVE_CAPITAL_USD = 10_000.0
MAX_DEAL_NOTIONAL_USD = 5_000.0
MAX_PREDICTED_BREAK_LOSS_USD = 500.0
MAX_ADV_FRACTION = 0.01
MAX_CONCURRENT_NOTIONAL_USD = 10_000.0

BREAK_LOOKBACK_SESSIONS = 20
ADV_LOOKBACK_SESSIONS = 20
MIN_IMPLIED_COMPLETION_PROBABILITY = 0.70
CARRY_ANNUAL_RATE = 0.05
ROUND_TRIP_COST_RATE = 0.0035
HALF_TRADE_COST_RATE = ROUND_TRIP_COST_RATE / 2.0
TIMEOUT_CALENDAR_DAYS = 365
DEFAULT_EVENT_FEE_USD = 20.0
EVENT_FEE_SENSITIVITIES_USD = (0.0, 20.0, 40.0)

# The shared rule calendar covers recurring NYSE holidays.  This fixed-window
# sleeve also needs the one-off national day of mourning inside its evidence
# range.  Callers can inject their canonical calendar for any other window.
_SPECIAL_FULL_DAY_CLOSURES = frozenset({"2025-01-09"})

_COMPLETED = frozenset({"completed", "complete", "success", "successful"})
_TERMINATED_NEGATIVE = frozenset(
    {"terminated_negative", "terminated", "failed", "withdrawn", "cancelled"}
)
_TERMINATED_HIGHER_BID = frozenset(
    {"terminated_higher_bid", "higher_bid_termination", "superior_bid_termination"}
)
_HIGHER_BID_PUBLIC = frozenset({"higher_bid_pending"})
_PENDING = frozenset(
    {"pending", "extended_pending", "open", "unknown"}
)


def is_us_equity_session(as_of: Any) -> bool:
    day = _date10(as_of)
    return bool(
        day
        and day not in _SPECIAL_FULL_DAY_CLOSURES
        and _base_is_us_equity_session(day)
    )


def production_impact() -> dict[str, Any]:
    """Return the immutable no-order boundary exposed by both public APIs."""

    return {
        "shared_policy_changed": True,
        "default_off_paper_only": True,
        "trade_enabled": False,
        "enabled": False,
        "live_ready": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_core": False,
        "uses_llm": False,
        "llm_authority": "none",
    }


def execution_sizing_contract() -> dict[str, Any]:
    return {
        "rule_version": RULE_VERSION,
        "total_account_capital_usd": TOTAL_ACCOUNT_CAPITAL_USD,
        "funded_sleeve_capital_usd": SLEEVE_CAPITAL_USD,
        "maximum_deal_notional_usd": MAX_DEAL_NOTIONAL_USD,
        "maximum_predicted_break_loss_usd": MAX_PREDICTED_BREAK_LOSS_USD,
        "maximum_adv_fraction": MAX_ADV_FRACTION,
        "maximum_concurrent_notional_usd": MAX_CONCURRENT_NOTIONAL_USD,
        "whole_shares_required": True,
        "cash_must_remain_nonnegative": True,
        "same_session_exit_proceeds_reused": False,
        "borrowing_allowed": False,
        "leverage_allowed": False,
        "experiment_notional_usd": None,
        "paper_notional_is_evidence_only": True,
        "trade_enabled": False,
        "live_ready": False,
        "fail_closed": True,
    }


def _date10(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _normalise_status(value: Any) -> str:
    return str(value or "pending").strip().lower().replace("-", "_").replace(" ", "_")


def _episode_fields(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt both the agreed flat schema and lifecycle.py's nested schema."""

    terms = _mapping(episode.get("terms"))
    eligibility = _mapping(episode.get("eligibility"))
    outcome = _mapping(episode.get("outcome"))
    source_documents = [
        value
        for value in (
            episode.get("primary_schedule_to"),
            episode.get("offer_to_purchase_exhibit"),
        )
        if isinstance(value, Mapping)
    ]
    source_hashes = sorted(
        {
            str(value)
            for value in (
                episode.get("raw_submission_sha256"),
                *(row.get("source_sha256") for row in source_documents),
            )
            if value
        }
    )
    status = _normalise_status(
        _first_value(outcome.get("status"), outcome.get("outcome_type"))
    )
    return {
        "accession_number": str(episode.get("accession_number") or "").strip(),
        "target_cik": str(
            _first_value(episode.get("target_cik"), episode.get("subject_cik")) or ""
        ).strip(),
        "ticker": str(
            _first_value(
                episode.get("ticker"),
                terms.get("target_ticker"),
                eligibility.get("ticker"),
            )
            or ""
        ).strip().upper(),
        "exchange": str(
            _first_value(
                episode.get("exchange"),
                terms.get("target_exchange"),
                eligibility.get("exchange"),
            )
            or ""
        ).strip().upper(),
        "filing_date": _date10(episode.get("filing_date")),
        "accepted_at": episode.get("accepted_at"),
        "announcement_date": _date10(
            _first_value(
                episode.get("announcement_or_agreement_date"),
                episode.get("agreement_or_announcement_date"),
                terms.get("announcement_or_agreement_date"),
                terms.get("agreement_or_announcement_date"),
            )
        ),
        "offer_price": _finite(
            _first_value(
                episode.get("offer_price"),
                episode.get("offer_price_usd"),
                terms.get("offer_price"),
                terms.get("offer_price_usd"),
            )
        ),
        "expiration_date": _date10(
            _first_value(
                episode.get("expiration_date"),
                episode.get("scheduled_expiration_date"),
                terms.get("expiration_date"),
                terms.get("scheduled_expiration_date"),
            )
        ),
        "policy_eligible": _first_value(
            episode.get("policy_eligible"), eligibility.get("eligible")
        ),
        "outcome": outcome,
        "outcome_status": status,
        "outcome_date": _date10(
            _first_value(
                outcome.get("date"),
                outcome.get("public_date"),
                outcome.get("outcome_date"),
                outcome.get("completion_date"),
                outcome.get("termination_date"),
                outcome.get("amendment_filing_date"),
            )
        ),
        "outcome_cash_price": _finite(
            _first_value(
                outcome.get("cash_price"),
                outcome.get("cash_price_usd"),
                outcome.get("actual_cash_price"),
                outcome.get("actual_cash_price_usd"),
                outcome.get("completion_cash_price_usd"),
            )
        ),
        "amendments": episode.get("amendments"),
        "target_price_role": "contract_cash_offer_price",
        "sec_provenance": {
            "accession_number": episode.get("accession_number"),
            "raw_submission_url": episode.get("raw_submission_url"),
            "raw_submission_sha256": episode.get("raw_submission_sha256"),
            "source_hashes": source_hashes,
            "source_documents": [dict(row) for row in source_documents],
            "terms_evidence_refs": list(terms.get("evidence_spans") or []),
            "outcome_evidence_refs": list(outcome.get("evidence_spans") or []),
            "outcome_amendment_accession_number": outcome.get(
                "amendment_accession_number"
            ),
        },
    }


def _row_value(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _finite(row.get(key))
        if value is not None:
            return value
    return None


def _looks_like_date_key(value: Any) -> bool:
    return _date10(value) is not None


def _resolve_price_payload(
    episode: Mapping[str, Any],
    fields: Mapping[str, Any],
    ohlcv_by_episode: Any,
) -> Any:
    if not isinstance(ohlcv_by_episode, Mapping):
        return ohlcv_by_episode
    if isinstance(ohlcv_by_episode.get("rows"), Sequence):
        return ohlcv_by_episode
    if ohlcv_by_episode and all(_looks_like_date_key(key) for key in ohlcv_by_episode):
        return ohlcv_by_episode
    keys = (
        fields.get("accession_number"),
        fields.get("ticker"),
        str(fields.get("ticker") or "").lower(),
        fields.get("target_cik"),
        str(fields.get("target_cik") or "").lstrip("0"),
    )
    for key in keys:
        if key and key in ohlcv_by_episode:
            return ohlcv_by_episode[key]
    # A caller may retain the exact episode mapping as the key.
    try:
        if episode in ohlcv_by_episode:
            return ohlcv_by_episode[episode]
    except TypeError:
        pass
    return None


def _raw_ohlcv_rows_through(payload: Any, as_of: str) -> list[Any]:
    """Return raw rows no later than ``as_of`` without validating future rows."""

    if hasattr(payload, "iterrows"):
        raw_rows = []
        for fallback, row in payload.iterrows():
            value = row.to_dict() if hasattr(row, "to_dict") else row
            if isinstance(value, Mapping):
                value = {**dict(value), "date": value.get("date") or fallback}
            raw_rows.append(value)
    elif isinstance(payload, Mapping) and isinstance(payload.get("rows"), Sequence):
        raw_rows = list(payload.get("rows") or [])
    elif isinstance(payload, Mapping):
        raw_rows = [
            ({**dict(row), "date": row.get("date") or key} if isinstance(row, Mapping) else row)
            for key, row in payload.items()
        ]
    elif isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
        raw_rows = list(payload)
    else:
        raw_rows = []
    result: list[Any] = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            result.append(row)
            continue
        row_day = _date10(
            _first_value(
                row.get("date"),
                row.get("Date"),
                row.get("datetime"),
                row.get("Datetime"),
                row.get("timestamp"),
                row.get("time_key"),
            )
        )
        # An unparseable date is retained so normalization fails closed.
        if row_day is None or row_day <= as_of:
            result.append(row)
    return result


def _normalise_ohlcv(payload: Any) -> tuple[dict[str, dict[str, float]], list[str]]:
    errors: list[str] = []
    if hasattr(payload, "iterrows"):
        candidates = list(payload.iterrows())
    elif isinstance(payload, Mapping):
        if isinstance(payload.get("rows"), Sequence) and not isinstance(
            payload.get("rows"), (str, bytes, bytearray)
        ):
            candidates = [(None, row) for row in payload["rows"]]
        else:
            candidates = list(payload.items())
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        candidates = [(None, row) for row in payload]
    else:
        candidates = []
    bars: dict[str, dict[str, float]] = {}
    for fallback, raw in candidates:
        if not isinstance(raw, Mapping) and hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        if not isinstance(raw, Mapping):
            errors.append("non_mapping_ohlcv_row")
            continue
        day = next(
            (
                _date10(raw.get(key))
                for key in ("date", "Date", "datetime", "Datetime", "timestamp", "time_key")
                if _date10(raw.get(key))
            ),
            _date10(fallback),
        )
        open_price = _row_value(raw, "open", "Open")
        high = _row_value(raw, "high", "High")
        low = _row_value(raw, "low", "Low")
        close = _row_value(raw, "close", "Close")
        volume = _row_value(raw, "volume", "Volume")
        if not day or None in (open_price, high, low, close, volume):
            errors.append("incomplete_ohlcv_row")
            continue
        assert open_price is not None and high is not None and low is not None
        assert close is not None and volume is not None
        if min(open_price, high, low, close) <= 0 or volume < 0:
            errors.append("invalid_ohlcv_value")
            continue
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            errors.append("invalid_ohlcv_range")
            continue
        if day in bars:
            errors.append("duplicate_ohlcv_session")
            continue
        bars[day] = {
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        }
    return dict(sorted(bars.items())), sorted(set(errors))


def _regular_sessions(start: str, end: str) -> list[str]:
    current = date.fromisoformat(start)
    finish = date.fromisoformat(end)
    result: list[str] = []
    while current <= finish:
        if is_us_equity_session(current):
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _next_session_after(
    anchor: str,
    *,
    offset: int = 1,
    calendar_sessions: Sequence[Any] | None = None,
) -> str:
    if calendar_sessions is not None:
        known = sorted(
            {
                day
                for raw in calendar_sessions
                if (day := _date10(raw)) is not None and day > anchor
            }
        )
        if len(known) >= offset:
            return known[offset - 1]
    current = date.fromisoformat(anchor)
    found = 0
    while found < offset:
        current += timedelta(days=1)
        if is_us_equity_session(current):
            found += 1
    return current.isoformat()


def _session_on_or_after(
    anchor: str, *, calendar_sessions: Sequence[Any] | None = None
) -> str:
    if calendar_sessions is not None:
        known = sorted(
            {
                day
                for raw in calendar_sessions
                if (day := _date10(raw)) is not None and day >= anchor
            }
        )
        if known:
            return known[0]
    current = date.fromisoformat(anchor)
    while not is_us_equity_session(current):
        current += timedelta(days=1)
    return current.isoformat()


def _strict_prior_rows(
    bars: Mapping[str, Mapping[str, float]], anchor: str, count: int
) -> list[Mapping[str, float]]:
    dates = [day for day in sorted(bars) if day < anchor]
    return [bars[day] for day in dates[-count:]]


def _last_close(
    bars: Mapping[str, Mapping[str, float]], day: str
) -> tuple[float | None, str | None]:
    dates = [candidate for candidate in sorted(bars) if candidate <= day]
    if not dates:
        return None, None
    mark_day = dates[-1]
    return float(bars[mark_day]["close"]), mark_day


def _invalidating_amendment(amendment: Mapping[str, Any]) -> bool:
    eligibility = _mapping(amendment.get("eligibility"))
    explicit = _first_value(
        amendment.get("invalidates_policy"),
        amendment.get("policy_invalidated"),
    )
    if explicit is True:
        return True
    if amendment.get("policy_eligible") is False or eligibility.get("eligible") is False:
        return True
    status = _normalise_status(
        _first_value(
            amendment.get("status"),
            amendment.get("outcome_type"),
            _mapping(amendment.get("outcome")).get("status"),
            _mapping(amendment.get("outcome")).get("outcome_type"),
        )
    )
    return status in {"policy_invalid", "invalid", "ineligible", "offer_invalidated"}


def _amendment_date(amendment: Mapping[str, Any]) -> str | None:
    outcome = _mapping(amendment.get("outcome"))
    return _date10(
        _first_value(
            amendment.get("date"),
            amendment.get("public_date"),
            amendment.get("filing_date"),
            amendment.get("amendment_filing_date"),
            outcome.get("date"),
            outcome.get("public_date"),
        )
    )


def _public_before_entry_open(
    public_date: str | None,
    accepted_at: Any,
    entry_date: str,
) -> bool | None:
    """Return whether an event was public before entry, or None if unknowable."""

    if not public_date:
        return None
    if public_date < entry_date:
        return True
    if public_date > entry_date:
        return False
    text = str(accepted_at or "").strip()
    if not text:
        return None
    accepted_day = _date10(text)
    if accepted_day and accepted_day != public_date:
        return None
    time_text = text[11:19] if len(text) >= 16 else ""
    pieces = time_text.split(":")
    try:
        hour = int(pieces[0])
        minute = int(pieces[1])
        second = int(pieces[2]) if len(pieces) > 2 else 0
    except (IndexError, TypeError, ValueError):
        return None
    return (hour, minute, second) < (9, 30, 0)


def _first_executable_open_after_publication(
    public_date: str,
    accepted_at: Any,
    *,
    calendar_sessions: Sequence[Any] | None = None,
) -> str:
    before_open = _public_before_entry_open(
        public_date, accepted_at, public_date
    )
    if before_open is True:
        return _session_on_or_after(
            public_date, calendar_sessions=calendar_sessions
        )
    return _next_session_after(
        public_date, calendar_sessions=calendar_sessions
    )


def _completion_cash_price_as_of(
    *,
    fields: Mapping[str, Any],
    amendments: Sequence[Mapping[str, Any]],
    completion_date: str,
    amendment_outcome: Mapping[str, Any] | None = None,
) -> float | None:
    """Resolve only contractual cash information public by completion."""

    local_outcome = _mapping(amendment_outcome)
    explicit_local = _finite(
        _first_value(
            local_outcome.get("cash_price"),
            local_outcome.get("cash_price_usd"),
            local_outcome.get("actual_cash_price"),
            local_outcome.get("actual_cash_price_usd"),
            local_outcome.get("completion_cash_price_usd"),
        )
    )
    if explicit_local and explicit_local > 0:
        return explicit_local

    price_events: list[tuple[str, str, float]] = []
    for amendment in amendments:
        public_date = _amendment_date(amendment)
        if not public_date or public_date > completion_date:
            continue
        outcome = _mapping(amendment.get("outcome"))
        outcome_status = _normalise_status(
            _first_value(outcome.get("status"), outcome.get("outcome_type"))
        )
        accepted_revision = bool(
            outcome_status in _COMPLETED
            or outcome.get("accepted_revised_offer") is True
            or outcome.get("revised_offer_accepted") is True
            or outcome.get("offer_price_revised") is True
        )
        higher_price = _finite(outcome.get("higher_bid_price_usd"))
        if accepted_revision and higher_price and higher_price > 0:
            price_events.append(
                (
                    public_date,
                    str(amendment.get("accession_number") or ""),
                    higher_price,
                )
            )
    aggregate_outcome = _mapping(fields.get("outcome"))
    for row in aggregate_outcome.get("higher_bid_prices") or []:
        if not isinstance(row, Mapping):
            continue
        if not (
            row.get("accepted_revised_offer") is True
            or row.get("revised_offer_accepted") is True
            or row.get("offer_price_revised") is True
        ):
            continue
        public_date = _date10(row.get("filing_date"))
        price = _finite(row.get("price_usd"))
        if public_date and public_date <= completion_date and price and price > 0:
            price_events.append(
                (
                    public_date,
                    str(row.get("accession_number") or ""),
                    price,
                )
            )
    if price_events:
        return sorted(price_events)[-1][2]

    aggregate_date = fields.get("outcome_date")
    aggregate_cash = _finite(fields.get("outcome_cash_price"))
    aggregate_has_unaccepted_bid_prices = bool(
        aggregate_outcome.get("higher_bid_prices")
    ) and not bool(
        aggregate_outcome.get("cash_price_is_actual") is True
        or aggregate_outcome.get("accepted_revised_offer") is True
        or aggregate_outcome.get("revised_offer_accepted") is True
    )
    if (
        aggregate_date == completion_date
        and aggregate_cash
        and aggregate_cash > 0
        and not aggregate_has_unaccepted_bid_prices
    ):
        return aggregate_cash
    offer = _finite(fields.get("offer_price"))
    return offer if offer and offer > 0 else None


def _prepare_candidate(
    episode: Mapping[str, Any],
    ohlcv_by_episode: Any,
    *,
    event_fee_usd: float,
    start: str,
    end: str,
    calendar_sessions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    fields = _episode_fields(episode)
    reasons: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition and reason not in reasons:
            reasons.append(reason)

    require(bool(fields["accession_number"]), "missing_accession_number")
    require(bool(fields["target_cik"]), "missing_target_cik")
    require(bool(fields["ticker"]), "missing_ticker")
    require(bool(fields["exchange"]), "missing_exchange")
    require(bool(fields["filing_date"]), "missing_or_invalid_filing_date")
    require(bool(fields["accepted_at"]), "missing_accepted_at")
    require(bool(fields["announcement_date"]), "missing_announcement_or_agreement_date")
    require(
        fields["offer_price"] is not None and float(fields["offer_price"] or 0.0) > 0,
        "missing_or_invalid_offer_price",
    )
    require(bool(fields["expiration_date"]), "missing_or_invalid_expiration_date")
    require(fields["policy_eligible"] is True, "policy_ineligible_or_unverified")
    require(isinstance(fields["outcome"], Mapping) and bool(fields["outcome"]), "missing_outcome")
    amendments = fields["amendments"]
    require(
        isinstance(amendments, Sequence) and not isinstance(amendments, (str, bytes, bytearray)),
        "missing_or_invalid_amendments",
    )

    status = str(fields["outcome_status"])
    require(
        status
        in _COMPLETED
        | _TERMINATED_NEGATIVE
        | _TERMINATED_HIGHER_BID
        | _HIGHER_BID_PUBLIC
        | _PENDING,
        "unknown_outcome_status",
    )
    if status in (
        _COMPLETED
        | _TERMINATED_NEGATIVE
        | _TERMINATED_HIGHER_BID
        | _HIGHER_BID_PUBLIC
    ):
        require(bool(fields["outcome_date"]), "missing_outcome_public_date")
    if status in _COMPLETED:
        require(
            fields["outcome_cash_price"] is not None
            and float(fields["outcome_cash_price"] or 0.0) > 0,
            "missing_actual_completion_cash_price",
        )

    payload = _resolve_price_payload(episode, fields, ohlcv_by_episode)
    bars, bar_errors = _normalise_ohlcv(_raw_ohlcv_rows_through(payload, end))
    require(bool(bars), "missing_complete_ohlcv")
    require(not bar_errors, "invalid_ohlcv_rows")

    filing = fields["filing_date"]
    entry_date = (
        _next_session_after(filing, calendar_sessions=calendar_sessions)
        if filing
        else None
    )
    if filing:
        require(start <= filing <= end, "filing_outside_replay_window")
    if entry_date:
        require(start <= entry_date <= end, "entry_outside_replay_window")
        require(entry_date in bars, "missing_first_post_filing_session_open")

    announcement = fields["announcement_date"]
    break_rows = (
        _strict_prior_rows(bars, announcement, BREAK_LOOKBACK_SESSIONS)
        if announcement
        else []
    )
    require(
        len(break_rows) == BREAK_LOOKBACK_SESSIONS,
        "insufficient_strict_prior_20_close_break_history",
    )
    break_value = mean(float(row["close"]) for row in break_rows) if break_rows else None

    adv_rows = (
        _strict_prior_rows(bars, entry_date, ADV_LOOKBACK_SESSIONS)
        if entry_date
        else []
    )
    require(len(adv_rows) == ADV_LOOKBACK_SESSIONS, "insufficient_strict_prior_20_session_adv")
    avg_dollar_adv = (
        mean(float(row["close"]) * float(row["volume"]) for row in adv_rows)
        if adv_rows
        else None
    )
    entry_price = (
        float(bars[entry_date]["open"])
        if entry_date and entry_date in bars
        else None
    )
    expiration = fields["expiration_date"]
    carry_days_to_expiration = (
        (date.fromisoformat(expiration) - date.fromisoformat(entry_date)).days
        if expiration and entry_date
        else None
    )
    require(
        carry_days_to_expiration is not None and carry_days_to_expiration > 0,
        "expiration_not_after_entry",
    )
    projected_carry_per_share = (
        float(entry_price) * CARRY_ANNUAL_RATE * float(carry_days_to_expiration) / 365.0
        if entry_price is not None and carry_days_to_expiration is not None
        else None
    )
    discounted_offer = (
        float(fields["offer_price"]) - float(projected_carry_per_share)
        if fields["offer_price"] is not None and projected_carry_per_share is not None
        else None
    )
    denominator = (
        float(discounted_offer) - float(break_value)
        if discounted_offer is not None and break_value is not None
        else None
    )
    implied_probability = (
        (float(entry_price) - float(break_value)) / float(denominator)
        if entry_price is not None and break_value is not None and denominator and denominator > 0
        else None
    )
    require(denominator is not None and denominator > 0, "discounted_offer_not_above_break")
    require(
        implied_probability is not None
        and 0.0 <= implied_probability <= 1.0
        and implied_probability >= MIN_IMPLIED_COMPLETION_PROBABILITY,
        "implied_completion_probability_below_70pct",
    )

    max_shares_by_deal = (
        math.floor(MAX_DEAL_NOTIONAL_USD / float(entry_price)) if entry_price else 0
    )
    raw_price_risk_per_share = (
        max(0.0, float(entry_price) - float(break_value))
        if entry_price is not None and break_value is not None
        else None
    )
    risk_per_share = (
        float(raw_price_risk_per_share)
        + float(entry_price) * HALF_TRADE_COST_RATE
        + float(break_value) * HALF_TRADE_COST_RATE
        if raw_price_risk_per_share is not None
        and entry_price is not None
        and break_value is not None
        else None
    )
    max_shares_by_break = (
        math.floor(
            max(0.0, MAX_PREDICTED_BREAK_LOSS_USD - event_fee_usd)
            / risk_per_share
        )
        if risk_per_share and risk_per_share > 0
        else 0
    )
    max_shares_by_adv = (
        math.floor(float(avg_dollar_adv) * MAX_ADV_FRACTION / float(entry_price))
        if avg_dollar_adv and entry_price
        else 0
    )
    static_share_cap = min(max_shares_by_deal, max_shares_by_break, max_shares_by_adv)
    require(static_share_cap >= 1, "no_whole_shares_within_deal_break_and_adv_caps")

    projected_net_spread = None
    if static_share_cap >= 1 and entry_price and fields["offer_price"] is not None:
        entry_notional = static_share_cap * float(entry_price)
        projected_exit_value = static_share_cap * float(fields["offer_price"])
        projected_carry = static_share_cap * float(projected_carry_per_share or 0.0)
        projected_net_spread = (
            projected_exit_value
            - projected_exit_value * HALF_TRADE_COST_RATE
            - entry_notional
            - entry_notional * HALF_TRADE_COST_RATE
            - projected_carry
            - event_fee_usd
        )
    require(
        projected_net_spread is not None and projected_net_spread > 0,
        "net_spread_not_positive_after_cost_carry_and_event_fee",
    )

    invalid_amendments: list[dict[str, Any]] = []
    amendment_public_events: list[dict[str, Any]] = []
    if isinstance(amendments, Sequence) and not isinstance(amendments, (str, bytes, bytearray)):
        for amendment in amendments:
            if not isinstance(amendment, Mapping):
                continue
            public_date = _amendment_date(amendment)
            if _invalidating_amendment(amendment):
                if not public_date:
                    require(False, "invalidating_amendment_missing_public_date")
                invalid_amendments.append(
                    {
                        "accession_number": amendment.get("accession_number"),
                        "public_date": public_date,
                        "accepted_at": amendment.get("accepted_at"),
                    }
                )
            amendment_outcome = _mapping(amendment.get("outcome"))
            amendment_status = _normalise_status(
                _first_value(
                    amendment_outcome.get("status"),
                    amendment_outcome.get("outcome_type"),
                    amendment.get("status"),
                    amendment.get("outcome_type"),
                )
            )
            if amendment_status not in (
                _COMPLETED
                | _TERMINATED_NEGATIVE
                | _TERMINATED_HIGHER_BID
                | _HIGHER_BID_PUBLIC
            ):
                continue
            if not public_date:
                require(False, "decisive_amendment_missing_public_date")
                continue
            amendment_cash_price = (
                _completion_cash_price_as_of(
                    fields=fields,
                    amendments=[
                        row for row in amendments if isinstance(row, Mapping)
                    ],
                    completion_date=public_date,
                    amendment_outcome=amendment_outcome,
                )
                if amendment_status in _COMPLETED
                else None
            )
            if amendment_status in _COMPLETED and not amendment_cash_price:
                require(False, "completed_amendment_missing_actual_cash_price")
            if amendment_status in _COMPLETED:
                kind = "completed_cash_settlement"
            elif amendment_status in _HIGHER_BID_PUBLIC:
                kind = "higher_bid_pending_public_exit"
            else:
                kind = amendment_status
            amendment_public_events.append(
                {
                    "kind": kind,
                    "status": amendment_status,
                    "public_date": public_date,
                    "cash_price": amendment_cash_price,
                    "cash_price_source": (
                        "completion_amendment_explicit_or_original_fixed_offer_with_only_accepted_revisions"
                        if amendment_status in _COMPLETED
                        else None
                    ),
                    "amendment_accession_number": amendment.get("accession_number"),
                    "accepted_at": amendment.get("accepted_at"),
                }
            )
    invalid_amendments.sort(key=lambda row: str(row.get("public_date") or ""))
    if entry_date:
        for row in invalid_amendments:
            relation = _public_before_entry_open(
                _date10(row.get("public_date")), row.get("accepted_at"), entry_date
            )
            if relation is True:
                require(False, "policy_invalidating_amendment_public_before_entry")
            elif relation is None and row.get("public_date") == entry_date:
                require(False, "same_day_invalidating_amendment_timing_unverified")
        aggregate_accepted_at = fields["outcome"].get("accepted_at")
        aggregate_accession = fields["outcome"].get("amendment_accession_number")
        if not aggregate_accepted_at and aggregate_accession:
            aggregate_accepted_at = next(
                (
                    row.get("accepted_at")
                    for row in amendments
                    if isinstance(row, Mapping)
                    and row.get("accession_number") == aggregate_accession
                ),
                None,
            )
        if status in (
            _COMPLETED
            | _TERMINATED_NEGATIVE
            | _TERMINATED_HIGHER_BID
            | _HIGHER_BID_PUBLIC
        ):
            relation = _public_before_entry_open(
                _date10(fields["outcome_date"]), aggregate_accepted_at, entry_date
            )
            if relation is True:
                require(False, "decisive_outcome_public_before_entry")
            elif relation is None and fields["outcome_date"] == entry_date:
                require(False, "same_day_decisive_outcome_timing_unverified")
        for row in amendment_public_events:
            relation = _public_before_entry_open(
                _date10(row.get("public_date")), row.get("accepted_at"), entry_date
            )
            if relation is True:
                require(False, "decisive_amendment_public_before_entry")
            elif relation is None and row.get("public_date") == entry_date:
                require(False, "same_day_decisive_amendment_timing_unverified")

    exit_action: dict[str, Any] | None = None
    if entry_date:
        possible: list[dict[str, Any]] = []
        for amendment_event in amendment_public_events:
            public_date = str(amendment_event["public_date"])
            completion = amendment_event["kind"] == "completed_cash_settlement"
            possible.append(
                {
                    **amendment_event,
                    "due_date": (
                        _next_session_after(
                            public_date,
                            offset=2,
                            calendar_sessions=calendar_sessions,
                        )
                        if completion
                        else _first_executable_open_after_publication(
                            public_date,
                            amendment_event.get("accepted_at"),
                            calendar_sessions=calendar_sessions,
                        )
                    ),
                }
            )
        if invalid_amendments and invalid_amendments[0].get("public_date"):
            public_date = str(invalid_amendments[0]["public_date"])
            possible.append(
                {
                    "kind": "policy_invalidating_amendment",
                    "public_date": public_date,
                    "due_date": _first_executable_open_after_publication(
                        public_date,
                        invalid_amendments[0].get("accepted_at"),
                        calendar_sessions=calendar_sessions,
                    ),
                    "cash_price": None,
                }
            )
        if status in _COMPLETED and fields["outcome_date"]:
            aggregate_completion_cash = _completion_cash_price_as_of(
                fields=fields,
                amendments=[row for row in amendments if isinstance(row, Mapping)],
                completion_date=str(fields["outcome_date"]),
            )
            possible.append(
                {
                    "kind": "completed_cash_settlement",
                    "public_date": fields["outcome_date"],
                    "due_date": _next_session_after(
                        str(fields["outcome_date"]),
                        offset=2,
                        calendar_sessions=calendar_sessions,
                    ),
                    "cash_price": aggregate_completion_cash,
                    "cash_price_source": (
                        "aggregate_completion_explicit_or_original_fixed_offer_with_only_accepted_revisions"
                    ),
                }
            )
        elif status in _TERMINATED_NEGATIVE | _TERMINATED_HIGHER_BID and fields["outcome_date"]:
            possible.append(
                {
                    "kind": status,
                    "public_date": fields["outcome_date"],
                    "due_date": _next_session_after(
                        str(fields["outcome_date"]), calendar_sessions=calendar_sessions
                    ),
                    "cash_price": None,
                }
            )
        elif status in _HIGHER_BID_PUBLIC and fields["outcome_date"]:
            possible.append(
                {
                    "kind": "higher_bid_pending_public_exit",
                    "public_date": fields["outcome_date"],
                    "due_date": _next_session_after(
                        str(fields["outcome_date"]), calendar_sessions=calendar_sessions
                    ),
                    "cash_price": None,
                }
            )
        timeout_anchor = (
            date.fromisoformat(entry_date) + timedelta(days=TIMEOUT_CALENDAR_DAYS)
        ).isoformat()
        possible.append(
            {
                "kind": "365_calendar_day_timeout",
                "public_date": None,
                "due_date": _session_on_or_after(
                    timeout_anchor, calendar_sessions=calendar_sessions
                ),
                "cash_price": None,
            }
        )
        exit_action = sorted(possible, key=lambda row: (str(row["due_date"]), str(row["kind"])))[0]

    return {
        "candidate_id": f"{RULE_VERSION}:{fields['accession_number'] or 'missing'}",
        **fields,
        "entry_date": entry_date,
        "target_price": fields["offer_price"],
        "entry_price": entry_price,
        "break_value": break_value,
        "break_value_method": "arithmetic_mean_of_strictly_prior_20_session_closes",
        "break_lookback_session_count": len(break_rows),
        "avg_dollar_adv_20": avg_dollar_adv,
        "adv_lookback_session_count": len(adv_rows),
        "carry_days_to_expiration": carry_days_to_expiration,
        "projected_carry_per_share": projected_carry_per_share,
        "discounted_offer": discounted_offer,
        "implied_completion_probability": implied_probability,
        "max_shares_by_deal_cap": max_shares_by_deal,
        "max_shares_by_break_loss": max_shares_by_break,
        "max_shares_by_adv": max_shares_by_adv,
        "static_share_cap": static_share_cap,
        "projected_net_spread_usd_at_static_cap": projected_net_spread,
        "risk_per_share_to_break": risk_per_share,
        "raw_price_risk_per_share_to_break": raw_price_risk_per_share,
        "predicted_break_loss_method": (
            "entry_minus_break_plus_both_side_17_5bp_costs_plus_flat_event_fee"
        ),
        "invalidating_amendments": invalid_amendments,
        "amendment_public_events": amendment_public_events,
        "exit_action": exit_action,
        "ohlcv": bars,
        "ohlcv_errors": bar_errors,
        "status": "eligible" if not reasons else "rejected",
        "eligible": not reasons,
        "rejection_reasons": reasons,
        "primary_rejection_reason": reasons[0] if reasons else None,
        "trade_enabled": False,
    }


def _carry_days(entry_date: str, as_of: str, *, open_at_close: bool) -> int:
    elapsed = (date.fromisoformat(as_of) - date.fromisoformat(entry_date)).days
    return max(0, elapsed + (1 if open_at_close else 0))


def _accrued_carry(position: Mapping[str, Any], as_of: str, *, open_at_close: bool) -> float:
    return (
        float(position["entry_notional"])
        * CARRY_ANNUAL_RATE
        * _carry_days(str(position["entry_date"]), as_of, open_at_close=open_at_close)
        / 365.0
    )


def _trade_from_exit(
    position: Mapping[str, Any],
    *,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
    actual_cash_payout: bool,
) -> dict[str, Any]:
    shares = int(position["shares"])
    gross_proceeds = shares * float(exit_price)
    exit_cost = gross_proceeds * HALF_TRADE_COST_RATE
    carry = _accrued_carry(position, exit_date, open_at_close=False)
    net_pnl = (
        gross_proceeds
        - exit_cost
        - float(position["event_fee_usd"])
        - carry
        - float(position["entry_notional"])
        - float(position["entry_trade_cost"])
    )
    return {
        **{key: value for key, value in position.items() if key != "ohlcv"},
        "exit_date": exit_date,
        "valuation_date": exit_date,
        "exit_price": float(exit_price),
        "valuation_price": float(exit_price),
        "exit_reason": exit_reason,
        "actual_cash_payout": bool(actual_cash_payout),
        "cash_payout_price_source": (
            _mapping(position.get("exit_action")).get("cash_price_source")
            if actual_cash_payout
            else None
        ),
        "actual_close": True,
        "right_censored": False,
        "gross_proceeds": gross_proceeds,
        "exit_trade_cost": exit_cost,
        "carry_days": _carry_days(
            str(position["entry_date"]), exit_date, open_at_close=False
        ),
        "accrued_carry": carry,
        "net_pnl_usd": net_pnl,
        "return_on_entry_notional": net_pnl / float(position["entry_notional"]),
        "trade_enabled": False,
    }


def _right_censored_trade(position: Mapping[str, Any], final_day: str) -> dict[str, Any]:
    mark_price, mark_date = _last_close(_mapping(position.get("ohlcv")), final_day)
    if mark_price is None:
        mark_price = float(position["entry_price"])
        mark_date = str(position["entry_date"])
    shares = int(position["shares"])
    market_value = shares * mark_price
    estimated_exit_cost = market_value * HALF_TRADE_COST_RATE
    carry = _accrued_carry(position, final_day, open_at_close=True)
    net_pnl = (
        market_value
        - estimated_exit_cost
        - float(position["event_fee_usd"])
        - carry
        - float(position["entry_notional"])
        - float(position["entry_trade_cost"])
    )
    return {
        **{key: value for key, value in position.items() if key != "ohlcv"},
        "exit_date": None,
        "valuation_date": final_day,
        "exit_price": None,
        "valuation_price": mark_price,
        "valuation_price_date": mark_date,
        "mark_is_exact_window_close": mark_date == final_day,
        "exit_reason": None,
        "actual_cash_payout": False,
        "cash_payout_price_source": None,
        "actual_close": False,
        "right_censored": True,
        "censor_reason": position.get("terminally_blocked_reason")
        or "window_end_mark_to_market",
        "gross_proceeds": None,
        "market_value": market_value,
        "estimated_exit_trade_cost": estimated_exit_cost,
        "carry_days": _carry_days(
            str(position["entry_date"]), final_day, open_at_close=True
        ),
        "accrued_carry": carry,
        "net_pnl_usd": net_pnl,
        "return_on_entry_notional": net_pnl / float(position["entry_notional"]),
        "trade_enabled": False,
    }


def _max_drawdown(daily_ledger: Sequence[Mapping[str, Any]]) -> float:
    peak = SLEEVE_CAPITAL_USD
    worst = 0.0
    for row in daily_ledger:
        equity = float(row.get("equity") or 0.0)
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return worst


def compute_sec_cash_tender_spread_metrics(
    daily_ledger_or_result: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    trades: Sequence[Mapping[str, Any]] | None = None,
    *,
    signals_generated: int | None = None,
    signals_survived: int | None = None,
    candidate_rejections: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute sign-preserving EV and audit metrics from the paper ledger."""

    if isinstance(daily_ledger_or_result, Mapping):
        source = daily_ledger_or_result
        daily_ledger = list(source.get("daily_ledger") or [])
        if trades is None:
            trades = list(source.get("trades") or [])
        if signals_generated is None:
            signals_generated = int(source.get("signals_generated") or 0)
        if signals_survived is None:
            signals_survived = int(source.get("signals_survived") or 0)
        if candidate_rejections is None:
            candidate_rejections = list(source.get("candidate_rejections") or [])
    else:
        daily_ledger = list(daily_ledger_or_result)
    trade_rows = [row for row in (trades or []) if isinstance(row, Mapping)]
    actual_trade_rows = [row for row in trade_rows if bool(row.get("actual_close"))]
    generated = int(signals_generated or 0)
    survived = int(signals_survived or 0)
    ending_equity = (
        float(daily_ledger[-1].get("equity") or 0.0)
        if daily_ledger
        else SLEEVE_CAPITAL_USD
    )
    total_pnl = ending_equity - SLEEVE_CAPITAL_USD
    total_return = total_pnl / SLEEVE_CAPITAL_USD
    returns = [
        float(row["daily_return"])
        for row in daily_ledger
        if _finite(row.get("daily_return")) is not None
    ]
    sharpe_daily = 0.0
    if len(returns) >= 2:
        volatility = stdev(returns)
        if volatility > 0:
            sharpe_daily = mean(returns) / volatility * math.sqrt(252.0)
    expected_value_score = compute_expected_value_score(
        {
            "benchmarks": {"strategy_total_return_pct": total_return},
            "sharpe_daily": sharpe_daily,
        }
    )
    pnls = [float(row.get("net_pnl_usd") or 0.0) for row in trade_rows]
    actual_pnls = [
        float(row.get("net_pnl_usd") or 0.0) for row in actual_trade_rows
    ]

    def concentration_for(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        row_pnls = [float(row.get("net_pnl_usd") or 0.0) for row in rows]
        positive_total = sum(value for value in row_pnls if value > 0)
        ticker_pnl: dict[str, float] = {}
        ticker_counts = Counter()
        for row, pnl in zip(rows, row_pnls):
            ticker = str(row.get("ticker") or "")
            if ticker:
                ticker_pnl[ticker] = ticker_pnl.get(ticker, 0.0) + pnl
                ticker_counts[ticker] += 1
        positive_ticker_pnl = {
            ticker: value
            for ticker, value in sorted(ticker_pnl.items())
            if value > 0
        }
        return {
            "population": "actual_closed_realized_rows",
            "row_count": len(rows),
            "by_ticker_count": dict(sorted(ticker_counts.items())),
            "by_ticker_pnl_usd": dict(sorted(ticker_pnl.items())),
            "maximum_single_deal_positive_pnl_share": (
                max((value for value in row_pnls if value > 0), default=0.0)
                / positive_total
                if positive_total > 0
                else None
            ),
            "maximum_positive_ticker_pnl_share": (
                max(positive_ticker_pnl.values(), default=0.0) / positive_total
                if positive_total > 0
                else None
            ),
            "positive_ticker_pnl_hhi": (
                sum(
                    (value / positive_total) ** 2
                    for value in positive_ticker_pnl.values()
                )
                if positive_total > 0
                else None
            ),
        }

    concentration = concentration_for(actual_trade_rows)
    mtm_inclusive_concentration = concentration_for(trade_rows)
    mtm_inclusive_concentration["population"] = (
        "entered_rows_including_right_censored_window_end_mtm"
    )
    equity_identity_passed = all(
        abs(
            float(row.get("cash") or 0.0)
            + float(row.get("market_value") or 0.0)
            - float(row.get("accrued_carry") or 0.0)
            - float(row.get("accrued_exit_cost") or 0.0)
            - float(row.get("accrued_event_fees") or 0.0)
            - float(row.get("equity") or 0.0)
        )
        <= 1e-6
        for row in daily_ledger
    )
    cash_transition_reconciliation_passed = all(
        abs(float(row.get("cash_transition_error") or 0.0)) <= 1e-6
        for row in daily_ledger
    )
    return {
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": survived / generated if generated else None,
        "candidate_rejection_count": len(candidate_rejections or []),
        "trade_count": len(actual_trade_rows),
        "entered_trade_count": survived,
        "funded_entry_count": survived,
        "mtm_inclusive_trade_count": len(trade_rows),
        "actual_closed_trade_count": sum(bool(row.get("actual_close")) for row in trade_rows),
        "right_censored_trade_count": sum(bool(row.get("right_censored")) for row in trade_rows),
        "win_rate": (
            sum(value > 0 for value in actual_pnls) / len(actual_pnls)
            if actual_pnls
            else None
        ),
        "realized_win_rate": (
            sum(value > 0 for value in actual_pnls) / len(actual_pnls)
            if actual_pnls
            else None
        ),
        "mtm_inclusive_win_rate": (
            sum(value > 0 for value in pnls) / len(pnls) if pnls else None
        ),
        "total_pnl": total_pnl,
        "strategy_total_return_pct": total_return,
        "sharpe_daily": sharpe_daily,
        "expected_value_score": expected_value_score,
        "max_drawdown_pct": _max_drawdown(daily_ledger),
        "ending_equity": ending_equity,
        "minimum_cash": min(
            (float(row.get("cash") or 0.0) for row in daily_ledger),
            default=SLEEVE_CAPITAL_USD,
        ),
        "maximum_open_count": max(
            (int(row.get("open_count") or 0) for row in daily_ledger), default=0
        ),
        "maximum_concurrent_notional": max(
            (float(row.get("open_entry_notional") or 0.0) for row in daily_ledger),
            default=0.0,
        ),
        "cash_nonnegative": all(
            float(row.get("cash") or 0.0) >= -1e-7 for row in daily_ledger
        ),
        "equity_identity_passed": equity_identity_passed,
        "cash_transition_reconciliation_passed": (
            cash_transition_reconciliation_passed
        ),
        "cash_conservation_passed": (
            equity_identity_passed and cash_transition_reconciliation_passed
        ),
        "concentration": concentration,
        "realized_concentration": concentration,
        "mtm_inclusive_concentration": mtm_inclusive_concentration,
    }


# A concise public alias for experiment runners.
summarize_sec_cash_tender_spread_replay = compute_sec_cash_tender_spread_metrics


def _run_replay_core(
    episodes: Sequence[Mapping[str, Any]],
    ohlcv_by_episode: Any,
    *,
    start: str,
    end: str,
    event_fee_usd: float,
    calendar_sessions: Sequence[Any] | None,
    right_censor_at_end: bool,
) -> dict[str, Any]:
    if calendar_sessions is None:
        sessions = _regular_sessions(start, end)
    else:
        sessions = sorted(
            {
                day
                for raw in calendar_sessions
                if (day := _date10(raw)) is not None
                and start <= day <= end
                and is_us_equity_session(day)
            }
        )

    candidates: list[dict[str, Any]] = []
    duplicate_accessions: set[str] = set()
    seen_accessions: set[str] = set()
    for raw_episode in episodes:
        episode = raw_episode if isinstance(raw_episode, Mapping) else {}
        candidate = _prepare_candidate(
            episode,
            ohlcv_by_episode,
            event_fee_usd=event_fee_usd,
            start=start,
            end=end,
            calendar_sessions=calendar_sessions,
        )
        accession = str(candidate.get("accession_number") or "")
        if accession and accession in seen_accessions:
            candidate["eligible"] = False
            candidate["status"] = "rejected"
            candidate["rejection_reasons"] = list(candidate["rejection_reasons"]) + [
                "duplicate_accession_number"
            ]
            candidate["primary_rejection_reason"] = candidate["rejection_reasons"][0]
            duplicate_accessions.add(accession)
        if accession:
            seen_accessions.add(accession)
        candidates.append(candidate)

    entry_queue: dict[str, list[dict[str, Any]]] = {}
    candidate_rejections: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["eligible"]:
            entry_queue.setdefault(str(candidate["entry_date"]), []).append(candidate)
        else:
            candidate_rejections.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "accession_number": candidate["accession_number"],
                    "ticker": candidate["ticker"],
                    "status": "rejected_before_entry",
                    "rejection_reasons": list(candidate["rejection_reasons"]),
                    "primary_rejection_reason": candidate["primary_rejection_reason"],
                    "trade_enabled": False,
                }
            )
    for rows in entry_queue.values():
        rows.sort(key=lambda row: (str(row.get("accepted_at") or ""), str(row["accession_number"])))

    cash = SLEEVE_CAPITAL_USD
    positions: dict[str, dict[str, Any]] = {}
    closed_trades: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    measurement_failures: list[dict[str, Any]] = []
    daily_ledger: list[dict[str, Any]] = []
    previous_equity = SLEEVE_CAPITAL_USD
    entries_funded = 0

    for day in sessions:
        opening_cash = cash
        opening_liability_reserve = sum(
            float(position.get("cash_liability_reserve") or 0.0)
            for position in positions.values()
        )
        entry_cash_outflow = 0.0
        exit_net_cash_inflow = 0.0
        # Exits are booked first, but their proceeds cannot fund an entry at the
        # same open.  This makes the no-reuse/no-leverage boundary explicit.
        for candidate_id, position in list(positions.items()):
            action = _mapping(position.get("exit_action"))
            if str(action.get("due_date") or "") != day:
                continue
            kind = str(action.get("kind") or "")
            actual_cash = kind == "completed_cash_settlement"
            if actual_cash:
                exit_price = _finite(action.get("cash_price"))
            else:
                bar = _mapping(position.get("ohlcv")).get(day)
                exit_price = _finite(_mapping(bar).get("open"))
            if exit_price is None or exit_price <= 0:
                position["event_exit_missed"] = True
                position["terminally_blocked"] = True
                position["terminally_blocked_reason"] = (
                    "missing_exact_required_event_exit_open"
                )
                position["exit_action"] = {
                    **dict(action),
                    "status": "terminally_blocked_missing_exact_open",
                }
                failure = {
                    "candidate_id": candidate_id,
                    "accession_number": position.get("accession_number"),
                    "ticker": position.get("ticker"),
                    "date": day,
                    "reason": "missing_exact_required_event_exit_open",
                    "exit_reason": kind,
                }
                measurement_failures.append(failure)
                events.append({**failure, "event": "event_exit_failed_closed"})
                continue
            trade = _trade_from_exit(
                position,
                exit_date=day,
                exit_price=float(exit_price),
                exit_reason=kind,
                actual_cash_payout=actual_cash,
            )
            net_cash_inflow = (
                float(trade["gross_proceeds"])
                - float(trade["exit_trade_cost"])
                - float(trade["event_fee_usd"])
                - float(trade["accrued_carry"])
            )
            cash += net_cash_inflow
            exit_net_cash_inflow += net_cash_inflow
            if cash < -1e-7:
                raise RuntimeError("cash invariant violated while closing tender position")
            closed_trades.append(trade)
            del positions[candidate_id]
            events.append(
                {
                    "event": "exited",
                    "candidate_id": candidate_id,
                    "date": day,
                    "exit_reason": kind,
                    "actual_cash_payout": actual_cash,
                    "net_pnl_usd": trade["net_pnl_usd"],
                    "trade_enabled": False,
                }
            )

        # Opening cash already contains the liability reserves for positions
        # carried into the session.  Same-open exits do not release those
        # reserves into today's entry budget.
        entry_cash_budget = max(0.0, opening_cash - opening_liability_reserve)
        for candidate in entry_queue.get(day, []):
            entry_price = float(candidate["entry_price"])
            open_notional = sum(float(row["entry_notional"]) for row in positions.values())
            maximum_exit_reference = max(
                entry_price, float(candidate["offer_price"])
            )
            # Reserve independently of future outcome knowledge.  Seven extra
            # calendar days cover a weekend/holiday before the timeout open.
            maximum_carry_days = TIMEOUT_CALENDAR_DAYS + 7
            maximum_carry_fraction = (
                CARRY_ANNUAL_RATE * maximum_carry_days / 365.0
            )
            per_share_funded_requirement = (
                entry_price * (1.0 + HALF_TRADE_COST_RATE)
                + entry_price * maximum_carry_fraction
                + maximum_exit_reference * HALF_TRADE_COST_RATE
            )
            fundable_cash = min(entry_cash_budget, cash)
            cash_cap = math.floor(
                max(0.0, fundable_cash - event_fee_usd)
                / per_share_funded_requirement
            )
            concurrent_cap = math.floor(
                max(0.0, MAX_CONCURRENT_NOTIONAL_USD - open_notional) / entry_price
            )
            shares = min(int(candidate["static_share_cap"]), cash_cap, concurrent_cap)
            dynamic_reasons: list[str] = []
            if shares < 1:
                if cash_cap < 1:
                    dynamic_reasons.append("insufficient_unreused_sleeve_cash")
                if concurrent_cap < 1:
                    dynamic_reasons.append("concurrent_notional_cap_exhausted")
                if not dynamic_reasons:
                    dynamic_reasons.append("no_whole_shares_after_dynamic_caps")
            entry_notional = shares * entry_price
            entry_trade_cost = entry_notional * HALF_TRADE_COST_RATE
            cash_liability_reserve = (
                event_fee_usd
                + entry_notional * maximum_carry_fraction
                + shares * maximum_exit_reference * HALF_TRADE_COST_RATE
            )
            projected_exit_value = shares * float(candidate["offer_price"])
            projected_net = (
                projected_exit_value
                - projected_exit_value * HALF_TRADE_COST_RATE
                - entry_notional
                - entry_trade_cost
                - shares * float(candidate["projected_carry_per_share"])
                - event_fee_usd
            )
            if shares >= 1 and projected_net <= 0:
                dynamic_reasons.append("net_spread_not_positive_at_funded_size")
            if dynamic_reasons:
                rejection = {
                    "candidate_id": candidate["candidate_id"],
                    "accession_number": candidate["accession_number"],
                    "ticker": candidate["ticker"],
                    "status": "rejected_at_entry",
                    "rejection_reasons": dynamic_reasons,
                    "primary_rejection_reason": dynamic_reasons[0],
                    "entry_date": day,
                    "available_cash": entry_cash_budget,
                    "open_entry_notional": open_notional,
                    "trade_enabled": False,
                }
                candidate_rejections.append(rejection)
                events.append({**rejection, "event": "entry_rejected"})
                continue

            required_cash = entry_notional + entry_trade_cost
            required_funded_budget = required_cash + cash_liability_reserve
            if (
                required_funded_budget > entry_cash_budget + 1e-7
                or required_cash > cash + 1e-7
            ):
                raise RuntimeError("entry sizing exceeded funded cash")
            position = {
                **{
                    key: value
                    for key, value in candidate.items()
                    if key
                    not in {
                        "ohlcv",
                        "outcome",
                        "amendments",
                        "rejection_reasons",
                    }
                },
                "shares": shares,
                "entry_notional": entry_notional,
                "entry_trade_cost": entry_trade_cost,
                "entry_cash_paid": required_cash,
                "cash_liability_reserve": cash_liability_reserve,
                "cash_reserve_carry_days": maximum_carry_days,
                "predicted_break_loss": shares
                * float(candidate["risk_per_share_to_break"])
                + event_fee_usd,
                "raw_predicted_price_break_loss": shares
                * float(candidate["raw_price_risk_per_share_to_break"]),
                "adv_fraction": entry_notional / float(candidate["avg_dollar_adv_20"]),
                "event_fee_usd": event_fee_usd,
                "projected_net_spread_usd": projected_net,
                "ohlcv": candidate["ohlcv"],
                "exit_action": candidate["exit_action"],
                "trade_enabled": False,
            }
            cash -= required_cash
            entry_cash_outflow += required_cash
            entry_cash_budget -= required_funded_budget
            if cash < -1e-7:
                raise RuntimeError("cash invariant violated while funding tender position")
            positions[candidate["candidate_id"]] = position
            entries_funded += 1
            events.append(
                {
                    "event": "entered",
                    "candidate_id": candidate["candidate_id"],
                    "accession_number": candidate["accession_number"],
                    "ticker": candidate["ticker"],
                    "date": day,
                    "entry_date": day,
                    "target_price": candidate["offer_price"],
                    "target_price_role": "contract_cash_offer_price",
                    "entry_price": entry_price,
                    "shares": shares,
                    "entry_notional": entry_notional,
                    "predicted_break_loss": position["predicted_break_loss"],
                    "trade_enabled": False,
                }
            )

        market_value = 0.0
        accrued_carry = 0.0
        accrued_exit_cost = 0.0
        accrued_event_fees = 0.0
        exact_mark_count = 0
        stale_mark_count = 0
        for position in positions.values():
            mark_price, mark_date = _last_close(_mapping(position.get("ohlcv")), day)
            if mark_price is None:
                mark_price = float(position["entry_price"])
                mark_date = str(position["entry_date"])
            value = int(position["shares"]) * mark_price
            market_value += value
            accrued_carry += _accrued_carry(position, day, open_at_close=True)
            accrued_exit_cost += value * HALF_TRADE_COST_RATE
            accrued_event_fees += float(position["event_fee_usd"])
            if mark_date == day:
                exact_mark_count += 1
            else:
                stale_mark_count += 1
        equity = cash + market_value - accrued_carry - accrued_exit_cost - accrued_event_fees
        daily_return = equity / previous_equity - 1.0 if previous_equity != 0 else None
        expected_cash = opening_cash - entry_cash_outflow + exit_net_cash_inflow
        row = {
            "date": day,
            "as_of": day,
            "cash": cash,
            "market_value": market_value,
            "accrued_carry": accrued_carry,
            "accrued_exit_cost": accrued_exit_cost,
            "accrued_event_fees": accrued_event_fees,
            "equity": equity,
            "daily_return": daily_return,
            "open_count": len(positions),
            "entry_cash_outflow": entry_cash_outflow,
            "exit_net_cash_inflow": exit_net_cash_inflow,
            "cash_transition_error": cash - expected_cash,
            "reserved_liability_cash": sum(
                float(position.get("cash_liability_reserve") or 0.0)
                for position in positions.values()
            ),
            "open_entry_notional": sum(
                float(position["entry_notional"]) for position in positions.values()
            ),
            "exact_mark_count": exact_mark_count,
            "stale_mark_count": stale_mark_count,
            # Readable aliases used by other sleeve summaries.
            "cash_usd": cash,
            "market_value_usd": market_value,
            "accrued_carry_usd": accrued_carry,
            "equity_usd": equity,
        }
        if stale_mark_count:
            measurement_failures.append(
                {
                    "date": day,
                    "reason": "stale_open_position_mark_disclosed",
                    "stale_mark_count": stale_mark_count,
                    "binding_measurement_eligible": False,
                }
            )
        daily_ledger.append(row)
        previous_equity = equity

    final_day = sessions[-1] if sessions else end
    right_censored = (
        [_right_censored_trade(position, final_day) for position in positions.values()]
        if right_censor_at_end
        else []
    )
    right_censored.sort(key=lambda row: str(row.get("candidate_id") or ""))
    for row in right_censored:
        if row.get("mark_is_exact_window_close") is False:
            measurement_failures.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "accession_number": row.get("accession_number"),
                    "ticker": row.get("ticker"),
                    "date": final_day,
                    "reason": "missing_exact_window_end_close_stale_mtm_disclosed",
                    "valuation_price_date": row.get("valuation_price_date"),
                }
            )
    trades = closed_trades + right_censored
    trades.sort(
        key=lambda row: (
            str(row.get("entry_date") or ""),
            str(row.get("accession_number") or ""),
        )
    )
    metrics = compute_sec_cash_tender_spread_metrics(
        daily_ledger,
        trades,
        signals_generated=len(candidates),
        signals_survived=entries_funded,
        candidate_rejections=candidate_rejections,
    )
    metrics["measurement_valid"] = not measurement_failures
    metrics["measurement_failure_count"] = len(measurement_failures)
    rejection_counts = Counter(
        reason
        for row in candidate_rejections
        for reason in row.get("rejection_reasons") or []
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "start": start,
        "end": end,
        "session_count": len(sessions),
        "event_fee_usd": event_fee_usd,
        "signals_generated": len(candidates),
        "signals_survived": entries_funded,
        "entered_trade_count": entries_funded,
        "actual_closed_trade_count": len(closed_trades),
        "right_censored_position_count": len(right_censored),
        "entered_episodes": [
            dict(row) for row in events if row.get("event") == "entered"
        ],
        "candidate_evaluations": [
            {key: value for key, value in row.items() if key not in {"ohlcv", "outcome", "amendments"}}
            for row in candidates
        ],
        "candidate_rejections": candidate_rejections,
        "candidate_rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "events": events,
        "trades": trades,
        "actual_closed_trades": closed_trades,
        "right_censored_trades": right_censored,
        "open_positions": [
            {key: value for key, value in row.items() if key != "ohlcv"}
            for row in sorted(positions.values(), key=lambda item: str(item["candidate_id"]))
        ],
        "daily_ledger": daily_ledger,
        "daily_equity": daily_ledger,
        "daily_returns": [
            {"as_of": row["as_of"], "equity": row["equity"], "daily_return": row["daily_return"]}
            for row in daily_ledger
        ],
        "measurement_failures": measurement_failures,
        "metrics": metrics,
        "binding_metrics": metrics if not measurement_failures else None,
        "binding_measurement_status": (
            "valid" if not measurement_failures else "fail_closed"
        ),
        "summary": metrics,
        "concentration": metrics["concentration"],
        "execution_sizing_contract": execution_sizing_contract(),
        "trade_enabled": False,
        "orders": [],
        "production_impact": production_impact(),
    }


def _validate_fee(event_fee_usd: Any) -> float:
    fee = _finite(event_fee_usd)
    if fee is None or fee not in EVENT_FEE_SENSITIVITIES_USD:
        raise ValueError("event_fee_usd must be one of 0, 20, or 40")
    return float(fee)


def _derive_window(
    episodes: Sequence[Mapping[str, Any]],
    ohlcv_by_episode: Any,
    start: Any,
    end: Any,
) -> tuple[str, str]:
    start_day = _date10(start)
    end_day = _date10(end)
    filing_days = [
        day
        for episode in episodes
        if isinstance(episode, Mapping)
        and (day := _date10(episode.get("filing_date"))) is not None
    ]
    price_days: list[str] = []
    for episode in episodes:
        if not isinstance(episode, Mapping):
            continue
        fields = _episode_fields(episode)
        bars, _ = _normalise_ohlcv(
            _resolve_price_payload(episode, fields, ohlcv_by_episode)
        )
        price_days.extend(bars)
    start_day = start_day or (min(filing_days) if filing_days else None) or (
        min(price_days) if price_days else None
    )
    end_day = end_day or (max(price_days) if price_days else None) or (
        max(filing_days) if filing_days else None
    )
    if not start_day or not end_day or start_day > end_day:
        raise ValueError(f"invalid or underivable replay window: {start!r}..{end!r}")
    return start_day, end_day


def _episode_visible_as_of(
    episode: Mapping[str, Any], as_of: str
) -> dict[str, Any]:
    """Remove amendment/outcome knowledge that was not public by ``as_of``."""

    visible = dict(episode)
    amendments = [
        dict(row)
        for row in episode.get("amendments") or []
        if isinstance(row, Mapping)
        and (_amendment_date(row) or "9999-12-31") <= as_of
    ]
    visible["amendments"] = amendments
    original_outcome = _mapping(episode.get("outcome"))
    original_date = _date10(
        _first_value(
            original_outcome.get("date"),
            original_outcome.get("public_date"),
            original_outcome.get("outcome_date"),
            original_outcome.get("amendment_filing_date"),
        )
    )
    if original_date and original_date <= as_of:
        visible["outcome"] = dict(original_outcome)
        return visible

    terminal_statuses = (
        _COMPLETED
        | _TERMINATED_NEGATIVE
        | _TERMINATED_HIGHER_BID
        | _HIGHER_BID_PUBLIC
    )
    visible_outcomes: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for amendment in amendments:
        amendment_outcome = _mapping(amendment.get("outcome"))
        status = _normalise_status(
            _first_value(
                amendment_outcome.get("status"),
                amendment_outcome.get("outcome_type"),
                amendment.get("status"),
                amendment.get("outcome_type"),
            )
        )
        public_date = _amendment_date(amendment)
        if public_date and status in terminal_statuses:
            visible_outcomes.append((public_date, amendment_outcome, amendment))
    if visible_outcomes:
        public_date, amendment_outcome, amendment = sorted(
            visible_outcomes,
            key=lambda item: (
                item[0],
                str(item[2].get("accepted_at") or ""),
                str(item[2].get("accession_number") or ""),
            ),
        )[-1]
        rebuilt = dict(amendment_outcome)
        rebuilt["outcome_date"] = public_date
        rebuilt["amendment_filing_date"] = public_date
        rebuilt.setdefault("amendment_accession_number", amendment.get("accession_number"))
        visible["outcome"] = rebuilt
    else:
        visible["outcome"] = {
            "outcome_type": "pending",
            "outcome_date": None,
            "cash_price_usd": None,
            "evidence_spans": [],
        }
    return visible


def _prices_visible_as_of(
    episodes: Sequence[Mapping[str, Any]],
    ohlcv_by_episode: Any,
    as_of: str,
) -> dict[str, Any]:
    """Canonicalize and trim each episode's prices to its daily PIT boundary."""

    result: dict[str, Any] = {}
    for episode in episodes:
        fields = _episode_fields(episode)
        payload = _resolve_price_payload(episode, fields, ohlcv_by_episode)
        trimmed_rows = _raw_ohlcv_rows_through(payload, as_of)
        bars, errors = _normalise_ohlcv(trimmed_rows)
        canonical_rows: list[dict[str, Any]] = [
            {"date": day, **dict(row)} for day, row in bars.items()
        ]
        if errors:
            # Preserve the fail-closed fact across the canonicalization pass;
            # _prepare_candidate will reject this deliberately incomplete row.
            canonical_rows.append(
                {"date": as_of, "ohlcv_normalization_errors": errors}
            )
        result[str(fields["accession_number"])] = {"rows": canonical_rows}
    return result


def _pending_entry_snapshot_row(
    episode: Mapping[str, Any],
    *,
    calendar_sessions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    fields = _episode_fields(episode)
    filing_date = fields.get("filing_date")
    reasons: list[str] = []
    checks = (
        (bool(fields["accession_number"]), "missing_accession_number"),
        (bool(fields["target_cik"]), "missing_target_cik"),
        (bool(fields["ticker"]), "missing_ticker"),
        (bool(fields["exchange"]), "missing_exchange"),
        (bool(filing_date), "missing_or_invalid_filing_date"),
        (bool(fields["accepted_at"]), "missing_accepted_at"),
        (bool(fields["announcement_date"]), "missing_announcement_or_agreement_date"),
        (
            fields["offer_price"] is not None
            and float(fields["offer_price"] or 0.0) > 0,
            "missing_or_invalid_offer_price",
        ),
        (bool(fields["expiration_date"]), "missing_or_invalid_expiration_date"),
        (fields["policy_eligible"] is True, "policy_ineligible_or_unverified"),
        (bool(fields["outcome"]), "missing_outcome"),
        (
            isinstance(fields["amendments"], Sequence)
            and not isinstance(fields["amendments"], (str, bytes, bytearray)),
            "missing_or_invalid_amendments",
        ),
    )
    reasons.extend(reason for passed, reason in checks if not passed)
    return {
        "candidate_id": f"{RULE_VERSION}:{fields['accession_number'] or 'missing'}",
        "accession_number": fields["accession_number"],
        "target_cik": fields["target_cik"],
        "ticker": fields["ticker"],
        "exchange": fields["exchange"],
        "filing_date": filing_date,
        "accepted_at": fields["accepted_at"],
        "entry_date": (
            _next_session_after(
                str(filing_date), calendar_sessions=calendar_sessions
            )
            if filing_date
            else None
        ),
        "entry_price": None,
        "target_price": fields["offer_price"],
        "target_price_role": "contract_cash_offer_price",
        "status": "pending_next_session_open" if not reasons else "rejected",
        "eligible": not reasons,
        "rejection_reasons": reasons,
        "primary_rejection_reason": reasons[0] if reasons else None,
        "sec_provenance": fields["sec_provenance"],
        "trade_enabled": False,
    }


def replay_sec_cash_tender_spread_sleeve(
    episodes: Sequence[Mapping[str, Any]],
    ohlcv_by_episode: Any,
    start: Any = None,
    end: Any = None,
    *,
    event_fee_usd: float = DEFAULT_EVENT_FEE_USD,
    calendar_sessions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Replay the fixed funded cash-tender policy without any network calls."""

    if not isinstance(episodes, Sequence) or isinstance(episodes, (str, bytes, bytearray)):
        raise TypeError("episodes must be a sequence of normalized mappings")
    fee = _validate_fee(event_fee_usd)
    start_day, end_day = _derive_window(episodes, ohlcv_by_episode, start, end)
    result = _run_replay_core(
        episodes,
        ohlcv_by_episode,
        start=start_day,
        end=end_day,
        event_fee_usd=fee,
        calendar_sessions=calendar_sessions,
        right_censor_at_end=True,
    )
    sensitivity: dict[str, Any] = {}
    for sensitivity_fee in EVENT_FEE_SENSITIVITIES_USD:
        if sensitivity_fee == fee:
            sensitivity_result = result
        else:
            sensitivity_result = _run_replay_core(
                episodes,
                ohlcv_by_episode,
                start=start_day,
                end=end_day,
                event_fee_usd=sensitivity_fee,
                calendar_sessions=calendar_sessions,
                right_censor_at_end=True,
            )
        metrics = sensitivity_result["metrics"]
        sensitivity_failures = sensitivity_result.get("measurement_failures") or []
        sensitivity[str(int(sensitivity_fee))] = {
            key: metrics.get(key)
            for key in (
                "trade_count",
                "entered_trade_count",
                "actual_closed_trade_count",
                "right_censored_trade_count",
                "total_pnl",
                "strategy_total_return_pct",
                "sharpe_daily",
                "expected_value_score",
                "max_drawdown_pct",
            )
        }
        sensitivity[str(int(sensitivity_fee))].update(
            {
                "measurement_valid": bool(metrics.get("measurement_valid")),
                "measurement_failure_count": len(sensitivity_failures),
                "measurement_failure_reasons": sorted(
                    {
                        str(row.get("reason") or "unknown")
                        for row in sensitivity_failures
                        if isinstance(row, Mapping)
                    }
                ),
                "binding_policy_fee": sensitivity_fee == fee,
            }
        )
    result["event_fee_sensitivity"] = sensitivity
    return result


def build_sec_cash_tender_spread_paper_snapshot(
    as_of: Any,
    episodes: Sequence[Mapping[str, Any]],
    ohlcv_by_episode: Any,
    *,
    start: Any = None,
    event_fee_usd: float = DEFAULT_EVENT_FEE_USD,
    calendar_sessions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build the daily view through ``as_of`` using the replay state machine."""

    as_of_day = _date10(as_of)
    if not as_of_day:
        raise ValueError(f"invalid as_of: {as_of!r}")
    visible_episodes = [
        _episode_visible_as_of(episode, as_of_day)
        for episode in episodes
        if isinstance(episode, Mapping)
        and (
            _date10(episode.get("filing_date")) is None
            or str(_date10(episode.get("filing_date"))) <= as_of_day
        )
    ]
    pending_episodes = [
        episode
        for episode in visible_episodes
        if (filing := _date10(episode.get("filing_date"))) is not None
        and _next_session_after(
            filing, calendar_sessions=calendar_sessions
        )
        > as_of_day
    ]
    mature_episodes = [episode for episode in visible_episodes if episode not in pending_episodes]
    visible_prices = _prices_visible_as_of(visible_episodes, ohlcv_by_episode, as_of_day)
    fee = _validate_fee(event_fee_usd)
    if mature_episodes:
        start_day, _ = _derive_window(mature_episodes, visible_prices, start, as_of_day)
        replay = _run_replay_core(
            mature_episodes,
            visible_prices,
            start=start_day,
            end=as_of_day,
            event_fee_usd=fee,
            calendar_sessions=calendar_sessions,
            right_censor_at_end=False,
        )
    else:
        start_day = _date10(start) or as_of_day
        sessions = _regular_sessions(start_day, as_of_day)
        ledger: list[dict[str, Any]] = []
        previous = SLEEVE_CAPITAL_USD
        for day in sessions:
            row = {
                "date": day,
                "as_of": day,
                "cash": SLEEVE_CAPITAL_USD,
                "market_value": 0.0,
                "accrued_carry": 0.0,
                "accrued_exit_cost": 0.0,
                "accrued_event_fees": 0.0,
                "equity": SLEEVE_CAPITAL_USD,
                "daily_return": SLEEVE_CAPITAL_USD / previous - 1.0,
                "open_count": 0,
                "open_entry_notional": 0.0,
                "exact_mark_count": 0,
                "stale_mark_count": 0,
            }
            ledger.append(row)
            previous = SLEEVE_CAPITAL_USD
        replay = {
            "signals_generated": 0,
            "signals_survived": 0,
            "candidate_evaluations": [],
            "candidate_rejections": [],
            "events": [],
            "trades": [],
            "open_positions": [],
            "daily_ledger": ledger,
            "metrics": compute_sec_cash_tender_spread_metrics(ledger, []),
            "measurement_failures": [],
        }
    pending_rows = [
        _pending_entry_snapshot_row(
            episode, calendar_sessions=calendar_sessions
        )
        for episode in pending_episodes
    ]
    replay["candidate_evaluations"] = list(replay["candidate_evaluations"]) + pending_rows
    pending_rejections = [
        {
            "candidate_id": row["candidate_id"],
            "accession_number": row["accession_number"],
            "ticker": row["ticker"],
            "status": "rejected_before_pending_entry",
            "rejection_reasons": list(row["rejection_reasons"]),
            "primary_rejection_reason": row["primary_rejection_reason"],
            "trade_enabled": False,
        }
        for row in pending_rows
        if not row["eligible"]
    ]
    replay["candidate_rejections"] = list(replay["candidate_rejections"]) + pending_rejections
    replay["signals_generated"] = int(replay.get("signals_generated") or 0) + len(
        pending_rows
    )
    replay["metrics"]["signals_generated"] = replay["signals_generated"]
    replay["metrics"]["survival_rate"] = (
        int(replay.get("signals_survived") or 0) / replay["signals_generated"]
        if replay["signals_generated"]
        else None
    )
    replay["metrics"]["candidate_rejection_count"] = len(
        replay["candidate_rejections"]
    )
    latest = replay["daily_ledger"][-1] if replay["daily_ledger"] else {
        "as_of": as_of_day,
        "cash": SLEEVE_CAPITAL_USD,
        "market_value": 0.0,
        "accrued_carry": 0.0,
        "equity": SLEEVE_CAPITAL_USD,
        "daily_return": 0.0,
        "open_count": 0,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "as_of": as_of_day,
        "status": (
            "fail_closed" if replay["measurement_failures"] else "ready"
        ),
        "reason": (
            "measurement_failure"
            if replay["measurement_failures"]
            else None
        ),
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "orders": [],
        "llm": {"used": False, "authority": "none"},
        "llm_authority": "none",
        "signals_generated": replay.get("signals_generated", 0),
        "signals_survived": replay.get("signals_survived", 0),
        "entered_trade_count": replay.get("signals_survived", 0),
        "actual_closed_trade_count": sum(
            bool(row.get("actual_close")) for row in replay.get("trades") or []
        ),
        "latest_ledger": latest,
        "daily_ledger": replay["daily_ledger"],
        "candidate_evaluations": replay["candidate_evaluations"],
        "candidate_rejections": replay["candidate_rejections"],
        "events": replay["events"],
        "trades": replay["trades"],
        "open_positions": replay["open_positions"],
        "measurement_failures": replay["measurement_failures"],
        "metrics": replay["metrics"],
        "execution_sizing_contract": execution_sizing_contract(),
        "production_impact": production_impact(),
        "next_action": "paper_observe_only_no_orders",
    }


__all__ = [
    "ADV_LOOKBACK_SESSIONS",
    "BREAK_LOOKBACK_SESSIONS",
    "CARRY_ANNUAL_RATE",
    "DEFAULT_EVENT_FEE_USD",
    "EVENT_FEE_SENSITIVITIES_USD",
    "HALF_TRADE_COST_RATE",
    "MAX_ADV_FRACTION",
    "MAX_CONCURRENT_NOTIONAL_USD",
    "MAX_DEAL_NOTIONAL_USD",
    "MAX_PREDICTED_BREAK_LOSS_USD",
    "MIN_IMPLIED_COMPLETION_PROBABILITY",
    "ROUND_TRIP_COST_RATE",
    "RULE_VERSION",
    "SCHEMA_VERSION",
    "SLEEVE_CAPITAL_USD",
    "TIMEOUT_CALENDAR_DAYS",
    "TOTAL_ACCOUNT_CAPITAL_USD",
    "build_sec_cash_tender_spread_paper_snapshot",
    "compute_sec_cash_tender_spread_metrics",
    "execution_sizing_contract",
    "production_impact",
    "replay_sec_cash_tender_spread_sleeve",
    "summarize_sec_cash_tender_spread_replay",
]
