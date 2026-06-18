"""
Unified Quant Pipeline — single daily entry point.

Replaces both run_quant.py (technical signals) and run_pipeline.py (news + LLM).

Steps:
  1.  Load config (open_positions, universe)
  2.  Market regime           — SPY/QQQ vs 200-day MA        (single call)
  3.  OHLCV + earnings data   — 400 calendar days per ticker  (batched OHLCV)
  4.  Feature layer           — trend score, breakout, ATR, earnings features
  5.  Position context        — exit levels / exit signals for held tickers
  6.  Quant signals           — 3 strategies, risk enrichment, position sizing
  7.  Quant report            — daily report + quant_signals_YYYYMMDD.json
  8.  Fetch & filter news     — RSS sources → hygiene → trade filter
  9.  LLM prompt              — save prompt to data/daily/llm/prompts/
  10. Summary

Usage:
    cd d:/Github/ginger
    python quant/run.py
"""

import functools
import json
import logging
import os
from copy import deepcopy
from datetime import datetime

import pandas as pd

from constants import (
    ENABLED_STRATEGIES,
    ATR_TARGET_MULT,
    BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    BREAKOUT_RANK_BY_52W_HIGH,
    MAX_POSITIONS,
    REGIME_AWARE_EXIT,
)
from data_paths import daily_artifact_path, atomic_write_json, atomic_write_text
from earnings_snapshot import persist_earnings_snapshot
from estimate_revision_ledger import persist_estimate_revision_ledger
from operator_input_paths import open_positions_path, repo_relative
from open_position_schema import core_slot_positions, has_account_positions, positions_by_ticker
from regime_exit import compute_regime_exit_profile


# ── Logging ──────────────────────────────────────────────────────────────────
# colorlog adds ANSI colours: DEBUG=cyan, INFO=green, WARNING=yellow,
# ERROR=red, CRITICAL=bold red.  Falls back to plain logging if unavailable.

try:
    import colorlog
    _handler = colorlog.StreamHandler()
    _handler.setFormatter(colorlog.ColoredFormatter(
        fmt="%(asctime)s  %(log_color)s%(levelname)-7s%(reset)s  %(cyan)s%(name)s%(reset)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    ))
    logging.root.setLevel(logging.INFO)
    logging.root.handlers = [_handler]
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _save_json(obj, filepath):
    # Atomic write (temp + os.replace) so an interrupted/overlapping write can
    # never leave a half-written or stale-tailed artifact (see bug audit #9).
    atomic_write_json(obj, filepath, default=str)
    log.info(f"Saved → {filepath}")


def _save_json_best_effort(obj, filepath, artifact_name):
    try:
        _save_json(obj, filepath)
        return True
    except Exception as e:
        log.error(
            "%s save failed; continuing so news/LLM prompt can still be generated: %s",
            artifact_name,
            e,
        )
        return False


def _save_text(text, filepath):
    atomic_write_text(text, filepath)
    log.info(f"Saved → {filepath}")


def _refresh_open_positions_from_moomoo():
    """Refresh open_positions.json from the moomoo account before loading it.

    moomoo is the authoritative source for qty / avg_cost / cash / market_val;
    the operator only maintains the tag map (``operator_inputs/position_tags.json``).
    On any failure (SDK missing, OpenD down, empty account) the generator keeps
    the existing file untouched, so the daily run degrades gracefully to the
    last-known holdings rather than trading on a stale or empty book. Set
    ``GINGER_SKIP_MOOMOO_REFRESH=1`` to skip the live pull (offline reruns,
    backtests driving run.py).
    """
    if os.environ.get("GINGER_SKIP_MOOMOO_REFRESH"):
        log.info("Skipping moomoo open-positions refresh (GINGER_SKIP_MOOMOO_REFRESH set).")
        return
    try:
        from moomoo_open_positions import generate as _moomoo_generate
    except ImportError as e:
        log.warning(f"moomoo_open_positions unavailable; using existing open_positions.json: {e}")
        return
    try:
        result = _moomoo_generate(preview=False)
    except Exception as e:  # noqa: BLE001
        log.warning(f"moomoo open-positions refresh failed; using existing file: {e}")
        return
    if result.get("status") == "written":
        untagged = result.get("untagged") or []
        msg = f"Refreshed open_positions.json from moomoo -> {repo_relative(result.get('wrote'))}."
        if untagged:
            msg += f" Untagged tickers default to sleeve section: {untagged}."
        log.info(msg)
    else:
        log.warning("moomoo unavailable/empty; using existing open_positions.json (fallback).")


def _load_open_positions():
    path = open_positions_path()
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error(
                f"open_positions.json at {repo_relative(path)} is unreadable/malformed: {e}. "
                "Treating as no open positions; fix the file and re-run."
            )
            return None
    log.warning(f"open_positions.json not found at {repo_relative(path)}")
    return None


def _core_slot_ticker_set(open_positions):
    return {
        str(row.get("ticker") or "").upper().strip()
        for row in core_slot_positions(open_positions, positive_only=True)
        if row.get("ticker")
    }


def _print_section(title):
    log.info("")
    log.info("=" * 55)
    log.info(f"  {title}")
    log.info("=" * 55)


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name):
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        log.warning("Ignoring invalid integer env %s=%r", name, value)
        return None


def _env_float(name, default):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        log.warning("Ignoring invalid float env %s=%r", name, value)
        return default


# Fixed ingestion-tuning defaults. These were env-overridable knobs that were
# never set in any deployment, so the env indirection was dead config surface;
# inlined to module constants. Subsystem on/off toggles (KOVA_REFRESH_*,
# *_DISABLED, RUN_BROAD_ACCUMULATION, LLM_PROMPT_PRIORITY), manual 13F/intraday
# inputs, paths, and secrets (ALPHA_VANTAGE_API_KEY) stay env-driven.
OHLCV_WAREHOUSE_COMMIT_EVERY = 1000
EARNINGS_BROAD_BATCH_SIZE = 40
EARNINGS_BROAD_BATCH_SLEEP_SECS = 1.0
OPTIONS_MAX_TICKERS = 250
KOVA_COMPANYFACTS_STALE_DAYS = 2.0
KOVA_COMPANYFACTS_LOOKBACK_DAYS = 820
KOVA_COMPANYFACTS_MAX_CIKS = None  # None = no cap (full universe)
KOVA_DATA_SLEEP_SECONDS = 0.11


def _run_expectation_residual_leadership_attribution_observer():
    """Refresh the read-only expectation/residual attribution artifact."""
    try:
        from experiments.exp_20260525_017_expectation_residual_leadership_attribution import (
            build_payload,
            persist,
        )

        payload = build_payload()
        persist(payload, update_experiment_log=False)
        gate = payload.get("gate") or {}
        coverage = payload.get("coverage") or {}
        log.info(
            "Expectation/residual attribution: decision=%s bucket_a_5d=%s usable=%s candidates=%s",
            payload.get("decision"),
            gate.get("bucket_a_closed_5d_outcomes"),
            gate.get("total_usable_candidates"),
            coverage.get("candidate_objects_total"),
        )
        related_files = payload.get("related_files") or []
        return {
            "status": payload.get("status"),
            "decision": payload.get("decision"),
            "artifact": related_files[1] if len(related_files) > 1 else None,
            "gate": gate,
            "coverage": coverage,
            "production_impact": payload.get("production_impact"),
        }
    except Exception as e:
        log.warning(f"Expectation/residual attribution observer unavailable: {e}")
        return {
            "status": "unavailable",
            "decision": "observer_failed",
            "error": str(e),
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def _collect_trade_news(today, universe, pilot_universe):
    trade_items = []
    try:
        from sources import get_all_sources
        from parser import parse_feed_with_diagnostics, deduplicate_items, sort_items_by_date
        from filter import apply_hygiene_filters, apply_trade_filters

        all_items = []
        source_stats = []
        sources = get_all_sources(extra_tickers=pilot_universe)
        log.info(f"Fetching from {len(sources)} RSS sources...")
        for source in sources:
            try:
                items, diagnostics = parse_feed_with_diagnostics(
                    source["url"], source["source_type"], source.get("metadata", {})
                )
                all_items.extend(items)
                source_stats.append(diagnostics)
            except Exception as e:
                log.warning(f"Source {source['url']}: {e}")
                source_stats.append({
                    "url": source["url"],
                    "source_type": source["source_type"],
                    "metadata": dict(source.get("metadata", {})),
                    "request_headers_used": {},
                    "status": None,
                    "bozo": False,
                    "bozo_exception": None,
                    "entry_count": 0,
                    "parsed_item_count": 0,
                    "error": str(e),
                })

        sorted_items = sort_items_by_date(deduplicate_items(all_items))
        hygiene_items = apply_hygiene_filters(sorted_items)["items"]
        trade_watchlist = sorted(set(universe) | set(pilot_universe))
        trade_items = apply_trade_filters(
            sorted_items,
            watchlist=trade_watchlist,
        )["items"]

        _save_json_best_effort(
            sorted_items,
            str(daily_artifact_path("news", today)),
            "raw news",
        )
        _save_json_best_effort(
            source_stats,
            str(daily_artifact_path("news_source_stats", today)),
            "news source stats",
        )
        _save_json_best_effort(
            hygiene_items,
            str(daily_artifact_path("clean_news", today)),
            "clean news",
        )
        _save_json_best_effort(
            trade_items,
            str(daily_artifact_path("clean_trade_news", today)),
            "trade news",
        )

        log.info(
            f"News: {len(sorted_items)} raw -> {len(hygiene_items)} hygiene "
            f"-> {len(trade_items)} trade-filtered"
        )
    except Exception as e:
        log.error(f"News collection failed: {e}")
    return trade_items


def _generate_llm_prompt(trade_items, open_positions, trend_signals_dict):
    try:
        from llm_advisor import get_investment_advice

        result = get_investment_advice(
            trade_items,
            open_positions=open_positions,
            trend_signals=trend_signals_dict,
        )
        if result["success"]:
            log.info(result["advice"])
            return True
        log.error(f"LLM advisor: {result['error']}")
    except Exception as e:
        log.error(f"LLM advisor failed: {e}")
    return False


# ── Post-prompt accumulation steps ────────────────────────────────────────────
# These run after the operator prompt is written (deferred when
# LLM_PROMPT_PRIORITY is on, else inline). They are pure data accumulation over
# the broad universe and never feed core signals/ranking/sizing/exits.

def _refresh_reference_caches_step(universe):
    """Refresh the sector + SEC-ticker reference caches over the broad universe."""
    try:
        from reference_cache_refresh import refresh_reference_caches
        ref_cache = refresh_reference_caches(universe=universe)
        sector = ref_cache.get("sector_cache", {})
        tickers = ref_cache.get("sec_company_tickers", {})
        if sector.get("refreshed_count") or tickers.get("refreshed"):
            log.info(
                "Reference caches: sector refreshed=%s, sec_tickers refreshed=%s",
                sector.get("refreshed_count", 0),
                tickers.get("refreshed", False),
            )
    except Exception as e:
        log.warning(f"Reference cache refresh skipped: {e}")


def _broad_earnings_merge_step(universe):
    """Fetch broad-universe earnings into the shared earnings snapshot."""
    try:
        from fetch_broad_earnings_snapshot import fetch_broad_universe_earnings

        summary = fetch_broad_universe_earnings(
            as_of=datetime.now(),
            tickers=universe,
            batch_size=EARNINGS_BROAD_BATCH_SIZE,
            batch_sleep_secs=EARNINGS_BROAD_BATCH_SLEEP_SECS,
        )
        log.info(
            "Broad earnings merge: status=%s fetched=%s eps=%s failed=%s",
            summary.get("status"),
            summary.get("tickers_fetched"),
            summary.get("tickers_with_eps_estimate"),
            summary.get("tickers_failed"),
        )
    except Exception as e:
        log.warning(f"Broad earnings merge unavailable: {e}")


def _kova_sidecar_step(
    *,
    universe,
    today_iso,
    ohlcv_dict,
    spy_ohlcv,
    ohlcv_warehouse_enabled,
    ohlcv_warehouse_path,
    non_ohlcv_snapshot,
):
    """Persist the Kova data sidecar (fundamentals / rs_proxy / intraday / 13F).

    Mutates ``non_ohlcv_snapshot["kova_data_sidecar"]`` in place (faithful to the
    prior inline closure). Post-prompt accumulation only.
    """
    try:
        from kova_data_sidecar import persist_kova_data_snapshot

        # exp-20260614-022: rs_proxy is derived from this in-memory OHLCV, so
        # seeding it only from the core ohlcv_dict (~57 names) capped rs_proxy at
        # ~57 while every other stream went broad after exp-20260613-023. Seed
        # from broad warehouse frames (returns-only need) for the broad ingest
        # universe, then overlay the fresh in-memory core OHLCV + SPY on top so
        # core names keep today's data. Degrades to the core dict on any failure.
        kova_ohlcv_dict: dict = {}
        try:
            if ohlcv_warehouse_enabled and universe:
                from datetime import timedelta as _td
                from ohlcv_warehouse import load_warehouse_ohlcv_frames
                rs_start = (datetime.now().date() - _td(days=320)).isoformat()
                wh_frames = load_warehouse_ohlcv_frames(
                    ohlcv_warehouse_path,
                    tickers=set(universe) | {"SPY"},
                    start=rs_start,
                    end=today_iso,
                )
                # Convert to the list-of-dicts shape rs_proxy expects. The
                # warehouse frame index is an unnamed DatetimeIndex, so passing
                # frames straight through normalize_ohlcv_mapping drops every row
                # (reset_index yields an "index" column, not "Date").
                for tk, fr in wh_frames.items():
                    kova_ohlcv_dict[tk] = [
                        {
                            "Date": str(idx.date()),
                            "Open": float(r["Open"]),
                            "High": float(r["High"]),
                            "Low": float(r["Low"]),
                            "Close": float(r["Close"]),
                            "Volume": float(r["Volume"]),
                        }
                        for idx, r in fr.iterrows()
                    ]
                log.info(
                    "rs_proxy broad OHLCV seed: %d tickers from warehouse",
                    len(kova_ohlcv_dict),
                )
        except Exception as rs_e:
            log.warning(
                "rs_proxy broad warehouse seed failed, using core OHLCV: %s", rs_e
            )
            kova_ohlcv_dict = {}
        for t, rows in ohlcv_dict.items():
            kova_ohlcv_dict[t] = rows  # fresh in-memory core overrides warehouse
        if spy_ohlcv is not None:
            kova_ohlcv_dict["SPY"] = spy_ohlcv
        kova_intervals = tuple(
            item.strip()
            for item in os.environ.get("KOVA_INTRADAY_INTERVALS", "15min,60min").replace(";", ",").split(",")
            if item.strip()
        )
        kova_data_snapshot = persist_kova_data_snapshot(
            asof_date=today_iso,
            tickers=universe,
            data_dir="data/kova",
            non_ohlcv_dir="data/non_ohlcv",
            ohlcv_data=kova_ohlcv_dict,
            alpha_vantage_api_key=os.environ.get("ALPHA_VANTAGE_API_KEY"),
            refresh_intraday=_env_flag("KOVA_REFRESH_INTRADAY", False),
            intervals=kova_intervals,
            month=os.environ.get("KOVA_INTRADAY_MONTH") or None,
            # exp-20260613-023: refresh companyfacts on every run (was env-gated
            # off, which froze the cache at 2026-06-04) and pass a finite
            # stale_days so already-cached CIK files are re-fetched on a throttle
            # instead of being treated as permanently fresh (stale_days=None).
            refresh_companyfacts=_env_flag("KOVA_REFRESH_COMPANYFACTS", True),
            companyfacts_stale_days=KOVA_COMPANYFACTS_STALE_DAYS,
            companyfacts_max_ciks=KOVA_COMPANYFACTS_MAX_CIKS,
            companyfacts_lookback_days=KOVA_COMPANYFACTS_LOOKBACK_DAYS,
            sec13f_zip=os.environ.get("KOVA_SEC13F_ZIP") or None,
            sec13f_year=_env_int("KOVA_SEC13F_YEAR"),
            sec13f_quarter=_env_int("KOVA_SEC13F_QUARTER"),
            cusip_map=os.environ.get("KOVA_CUSIP_MAP") or None,
            refresh_sec13f=_env_flag("KOVA_REFRESH_SEC13F", False),
            sleep_seconds=KOVA_DATA_SLEEP_SECONDS,
        )
        non_ohlcv_snapshot["kova_data_sidecar"] = kova_data_snapshot
        log.info(
            "Kova data sidecar: status=%s fundamentals=%s rs=%s intraday=%s institutional=%s",
            kova_data_snapshot.get("status"),
            (kova_data_snapshot.get("fundamental_growth") or {}).get("rows_written"),
            (kova_data_snapshot.get("rs_proxy") or {}).get("rows_written"),
            (kova_data_snapshot.get("intraday_ohlcv") or {}).get("rows_written"),
            (kova_data_snapshot.get("institutional_ownership") or {}).get("rows_written"),
        )
    except Exception as e:
        log.warning(f"Kova data sidecar unavailable: {e}")
        non_ohlcv_snapshot["kova_data_sidecar"] = {
            "status": "failed",
            "asof_date": today_iso,
            "error": str(e),
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_exits": False,
                "alters_orders": False,
            },
        }


def _step2_market_regime():
    """STEP 2 — compute the SPY/QQQ market regime (UNKNOWN on any failure)."""
    _print_section("STEP 2 — Market regime")
    try:
        from regime import compute_market_regime
        market_regime = compute_market_regime()
        log.info(f"Regime: {market_regime['regime']}")
        return market_regime
    except Exception as e:
        log.warning(f"Regime unavailable: {e}")
        return {"regime": "UNKNOWN", "note": str(e), "indices": {}}


def _compute_feature_layer(data_universe, ohlcv_dict, earnings_dict):
    """STEP 4 — compute technical/event features for every data-universe ticker."""
    from feature_layer import compute_features

    features_dict = {}
    for ticker in data_universe:
        features_dict[ticker] = compute_features(
            ticker, ohlcv_dict[ticker], earnings_dict[ticker]
        )
    ok = sum(1 for f in features_dict.values() if f)
    log.info(f"Features ready: {ok}/{len(data_universe)} tickers")
    return features_dict


def _resolve_live_portfolio_value(open_positions, features_dict, portfolio_value, stored_pv):
    """STEP 4 — derive live portfolio value from positions + current prices.

    If cash_usd is omitted, cash is derived from portfolio_value_usd - live
    equity, avoiding daily manual cash maintenance while keeping sizing
    accurate. Returns the (possibly updated) portfolio value; falls back to the
    stored value when there are no positions.
    """
    from portfolio_accounting import resolve_portfolio_accounting

    if has_account_positions(open_positions, positive_only=True):
        current_px = {
            t: f["close"] for t, f in features_dict.items()
            if f and f.get("close") is not None
        }
        accounting = resolve_portfolio_accounting(
            open_positions,
            current_px,
            stored_portfolio_value=stored_pv,
            logger=log,
        )
        if accounting.get("portfolio_value_usd"):
            portfolio_value = accounting["portfolio_value_usd"]
            log.info(
                "Portfolio value: $%s (%s; equity=$%s cash=$%s)",
                f"{portfolio_value:,.0f}",
                accounting["cash_source"],
                f"{accounting['equity_market_value_usd']:,.0f}",
                (
                    f"{accounting['cash_usd']:,.0f}"
                    if accounting.get("cash_usd") is not None else "n/a"
                ),
            )
    elif portfolio_value:
        log.info(f"Portfolio value: ${portfolio_value:,.0f} (stored, no positions)")
    return portfolio_value


def main():
    today = datetime.now().strftime("%Y%m%d")
    today_iso = datetime.now().date().isoformat()

    from paper_sleeve_runner import run_sleeve as _run_sleeve

    def _sleeve(build, empty_fn, log_label, fail_reason, *, log_metrics=(),
                activity_keys=None, noun="sleeve"):
        # Thin local wrapper capturing log + today_iso; collapses each sleeve's
        # (or upstream queue's) try/activity-log/except-fallback boilerplate into
        # one call. noun="queue" for the forward-event queues.
        kwargs = {} if activity_keys is None else {"activity_keys": activity_keys}
        return _run_sleeve(
            build,
            empty_fn,
            logger=log,
            today_iso=today_iso,
            log_label=log_label,
            fail_reason=fail_reason,
            log_metrics=log_metrics,
            noun=noun,
            **kwargs,
        )

    # Shared metric/activity specs for the SEC forward-event paper sleeves (they
    # gate on new_pending_count and log pending/open/closed/pnl identically).
    _EVENT_SLEEVE_METRICS = (
        ("pending", "pending_count"),
        ("open", "open_position_count"),
        ("closed_today", "closed_count_today"),
        ("pnl", "realized_pnl_to_date"),
    )
    _EVENT_SLEEVE_ACTIVITY = ("new_pending_count", "open_position_count", "closed_count_today")
    # Standard candidate-pool sleeve metrics (default activity keys: candidate/
    # pending/open/closed). Shared by the broad-universe / relation / contraction
    # sleeves that all log candidates/pending/open/closed/pnl identically.
    _STD_SLEEVE_METRICS = (
        ("candidates", "candidate_count"),
        ("pending", "pending_count"),
        ("open", "open_position_count"),
        ("closed_today", "closed_count_today"),
        ("pnl", "realized_pnl_to_date"),
    )
    # Upstream forward-event queues: gate/log on candidate_count only, noun "queue".
    _QUEUE_METRICS = (("candidates", "candidate_count"),)
    _QUEUE_ACTIVITY = ("candidate_count",)

    # ── Step 1: Config ────────────────────────────────────────────────────────
    _print_section("STEP 1 — Loading config")

    # Imports are inside main() so the module can be imported without side-effects
    from data_layer         import get_universe, get_ohlcv, get_ohlcv_many, get_earnings_data
    from ohlcv_warehouse    import DEFAULT_WAREHOUSE_PATH, upsert_ohlcv_frames
    from feature_layer      import compute_features
    from trend_signals      import compute_position_context, save_trend_signals
    from signal_engine      import generate_signals, rank_signals_for_allocation
    from risk_engine        import enrich_signals
    from price_asof_guard   import latest_ohlcv_dates
    from portfolio_engine   import size_signals, compute_portfolio_heat
    from production_parity  import (
        build_entry_candidate_review,
        build_followthrough_addon_actions,
        count_core_strategy_positions,
        filter_entry_signal_candidates,
        plan_entry_candidates,
        risk_pct_for_market_state,
    )
    from performance_engine import compute_metrics
    from report_generator   import generate_daily_report, save_report
    from default_off_alpha_attribution import (
        build_default_off_alpha_attribution_report,
    )
    from peer_earnings_reaction import (
        attach_peer_earnings_reaction_to_signals,
        build_peer_earnings_reaction_sidecar,
    )
    from market_context import build_readonly_market_state_context
    from market_state_analysis import build_market_state_snapshot
    from daily_non_ohlcv_snapshot import persist_daily_non_ohlcv_snapshots
    from kova_data_sidecar import persist_kova_data_snapshot
    from backfill_non_ohlcv import (
        catch_up_missing_non_ohlcv,
        ensure_non_ohlcv_coverage,
    )
    from crypto_sleeve      import (
        build_crypto_sleeve_advice,
        empty_crypto_sleeve_advice,
        load_crypto_config,
    )
    from universe_adapter   import save_universe_state_report, universe_segments_as_of
    from candidate_competition_logger import summarize_pilot_competition
    from form4_event_queue import (
        build_forward_queue_from_transactions,
        empty_form4_event_queue,
    )
    from form4_event_sleeve import (
        build_form4_event_sleeve_snapshot,
        empty_form4_event_sleeve_snapshot,
    )
    from sec_event_queue import (
        build_forward_financial_report_t1_queue_from_sec_filing_events,
        build_forward_leadership_queue_from_sec_filing_text,
        build_forward_queue_from_sec_filing_text,
        build_forward_governance_queue_from_sec_filing_text,
        empty_sec_event_queue,
        empty_sec_financial_report_t1_queue,
        empty_sec_governance_queue,
        empty_sec_leadership_queue,
    )
    from sec_event_sleeve import (
        build_sec_event_sleeve_snapshot,
        empty_sec_event_sleeve_snapshot,
    )
    from sec_negative_event_sleeve import (
        build_sec_negative_event_sleeve_snapshot,
        empty_sec_negative_event_sleeve_snapshot,
    )
    from sec_leadership_event_sleeve import (
        build_sec_leadership_event_sleeve_snapshot,
        empty_sec_leadership_event_sleeve_snapshot,
    )
    from sec_financial_report_event_sleeve import (
        build_sec_financial_report_event_sleeve_snapshot,
        empty_sec_financial_report_event_sleeve_snapshot,
    )
    from event_sleeve_bundle import (
        build_event_sleeve_bundle_snapshot,
        empty_event_sleeve_bundle_snapshot,
    )
    from state_surface_sleeve import (
        build_state_surface_queue,
        build_state_surface_sleeve_snapshot,
        empty_state_surface_queue,
        empty_state_surface_sleeve_snapshot,
    )
    from low_deployment_etf_overlay import (
        build_low_deployment_etf_overlay_snapshot,
        empty_low_deployment_etf_overlay_snapshot,
    )
    from core_misfit_paper_sleeve import (
        build_core_misfit_paper_sleeve_snapshot,
        empty_core_misfit_paper_sleeve_snapshot,
    )
    from broad_market_paper_sleeve import (
        build_broad_market_candidate_universe_from_universe_state,
        empty_broad_market_paper_sleeve_snapshot,
        load_broad_market_candidate_universe,
        prep_and_build_broad_market_paper_sleeve_snapshot,
    )
    from macro_relief_leadership_paper_sleeve import (
        empty_macro_relief_leadership_snapshot,
        prep_and_build_macro_relief_leadership_snapshot,
    )
    from volatility_relief_stock_leadership_paper_sleeve import (
        empty_volatility_relief_stock_leadership_snapshot,
        prep_and_build_volatility_relief_stock_leadership_snapshot,
    )
    from rolling_corr_peer_shock_paper_sleeve import (
        empty_rolling_corr_peer_shock_paper_sleeve_snapshot,
        prep_and_build_rolling_corr_peer_shock_paper_sleeve_snapshot,
    )
    from industry_relative_laggard_repair_paper_sleeve import (
        empty_industry_relative_laggard_repair_paper_sleeve_snapshot,
        prep_and_build_industry_relative_laggard_repair_paper_sleeve_snapshot,
    )
    from industry_stable_core_flow_paper_sleeve import (
        empty_industry_stable_core_flow_snapshot,
        prep_and_build_industry_stable_core_flow_snapshot,
    )
    from turn_of_month_liquid_leadership_paper_sleeve import (
        empty_turn_of_month_liquid_leadership_snapshot,
        prep_and_build_turn_of_month_liquid_leadership_snapshot,
    )
    from narrow_range_compression_breakout_paper_sleeve import (
        empty_narrow_range_compression_breakout_snapshot,
        prep_and_build_narrow_range_compression_breakout_snapshot,
    )
    from distribution_day_absorption_leadership_paper_sleeve import (
        empty_distribution_day_absorption_leadership_snapshot,
        prep_and_build_distribution_day_absorption_leadership_snapshot,
    )
    from sbc_burden_improvement_paper_sleeve import (
        empty_sbc_burden_improvement_paper_sleeve_snapshot,
        prep_and_build_sbc_burden_improvement_paper_sleeve_snapshot,
    )
    from revision_surprise_low_extension_paper_sleeve import (
        empty_revision_surprise_low_extension_snapshot,
        prep_and_build_revision_surprise_low_extension_snapshot,
    )
    from accepted_helper_source_priority_allocator_paper_sleeve import (
        build_accepted_helper_source_priority_allocator_snapshot,
        empty_accepted_helper_source_priority_allocator_snapshot,
    )
    from ai_optical_paper_sleeve import (
        empty_ai_optical_paper_sleeve_snapshot,
        prep_and_build_ai_optical_paper_sleeve_snapshot,
    )
    from volatility_contraction_paper_sleeve import (
        empty_volatility_contraction_paper_sleeve_snapshot,
        prep_and_build_volatility_contraction_paper_sleeve_snapshot,
    )
    from volume_breadth_breakout_paper_sleeve import (
        empty_volume_breadth_breakout_paper_sleeve_snapshot,
        prep_and_build_volume_breadth_breakout_paper_sleeve_snapshot,
    )
    from post_earnings_underpriced_drift_paper_sleeve import (
        empty_post_earnings_underpriced_drift_paper_sleeve_snapshot,
        prep_and_build_post_earnings_underpriced_drift_paper_sleeve_snapshot,
    )
    from pead_broad_universe_paper_sleeve import (
        empty_pead_broad_universe_paper_sleeve_snapshot,
        prep_and_build_pead_broad_universe_paper_sleeve_snapshot,
    )
    from alpha_score_market_regime_paper_sleeve import (
        empty_alpha_score_market_regime_paper_sleeve_snapshot,
        prep_and_build_alpha_score_market_regime_paper_sleeve_snapshot,
    )
    from accepted_source_consensus_paper_sleeve import (
        build_accepted_source_consensus_paper_sleeve_snapshot,
        empty_accepted_source_consensus_paper_sleeve_snapshot,
    )
    from free_data_cross_source_consensus_paper_sleeve import (
        build_free_data_cross_source_consensus_paper_sleeve_snapshot,
        empty_free_data_cross_source_consensus_paper_sleeve_snapshot,
        finra_borrow_pressure_source_snapshot_from_finra_iwm_snapshot,
    )
    from fundamental_growth_rs_paper_sleeve import (
        empty_fundamental_growth_rs_paper_sleeve_snapshot,
        prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot,
    )
    from finra_iwm_paper_sleeve import (
        empty_finra_iwm_paper_sleeve_snapshot,
        prep_and_build_finra_iwm_paper_sleeve_snapshot,
    )
    from sec_ftd_finra_paper_sleeve import (
        empty_sec_ftd_finra_paper_sleeve_snapshot,
        prep_and_build_sec_ftd_finra_paper_sleeve_snapshot,
    )
    from space_catalyst_sleeve import (
        build_space_catalyst_event_ledger_snapshot,
        build_space_catalyst_observation_slot,
        build_space_catalyst_shadow_snapshot,
        empty_space_catalyst_event_ledger,
        empty_space_catalyst_observation_slot,
        empty_space_catalyst_shadow_snapshot,
        persist_space_catalyst_observation_slot,
        persist_space_catalyst_event_ledger,
        space_catalyst_event_tickers,
        space_catalyst_forward_replacement_positive_profiles,
        space_catalyst_observation_feature_tickers,
        space_catalyst_observation_tickers,
    )
    from pilot_sleeve       import (
        AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
        append_pilot_decision_snapshots,
        apply_pilot_sizing_policy,
        build_ai_infra_aggressive_attribution,
        build_counterfactual_snapshots,
        mark_pilot_signals,
        pilot_governance_metadata,
        pilot_records_as_of,
        select_pilot_entry_candidates,
    )
    from platform_rs20_watch import (
        build_platform_rs20_forward_watch,
        empty_platform_rs20_forward_watch,
        persist_platform_rs20_forward_watch,
    )
    from sec_10k_forward_watch import (
        build_sec_10k_forward_watch,
        empty_sec_10k_forward_watch,
        persist_sec_10k_forward_watch,
    )

    _refresh_open_positions_from_moomoo()
    open_positions    = _load_open_positions()
    _stored_pv        = (open_positions or {}).get("portfolio_value_usd")
    portfolio_value   = _stored_pv          # updated below after OHLCV is available
    universe          = get_universe()
    log.info(f"Universe ({len(universe)} tickers): {universe}")
    universe_governance_state = None
    pilot_records = {}
    pilot_universe = []
    pilot_metadata = {}
    universe_governance_state = None
    space_catalyst_shadow = empty_space_catalyst_shadow_snapshot(today_iso)
    space_catalyst_event_ledger = empty_space_catalyst_event_ledger(today_iso)
    space_catalyst_observation_slot = empty_space_catalyst_observation_slot(today_iso)
    try:
        universe_governance_state = universe_segments_as_of(
            today_iso,
            core_universe=universe,
        )
        save_universe_state_report(
            universe_governance_state,
            str(daily_artifact_path("universe_state", today)),
        )
        pilot_records = pilot_records_as_of(today_iso)
        pilot_universe = sorted(set(pilot_records) - set(universe))
        pilot_metadata = pilot_governance_metadata()
        if pilot_universe:
            universe_governance_state["mode"] = "production_pilot_sleeve"
            universe_governance_state["production_impact"] = {
                "alters_signal_generation": True,
                "alters_candidate_ranking": True,
                "alters_sizing": True,
                "alters_orders": True,
                "scope": "pilot_sleeve_only",
            }
            universe_governance_state["pilot_trade_universe"] = pilot_universe
            save_universe_state_report(
                universe_governance_state,
                str(daily_artifact_path("universe_state", today)),
            )
        log.info(
            "Universe governance: core=%s pilot=%s trade-enabled-pilot=%s research=%s specialist=%s quarantine=%s",
            len(universe_governance_state["core_trade_universe"]),
            len(universe_governance_state["segments"]["pilot"]),
            len(pilot_universe),
            len(universe_governance_state["segments"]["research"]),
            len(universe_governance_state["segments"]["specialist"]),
            len(universe_governance_state["segments"]["quarantine"]),
        )
        if pilot_universe:
            log.info("Pilot sleeve trade-enabled tickers: %s", pilot_universe)
    except Exception as e:
        log.warning(f"Universe governance adapter unavailable: {e}")
    try:
        space_catalyst_shadow = build_space_catalyst_shadow_snapshot(today_iso)
        if universe_governance_state is not None:
            universe_governance_state["space_catalyst_shadow"] = space_catalyst_shadow
            save_universe_state_report(
                universe_governance_state,
                str(daily_artifact_path("universe_state", today)),
            )
        if space_catalyst_shadow.get("candidate_count", 0) > 0:
            log.info(
                "Space catalyst shadow: candidates=%d trade_enabled=%d mode=%s",
                space_catalyst_shadow.get("candidate_count", 0),
                len(space_catalyst_shadow.get("trade_enabled_tickers") or []),
                space_catalyst_shadow.get("mode"),
            )
    except Exception as e:
        log.warning(f"Space catalyst shadow snapshot unavailable: {e}")
        space_catalyst_shadow = empty_space_catalyst_shadow_snapshot(
            today_iso,
            "space_catalyst_shadow_build_failed",
        )

    data_universe = sorted(set(universe) | set(pilot_universe))
    ohlcv_warehouse_path = os.environ.get(
        "OHLCV_WAREHOUSE_PATH",
        str(DEFAULT_WAREHOUSE_PATH),
    )
    llm_prompt_priority = _env_flag("LLM_PROMPT_PRIORITY", True)
    # Heavy data-accumulation phase. In priority mode the pre-prompt path stays
    # narrow so the operator's prompt is out fast; once the prompt is written the
    # SAME process keeps running and accumulates the broad ~1200-name universe
    # (broad OHLCV -> warehouse, plus kova/SEC/earnings sidecars on the broad
    # set). This is data-only — it never re-runs the prompt, LLM advice, or
    # sleeve evaluation. Set RUN_BROAD_ACCUMULATION=0 for a true light-only run
    # (narrow universe, no broad accumulation — the prior priority-mode behavior).
    broad_accumulation = _env_flag("RUN_BROAD_ACCUMULATION", True)

    # Deferred work queue: in LLM-prompt-priority mode, broad/alt-data
    # accumulation that the operator's prompt does not consume is appended here
    # and drained right after the Step 6A prompt checkpoint, so the prompt is
    # not blocked by it. When priority is off the blocks run inline (the queue
    # stays empty) and behavior is unchanged.
    _deferred_after_prompt: list = []

    def _run_deferred_after_prompt():
        while _deferred_after_prompt:
            _job_name, _job = _deferred_after_prompt.pop(0)
            try:
                _job()
            except Exception as _deferred_err:
                log.warning("Deferred post-prompt job %s failed: %s", _job_name, _deferred_err)

    # ── Broad ingestion universe (exp-20260613-023) ───────────────────────────
    # Fundamental/alternative data streams (SEC companyfacts, kova fundamentals,
    # earnings snapshot, FINRA short interest) must attempt the broad ~1200-name
    # universe on every production run so a narrow watchlist sample cannot
    # silently distort or freeze them. Falls back to the trade universe if the
    # feed is unavailable, so there is no regression when the feed is missing.
    try:
        _broad_feed = load_broad_market_candidate_universe()
        _broad_feed_tickers = {str(t).upper() for t in (_broad_feed.get("tickers") or [])}
    except Exception as _broad_exc:  # pragma: no cover - defensive
        _broad_feed_tickers = set()
        log.warning(
            f"Broad ingestion universe unavailable, using trade universe: {_broad_exc}"
        )
    broad_ingest_universe = sorted(_broad_feed_tickers | {str(t).upper() for t in data_universe})
    log.info(
        "Broad ingestion universe: %d tickers (feed=%d, trade=%d)",
        len(broad_ingest_universe),
        len(_broad_feed_tickers),
        len(data_universe),
    )
    prompt_sidecar_universe = data_universe if llm_prompt_priority else broad_ingest_universe
    # Universe the DEFERRED post-prompt jobs accumulate over. In priority mode the
    # pre-prompt refreshes stay narrow (fast prompt) but the deferred drain widens
    # to the broad universe so data still accumulates — unless broad accumulation
    # is switched off (then it stays narrow, i.e. true light-only). In non-priority
    # mode prompt_sidecar_universe is already broad, so this is a no-op there.
    post_prompt_accumulation_universe = (
        broad_ingest_universe
        if (llm_prompt_priority and broad_accumulation)
        else prompt_sidecar_universe
    )
    if llm_prompt_priority and len(prompt_sidecar_universe) < len(broad_ingest_universe):
        log.info(
            "LLM prompt priority: pre-prompt sidecar refreshes limited to %d trade/pilot tickers; "
            "broad accumulation (%s) runs on %d tickers after the prompt.",
            len(prompt_sidecar_universe),
            "on" if broad_accumulation else "off",
            len(post_prompt_accumulation_universe),
        )
    # Options come from a free source that cannot cover the full universe, so
    # rank the broad universe by recent dollar volume and let the per-stream cap
    # take the most-liquid names. Still attempted every run; trade-universe names
    # are always included first.
    options_ingest_tickers = list(data_universe)
    try:
        import sqlite3 as _sqlite3
        from datetime import timedelta as _timedelta

        _cut = (datetime.now() - _timedelta(days=30)).strftime("%Y-%m-%d")
        _wh = _sqlite3.connect(ohlcv_warehouse_path)
        try:
            _ranked = [
                str(row[0]).upper()
                for row in _wh.execute(
                    "SELECT ticker, AVG(close * volume) AS dv FROM ohlcv "
                    "WHERE date >= ? GROUP BY ticker ORDER BY dv DESC",
                    (_cut,),
                )
            ]
        finally:
            _wh.close()
        _broad_set = set(broad_ingest_universe)
        _ranked_in = [t for t in _ranked if t in _broad_set]
        options_ingest_tickers = list(
            dict.fromkeys([str(t).upper() for t in data_universe] + _ranked_in)
        )
        if llm_prompt_priority:
            options_ingest_tickers = list(data_universe)
        log.info(
            "Options ingestion universe ranked by dollar volume: %d candidates",
            len(options_ingest_tickers),
        )
    except Exception as _opt_exc:  # pragma: no cover - defensive
        log.warning(
            f"Options liquidity ranking unavailable, using trade universe: {_opt_exc}"
        )
    ohlcv_warehouse_enabled = not _env_flag(
        "DISABLE_OHLCV_WAREHOUSE_ACCUMULATION",
        False,
    )
    ohlcv_warehouse_update_existing = _env_flag(
        "OHLCV_WAREHOUSE_UPDATE_EXISTING",
        False,
    )
    ohlcv_warehouse_commit_every = OHLCV_WAREHOUSE_COMMIT_EVERY
    ohlcv_warehouse_recorded_tickers = set()
    ohlcv_warehouse_processed_tickers = set()
    ohlcv_warehouse_empty_tickers = set()
    ohlcv_warehouse_touched_tickers = set()
    ohlcv_warehouse_summary = {
        "status": "enabled" if ohlcv_warehouse_enabled else "disabled",
        "path": ohlcv_warehouse_path,
        "update_existing": ohlcv_warehouse_update_existing,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_existing": 0,
        "skipped_rows": 0,
        "processed_ticker_count": 0,
        "empty_ticker_count": 0,
        "touched_ticker_count": 0,
        "phases": [],
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }

    def _accumulate_ohlcv_warehouse(frames_by_ticker, phase):
        if not ohlcv_warehouse_enabled:
            return
        frames_by_ticker = dict(frames_by_ticker or {})
        if not frames_by_ticker:
            return
        try:
            summary = upsert_ohlcv_frames(
                ohlcv_warehouse_path,
                frames_by_ticker,
                source=f"run.py:{phase}",
                provider="yfinance",
                update_existing=ohlcv_warehouse_update_existing,
                commit_every=ohlcv_warehouse_commit_every,
            )
        except Exception as e:
            log.warning("OHLCV warehouse accumulation failed during %s: %s", phase, e)
            ohlcv_warehouse_summary["status"] = "failed"
            ohlcv_warehouse_summary.setdefault("errors", []).append(
                {"phase": phase, "error": str(e)}
            )
            return

        processed = set(summary.get("processed_tickers") or [])
        empty = set(summary.get("empty_tickers") or [])
        touched = set(summary.get("touched_tickers") or [])
        ohlcv_warehouse_recorded_tickers.update(processed | empty)
        ohlcv_warehouse_processed_tickers.update(processed)
        ohlcv_warehouse_empty_tickers.update(empty)
        ohlcv_warehouse_touched_tickers.update(touched)
        for key in (
            "inserted",
            "updated",
            "unchanged",
            "skipped_existing",
            "skipped_rows",
        ):
            ohlcv_warehouse_summary[key] += int(summary.get(key) or 0)
        ohlcv_warehouse_summary["processed_ticker_count"] = len(
            ohlcv_warehouse_processed_tickers
        )
        ohlcv_warehouse_summary["empty_ticker_count"] = len(
            ohlcv_warehouse_empty_tickers
        )
        ohlcv_warehouse_summary["touched_ticker_count"] = len(
            ohlcv_warehouse_touched_tickers
        )
        if ohlcv_warehouse_summary.get("errors"):
            ohlcv_warehouse_summary["status"] = "partial_failed"
        else:
            ohlcv_warehouse_summary["status"] = (
                "updated"
                if (
                    ohlcv_warehouse_summary["inserted"]
                    or ohlcv_warehouse_summary["updated"]
                )
                else "no_new_rows"
            )
        ohlcv_warehouse_summary["phases"].append(
            {
                "phase": phase,
                "ticker_count": summary.get("ticker_count"),
                "processed_ticker_count": summary.get("processed_ticker_count"),
                "empty_ticker_count": summary.get("empty_ticker_count"),
                "inserted": summary.get("inserted"),
                "updated": summary.get("updated"),
                "skipped_existing": summary.get("skipped_existing"),
                "skipped_rows": summary.get("skipped_rows"),
                "touched_ticker_count": summary.get("touched_ticker_count"),
                "processed_tickers_sample": sorted(processed)[:20],
                "touched_tickers_sample": sorted(touched)[:20],
            }
        )
        log.info(
            "OHLCV warehouse %s: tickers=%s inserted=%s updated=%s existing=%s skipped_rows=%s",
            phase,
            summary.get("processed_ticker_count"),
            summary.get("inserted"),
            summary.get("updated"),
            summary.get("skipped_existing"),
            summary.get("skipped_rows"),
        )

    ohlcv_cache = {}
    earnings_cache = {}

    def _cached_ohlcv(ticker):
        key = str(ticker).upper()
        if key not in ohlcv_cache:
            ohlcv_cache[key] = get_ohlcv(key)
        return ohlcv_cache.get(key)

    def _cached_earnings(ticker):
        key = str(ticker).upper()
        if key not in earnings_cache:
            earnings_cache[key] = get_earnings_data(key)
        return earnings_cache.get(key)

    try:
        non_ohlcv_catchup_summary = catch_up_missing_non_ohlcv(
            as_of=today_iso,
            universe=data_universe,
            logger_obj=log,
        )
        if non_ohlcv_catchup_summary.get("status") != "skipped":
            log.info(
                "Non-OHLCV catch-up: status=%s days=%s generated=%s existing=%s failed=%s",
                non_ohlcv_catchup_summary.get("status"),
                non_ohlcv_catchup_summary.get("days_total"),
                non_ohlcv_catchup_summary.get("days_generated"),
                non_ohlcv_catchup_summary.get("days_recorded_existing"),
                non_ohlcv_catchup_summary.get("days_failed"),
            )
    except Exception as e:
        log.warning(f"Non-OHLCV catch-up unavailable: {e}")
        non_ohlcv_catchup_summary = {
            "status": "failed",
            "error": str(e),
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }

    # ── Step 1.6: Macro event calendar refresh (append-only data update) ─────
    # Accumulates future NFP/CPI/FOMC dates from official schedules into
    # data/reference/macro_events_overlay.json (weekly throttle). Never edits
    # hand-verified seed history; total failure changes nothing and the
    # intraday report's calendar audit remains the alarm.
    try:
        from macro_events_refresh import refresh_macro_events_overlay
        _macro_cal = refresh_macro_events_overlay()
        if _macro_cal.get("added"):
            log.info(
                "Macro event calendar: appended %s future date(s) from "
                "official schedules", _macro_cal["added"],
            )
        elif _macro_cal.get("status") == "failed":
            log.warning(
                "Macro event calendar refresh failed (will retry next run): %s",
                _macro_cal.get("errors"),
            )
    except Exception as e:
        log.warning(f"Macro event calendar refresh skipped: {e}")

    # exp-20260612-009: keep unowned reference caches fresh from the daily path.
    # Sector map rolls a stale slice (caps the yfinance burst); SEC company
    # tickers refresh weekly. Env opt-outs: REFERENCE_CACHE_REFRESH_DISABLED,
    # SECTOR_CACHE_REFRESH_DISABLED, SEC_TICKER_REFRESH_DISABLED.
    # The sector-map yfinance .info refresh is the slowest single pre-prompt call
    # and nothing on the prompt path reads its output (broad sleeves + universe
    # feed consume it after the Step 6A checkpoint; enrich_signals uses the static
    # risk_engine.SECTOR_MAP, not this cache), so defer it in priority mode.
    _reference_cache_job = functools.partial(
        _refresh_reference_caches_step, post_prompt_accumulation_universe
    )
    if llm_prompt_priority:
        _deferred_after_prompt.append(("reference_cache_refresh", _reference_cache_job))
    else:
        _reference_cache_job()

    # ── Step 2: Market Regime ─────────────────────────────────────────────────
    market_regime = _step2_market_regime()

    # ── Step 3: OHLCV + Earnings (batched OHLCV + cached fallbacks) ─────────
    _print_section("STEP 3 — OHLCV + earnings data")
    ohlcv_dict    = get_ohlcv_many(data_universe)
    earnings_dict = {}
    for ticker in data_universe:
        ohlcv_cache[str(ticker).upper()] = ohlcv_dict.get(ticker)
        earnings_dict[ticker] = _cached_earnings(ticker)
    spy_ohlcv = ohlcv_dict.get("SPY")
    if spy_ohlcv is None:
        spy_ohlcv = _cached_ohlcv("SPY")
    primary_warehouse_frames = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        primary_warehouse_frames["SPY"] = spy_ohlcv
    _accumulate_ohlcv_warehouse(primary_warehouse_frames, "primary_batch")
    option_underlying_prices = {}
    for ticker, ohlcv in ohlcv_dict.items():
        if ohlcv is None or ohlcv.empty:
            continue
        try:
            raw_close = ohlcv["Close"].iloc[-1]
            option_underlying_prices[ticker] = float(
                raw_close.item() if hasattr(raw_close, "item") else raw_close
            )
        except Exception:
            pass

    # P-ERN: persist today's earnings snapshot so backtester can reconstruct
    # eps_estimate and avg_historical_surprise_pct for earnings_event_long.
    # Without this snapshot, the backtester uses None for both fields, capping
    # C-strategy confidence at 0.83 and preventing quality filtering.
    persist_earnings_snapshot(earnings_dict, as_of=datetime.now(), logger=log)

    # NOTE: broad-universe OHLCV warehouse accumulation is NOT done here. It is
    # already handled downstream by refresh_warehouse_ohlcv() (exp-20260612-002,
    # gated by BROAD_UNIVERSE_REFRESH_DISABLED), which is staleness-aware: it only
    # fetches stale tickers and only their missing day-window. RUN_BROAD_ACCUMULATION
    # below widens the deferred *sidecars* (earnings / kova / reference cache) to the
    # broad universe; it deliberately does not re-download broad OHLCV.

    # Broad-universe earnings merge (exp-20260613-023): attempt yfinance earnings
    # for the broad universe on every run so coverage is not capped at the
    # ~58-name watchlist. Additive merge — core watchlist rows are never
    # overwritten; per-ticker failures are tolerated and never abort the run.
    # The operator prompt never reads this merge (core earnings are persisted
    # above and signals use the in-memory core earnings), so in priority mode it
    # is deferred until after the Step 6A prompt checkpoint.
    _broad_earnings_job = functools.partial(
        _broad_earnings_merge_step, post_prompt_accumulation_universe
    )
    if llm_prompt_priority:
        _deferred_after_prompt.append(("broad_earnings_merge", _broad_earnings_job))
    else:
        _broad_earnings_job()
    try:
        estimate_revision_summary = persist_estimate_revision_ledger(
            as_of=today_iso,
            data_dir="data",
            output_dir="data/non_ohlcv",
            # Current-day quant_signals are written later in the pipeline.
            # Keep run.py's daily artifact free of stale same-day matches.
            match_daily_signals=False,
        )
        log.info(
            "Estimate revision ledger: rows=%s usable=%s up=%s down=%s",
            estimate_revision_summary.get("row_count"),
            estimate_revision_summary.get("estimate_revision_usable_rows"),
            estimate_revision_summary.get("up_revision_rows"),
            estimate_revision_summary.get("down_revision_rows"),
        )
    except Exception as e:
        log.warning(f"Estimate revision ledger unavailable: {e}")
        estimate_revision_summary = {
            "status": "failed",
            "as_of_date": today_iso,
            "error": str(e),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": True,
                "replay_only": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
                "scope": "default_off_forward_estimate_revision_data_ledger_failed",
            },
        }

    try:
        non_ohlcv_daily_summary = ensure_non_ohlcv_coverage(
            start=today_iso,
            end=today_iso,
            profile="daily",
            only_missing=False,
            universe=data_universe,
            refresh_earnings=False,
            refresh_options=True,
            options_tickers=options_ingest_tickers,
            option_underlying_prices=option_underlying_prices,
            options_max_expirations=2,
            options_max_strikes_per_side=12,
            options_max_tickers=OPTIONS_MAX_TICKERS,
            logger_obj=log,
        )
        non_ohlcv_snapshot = (
            non_ohlcv_daily_summary.get("daily_snapshots", {}).get(today_iso)
            or persist_daily_non_ohlcv_snapshots(
                as_of=today_iso,
                logger=log,
                refresh_sec_submissions=False,
                refresh_form4_submissions=False,
            )
        )
        non_ohlcv_snapshot["coverage_manifest"] = {
            "daily_summary": {
                key: non_ohlcv_daily_summary.get(key)
                for key in (
                    "profile",
                    "days_total",
                    "days_generated",
                    "days_recorded_existing",
                    "days_failed",
                    "errors",
                )
            },
            "catchup_summary": {
                key: non_ohlcv_catchup_summary.get(key)
                for key in (
                    "status",
                    "days_total",
                    "days_generated",
                    "days_recorded_existing",
                    "days_failed",
                    "errors",
                    "latest_complete_trade_date_before",
                )
            },
        }
    except Exception as e:
        log.warning(f"Daily non-OHLCV snapshot unavailable: {e}")
        non_ohlcv_snapshot = {
            "status": "failed",
            "asof_date": today_iso,
            "error": str(e),
            "paths": {
                "form4_transactions": f"data/non_ohlcv/form4_transactions_{today}.jsonl",
                "sec_filing_events": f"data/non_ohlcv/sec_filing_events_{today}.jsonl",
                "sec_filing_text": f"data/non_ohlcv/sec_filing_text_{today}.jsonl",
            },
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
            "coverage_manifest": {
                "catchup_summary": non_ohlcv_catchup_summary,
                "daily_error": str(e),
            },
        }

    # ── Step 4: Feature Layer ─────────────────────────────────────────────────
    _print_section("STEP 4 — Feature layer")

    # Kova sidecar (companyfacts SEC refresh + rs_proxy broad warehouse seed) is
    # network-heavy and the operator prompt never reads its output — the
    # consumers (fundamental_growth_rs / consensus sleeves, non_ohlcv_snapshot
    # persist at 1957+) all run after the Step 6A checkpoint. So in priority mode
    # it is deferred until the prompt is out. non_ohlcv_snapshot is the same dict
    # the deferred job mutates, drained before its first reader.
    _kova_job = functools.partial(
        _kova_sidecar_step,
        universe=post_prompt_accumulation_universe,
        today_iso=today_iso,
        ohlcv_dict=ohlcv_dict,
        spy_ohlcv=spy_ohlcv,
        ohlcv_warehouse_enabled=ohlcv_warehouse_enabled,
        ohlcv_warehouse_path=ohlcv_warehouse_path,
        non_ohlcv_snapshot=non_ohlcv_snapshot,
    )
    if llm_prompt_priority:
        _deferred_after_prompt.append(("kova_sidecar", _kova_job))
    else:
        _kova_job()

    non_ohlcv_snapshot["estimate_revision_ledger"] = estimate_revision_summary
    features_dict = _compute_feature_layer(data_universe, ohlcv_dict, earnings_dict)
    portfolio_value = _resolve_live_portfolio_value(
        open_positions, features_dict, portfolio_value, _stored_pv
    )

    # ── Step 5: Position context (exit signals for held tickers) ─────────────
    _print_section("STEP 5 — Position context")
    held_positions_by_ticker = positions_by_ticker(open_positions, positive_only=True)

    # Build trend_signals dict with key names that llm_advisor.build_prompt() expects:
    #   breakout_20d → breakout,  breakdown_20d → breakdown,
    #   high_20d     → 20d_high,  low_20d       → 20d_low
    trend_signals_signals = {}
    for ticker, f in features_dict.items():
        if f is None:
            continue
        sig = {
            "close":            f["close"],
            "daily_high":       f.get("daily_high"),
            "20d_high":         f["high_20d"],
            "20d_low":          f["low_20d"],
            "breakout":         f["breakout_20d"],
            "breakdown":        f["breakdown_20d"],
            "atr":              f.get("atr"),
            # Bonus keys for LLM context (not required by build_prompt, but useful)
            "above_200ma":      f.get("above_200ma"),
            "momentum_10d_pct": f.get("momentum_10d_pct"),
            "volume_spike":     f.get("volume_spike"),
            "trend_score":      f.get("trend_score"),
            "days_to_earnings": f.get("days_to_earnings"),
        }
        # Compute prev_close for daily_return_pct (post-earnings gap detection).
        # Required by LLM rules: "daily_return_pct > +8% → REDUCE 50%", "< -5% → EXIT".
        # Without this the LLM cannot distinguish a single-day gap from cumulative PnL.
        ohlcv = ohlcv_dict.get(ticker)
        prev_close = None
        if ohlcv is not None and len(ohlcv) >= 2:
            try:
                prev_val   = ohlcv['Close'].iloc[-2]
                prev_close = float(prev_val.item() if hasattr(prev_val, 'item') else prev_val)
            except Exception:
                pass

        # Compute high_since_entry for accurate trailing stop high-water mark.
        # Bug: without this, trailing stop uses 20d high, missing peaks from >20 days ago.
        # Example: stock peaked at $150 (35d ago), high_20d=$142 → trailing=$130.64 (wrong);
        # high_since_entry=$150 → trailing=$138.00 (correct, would have triggered).
        high_since_entry = None
        if open_positions and ohlcv is not None:
            pos = held_positions_by_ticker.get(str(ticker).upper())
            entry_date_str = pos.get('entry_date') if pos else None
            if entry_date_str:
                try:
                    entry_dt    = pd.Timestamp(entry_date_str)
                    data_since  = ohlcv[ohlcv.index >= entry_dt]
                    if not data_since.empty:
                        raw_high         = data_since['High'].max()
                        high_since_entry = float(
                            raw_high.item() if hasattr(raw_high, 'item') else raw_high
                        )
                except Exception:
                    pass

        # Add exit-level position context for held tickers
        pos_ctx = compute_position_context(
            ticker, f["close"], open_positions,
            atr=f.get("atr"),
            high_20d=f.get("high_20d"),
            high_since_entry=high_since_entry,
            prev_close=prev_close,
            daily_high=f.get("daily_high"),
        )
        if pos_ctx:
            sig["position"] = pos_ctx
            log.info(f"{ticker}: position context added "
                     f"(urgency={pos_ctx['exit_signals']['high_urgency']})")

        trend_signals_signals[ticker] = sig

    trend_signals_dict = {
        "generated_at": datetime.now().isoformat(),
        "asof_date":    datetime.now().strftime("%Y-%m-%d"),
        "universe":     universe,
        "pilot_universe": pilot_universe,
        "data_universe": data_universe,
        "market_regime": market_regime,
        "ohlcv_warehouse": ohlcv_warehouse_summary,
        "signals":      trend_signals_signals,
    }

    # Save trend signals JSON (backward-compatible output)
    # quant_signals will be attached after Step 6 enrichment
    trend_output = str(daily_artifact_path("trend_signals", today))
    save_trend_signals(trend_signals_dict, trend_output)

    # Exit lifecycle shadow log (read-only attribution, exp-20260531-020)
    try:
        from exit_lifecycle_shadow_log import (
            build_exit_lifecycle_snapshot,
            persist_exit_lifecycle_snapshot,
        )
        _exit_snapshot = build_exit_lifecycle_snapshot(
            as_of=today_iso,
            trend_signals_signals=trend_signals_signals,
            open_positions=open_positions,
        )
        _exit_log_path = persist_exit_lifecycle_snapshot(_exit_snapshot)
        if _exit_snapshot.get("advisory_event_count", 0) > 0:
            log.info(
                "Exit lifecycle shadow log: %d positions, %d advisory events -> %s",
                _exit_snapshot.get("position_count", 0),
                _exit_snapshot.get("advisory_event_count", 0),
                _exit_log_path,
            )
    except Exception as _exit_exc:
        log.warning("Exit lifecycle shadow log unavailable: %s", _exit_exc)

    # ── Step 6: Quant signals ─────────────────────────────────────────────────
    _print_section("STEP 6 — Quant signals")

    # Build market_context: regime + RS filter + pct_from_ma for BEAR tier detection.
    spy_10d         = market_regime.get("indices", {}).get("SPY", {}).get("momentum_10d_pct")
    qqq_10d         = market_regime.get("indices", {}).get("QQQ", {}).get("momentum_10d_pct")
    spy_pct_from_ma = market_regime.get("indices", {}).get("SPY", {}).get("pct_from_ma")
    qqq_pct_from_ma = market_regime.get("indices", {}).get("QQQ", {}).get("pct_from_ma")
    market_context  = {
        "market_regime":   market_regime.get("regime", "UNKNOWN"),
        "spy_10d_return":  spy_10d,
        "qqq_10d_return":  qqq_10d,
        "spy_pct_from_ma": spy_pct_from_ma,
        "qqq_pct_from_ma": qqq_pct_from_ma,
    }
    if spy_10d is not None:
        log.info(f"SPY 10d return: {spy_10d*100:.2f}% (RS filter active)")
    if spy_pct_from_ma is not None and qqq_pct_from_ma is not None:
        log.info(f"SPY vs 200MA: {spy_pct_from_ma*100:+.2f}%   "
                 f"QQQ vs 200MA: {qqq_pct_from_ma*100:+.2f}%")

    core_features_dict = {
        ticker: features_dict.get(ticker)
        for ticker in universe
        if ticker in features_dict
    }
    pilot_features_dict = {
        ticker: features_dict.get(ticker)
        for ticker in pilot_universe
        if ticker in features_dict
    }

    signals = generate_signals(
        core_features_dict,
        market_context=market_context,
        enabled_strategies=ENABLED_STRATEGIES,
        breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    )
    if BREAKOUT_RANK_BY_52W_HIGH:
        signals = rank_signals_for_allocation(signals)
    exit_profile = compute_regime_exit_profile(market_context, base_target_mult=ATR_TARGET_MULT)
    atr_target_mult = exit_profile["target_mult"] if REGIME_AWARE_EXIT else ATR_TARGET_MULT
    if REGIME_AWARE_EXIT:
        log.info(
            "Regime-aware exit active: "
            f"bucket={exit_profile['bucket']} score={exit_profile['score']} "
            f"target_mult={atr_target_mult:.2f}"
        )
    signals = enrich_signals(signals, features_dict, atr_target_mult=atr_target_mult)
    if REGIME_AWARE_EXIT:
        for s in signals:
            s["target_mult_used"] = exit_profile["target_mult"]
            s["regime_exit_bucket"] = exit_profile["bucket"]
            s["regime_exit_score"] = exit_profile["score"]

    signals, entry_filter_audit = filter_entry_signal_candidates(
        signals,
        open_positions=open_positions,
        market_regime=market_regime.get("regime", "").upper(),
        spy_pct_from_ma=spy_pct_from_ma,
        qqq_pct_from_ma=qqq_pct_from_ma,
    )
    if entry_filter_audit["already_held_dropped"]:
        log.info(
            "Already-held filter: dropped %s",
            [s["ticker"] for s in entry_filter_audit["already_held_dropped"]],
        )
    for s in entry_filter_audit["sector_cap_dropped"]:
        log.warning(
            "%s: dropped by sector cap for sector '%s'",
            s.get("ticker"),
            s.get("sector", "Unknown"),
        )
    if entry_filter_audit["bear_shallow_active"]:
        log.info(
            "BEAR_SHALLOW filter: %d -> %d signals",
            entry_filter_audit["signals_before_entry_filters"],
            entry_filter_audit["signals_after_entry_filters"],
        )
    # Surface any signals dropped during enrichment (ATR missing, R:R too low)
    from risk_engine import last_dropped_signals
    if last_dropped_signals:
        log.warning(
            f"Dropped {len(last_dropped_signals)} signal(s) during enrichment: "
            + "; ".join(f"{d['ticker']} — {d['reason']}" for d in last_dropped_signals)
        )

    _regime_str = market_regime.get("regime", "").upper()

    log.info(f"Signals generated: {len(signals)}")
    qqq_ohlcv = ohlcv_dict.get("QQQ")
    if qqq_ohlcv is None:
        qqq_ohlcv = _cached_ohlcv("QQQ")
    try:
        vix_ohlcv = _cached_ohlcv("^VIX")
    except Exception as e:
        log.warning("VIX OHLCV unavailable for market-state context: %s", e)
        vix_ohlcv = None
    market_state_context = build_readonly_market_state_context(
        market_context,
        ohlcv_by_ticker={
            "SPY": spy_ohlcv,
            "QQQ": qqq_ohlcv,
        },
        vix_ohlcv=vix_ohlcv,
    )
    log.info(
        "Market-state context: spy20=%s qqq20=%s qqq-spy20=%s vix=%s vix10d=%s",
        market_state_context.get("spy_20d_return"),
        market_state_context.get("qqq_20d_return"),
        market_state_context.get("qqq_minus_spy_ret20"),
        market_state_context.get("vix"),
        market_state_context.get("vix_10d_change"),
    )
    market_state_snapshot = build_market_state_snapshot(
        market_context=market_state_context,
        signals=signals,
        source="production_daily_quant",
    )
    _state_regime = (
        market_state_snapshot.get("market_regime_report") or {}
    ).get("regime")
    _state_sentiment = (
        market_state_snapshot.get("sentiment_surface") or {}
    ).get("sentiment")
    log.info(
        "Market-state snapshot: regime_engine=%s sentiment=%s",
        _state_regime,
        _state_sentiment,
    )

    pilot_signals = []
    pilot_entry_filter_audit = {
        "signals_before_entry_filters": 0,
        "signals_after_entry_filters": 0,
        "already_held_dropped": [],
        "sector_cap_dropped": [],
        "bear_shallow_dropped": [],
    }
    if pilot_features_dict:
        pilot_signals = generate_signals(
            pilot_features_dict,
            market_context=market_context,
            enabled_strategies=ENABLED_STRATEGIES,
            breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
        )
        if BREAKOUT_RANK_BY_52W_HIGH:
            pilot_signals = rank_signals_for_allocation(pilot_signals)
        pilot_signals = enrich_signals(
            pilot_signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        if REGIME_AWARE_EXIT:
            for s in pilot_signals:
                s["target_mult_used"] = exit_profile["target_mult"]
                s["regime_exit_bucket"] = exit_profile["bucket"]
                s["regime_exit_score"] = exit_profile["score"]
        pilot_signals = mark_pilot_signals(
            pilot_signals,
            pilot_records,
            metadata=pilot_metadata,
        )
        pilot_signals, pilot_entry_filter_audit = filter_entry_signal_candidates(
            pilot_signals,
            open_positions=open_positions,
            market_regime=market_regime.get("regime", "").upper(),
            spy_pct_from_ma=spy_pct_from_ma,
            qqq_pct_from_ma=qqq_pct_from_ma,
        )
        log.info(f"Pilot sleeve signals generated: {len(pilot_signals)}")

    _trade_risk_pct = risk_pct_for_market_state(
        _regime_str,
        spy_pct_from_ma=spy_pct_from_ma,
        qqq_pct_from_ma=qqq_pct_from_ma,
    )
    if _trade_risk_pct is not None:
        log.info("Regime-adjusted position sizing: %.2f%% risk per trade", _trade_risk_pct * 100)

    # Current prices for heat + sizing
    current_prices = {
        t: f["close"] for t, f in features_dict.items() if f and f.get("close")
    }
    current_open_prices = {}
    for ticker, ohlcv in ohlcv_dict.items():
        try:
            raw_open = ohlcv["Open"].iloc[-1]
            current_open_prices[ticker] = float(
                raw_open.item() if hasattr(raw_open, "item") else raw_open
            )
        except Exception:
            pass
    current_price_dates = latest_ohlcv_dates(ohlcv_dict)
    current_open_price_dates = dict(current_price_dates)

    portfolio_heat = None
    heat_blocked_signals = []
    heat_blocked_pilot_signals = []
    if open_positions and portfolio_value:
        # Pass features_dict so heat uses effective stops (ATR/trailing) not just avg_cost stop
        portfolio_heat = compute_portfolio_heat(
            open_positions, current_prices, portfolio_value,
            features_dict=features_dict
        )
        log.info(portfolio_heat["heat_note"])
        if portfolio_heat["can_add_new_positions"] and portfolio_value:
            signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)
            pilot_signals = size_signals(
                pilot_signals,
                portfolio_value,
                risk_pct=_trade_risk_pct,
            )
        else:
            heat_blocked_signals = signals
            heat_blocked_pilot_signals = pilot_signals
            signals = []
            pilot_signals = []
    elif portfolio_value:
        signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)
        pilot_signals = size_signals(
            pilot_signals,
            portfolio_value,
            risk_pct=_trade_risk_pct,
        )

    advisory_entry_signals = list(signals or [])
    live_heat_blocked = bool(heat_blocked_signals)
    if live_heat_blocked:
        advisory_entry_signals = (
            size_signals(
                deepcopy(heat_blocked_signals),
                portfolio_value,
                risk_pct=_trade_risk_pct,
            )
            if portfolio_value
            else deepcopy(heat_blocked_signals)
        )

    strategy_active_positions = count_core_strategy_positions(open_positions)
    total_accounting_signals, total_accounting_entry_execution_plan = plan_entry_candidates(
        deepcopy(advisory_entry_signals),
        open_positions,
        market_context=market_context,
        active_positions_scope="total_account_positive_positions_shadow",
    )
    strategy_accounting_signals, strategy_entry_execution_plan = plan_entry_candidates(
        deepcopy(advisory_entry_signals),
        open_positions,
        market_context=market_context,
        active_positions_count=strategy_active_positions,
        active_positions_scope="core_strategy_slot_accounting",
    )
    signals, entry_execution_plan = plan_entry_candidates(
        signals,
        open_positions,
        market_context=market_context,
        active_positions_count=strategy_active_positions,
        active_positions_scope="core_strategy_slot_accounting",
    )
    entry_candidate_review = build_entry_candidate_review(
        advisory_entry_signals,
        live_selected_signals=signals,
        live_entry_execution_plan=entry_execution_plan,
        strategy_selected_signals=strategy_accounting_signals,
        strategy_entry_execution_plan=strategy_entry_execution_plan,
        total_account_selected_signals=total_accounting_signals,
        total_account_entry_execution_plan=total_accounting_entry_execution_plan,
        open_positions=open_positions,
        live_heat_blocked=live_heat_blocked,
    )
    pilot_signals = apply_pilot_sizing_policy(pilot_signals, pilot_records)
    pilot_signals, pilot_entry_execution_plan = select_pilot_entry_candidates(
        pilot_signals,
        pilot_records,
        open_positions=open_positions,
        market_context=market_context,
    )
    pilot_decision_snapshots = build_counterfactual_snapshots(
        pilot_signals,
        core_signals=signals,
        pilot_alternative_signals=pilot_entry_execution_plan.get(
            "pilot_slot_sliced_signals",
            [],
        ),
        as_of=datetime.now().date().isoformat(),
        market_context=market_context,
        portfolio_heat=portfolio_heat,
        metadata=pilot_metadata,
    )
    pilot_decision_hashes = []
    if pilot_decision_snapshots:
        try:
            pilot_decision_hashes = append_pilot_decision_snapshots(
                pilot_decision_snapshots
            )
            for sig, snapshot, decision_hash in zip(
                pilot_signals,
                pilot_decision_snapshots,
                pilot_decision_hashes,
            ):
                sig.setdefault("pilot_sleeve", {})["decision_id"] = snapshot["decision_id"]
                sig.setdefault("pilot_sleeve", {})["decision_hash"] = decision_hash
            log.info(
                "Pilot sleeve pre-trade snapshots logged: %s",
                pilot_decision_hashes,
            )
        except Exception as e:
            log.error(f"Pilot sleeve decision snapshot logging failed: {e}")
    if entry_execution_plan["deferred_breakout_signals"]:
        log.info(
            "Scarce-slot routing deferred %d breakout signal(s)",
            len(entry_execution_plan["deferred_breakout_signals"]),
        )
    if entry_execution_plan["slot_sliced_signals"]:
        log.info(
            "Position slots kept %d/%d signal(s)",
            entry_execution_plan["signals_after_entry_plan"],
            entry_execution_plan["signals_before_entry_plan"],
        )
    if entry_candidate_review.get("operator_review_count"):
        log.info(
            "Operator review: %d candidate(s) are backtest-accounting buys but live-accounting deferred",
            entry_candidate_review["operator_review_count"],
        )

    try:
        space_official_observation_tickers = set(
            space_catalyst_observation_tickers(space_catalyst_shadow)
        )
        space_observation_tickers = space_catalyst_observation_feature_tickers(
            space_catalyst_shadow
        )
        space_observation_features = {}
        for ticker in space_observation_tickers:
            if features_dict.get(ticker):
                space_observation_features[ticker] = features_dict[ticker]
                continue
            try:
                ticker_ohlcv = _cached_ohlcv(ticker)
                ticker_earnings = _cached_earnings(ticker)
                ticker_features = compute_features(ticker, ticker_ohlcv, ticker_earnings)
                if ticker_features:
                    space_observation_features[ticker] = ticker_features
            except Exception as ticker_error:
                log.warning(
                    "Space catalyst observation data unavailable for %s: %s",
                    ticker,
                    ticker_error,
                )

        space_observation_signals = []
        space_observation_raw_count = 0
        space_observation_enriched_count = 0
        space_observation_filter_audit = {}
        space_signal_features = {
            ticker: features
            for ticker, features in space_observation_features.items()
            if ticker in space_official_observation_tickers
        }
        if space_signal_features:
            space_observation_feature_context = {
                **features_dict,
                **space_observation_features,
            }
            space_observation_signals = generate_signals(
                space_signal_features,
                market_context=market_context,
                enabled_strategies=ENABLED_STRATEGIES,
                breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
            )
            space_observation_raw_count = len(space_observation_signals)
            if BREAKOUT_RANK_BY_52W_HIGH:
                space_observation_signals = rank_signals_for_allocation(
                    space_observation_signals
                )
            _pre_space_dropped_signals = list(last_dropped_signals)
            space_observation_signals = enrich_signals(
                space_observation_signals,
                space_observation_feature_context,
                atr_target_mult=atr_target_mult,
            )
            space_observation_enriched_count = len(space_observation_signals)
            last_dropped_signals.clear()
            last_dropped_signals.extend(_pre_space_dropped_signals)
            if REGIME_AWARE_EXIT:
                for s in space_observation_signals:
                    s["target_mult_used"] = exit_profile["target_mult"]
                    s["regime_exit_bucket"] = exit_profile["bucket"]
                    s["regime_exit_score"] = exit_profile["score"]
            space_observation_signals, space_observation_filter_audit = (
                filter_entry_signal_candidates(
                    space_observation_signals,
                    open_positions=open_positions,
                    market_regime=market_regime.get("regime", "").upper(),
                    spy_pct_from_ma=spy_pct_from_ma,
                    qqq_pct_from_ma=qqq_pct_from_ma,
                )
            )
            if portfolio_value and (
                not portfolio_heat
                or portfolio_heat.get("can_add_new_positions", True)
            ):
                space_observation_signals = size_signals(
                    space_observation_signals,
                    portfolio_value,
                    risk_pct=_trade_risk_pct,
                )

        space_catalyst_observation_slot = persist_space_catalyst_observation_slot(
            build_space_catalyst_observation_slot(
                as_of=today_iso,
                candidate_signals=space_observation_signals,
                features_by_ticker={**features_dict, **space_observation_features},
                space_catalyst_shadow=space_catalyst_shadow,
                core_signals=signals,
                entry_execution_plan=entry_execution_plan,
                portfolio_heat=portfolio_heat,
                entry_filter_audit=space_observation_filter_audit,
                raw_signal_count=space_observation_raw_count,
                enriched_signal_count=space_observation_enriched_count,
                space_forward_replacement_profiles=(
                    space_catalyst_forward_replacement_positive_profiles(
                        included_tickers=space_official_observation_tickers
                    )
                ),
            )
        )
        if space_catalyst_observation_slot.get("candidate_count", 0) > 0:
            persistence = space_catalyst_observation_slot.get("persistence") or {}
            log.info(
                "Space catalyst observation slot: candidates=%d selected=%d appended=%d",
                space_catalyst_observation_slot.get("candidate_count", 0),
                space_catalyst_observation_slot.get("selected_count", 0),
                persistence.get("appended_count", 0),
            )
    except Exception as e:
        log.warning(f"Space catalyst observation slot unavailable: {e}")
        space_catalyst_observation_slot = empty_space_catalyst_observation_slot(
            today_iso,
            "space_catalyst_observation_slot_build_failed",
        )

    try:
        platform_rs20_watch = persist_platform_rs20_forward_watch(
            build_platform_rs20_forward_watch(
                as_of=today_iso,
                entry_execution_plan=entry_execution_plan,
                ohlcv_by_ticker={**ohlcv_dict, "SPY": spy_ohlcv},
                features_by_ticker=features_dict,
                earnings_by_ticker=earnings_dict,
            )
        )
        if platform_rs20_watch.get("candidate_count", 0) > 0:
            persistence = platform_rs20_watch.get("persistence") or {}
            log.info(
                "Platform RS20 no-gap watch: candidates=%d appended=%d ledger_rows=%d",
                platform_rs20_watch.get("candidate_count", 0),
                persistence.get("appended_count", 0),
                persistence.get("ledger_row_count", 0),
            )
    except Exception as e:
        log.warning(f"Platform RS20 no-gap watch unavailable: {e}")
        platform_rs20_watch = empty_platform_rs20_forward_watch(
            today_iso,
            "platform_rs20_watch_build_failed",
        )

    addon_ohlcv_dict = dict(ohlcv_dict)
    addon_ohlcv_dict["SPY"] = spy_ohlcv
    addon_actions, addon_audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=addon_ohlcv_dict,
        portfolio_value=portfolio_value,
        current_prices=current_prices,
        current_price_dates=current_price_dates,
        portfolio_heat=portfolio_heat,
    )
    if addon_actions:
        log.info(
            "Follow-through add-ons: %s",
            ", ".join(
                f"{a['ticker']} +{a['shares_to_buy']}" for a in addon_actions
            ),
        )

    trade_items = []
    daily_prompt_generated = False
    if llm_prompt_priority:
        # Prompt checkpoint: live-relevant context is ready here.  Default-off
        # paper sleeves and broad-universe observers are useful for research, but
        # they should not delay the operator's daily LLM handoff.
        trend_signals_dict["quant_signals"] = signals
        trend_signals_dict["pilot_quant_signals"] = pilot_signals
        trend_signals_dict["addon_actions"] = addon_actions
        trend_signals_dict["entry_filter_audit"] = entry_filter_audit
        trend_signals_dict["entry_execution_plan"] = entry_execution_plan
        trend_signals_dict["strategy_entry_execution_plan"] = strategy_entry_execution_plan
        trend_signals_dict["entry_candidate_review"] = entry_candidate_review
        trend_signals_dict["market_state_snapshot"] = market_state_snapshot
        trend_signals_dict["pilot_entry_filter_audit"] = pilot_entry_filter_audit
        trend_signals_dict["pilot_entry_execution_plan"] = pilot_entry_execution_plan
        trend_signals_dict["pilot_decision_hashes"] = pilot_decision_hashes
        trend_signals_dict["ohlcv_warehouse"] = ohlcv_warehouse_summary

        _print_section("STEP 6A - Priority news + LLM prompt")
        trade_items = _collect_trade_news(today, universe, pilot_universe)
        daily_prompt_generated = _generate_llm_prompt(
            trade_items,
            open_positions,
            trend_signals_dict,
        )
        # Prompt is out — now drain deferred broad/alt-data accumulation that the
        # operator handoff did not need.
        _run_deferred_after_prompt()

    try:
        low_deployment_etf_overlay = build_low_deployment_etf_overlay_snapshot(
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            open_positions=open_positions,
            portfolio_value=portfolio_value,
        )
        if (
            low_deployment_etf_overlay.get("candidate_count", 0) > 0
            or low_deployment_etf_overlay.get("closed_count_today", 0) > 0
            or low_deployment_etf_overlay.get("closed_position_count", 0) > 0
        ):
            log.info(
                "Low-deployment ETF overlay paper: candidate=%s closed_today=%d pnl=$%s",
                (
                    (low_deployment_etf_overlay.get("candidate") or {}).get("ticker")
                    or "none"
                ),
                low_deployment_etf_overlay.get("closed_count_today", 0),
                low_deployment_etf_overlay.get("realized_pnl_to_date", 0.0),
            )
    except Exception as e:
        log.warning(f"Low-deployment ETF overlay unavailable: {e}")
        low_deployment_etf_overlay = empty_low_deployment_etf_overlay_snapshot(
            today_iso,
            "low_deployment_etf_overlay_build_failed",
        )

    # Peer-earnings-reaction attribution sidecar (read-only, exp-20260531-019)
    try:
        from risk_engine import SECTOR_MAP as _sector_map
        _peer_sidecar = build_peer_earnings_reaction_sidecar(
            signals=signals,
            ohlcv_dict=ohlcv_dict,
            sector_map=_sector_map,
        )
        attach_peer_earnings_reaction_to_signals(signals, _peer_sidecar)
        _peer_seen = sum(
            1 for v in _peer_sidecar.values()
            if v.get("peer_earnings_reaction_seen")
        )
        if _peer_seen:
            log.info(
                "Peer-earnings-reaction sidecar: %d/%d signals with peer reaction",
                _peer_seen,
                len(signals),
            )
    except Exception as _peer_exc:
        log.warning("Peer-earnings-reaction sidecar unavailable: %s", _peer_exc)

    metrics = compute_metrics()
    pilot_attribution = summarize_pilot_competition()
    ai_infra_aggressive_attribution = summarize_pilot_competition(
        sleeve=AI_INFRA_AGGRESSIVE_SLEEVE_NAME
    )
    ai_infra_aggressive_attribution = build_ai_infra_aggressive_attribution(
        pilot_signals=pilot_signals,
        pilot_entry_execution_plan=pilot_entry_execution_plan,
        pilot_attribution=ai_infra_aggressive_attribution,
    )
    if pilot_attribution.get("outcome_records"):
        log.info(
            "Pilot attribution: outcomes=%s direct_pnl=$%s replacement_value=%s pending=%s",
            pilot_attribution.get("outcome_records"),
            pilot_attribution.get("direct_pilot_pnl"),
            pilot_attribution.get("replacement_value"),
            pilot_attribution.get("pending_replacement_outcomes"),
        )

    try:
        space_event_ohlcv = {}
        for ticker in space_catalyst_event_tickers(
            today_iso,
            space_catalyst_shadow=space_catalyst_shadow,
        ):
            if ticker in ohlcv_dict:
                space_event_ohlcv[ticker] = ohlcv_dict[ticker]
                continue
            if ticker == "SPY" and spy_ohlcv is not None:
                space_event_ohlcv[ticker] = spy_ohlcv
                continue
            try:
                space_event_ohlcv[ticker] = _cached_ohlcv(ticker)
            except Exception as ticker_error:
                log.warning(
                    "Space catalyst event OHLCV unavailable for %s: %s",
                    ticker,
                    ticker_error,
                )
        space_catalyst_event_ledger = persist_space_catalyst_event_ledger(
            build_space_catalyst_event_ledger_snapshot(
                as_of=today_iso,
                ohlcv_by_ticker=space_event_ohlcv,
                space_catalyst_shadow=space_catalyst_shadow,
                core_signals=signals,
                entry_execution_plan=entry_execution_plan,
            )
        )
        if space_catalyst_event_ledger.get("active_event_count", 0) > 0:
            persistence = space_catalyst_event_ledger.get("persistence") or {}
            log.info(
                "Space catalyst event ledger: events=%d rows=%d closed_10d=%d appended=%d",
                space_catalyst_event_ledger.get("active_event_count", 0),
                space_catalyst_event_ledger.get("event_row_count", 0),
                space_catalyst_event_ledger.get("closed_decision_count", 0),
                persistence.get("appended_count", 0),
            )
    except Exception as e:
        log.warning(f"Space catalyst event ledger unavailable: {e}")
        space_catalyst_event_ledger = empty_space_catalyst_event_ledger(
            today_iso,
            "space_catalyst_event_ledger_build_failed",
        )

    non_ohlcv_paths = non_ohlcv_snapshot.get("paths") or {}

    try:
        sec_10k_forward_watch = persist_sec_10k_forward_watch(
            build_sec_10k_forward_watch(
                as_of=today_iso,
                source_path=non_ohlcv_paths.get("sec_filing_events"),
                ohlcv_by_ticker=ohlcv_dict,
                current_universe=set(universe) | set(pilot_universe),
                core_signals=signals,
                entry_execution_plan=entry_execution_plan,
            )
        )
        if sec_10k_forward_watch.get("ten_k_event_count", 0) > 0:
            persistence = sec_10k_forward_watch.get("persistence") or {}
            log.info(
                "SEC 10-K liquidity watch: 10-K=%d candidates=%d appended=%d ledger_rows=%d",
                sec_10k_forward_watch.get("ten_k_event_count", 0),
                sec_10k_forward_watch.get("candidate_count", 0),
                persistence.get("appended_count", 0),
                persistence.get("ledger_row_count", 0),
            )
    except Exception as e:
        log.warning(f"SEC 10-K liquidity watch unavailable: {e}")
        sec_10k_forward_watch = empty_sec_10k_forward_watch(
            today_iso,
            "sec_10k_forward_watch_build_failed",
        )

    form4_event_queue = _sleeve(
        lambda: build_forward_queue_from_transactions(
            data_dir="data/non_ohlcv",
            as_of=today_iso,
            core_signals=signals,
            source_path=non_ohlcv_paths.get("form4_transactions"),
        ),
        empty_form4_event_queue,
        "Form 4 forward event",
        "form4_event_queue_build_failed",
        log_metrics=_QUEUE_METRICS, activity_keys=_QUEUE_ACTIVITY, noun="queue",
    )

    form4_event_sleeve = _sleeve(
        lambda: build_form4_event_sleeve_snapshot(
            form4_event_queue=form4_event_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_form4_event_sleeve_snapshot,
        "Form 4 paper event",
        "form4_event_sleeve_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=_EVENT_SLEEVE_ACTIVITY,
    )

    sec_event_queue = _sleeve(
        lambda: build_forward_queue_from_sec_filing_text(
            data_dir="data/non_ohlcv",
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            core_signals=signals,
            source_path=non_ohlcv_paths.get("sec_filing_text"),
        ),
        empty_sec_event_queue,
        "SEC negative-reaction forward event",
        "sec_event_queue_build_failed",
        log_metrics=_QUEUE_METRICS, activity_keys=_QUEUE_ACTIVITY, noun="queue",
    )

    sec_negative_event_sleeve = _sleeve(
        lambda: build_sec_negative_event_sleeve_snapshot(
            sec_event_queue=sec_event_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_sec_negative_event_sleeve_snapshot,
        "SEC negative-reaction paper event",
        "sec_negative_event_sleeve_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=_EVENT_SLEEVE_ACTIVITY,
    )

    sec_governance_event_queue = _sleeve(
        lambda: build_forward_governance_queue_from_sec_filing_text(
            data_dir="data/non_ohlcv",
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            core_signals=signals,
            source_path=non_ohlcv_paths.get("sec_filing_text"),
        ),
        empty_sec_governance_queue,
        "SEC governance/procedural forward event",
        "sec_governance_event_queue_build_failed",
        log_metrics=_QUEUE_METRICS, activity_keys=_QUEUE_ACTIVITY, noun="queue",
    )

    sec_governance_event_sleeve = _sleeve(
        lambda: build_sec_event_sleeve_snapshot(
            sec_event_queue=sec_governance_event_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_sec_event_sleeve_snapshot,
        "SEC governance paper event",
        "sec_governance_event_sleeve_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=_EVENT_SLEEVE_ACTIVITY,
    )

    sec_leadership_event_queue = _sleeve(
        lambda: build_forward_leadership_queue_from_sec_filing_text(
            data_dir="data/non_ohlcv",
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            core_signals=signals,
            source_path=non_ohlcv_paths.get("sec_filing_text"),
        ),
        empty_sec_leadership_queue,
        "SEC leadership-change forward event",
        "sec_leadership_event_queue_build_failed",
        log_metrics=_QUEUE_METRICS, activity_keys=_QUEUE_ACTIVITY, noun="queue",
    )

    sec_leadership_event_sleeve = _sleeve(
        lambda: build_sec_leadership_event_sleeve_snapshot(
            sec_leadership_event_queue=sec_leadership_event_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_sec_leadership_event_sleeve_snapshot,
        "SEC leadership paper event",
        "sec_leadership_event_sleeve_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=_EVENT_SLEEVE_ACTIVITY,
    )

    sec_financial_report_t1_queue = _sleeve(
        lambda: build_forward_financial_report_t1_queue_from_sec_filing_events(
            data_dir="data/non_ohlcv",
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            core_signals=signals,
            source_path=non_ohlcv_paths.get("sec_filing_events"),
            text_source_path=non_ohlcv_paths.get("sec_filing_text"),
        ),
        empty_sec_financial_report_t1_queue,
        "SEC financial-report T+1 drift",
        "sec_financial_report_t1_queue_build_failed",
        log_metrics=_QUEUE_METRICS, activity_keys=_QUEUE_ACTIVITY, noun="queue",
    )

    sec_financial_report_event_sleeve = _sleeve(
        lambda: build_sec_financial_report_event_sleeve_snapshot(
            sec_financial_report_t1_queue=sec_financial_report_t1_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_sec_financial_report_event_sleeve_snapshot,
        "SEC financial-report paper",
        "sec_financial_report_event_sleeve_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=_EVENT_SLEEVE_ACTIVITY,
    )

    try:
        state_surface_queue = build_state_surface_queue(
            as_of=today_iso,
            ohlcv_by_ticker=ohlcv_dict,
            universe=universe,
            core_signals=signals,
        )
    except Exception as e:
        log.warning(f"State-surface queue unavailable: {e}")
        state_surface_queue = empty_state_surface_queue(
            today_iso,
            "state_surface_queue_build_failed",
        )

    event_sleeve_bundle = _sleeve(
        lambda: build_event_sleeve_bundle_snapshot(
            as_of=today_iso,
            form4_event_queue=form4_event_queue,
            sec_negative_event_queue=sec_event_queue,
            sec_governance_event_queue=sec_governance_event_queue,
            state_surface_queue=state_surface_queue,
            form4_event_sleeve=form4_event_sleeve,
            sec_negative_event_sleeve=sec_negative_event_sleeve,
            sec_governance_event_sleeve=sec_governance_event_sleeve,
        ),
        empty_event_sleeve_bundle_snapshot,
        "Event overlay bundle paper attribution",
        "event_sleeve_bundle_build_failed",
        log_metrics=_EVENT_SLEEVE_METRICS,
        activity_keys=("pending_count", "open_position_count", "closed_count_today"),
    )

    state_surface_sleeve = _sleeve(
        lambda: build_state_surface_sleeve_snapshot(
            state_surface_queue=state_surface_queue,
            as_of=today_iso,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_state_surface_sleeve_snapshot,
        "State-surface paper",
        "state_surface_sleeve_build_failed",
        log_metrics=[
            ("candidates", "candidate_count"),
            ("pending", "pending_count"),
            ("open", "open_position_count"),
            ("closed_today", "closed_count_today"),
            ("pnl", "realized_pnl_to_date"),
        ],
    )

    core_misfit_paper_sleeve = _sleeve(
        lambda: build_core_misfit_paper_sleeve_snapshot(
            as_of=today_iso,
            candidate_signals=signals,
            entry_execution_plan=entry_execution_plan,
            open_prices=current_open_prices,
            current_prices=current_prices,
            open_price_dates=current_open_price_dates,
            current_price_dates=current_price_dates,
        ),
        empty_core_misfit_paper_sleeve_snapshot,
        "Core-misfit paper",
        "core_misfit_paper_sleeve_build_failed",
        log_metrics=[
            ("candidates", "candidate_count"),
            ("pending", "pending_count"),
            ("open", "open_position_count"),
            ("closed_today", "closed_count_today"),
            ("inverse_pnl", "realized_inverse_pnl_to_date"),
        ],
    )

    ai_optical_paper_sleeve = _sleeve(
        lambda: prep_and_build_ai_optical_paper_sleeve_snapshot(
            as_of=today_iso,
            universe_governance_state=universe_governance_state,
            universe_state_artifact_path=str(
                daily_artifact_path("universe_state", today)
            ),
            core_universe=universe,
            ohlcv_dict=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            cached_ohlcv_fn=_cached_ohlcv,
            cached_earnings_fn=_cached_earnings,
            features_by_ticker=features_dict,
            earnings_by_ticker=earnings_dict,
            market_context=market_context,
            enabled_strategies=ENABLED_STRATEGIES,
            breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
            breakout_rank_by_52w_high=BREAKOUT_RANK_BY_52W_HIGH,
            atr_target_mult=atr_target_mult,
            regime_aware_exit=REGIME_AWARE_EXIT,
            exit_profile=exit_profile,
            market_regime=market_regime,
            spy_pct_from_ma=spy_pct_from_ma,
            qqq_pct_from_ma=qqq_pct_from_ma,
            open_positions=open_positions,
            open_prices=current_open_prices,
            current_prices=current_prices,
            logger=log,
        ),
        empty_ai_optical_paper_sleeve_snapshot,
        "AI optical",
        "ai_optical_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    volatility_contraction_paper_sleeve = _sleeve(
        lambda: prep_and_build_volatility_contraction_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            cached_ohlcv_fn=_cached_ohlcv,
            open_prices=current_open_prices, current_prices=current_prices),
        empty_volatility_contraction_paper_sleeve_snapshot,
        "Volatility-contraction paper",
        "volatility_contraction_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    volume_breadth_breakout_paper_sleeve = _sleeve(
        lambda: prep_and_build_volume_breadth_breakout_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            open_prices=current_open_prices, current_prices=current_prices),
        empty_volume_breadth_breakout_paper_sleeve_snapshot,
        "Volume-breadth breakout paper",
        "volume_breadth_breakout_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    post_earnings_underpriced_drift_paper_sleeve = _sleeve(
        lambda: prep_and_build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            signals=signals,
            open_prices=current_open_prices, current_prices=current_prices),
        empty_post_earnings_underpriced_drift_paper_sleeve_snapshot,
        "Post-earnings underpriced drift paper",
        "post_earnings_underpriced_drift_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    pead_broad_universe_paper_sleeve = _sleeve(
        lambda: prep_and_build_pead_broad_universe_paper_sleeve_snapshot(
            as_of=today_iso,
            ohlcv_dict=ohlcv_dict,
            spy_ohlcv=spy_ohlcv,
            cached_ohlcv_fn=_cached_ohlcv,
            universe_governance_state=universe_governance_state,
            open_prices=current_open_prices,
            current_prices=current_prices,
            logger=log,
        ),
        empty_pead_broad_universe_paper_sleeve_snapshot,
        "PEAD broad-universe",
        "pead_broad_universe_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    fundamental_growth_rs_paper_sleeve = _sleeve(
        lambda: prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            current_core_tickers=_core_slot_ticker_set(open_positions),
            open_prices=current_open_prices, current_prices=current_prices,
        ),
        empty_fundamental_growth_rs_paper_sleeve_snapshot,
        "Fundamental growth + RS",
        "fundamental_growth_rs_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    finra_iwm_paper_sleeve = _sleeve(
        lambda: prep_and_build_finra_iwm_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            cached_ohlcv_fn=_cached_ohlcv, broad_ingest_universe=broad_ingest_universe,
            open_prices=current_open_prices, current_prices=current_prices,
        ),
        empty_finra_iwm_paper_sleeve_snapshot,
        "FINRA IWM",
        "finra_iwm_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    sec_ftd_finra_paper_sleeve = _sleeve(
        lambda: prep_and_build_sec_ftd_finra_paper_sleeve_snapshot(
            as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
            same_day_core_tickers={
                str(s.get("ticker") or "").upper() for s in signals if s.get("ticker")
            },
            open_prices=current_open_prices, current_prices=current_prices,
        ),
        empty_sec_ftd_finra_paper_sleeve_snapshot,
        "SEC FTD + FINRA",
        "sec_ftd_finra_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    alpha_score_market_regime_ohlcv = {}
    alpha_score_market_regime_candidate_universe = {"status": "not_built", "tickers": []}

    def _build_alpha_score_market_regime():
        nonlocal alpha_score_market_regime_ohlcv, alpha_score_market_regime_candidate_universe
        snap, alpha_score_market_regime_ohlcv, alpha_score_market_regime_candidate_universe = \
            prep_and_build_alpha_score_market_regime_paper_sleeve_snapshot(
                as_of=today_iso, ohlcv_dict=ohlcv_dict, spy_ohlcv=spy_ohlcv,
                cached_ohlcv_fn=_cached_ohlcv, features_by_ticker=features_dict,
                source_consensus_snapshots=[
                    volume_breadth_breakout_paper_sleeve,
                    finra_iwm_paper_sleeve,
                ],
                open_prices=current_open_prices, current_prices=current_prices,
            )
        return snap

    alpha_score_market_regime_paper_sleeve = _sleeve(
        _build_alpha_score_market_regime,
        empty_alpha_score_market_regime_paper_sleeve_snapshot,
        "Alpha-score market-regime",
        "alpha_score_market_regime_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    accepted_source_consensus_paper_sleeve = _sleeve(
        lambda: build_accepted_source_consensus_paper_sleeve_snapshot(
            as_of=today_iso,
            features_by_ticker=features_dict,
            ohlcv_by_ticker=alpha_score_market_regime_ohlcv,
            candidate_universe=alpha_score_market_regime_candidate_universe,
            source_consensus_snapshots=[
                volume_breadth_breakout_paper_sleeve,
                finra_iwm_paper_sleeve,
            ],
            open_prices=current_open_prices,
            current_prices=current_prices,
        ),
        empty_accepted_source_consensus_paper_sleeve_snapshot,
        "Accepted-source consensus",
        "accepted_source_consensus_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    free_data_cross_source_consensus_paper_sleeve = _sleeve(
        lambda: build_free_data_cross_source_consensus_paper_sleeve_snapshot(
            as_of=today_iso,
            ohlcv_by_ticker=alpha_score_market_regime_ohlcv,
            source_snapshots=[
                fundamental_growth_rs_paper_sleeve,
                volume_breadth_breakout_paper_sleeve,
                finra_iwm_paper_sleeve,
                finra_borrow_pressure_source_snapshot_from_finra_iwm_snapshot(
                    finra_iwm_paper_sleeve
                ),
                alpha_score_market_regime_paper_sleeve,
            ],
            open_prices=current_open_prices,
            current_prices=current_prices,
            core_active_position_count=strategy_active_positions,
            max_core_positions=MAX_POSITIONS,
        ),
        empty_free_data_cross_source_consensus_paper_sleeve_snapshot,
        "Free-data cross-source consensus",
        "free_data_cross_source_consensus_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    broad_market_candidate_universe = {"status": "not_built", "tickers": []}
    broad_market_ohlcv = {}

    def _build_broad_market():
        nonlocal broad_market_candidate_universe, broad_market_ohlcv
        snap, broad_market_candidate_universe, broad_market_ohlcv = \
            prep_and_build_broad_market_paper_sleeve_snapshot(
                as_of=today_iso,
                ohlcv_dict=ohlcv_dict,
                spy_ohlcv=spy_ohlcv,
                cached_ohlcv_fn=_cached_ohlcv,
                universe_governance_state=universe_governance_state,
                universe_state_artifact_path=str(
                    daily_artifact_path("universe_state", today)
                ),
                core_universe=universe,
                pilot_universe=pilot_universe,
                open_prices=current_open_prices,
                current_prices=current_prices,
                logger=log,
                refresh_disabled=_env_flag("BROAD_UNIVERSE_REFRESH_DISABLED"),
                feed_disabled=_env_flag("BROAD_UNIVERSE_FEED_DISABLED"),
            )
        return snap

    broad_market_paper_sleeve = _sleeve(
        _build_broad_market,
        empty_broad_market_paper_sleeve_snapshot,
        "Broad-market",
        "broad_market_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    macro_relief_leadership_paper_sleeve = _sleeve(
        lambda: prep_and_build_macro_relief_leadership_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, ohlcv_dict=ohlcv_dict, cached_ohlcv_fn=_cached_ohlcv,
        ),
        empty_macro_relief_leadership_snapshot,
        "Macro-relief leadership",
        "macro_relief_leadership_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    volatility_relief_stock_leadership_paper_sleeve = _sleeve(
        lambda: prep_and_build_volatility_relief_stock_leadership_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, ohlcv_dict=ohlcv_dict, cached_ohlcv_fn=_cached_ohlcv,
            core_entries=signals,
        ),
        empty_volatility_relief_stock_leadership_snapshot,
        "Volatility-relief leadership",
        "volatility_relief_stock_leadership_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    rolling_corr_peer_shock_paper_sleeve = _sleeve(
        lambda: prep_and_build_rolling_corr_peer_shock_paper_sleeve_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, core_entries=signals,
        ),
        empty_rolling_corr_peer_shock_paper_sleeve_snapshot,
        "Rolling-corr peer-shock",
        "rolling_corr_peer_shock_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    industry_relative_laggard_repair_paper_sleeve = _sleeve(
        lambda: prep_and_build_industry_relative_laggard_repair_paper_sleeve_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, core_entries=signals,
        ),
        empty_industry_relative_laggard_repair_paper_sleeve_snapshot,
        "Industry-relative laggard repair",
        "industry_relative_laggard_repair_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    industry_stable_core_flow_paper_sleeve = _sleeve(
        lambda: prep_and_build_industry_stable_core_flow_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, ohlcv_dict=ohlcv_dict, qqq_ohlcv=qqq_ohlcv,
            cached_ohlcv_fn=_cached_ohlcv, core_entries=signals,
        ),
        empty_industry_stable_core_flow_snapshot,
        "Industry stable core-flow",
        "industry_stable_core_flow_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    turn_of_month_liquid_leadership_paper_sleeve = _sleeve(
        lambda: prep_and_build_turn_of_month_liquid_leadership_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, core_entries=signals,
        ),
        empty_turn_of_month_liquid_leadership_snapshot,
        "Turn-of-month liquid leadership",
        "turn_of_month_liquid_leadership_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    narrow_range_compression_breakout_paper_sleeve = _sleeve(
        lambda: prep_and_build_narrow_range_compression_breakout_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, core_entries=signals,
        ),
        empty_narrow_range_compression_breakout_snapshot,
        "Narrow-range compression breakout",
        "narrow_range_compression_breakout_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    distribution_day_absorption_leadership_paper_sleeve = _sleeve(
        lambda: prep_and_build_distribution_day_absorption_leadership_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, ohlcv_dict=ohlcv_dict, cached_ohlcv_fn=_cached_ohlcv,
            core_entries=signals,
        ),
        empty_distribution_day_absorption_leadership_snapshot,
        "Distribution-day absorption leadership",
        "distribution_day_absorption_leadership_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    sbc_burden_improvement_paper_sleeve = _sleeve(
        lambda: prep_and_build_sbc_burden_improvement_paper_sleeve_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            broad_market_candidate_universe=broad_market_candidate_universe,
            spy_ohlcv=spy_ohlcv, open_prices=current_open_prices,
            current_prices=current_prices,
        ),
        empty_sbc_burden_improvement_paper_sleeve_snapshot,
        "SBC burden improvement",
        "sbc_burden_improvement_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    revision_surprise_low_extension_paper_sleeve = _sleeve(
        lambda: prep_and_build_revision_surprise_low_extension_snapshot(
            as_of=today_iso, broad_market_ohlcv=broad_market_ohlcv,
            spy_ohlcv=spy_ohlcv, core_entries=signals,
        ),
        empty_revision_surprise_low_extension_snapshot,
        "Revision surprise low-extension",
        "revision_surprise_low_extension_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    accepted_helper_source_priority_allocator_paper_sleeve = _sleeve(
        lambda: build_accepted_helper_source_priority_allocator_snapshot(
            as_of=today_iso,
            source_snapshots={
                "lagged_cross_source_consensus": free_data_cross_source_consensus_paper_sleeve,
                "volatility_relief": volatility_relief_stock_leadership_paper_sleeve,
                "rolling_peer_shock": rolling_corr_peer_shock_paper_sleeve,
                "turn_of_month": turn_of_month_liquid_leadership_paper_sleeve,
                "industry_laggard_repair": industry_relative_laggard_repair_paper_sleeve,
                "revision_surprise_low_extension": revision_surprise_low_extension_paper_sleeve,
                "compression": narrow_range_compression_breakout_paper_sleeve,
                "industry_stable_core_flow": industry_stable_core_flow_paper_sleeve,
            },
            ohlcv_by_ticker=broad_market_ohlcv,
        ),
        empty_accepted_helper_source_priority_allocator_snapshot,
        "Accepted-helper source-priority allocator",
        "accepted_helper_source_priority_allocator_paper_sleeve_build_failed",
        log_metrics=_STD_SLEEVE_METRICS,
    )

    try:
        crypto_sleeve = build_crypto_sleeve_advice(load_crypto_config())
        if crypto_sleeve.get("enabled"):
            crypto_action = crypto_sleeve.get("action", {}).get("action")
            crypto_state = crypto_sleeve.get("state")
            crypto_target = crypto_sleeve.get("action", {}).get("target_position_pct")
            log.info(
                "BTC/USD crypto sleeve: state=%s action=%s target=%s",
                crypto_state,
                crypto_action,
                (
                    f"{crypto_target * 100:.0f}%"
                    if isinstance(crypto_target, (int, float))
                    else "n/a"
                ),
            )
    except Exception as e:
        log.warning(f"BTC/USD crypto sleeve unavailable: {e}")
        crypto_sleeve = empty_crypto_sleeve_advice(e)

    extra_ohlcv_frames = {
        ticker: frame
        for ticker, frame in ohlcv_cache.items()
        if ticker not in ohlcv_warehouse_recorded_tickers
    }
    _accumulate_ohlcv_warehouse(extra_ohlcv_frames, "cached_extra")

    try:
        from forward_replacement_value import enrich_all_sleeve_states

        forward_replacement_value_summary = enrich_all_sleeve_states(today_iso)
        if forward_replacement_value_summary.get("rows_enriched"):
            log.info(
                "Forward replacement-value enrichment: %d closed sleeve rows enriched",
                forward_replacement_value_summary.get("rows_enriched", 0),
            )
    except Exception as e:
        log.warning(f"Forward replacement-value enrichment unavailable: {e}")
        forward_replacement_value_summary = {"status": "error", "error": str(e)}

    default_off_alpha_attribution = build_default_off_alpha_attribution_report(
        as_of=today_iso,
        pilot_attribution=pilot_attribution,
        ai_infra_aggressive_attribution=ai_infra_aggressive_attribution,
        sec_financial_report_event_sleeve=sec_financial_report_event_sleeve,
        event_sleeve_bundle=event_sleeve_bundle,
        state_surface_sleeve=state_surface_sleeve,
        low_deployment_etf_overlay=low_deployment_etf_overlay,
        core_misfit_paper_sleeve=core_misfit_paper_sleeve,
        broad_market_paper_sleeve=broad_market_paper_sleeve,
        macro_relief_leadership_paper_sleeve=macro_relief_leadership_paper_sleeve,
        volatility_relief_stock_leadership_paper_sleeve=volatility_relief_stock_leadership_paper_sleeve,
        rolling_corr_peer_shock_paper_sleeve=rolling_corr_peer_shock_paper_sleeve,
        industry_relative_laggard_repair_paper_sleeve=industry_relative_laggard_repair_paper_sleeve,
        industry_stable_core_flow_paper_sleeve=industry_stable_core_flow_paper_sleeve,
        accepted_helper_source_priority_allocator_paper_sleeve=accepted_helper_source_priority_allocator_paper_sleeve,
        ai_optical_paper_sleeve=ai_optical_paper_sleeve,
        volatility_contraction_paper_sleeve=volatility_contraction_paper_sleeve,
        volume_breadth_breakout_paper_sleeve=volume_breadth_breakout_paper_sleeve,
        post_earnings_underpriced_drift_paper_sleeve=post_earnings_underpriced_drift_paper_sleeve,
        alpha_score_market_regime_paper_sleeve=alpha_score_market_regime_paper_sleeve,
        accepted_source_consensus_paper_sleeve=accepted_source_consensus_paper_sleeve,
        free_data_cross_source_consensus_paper_sleeve=free_data_cross_source_consensus_paper_sleeve,
        fundamental_growth_rs_paper_sleeve=fundamental_growth_rs_paper_sleeve,
        finra_iwm_paper_sleeve=finra_iwm_paper_sleeve,
        sec_ftd_finra_paper_sleeve=sec_ftd_finra_paper_sleeve,
    )

    # Attach enriched quant signals to trend_signals_dict so llm_advisor can show
    # pre-computed target_price, risk_reward_ratio, trade_quality_score, strategy.
    trend_signals_dict["quant_signals"] = signals
    trend_signals_dict["pilot_quant_signals"] = pilot_signals
    trend_signals_dict["addon_actions"] = addon_actions
    trend_signals_dict["entry_filter_audit"] = entry_filter_audit
    trend_signals_dict["entry_execution_plan"] = entry_execution_plan
    trend_signals_dict["strategy_entry_execution_plan"] = strategy_entry_execution_plan
    trend_signals_dict["entry_candidate_review"] = entry_candidate_review
    trend_signals_dict["market_state_snapshot"] = market_state_snapshot
    trend_signals_dict["pilot_entry_filter_audit"] = pilot_entry_filter_audit
    trend_signals_dict["pilot_entry_execution_plan"] = pilot_entry_execution_plan
    trend_signals_dict["pilot_decision_hashes"] = pilot_decision_hashes
    trend_signals_dict["pilot_attribution"] = pilot_attribution
    trend_signals_dict["ai_infra_aggressive_attribution"] = ai_infra_aggressive_attribution
    trend_signals_dict["default_off_alpha_attribution"] = default_off_alpha_attribution
    trend_signals_dict["forward_replacement_value_summary"] = forward_replacement_value_summary
    trend_signals_dict["form4_event_queue"] = form4_event_queue
    trend_signals_dict["form4_event_sleeve"] = form4_event_sleeve
    trend_signals_dict["sec_event_queue"] = sec_event_queue
    trend_signals_dict["sec_negative_event_sleeve"] = sec_negative_event_sleeve
    trend_signals_dict["sec_governance_event_queue"] = sec_governance_event_queue
    trend_signals_dict["sec_governance_event_sleeve"] = sec_governance_event_sleeve
    trend_signals_dict["sec_leadership_event_queue"] = sec_leadership_event_queue
    trend_signals_dict["sec_leadership_event_sleeve"] = sec_leadership_event_sleeve
    trend_signals_dict["sec_financial_report_t1_queue"] = sec_financial_report_t1_queue
    trend_signals_dict["sec_financial_report_event_sleeve"] = sec_financial_report_event_sleeve
    trend_signals_dict["event_sleeve_bundle"] = event_sleeve_bundle
    trend_signals_dict["state_surface_queue"] = state_surface_queue
    trend_signals_dict["state_surface_sleeve"] = state_surface_sleeve
    trend_signals_dict["low_deployment_etf_overlay"] = low_deployment_etf_overlay
    trend_signals_dict["core_misfit_paper_sleeve"] = core_misfit_paper_sleeve
    trend_signals_dict["broad_market_paper_sleeve"] = broad_market_paper_sleeve
    trend_signals_dict["macro_relief_leadership_paper_sleeve"] = macro_relief_leadership_paper_sleeve
    trend_signals_dict["volatility_relief_stock_leadership_paper_sleeve"] = volatility_relief_stock_leadership_paper_sleeve
    trend_signals_dict["rolling_corr_peer_shock_paper_sleeve"] = rolling_corr_peer_shock_paper_sleeve
    trend_signals_dict["industry_relative_laggard_repair_paper_sleeve"] = industry_relative_laggard_repair_paper_sleeve
    trend_signals_dict["industry_stable_core_flow_paper_sleeve"] = industry_stable_core_flow_paper_sleeve
    trend_signals_dict["turn_of_month_liquid_leadership_paper_sleeve"] = turn_of_month_liquid_leadership_paper_sleeve
    trend_signals_dict["narrow_range_compression_breakout_paper_sleeve"] = narrow_range_compression_breakout_paper_sleeve
    trend_signals_dict["distribution_day_absorption_leadership_paper_sleeve"] = distribution_day_absorption_leadership_paper_sleeve
    trend_signals_dict["sbc_burden_improvement_paper_sleeve"] = sbc_burden_improvement_paper_sleeve
    trend_signals_dict["revision_surprise_low_extension_paper_sleeve"] = revision_surprise_low_extension_paper_sleeve
    trend_signals_dict["accepted_helper_source_priority_allocator_paper_sleeve"] = accepted_helper_source_priority_allocator_paper_sleeve
    trend_signals_dict["ai_optical_paper_sleeve"] = ai_optical_paper_sleeve
    trend_signals_dict["volatility_contraction_paper_sleeve"] = volatility_contraction_paper_sleeve
    trend_signals_dict["volume_breadth_breakout_paper_sleeve"] = volume_breadth_breakout_paper_sleeve
    trend_signals_dict["post_earnings_underpriced_drift_paper_sleeve"] = post_earnings_underpriced_drift_paper_sleeve
    trend_signals_dict["pead_broad_universe_paper_sleeve"] = pead_broad_universe_paper_sleeve
    trend_signals_dict["alpha_score_market_regime_paper_sleeve"] = alpha_score_market_regime_paper_sleeve
    trend_signals_dict["accepted_source_consensus_paper_sleeve"] = accepted_source_consensus_paper_sleeve
    trend_signals_dict["free_data_cross_source_consensus_paper_sleeve"] = free_data_cross_source_consensus_paper_sleeve
    trend_signals_dict["fundamental_growth_rs_paper_sleeve"] = fundamental_growth_rs_paper_sleeve
    trend_signals_dict["finra_iwm_paper_sleeve"] = finra_iwm_paper_sleeve
    trend_signals_dict["sec_ftd_finra_paper_sleeve"] = sec_ftd_finra_paper_sleeve
    trend_signals_dict["space_catalyst_shadow"] = space_catalyst_shadow
    trend_signals_dict["space_catalyst_observation_slot"] = space_catalyst_observation_slot
    trend_signals_dict["space_catalyst_event_ledger"] = space_catalyst_event_ledger
    trend_signals_dict["platform_rs20_watch"] = platform_rs20_watch
    trend_signals_dict["sec_10k_forward_watch"] = sec_10k_forward_watch
    trend_signals_dict["ohlcv_warehouse"] = ohlcv_warehouse_summary
    trend_signals_dict["non_ohlcv_snapshot"] = non_ohlcv_snapshot
    trend_signals_dict["crypto_sleeve"] = crypto_sleeve

    try:
        from sleeve_health import build_sleeve_health_report

        sleeve_health_report = build_sleeve_health_report(today_iso, trend_signals_dict)
        if sleeve_health_report.get("failing_builds") or sleeve_health_report.get("stalled_sleeves"):
            log.warning(
                "Sleeve health: failing_builds=%s stalled_sleeves=%s",
                sleeve_health_report.get("failing_builds"),
                sleeve_health_report.get("stalled_sleeves"),
            )
    except Exception as e:
        log.warning(f"Sleeve health report unavailable: {e}")
        sleeve_health_report = {"status": "error", "error": str(e)}
    trend_signals_dict["sleeve_health_report"] = sleeve_health_report


    # Safety net: drain any deferred post-prompt work not already run (e.g. when
    # the Step 6A checkpoint was skipped). No-op once the queue is empty.
    _run_deferred_after_prompt()

    # ── Step 7: Quant report ──────────────────────────────────────────────────
    _print_section("STEP 7 — Quant report")
    report = generate_daily_report(
        signals          = signals,
        features_dict    = features_dict,
        portfolio_heat   = portfolio_heat,
        metrics          = metrics,
        market_regime    = market_regime,
        open_positions   = open_positions,
        market_state_snapshot = market_state_snapshot,
        dropped_signals  = last_dropped_signals or None,
        addon_actions    = addon_actions,
        entry_execution_plan = entry_execution_plan,
        entry_candidate_review = entry_candidate_review,
        pilot_attribution = pilot_attribution,
        ai_infra_aggressive_attribution = ai_infra_aggressive_attribution,
        default_off_alpha_attribution = default_off_alpha_attribution,
        form4_event_queue = form4_event_queue,
        form4_event_sleeve = form4_event_sleeve,
        sec_event_queue = sec_event_queue,
        sec_negative_event_sleeve = sec_negative_event_sleeve,
        sec_governance_event_queue = sec_governance_event_queue,
        sec_governance_event_sleeve = sec_governance_event_sleeve,
        sec_leadership_event_queue = sec_leadership_event_queue,
        sec_leadership_event_sleeve = sec_leadership_event_sleeve,
        sec_financial_report_t1_queue = sec_financial_report_t1_queue,
        sec_financial_report_event_sleeve = sec_financial_report_event_sleeve,
        event_sleeve_bundle = event_sleeve_bundle,
        state_surface_sleeve = state_surface_sleeve,
        low_deployment_etf_overlay = low_deployment_etf_overlay,
        core_misfit_paper_sleeve = core_misfit_paper_sleeve,
        broad_market_paper_sleeve = broad_market_paper_sleeve,
        macro_relief_leadership_paper_sleeve = macro_relief_leadership_paper_sleeve,
        volatility_relief_stock_leadership_paper_sleeve = volatility_relief_stock_leadership_paper_sleeve,
        rolling_corr_peer_shock_paper_sleeve = rolling_corr_peer_shock_paper_sleeve,
        industry_relative_laggard_repair_paper_sleeve = industry_relative_laggard_repair_paper_sleeve,
        industry_stable_core_flow_paper_sleeve = industry_stable_core_flow_paper_sleeve,
        accepted_helper_source_priority_allocator_paper_sleeve = accepted_helper_source_priority_allocator_paper_sleeve,
        ai_optical_paper_sleeve = ai_optical_paper_sleeve,
        volatility_contraction_paper_sleeve = volatility_contraction_paper_sleeve,
        volume_breadth_breakout_paper_sleeve = volume_breadth_breakout_paper_sleeve,
        post_earnings_underpriced_drift_paper_sleeve = post_earnings_underpriced_drift_paper_sleeve,
        alpha_score_market_regime_paper_sleeve = alpha_score_market_regime_paper_sleeve,
        accepted_source_consensus_paper_sleeve = accepted_source_consensus_paper_sleeve,
        free_data_cross_source_consensus_paper_sleeve = free_data_cross_source_consensus_paper_sleeve,
        fundamental_growth_rs_paper_sleeve = fundamental_growth_rs_paper_sleeve,
        finra_iwm_paper_sleeve = finra_iwm_paper_sleeve,
        sec_ftd_finra_paper_sleeve = sec_ftd_finra_paper_sleeve,
        space_catalyst_shadow = space_catalyst_shadow,
        space_catalyst_observation_slot = space_catalyst_observation_slot,
        space_catalyst_event_ledger = space_catalyst_event_ledger,
        platform_rs20_watch = platform_rs20_watch,
        sec_10k_forward_watch = sec_10k_forward_watch,
        non_ohlcv_snapshot = non_ohlcv_snapshot,
        crypto_sleeve = crypto_sleeve,
    )
    print("\n" + report)
    save_report(report)

    _save_json_best_effort({
        "generated_at":   datetime.now().isoformat(),
        "market_regime":  market_regime,
        "portfolio_heat": portfolio_heat,
        "signals":        signals,
        "pilot_signals":  pilot_signals,
        "addon_actions":  addon_actions,
        "addon_audit":    addon_audit,
        "entry_filter_audit": entry_filter_audit,
        "entry_execution_plan": entry_execution_plan,
        "strategy_entry_execution_plan": strategy_entry_execution_plan,
        "entry_candidate_review": entry_candidate_review,
        "market_state_snapshot": market_state_snapshot,
        "pilot_entry_filter_audit": pilot_entry_filter_audit,
        "pilot_entry_execution_plan": pilot_entry_execution_plan,
        "pilot_decision_snapshots": pilot_decision_snapshots,
        "pilot_decision_hashes": pilot_decision_hashes,
        "pilot_attribution": pilot_attribution,
        "ai_infra_aggressive_attribution": ai_infra_aggressive_attribution,
        "default_off_alpha_attribution": default_off_alpha_attribution,
        "form4_event_queue": form4_event_queue,
        "form4_event_sleeve": form4_event_sleeve,
        "sec_event_queue": sec_event_queue,
        "sec_negative_event_sleeve": sec_negative_event_sleeve,
        "sec_governance_event_queue": sec_governance_event_queue,
        "sec_governance_event_sleeve": sec_governance_event_sleeve,
        "sec_leadership_event_queue": sec_leadership_event_queue,
        "sec_leadership_event_sleeve": sec_leadership_event_sleeve,
        "sec_financial_report_t1_queue": sec_financial_report_t1_queue,
        "sec_financial_report_event_sleeve": sec_financial_report_event_sleeve,
        "event_sleeve_bundle": event_sleeve_bundle,
        "state_surface_queue": state_surface_queue,
        "state_surface_sleeve": state_surface_sleeve,
        "low_deployment_etf_overlay": low_deployment_etf_overlay,
        "core_misfit_paper_sleeve": core_misfit_paper_sleeve,
        "broad_market_paper_sleeve": broad_market_paper_sleeve,
        "macro_relief_leadership_paper_sleeve": macro_relief_leadership_paper_sleeve,
        "volatility_relief_stock_leadership_paper_sleeve": volatility_relief_stock_leadership_paper_sleeve,
        "rolling_corr_peer_shock_paper_sleeve": rolling_corr_peer_shock_paper_sleeve,
        "industry_relative_laggard_repair_paper_sleeve": industry_relative_laggard_repair_paper_sleeve,
        "industry_stable_core_flow_paper_sleeve": industry_stable_core_flow_paper_sleeve,
        "turn_of_month_liquid_leadership_paper_sleeve": turn_of_month_liquid_leadership_paper_sleeve,
        "narrow_range_compression_breakout_paper_sleeve": narrow_range_compression_breakout_paper_sleeve,
        "distribution_day_absorption_leadership_paper_sleeve": distribution_day_absorption_leadership_paper_sleeve,
        "sbc_burden_improvement_paper_sleeve": sbc_burden_improvement_paper_sleeve,
        "revision_surprise_low_extension_paper_sleeve": revision_surprise_low_extension_paper_sleeve,
        "accepted_helper_source_priority_allocator_paper_sleeve": accepted_helper_source_priority_allocator_paper_sleeve,
        "ai_optical_paper_sleeve": ai_optical_paper_sleeve,
        "volatility_contraction_paper_sleeve": volatility_contraction_paper_sleeve,
        "volume_breadth_breakout_paper_sleeve": volume_breadth_breakout_paper_sleeve,
        "post_earnings_underpriced_drift_paper_sleeve": post_earnings_underpriced_drift_paper_sleeve,
        "pead_broad_universe_paper_sleeve": pead_broad_universe_paper_sleeve,
        "alpha_score_market_regime_paper_sleeve": alpha_score_market_regime_paper_sleeve,
        "accepted_source_consensus_paper_sleeve": accepted_source_consensus_paper_sleeve,
        "free_data_cross_source_consensus_paper_sleeve": free_data_cross_source_consensus_paper_sleeve,
        "fundamental_growth_rs_paper_sleeve": fundamental_growth_rs_paper_sleeve,
        "finra_iwm_paper_sleeve": finra_iwm_paper_sleeve,
        "sec_ftd_finra_paper_sleeve": sec_ftd_finra_paper_sleeve,
        "space_catalyst_shadow": space_catalyst_shadow,
        "space_catalyst_observation_slot": space_catalyst_observation_slot,
        "space_catalyst_event_ledger": space_catalyst_event_ledger,
        "platform_rs20_watch": platform_rs20_watch,
        "sec_10k_forward_watch": sec_10k_forward_watch,
        "ohlcv_warehouse": ohlcv_warehouse_summary,
        "non_ohlcv_snapshot": non_ohlcv_snapshot,
        "crypto_sleeve": crypto_sleeve,
        "heat_blocked_signals": heat_blocked_signals,
        "heat_blocked_pilot_signals": heat_blocked_pilot_signals,
        "universe_governance": universe_governance_state,
        "features":       features_dict,
    }, str(daily_artifact_path("quant_signals", today)), "quant signals")

    _run_expectation_residual_leadership_attribution_observer()

    # ── Step 8: Fetch & filter news ───────────────────────────────────────────
    _print_section("STEP 8 — News collection")
    if daily_prompt_generated:
        log.info("News already collected for priority LLM prompt; skipping duplicate collection.")
    else:
        trade_items = _collect_trade_news(today, universe, pilot_universe)

    # ── Step 9: LLM prompt ────────────────────────────────────────────────────
    _print_section("STEP 9 — LLM prompt")
    # Always generate the prompt — quant signals and position management do not
    # require news. On news-quiet days the prompt still surfaces exit signals
    # and high-confidence quant signals that stand alone (confidence >= 0.85).
    #
    # P-LLM coverage note (exp-20260612-009): the operator workflow is manual —
    # paste the prompt into an external LLM, then import the response with
    # quant/import_advice.py, which writes llm_prompt_resp_YYYYMMDD.json (the
    # canonical artifact backtester --replay-llm consumes). Replay coverage
    # only compounds when the import step happens; llm_backlog tracks gaps.
    if daily_prompt_generated:
        log.info("Daily LLM prompt already generated in priority checkpoint.")
    else:
        daily_prompt_generated = _generate_llm_prompt(
            trade_items,           # may be [] on quiet news days; that's fine
            open_positions,
            trend_signals_dict,
        )

    # ── Step 10: Summary ──────────────────────────────────────────────────────
    _print_section("PIPELINE COMPLETE")
    log.info(f"  Tickers analyzed:   {len(universe)}")
    log.info(f"  Signals generated:  {len(signals)}")
    log.info(f"  Pilot signals:      {len(pilot_signals)}")
    log.info(f"  Add-on actions:     {len(addon_actions)}")
    log.info(f"  News (trade):       {len(trade_items)}")
    log.info(f"  Regime:             {market_regime['regime']}")
    if portfolio_heat:
        log.info(f"  Portfolio heat:     {portfolio_heat['portfolio_heat_pct']*100:.1f}%")
    if crypto_sleeve:
        if crypto_sleeve.get("enabled"):
            _crypto_action = crypto_sleeve.get("action", {})
            _crypto_trade_value = _crypto_action.get("trade_value_usd")
            _crypto_trade_text = (
                f"${abs(_crypto_trade_value):,.0f}"
                if isinstance(_crypto_trade_value, (int, float))
                else "manual sizing"
            )
            _crypto_target = _crypto_action.get("target_position_pct")
            _crypto_target_text = (
                f"{_crypto_target * 100:.0f}%"
                if isinstance(_crypto_target, (int, float))
                else "n/a"
            )
            log.info(
                "  BTC/USD sleeve:     %s %s -> target %s (%s)",
                _crypto_action.get("action"),
                _crypto_trade_text,
                _crypto_target_text,
                crypto_sleeve.get("state"),
            )
        else:
            log.info(
                "  BTC/USD sleeve:     unavailable (%s)",
                crypto_sleeve.get("error") or crypto_sleeve.get("reason"),
            )
    if metrics.get("total_trades", 0) > 0:
        log.info(f"  P&L (realized):     ${metrics['total_pnl_usd']:,.2f}  "
                 f"WR={metrics['win_rate']*100:.0f}%")
    log.info("")

    # Pilot tracker: regenerate the manual small-live pilot recommendation sheet
    # and benchmark scorecard from the freshly-written sleeve states. Read-only;
    # wrapped so a tracker error can never break the daily production run.
    try:
        import pilot_tracker
        _pilot = pilot_tracker.generate(write=True)
        _overlaps = _pilot.get("cross_pilot_overlap") or []
        log.info(
            "  Pilot tracker:      %d pilots, %d cross-pilot overlap(s) -> data/pilots/pilot_tracker.md",
            len(_pilot.get("scorecards") or []),
            len(_overlaps),
        )
        for _ov in _overlaps:
            log.warning(
                "  Pilot overlap:      %s held by %d pilots -> $%s stacked exposure",
                _ov.get("ticker"), _ov.get("positions", 0),
                f"{_ov.get('total_exposure_usd', 0.0):,.0f}",
            )
    except Exception as exc:  # never let pilot tracking break the daily run
        log.warning("  Pilot tracker:      skipped (%s)", exc)


if __name__ == "__main__":
    main()
