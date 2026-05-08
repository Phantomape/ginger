import json
import logging
import os
from datetime import datetime, timedelta


SNAPSHOT_SCHEMA_VERSION = 2
SNAPSHOT_FIELDS = (
    "next_earnings_date",
    "next_earnings_date_source",
    "next_earnings_date_inferred",
    "days_to_earnings",
    "eps_estimate",
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


def _normalize_snapshot_row(earnings_data, as_of):
    row = {
        key: value
        for key, value in (earnings_data or {}).items()
        if key in SNAPSHOT_FIELDS
    }

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


def _build_snapshot_payload(earnings_by_ticker, as_of):
    earnings = {
        ticker: _normalize_snapshot_row(earnings_data, as_of)
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
    existing_next = _count_rows_with_next_earnings_date(existing)
    replacement_next = _count_rows_with_next_earnings_date(replacement)
    return replacement_next > existing_next


def persist_earnings_snapshot(
    earnings_by_ticker,
    as_of=None,
    base_dir=None,
    logger=None,
):
    """Persist a daily earnings snapshot for later backtest replay."""
    if as_of is None:
        as_of = datetime.now()
    if logger is None:
        logger = logging.getLogger(__name__)
    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "data")

    date_str = as_of.strftime("%Y%m%d")
    snapshot_path = os.path.join(base_dir, f"earnings_snapshot_{date_str}.json")
    os.makedirs(os.path.dirname(os.path.abspath(snapshot_path)), exist_ok=True)
    payload = _build_snapshot_payload(earnings_by_ticker, as_of)

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
