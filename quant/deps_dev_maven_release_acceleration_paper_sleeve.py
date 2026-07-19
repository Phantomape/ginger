"""Shared default-off deps.dev Maven release-acceleration paper policy.

The source contract is deliberately outcome-blind.  It accepts only exact,
effective-dated first-party Maven coordinates and immutable publication
timestamps, collapses exact duplicates, and fails closed when one package
version is assigned conflicting publication times.  Historical replay and the
daily paper snapshot call the same completed-week selector.

This module never fetches data and never creates orders.  The fixed notional is
an evidence unit only; ``trade_enabled`` remains false everywhere.
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
from statistics import median
from typing import Any

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


SLEEVE_NAME = "DEPS_DEV_MAVEN_RELEASE_ACCELERATION_PAPER"
RULE_VERSION = "deps_dev_maven_release_acceleration_top3_nextopen_h10_shared_v1"
SOURCE_RULE_VERSION = "deps_dev_exact_coordinate_complete_week_prior8_median_v1"
STATE_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = "deps_dev_maven_release_default_off_snapshot_v1"

PAPER_NOTIONAL_USD = 4_000.0
HOLD_SESSIONS = 10
MAX_WEEKLY_CANDIDATES = 3
MAX_ACTIVE_POSITIONS = 6
MIN_CURRENT_RELEASE_COUNT = 2
PRIOR_COMPLETE_WEEKS = 8
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5
TRADE_ENABLED = False

PACKAGE_MAP_EFFECTIVE_FROM = "2024-01-01"
PACKAGE_EFFECTIVE_FROM_OVERRIDES: dict[str, str] = {
    # Cisco completed its Splunk acquisition on 2024-03-18; publications from
    # this namespace must not be back-attributed to CSCO before closing.
    "com.splunk:opentelemetry-javaagent": "2024-03-18",
}

# Frozen before the outcome replay.  Coordinates are exact and case-sensitive;
# no group-prefix, artifact-prefix, or fuzzy ownership attribution is allowed.
ISSUER_PACKAGE_COORDINATES: dict[str, tuple[str, ...]] = {
    "AMZN": (
        "software.amazon.awssdk:bom",
        "com.amazonaws:aws-java-sdk-bom",
    ),
    "MSFT": (
        "com.azure:azure-sdk-bom",
        "com.microsoft.azure:azure-sdk-bom",
    ),
    "GOOGL": (
        "com.google.cloud:libraries-bom",
        "com.google.api-client:google-api-client",
    ),
    "ORCL": ("com.oracle.oci.sdk:oci-java-sdk-bom",),
    "IBM": ("com.ibm.cloud:sdk-core", "io.quarkus.platform:quarkus-bom"),
    "SAP": ("com.sap.cloud.sdk:sdk-bom",),
    "DDOG": (
        "com.datadoghq:dd-trace-api",
        "com.datadoghq:java-dogstatsd-client",
    ),
    "MDB": ("org.mongodb:mongodb-driver-bom",),
    "SNOW": ("net.snowflake:snowflake-jdbc",),
    "TWLO": ("com.twilio.sdk:twilio",),
    "OKTA": ("com.okta.sdk:okta-sdk-bom",),
    "AKAM": ("com.akamai.edgegrid:edgegrid-signer-core",),
    "CFLT": ("io.confluent:kafka-schema-registry-client",),
    "DT": ("com.dynatrace.openkit:openkit",),
    "ADBE": ("com.adobe.aem:aem-sdk-api",),
    "TEAM": ("com.atlassian.jira:jira-rest-java-client-core",),
    "META": ("com.facebook.react:react-android",),
    "NFLX": ("com.netflix.graphql.dgs:graphql-dgs-platform-dependencies",),
    "PLTR": ("com.palantir.conjure.java:conjure-lib",),
    "SHOP": ("com.shopify.mobilebuysdk:buy3",),
    "UBER": ("com.uber.motif:motif",),
    "BABA": ("com.alibaba.cloud:spring-cloud-alibaba-dependencies",),
    "CSCO": ("com.splunk:opentelemetry-javaagent",),
    "ESTC": ("co.elastic.clients:elasticsearch-java",),
}

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "deps_dev_maven_release_acceleration" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "deps_dev_maven_release_acceleration"
    / "snapshots.jsonl"
)


class DepsDevMavenReleaseContractError(ValueError):
    """Raised when a supposedly immutable source or market identity conflicts."""


def _coordinate_map() -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for ticker, coordinates in ISSUER_PACKAGE_COORDINATES.items():
        for coordinate in coordinates:
            if coordinate in output:
                raise RuntimeError(f"ambiguous Maven coordinate: {coordinate}")
            output[coordinate] = {
                "ticker": ticker,
                "effective_from": PACKAGE_EFFECTIVE_FROM_OVERRIDES.get(
                    coordinate,
                    PACKAGE_MAP_EFFECTIVE_FROM,
                ),
            }
    return output


COORDINATE_TO_ISSUER = _coordinate_map()
if len(COORDINATE_TO_ISSUER) != 29:
    raise RuntimeError("frozen deps.dev Maven coordinate map must remain 29 anchors")


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
        raise DepsDevMavenReleaseContractError(f"invalid date: {value!r}") from error


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    else:
        text = str(value or "").strip()
        if not text:
            raise DepsDevMavenReleaseContractError("publishedAt missing")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as error:
            raise DepsDevMavenReleaseContractError(
                f"invalid publishedAt: {value!r}"
            ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _week_bounds(day: date) -> tuple[date, date]:
    week_start = day - timedelta(days=day.weekday())
    return week_start, week_start + timedelta(days=6)


def _row_coordinate(raw: Mapping[str, Any]) -> str:
    coordinate = raw.get("package_coordinate") or raw.get("coordinate")
    if coordinate is None:
        package = raw.get("package")
        if isinstance(package, Mapping):
            coordinate = package.get("name") or package.get("coordinate")
        else:
            coordinate = package
    text = str(coordinate or "").strip()
    if text.upper().startswith("MAVEN:"):
        text = text[6:]
    return text


def normalise_deps_dev_maven_release_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Exact-map and canonicalise deps.dev package-version publications.

    Exact duplicate ``(package, version, publishedAt)`` rows collapse.  The
    immutable natural key ``(package, version)`` may have only one publication
    timestamp; a disagreement fails closed instead of silently choosing a
    convenient vintage.
    """

    by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    version_times: dict[tuple[str, str], str] = {}
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        coordinate = _row_coordinate(raw)
        mapping = COORDINATE_TO_ISSUER.get(coordinate)
        if mapping is None:
            continue
        version = str(raw.get("version") or raw.get("version_name") or "").strip()
        if not version or "SNAPSHOT" in version.upper():
            continue
        timestamp_raw = (
            raw.get("publishedAt")
            if raw.get("publishedAt") is not None
            else raw.get("published_at") or raw.get("published")
        )
        try:
            published_at = _utc_datetime(timestamp_raw)
        except DepsDevMavenReleaseContractError:
            continue
        published_date = published_at.date().isoformat()
        if published_date < mapping["effective_from"]:
            continue
        canonical_timestamp = published_at.isoformat().replace("+00:00", "Z")
        natural_key = (coordinate, version)
        prior_timestamp = version_times.get(natural_key)
        if prior_timestamp is not None and prior_timestamp != canonical_timestamp:
            raise DepsDevMavenReleaseContractError(
                "conflicting publication timestamp for "
                f"{coordinate}:{version}: {prior_timestamp} != {canonical_timestamp}"
            )
        version_times[natural_key] = canonical_timestamp
        identity = (coordinate, version, canonical_timestamp)
        week_start, week_end = _week_bounds(published_at.date())
        canonical = {
            "package_coordinate": coordinate,
            "version": version,
            "published_at": canonical_timestamp,
            "published_date": published_date,
            "ticker": mapping["ticker"],
            "mapping_effective_from": mapping["effective_from"],
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "source_rule_version": SOURCE_RULE_VERSION,
        }
        canonical["source_record_sha256"] = _payload_sha256(canonical)
        by_identity.setdefault(identity, canonical)
    return sorted(
        by_identity.values(),
        key=lambda row: (
            row["published_at"],
            row["package_coordinate"],
            row["version"],
        ),
    )


def evaluate_deps_dev_maven_release_acceleration_weekly_decisions(
    release_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    archive_start: Any | None = None,
) -> dict[str, Any]:
    """Rank eligible issuer release bursts from completed Monday-Sunday weeks."""

    canonical = normalise_deps_dev_maven_release_rows(release_rows)
    as_of_date = date.fromisoformat(_date10(as_of))
    start_date = date.fromisoformat(_date10(start)) if start is not None else None
    end_date = date.fromisoformat(_date10(end)) if end is not None else None
    coverage_start = date.fromisoformat(
        _date10(archive_start or PACKAGE_MAP_EFFECTIVE_FROM)
    )
    coverage_week_start, _ = _week_bounds(coverage_start)

    counts: Counter[tuple[str, str]] = Counter()
    release_ids: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for row in canonical:
        key = (str(row["ticker"]), str(row["week_start"]))
        counts[key] += 1
        release_ids[key].append(
            f"{row['package_coordinate']}:{row['version']}@{row['published_at']}"
        )

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
        prior_median = float(median(prior_counts))
        acceleration = float(current_count) - prior_median
        if current_count < MIN_CURRENT_RELEASE_COUNT or acceleration <= 0.0:
            continue
        eligible_by_week[week_end_date.isoformat()].append(
            {
                "ticker": ticker,
                "week_start": week_start_date.isoformat(),
                "week_end": week_end_date.isoformat(),
                "signal_date": week_end_date.isoformat(),
                "current_release_count": int(current_count),
                "prior_eight_week_counts": [int(value) for value in prior_counts],
                "prior_eight_week_median": round(prior_median, 8),
                "release_acceleration": round(acceleration, 8),
                "release_ids": sorted(release_ids[(ticker, week_start_text)]),
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
                -float(row["release_acceleration"]),
                -int(row["current_release_count"]),
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


def select_deps_dev_maven_release_acceleration_weekly_decisions(
    release_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    archive_start: Any | None = None,
) -> list[dict[str, Any]]:
    return evaluate_deps_dev_maven_release_acceleration_weekly_decisions(
        release_rows,
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
        except DepsDevMavenReleaseContractError:
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
            raise DepsDevMavenReleaseContractError(f"conflicting OHLCV date: {day}")
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
            raise DepsDevMavenReleaseContractError(
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
    index_by_date = {str(row["date"]): index for index, row in enumerate(rows)}
    true_ranges: list[float] = []
    for row in sample:
        index = index_by_date[str(row["date"])]
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


def build_deps_dev_maven_release_acceleration_historical_trades(
    *,
    release_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: Any,
    end: Any,
    as_of: Any | None = None,
    trading_dates: Iterable[Any] | None = None,
    archive_start: Any | None = None,
) -> dict[str, Any]:
    """Replay the locked weekly candidate pool with next-open fills and costs."""

    start_iso = _date10(start)
    end_iso = _date10(end)
    as_of_iso = _date10(as_of or end_iso)
    if start_iso > end_iso:
        raise DepsDevMavenReleaseContractError("start is after end")
    canonical_releases = normalise_deps_dev_maven_release_rows(release_rows)
    weekly_evaluation = (
        evaluate_deps_dev_maven_release_acceleration_weekly_decisions(
            canonical_releases,
            as_of=as_of_iso,
            archive_start=archive_start,
        )
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
            "target_price_role": "3.5x_atr14_signal_contract_sentinel_not_exit_driver",
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
        "schema": "deps_dev_maven_release_acceleration_historical_replay_v1",
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
        "normalised_release_count": len(canonical_releases),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "production_impact": _production_impact(),
    }


def empty_deps_dev_maven_release_acceleration_state() -> dict[str, Any]:
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


def load_deps_dev_maven_release_acceleration_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_deps_dev_maven_release_acceleration_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_deps_dev_maven_release_acceleration_state()
    if isinstance(payload, Mapping):
        state.update(payload)
    return state


def save_deps_dev_maven_release_acceleration_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def append_deps_dev_maven_release_acceleration_snapshot(
    snapshot: Mapping[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")


def build_deps_dev_maven_release_acceleration_snapshot(
    *,
    release_rows: Iterable[Mapping[str, Any]],
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
    start_iso = _date10(start or archive_start or PACKAGE_MAP_EFFECTIVE_FROM)
    bounded_releases = [
        row
        for row in release_rows
        if _date10(
            row.get("publishedAt")
            or row.get("published_at")
            or row.get("published")
        )
        <= as_of_iso
    ]
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
    replay = build_deps_dev_maven_release_acceleration_historical_trades(
        release_rows=bounded_releases,
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
            load_deps_dev_maven_release_acceleration_state(state_path)
            if persist
            else empty_deps_dev_maven_release_acceleration_state()
        )
    )
    closed_by_id = {
        str(row.get("decision_id")): row
        for row in working_state.get("closed_positions") or []
        if row.get("decision_id")
    }
    closed_by_id.update({str(row["decision_id"]): row for row in replay["trades"]})
    open_positions = [
        row
        for row in replay["trade_candidates"]
        if row["decision_id"] not in closed_by_id
        and row.get("entry_date") <= as_of_iso
    ]
    processed = sorted(
        {
            *working_state.get("processed_decision_ids", []),
            *(row["decision_id"] for row in replay["trade_candidates"]),
        }
    )
    working_state.update(
        {
            "updated_at": _utc_now_iso(),
            "pending_entries": [],
            "open_positions": open_positions,
            "closed_positions": sorted(
                closed_by_id.values(),
                key=lambda row: (row.get("exit_date") or "", row["decision_id"]),
            ),
            "processed_decision_ids": processed,
        }
    )
    snapshot = {
        "schema": SNAPSHOT_SCHEMA_VERSION,
        "as_of": as_of_iso,
        "generated_at": _utc_now_iso(),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "execution_envelope": {
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "max_concurrent_positions": MAX_ACTIVE_POSITIONS,
            "one_active_position_per_ticker": True,
            "hold_sessions": HOLD_SESSIONS,
            "entry_order_semantics": "next_regular_session_market_open_paper_only",
            "exit_order_semantics": "tenth_session_close_paper_only",
            "kill_switch": "trade_enabled_false",
            "failure_handling": "missing_exact_bar_or_atr_fails_closed",
        },
        "source_contract": {
            "default_mapping_effective_from": PACKAGE_MAP_EFFECTIVE_FROM,
            "mapping_effective_from_overrides": dict(
                sorted(PACKAGE_EFFECTIVE_FROM_OVERRIDES.items())
            ),
            "frozen_coordinate_count": len(COORDINATE_TO_ISSUER),
            "snapshot_versions_excluded": True,
            "completed_week_only": True,
            "prior_completed_weeks": PRIOR_COMPLETE_WEEKS,
        },
        "replay": replay,
        "state": working_state,
        "production_impact": _production_impact(),
    }
    snapshot["snapshot_sha256"] = _payload_sha256(
        {key: value for key, value in snapshot.items() if key != "generated_at"}
    )
    if persist:
        save_deps_dev_maven_release_acceleration_state(working_state, state_path)
        append_deps_dev_maven_release_acceleration_snapshot(
            snapshot, snapshot_log_path
        )
    return snapshot


__all__ = [
    "COORDINATE_TO_ISSUER",
    "DEFAULT_SNAPSHOT_LOG_PATH",
    "DEFAULT_STATE_PATH",
    "HOLD_SESSIONS",
    "ISSUER_PACKAGE_COORDINATES",
    "MAX_ACTIVE_POSITIONS",
    "MAX_WEEKLY_CANDIDATES",
    "PACKAGE_MAP_EFFECTIVE_FROM",
    "PACKAGE_EFFECTIVE_FROM_OVERRIDES",
    "PAPER_NOTIONAL_USD",
    "PRIOR_COMPLETE_WEEKS",
    "RULE_VERSION",
    "SNAPSHOT_SCHEMA_VERSION",
    "SOURCE_RULE_VERSION",
    "TRADE_ENABLED",
    "DepsDevMavenReleaseContractError",
    "append_deps_dev_maven_release_acceleration_snapshot",
    "build_deps_dev_maven_release_acceleration_historical_trades",
    "build_deps_dev_maven_release_acceleration_snapshot",
    "empty_deps_dev_maven_release_acceleration_state",
    "evaluate_deps_dev_maven_release_acceleration_weekly_decisions",
    "load_deps_dev_maven_release_acceleration_state",
    "normalise_deps_dev_maven_release_rows",
    "save_deps_dev_maven_release_acceleration_state",
    "select_deps_dev_maven_release_acceleration_weekly_decisions",
]
