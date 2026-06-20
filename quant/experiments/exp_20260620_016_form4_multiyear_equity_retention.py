"""exp-20260620-016: Form 4 multi-year equity-retention scout.

Replay-only alpha search. The single decision hypothesis is a PIT public Form 4
candidate source: officer/director equity-compensation rows whose footnotes
explicitly disclose multi-year vesting / retention, with retained direct
ownership and no same-accession open-market sale, may identify aligned
leadership and constrained future supply better than raw transaction-code
context.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily parser reproduces the same Form 4
footnote semantics. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260620-016"
STEM = "form4_multiyear_equity_retention"
TRIAL_FAMILY = "form4_multiyear_equity_retention_candidate_pool"
TRIAL_VARIANT_ID = "form4_multiyear_equity_retention_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form4_multiyear_equity_retention_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
FORM4_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_GRANT_SHARES = 5_000.0
MIN_RETAINED_TO_GRANT_RATIO = 1.0
MIN_VESTING_HORIZON_YEARS = 2.0
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 25_000_000.0
MIN_RET20_EXCESS_SPY = -0.02
MIN_RET60_EXCESS_SPY = -0.05
MIN_SIGNAL_RETURN = -0.05
MAX_SIGNAL_RETURN = 0.08
MIN_CLOSE_LOCATION = 0.35
MAX_REALIZED_VOL_20D = 0.12

ACQUISITION_CODES = {"A", "M"}
SALE_CODES = {"S"}
TEXT_HINT_RE = re.compile(
    r"\b(vest|vesting|restricted stock|rsu|performance stock|stock unit|"
    r"option award|equity award|retention|incentive)\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20[2-3][0-9])\b")
DURATION_RE = re.compile(
    r"\b(?:(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    r"[-\s]+(?:year|annual|equal annual)|over\s+(?:a\s+)?"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    r"[-\s]+year|multi[-\s]+year)\b",
    re.IGNORECASE,
)
WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "routine_compensation_plumbing",
        "thin_sample",
        "old_thin_regression",
        "accepted_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Prior Form 4 compensation-context tests failed when they only used "
        "transaction-code context. This tests a materially different provenance "
        "field, the disclosed multi-year vesting/retention horizon in Form 4 "
        "footnotes, but risk remains high because many grants are routine "
        "compensation rather than demand."
    ),
    "recorded_at": "2026-06-20T15:05:12+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv": True,
    "uses_free_sec_form4": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $25M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing Form 4 usable_trade_date, missing multi-year vesting "
            "footnote, same-accession open-market sale, insufficient retained "
            "ownership, missing OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same Form 4 "
        "footnotes, multi-year vesting horizon, same-accession sale exclusion, "
        "retained ownership ratio, price confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: Form 4 footnotes that disclose multi-year executive "
        "equity vesting with retained ownership may identify aligned leadership "
        "and constrained future supply better than raw A/M/S/F transaction-code "
        "context."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate blocked nearby Form 4 candidate-pool families. "
            "Override is recorded because the new evidence axis is parsed "
            "multi-year vesting/retention horizon and grant-retained ownership "
            "ratio from Form 4 footnotes, not transaction-code thresholds."
        ),
        "exp-20260616-013": (
            "Rejected raw Form 4 exercise-and-hold rows. This run requires "
            "explicit multi-year vesting or retention footnote evidence."
        ),
        "exp-20260616-017": (
            "Rejected SBC per-share / buyback-adjusted Form 4 refinement. This "
            "run is a standalone Form 4 footnote provenance source, not an SBC "
            "ratio variant."
        ),
        "exp-20260620-004": (
            "Rejected fixed A/M versus S/F Form 4 context scalars on the accepted "
            "SBC helper. This run does not change SBC notional and does not "
            "sweep A/M/S/F code lists."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_016_form4_multiyear_equity_retention.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _num(value: str) -> int | None:
    text = value.lower().strip()
    if text.isdigit():
        return int(text)
    return WORD_NUMBERS.get(text)


def _vesting_horizon_years(text: str, usable_trade_date: str) -> float | None:
    lowered = text.lower()
    if not TEXT_HINT_RE.search(lowered):
        return None
    usable_year = int(str(usable_trade_date)[:4])
    candidates: list[float] = []
    years = [int(match.group(1)) for match in YEAR_RE.finditer(lowered)]
    future_years = [year for year in years if year >= usable_year]
    if future_years:
        candidates.append(float(max(future_years) - usable_year))
    for match in DURATION_RE.finditer(lowered):
        if "multi" in match.group(0).lower():
            candidates.append(2.0)
            continue
        number = _num(match.group(1) or match.group(2) or "")
        if number is not None:
            candidates.append(float(number))
    if not candidates:
        return None
    horizon = max(candidates)
    if horizon < MIN_VESTING_HORIZON_YEARS:
        return None
    return horizon


def _load_form4_rows(*, max_filed: str, tickers: list[str]) -> list[dict[str, Any]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    for path in sorted(FORM4_DIR.glob("form4_transactions_*.jsonl")):
        date_key = path.stem.rsplit("_", 1)[-1]
        if len(date_key) == 8 and f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}" > max_filed:
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper()
                if ticker not in ticker_set:
                    continue
                usable = str(row.get("usable_trade_date") or "")[:10]
                if not usable or usable > max_filed:
                    continue
                if row.get("pit_safe_flag") is False:
                    continue
                key = (
                    row.get("accession_number"),
                    row.get("owner_cik"),
                    row.get("transaction_code"),
                    row.get("acquired_disposed_code"),
                    row.get("table"),
                    row.get("security_title"),
                    row.get("transaction_date"),
                    row.get("shares"),
                    row.get("underlying_security_shares"),
                )
                rows[key] = row
    return list(rows.values())


def _build_quality_index(
    form4_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in form4_rows:
        accession = str(row.get("accession_number") or "")
        if accession:
            by_accession[accession].append(row)

    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    stats: Counter[str] = Counter()
    seen_events: set[tuple[str, str, str]] = set()
    for accession, accession_rows in by_accession.items():
        has_sale = any(str(row.get("transaction_code") or "").upper() in SALE_CODES for row in accession_rows)
        has_10b5 = any(bool(row.get("10b5_1_flag")) for row in accession_rows)
        if has_sale:
            stats["accessions_rejected_same_accession_sale"] += 1
        if has_10b5:
            stats["accessions_rejected_10b5_1"] += 1
        for row in accession_rows:
            ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper()
            usable = str(row.get("usable_trade_date") or "")[:10]
            if not ticker or not usable:
                stats["rows_missing_ticker_or_usable_date"] += 1
                continue
            if str(row.get("transaction_code") or "").upper() not in ACQUISITION_CODES:
                stats["rows_rejected_non_acquisition_code"] += 1
                continue
            if str(row.get("acquired_disposed_code") or "").upper() != "A":
                stats["rows_rejected_not_acquired"] += 1
                continue
            if not (row.get("is_officer") or row.get("is_director")):
                stats["rows_rejected_not_officer_or_director"] += 1
                continue
            if str(row.get("direct_or_indirect") or "").upper() not in {"", "D"}:
                stats["rows_rejected_indirect_ownership"] += 1
                continue
            if has_sale or has_10b5:
                stats["rows_rejected_accession_sale_or_10b5_1"] += 1
                continue
            footnote = str(row.get("footnote_text") or "")
            horizon = _vesting_horizon_years(footnote, usable)
            if horizon is None:
                stats["rows_rejected_no_multiyear_vesting_text"] += 1
                continue
            grant_shares = _float_or_none(row.get("underlying_security_shares"))
            if grant_shares is None or grant_shares <= 0.0:
                grant_shares = _float_or_none(row.get("shares"))
            shares_owned = _float_or_none(row.get("shares_owned_following_transaction"))
            if grant_shares is None or grant_shares < MIN_GRANT_SHARES:
                stats["rows_rejected_small_or_missing_grant_shares"] += 1
                continue
            retained_ratio = None
            if shares_owned is not None and grant_shares > 0.0:
                retained_ratio = shares_owned / grant_shares
                if retained_ratio < MIN_RETAINED_TO_GRANT_RATIO:
                    stats["rows_rejected_low_retained_ratio"] += 1
                    continue
            event_key = (ticker, usable, accession)
            if event_key in seen_events:
                stats["events_deduped"] += 1
                continue
            seen_events.add(event_key)
            event = {
                "ticker": ticker,
                "date": usable,
                "accepted_at": str(row.get("accepted_at") or ""),
                "accession_number": accession,
                "owner_name": row.get("owner_name"),
                "owner_cik": row.get("owner_cik"),
                "officer_title": row.get("officer_title"),
                "is_officer": bool(row.get("is_officer")),
                "is_director": bool(row.get("is_director")),
                "transaction_code": row.get("transaction_code"),
                "security_title": row.get("security_title"),
                "grant_shares": _round(grant_shares, 2),
                "shares_owned_following_transaction": _round(shares_owned, 2),
                "retained_to_grant_ratio": _round(retained_ratio, 6),
                "vesting_horizon_years": _round(horizon, 2),
                "footnote_excerpt": footnote[:320],
            }
            index.setdefault(ticker, {"events": []})["events"].append(event)
            stats["events_accepted"] += 1
    for payload in index.values():
        payload["events"].sort(key=lambda row: (row["date"], row["ticker"], row["accession_number"]))
    return index, {
        "form4_rows_loaded": len(form4_rows),
        "accessions_seen": len(by_accession),
        "tickers_with_multiyear_retention_events": len(index),
        **dict(stats),
    }


def _price_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = base.framework.shadow._series(snapshot, ticker)
    spy_rows = base.framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = base.framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = base.framework._daily_return(rows, idx)
    close_location = base.framework._close_location(rows[idx])
    ret20 = base.framework._ret(rows, idx, 20)
    ret60 = base.framework._ret(rows, idx, 60)
    spy_ret20 = base.framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = base.framework._ret(spy_rows, spy_idx, 60)
    realized_vol = base.framework._realized_vol(rows, idx, 20)
    if any(
        value is None
        for value in (signal_return, close_location, ret20, ret60, spy_ret20, spy_ret60, realized_vol)
    ):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = base.framework._volume_ratio(rows, idx) or 0.0
    return {
        "candidate_close": _round(close, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = {day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])}
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_form4_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for ticker in eligible:
        for event in quality_index[ticker].get("events", []):
            signal_date = str(event["date"])
            if signal_date not in window_dates:
                scan["events_outside_window"] += 1
                continue
            scan["event_rows_evaluated"] += 1
            confirm = _price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            grant_value = float(event["grant_shares"] or 0.0) * float(confirm["candidate_close"] or 0.0)
            retained_ratio = float(event.get("retained_to_grant_ratio") or 1.0)
            horizon = float(event["vesting_horizon_years"] or 0.0)
            score = (
                0.85 * min(horizon, 5.0)
                + 0.25 * min(math.log10(max(grant_value, 1.0)), 8.0)
                + 0.20 * min(retained_ratio, 5.0)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
            )
            meta = sector_entries.get(ticker, {})
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "FORM4_MULTIYEAR_EQUITY_RETENTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "form4_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_form4": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "form4_grant_value_proxy_usd": _round(grant_value, 2),
                    **{f"form4_{key}": value for key, value in event.items()},
                    **confirm,
                }
            )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["form4_vesting_horizon_years"] or 0.0),
            -float(row["form4_grant_value_proxy_usd"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_vesting_horizon_years": MIN_VESTING_HORIZON_YEARS,
        "min_retained_to_grant_ratio": MIN_RETAINED_TO_GRANT_RATIO,
        "min_grant_shares": MIN_GRANT_SHARES,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_form4_multiyear_equity_retention"
        if gate["passed"]
        else "rejected_form4_multiyear_equity_retention_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Form4 tickers | Raw rows | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_form4_tickers", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form 4 Multi-Year Equity Retention",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_form4_rows
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The Form 4 multi-year equity-retention source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The Form 4 multi-year equity-retention source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected",
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_form4_footnote_retention_candidate_pool",
            "new_evidence_type": "parsed_form4_multiyear_vesting_retention_footnote",
            "nearby_prior_experiments": [
                "exp-20260616-013",
                "exp-20260616-017",
                "exp-20260620-004",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "acquisition_codes": sorted(ACQUISITION_CODES),
        "sale_codes_excluded_same_accession": sorted(SALE_CODES),
        "min_grant_shares": MIN_GRANT_SHARES,
        "min_retained_to_grant_ratio": MIN_RETAINED_TO_GRANT_RATIO,
        "min_vesting_horizon_years": MIN_VESTING_HORIZON_YEARS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(FORM4_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "SEC Form 4 rows are keyed by usable_trade_date and accepted_at. The "
        "parser admits only officer/director acquisition rows with explicit "
        "multi-year vesting or retention language in footnotes, retained direct "
        "ownership, no same-accession open-market sale, and no 10b5-1 flag. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "Form 4 usable_trade_date and accepted_at",
        "Form 4 accession_number",
        "Form 4 footnote_text",
        "Form 4 officer/director/direct ownership flags",
        "Form 4 transaction_code and acquired_disposed_code",
        "Form 4 shares, underlying_security_shares, shares_owned_following_transaction",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer executive-compensation provenance, such "
        "as grant fair value from proxy data, vesting/lockup terms tied to "
        "actual retention outcomes, executive ownership percentage, or closed "
        "forward replacement-value rows from a shared daily Form 4 retention "
        "helper. Do not sweep Form 4 transaction-code lists, role filters, "
        "10b5-1 handling, vesting-year threshold, RS/close/volume guards, top-N, "
        "hold, cooldown, or notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping Form 4 A/M/S/F code lists, owner roles, "
            "10b5-1 handling, vesting-year threshold, retained-ratio threshold, "
            "grant-share threshold, RS/close/volume/vol guards, top-N, hold "
            "days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
