"""Intraday risk re-check core for the advisory midday review (~10:00 PT).

ADVISORY ONLY — execution monitoring of EXISTING rules at intraday prices.
This module re-evaluates the same exit levels / exit signals production uses
(trend_signals.compute_position_context) with an intraday quote instead of the
last EOD close. It introduces NO new strategy rules: proximity ("approaching")
fields below are report-display-only and never feed evaluate_exit_signals,
signal generation, sizing, or orders.

Nothing here is consumed by run.py, backtester.py, or experiments. Output
paths live under data/daily/intraday/ and are intentionally NOT registered in
data_paths.DAILY_ARTIFACTS so EOD/backtest code cannot resolve them.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

try:
    from data_paths import DATA_ROOT
    from macro_events import (
        calendar_family_coverage,
        macro_events_on,
        upcoming_macro_events,
    )
    from open_position_schema import positions_by_ticker
    from position_manager import compute_atr
    from regime import MA_PERIOD, _compute_regime_from_ohlcv
    from trend_signals import compute_position_context
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_paths import DATA_ROOT
    from quant.macro_events import (
        calendar_family_coverage,
        macro_events_on,
        upcoming_macro_events,
    )
    from quant.open_position_schema import positions_by_ticker
    from quant.position_manager import compute_atr
    from quant.regime import MA_PERIOD, _compute_regime_from_ohlcv
    from quant.trend_signals import compute_position_context

logger = logging.getLogger(__name__)

# Display-only "approaching" threshold: a stop/target within this fraction of
# the current price is flagged in the APPROACHING report section. This is NOT
# an exit rule (see module docstring / Gate boundary in CLAUDE.md).
PROXIMITY_PCT = 0.02

INDEX_TICKERS = ["SPY", "QQQ"]

_INTRADAY_OUTPUTS: dict[str, tuple[str, str, str]] = {
    "report": ("daily/intraday/reports", "intraday_report", "txt"),
    "llm_prompt": ("daily/intraday/llm", "intraday_llm_prompt", "txt"),
    "news_raw": ("daily/intraday/news", "intraday_news_raw", "json"),
    "trade_news": ("daily/intraday/news", "intraday_trade_news", "json"),
    "snapshot": ("daily/intraday/snapshots", "intraday_review", "json"),
}


def intraday_output_path(
    kind: str,
    date_str: str,
    time_label: str,
    data_dir: str | Path | None = None,
) -> Path:
    """Path for an intraday artifact, e.g. intraday_report_20260610_1300ET.txt.

    The time label keeps multiple runs per day side by side and keeps these
    files structurally unresolvable via data_paths.daily_artifact_path().
    """
    subdir, prefix, ext = _INTRADAY_OUTPUTS[kind]
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    return root / subdir / f"{prefix}_{date_str}_{time_label}.{ext}"


def split_completed_sessions(ohlcv, asof_et_date):
    """Split a daily OHLCV frame into (completed_sessions, today_partial_row).

    When run intraday, yfinance daily frames usually end with TODAY'S
    UNFINISHED bar. That row must be excluded from MA200 / ATR / high_20d /
    prev_close / high_since_entry math — otherwise prev_close becomes the
    intraday price itself (session return pinned to 0) and every rolling stat
    is contaminated by a half-day bar.

    Returns (completed_df_or_None, partial_last_row_or_None).
    """
    if ohlcv is None or len(ohlcv) == 0:
        return None, None
    try:
        row_dates = [ts.date() for ts in ohlcv.index]
    except (AttributeError, TypeError):
        logger.warning("split_completed_sessions: non-datetime index, passing through")
        return ohlcv, None
    mask = [d < asof_et_date for d in row_dates]
    completed = ohlcv.iloc[[i for i, keep in enumerate(mask) if keep]]
    partial = None
    if not all(mask):
        partial = ohlcv.iloc[-1]
    if len(completed) == 0:
        return None, partial
    return completed, partial


def _classify_regime(above_flags: list[bool]) -> str:
    if not above_flags:
        return "UNKNOWN"
    above = sum(1 for f in above_flags if f)
    if above == len(above_flags):
        return "BULL"
    if above == 0:
        return "BEAR"
    return "NEUTRAL"


def build_intraday_market_regime(
    index_ohlcv: dict,
    quotes: dict,
    asof_et_date,
    ma_period: int = MA_PERIOD,
) -> dict:
    """Market regime with MA from completed sessions, judged at intraday price.

    Mirrors regime.compute_market_regime() output, with extra per-index keys:
    intraday_price / price_source / eod_above_ma (last-completed-close basis).
    Does not call compute_market_regime() directly: its live download would
    blend today's partial bar into the MA window.
    """
    indices: dict[str, dict] = {}
    intraday_flags: list[bool] = []
    eod_flags: list[bool] = []

    for ticker in INDEX_TICKERS:
        completed, _ = split_completed_sessions(index_ohlcv.get(ticker), asof_et_date)
        info = _compute_regime_from_ohlcv(ticker, completed, ma_period)
        if info is None:
            continue
        ma_value = info[f"ma{ma_period}"]
        eod_above = bool(info["above_ma"])

        quote = (quotes or {}).get(ticker) or {}
        price = quote.get("price")
        if price is not None and ma_value:
            intraday_above = price > ma_value
            intraday_pct = round((price - ma_value) / ma_value, 4)
        else:
            # No usable intraday quote: fall back to the EOD-close judgement.
            price = info["close"]
            intraday_above = eod_above
            intraday_pct = info["pct_from_ma"]

        indices[ticker] = {
            **info,
            "above_ma": intraday_above,
            "pct_from_ma": intraday_pct,
            "intraday_price": round(price, 2),
            "price_source": quote.get("source", "eod_close_fallback"),
            "quote_time_et": quote.get("quote_time_et"),
            "capture_time_et": quote.get("capture_time_et"),
            "eod_above_ma": eod_above,
            "eod_close": info["close"],
        }
        intraday_flags.append(intraday_above)
        eod_flags.append(eod_above)

    if not indices:
        return {
            "regime": "UNKNOWN",
            "eod_basis_regime": "UNKNOWN",
            "regime_flip_intraday": False,
            "note": "Could not compute index data — treat as NEUTRAL",
            "indices": {},
        }

    regime = _classify_regime(intraday_flags)
    eod_regime = _classify_regime(eod_flags)
    flipped = regime != eod_regime
    note = f"Intraday-price basis: {regime} (last-close basis: {eod_regime})."
    if flipped:
        note += " REGIME FLIP INTRADAY — confirm at the close before acting on regime rules."

    return {
        "regime": regime,
        "eod_basis_regime": eod_regime,
        "regime_flip_intraday": flipped,
        "note": note,
        "indices": indices,
    }


def _distance_pct(price: float, level) -> float | None:
    """Signed distance from price down to a stop level, as fraction of price.

    Positive = price above the level (room left); negative = level breached.
    """
    if not level or not price or price <= 0:
        return None
    return round((price - level) / price, 4)


def _proximity_fields(price: float, ctx: dict) -> dict:
    levels = ctx.get("exit_levels", {})
    triggered_rules = {
        t.get("rule") for t in ctx.get("exit_signals", {}).get("triggered_rules", [])
    }

    fields: dict = {"proximity_flags": []}

    pairs = [
        ("distance_to_hard_stop_pct", levels.get("hard_stop_price"),
         "NEAR_HARD_STOP", "HARD_STOP"),
        ("distance_to_atr_stop_pct", levels.get("atr_stop_price"),
         "NEAR_ATR_STOP", "ATR_STOP"),
        ("distance_to_trailing_stop_pct", ctx.get("trailing_stop_from_20d_high"),
         "NEAR_TRAILING_STOP", "TRAILING_STOP"),
    ]
    for field, level, flag, rule in pairs:
        dist = _distance_pct(price, level)
        if dist is None:
            continue
        fields[field] = dist
        if 0 <= dist < PROXIMITY_PCT and rule not in triggered_rules:
            fields["proximity_flags"].append(flag)

    target = levels.get("signal_target_price")
    if target and price > 0:
        dist_to_target = round((target - price) / price, 4)
        fields["distance_to_target_pct"] = dist_to_target
        if 0 <= dist_to_target < PROXIMITY_PCT and not (
            {"SIGNAL_TARGET", "LEGACY_TARGET_REVIEW"} & triggered_rules
        ):
            fields["proximity_flags"].append("NEAR_TARGET")

    return fields


def build_position_reviews(
    open_positions: dict,
    ohlcv_dict: dict,
    quotes: dict,
    asof_et_date,
) -> list[dict]:
    """Re-evaluate each held position's EXISTING exit rules at intraday prices.

    Wiring mirrors run.py STEP 5 (ATR / high_20d / prev_close / high_since_entry
    from completed sessions, then compute_position_context) so exit_levels and
    exit_signals share production semantics exactly — only the price is fresher.
    """
    reviews: list[dict] = []
    held = positions_by_ticker(open_positions, positive_only=True)

    for ticker in sorted(held):
        pos = held[ticker]
        quote = (quotes or {}).get(ticker) or {}
        price = quote.get("price")

        review = {
            "ticker": ticker,
            "sleeve": pos.get("sleeve"),
            "quote": {
                "price": price,
                "day_high": quote.get("day_high"),
                "day_low": quote.get("day_low"),
                "source": quote.get("source", "unavailable"),
                "quote_time_et": quote.get("quote_time_et"),
                "capture_time_et": quote.get("capture_time_et"),
                "is_stale": quote.get("is_stale", True),
            },
        }

        if price is None:
            review["status"] = "QUOTE_UNAVAILABLE"
            reviews.append(review)
            continue

        completed, _ = split_completed_sessions(ohlcv_dict.get(ticker), asof_et_date)

        atr = high_20d = prev_close = high_since_entry = None
        if completed is not None and len(completed) > 0:
            atr = compute_atr(completed)
            try:
                raw = completed["High"].tail(20).max()
                high_20d = float(raw.item() if hasattr(raw, "item") else raw)
            except Exception:
                high_20d = None
            try:
                raw = completed["Close"].iloc[-1]
                prev_close = float(raw.item() if hasattr(raw, "item") else raw)
            except Exception:
                prev_close = None
            entry_date_str = pos.get("entry_date")
            if entry_date_str:
                try:
                    since = completed[completed.index >= pd.Timestamp(entry_date_str)]
                    if not since.empty:
                        raw = since["High"].max()
                        high_since_entry = float(
                            raw.item() if hasattr(raw, "item") else raw
                        )
                except Exception:
                    high_since_entry = None
        # Intraday session high extends the trailing high-water mark.
        day_high = quote.get("day_high")
        if day_high:
            high_since_entry = max(high_since_entry or 0, day_high) or None

        ctx = compute_position_context(
            ticker,
            price,
            open_positions,
            atr=atr,
            high_20d=high_20d,
            high_since_entry=high_since_entry,
            prev_close=prev_close,
            daily_high=day_high,
        )
        if ctx is None:
            review["status"] = "NO_CONTEXT"
            reviews.append(review)
            continue

        review["context"] = ctx
        # Raw inputs surfaced for the orchestrator's portfolio-heat call
        # (compute_portfolio_heat features_dict needs atr / high_20d).
        review["atr"] = atr
        review["high_20d"] = high_20d
        review.update(_proximity_fields(price, ctx))
        if ctx["exit_signals"]["any_triggered"]:
            review["status"] = "BREACHED"
        elif review.get("proximity_flags"):
            review["status"] = "APPROACHING"
        else:
            review["status"] = "OK"
        reviews.append(review)

    return reviews


def build_macro_context(date_iso: str, horizon_days: int = 7) -> dict:
    """Today's macro events + upcoming events + per-family calendar coverage."""
    coverage = calendar_family_coverage()
    stale_families = sorted(
        family for family, end in coverage.items() if end < date_iso
    )
    return {
        "today": macro_events_on(date_iso),
        "upcoming": upcoming_macro_events(date_iso, horizon_days=horizon_days),
        "family_coverage_end": coverage,
        "stale_families": stale_families,
    }


# ── Report rendering ─────────────────────────────────────────────────────────

def _fmt_pct(value, signed=True) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.1f}%" if signed else f"{value * 100:.1f}%"


def _quote_label(quote: dict) -> str:
    label = quote.get("source", "unavailable")
    if quote.get("quote_time_et"):
        label += f" {quote['quote_time_et']}"
    if quote.get("is_stale"):
        label += " [STALE: last EOD close]"
    return label


def _position_lines(review: dict) -> list[str]:
    ticker = review["ticker"]
    quote = review["quote"]
    price = quote.get("price")

    if review["status"] == "QUOTE_UNAVAILABLE":
        return [f"  {ticker:<6} QUOTE UNAVAILABLE — manual check required"]
    if review["status"] == "NO_CONTEXT":
        return [f"  {ticker:<6} ${price:.2f} — no position context (check open_positions.json)"]

    ctx = review["context"]
    session = ctx.get("daily_return_pct")
    lines = [
        f"  {ticker:<6} ${price:.2f} ({_fmt_pct(session)} today, {_quote_label(quote)})"
    ]

    for rule in ctx["exit_signals"]["triggered_rules"]:
        lines.append(f"    {rule['rule']} {rule['urgency']}: {rule['message']}")

    levels = ctx.get("exit_levels", {})
    detail = []
    hard = levels.get("hard_stop_price")
    if hard:
        suffix = f" [stop_source={ctx.get('stop_source')}]"
        if ctx.get("stop_source") == "auto_rolling":
            suffix += " (intraday rolling value, not the EOD level)"
        dist = review.get("distance_to_hard_stop_pct")
        detail.append(f"hard stop {hard:.2f} ({_fmt_pct(dist)} away){suffix}")
    atr_stop = levels.get("atr_stop_price")
    if atr_stop:
        detail.append(
            f"ATR stop {atr_stop:.2f} ({_fmt_pct(review.get('distance_to_atr_stop_pct'))} away)"
        )
    trailing = ctx.get("trailing_stop_from_20d_high")
    if trailing:
        detail.append(
            f"trailing {trailing:.2f} "
            f"({_fmt_pct(review.get('distance_to_trailing_stop_pct'))} away)"
        )
    target = levels.get("signal_target_price")
    if target:
        detail.append(
            f"target {target:.2f} ({_fmt_pct(review.get('distance_to_target_pct'))} to go)"
        )
    for chunk in detail:
        lines.append(f"    {chunk}")
    if review.get("proximity_flags"):
        lines.append(f"    flags: {', '.join(review['proximity_flags'])}")
    return lines


def _ok_position_line(review: dict) -> str:
    ticker = review["ticker"]
    quote = review["quote"]
    price = quote.get("price")
    if price is None:
        return f"  {ticker:<6} QUOTE UNAVAILABLE — manual check required"
    ctx = review.get("context", {})
    session = ctx.get("daily_return_pct")
    stop_d = review.get("distance_to_hard_stop_pct")
    tgt_d = review.get("distance_to_target_pct")
    return (
        f"  {ticker:<6} ${price:<9.2f} day {_fmt_pct(session):<7} "
        f"stop {_fmt_pct(stop_d):<7} target {_fmt_pct(tgt_d):<7} "
        f"[{quote.get('source')}]"
    )


def render_intraday_report(review: dict) -> str:
    """Human-readable intraday risk review, modeled on the EOD report style."""
    bar = "=" * 60
    thin = "-" * 60
    lines = [
        bar,
        f"INTRADAY RISK REVIEW  —  {review['generated_at_et']} ({review['generated_at_pt']})",
        "ADVISORY ONLY — execution monitoring of existing rules.",
        "No new entry signals. Does not modify EOD artifacts or operator_inputs/.",
        bar,
        "",
    ]

    macro = review.get("macro", {})
    today_events = macro.get("today", [])
    if today_events:
        labels = "; ".join(f"{e['family']} ({e['label']})" for e in today_events)
        lines.append(f"MACRO EVENT DAY: *** {labels} ***")
        lines.append("  Scheduled-release day — expect headline-driven volatility.")
    else:
        lines.append("MACRO EVENT DAY: none scheduled today")
    for family in macro.get("stale_families", []):
        end = macro.get("family_coverage_end", {}).get(family)
        lines.append(
            f"  [!] {family} calendar coverage ended {end} — STALE, "
            "update quant/macro_events.py from the official schedule"
        )
    upcoming = macro.get("upcoming", [])
    if upcoming:
        nxt = ", ".join(f"{e['date']} {e['family']}" for e in upcoming)
        lines.append(f"  Upcoming (7d): {nxt}")
    lines.append("")

    regime = review.get("market_regime_intraday", {})
    lines.append(
        f"MARKET REGIME (intraday): {regime.get('regime', 'UNKNOWN')}   "
        f"[last-close basis: {regime.get('eod_basis_regime', 'UNKNOWN')}]"
    )
    if regime.get("regime_flip_intraday"):
        lines.append(
            f"  *** REGIME FLIP INTRADAY: {regime['eod_basis_regime']} "
            f"-> {regime['regime']} ***"
        )
    for ticker, info in regime.get("indices", {}).items():
        lines.append(
            f"  {ticker} {info['intraday_price']:.2f} vs 200MA "
            f"{info.get('ma200', 0):.2f} ({_fmt_pct(info.get('pct_from_ma'))})  "
            f"[{info.get('price_source')}]"
        )
    lines.append("")

    heat = review.get("portfolio_heat")
    if heat:
        lines.append(
            f"PORTFOLIO HEAT (intraday prices): "
            f"{heat['portfolio_heat_pct'] * 100:.1f}% / cap "
            f"{heat['max_heat_pct'] * 100:.0f}%   "
            f"(quote coverage {review.get('heat_quote_coverage', 'n/a')})"
        )
    else:
        lines.append("PORTFOLIO HEAT: unavailable")
    lines.append("")

    positions = review.get("positions", [])
    breached = [p for p in positions if p["status"] == "BREACHED"]
    approaching = [p for p in positions if p["status"] == "APPROACHING"]
    unreviewed = [
        p for p in positions if p["status"] in ("QUOTE_UNAVAILABLE", "NO_CONTEXT")
    ]
    rest = [p for p in positions if p["status"] == "OK"]

    lines.append(thin)
    lines.append("BREACHED — existing rules currently triggered at intraday prices")
    lines.append(thin)
    if breached:
        for p in breached:
            lines.extend(_position_lines(p))
    else:
        lines.append("  none")
    lines.append("")

    lines.append(thin)
    lines.append(
        f"APPROACHING — within {PROXIMITY_PCT * 100:.0f}% of a stop/target "
        "(advisory display only, not an exit rule)"
    )
    lines.append(thin)
    if approaching:
        for p in approaching:
            lines.extend(_position_lines(p))
    else:
        lines.append("  none")
    lines.append("")

    lines.append(thin)
    lines.append("OK POSITIONS")
    lines.append(thin)
    if rest:
        for p in rest:
            lines.append(_ok_position_line(p))
    else:
        lines.append("  none")
    lines.append("")

    if unreviewed:
        lines.append(thin)
        lines.append("NOT REVIEWED — quote/data missing, verify manually")
        lines.append(thin)
        for p in unreviewed:
            lines.extend(_position_lines(p))
        lines.append("")

    pending = review.get("pending_actions", [])
    if pending:
        lines.append(thin)
        lines.append("PENDING ACTIONS STILL OPEN (operator_inputs / prior advice)")
        lines.append(thin)
        for action in pending:
            lines.append(
                f"  {action.get('ticker', '?'):<6} {action.get('action', '?')} "
                f"(from {action.get('advice_date', action.get('created_date', '?'))})"
            )
        lines.append("")

    news = review.get("news")
    if news is not None:
        items = news.get("trade_items", [])
        lines.append(thin)
        lines.append(
            f"INTRADAY NEWS (fetched {review['generated_at_et']}): "
            f"{len(items)} trade-filtered item(s)"
        )
        lines.append(thin)
        held_tickers = {p["ticker"] for p in positions}
        def _is_held(item):
            return bool(held_tickers & set(item.get("tickers", [])))
        shown = sorted(items, key=lambda it: (not _is_held(it),))[:15]
        for item in shown:
            tickers = ",".join(item.get("tickers", [])) or "-"
            tier = item.get("tier", "?")
            lines.append(f"  [{tier}] {tickers}: {item.get('title', '')[:90]}")
        if not items:
            lines.append("  none after trade filters")
        lines.append("")

    dq = review.get("data_quality", {})
    quote_sources = dq.get("quote_sources", {})
    src_txt = " ".join(f"{k}={v}" for k, v in sorted(quote_sources.items())) or "n/a"
    lines.append(thin)
    lines.append(f"DATA QUALITY: quotes {src_txt}")
    if "news_sources_ok" in dq:
        lines.append(
            f"  news sources ok={dq['news_sources_ok']} failed={dq['news_sources_failed']}"
        )
    for finding in dq.get("calendar_audit", []):
        marker = "[!]" if finding["severity"] in ("stale", "gap", "error") else "[i]"
        lines.append(f"  {marker} calendar/{finding['calendar']}: {finding['message']}")
    lines.append(
        "  Note: daily history is dividend-adjusted while live quotes are raw; "
        "tiny stop/ATR offsets are possible near ex-dividend dates."
    )
    lines.append(bar)
    return "\n".join(lines) + "\n"


# ── LLM prompt ───────────────────────────────────────────────────────────────

_LLM_SYSTEM = """You are an INTRADAY RISK REVIEW assistant for a daily-cadence
long-equity system. This is a midday (10:00 PT / 13:00 ET) advisory check of
EXISTING risk rules at intraday prices — it is NOT a trading-signal session.

Hard constraints on your recommendations:
- Allowed outputs per position: HOLD, or early execution of an ALREADY
  TRIGGERED existing rule (EXIT / REDUCE per the rule's semantics), or
  tightening override_stop_price.
- Do NOT recommend opening new positions or adding to positions.
- Do NOT invent new exit rules; "approaching" flags are informational only.
- Intraday quotes are not closing prices; flag anything marked STALE or
  QUOTE UNAVAILABLE for manual verification instead of acting on it.
"""


def build_intraday_llm_prompt(review: dict) -> str:
    """Self-contained intraday risk prompt (paste into any LLM)."""
    payload_positions = []
    for p in review.get("positions", []):
        entry = {
            "ticker": p["ticker"],
            "status": p["status"],
            "quote": p["quote"],
            "proximity_flags": p.get("proximity_flags", []),
        }
        for key in (
            "distance_to_hard_stop_pct",
            "distance_to_atr_stop_pct",
            "distance_to_trailing_stop_pct",
            "distance_to_target_pct",
        ):
            if key in p:
                entry[key] = p[key]
        if "context" in p:
            entry["position_context"] = p["context"]
        payload_positions.append(entry)

    news = review.get("news") or {}
    news_items = news.get("trade_items", [])[:25]

    sections = [
        _LLM_SYSTEM,
        f"AS OF: {review['generated_at_et']} ({review['generated_at_pt']})",
        "",
        "MACRO EVENT CONTEXT:",
        json.dumps(review.get("macro", {}), indent=2, ensure_ascii=False),
        "",
        "MARKET REGIME (intraday-price basis vs last-close basis):",
        json.dumps(review.get("market_regime_intraday", {}), indent=2, ensure_ascii=False),
        "",
        "PORTFOLIO HEAT (intraday prices):",
        json.dumps(review.get("portfolio_heat"), indent=2, ensure_ascii=False),
        "",
        "HELD POSITIONS (existing-rule re-check at intraday prices):",
        json.dumps(payload_positions, indent=2, ensure_ascii=False),
        "",
        "OPEN PENDING ACTIONS (unexecuted prior advice):",
        json.dumps(review.get("pending_actions", []), indent=2, ensure_ascii=False),
        "",
        f"INTRADAY NEWS (trade-filtered, {len(news_items)} item(s) shown):",
        json.dumps(news_items, indent=2, ensure_ascii=False),
        "",
        "TASK: For each held position, output HOLD / EXIT / REDUCE / TIGHTEN_STOP",
        "with a one-sentence reason. Only EXIT/REDUCE where an existing rule has",
        "already triggered (status BREACHED). Then give a one-paragraph portfolio",
        "risk summary for the rest of today's session.",
    ]
    return "\n".join(sections) + "\n"
