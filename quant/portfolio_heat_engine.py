"""Portfolio heat engine.

Read-only portfolio crowding diagnostics. The goal is to detect when multiple
positions are economically the same bet even if tickers differ.
"""

from __future__ import annotations


DEFAULT_THEME_MAP = {
    "NVDA": "ai_compute",
    "AMD": "ai_compute",
    "AVGO": "ai_compute",
    "TSM": "ai_compute",
    "ASML": "ai_compute",
    "LRCX": "ai_semicap",
    "AMAT": "ai_semicap",
    "MU": "ai_memory",
    "INTC": "ai_semis_turnaround",
    "LITE": "ai_optical",
    "COHR": "ai_optical",
    "BE": "ai_power",
    "VST": "ai_power",
    "TLN": "ai_power",
    "CEG": "ai_power",
    "CORZ": "btc_miner_hpc",
    "IREN": "btc_miner_hpc",
    "CIFR": "btc_miner_hpc",
    "WULF": "btc_miner_hpc",
    "RIOT": "btc_miner_hpc",
    "MARA": "btc_miner_hpc",
    "GLD": "gold",
    "IAU": "gold",
    "SLV": "silver",
    "XLE": "energy",
    "XLK": "technology_beta",
    "QQQ": "technology_beta",
    "SPY": "market_beta",
}

DEFAULT_THEME_CLUSTER_MAP = {
    "ai_compute": "ai_beta",
    "ai_semicap": "ai_beta",
    "ai_memory": "ai_beta",
    "ai_semis_turnaround": "ai_beta",
    "ai_optical": "ai_beta",
    "ai_power": "ai_infra_beta",
    "btc_miner_hpc": "btc_hpc_beta",
    "technology_beta": "tech_beta",
    "market_beta": "market_beta",
    "gold": "precious_metals",
    "silver": "precious_metals",
    "energy": "energy_beta",
}


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ticker(position):
    return str(position.get("ticker") or "").upper()


def _position_value(position, portfolio_value=None):
    explicit = _float(position.get("position_value_usd"), None)
    if explicit is not None:
        return explicit
    pct = _float(position.get("position_pct_of_portfolio"), None)
    if pct is not None and portfolio_value:
        return pct * portfolio_value
    shares = _float(position.get("shares"), 0.0)
    price = _float(position.get("current_price") or position.get("avg_cost") or position.get("entry_price"), 0.0)
    return shares * price


def _risk_value(position, portfolio_value=None):
    explicit = _float(position.get("risk_amount_usd"), None)
    if explicit is not None:
        return explicit
    risk_pct = _float(position.get("actual_risk_pct") or position.get("risk_pct"), None)
    if risk_pct is not None and portfolio_value:
        return risk_pct * portfolio_value
    entry = _float(position.get("entry_price") or position.get("avg_cost"), 0.0)
    stop = _float(position.get("stop_price"), 0.0)
    shares = _float(position.get("shares"), 0.0)
    if entry > stop > 0 and shares > 0:
        return (entry - stop) * shares
    return 0.0


def _sector(position):
    return str(position.get("sector") or "unknown").lower()


def _theme(position, theme_map=None):
    explicit = position.get("theme") or position.get("theme_segment")
    if explicit:
        return str(explicit).lower()
    theme_map = theme_map or DEFAULT_THEME_MAP
    return str(theme_map.get(_ticker(position), "unknown")).lower()


def _theme_cluster(theme, cluster_map=None):
    cluster_map = cluster_map or DEFAULT_THEME_CLUSTER_MAP
    return str(cluster_map.get(str(theme).lower(), theme or "unknown")).lower()


def _add_bucket(buckets, key, value, risk, ticker):
    key = key or "unknown"
    bucket = buckets.setdefault(key, {"value_usd": 0.0, "risk_usd": 0.0, "tickers": set()})
    bucket["value_usd"] += value
    bucket["risk_usd"] += risk
    if ticker:
        bucket["tickers"].add(ticker)


def _finalize_buckets(buckets, total_value, total_risk):
    rows = []
    for key, data in buckets.items():
        value = data["value_usd"]
        risk = data["risk_usd"]
        rows.append({
            "name": key,
            "value_usd": round(value, 2),
            "risk_usd": round(risk, 2),
            "value_pct": round(value / total_value, 4) if total_value > 0 else None,
            "risk_pct": round(risk / total_risk, 4) if total_risk > 0 else None,
            "tickers": sorted(data["tickers"]),
        })
    return sorted(rows, key=lambda r: (r.get("value_pct") or 0), reverse=True)


def _hhi(weights):
    clean = [w for w in weights if w and w > 0]
    total = sum(clean)
    if total <= 0:
        return None
    return round(sum((w / total) ** 2 for w in clean), 4)


def build_portfolio_heat_report(
    positions,
    *,
    portfolio_value=None,
    theme_map=None,
    cluster_map=None,
    max_theme_pct=0.35,
    max_cluster_pct=0.50,
    max_sector_pct=0.45,
    max_single_name_pct=0.35,
):
    """Return concentration/crowding diagnostics for open positions.

    This is read-only. It does not size, block, or alter trades.
    """
    positions = list(positions or [])
    enriched = []
    total_value = 0.0
    total_risk = 0.0
    sector_buckets = {}
    theme_buckets = {}
    cluster_buckets = {}
    sleeve_buckets = {}

    for pos in positions:
        ticker = _ticker(pos)
        value = _position_value(pos, portfolio_value)
        risk = _risk_value(pos, portfolio_value)
        sector = _sector(pos)
        theme = _theme(pos, theme_map)
        cluster = _theme_cluster(theme, cluster_map)
        sleeve = str(pos.get("sleeve") or "core").lower()

        total_value += value
        total_risk += risk
        _add_bucket(sector_buckets, sector, value, risk, ticker)
        _add_bucket(theme_buckets, theme, value, risk, ticker)
        _add_bucket(cluster_buckets, cluster, value, risk, ticker)
        _add_bucket(sleeve_buckets, sleeve, value, risk, ticker)
        enriched.append({
            "ticker": ticker,
            "sector": sector,
            "theme": theme,
            "theme_cluster": cluster,
            "sleeve": sleeve,
            "value_usd": round(value, 2),
            "risk_usd": round(risk, 2),
        })

    sectors = _finalize_buckets(sector_buckets, total_value, total_risk)
    themes = _finalize_buckets(theme_buckets, total_value, total_risk)
    clusters = _finalize_buckets(cluster_buckets, total_value, total_risk)
    sleeves = _finalize_buckets(sleeve_buckets, total_value, total_risk)

    flags = []
    for row in sectors:
        if row.get("value_pct") is not None and row["value_pct"] > max_sector_pct:
            flags.append({"type": "sector_concentration", "name": row["name"], "value_pct": row["value_pct"]})
    for row in themes:
        if row.get("value_pct") is not None and row["value_pct"] > max_theme_pct:
            flags.append({"type": "theme_concentration", "name": row["name"], "value_pct": row["value_pct"]})
    for row in clusters:
        if row.get("value_pct") is not None and row["value_pct"] > max_cluster_pct:
            flags.append({"type": "cluster_concentration", "name": row["name"], "value_pct": row["value_pct"]})
    for pos in enriched:
        pct = pos["value_usd"] / total_value if total_value > 0 else 0.0
        if pct > max_single_name_pct:
            flags.append({"type": "single_name_concentration", "name": pos["ticker"], "value_pct": round(pct, 4)})

    return {
        "schema_version": 1,
        "read_only": True,
        "positions_count": len(positions),
        "total_position_value_usd": round(total_value, 2),
        "total_planned_risk_usd": round(total_risk, 2),
        "gross_exposure_pct": round(total_value / portfolio_value, 4) if portfolio_value else None,
        "planned_risk_pct": round(total_risk / portfolio_value, 4) if portfolio_value else None,
        "sector_exposure": sectors,
        "theme_exposure": themes,
        "theme_cluster_exposure": clusters,
        "sleeve_exposure": sleeves,
        "position_details": enriched,
        "concentration_hhi": {
            "single_name_value_hhi": _hhi([p["value_usd"] for p in enriched]),
            "sector_value_hhi": _hhi([r["value_usd"] for r in sectors]),
            "theme_value_hhi": _hhi([r["value_usd"] for r in themes]),
            "cluster_value_hhi": _hhi([r["value_usd"] for r in clusters]),
        },
        "heat_flags": flags,
        "thresholds": {
            "max_theme_pct": max_theme_pct,
            "max_cluster_pct": max_cluster_pct,
            "max_sector_pct": max_sector_pct,
            "max_single_name_pct": max_single_name_pct,
        },
    }


def heat_score(report):
    """Return a compact 0-100 crowding score. Higher means hotter."""
    if not report:
        return 0
    hhi = report.get("concentration_hhi") or {}
    components = [
        hhi.get("single_name_value_hhi"),
        hhi.get("sector_value_hhi"),
        hhi.get("theme_value_hhi"),
        hhi.get("cluster_value_hhi"),
    ]
    clean = [c for c in components if c is not None]
    if not clean:
        return 0
    base = sum(clean) / len(clean)
    flag_bonus = min(0.5, 0.1 * len(report.get("heat_flags") or []))
    return round(min(100.0, (base + flag_bonus) * 100), 2)
