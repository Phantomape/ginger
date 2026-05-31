"""
Read-only peer-earnings-reaction attribution sidecar.

For each signal ticker, checks whether any same-sector peer had a large
positive open-gap with volume confirmation in the last N trading days, a
PIT-safe OHLCV-only proxy for "did a sector peer just have a positive
earnings announcement reaction."

Fields added per ticker:
  early_peer_earnings_reaction_bucket_v1:
    "peer_positive_earnings_gap" | "no_peer_earnings_gap"
  peer_earnings_reaction_seen:   bool
  peer_earnings_reaction_details: list (up to 3 items)

These are read-only attribution sidecars. They never change entry, exit,
ranking, sizing, portfolio heat, LLM output, or orders.

exp-20260531-019
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

RULE_VERSION = "early_peer_earnings_reaction_bucket_v1"
LOOKBACK_TRADING_DAYS = 10
MIN_GAP_PCT = 0.03          # open vs prior close gap threshold
MIN_VOLUME_RATIO = 1.5      # volume vs 10-day average (earnings day proxy)
MAX_DETAILS = 3             # cap stored detail records


def build_peer_earnings_reaction_sidecar(
    signals: list[dict[str, Any]],
    ohlcv_dict: dict[str, Any],
    sector_map: dict[str, str],
    *,
    lookback_trading_days: int = LOOKBACK_TRADING_DAYS,
    min_gap_pct: float = MIN_GAP_PCT,
    min_volume_ratio: float = MIN_VOLUME_RATIO,
) -> dict[str, dict[str, Any]]:
    """Return a dict mapping ticker -> peer-earnings-reaction attribution record.

    Parameters
    ----------
    signals:
        List of signal dicts (each must have "ticker" and optionally "sector").
    ohlcv_dict:
        Mapping of ticker -> pandas DataFrame (columns Open/High/Low/Close/Volume,
        DatetimeIndex) as returned by data_layer.get_ohlcv_many().
    sector_map:
        Mapping of ticker -> sector string (e.g. risk_engine.SECTOR_MAP).
    """
    result: dict[str, dict[str, Any]] = {}

    # Pre-compute sector -> peer list once to avoid repeated peer scans.
    sector_to_peers: dict[str, list[str]] = {}
    for t, s in sector_map.items():
        if s not in ("ETF", "Commodities"):  # skip non-equity sectors
            sector_to_peers.setdefault(s, []).append(t)

    for signal in signals:
        ticker = str(signal.get("ticker") or "").upper()
        if not ticker:
            continue
        sector = signal.get("sector") or sector_map.get(ticker, "Unknown")
        peers = [p for p in sector_to_peers.get(sector, []) if p != ticker]

        reactions: list[dict[str, Any]] = []
        for peer in peers:
            if len(reactions) >= MAX_DETAILS * 2:
                break  # enough evidence found
            df = ohlcv_dict.get(peer)
            if df is None or getattr(df, "empty", True) or len(df) < 12:
                continue
            try:
                # Work on the most recent lookback + buffer rows
                tail = df.tail(lookback_trading_days + 2)
                if len(tail) < 2:
                    continue
                # Compute average volume over the tail window (excluding most recent)
                avg_vol = float(tail["Volume"].iloc[:-1].mean())
                if avg_vol <= 0:
                    continue
                # Scan for gap + volume days
                for i in range(1, len(tail)):
                    open_p = float(tail["Open"].iloc[i])
                    prev_c = float(tail["Close"].iloc[i - 1])
                    vol = float(tail["Volume"].iloc[i])
                    if prev_c <= 0:
                        continue
                    gap = (open_p - prev_c) / prev_c
                    vol_ratio = vol / avg_vol if avg_vol > 0 else 0.0
                    if gap >= min_gap_pct and vol_ratio >= min_volume_ratio:
                        date_str = str(tail.index[i])[:10]
                        reactions.append({
                            "peer_ticker": peer,
                            "date": date_str,
                            "gap_pct": round(gap, 4),
                            "volume_ratio": round(vol_ratio, 2),
                        })
            except Exception as exc:
                log.debug("peer_earnings_reaction: %s / peer %s error: %s", ticker, peer, exc)

        seen = bool(reactions)
        result[ticker] = {
            "rule_version": RULE_VERSION,
            "early_peer_earnings_reaction_bucket_v1": (
                "peer_positive_earnings_gap" if seen else "no_peer_earnings_gap"
            ),
            "peer_earnings_reaction_seen": seen,
            "peer_earnings_reaction_details": reactions[:MAX_DETAILS],
            "peer_count_checked": len(peers),
            "sector": sector,
            "lookback_trading_days": lookback_trading_days,
            "min_gap_pct": min_gap_pct,
            "min_volume_ratio": min_volume_ratio,
            "read_only": True,
            "alters_orders": False,
            "trade_enabled": False,
            "known_at": "after_signal_date_close_production_run",
        }

    return result


def attach_peer_earnings_reaction_to_signals(
    signals: list[dict[str, Any]],
    sidecar: dict[str, dict[str, Any]],
) -> None:
    """Mutate signals in-place to attach peer_earnings_reaction attribution.

    The sidecar dict is keyed by ticker. If a ticker is missing from the
    sidecar, the signal receives a stub record marking coverage as missing.
    """
    stub = {
        "rule_version": RULE_VERSION,
        "early_peer_earnings_reaction_bucket_v1": "coverage_missing",
        "peer_earnings_reaction_seen": None,
        "peer_earnings_reaction_details": [],
        "read_only": True,
        "alters_orders": False,
        "trade_enabled": False,
    }
    for signal in signals:
        ticker = str(signal.get("ticker") or "").upper()
        signal["peer_earnings_reaction"] = sidecar.get(ticker, stub)
