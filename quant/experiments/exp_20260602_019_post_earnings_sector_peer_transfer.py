"""exp-20260602-019: post-earnings same-sector peer transfer scout.

This alpha search tests one broader relation-construction candidate source.
A confirmed positive EPS-surprise issuer must have a strong positive event-day
reaction, then a liquid same-sector peer can enter a default-off paper sleeve
only if that peer confirms with same-day relative strength, event-to-signal
strength, trend, and a high close location.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_012_post_earnings_peer_reaction_transfer as peer_parent
from broad_market_sector_map import DEFAULT_CACHE_PATH, load_cache, lookup_sector


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-019"
STEM = "post_earnings_sector_peer_transfer"
TRIAL_FAMILY = "post_earnings_peer_transfer_relation"
CHANGED_VARIABLE = "post_earnings_same_sector_peer_transfer_candidate_source_v1"
RULE_VERSION = "post_earnings_same_sector_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_019_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RECENT_SIGNAL_DAYS_MIN = 0
RECENT_SIGNAL_DAYS_MAX = 3
MIN_ISSUER_EVENT_EXCESS_VS_SPY = 0.015
MIN_ISSUER_EVENT_CLOSE_LOCATION = 0.60
MIN_PEER_SIGNAL_EXCESS_VS_SPY = 0.005
MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY = 0.005
MIN_PEER_CLOSE_LOCATION = 0.60


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sector_peer_groups(
    universe: list[str],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    """Return peer groups keyed by sector while preserving parent field names."""
    cache = load_cache(DEFAULT_CACHE_PATH)
    lookups: dict[str, dict[str, Any]] = {}
    by_sector: dict[str, list[str]] = defaultdict(list)
    for ticker in sorted(
        set(universe).intersection(snapshot).difference(peer_parent.parent.framework.EXCLUDED_TICKERS)
    ):
        lookup = dict(lookup_sector(ticker, cache))
        if lookup.get("status") != "ok":
            lookups[ticker] = lookup
            continue
        sector = str(lookup.get("sector") or "").strip()
        if not sector:
            lookups[ticker] = lookup
            continue
        lookup["industry"] = sector
        lookup["peer_relation_original_industry"] = lookup_sector(ticker, cache).get("industry")
        lookups[ticker] = lookup
        by_sector[sector.lower()].append(ticker)
    coverage = {
        "cache_path": str(DEFAULT_CACHE_PATH.relative_to(REPO_ROOT)),
        "cache_generated_at": cache.get("generated_at"),
        "tickers_with_lookup": len(lookups),
        "ok_lookup_count": sum(1 for row in lookups.values() if row.get("status") == "ok"),
        "sector_count": len(by_sector),
        "relation_key": "yfinance_sector",
    }
    return lookups, by_sector, coverage


def _patch_parent() -> None:
    peer_parent.EXPERIMENT_ID = EXPERIMENT_ID
    peer_parent.STEM = STEM
    peer_parent.TRIAL_FAMILY = TRIAL_FAMILY
    peer_parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    peer_parent.RULE_VERSION = RULE_VERSION
    peer_parent.OUT_DIR = OUT_DIR
    peer_parent.OUT_JSON = OUT_JSON
    peer_parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    peer_parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    peer_parent.LOG_JSON = LOG_JSON
    peer_parent.TICKET_JSON = TICKET_JSON
    peer_parent.CARD_MD = CARD_MD
    peer_parent.ARTIFACT_MD = ARTIFACT_MD
    peer_parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    peer_parent.MANIFEST_JSON = MANIFEST_JSON
    peer_parent.RECENT_SIGNAL_DAYS_MIN = RECENT_SIGNAL_DAYS_MIN
    peer_parent.RECENT_SIGNAL_DAYS_MAX = RECENT_SIGNAL_DAYS_MAX
    peer_parent.MIN_ISSUER_EVENT_EXCESS_VS_SPY = MIN_ISSUER_EVENT_EXCESS_VS_SPY
    peer_parent.MIN_ISSUER_EVENT_CLOSE_LOCATION = MIN_ISSUER_EVENT_CLOSE_LOCATION
    peer_parent.MIN_PEER_SIGNAL_EXCESS_VS_SPY = MIN_PEER_SIGNAL_EXCESS_VS_SPY
    peer_parent.MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY = MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY
    peer_parent.MIN_PEER_CLOSE_LOCATION = MIN_PEER_CLOSE_LOCATION
    peer_parent._industry_peers = _sector_peer_groups
    peer_parent._build_report = _build_report
    peer_parent._patch_parent()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = peer_parent._postprocess_payload(payload)
    gate4 = payload["gate4"]
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if gate4["passed"]
        else "rejected_post_earnings_same_sector_peer_transfer"
    )
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.20,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "window_regression",
            "thin_sample",
            "concentration_failed",
            "drawdown_drift",
        ],
        "confidence_reason": (
            "Exact-industry peer transfer had positive aggregate evidence but "
            "failed sample and concentration; same-sector relation broadens "
            "sample while requiring stronger issuer and peer confirmation."
        ),
        "recorded_at": "2026-06-02T13:07:48+00:00",
        "brier_score": round((0.20 - actual_success) ** 2, 6),
    }
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Same-sector peers of confirmed positive EPS-surprise issuers "
                "may produce cleaner default-off paper candidates when the "
                "issuer reacts strongly and the peer confirms with price/RS."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "event_graph_relation_candidate_pool",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-006",
                "exp-20260602-011",
                "exp-20260602-012",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_earnings_snapshot_sector_peer_relation_field",
            "prediction": prediction,
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": prediction["success_probability"],
                "brier_score": prediction["brier_score"],
                "expected_ev_delta": prediction["expected_ev_delta"],
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "expected_pnl_delta": prediction["expected_pnl_delta"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "predicted_failure_modes": prediction["main_failure_modes"],
                "realized_failure_mode": None
                if gate4["passed"]
                else "; ".join(gate4["failed_reasons"]),
                "predicted_failure_mode_hit": (
                    False
                    if gate4["passed"]
                    else any(
                        token in "; ".join(gate4["failed_reasons"])
                        for token in ["window", "sample", "concentration", "drawdown"]
                    )
                ),
            },
            "parameters": {
                **payload["parameters"],
                "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
                "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
                "min_issuer_event_excess_vs_spy": MIN_ISSUER_EVENT_EXCESS_VS_SPY,
                "min_issuer_event_close_location": MIN_ISSUER_EVENT_CLOSE_LOCATION,
                "min_peer_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
                "min_peer_event_to_signal_excess_vs_spy": (
                    MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY
                ),
                "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
                "source_definition": [
                    "event issuer has PIT earnings snapshot transition-confirmed positive EPS surprise",
                    "issuer event-day return beats SPY by at least 1.5pp and closes in upper 60% of range",
                    "candidate is a different ticker in the same yfinance sector",
                    "candidate has signal-day return beating SPY by at least 0.5pp",
                    "candidate event-to-signal return beats SPY by at least 0.5pp and has positive 20d RS",
                    "candidate is liquid, above prior 50d average, and close_location >= 0.60",
                    "top-1 selected paper entry per signal date",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: positive earnings-surprise reactions "
                    "may transfer to same-sector peers when both issuer reaction "
                    "and peer same-day confirmation are strong."
                ),
                "2_history_check": {
                    "exp-20260602-006": (
                        "Issuer-only positive-surprise drift was positive but "
                        "failed a window and drawdown."
                    ),
                    "exp-20260602-011": (
                        "Issuer underreaction close-location cap was positive "
                        "but failed the target-trade sample floor."
                    ),
                    "exp-20260602-012": (
                        "Exact-industry peer transfer was positive in aggregate "
                        "but failed sample, concentration, and one window."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_019_post_earnings_sector_peer_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain sparse. "
                "Skipped Companyfacts, FINRA, VBB, consensus, Space, and state-surface "
                "retunes because the playbook requires forward rows or materially new "
                "fields. This run changes only the relation construction from exact "
                "industry to stricter same-sector peer transfer."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. A future promotion would "
                    "need this exact relation field moved into a shared default-off "
                    "adapter using the same earnings snapshot and sector-map inputs "
                    "available to production before next-open paper entry."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "live_orders_changed": False,
            },
            "interpretation": (
                "The same-sector peer earnings-reaction transfer source cleared "
                "Gate 4 as a replay lead, but no shared adapter was promoted."
                if gate4["passed"]
                else (
                    "The same-sector peer earnings-reaction transfer source did "
                    "not clear Gate 4. Do not promote it or retry nearby peer "
                    "transfer relation thresholds on these frozen windows without "
                    "forward rows or a stronger relation source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a stronger peer relation source "
                "such as audited customer/supplier links, source overlap, or "
                "multi-season early-peer earnings transfer evidence."
            ),
            "related_files": [
                "quant/experiments/exp_20260602_019_post_earnings_sector_peer_transfer.py",
                "data/experiments/exp-20260602-019/exp_20260602_019_post_earnings_sector_peer_transfer.json",
                "data/experiments/exp-20260602-019/post_earnings_sector_peer_transfer_before_aggregate.json",
                "data/experiments/exp-20260602-019/post_earnings_sector_peer_transfer_after_aggregate.json",
                "experiments/logs/exp-20260602-019.json",
                "experiments/tickets/exp-20260602-019.json",
                "experiments/artifacts/exp-20260602-019_post_earnings_sector_peer_transfer.md",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_field_coverage"]["peer_relation"] = {
        "source": "data/reference/broad_market_sector_map.json",
        "required_fields": ["sector", "status"],
        "relation": "same yfinance sector string match",
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in peer_parent.parent.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {events} | {reactions} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                events=audit.get("positive_surprise_event_count", 0),
                reactions=audit.get("issuer_positive_reaction_event_count", 0),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260602-019 Post-Earnings Same-Sector Peer Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: same-sector peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest() -> None:
    base = peer_parent.parent.framework.base
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": _repo_rel(AFTER_AGG_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
        "experiment_log": _repo_rel(EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(peer_parent.parent.framework._build_payload())
    peer_parent._persist(payload)
    _write_manifest()
    print(
        json.dumps(
            peer_parent.parent.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": _repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
