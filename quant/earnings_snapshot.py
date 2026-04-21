import json
import logging
import os
from datetime import datetime


SNAPSHOT_FIELDS = (
    "days_to_earnings",
    "eps_estimate",
    "eps_actual_last",
    "avg_historical_surprise_pct",
    "historical_surprise_pct",
)


def _build_snapshot_payload(earnings_by_ticker, as_of):
    earnings = {
        ticker: {
            key: value
            for key, value in (earnings_data or {}).items()
            if key in SNAPSHOT_FIELDS
        }
        for ticker, earnings_data in (earnings_by_ticker or {}).items()
        if earnings_data is not None
    }

    coverage = {
        "tickers_total": len(earnings_by_ticker or {}),
        "tickers_persisted": len(earnings),
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
        "date": as_of.strftime("%Y%m%d"),
        "timestamp": as_of.isoformat(),
        "coverage": coverage,
        "earnings": earnings,
    }


def _payload_has_required_shape(payload):
    return isinstance(payload, dict) and isinstance(payload.get("earnings"), dict)


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
                coverage = existing.get("coverage") or {}
                logger.info(
                    "Earnings snapshot already exists: %s "
                    "(persisted=%s eps=%s surprise=%s)",
                    snapshot_path,
                    coverage.get("tickers_persisted", "?"),
                    coverage.get("tickers_with_eps_estimate", "?"),
                    coverage.get("tickers_with_surprise_history", "?"),
                )
                return snapshot_path
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
        "Earnings snapshot saved: %s (persisted=%s dte=%s eps=%s surprise=%s)",
        snapshot_path,
        coverage["tickers_persisted"],
        coverage["tickers_with_days_to_earnings"],
        coverage["tickers_with_eps_estimate"],
        coverage["tickers_with_surprise_history"],
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
