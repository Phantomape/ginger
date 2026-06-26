"""exp-20260624-022: SEC offering richer-terms constructive financing.

Alpha search with one fixed decision bundle. The prior raw offering and
primary-text economics attempts were rejected, but exp-20260624-021
materialized richer PIT financing terms. This runner tests whether those
terms identify constructive capital raises rather than dilution noise.

No live/default orders, ranking, sizing, exits, LLM/news behavior, or daily
production adapters are changed by this runner.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260620_018_sec_offering_primary_text_economics as prior  # noqa: E402
import exp_20260624_021_sec_offering_richer_financing_terms as richer  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260624-022"
OWNER = "alpha-explore"
STEM = "sec_offering_richer_terms_constructive_financing"
TRIAL_FAMILY = "sec_offering_richer_terms_constructive_financing_candidate_pool"
TRIAL_VARIANT_ID = "top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_offering_richer_terms_constructive_financing_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260624_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

MIN_TAKEDOWN_USD = 50_000_000.0
MAX_TAKEDOWN_USD = 30_000_000_000.0
MAX_AMOUNT_TO_MARKET_CAP = 0.70
MAX_ACTUAL_TO_SHELF_RATIO = 1.35
MAX_FLOAT_DILUTION_PCT = 0.06
ALLOWED_SECURITY_TYPES = {"debt_notes", "convertible_debt"}
ALLOWED_STATUSES = {"completed_or_issued", "priced"}
CONSTRUCTIVE_USES = {"growth_project_or_capacity", "debt_refinancing"}
TOP_UNDERWRITER_BUCKETS = {"single_top_tier", "multiple_top_tier"}

PREDICTION = {
    "success_probability": 0.26,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "thin_sample",
        "accepted_distribution_comparator_not_beaten",
        "offering_terms_still_dilution_noise",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Raw offering form absorption and primary-text economics were rejected, "
        "but exp-20260624-021 materialized a materially richer PIT SEC financing "
        "ledger with actual takedown, shelf ratio, underwriter quality, "
        "lockup/hedging, and float-dilution fields across all three windows. "
        "The mechanism is constructive capital access after price absorption; "
        "the main disconfirmer is that offering events remain dilution or "
        "capital-structure noise and fail accepted comparators."
    ),
    "recorded_at": "2026-06-24T19:04:20+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "experiment_owned_replay_no_live_adapter",
    "implementation_mode": "candidate_pool_full_stack_replay_attempt",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "trade_enabled": False,
    "live_ready": False,
    "uses_free_sec_filing_text": True,
    "uses_richer_sec_offering_terms": True,
    "uses_free_sec_companyfacts": True,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "capital_cap": "8% paper sleeve cap; no live capital enabled",
        "liquidity_slippage_model": "ADV20 >= $50M; existing next-open/slippage/cost model",
        "portfolio_displacement": "default-off additive paper overlay; no core displacement",
        "max_concurrent": HOLD_DAYS * MAX_PAPER_TRADES_PER_DAY,
        "order_semantics": "next available open paper entry, close after 10 trading days",
        "kill_switch": "paper-only; proposed 5% sleeve drawdown review before live consideration",
        "failure_handling": (
            "missing richer SEC term, stale/missing shares denominator, missing "
            "OHLCV/next open/10d exit, high float dilution, non-top-tier "
            "underwriter, unsupported security type, or failed price confirmation "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment reuses a single candidate builder for replay and an "
        "artifact-level daily snapshot semantics block, but does not wire a "
        "daily production adapter. A positive result would remain a lead until "
        "a shared default-off helper and parity test are promoted."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: richer SEC offering/prospectus terms may distinguish "
        "constructive financing from raw dilution events when completed/priced "
        "debt or convertible offerings have top-tier underwriting, non-excessive "
        "actual takedown versus shelf capacity, low measured float dilution, "
        "constructive use/hedging context, and signal-day price absorption."
    ),
    "2_history_check": {
        "exp-20260617-023": (
            "Rejected raw offering/prospectus form price absorption. This run "
            "does not sweep form lists or price thresholds."
        ),
        "exp-20260620-018": (
            "Rejected primary-text amount/security/use economics and required "
            "actual takedown vs shelf capacity, dilution, underwriter quality, "
            "lockup/hedging, closed deal outcome, or forward rows before retry."
        ),
        "exp-20260624-021": (
            "Accepted measurement repair that materialized the richer financing "
            "terms used here."
        ),
        "novelty_gate": (
            "Gate classified the text-ledger idea as companyfacts_ratio; novelty "
            "and saturated-source overrides were recorded because Companyfacts "
            "is only the PIT shares denominator, not the scanned alpha source."
        ),
    },
    "3_single_policy_bundle": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical windows. Aggregate EV/PnL must be "
        "positive, no window EV/PnL regression, at least two EV-improved windows, "
        "sufficient target trades across all three windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution comparators must be beaten."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260624_022_sec_offering_richer_terms_constructive_financing.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    return prior._float_or_none(value)


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    allowed = {ticker.upper() for ticker in tickers or []}
    rows, _file_audit = richer.iter_sec_text_rows()
    rows, _shares_audit = richer.attach_float_dilution(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        usable_date = str(row.get("usable_trade_date") or "")[:10]
        if allowed and ticker not in allowed:
            continue
        if not usable_date or usable_date > max_filed:
            continue
        enriched = dict(row)
        enriched["ticker"] = ticker
        enriched["date"] = usable_date
        out.append(enriched)
    return out


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    security_counter: Counter[str] = Counter()
    use_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    underwriter_counter: Counter[str] = Counter()
    richer_field_counter: Counter[str] = Counter()
    amount_sum = 0.0
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        by_ticker[ticker].append(row)
        security_counter[str(row.get("security_type") or "unknown")] += 1
        use_counter[str(row.get("use_of_proceeds") or "unknown")] += 1
        status_counter[str(row.get("offering_status") or "unknown")] += 1
        underwriter_counter[str(row.get("underwriter_quality_bucket") or "unknown")] += 1
        amount_sum += float(row.get("actual_takedown_amount_usd") or row.get("financing_amount_usd") or 0.0)
        for field in row.get("richer_fields_materialized") or []:
            richer_field_counter[str(field)] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                str(row.get("date") or ""),
                -float(row.get("richer_field_count") or 0.0),
                -float(row.get("top_tier_underwriter_count") or 0.0),
                -float(row.get("actual_takedown_amount_usd") or 0.0),
                str(row.get("accession_number") or ""),
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_richer_term_rows_loaded": len(text_rows),
        "tickers_with_richer_terms": len(by_ticker),
        "total_actual_takedown_amount_usd": round(amount_sum, 2),
        "security_type_counts": dict(security_counter),
        "use_of_proceeds_counts": dict(use_counter),
        "offering_status_counts": dict(status_counter),
        "underwriter_quality_counts": dict(underwriter_counter),
        "richer_field_counts": dict(richer_field_counter),
        "text_source": _repo_rel(richer.TEXT_DIR),
        "source_measurement_repair": "exp-20260624-021",
        "rule_version": RULE_VERSION,
    }


def _constructive_gate(event: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    status = str(event.get("offering_status") or "")
    security_type = str(event.get("security_type") or "")
    use_of_proceeds = str(event.get("use_of_proceeds") or "")
    underwriter_bucket = str(event.get("underwriter_quality_bucket") or "")
    top_tier_count = int(event.get("top_tier_underwriter_count") or 0)
    amount = _float_or_none(event.get("actual_takedown_amount_usd") or event.get("financing_amount_usd"))
    ratio = _float_or_none(event.get("actual_to_shelf_ratio"))
    float_dilution = _float_or_none(event.get("float_dilution_pct"))
    hedged_or_locked = bool(event.get("lockup_or_hedging_terms_present"))

    if status not in ALLOWED_STATUSES:
        reasons.append("status_not_completed_or_priced")
    if security_type not in ALLOWED_SECURITY_TYPES:
        reasons.append("security_not_debt_or_convertible")
    if amount is None or amount < MIN_TAKEDOWN_USD:
        reasons.append("actual_takedown_too_small")
    if amount is not None and amount > MAX_TAKEDOWN_USD:
        reasons.append("actual_takedown_too_large")
    if ratio is not None and (ratio <= 0.0 or ratio > MAX_ACTUAL_TO_SHELF_RATIO):
        reasons.append("actual_to_shelf_ratio_outside_quality_band")
    if float_dilution is not None and float_dilution > MAX_FLOAT_DILUTION_PCT:
        reasons.append("float_dilution_too_high")
    if underwriter_bucket not in TOP_UNDERWRITER_BUCKETS and top_tier_count <= 0:
        reasons.append("no_top_tier_underwriter")
    if use_of_proceeds not in CONSTRUCTIVE_USES and top_tier_count < 2 and not hedged_or_locked:
        reasons.append("no_constructive_use_or_extra_quality_context")
    if security_type == "convertible_debt" and not hedged_or_locked and float_dilution is None:
        reasons.append("convertible_without_hedge_or_dilution_measure")
    return not reasons, reasons


def _quality_score(event: dict[str, Any], confirm: dict[str, Any], amount_to_market_cap: float) -> float:
    top_tier_count = min(int(event.get("top_tier_underwriter_count") or 0), 3)
    use_of_proceeds = str(event.get("use_of_proceeds") or "")
    ratio = _float_or_none(event.get("actual_to_shelf_ratio"))
    float_dilution = _float_or_none(event.get("float_dilution_pct"))
    amount = _float_or_none(event.get("actual_takedown_amount_usd") or event.get("financing_amount_usd")) or 1.0
    use_component = 0.85 if use_of_proceeds == "growth_project_or_capacity" else 0.35
    shelf_component = 0.20 if ratio is None else max(0.0, (MAX_ACTUAL_TO_SHELF_RATIO - ratio) / MAX_ACTUAL_TO_SHELF_RATIO)
    dilution_component = 0.25 if float_dilution is None else max(0.0, (MAX_FLOAT_DILUTION_PCT - float_dilution) / MAX_FLOAT_DILUTION_PCT)
    hedge_component = 0.30 if event.get("lockup_or_hedging_terms_present") else 0.0
    materiality_component = min(amount_to_market_cap / 0.01, 6.0)
    amount_component = min(max(math.log10(max(amount, 1.0)) - 7.5, 0.0), 3.0)
    return (
        0.55 * top_tier_count
        + use_component
        + 0.45 * shelf_component
        + 0.35 * dilution_component
        + hedge_component
        + 0.22 * materiality_component
        + 0.18 * amount_component
        + 0.55 * float(confirm["candidate_ret20_excess_spy"])
        + 0.18 * float(confirm["candidate_ret60_excess_spy"])
        + 0.10 * float(confirm["candidate_close_location"])
        + 0.020 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: prior.base.framework.shadow._row_index(prior.base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in list(quality_index[ticker].get("events") or []):
            signal_date = str(event.get("date") or "")[:10]
            if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
                continue
            scan["event_rows_in_window"] += 1
            passed, reasons = _constructive_gate(event)
            if not passed:
                scan["failed_constructive_terms"] += 1
                for reason in reasons:
                    scan[f"failed_{reason}"] += 1
                continue
            confirm = prior.base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            amount = _float_or_none(event.get("actual_takedown_amount_usd") or event.get("financing_amount_usd"))
            shares = _float_or_none(event.get("shares_outstanding"))
            rows = prior.base.framework.shadow._series(snapshot, ticker)
            idx = indices.get(ticker, {}).get(signal_date)
            if amount is None or amount <= 0.0:
                scan["missing_actual_takedown_amount"] += 1
                continue
            if shares is None or shares <= 0.0:
                scan["missing_pit_shares_outstanding"] += 1
                continue
            if idx is None:
                scan["missing_signal_idx_for_market_cap"] += 1
                continue
            close = prior.base.framework._value(rows[idx], "Close")
            if close is None or close <= 0.0:
                scan["missing_signal_close_for_market_cap"] += 1
                continue
            market_cap = float(close) * shares
            amount_to_market_cap = amount / market_cap if market_cap > 0.0 else None
            if amount_to_market_cap is None or amount_to_market_cap <= 0.0:
                scan["invalid_amount_to_market_cap"] += 1
                continue
            if amount_to_market_cap > MAX_AMOUNT_TO_MARKET_CAP:
                scan["failed_max_amount_to_market_cap_sanity"] += 1
                continue
            score = _quality_score(event, confirm, amount_to_market_cap)
            meta = sector_entries.get(ticker, {})
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_security_{event.get('security_type') or 'unknown'}"] += 1
            scan[f"qualified_use_{event.get('use_of_proceeds') or 'unknown'}"] += 1
            scan[f"qualified_underwriter_{event.get('underwriter_quality_bucket') or 'unknown'}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_OFFERING_RICHER_TERMS_CONSTRUCTIVE_FINANCING_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_companyfacts": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "financing_amount_to_market_cap": _round(amount_to_market_cap, 6),
                    "financing_market_cap_usd": _round(market_cap, 2),
                    "financing_signal_day_close_for_market_cap": _round(close, 4),
                    **{f"financing_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
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
            -float(row.get("financing_top_tier_underwriter_count") or 0.0),
            -float(row.get("financing_amount_to_market_cap") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_takedown_usd": MIN_TAKEDOWN_USD,
        "max_takedown_usd": MAX_TAKEDOWN_USD,
        "max_amount_to_market_cap": MAX_AMOUNT_TO_MARKET_CAP,
        "max_actual_to_shelf_ratio": MAX_ACTUAL_TO_SHELF_RATIO,
        "max_float_dilution_pct": MAX_FLOAT_DILUTION_PCT,
        "allowed_security_types": sorted(ALLOWED_SECURITY_TYPES),
        "allowed_statuses": sorted(ALLOWED_STATUSES),
        "constructive_uses": sorted(CONSTRUCTIVE_USES),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= prior.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= prior.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= prior.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= prior.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = prior.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = prior.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_offering_richer_terms_constructive_financing"
        if gate["passed"]
        else "rejected_sec_offering_richer_terms_constructive_financing_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("event_rows_in_window", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Offering Richer-Terms Constructive Financing",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Gate 4 passed: `{payload['gate4']['passed']}`",
            "- Production impact: no live/default behavior changed.",
            "",
            "## Hypothesis",
            "",
            PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "",
            "## Three-window Gate 4",
            "",
            *rows,
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _execution_envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.08,
        min_dollar_volume=prior.base.MIN_AVG_DOLLAR_VOLUME_20D,
        slippage_bps=85.0,
        max_displacement=0,
        max_concurrent=HOLD_DAYS * MAX_PAPER_TRADES_PER_DAY,
        order_semantics="next_open_paper_entry_close_after_10_trading_days",
        kill_switch_drawdown_pct=0.05,
        sleeve_drawdown_stop_pct=0.08,
        notes="Default-off paper only; no live orders or core displacement.",
    )


def _add_full_stack_block(payload: dict[str, Any]) -> None:
    gate4 = payload["gate4"]
    envelope = _execution_envelope()
    live_readiness = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    helper_gate4 = {
        "passed": bool(gate4.get("passed")),
        "status": "passed" if gate4.get("passed") else "blocked",
        "hard_failures": list(gate4.get("failed_reasons") or []),
        "source_gate4": gate4,
    }
    verdict = full_stack_verdict(
        gate4=helper_gate4,
        live_readiness=live_readiness,
        envelope=envelope,
    )
    verdict["contract_completeness"] = {
        "shared_helper_promoted": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "parity_test_added": False,
        "note": (
            "This run records the full-stack envelope and replay verdict, but "
            "does not promote shared daily production code. Positive numeric "
            "results would remain a lead until shared helper/parity work exists."
        ),
    }
    payload["full_stack"] = verdict


def _configure_base() -> None:
    prior.base.EXPERIMENT_ID = EXPERIMENT_ID
    prior.base.STEM = STEM
    prior.base.TRIAL_FAMILY = TRIAL_FAMILY
    prior.base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.base.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.base.RULE_VERSION = RULE_VERSION
    prior.base.OWNER = OWNER
    prior.base.OUT_DIR = OUT_DIR
    prior.base.OUT_JSON = OUT_JSON
    prior.base.LOG_JSON = LOG_JSON
    prior.base.TICKET_JSON = TICKET_JSON
    prior.base.CARD_MD = CARD_MD
    prior.base.MANIFEST_JSON = MANIFEST_JSON
    prior.base.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.base.REGISTRY_JSON = REGISTRY_JSON
    prior.base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    prior.base.HOLD_DAYS = HOLD_DAYS
    prior.base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    prior.base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    prior.base.PREDICTION = PREDICTION
    prior.base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior.base.load_companyfacts_rows = _load_sec_text_rows
    prior.base._build_quality_index = _build_quality_index
    prior.base._candidate_rows_for_window = _candidate_rows_for_window
    prior.base._gate4 = _gate4
    prior.base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The richer SEC offering constructive-financing bundle cleared the "
            "numeric three-window replay screen, but no shared daily adapter was "
            "promoted in this run, so it remains a replay lead."
        )
        status = "positive_replay_lead_not_promoted"
        accepted = False
    else:
        interpretation = (
            "The richer SEC offering constructive-financing bundle did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
        status = "rejected"
        accepted = False
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": accepted,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "experiment_owned_full_stack_replay_attempt",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_offering_primary_text_economics_candidate_pool",
            "new_evidence_type": "richer_pit_offering_terms_field_build",
            "nearby_prior_experiments": [
                "exp-20260617-023",
                "exp-20260620-018",
                "exp-20260624-021",
            ],
            "prior_trial_count": 2,
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
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4.get("failed_reasons") or [])
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_takedown_usd": MIN_TAKEDOWN_USD,
        "max_takedown_usd": MAX_TAKEDOWN_USD,
        "max_amount_to_market_cap": MAX_AMOUNT_TO_MARKET_CAP,
        "max_actual_to_shelf_ratio": MAX_ACTUAL_TO_SHELF_RATIO,
        "max_float_dilution_pct": MAX_FLOAT_DILUTION_PCT,
        "allowed_security_types": sorted(ALLOWED_SECURITY_TYPES),
        "allowed_statuses": sorted(ALLOWED_STATUSES),
        "constructive_uses": sorted(CONSTRUCTIVE_USES),
        "top_underwriter_buckets": sorted(TOP_UNDERWRITER_BUCKETS),
        "min_price": prior.base.MIN_PRICE,
        "min_avg_dollar_volume_20d": prior.base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": prior.base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": prior.base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": prior.base.MIN_SIGNAL_RETURN,
        "max_signal_return": prior.base.MAX_SIGNAL_RETURN,
        "min_close_location": prior.base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": prior.base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(richer.TEXT_DIR)
    payload["backtest_protocol"]["source_measurement_repair"] = "exp-20260624-021"
    payload["backtest_protocol"]["execution_model"] = (
        "Richer SEC offering terms are keyed by accepted_at/usable_trade_date. "
        "The fixed bundle admits only completed/priced debt or convertible "
        "financings with top-tier underwriting, non-excessive actual takedown "
        "versus shelf capacity when present, float dilution <=6% when measured, "
        "constructive use or extra quality context, and signal-day OHLCV price "
        "absorption. Paper entry is next available open; exit is the close 10 "
        "trading days after the signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text accepted_at and usable_trade_date",
        "SEC accession_number and primary_document",
        "actual_takedown_amount_usd",
        "shelf_capacity_amount_usd and actual_to_shelf_ratio",
        "underwriter_quality_bucket and top_tier_underwriter_count",
        "lockup_or_hedging_terms_present",
        "shares_offered, shares_outstanding, and float_dilution_pct",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs closed forward replacement-value rows under this exact "
        "richer-term envelope, verified deal-close/lockup economics, or a "
        "different PIT field such as actual shelf drawdown history. Do not sweep "
        "offering regexes, amount/market-cap thresholds, security/use weights, "
        "underwriter buckets, float-dilution cuts, RS/close/volume guards, top-N, "
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
            "Do not retry by sweeping the same richer offering-term thresholds, "
            "regexes, security/use labels, underwriter buckets, float-dilution "
            "limits, RS/close/volume/volatility guards, top-N, hold days, "
            "cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    _add_full_stack_block(payload)
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
        "quant/experiments/exp_20260624_021_sec_offering_richer_financing_terms.py",
        "data/experiments/exp-20260624-021/exp_20260624_021_sec_offering_richer_financing_terms.json",
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    log_record = prior.base._build_log_record(payload)
    prior.base.framework._write_json(OUT_JSON, payload)
    prior.base.framework._write_json(LOG_JSON, payload)
    prior.base.framework._write_text(CARD_MD, _build_card(payload))
    prior.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    prior.base.persist_self_registered_result(
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
            _repo_rel(Path(__file__)): prior.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.base.framework._sha256(CARD_MD),
        },
    }
    prior.base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(prior.base._build_payload())
    _persist(payload)
    print(json.dumps(prior.base.framework._safe(prior.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
