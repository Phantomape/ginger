"""exp-20260616-012: Form 4 post-sale retention absorption candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
PIT-safe Form 4 non-derivative sale rows where the reporting insider retains
at least 90% of the inferred pre-sale share stake after the sale. The OHLCV
leadership envelope, top-1 next-open paper entry, 10-trading-day exit, costs,
cooldown, and Gate 4 comparators are inherited from exp-20260611-026.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260611_026_form4_sale_absorption_leadership as sale


framework = sale.framework
base = sale.base

EXPERIMENT_ID = "exp-20260616-012"
STEM = "form4_post_sale_retention_absorption"
TRIAL_FAMILY = "form4_post_sale_retention_absorption_candidate_pool"
TRIAL_VARIANT_ID = "form4_post_sale_retention_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form4_post_sale_retention_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = sale.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FORM4_DIR = sale.FORM4_DIR
FORM4_GLOB = sale.FORM4_GLOB

MIN_POST_SALE_RETENTION_RATIO = 0.90

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "thin_sample",
        "retention_field_noisy_or_missing",
        "routine_sales_still_overhang",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The base Form 4 sale absorption scout was rejected and froze "
        "threshold/role/10b5-1 retunes, but its closeout explicitly named "
        "post-sale ownership-retention as the new PIT evidence required for "
        "a valid retry. The local Form 4 archive exposes shares and "
        "shares_owned_following_transaction, so this tests materially "
        "different supply-overhang quality evidence."
    ),
    "recorded_at": "2026-06-16T10:11:34+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_form4": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain only a replay lead. Promotion would require one shared "
        "default-off adapter that loads the same PIT Form 4 transaction rows, "
        "computes the same post-sale retention ratio from shares and "
        "shares_owned_following_transaction, applies the same >=90% retention "
        "gate, non-derivative sale definition, minimum sale value, signal-date "
        "OHLCV leadership envelope, same-ticker core overlap exclusion, top-1 "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, "
        "comparator, and concentration guards in both historical replay and "
        "daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: large PIT-safe Form 4 insider sales are less bearish "
        "when the seller retains at least 90% of inferred pre-sale ownership, "
        "because the disclosure is more likely routine liquidity or "
        "diversification than true exit pressure. Same-day liquid "
        "SPY-relative leadership then tests whether demand absorbed the "
        "visible insider supply before next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260611-026": (
            "Rejected raw Form 4 sale absorption. Its reflection forbids "
            "threshold, role, 10b5-1, top-N, notional, hold-day, or cooldown "
            "retunes, but explicitly says a retry needs post-sale ownership "
            "retention context."
        ),
        "exp-20260612-023": (
            "Rejected Form 144 sale-notice absorption despite positive EV/PnL "
            "because drawdown drift was too high; Form 144 needs parsed "
            "sale/float fields before promotion pressure."
        ),
        "exp-20260613-013": (
            "Rejected isolated Form 144 sale-notice absorption because "
            "old_thin regressed and drawdown drift was unacceptable."
        ),
        "exp-20260615-024": (
            "Rejected Form 4 CEO/CFO low-liability purchase source. This run "
            "does not retry purchases; it tests sale-side post-transaction "
            "ownership retention as a supply-overhang discriminator."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT-safe Form 4 non-derivative sale rows "
        "must have transaction_code=S, acquired_disposed_code=D, usable_trade_"
        "date, row value >= $100k, same ticker-day sale value >= $1M, and "
        "post_sale_retention_ratio = post_sale_shares / "
        "(post_sale_shares + sold_shares) >= 0.90. The exp-20260611-026 "
        "liquid leadership envelope, same-ticker core overlap exclusion, "
        "top-1 next-open paper entry, 10-day hold, costs, cooldown, "
        "comparator, and concentration gates are inherited unchanged."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival "
        ">=5%, drawdown drift <=0.5pp, concentration guard passes, and both "
        "accepted compression and distribution comparators are beaten. A "
        "shared default-off helper and daily parity path are required for any "
        "retention."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_012_form4_post_sale_retention_absorption.py"
    ),
}

_BASE_ELIGIBLE_SALE_ROW = sale._eligible_sale_row
_BASE_EVENT_FROM_ROW = sale._event_from_row
_BASE_SALE_STATS = sale._sale_stats
_BASE_CANDIDATE_FOR_TICKER = sale._candidate_for_sale_absorption_ticker
_BASE_CANDIDATE_ROWS_FOR_WINDOW = sale._candidate_rows_for_window
_BASE_BUILD_PAYLOAD = sale._build_payload
_BASE_BUILD_CARD = sale._build_card
_BASE_BUILD_LOG_RECORD = sale._build_log_record

_EVENT_CACHE: dict[str, Any] | None = None


def _post_sale_retention_ratio(row: dict[str, Any]) -> float | None:
    sold_shares = sale._float(row.get("shares"))
    post_sale_shares = sale._float(row.get("shares_owned_following_transaction"))
    if sold_shares is None or post_sale_shares is None:
        return None
    sold_shares = abs(float(sold_shares))
    post_sale_shares = float(post_sale_shares)
    if sold_shares <= 0.0 or post_sale_shares < 0.0:
        return None
    pre_sale_shares = sold_shares + post_sale_shares
    if pre_sale_shares <= 0.0:
        return None
    return post_sale_shares / pre_sale_shares


def _event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    event = _BASE_EVENT_FROM_ROW(row)
    sold_shares = abs(float(sale._float(row.get("shares")) or 0.0))
    post_sale_shares = float(
        sale._float(row.get("shares_owned_following_transaction")) or 0.0
    )
    price = sale._float(row.get("price"))
    ratio = _post_sale_retention_ratio(row)
    pre_sale_shares = sold_shares + post_sale_shares
    event.update(
        {
            "shares_owned_following_transaction": post_sale_shares,
            "post_sale_retention_ratio": round(float(ratio or 0.0), 6),
            "sold_shares_to_pre_sale_shares": round(
                sold_shares / pre_sale_shares, 6
            )
            if pre_sale_shares > 0.0
            else None,
            "post_sale_value_at_transaction_price": round(post_sale_shares * price, 2)
            if price is not None
            else None,
        }
    )
    return event


def _load_sale_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    files = sale._form4_files()
    scan: dict[str, Any] = {
        "source_dir": sale._repo_rel(FORM4_DIR),
        "source_glob": FORM4_GLOB,
        "source_file_count": len(files),
        "raw_rows": 0,
        "base_eligible_sale_rows": 0,
        "retention_missing_rows": 0,
        "retention_below_min_rows": 0,
        "eligible_sale_rows": 0,
        "duplicate_sale_rows": 0,
        "below_ticker_total_sale_value_rows": 0,
        "kept_sale_rows": 0,
        "sale_dates": 0,
        "sale_tickers": 0,
        "min_event_row_value_usd": sale.MIN_EVENT_ROW_VALUE_USD,
        "min_total_sale_value_usd": sale.MIN_TOTAL_SALE_VALUE_USD,
        "min_post_sale_retention_ratio": MIN_POST_SALE_RETENTION_RATIO,
    }
    ticker_distribution: Counter[str] = Counter()
    owner_role_distribution: Counter[str] = Counter()
    retention_bucket_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    staged: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            scan["raw_rows"] += 1
            row = json.loads(line)
            if not _BASE_ELIGIBLE_SALE_ROW(row):
                continue
            scan["base_eligible_sale_rows"] += 1
            ratio = _post_sale_retention_ratio(row)
            if ratio is None:
                scan["retention_missing_rows"] += 1
                continue
            if ratio < MIN_POST_SALE_RETENTION_RATIO:
                scan["retention_below_min_rows"] += 1
                continue
            key = sale._row_key(row)
            if key in seen:
                scan["duplicate_sale_rows"] += 1
                continue
            seen.add(key)
            event = _event_from_row(row)
            staged.setdefault(event["usable_trade_date"], {}).setdefault(
                event["ticker"], []
            ).append(event)
            scan["eligible_sale_rows"] += 1

    for signal_date, by_ticker in staged.items():
        for ticker, events in by_ticker.items():
            total_value = sum(float(event["transaction_value"]) for event in events)
            if total_value < sale.MIN_TOTAL_SALE_VALUE_USD:
                scan["below_ticker_total_sale_value_rows"] += len(events)
                continue
            by_date_ticker.setdefault(signal_date, {})[ticker] = events
            ticker_distribution[ticker] += len(events)
            scan["kept_sale_rows"] += len(events)
            for event in events:
                if event["is_officer"]:
                    owner_role_distribution["officer"] += 1
                if event["is_director"]:
                    owner_role_distribution["director"] += 1
                if event["is_10pct_owner"]:
                    owner_role_distribution["ten_pct_owner"] += 1
                bucket = int(float(event["post_sale_retention_ratio"]) * 20) / 20
                retention_bucket_distribution[f"{bucket:.2f}"] += 1
            if len(examples) < 20:
                top = sorted(
                    events,
                    key=lambda event: (
                        -float(event["transaction_value"]),
                        str(event.get("accepted_at") or ""),
                    ),
                )[0]
                examples.append(
                    {
                        "ticker": ticker,
                        "usable_trade_date": signal_date,
                        "event_count": len(events),
                        "total_sale_value": round(total_value, 2),
                        "top_owner_name": top.get("owner_name"),
                        "top_transaction_value": top.get("transaction_value"),
                        "top_post_sale_retention_ratio": top.get(
                            "post_sale_retention_ratio"
                        ),
                        "top_accession_number": top.get("accession_number"),
                        "any_10b5_1_flag": any(
                            bool(event.get("10b5_1_flag")) for event in events
                        ),
                    }
                )

    all_tickers = {
        ticker
        for tickers in by_date_ticker.values()
        for ticker in tickers
    }
    scan["sale_dates"] = len(by_date_ticker)
    scan["sale_tickers"] = len(all_tickers)
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))
    scan["owner_role_distribution"] = dict(sorted(owner_role_distribution.items()))
    scan["post_sale_retention_bucket_distribution"] = dict(
        sorted(retention_bucket_distribution.items())
    )

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": scan,
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_sale_events()["by_date_ticker"].get(signal_date, {})


def _sale_stats(events: list[dict[str, Any]], adv20: float) -> dict[str, Any]:
    stats = _BASE_SALE_STATS(events, adv20)
    total_value = max(float(stats["total_sale_value"]), 1.0)
    ratios = [float(event["post_sale_retention_ratio"]) for event in events]
    weighted_ratio = sum(
        float(event["post_sale_retention_ratio"])
        * float(event["transaction_value"])
        for event in events
    ) / total_value
    post_sale_value = sum(
        float(event.get("post_sale_value_at_transaction_price") or 0.0)
        for event in events
    )
    stats.update(
        {
            "min_post_sale_retention_ratio": round(min(ratios), 6),
            "max_post_sale_retention_ratio": round(max(ratios), 6),
            "weighted_post_sale_retention_ratio": round(weighted_ratio, 6),
            "post_sale_value_at_transaction_price": round(post_sale_value, 2),
        }
    )
    return stats


def _candidate_for_sale_absorption_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    row = _BASE_CANDIDATE_FOR_TICKER(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        events=events,
    )
    if row is None:
        return None

    stats = _sale_stats(events, float(row["candidate_avg_dollar_volume_20d"]))
    top_event = sorted(
        events,
        key=lambda event: (
            -float(event["transaction_value"]),
            str(event.get("accepted_at") or ""),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row.update(
        {
            "source": "FORM4_POST_SALE_RETENTION_ABSORPTION_PAPER",
            "strategy": "form4_post_sale_retention_absorption_candidate_pool",
            "rule_version": RULE_VERSION,
            "candidate_form4_min_post_sale_retention_ratio": stats[
                "min_post_sale_retention_ratio"
            ],
            "candidate_form4_weighted_post_sale_retention_ratio": stats[
                "weighted_post_sale_retention_ratio"
            ],
            "candidate_form4_max_post_sale_retention_ratio": stats[
                "max_post_sale_retention_ratio"
            ],
            "candidate_form4_post_sale_value_at_transaction_price": stats[
                "post_sale_value_at_transaction_price"
            ],
            "candidate_form4_top_post_sale_retention_ratio": top_event.get(
                "post_sale_retention_ratio"
            ),
            "candidate_form4_top_shares_owned_following_transaction": top_event.get(
                "shares_owned_following_transaction"
            ),
        }
    )
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, day_contexts, scan = _BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    scan["min_post_sale_retention_ratio"] = MIN_POST_SALE_RETENTION_RATIO
    scan["candidate_min_post_sale_retention_ratio"] = (
        round(
            min(
                float(row["candidate_form4_min_post_sale_retention_ratio"])
                for row in candidates
            ),
            6,
        )
        if candidates
        else None
    )
    top_by_date = {row["date"]: row for row in candidates}
    for context in day_contexts:
        top = top_by_date.get(context["date"])
        if top is None:
            continue
        context["top_candidate_min_post_sale_retention_ratio"] = top[
            "candidate_form4_min_post_sale_retention_ratio"
        ]
        context["top_candidate_weighted_post_sale_retention_ratio"] = top[
            "candidate_form4_weighted_post_sale_retention_ratio"
        ]
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = sale.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= sale.ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= sale.ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= sale.ACCEPTED_DISTRIBUTION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= sale.ACCEPTED_DISTRIBUTION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_pnl_not_beaten")
    gate["accepted_compression_comparator"] = sale.ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = sale.ACCEPTED_DISTRIBUTION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_form4_post_sale_retention_absorption"
        if gate["passed"]
        else "rejected_form4_post_sale_retention_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = _BASE_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT Form 4 transaction rows on usable_trade_date plus "
        "close-of-day OHLCV available on the signal date. Eligible sale rows "
        "must retain at least 90% of inferred pre-sale ownership after the "
        "reported sale. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_form4_ohlcv_candidate_pool",
            "new_evidence_type": "form4_post_sale_ownership_retention_plus_ohlcv_leadership",
            "nearby_prior_experiments": [
                "exp-20260611-026",
                "exp-20260612-023",
                "exp-20260613-013",
                "exp-20260615-024",
            ],
            "prior_trial_count": 4,
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that high retained "
                "ownership is common among large-cap founders and executives, "
                "so it does not neutralize sale-overhang information once "
                "next-open execution, costs, and accepted comparators are "
                "applied. Do not answer by sweeping retention thresholds, "
                "sale-value thresholds, owner roles, 10b5-1 flags, top-N, "
                "notional, hold days, or cooldown on these windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence beyond retained "
                "ownership, such as daily forward replacement value for sale "
                "clusters, parsed Form 144 float/sale-plan context, or a "
                "shared default-off daily Form 4 sale-retention adapter with "
                "closed forward observations. Pure threshold, role, 10b5-1, "
                "or liquidity retunes stay frozen."
            ),
        }
    )
    payload["parameters"]["min_post_sale_retention_ratio"] = (
        MIN_POST_SALE_RETENTION_RATIO
    )
    payload["parameters"]["single_causal_variable"] = CHANGED_VARIABLE
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["gate2_runtime_fields"]["form4_post_sale_retention_rows"] = (
        _load_sale_events()["scan"]
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The Form 4 post-sale retention source did not clear Gate 4. The "
            "retention field narrowed the sale source to routine trimming, "
            "but retained ownership did not create a distinct forward edge "
            "after leadership, execution, cost, concentration, and comparator "
            "checks."
            if not passed
            else (
                "The Form 4 post-sale retention source passed Gate 4, but it "
                "remains only a replay lead until one shared historical/daily "
                "helper proves parity with the same Form 4 retention and "
                "OHLCV semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping retention thresholds, sale-value "
            "thresholds, owner roles, 10b5-1 flags, top-N, notional, hold "
            "days, or cooldown on these windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The Form 4 post-sale retention absorption source passed as a "
        "replay-only lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The Form 4 post-sale retention absorption source was rejected; "
            "retained ownership did not establish a distinct free SEC Form "
            "4/OHLCV candidate-pool edge under the standard three-window "
            "protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        sale._repo_rel(Path(__file__)),
        sale._repo_rel(OUT_JSON),
        sale._repo_rel(LOG_JSON),
        sale._repo_rel(TICKET_JSON),
        sale._repo_rel(CARD_MD),
        sale._repo_rel(MANIFEST_JSON),
        sale._repo_rel(EXPERIMENT_LOG),
        sale._repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = _BASE_BUILD_CARD(payload)
    retention_note = "\n".join(
        [
            "",
            "## Retention Rule",
            "",
            (
                "- Post-sale retention ratio: "
                f"`>= {MIN_POST_SALE_RETENTION_RATIO:.2f}`"
            ),
            (
                "- Base eligible sale rows: "
                f"`{_load_sale_events()['scan']['base_eligible_sale_rows']}`"
            ),
            (
                "- Retention-qualified sale rows: "
                f"`{_load_sale_events()['scan']['eligible_sale_rows']}`"
            ),
            (
                "- Missing retention rows: "
                f"`{_load_sale_events()['scan']['retention_missing_rows']}`"
            ),
            (
                "- Below retention rows: "
                f"`{_load_sale_events()['scan']['retention_below_min_rows']}`"
            ),
        ]
    )
    return f"{card}\n{retention_note}\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _BASE_BUILD_LOG_RECORD(payload)
    record["mechanism_family"] = payload["mechanism_family"]
    record["trial_family"] = TRIAL_FAMILY
    record["trial_variant_id"] = TRIAL_VARIANT_ID
    record["changed_variable"] = CHANGED_VARIABLE
    record["single_causal_variable"] = CHANGED_VARIABLE
    record["new_evidence_type"] = payload["new_evidence_type"]
    record["min_post_sale_retention_ratio"] = MIN_POST_SALE_RETENTION_RATIO
    record["production_impact"] = PRODUCTION_IMPACT
    record["prediction"] = PREDICTION
    record["pre_run_questions"] = PRE_RUN_QUESTIONS
    record["anti_js"] = "No JavaScript was used."
    return record


def _patch_sale_module() -> None:
    sale.__file__ = __file__
    sale.EXPERIMENT_ID = EXPERIMENT_ID
    sale.STEM = STEM
    sale.TRIAL_FAMILY = TRIAL_FAMILY
    sale.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    sale.CHANGED_VARIABLE = CHANGED_VARIABLE
    sale.RULE_VERSION = RULE_VERSION
    sale.OWNER = OWNER
    sale.OUT_DIR = OUT_DIR
    sale.OUT_JSON = OUT_JSON
    sale.LOG_JSON = LOG_JSON
    sale.TICKET_JSON = TICKET_JSON
    sale.CARD_MD = CARD_MD
    sale.MANIFEST_JSON = MANIFEST_JSON
    sale.EXPERIMENT_LOG = EXPERIMENT_LOG
    sale.REGISTRY_JSON = REGISTRY_JSON
    sale.PREDICTION = PREDICTION
    sale.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    sale.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    sale._EVENT_CACHE = None
    sale._load_sale_events = _load_sale_events
    sale._events_for_date = _events_for_date
    sale._event_from_row = _event_from_row
    sale._sale_stats = _sale_stats
    sale._candidate_for_sale_absorption_ticker = _candidate_for_sale_absorption_ticker
    sale._candidate_rows_for_window = _candidate_rows_for_window
    sale._gate4 = _gate4
    sale._build_payload = _build_payload
    sale._build_card = _build_card
    sale._build_log_record = _build_log_record
    sale._patch_framework()


_patch_sale_module()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
