#!/usr/bin/env python3
"""Intraday risk re-check — ADVISORY ONLY, manually triggered around 10:00 PT.

Re-evaluates EXISTING exit rules / regime / portfolio heat at intraday prices
and writes an advisory report, an LLM prompt, and a JSON snapshot under
data/daily/intraday/. Generates nothing consumed by run.py, backtester.py, or
experiments, and never writes operator_inputs/.

Usage (Windows):
    .\\.venv\\Scripts\\python.exe -B quant\\run_intraday.py [--no-news] [--offline]

Flags:
    --no-news   skip the intraday RSS fetch/filter pass
    --offline   no quote network calls (all quotes fall back to last EOD close;
                implies --no-news) — for smoke tests
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

try:
    from data_layer import get_ohlcv_many
    from data_paths import DATA_ROOT
    from intraday_quotes import get_intraday_quotes, quote_source_summary
    from intraday_review import (
        INDEX_TICKERS,
        build_advisory_shadow_actions,
        build_intraday_llm_prompt,
        build_intraday_market_regime,
        build_macro_context,
        build_position_reviews,
        intraday_output_path,
        render_intraday_report,
        split_completed_sessions,
    )
    from news_text_sanitizer import annotate_news_items, build_news_sanitation_summary
    from open_position_schema import positions_by_ticker
    from pending_actions import get_open_pending_actions
    from portfolio_accounting import resolve_portfolio_accounting
    from portfolio_engine import compute_portfolio_heat
    from trend_signals import load_open_positions
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_layer import get_ohlcv_many
    from quant.data_paths import DATA_ROOT
    from quant.intraday_quotes import get_intraday_quotes, quote_source_summary
    from quant.intraday_review import (
        INDEX_TICKERS,
        build_advisory_shadow_actions,
        build_intraday_llm_prompt,
        build_intraday_market_regime,
        build_macro_context,
        build_position_reviews,
        intraday_output_path,
        render_intraday_report,
        split_completed_sessions,
    )
    from quant.news_text_sanitizer import (
        annotate_news_items,
        build_news_sanitation_summary,
    )
    from quant.open_position_schema import positions_by_ticker
    from quant.pending_actions import get_open_pending_actions
    from quant.portfolio_accounting import resolve_portfolio_accounting
    from quant.portfolio_engine import compute_portfolio_heat
    from quant.trend_signals import load_open_positions

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_intraday")


def _write_intraday_text(text: str, filepath: str | Path) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _write_intraday_json(obj, filepath: str | Path, *, indent=2, default=None) -> None:
    _write_intraday_text(
        json.dumps(obj, indent=indent, ensure_ascii=False, default=default),
        filepath,
    )


def _completed_closes(ohlcv_dict: dict, asof_et_date) -> dict[str, float]:
    closes: dict[str, float] = {}
    for ticker, frame in (ohlcv_dict or {}).items():
        completed, _ = split_completed_sessions(frame, asof_et_date)
        if completed is None or len(completed) == 0:
            continue
        try:
            raw = completed["Close"].iloc[-1]
            closes[ticker] = float(raw.item() if hasattr(raw, "item") else raw)
        except Exception:
            continue
    return closes


def _offline_quotes(
    tickers,
    daily_closes: dict[str, float],
    capture_time_et: str,
) -> dict[str, dict]:
    quotes = {}
    for raw in dict.fromkeys(str(t).upper() for t in tickers if t):
        close = daily_closes.get(raw)
        quotes[raw] = {
            "ticker": raw,
            "price": close,
            "day_high": None,
            "day_low": None,
            "source": "eod_close_fallback" if close else "unavailable",
            "quote_time_et": None,
            "capture_time_et": capture_time_et,
            "is_stale": True,
        }
    return quotes


def _fetch_intraday_news(held_tickers: set[str]) -> dict | None:
    """Fresh midday RSS pass (run.py STEP 8 semantics, intraday-only outputs)."""
    from filter import WATCHLIST, apply_hygiene_filters, apply_trade_filters
    from parser import (
        deduplicate_items,
        parse_feed_with_diagnostics,
        sort_items_by_date,
    )
    from sources import get_all_sources

    all_items: list = []
    source_stats: list = []
    sources = get_all_sources()
    log.info("Fetching intraday news from %d RSS sources...", len(sources))
    for source in sources:
        try:
            items, diagnostics = parse_feed_with_diagnostics(
                source["url"], source["source_type"], source.get("metadata", {})
            )
            all_items.extend(items)
            source_stats.append(diagnostics)
        except Exception as e:
            log.warning("Source %s: %s", source["url"], e)
            source_stats.append({"url": source["url"], "error": str(e)})

    sorted_items = sort_items_by_date(deduplicate_items(all_items))
    apply_hygiene_filters(sorted_items)  # log-visible hygiene stats only
    trade_watchlist = sorted(set(WATCHLIST) | held_tickers)
    trade_items = apply_trade_filters(sorted_items, watchlist=trade_watchlist)["items"]
    failed = sum(1 for s in source_stats if s.get("error"))
    log.info(
        "Intraday news: %d raw -> %d trade-filtered (%d/%d sources failed)",
        len(sorted_items), len(trade_items), failed, len(source_stats),
    )
    return {
        "raw_items": sorted_items,
        "trade_items": trade_items,
        "sources_ok": len(source_stats) - failed,
        "sources_failed": failed,
    }


def _persist_intraday_structured_news_observation(
    date_str: str,
    time_label: str,
    data_dir,
) -> dict:
    """Persist read-only structured intraday event rows after trade news is saved."""
    try:
        try:
            from intraday_news_structured_event_snapshot import (
                persist_intraday_structured_event_snapshot,
            )
        except ImportError:  # pragma: no cover - package-style imports in tests
            from quant.intraday_news_structured_event_snapshot import (
                persist_intraday_structured_event_snapshot,
            )

        snapshot = persist_intraday_structured_event_snapshot(
            date_str,
            time_label,
            data_dir=data_dir,
        )
        event_rows = (snapshot.get("event_contract_audit") or {}).get(
            "selected_ledger_rows",
            0,
        )
        observation_rows = (
            snapshot.get("forward_observation_contract_audit") or {}
        ).get("observation_rows", 0)
        target_rows = (
            snapshot.get("forward_observation_contract_audit") or {}
        ).get("target_relation_quality_rows", 0)
        log.info(
            "Intraday structured-news observations: events=%s observations=%s target=%s",
            event_rows,
            observation_rows,
            target_rows,
        )
        return snapshot
    except Exception as e:
        log.warning("Intraday structured-news observation snapshot unavailable: %s", e)
        return {
            "status": "unavailable",
            "error": str(e),
            "strategy_behavior_changed": False,
            "trade_enabled": False,
        }


def main(no_news: bool = False, offline: bool = False, data_dir=None) -> dict:
    if offline:
        no_news = True
    data_dir = data_dir if data_dir is not None else DATA_ROOT

    now_et = pd.Timestamp.now(tz="America/New_York")
    now_pt = now_et.tz_convert("America/Los_Angeles")
    asof_date = now_et.date()
    date_str = now_et.strftime("%Y%m%d")
    date_iso = now_et.strftime("%Y-%m-%d")
    time_label = now_et.strftime("%H%M") + "ET"
    capture_time_et = now_et.strftime("%Y-%m-%d %H:%M ET")

    log.info("Intraday review as of %s ET / %s PT",
             now_et.strftime("%Y-%m-%d %H:%M"), now_pt.strftime("%H:%M"))
    if now_et.weekday() >= 5:
        log.warning("Weekend run — market closed, quotes will be last close.")
    elif not (9 * 60 + 30 <= now_et.hour * 60 + now_et.minute <= 16 * 60):
        log.warning("Outside regular session (9:30-16:00 ET) — quote semantics "
                    "are ambiguous, treat prices with care.")

    open_positions = load_open_positions()
    held = positions_by_ticker(open_positions, positive_only=True)
    held_tickers = set(held)
    if not held_tickers:
        log.warning("No open positions — producing regime/news-only review.")

    tickers = sorted(held_tickers | set(INDEX_TICKERS))

    ohlcv_dict: dict = {}
    try:
        ohlcv_dict = get_ohlcv_many(tickers) or {}
    except Exception as e:
        log.error("OHLCV download failed: %s", e)
    daily_closes = _completed_closes(ohlcv_dict, asof_date)

    if offline:
        quotes = _offline_quotes(tickers, daily_closes, capture_time_et)
    else:
        try:
            quotes = get_intraday_quotes(
                tickers,
                daily_closes,
                capture_time_et=capture_time_et,
            )
        except Exception as e:
            log.error("Quote fetch failed entirely: %s", e)
            quotes = _offline_quotes(tickers, daily_closes, capture_time_et)

    regime = build_intraday_market_regime(
        {t: ohlcv_dict.get(t) for t in INDEX_TICKERS}, quotes, asof_date
    )

    positions = []
    try:
        positions = build_position_reviews(open_positions, ohlcv_dict, quotes, asof_date)
    except Exception as e:
        log.error("Position review failed: %s", e, exc_info=True)

    heat = None
    heat_coverage = "n/a"
    accounting = None
    try:
        live_px = {
            t: q["price"] for t, q in quotes.items()
            if t in held_tickers and q.get("price")
        }
        if open_positions and live_px:
            accounting = resolve_portfolio_accounting(
                open_positions, live_px,
                stored_portfolio_value=open_positions.get("portfolio_value_usd"),
                logger=log,
            )
            features = {
                p["ticker"]: {"atr": p.get("atr"), "high_20d": p.get("high_20d")}
                for p in positions if "context" in p
            }
            pv = (accounting or {}).get("portfolio_value_usd")
            if pv:
                heat = compute_portfolio_heat(open_positions, live_px, pv, features)
            heat_coverage = f"{len(live_px)}/{len(held_tickers)} quotes"
    except Exception as e:
        log.error("Portfolio heat failed: %s", e)

    pending = []
    try:
        pending = get_open_pending_actions(
            open_positions, data_dir=str(data_dir), as_of_date=date_iso
        )
    except Exception as e:
        log.error("Pending actions load failed: %s", e)

    if not offline:
        try:
            try:
                from macro_events_refresh import refresh_macro_events_overlay
            except ImportError:  # pragma: no cover - package-style imports
                from quant.macro_events_refresh import refresh_macro_events_overlay
            refresh_summary = refresh_macro_events_overlay(date_iso)
            if refresh_summary.get("added"):
                log.info("Macro calendar: appended %s future date(s) from "
                         "official schedules", refresh_summary["added"])
        except Exception as e:
            log.warning("Macro calendar refresh skipped: %s", e)

    macro = build_macro_context(date_iso)

    calendar_findings = []
    try:
        from calendar_audit import audit_static_calendars
        calendar_findings = audit_static_calendars(date_iso)
        for finding in calendar_findings:
            if finding["severity"] in ("stale", "gap", "error"):
                log.warning("calendar audit: %s", finding["message"])
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.calendar_audit import audit_static_calendars
        calendar_findings = audit_static_calendars(date_iso)
    except Exception as e:
        log.error("Calendar audit failed: %s", e)

    news_payload = None
    news = None
    if not no_news:
        try:
            news_payload = _fetch_intraday_news(held_tickers)
        except Exception as e:
            log.error("Intraday news failed: %s", e)
    if news_payload:
        news_payload = dict(news_payload)
        news_payload["raw_items"] = annotate_news_items(
            news_payload.get("raw_items") or [], held_tickers
        )
        news_payload["trade_items"] = annotate_news_items(
            news_payload.get("trade_items") or [], held_tickers
        )
        news_sanitation_summary = build_news_sanitation_summary(
            news_payload["trade_items"]
        )
        news = {
            "trade_items": news_payload["trade_items"],
            "text_sanitation": news_sanitation_summary,
        }

    review = {
        "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M ET"),
        "generated_at_pt": now_pt.strftime("%H:%M PT"),
        "capture_time_et": capture_time_et,
        "date": date_str,
        "time_label": time_label,
        "advisory_note": (
            "ADVISORY ONLY: existing-rule re-check at intraday prices. "
            "Not consumed by the EOD pipeline or backtests."
        ),
        "macro": macro,
        "market_regime_intraday": regime,
        "portfolio_heat": heat,
        "heat_quote_coverage": heat_coverage,
        "accounting": accounting,
        "positions": positions,
        "advisory_shadow_actions": build_advisory_shadow_actions(positions),
        "pending_actions": pending,
        "news": news,
        "data_quality": {
            "quote_sources": quote_source_summary(
                {t: q for t, q in quotes.items() if t in held_tickers}
            ) if held_tickers else {},
            "calendar_audit": calendar_findings,
            **(
                {
                    "news_sources_ok": news_payload["sources_ok"],
                    "news_sources_failed": news_payload["sources_failed"],
                    "news_text_sanitation": news_sanitation_summary,
                }
                if news_payload else {}
            ),
        },
    }

    report_text = render_intraday_report(review)
    prompt_text = build_intraday_llm_prompt(review)

    outputs = []
    try:
        path = intraday_output_path("report", date_str, time_label, data_dir)
        _write_intraday_text(report_text, path)
        outputs.append(path)
        path = intraday_output_path("llm_prompt", date_str, time_label, data_dir)
        _write_intraday_text(prompt_text, path)
        outputs.append(path)
        path = intraday_output_path("snapshot", date_str, time_label, data_dir)
        _write_intraday_json(review, path, default=str)
        outputs.append(path)
        if news_payload:
            path = intraday_output_path("news_raw", date_str, time_label, data_dir)
            _write_intraday_json(news_payload["raw_items"], path, default=str)
            outputs.append(path)
            path = intraday_output_path("trade_news", date_str, time_label, data_dir)
            _write_intraday_json(news_payload["trade_items"], path, default=str)
            outputs.append(path)
            structured_snapshot = _persist_intraday_structured_news_observation(
                date_str,
                time_label,
                data_dir,
            )
            if structured_snapshot.get("status") != "unavailable":
                outputs.append(Path(structured_snapshot["event_artifact_path"]))
                outputs.append(
                    Path(structured_snapshot["forward_observation_artifact_path"])
                )
    except Exception as e:
        log.error("Failed writing intraday artifacts: %s", e)

    print(report_text)
    breached = sum(1 for p in positions if p["status"] == "BREACHED")
    approaching = sum(1 for p in positions if p["status"] == "APPROACHING")
    stale = sum(
        1 for t, q in quotes.items() if t in held_tickers and q.get("is_stale")
    )
    heat_txt = f"{heat['portfolio_heat_pct'] * 100:.1f}%" if heat else "n/a"
    print(f"SUMMARY: breached={breached} approaching={approaching} "
          f"regime={regime.get('regime')} heat={heat_txt}")
    if stale:
        print(f"WARNING: {stale} held-position quote(s) are stale/missing — "
              "verify those prices manually before acting.")
    for path in outputs:
        print(f"  wrote {path}")

    return review


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-news", action="store_true",
                        help="skip the intraday RSS news pass")
    parser.add_argument("--offline", action="store_true",
                        help="no quote network calls; implies --no-news")
    args = parser.parse_args()
    try:
        main(no_news=args.no_news, offline=args.offline)
    except Exception:
        log.exception("Intraday review failed")
        sys.exit(1)
