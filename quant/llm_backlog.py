"""
Actionable backlog helpers for LLM replay coverage.

This module turns backtest-time "candidate dates missing LLM replay archives"
into an operational queue: which dates already have prompts, which still lack
even a prompt, and what candidate signals were waiting on those dates.
"""

from __future__ import annotations

import json
import os
from collections import Counter


def _safe_load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_replay_archive_context(data_dir, date_str):
    """Load prompt-time context from replay archive or decision-log sidecar."""
    payload = _safe_load_json(os.path.join(data_dir, f"llm_prompt_resp_{date_str}.json"))
    if isinstance(payload, dict):
        context = payload.get("archive_context")
        if isinstance(context, dict):
            return context

    decision_log = _safe_load_json(os.path.join(data_dir, f"llm_decision_log_{date_str}.json"))
    if not isinstance(decision_log, dict):
        return None

    summary = _signal_summary(decision_log)
    signals_presented = summary["tickers"]
    new_trade_locked = decision_log.get("new_trade_locked")
    if new_trade_locked is True:
        ranking_eligible = False
    elif signals_presented:
        ranking_eligible = True
    else:
        ranking_eligible = False

    context = {
        "source": "llm_decision_log",
        "signals_presented": signals_presented,
        "signals_presented_count": len(signals_presented),
        "ranking_eligible": ranking_eligible,
    }
    if new_trade_locked is not None:
        context["new_trade_locked"] = bool(new_trade_locked)
    if decision_log.get("account_state") is not None:
        context["account_state"] = decision_log.get("account_state")
    if decision_log.get("lock_reason"):
        context["lock_reason"] = decision_log.get("lock_reason")
    return context


def _signal_summary(decision_log):
    if not isinstance(decision_log, dict):
        return {"tickers": [], "strategies": {}, "max_trade_quality_score": None}

    details = decision_log.get("signal_details")
    if not isinstance(details, list):
        details = []

    tickers = []
    strategies = Counter()
    max_tqs = None
    for item in details:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        strategy = item.get("strategy")
        tqs = item.get("trade_quality_score")
        if isinstance(ticker, str) and ticker.strip():
            tickers.append(ticker.strip().upper())
        if isinstance(strategy, str) and strategy.strip():
            strategies[strategy.strip()] += 1
        if isinstance(tqs, (int, float)):
            max_tqs = tqs if max_tqs is None else max(max_tqs, float(tqs))

    return {
        "tickers": tickers,
        "strategies": dict(strategies),
        "max_trade_quality_score": round(max_tqs, 4) if max_tqs is not None else None,
    }


def _saved_quant_signal_tickers(data_dir, date_str):
    """Return saved production quant-signal tickers for a date.

    Returns:
        None  -> quant_signals_YYYYMMDD.json missing or unreadable
        list  -> parsed ticker list (possibly empty)
    """
    payload = _safe_load_json(os.path.join(data_dir, f"quant_signals_{date_str}.json"))
    if not isinstance(payload, dict):
        return None

    signals = payload.get("signals")
    if not isinstance(signals, list):
        return []

    tickers = []
    for item in signals:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            tickers.append(ticker.strip().upper())
    return tickers


def _load_saved_quant_payload(data_dir, date_str):
    """Return the raw saved production quant payload when available."""
    payload = _safe_load_json(os.path.join(data_dir, f"quant_signals_{date_str}.json"))
    return payload if isinstance(payload, dict) else None


def build_llm_archive_backlog(data_dir, candidate_dates_missing, candidate_signal_counts_by_date):
    """
    Build an actionable queue for missing LLM replay archives.

    Args:
        data_dir: backtest data directory
        candidate_dates_missing: iterable of YYYYMMDD dates whose candidate
            signals reached the LLM gate but have no llm_prompt_resp archive
        candidate_signal_counts_by_date: mapping YYYYMMDD -> candidate count

    Returns:
        dict with summary counts plus per-date queue entries ordered by
        practical priority (more candidate signals first, prompt-ready dates
        ahead of dates that still lack even a saved prompt).
    """
    missing_dates = list(candidate_dates_missing or [])
    signal_counts = dict(candidate_signal_counts_by_date or {})
    queue = []

    for date_str in missing_dates:
        prompt_path = os.path.join(data_dir, f"llm_prompt_{date_str}.txt")
        response_path = os.path.join(data_dir, f"llm_prompt_resp_{date_str}.json")
        raw_response_path = os.path.join(data_dir, f"llm_output_{date_str}.json")
        advice_path = os.path.join(data_dir, f"investment_advice_{date_str}.json")
        decision_log_path = os.path.join(data_dir, f"llm_decision_log_{date_str}.json")
        news_path = os.path.join(data_dir, f"clean_trade_news_{date_str}.json")
        quant_signals_path = os.path.join(data_dir, f"quant_signals_{date_str}.json")
        trend_signals_path = os.path.join(data_dir, f"trend_signals_{date_str}.json")
        earnings_snapshot_path = os.path.join(data_dir, f"earnings_snapshot_{date_str}.json")

        decision_log = _safe_load_json(decision_log_path)
        quant_payload = _load_saved_quant_payload(data_dir, date_str) or {}
        signal_summary = _signal_summary(decision_log)
        prompt_context = _load_replay_archive_context(data_dir, date_str) or {}
        quant_signal_tickers = []
        quant_signals = quant_payload.get("signals")
        if isinstance(quant_signals, list):
            for item in quant_signals:
                if not isinstance(item, dict):
                    continue
                ticker = item.get("ticker")
                if isinstance(ticker, str) and ticker.strip():
                    quant_signal_tickers.append(ticker.strip().upper())
        portfolio_heat = quant_payload.get("portfolio_heat")
        can_add_new_positions = None
        if isinstance(portfolio_heat, dict):
            raw_can_add = portfolio_heat.get("can_add_new_positions")
            if isinstance(raw_can_add, bool):
                can_add_new_positions = raw_can_add
        raw_response_exists = os.path.exists(raw_response_path)
        prompt_exists = os.path.exists(prompt_path)
        response_exists = os.path.exists(response_path)
        decision_log_exists = os.path.exists(decision_log_path)
        quant_signals_exists = os.path.exists(quant_signals_path)
        trend_signals_exists = os.path.exists(trend_signals_path)
        earnings_snapshot_exists = os.path.exists(earnings_snapshot_path)

        prompt_candidates = [
            t.strip().upper()
            for t in prompt_context.get("signals_presented", [])
            if isinstance(t, str) and t.strip()
        ]
        ranking_eligible_prompt = prompt_context.get("ranking_eligible")
        if ranking_eligible_prompt is None:
            if prompt_candidates:
                ranking_eligible_prompt = True
            elif quant_signal_tickers and can_add_new_positions is not False:
                ranking_eligible_prompt = True
            elif quant_signals_exists:
                ranking_eligible_prompt = False

        has_replay_context = (
            decision_log_exists
            or quant_signals_exists
            or trend_signals_exists
            or os.path.exists(news_path)
        )

        if raw_response_exists and not response_exists:
            recovery_tier = "raw_response_recoverable"
        elif prompt_exists and not response_exists and ranking_eligible_prompt is True:
            recovery_tier = "prompt_only"
        elif has_replay_context:
            recovery_tier = "context_only"
        elif earnings_snapshot_exists:
            recovery_tier = "snapshot_only"
        else:
            recovery_tier = "archive_hole"

        entry = {
            "date": date_str,
            "candidate_signal_count": int(signal_counts.get(date_str, 0) or 0),
            "prompt_exists": prompt_exists,
            "response_exists": response_exists,
            "raw_response_exists": raw_response_exists,
            "investment_advice_exists": os.path.exists(advice_path),
            "decision_log_exists": decision_log_exists,
            "clean_trade_news_exists": os.path.exists(news_path),
            "quant_signals_exists": quant_signals_exists,
            "trend_signals_exists": trend_signals_exists,
            "earnings_snapshot_exists": earnings_snapshot_exists,
            "ready_for_manual_import": prompt_exists and not response_exists and ranking_eligible_prompt is True,
            "prompt_exists_but_not_ranking_eligible": prompt_exists and not response_exists and ranking_eligible_prompt is False,
            "recovery_tier": recovery_tier,
            "signal_tickers": signal_summary["tickers"],
            "prompt_signal_tickers": prompt_candidates,
            "quant_signal_tickers": quant_signal_tickers,
            "ranking_eligible_prompt": ranking_eligible_prompt,
            "can_add_new_positions": can_add_new_positions,
            "strategies": signal_summary["strategies"],
            "max_trade_quality_score": signal_summary["max_trade_quality_score"],
        }
        queue.append(entry)

    queue.sort(
        key=lambda item: (
            -item["candidate_signal_count"],
            item["recovery_tier"] != "raw_response_recoverable",
            not item["ready_for_manual_import"],
            not item["decision_log_exists"],
            item["date"],
        )
    )
    for idx, item in enumerate(queue, start=1):
        item["priority_rank"] = idx

    missing_candidate_signals = sum(item["candidate_signal_count"] for item in queue)
    prompt_ready_days = sum(1 for item in queue if item["ready_for_manual_import"])
    prompt_ineligible_days = sum(
        1 for item in queue if item["prompt_exists_but_not_ranking_eligible"]
    )
    prompt_missing_days = sum(1 for item in queue if not item["prompt_exists"])
    decision_log_days = sum(1 for item in queue if item["decision_log_exists"])
    advice_days = sum(1 for item in queue if item["investment_advice_exists"])
    news_days = sum(1 for item in queue if item["clean_trade_news_exists"])
    raw_response_days = sum(1 for item in queue if item["raw_response_exists"])
    quant_signals_days = sum(1 for item in queue if item["quant_signals_exists"])
    trend_signals_days = sum(1 for item in queue if item["trend_signals_exists"])
    earnings_snapshot_days = sum(1 for item in queue if item["earnings_snapshot_exists"])
    context_only_days = sum(1 for item in queue if item["recovery_tier"] == "context_only")
    snapshot_only_days = sum(1 for item in queue if item["recovery_tier"] == "snapshot_only")
    archive_hole_days = sum(1 for item in queue if item["recovery_tier"] == "archive_hole")

    return {
        "missing_candidate_days": len(queue),
        "missing_candidate_signals": missing_candidate_signals,
        "raw_response_recoverable_days": raw_response_days,
        "prompt_ready_days": prompt_ready_days,
        "prompt_ineligible_days": prompt_ineligible_days,
        "prompt_missing_days": prompt_missing_days,
        "context_only_days": context_only_days,
        "snapshot_only_days": snapshot_only_days,
        "archive_hole_days": archive_hole_days,
        "decision_log_days": decision_log_days,
        "investment_advice_days": advice_days,
        "clean_trade_news_days": news_days,
        "quant_signals_days": quant_signals_days,
        "trend_signals_days": trend_signals_days,
        "earnings_snapshot_days": earnings_snapshot_days,
        "notes": [
            "raw_response_recoverable_days means llm_output_YYYYMMDD.json exists and can be imported into llm_prompt_resp without inventing decisions.",
            "prompt_ready_days means llm_prompt_YYYYMMDD.txt exists and prompt-time context still indicates a real ranking-eligible new-trade decision can be reconstructed.",
            "prompt_ineligible_days means a prompt file exists, but saved context already shows no prompt-time ranking opportunity (for example no candidates or Task A locked), so it should not count toward soft-ranking readiness.",
            "context_only_days means some production-side context exists (decision log, quant signals, trend signals, or saved clean news), but no saved LLM prompt/response exists yet.",
            "snapshot_only_days means only earnings_snapshot_YYYYMMDD.json exists. That supports earnings replay, but it is not meaningful LLM replay context and should not be treated as a near-recoverable soft-ranking sample.",
            "priority ranks higher-candidate days first, then favors recoverable raw responses, then prompt-ready dates.",
            "signal_tickers and strategies come from llm_decision_log_YYYYMMDD.json when available.",
        ],
        "queue": queue,
    }


def build_llm_context_alignment(
    data_dir,
    candidate_dates_covered,
    candidate_tickers_by_date,
    candidate_signal_counts_by_date,
    candidate_days_total,
    candidate_signals_total,
):
    """Audit whether covered replay dates are actually aligned with production.

    A covered replay day is only a credible LLM sample when the repo also has a
    saved production-side quant candidate set for that day and it overlaps with
    the backtest candidate set. Otherwise "date covered" can still be a context
    mismatch: the live prompt may have seen no tradable candidates, or a
    different ticker set, even though a response file exists.
    """
    covered_dates = list(candidate_dates_covered or [])
    candidate_tickers_by_date = dict(candidate_tickers_by_date or {})
    candidate_signal_counts_by_date = dict(candidate_signal_counts_by_date or {})

    queue = []
    for date_str in covered_dates:
        backtest_tickers = [
            t.strip().upper()
            for t in candidate_tickers_by_date.get(date_str, [])
            if isinstance(t, str) and t.strip()
        ]
        archive_context = _load_replay_archive_context(data_dir, date_str) or {}
        archive_signal_tickers = [
            t.strip().upper()
            for t in archive_context.get("signals_presented", [])
            if isinstance(t, str) and t.strip()
        ]

        production_tickers = None
        production_source = None
        if archive_signal_tickers:
            production_tickers = archive_signal_tickers
            production_source = "archive_context"
        else:
            production_tickers = _saved_quant_signal_tickers(data_dir, date_str)
            production_source = "quant_signals"

        quant_file_exists = production_tickers is not None
        production_tickers = production_tickers or []
        overlap = [t for t in backtest_tickers if t in set(production_tickers)]

        if not quant_file_exists:
            alignment_status = "production_quant_missing"
        elif not production_tickers:
            alignment_status = "production_quant_empty"
        elif overlap:
            alignment_status = "aligned"
        else:
            alignment_status = "production_quant_mismatch"

        ranking_eligible = archive_context.get("ranking_eligible")
        new_trade_locked = archive_context.get("new_trade_locked")
        if ranking_eligible is True and overlap:
            ranking_status = "ranking_eligible_aligned"
        elif new_trade_locked is True:
            ranking_status = "new_trade_locked"
        elif ranking_eligible is False:
            ranking_status = "no_prompt_candidates"
        elif overlap:
            ranking_status = "aligned_but_unknown_eligibility"
        else:
            ranking_status = "unknown_eligibility"

        queue.append({
            "date": date_str,
            "candidate_signal_count": int(candidate_signal_counts_by_date.get(date_str, 0) or 0),
            "backtest_candidate_tickers": backtest_tickers,
            "production_quant_tickers": production_tickers,
            "overlap_tickers": overlap,
            "production_quant_exists": quant_file_exists,
            "alignment_status": alignment_status,
            "production_source": production_source,
            "archive_context_present": bool(archive_context),
            "ranking_eligible": ranking_eligible,
            "new_trade_locked": new_trade_locked,
            "ranking_status": ranking_status,
        })

    queue.sort(
        key=lambda item: (
            item["alignment_status"] != "aligned",
            -item["candidate_signal_count"],
            item["date"],
        )
    )

    aligned_days = sum(1 for item in queue if item["alignment_status"] == "aligned")
    aligned_signals = sum(len(item["overlap_tickers"]) for item in queue)
    production_quant_empty_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_empty"
    )
    production_quant_missing_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_missing"
    )
    production_quant_mismatch_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_mismatch"
    )
    ranking_eligible_aligned_days = sum(
        1 for item in queue if item["ranking_status"] == "ranking_eligible_aligned"
    )
    ranking_eligible_aligned_signals = sum(
        len(item["overlap_tickers"])
        for item in queue
        if item["ranking_status"] == "ranking_eligible_aligned"
    )
    ranking_locked_days = sum(
        1 for item in queue if item["ranking_status"] == "new_trade_locked"
    )
    ranking_ineligible_no_candidates_days = sum(
        1 for item in queue if item["ranking_status"] == "no_prompt_candidates"
    )
    ranking_unknown_days = sum(
        1 for item in queue
        if item["ranking_status"] in {"aligned_but_unknown_eligibility", "unknown_eligibility"}
    )

    return {
        "covered_candidate_days": len(queue),
        "aligned_days": aligned_days,
        "aligned_signals": aligned_signals,
        "production_quant_empty_days": production_quant_empty_days,
        "production_quant_missing_days": production_quant_missing_days,
        "production_quant_mismatch_days": production_quant_mismatch_days,
        "production_aligned_candidate_day_fraction_of_total": (
            round(aligned_days / candidate_days_total, 4) if candidate_days_total else 0.0
        ),
        "production_aligned_candidate_day_fraction_of_covered": (
            round(aligned_days / len(queue), 4) if queue else 0.0
        ),
        "production_aligned_candidate_signal_fraction_of_total": (
            round(aligned_signals / candidate_signals_total, 4)
            if candidate_signals_total else 0.0
        ),
        "ranking_eligible_aligned_days": ranking_eligible_aligned_days,
        "ranking_eligible_aligned_signals": ranking_eligible_aligned_signals,
        "ranking_locked_days": ranking_locked_days,
        "ranking_ineligible_no_candidates_days": ranking_ineligible_no_candidates_days,
        "ranking_unknown_days": ranking_unknown_days,
        "ranking_eligible_candidate_day_fraction_of_total": (
            round(ranking_eligible_aligned_days / candidate_days_total, 4)
            if candidate_days_total else 0.0
        ),
        "ranking_eligible_candidate_signal_fraction_of_total": (
            round(ranking_eligible_aligned_signals / candidate_signals_total, 4)
            if candidate_signals_total else 0.0
        ),
        "notes": [
            "aligned means saved production quant_signals for the same date share at least one ticker with the backtest pre-LLM candidate set.",
            "production_quant_empty means a replay file exists, but the saved production quant_signals file had zero candidates that day.",
            "production_quant_missing means the date has a replay file but no saved production quant_signals file, so candidate-set comparability is unknown.",
            "production_quant_mismatch means both sides had candidates, but none of the saved production tickers overlap the backtest candidate set.",
            "ranking_eligible_aligned means the saved prompt-time context says Task A was actually eligible for a new-trade decision and its candidate set overlaps the backtest pre-LLM candidates.",
            "new_trade_locked means the saved prompt-time program layer had already locked Task A (for example heat / regime), so that day should not count toward soft-ranking readiness even if a dated reply exists.",
        ],
        "queue": queue,
    }
