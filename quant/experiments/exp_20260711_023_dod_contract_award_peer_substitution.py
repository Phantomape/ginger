"""exp-20260711-023: DoD award winner-to-peer substitution scout.

The official DoD event surface and PIT timestamps are frozen from
exp-20260711-020. This experiment changes the response shape: target the
strongest non-awarded liquid Aerospace & Defense peer rather than the named
awardee, while keeping the $250M event threshold, next-open entry, 10-session
exit, costs, top-1/day, and cooldown fixed. A pass is only a private replay
lead until shared daily default-off parity exists.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260711_020_dod_contract_awards as source

# Registry persistence is delegated through source.runner._persist, whose
# sanctioned path calls experiment_registry.persist_self_registered_result(
# after the ticket has already been reserved and claimed.


EXPERIMENT_ID = "exp-20260711-023"
STEM = "dod_contract_award_peer_substitution"
TRIAL_FAMILY = "dod_contract_award_peer_substitution_candidate_pool"
TRIAL_VARIANT_ID = "fixed_250m_non_awarded_ad_peer_top1_10d_v1"
CHANGED_VARIABLE = "dod_award_winner_to_peer_substitution_top1_10d_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-explore"

REPO_ROOT = source.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_023_{STEM}.json"
EVENTS_JSON = source.EVENTS_JSON
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PEER_UNIVERSE = ("LMT", "NOC", "GD", "RTX", "BA", "HII")
PEER_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "aggregate_expected_value_delta": 0.3845,
    "aggregate_pnl_delta": 6107.66,
}
PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "thin_mid_weak_coverage",
        "peer_beta_not_award_diffusion",
        "concentration_in_lmt_noc",
        "accepted_peer_comparator_not_beaten",
    ],
    "confidence_reason": (
        "A no-ID diagnostic on nine A&D awardee trades found awardees lagged "
        "a fixed peer basket by 3.32% net on average (7/9 negative), but the "
        "sample covered only two windows."
    ),
    "recorded_at": "2026-07-11T18:08:26+00:00",
}
HYPOTHESIS = (
    "candidate_pool/private replay scout: after an official DoD daily "
    "contract award of at least $250M to a named liquid Aerospace & Defense "
    "prime, the awardee may be priced in while budget validation diffuses to "
    "non-awarded peers; selecting the strongest PIT non-awarded peer at the "
    "signal close for next-open entry and a fixed 10-session exit should add "
    "positive after-cost replacement value across canonical windows."
)
PRODUCTION_IMPACT = {
    **source.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "trade_enabled": False,
    "parity_note": (
        "No production/shared policy changes. A positive replay is only a "
        "lead until a shared default-off helper reproduces the same event, "
        "peer universe, rank, cooldown, entry, exit, and costs."
    ),
}
PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": HYPOTHESIS,
    "2_history_check": {
        "exp-20260711-020": (
            "Rejected the awarded-prime self candidate; its reflection permits "
            "a genuinely different ex-ante response shape."
        ),
        "exp-20260606-025": (
            "Accepted rolling-correlation peer shock is the closest retained "
            "peer comparator and must be beaten."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Canonical Gate 1-4; positive aggregate EV/PnL; >=2 improved windows; "
        ">=20 trades across all 3 windows; drawdown <=0.5pp worse; "
        "concentration pass; beat exp-20260606-025."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260711_023_dod_contract_award_peer_substitution.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return source.runner._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return source.runner._round(value, digits)


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = source._load_event_index()
    filtered = {ticker: rows for ticker, rows in index.items() if ticker in PEER_UNIVERSE}
    return filtered, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "exp-20260711-020 official DoD award event artifact",
        "awarded_prime_universe": list(PEER_UNIVERSE),
        "qualifying_prime_event_rows": sum(len(rows) for rows in filtered.values()),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shadow = source.runner.base.framework.shadow
    indices = {
        ticker: shadow._row_index(shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = shadow._trading_dates(snapshot)
    start, end = str(cfg["start"]), str(cfg["end"])
    available_peers = tuple(ticker for ticker in PEER_UNIVERSE if ticker in snapshot)
    scan: Counter[str] = Counter()
    scan["dod_award_events_total"] = sum(len(rows) for rows in quality_index.values())
    scan["eligible_awarded_prime_tickers"] = len(set(quality_index) & set(snapshot))
    scan["available_peer_tickers"] = len(available_peers)
    candidates: list[dict[str, Any]] = []

    for awarded_ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[awarded_ticker]:
            signal_date = source.runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["dod_award_events_in_window"] += 1
            for peer in available_peers:
                if peer == awarded_ticker:
                    continue
                scan["peer_rows_scanned"] += 1
                confirm = source.runner._absorption_confirmation(
                    snapshot=snapshot,
                    indices=indices,
                    ticker=peer,
                    signal_date=signal_date,
                )
                if confirm is None:
                    scan["peer_failed_absorption_or_liquidity_gate"] += 1
                    continue
                scan["qualified_peer_candidate_rows"] += 1
                score = (
                    1.60 * float(confirm["candidate_signal_excess_spy"])
                    + 0.40 * float(confirm["candidate_close_location"])
                    + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                    + 0.08
                    * math.log10(
                        max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                        / 1_000_000.0
                    )
                )
                meta = sector_entries.get(peer, {})
                candidates.append(
                    {
                        "date": signal_date,
                        "ticker": peer,
                        "source": "DOD_CONTRACT_AWARD_PEER_SUBSTITUTION_PAPER",
                        "candidate_score": _round(score, 6),
                        "rule_version": RULE_VERSION,
                        "source_rule_version": RULE_VERSION,
                        "known_at": (
                            "dod_award_published_17et_before_peer_signal_close_"
                            "and_next_open_paper_entry"
                        ),
                        "sector": meta.get("sector"),
                        "industry": meta.get("industry"),
                        "trade_enabled": False,
                        "uses_dod_contract_announcements": True,
                        "uses_free_ohlcv": True,
                        "uses_llm": False,
                        "awarded_ticker": awarded_ticker,
                        "peer_relation": "non_awarded_aerospace_defense_budget_validation",
                        "dod_announce_date": event.get("filing_date"),
                        "dod_publication_datetime_et": event.get("acceptance_datetime"),
                        "dod_award_total_usd": event.get("award_total_usd"),
                        "dod_award_count": event.get("award_count"),
                        "dod_max_single_award_usd": event.get("max_single_award_usd"),
                        "dod_branches": event.get("branches"),
                        "dod_contractors": event.get("contractors"),
                        "dod_article_id": event.get("article_id"),
                        "dod_article_url": event.get("article_url"),
                        **confirm,
                    }
                )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (str(row["date"]), str(row["ticker"]))
        existing = deduped.get(key)
        if existing is None or float(row.get("dod_award_total_usd") or 0.0) > float(
            existing.get("dod_award_total_usd") or 0.0
        ):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            str(row["date"]),
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("candidate_signal_excess_spy") or 0.0),
            -float(row.get("candidate_close_location") or 0.0),
            str(row["ticker"]),
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "event_rule": "fixed >=$250M DoD single-awardee prime event",
        "response_shape": "strongest non-awarded A&D peer top-1/day",
        "peer_universe": list(PEER_UNIVERSE),
        "peer_rank": "signal-day excess SPY, close location, ret20 excess, ADV",
        "min_award_total_usd": source.MIN_AWARD_TOTAL_USD,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = source.runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)
    if ev_delta <= PEER_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_peer_comparator_ev_not_beaten")
    if pnl_delta <= PEER_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_peer_comparator_pnl_not_beaten")
    gate["failed_reasons"] = list(dict.fromkeys(failed))
    gate["accepted_peer_comparator"] = PEER_COMPARATOR
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_dod_award_peer_substitution"
        if gate["passed"]
        else "rejected_dod_award_peer_substitution_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    interpretation = (
        "The fixed DoD award peer-substitution shape cleared the numeric replay "
        "screen but remains an unpromoted private lead."
        if gate4["passed"]
        else (
            "The fixed DoD award peer-substitution candidate pool failed Gate 4 "
            f"({', '.join(gate4['failed_reasons']) or 'none'}); no policy was retained."
        )
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
            "hypothesis": HYPOTHESIS,
            "change_type": "candidate_pool_private_replay_scout",
            "implementation_mode": "private_replay_scout_due_uncertain_peer_response_shape",
            "implementation_mode_reason": (
                "The official event surface is cached, but the peer response "
                "shape had only a nine-row no-ID diagnostic. A positive result "
                "requires shared-paper-first promotion."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_dod_contract_award_peer_substitution_candidate_pool",
            "new_evidence_type": "new_gate_shape_peer_substitution_relation",
            "new_evidence_axis": (
                "New gate shape: target a non-awarded PIT A&D peer through "
                "peer substitution/budget validation rather than the rejected "
                "awarded-prime self candidate from exp-20260711-020."
            ),
            "nearby_prior_experiments": ["exp-20260711-020", "exp-20260606-025"],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
            "accepted_peer_comparator": PEER_COMPARATOR,
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "brier_score": round((PREDICTION["success_probability"] - float(gate4["passed"])) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "failure_modes_observed": gate4["failed_reasons"],
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4["failed_reasons"])
        ),
    }
    payload["parameters"] = {
        "min_award_total_usd": source.MIN_AWARD_TOTAL_USD,
        "peer_universe": list(PEER_UNIVERSE),
        "peer_rank": "signal_day_excess_spy_then_close_location_ret20_adv",
        "paper_notional_usd": source.BASE_NOTIONAL_USD,
        "hold_days": source.HOLD_DAYS,
        "max_paper_trades_per_day": source.MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": source.SAME_TICKER_COOLDOWN_DAYS,
    }
    payload["backtest_protocol"]["announcement_source"] = _repo_rel(EVENTS_JSON)
    payload["backtest_protocol"]["execution_model"] = (
        "Use exp-20260711-020 official DoD >=$250M prime events. On the first "
        "trading session after the after-close announcement, rank non-awarded "
        "A&D peers passing the frozen absorption/liquidity recipe; select "
        "top-1/day, enter next open, exit after 10 sessions, and apply costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "DoD Contracts RSS publication timestamp and parsed award economics",
        "awarded_ticker and fixed non-awarded peer relation",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for peer relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not retry peer lists, award thresholds, rank weights, absorption "
        "thresholds, top-N, hold, cooldown, or notional. Reopen only with a "
        "shared fixed helper producing closed forward replacement rows, "
        "obligated-vs-ceiling/new-award economics from a second source, or a "
        "genuinely different supplier/backlog relation."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "{} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not invert the sign again or sweep peer universe/rank, award "
            "threshold, absorption, top-N, hold, cooldown, or notional."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)), _repo_rel(OUT_JSON), _repo_rel(EVENTS_JSON),
        _repo_rel(LOG_JSON), _repo_rel(TICKET_JSON), _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} DoD award peer substitution", "",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
        f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`", "",
        payload["interpretation"], "",
        "No production/shared trading behavior changed; `trade_enabled=false`.",
        "", "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in (
            Path(__file__), OUT_JSON, EVENTS_JSON, CARD_MD, MANIFEST_JSON,
            TICKET_JSON, LOG_JSON, EXPERIMENT_LOG, REGISTRY_JSON,
        )],
        "file_hashes": {
            _repo_rel(Path(__file__)): source.runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): source.runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): source.runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): source.runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): source.runner.base.framework._sha256(CARD_MD),
        },
    }
    source.runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _install() -> None:
    source._install()
    runner = source.runner
    runner.EXPERIMENT_ID = EXPERIMENT_ID
    runner.STEM = STEM
    runner.TRIAL_FAMILY = TRIAL_FAMILY
    runner.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    runner.CHANGED_VARIABLE = CHANGED_VARIABLE
    runner.RULE_VERSION = RULE_VERSION
    runner.OWNER = OWNER
    runner.OUT_DIR = OUT_DIR
    runner.OUT_JSON = OUT_JSON
    runner.LOG_JSON = LOG_JSON
    runner.TICKET_JSON = TICKET_JSON
    runner.CARD_MD = CARD_MD
    runner.MANIFEST_JSON = MANIFEST_JSON
    runner.EXPERIMENT_LOG = EXPERIMENT_LOG
    runner.REGISTRY_JSON = REGISTRY_JSON
    runner.PREDICTION = PREDICTION
    runner.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    runner.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    runner._build_quality_index = _build_quality_index
    runner._candidate_rows_for_window = _candidate_rows_for_window
    runner._gate4 = _gate4
    runner._postprocess_payload = _postprocess_payload
    runner._build_card = _build_card
    runner._write_manifest = _write_manifest


def main() -> None:
    if not EVENTS_JSON.exists():
        raise FileNotFoundError(
            f"missing frozen source artifact {EVENTS_JSON}; reproduce exp-20260711-020 first"
        )
    _install()
    source.runner.main()


if __name__ == "__main__":
    main()
