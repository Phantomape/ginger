import json
import logging
import os
from datetime import datetime, timedelta, timezone

from data_paths import daily_artifact_path


SNAPSHOT_SCHEMA_VERSION = 3
SNAPSHOT_FIELDS = (
    "next_earnings_date",
    "next_earnings_date_source",
    "next_earnings_date_inferred",
    "days_to_earnings",
    "eps_estimate",
    "eps_estimate_source",
    "eps_estimate_event_date",
    "eps_estimate_fiscal_period",
    "eps_estimate_vendor_asof",
    "observed_at",
    "eps_actual_last",
    "avg_historical_surprise_pct",
    "historical_surprise_pct",
)


def _asof_date(as_of):
    return as_of.date() if hasattr(as_of, "date") else as_of


def _infer_next_earnings_date_from_dte(as_of, days_to_earnings):
    """Infer the event date encoded by an existing PIT days-to-earnings field."""
    if days_to_earnings is None:
        return None
    try:
        dte = int(days_to_earnings)
    except (TypeError, ValueError):
        return None
    if dte < 0:
        return None

    current = _asof_date(as_of)
    if dte == 0:
        return current.isoformat()

    remaining = dte
    probe = current
    guard = 0
    while remaining > 0 and guard < 370:
        probe = probe + timedelta(days=1)
        if probe.weekday() < 5:
            remaining -= 1
        guard += 1

    if remaining == 0:
        return probe.isoformat()
    return None


def _aware_utc_iso(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            text = str(value).strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _normalize_snapshot_row(earnings_data, as_of, *, observed_at=None):
    row = {
        key: value
        for key, value in (earnings_data or {}).items()
        if key in SNAPSHOT_FIELDS
    }

    # Availability is a retrieval fact, not an earnings-calendar fact.  A
    # caller-provided row clock is retained only when it is timezone-aware;
    # persistence/merge callers pass their own conservative retrieval clock.
    row_clock = _aware_utc_iso(observed_at)
    if row_clock is None:
        row_clock = _aware_utc_iso(row.get("observed_at"))
    if row_clock is not None:
        row["observed_at"] = row_clock
    else:
        row.pop("observed_at", None)

    if row.get("next_earnings_date") is not None:
        row["next_earnings_date"] = str(row["next_earnings_date"])
        row.setdefault("next_earnings_date_source", "source")
        row.setdefault("next_earnings_date_inferred", False)
        return row

    inferred = _infer_next_earnings_date_from_dte(as_of, row.get("days_to_earnings"))
    if inferred is not None:
        row["next_earnings_date"] = inferred
        row["next_earnings_date_source"] = "derived_from_days_to_earnings"
        row["next_earnings_date_inferred"] = True

    return row


def _build_snapshot_payload(earnings_by_ticker, as_of, *, observed_at=None):
    earnings = {
        ticker: _normalize_snapshot_row(
            earnings_data,
            as_of,
            observed_at=observed_at,
        )
        for ticker, earnings_data in (earnings_by_ticker or {}).items()
        if earnings_data is not None
    }

    coverage = {
        "tickers_total": len(earnings_by_ticker or {}),
        "tickers_persisted": len(earnings),
        "tickers_with_next_earnings_date": sum(
            1 for data in earnings.values()
            if data.get("next_earnings_date") is not None
        ),
        "tickers_with_inferred_next_earnings_date": sum(
            1 for data in earnings.values()
            if data.get("next_earnings_date_inferred") is True
        ),
        "tickers_with_days_to_earnings": sum(
            1 for data in earnings.values()
            if data.get("days_to_earnings") is not None
        ),
        "tickers_with_eps_estimate": sum(
            1 for data in earnings.values()
            if data.get("eps_estimate") is not None
        ),
        "tickers_with_observed_at": sum(
            1 for data in earnings.values()
            if data.get("observed_at") is not None
        ),
        "tickers_with_eps_actual_last": sum(
            1 for data in earnings.values()
            if data.get("eps_actual_last") is not None
        ),
        "tickers_with_surprise_history": sum(
            1 for data in earnings.values()
            if (
                data.get("avg_historical_surprise_pct") is not None
                or data.get("historical_surprise_pct")
            )
        ),
    }

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "date": as_of.strftime("%Y%m%d"),
        "timestamp": as_of.isoformat(),
        "coverage": coverage,
        "earnings": earnings,
    }


def _payload_has_required_shape(payload):
    return isinstance(payload, dict) and isinstance(payload.get("earnings"), dict)


def _count_rows_with_next_earnings_date(payload):
    earnings = payload.get("earnings") if isinstance(payload, dict) else {}
    if not isinstance(earnings, dict):
        return 0
    return sum(
        1 for data in earnings.values()
        if isinstance(data, dict) and data.get("next_earnings_date") is not None
    )


def _snapshot_should_be_rewritten(existing, replacement):
    if not _payload_has_required_shape(existing):
        return True
    if int(existing.get("schema_version") or 0) < int(
        replacement.get("schema_version") or 0
    ):
        return True
    existing_next = _count_rows_with_next_earnings_date(existing)
    replacement_next = _count_rows_with_next_earnings_date(replacement)
    return replacement_next > existing_next


def merge_earnings_into_snapshot(
    additional_earnings_by_ticker,
    as_of=None,
    base_dir=None,
    logger=None,
    observed_at=None,
):
    """Merge additional tickers into an existing daily earnings snapshot.

    This is additive: only tickers NOT already present in the snapshot are
    inserted.  Existing tickers are never overwritten.  Used by the PEAD broad
    universe daily fetch (exp-20260607-003) to expand coverage from ~44 to ~500
    tickers without touching the core watchlist data.

    Returns the snapshot path, or None if no snapshot exists for this date.
    """
    if as_of is None:
        as_of = datetime.now()
    # The broad fetch may run minutes or hours after the core snapshot.  Stamp
    # every merged row at merge time so it can never inherit/backdate itself to
    # the earlier top-level snapshot timestamp.
    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    if logger is None:
        logger = logging.getLogger(__name__)
    if base_dir is None:
        base_dir = daily_artifact_path("earnings_snapshot", as_of.strftime("%Y%m%d")).parent

    date_str = as_of.strftime("%Y%m%d")
    snapshot_path = os.path.join(base_dir, f"earnings_snapshot_{date_str}.json")

    if not os.path.exists(snapshot_path):
        logger.info(
            "No existing snapshot for %s; creating new snapshot from broad universe data.",
            date_str,
        )
        return persist_earnings_snapshot(
            additional_earnings_by_ticker,
            as_of=as_of,
            base_dir=base_dir,
            logger=logger,
            observed_at=observed_at,
        )

    try:
        with open(snapshot_path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)
    except Exception as exc:
        logger.warning(
            "Failed to read existing snapshot for merge at %s: %s; skipping merge.",
            snapshot_path,
            exc,
        )
        return snapshot_path

    if not _payload_has_required_shape(existing):
        logger.warning(
            "Existing snapshot has invalid shape at %s; skipping merge.",
            snapshot_path,
        )
        return snapshot_path

    existing_earnings = existing.get("earnings") or {}
    new_tickers_added = 0
    for raw_ticker, earnings_data in (additional_earnings_by_ticker or {}).items():
        ticker = str(raw_ticker).upper().strip()
        if not ticker or ticker in existing_earnings:
            continue
        row = _normalize_snapshot_row(
            earnings_data,
            as_of,
            observed_at=observed_at,
        )
        if row is not None:
            existing_earnings[ticker] = row
            new_tickers_added += 1

    if new_tickers_added == 0:
        logger.info(
            "Earnings snapshot merge: no new tickers to add for %s (all %d broad tickers already present).",
            date_str,
            len(additional_earnings_by_ticker or {}),
        )
        return snapshot_path

    existing["earnings"] = existing_earnings
    # Recompute coverage stats
    existing["coverage"] = {
        "tickers_total": len(existing_earnings),
        "tickers_persisted": len(existing_earnings),
        "tickers_with_next_earnings_date": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("next_earnings_date") is not None
        ),
        "tickers_with_inferred_next_earnings_date": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("next_earnings_date_inferred") is True
        ),
        "tickers_with_days_to_earnings": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("days_to_earnings") is not None
        ),
        "tickers_with_eps_estimate": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("eps_estimate") is not None
        ),
        "tickers_with_observed_at": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("observed_at") is not None
        ),
        "tickers_with_eps_actual_last": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and data.get("eps_actual_last") is not None
        ),
        "tickers_with_surprise_history": sum(
            1 for data in existing_earnings.values()
            if isinstance(data, dict) and (
                data.get("avg_historical_surprise_pct") is not None
                or data.get("historical_surprise_pct")
            )
        ),
    }
    existing["broad_universe_expanded"] = True
    existing["broad_universe_ticker_count"] = len(existing_earnings)

    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2, ensure_ascii=False, default=str)

    coverage = existing["coverage"]
    logger.info(
        "Earnings snapshot merged (broad universe +%d): %s "
        "(total=%s next=%s eps=%s surprise=%s)",
        new_tickers_added,
        snapshot_path,
        coverage["tickers_persisted"],
        coverage["tickers_with_next_earnings_date"],
        coverage["tickers_with_eps_estimate"],
        coverage["tickers_with_surprise_history"],
    )
    return snapshot_path


def persist_earnings_snapshot(
    earnings_by_ticker,
    as_of=None,
    base_dir=None,
    logger=None,
    observed_at=None,
):
    """Persist a daily earnings snapshot for later backtest replay."""
    if as_of is None:
        as_of = datetime.now()
    if observed_at is None:
        observed_at = as_of
    if logger is None:
        logger = logging.getLogger(__name__)
    if base_dir is None:
        base_dir = daily_artifact_path("earnings_snapshot", as_of.strftime("%Y%m%d")).parent

    date_str = as_of.strftime("%Y%m%d")
    snapshot_path = os.path.join(base_dir, f"earnings_snapshot_{date_str}.json")
    os.makedirs(os.path.dirname(os.path.abspath(snapshot_path)), exist_ok=True)
    payload = _build_snapshot_payload(
        earnings_by_ticker,
        as_of,
        observed_at=observed_at,
    )

    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
            if _payload_has_required_shape(existing):
                if _snapshot_should_be_rewritten(existing, payload):
                    logger.info(
                        "Earnings snapshot coverage upgrade, rewriting: %s "
                        "(next_earnings_date %s -> %s)",
                        snapshot_path,
                        _count_rows_with_next_earnings_date(existing),
                        _count_rows_with_next_earnings_date(payload),
                    )
                else:
                    coverage = existing.get("coverage") or {}
                    logger.info(
                        "Earnings snapshot already exists: %s "
                        "(persisted=%s next=%s eps=%s surprise=%s)",
                        snapshot_path,
                        coverage.get("tickers_persisted", "?"),
                        coverage.get(
                            "tickers_with_next_earnings_date",
                            _count_rows_with_next_earnings_date(existing),
                        ),
                        coverage.get("tickers_with_eps_estimate", "?"),
                        coverage.get("tickers_with_surprise_history", "?"),
                    )
                    return snapshot_path
            else:
                logger.warning(
                    "Earnings snapshot invalid, rewriting: %s",
                    snapshot_path,
                )
        except Exception as exc:
            logger.warning(
                "Failed to read existing earnings snapshot, rewriting %s: %s",
                snapshot_path,
                exc,
            )

    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)

    coverage = payload["coverage"]
    logger.info(
        "Earnings snapshot saved: %s (persisted=%s next=%s inferred_next=%s dte=%s eps=%s surprise=%s)",
        snapshot_path,
        coverage["tickers_persisted"],
        coverage["tickers_with_next_earnings_date"],
        coverage["tickers_with_inferred_next_earnings_date"],
        coverage["tickers_with_days_to_earnings"],
        coverage["tickers_with_eps_estimate"],
        coverage["tickers_with_surprise_history"],
    )
    if coverage["tickers_with_next_earnings_date"] == 0:
        logger.warning(
            "Earnings snapshot has zero next_earnings_date coverage: %s",
            snapshot_path,
        )
    if coverage["tickers_with_eps_estimate"] == 0:
        logger.warning(
            "Earnings snapshot has zero eps_estimate coverage: %s",
            snapshot_path,
        )
    if coverage["tickers_with_surprise_history"] == 0:
        logger.warning(
            "Earnings snapshot has zero surprise-history coverage: %s",
            snapshot_path,
        )
    return snapshot_path
