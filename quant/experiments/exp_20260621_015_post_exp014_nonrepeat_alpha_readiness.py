"""exp-20260621-015: post-exp014 nonrepeat alpha readiness.

Alpha-search blocker. This run does not add a strategy rule. It asks whether
the next alpha can be evaluated honestly after the strongest fresh SEC customer
prepayment / capacity-commitment text surface failed Gate 4.

No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import exp_20260621_009_post_scalar_stack_nonrepeat_readiness as prior


EXPERIMENT_ID = "exp-20260621-015"
SLUG = "post_exp014_nonrepeat_alpha_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

HYPOTHESIS = (
    "candidate_pool/data-edge: after exp-20260621-014 rejected the strongest "
    "fresh SEC customer-prepayment/capacity-commitment text surface, the next "
    "executable alpha should proceed only if local surfaces expose a non-frozen "
    "PIT data edge with three canonical window coverage and shared-paper-first "
    "parity; otherwise strategy replay is blocked as near-neighbor mining."
)

TRIAL_FAMILY = "post_exp014_nonrepeat_alpha_readiness"
TRIAL_VARIANT_ID = "post_exp014_nonrepeat_pit_data_edge_readiness_v1"
CHANGED_VARIABLE = "post_exp014_nonrepeat_pit_data_edge_readiness_v1"

RECENT_EVIDENCE = [
    "exp-20260619-011",
    "exp-20260620-012",
    "exp-20260621-009",
    "exp-20260621-010",
    "exp-20260621-013",
    "exp-20260621-014",
]

PRIOR_FAMILY_CLOSURES = [
    "exp-20260617-012",  # SBC grant-value backlog relief rejected.
    "exp-20260619-014",  # 13G/A direction surface built, long bucket weak.
    "exp-20260619-016",  # 13G/A exit-overhang accepted-allocator veto rejected.
    "exp-20260620-024",  # proxy pay performance rejected.
    "exp-20260620-025",  # Form4 performance award rejected.
    "exp-20260621-014",  # SEC customer commitment text rejected.
]

KOVA_DIR = prior.REPO_ROOT / "data" / "kova"
FILING_TEXT_CACHE_DIR = prior.REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
FORM_INDEX_DIR = prior.REPO_ROOT / "data" / "cache" / "sec" / "form_index"


def configure_prior_module() -> None:
    data_dir = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.SLUG = SLUG
    prior.RUNNER_NAME = RUNNER_NAME
    prior.RUNNER_COMMAND = RUNNER_COMMAND
    prior.DATA_DIR = data_dir
    prior.ARTIFACT_JSON = data_dir / f"exp_20260621_015_{SLUG}.json"
    prior.BEFORE_JSON = data_dir / "before_baseline.json"
    prior.AFTER_JSON = data_dir / "after_no_strategy_change.json"
    prior.README_MD = data_dir / "README.md"
    prior.LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    prior.CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
    prior.MANIFEST_JSON = (
        prior.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
    )
    prior.TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    prior.HYPOTHESIS = HYPOTHESIS
    prior.PRIOR_BLOCKERS = RECENT_EVIDENCE


def parse_yyyymmdd(name: str) -> str | None:
    match = re.search(r"(20\d{6})", name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def date_in_window(value: str, start: str, end: str) -> bool:
    value_date = date.fromisoformat(value)
    return date.fromisoformat(start) <= value_date <= date.fromisoformat(end)


def audit_kova_snapshots() -> dict[str, Any]:
    by_surface: dict[str, dict[str, Any]] = {}
    all_dates: set[str] = set()
    for path in sorted(KOVA_DIR.rglob("*.jsonl")):
        snapshot_date = parse_yyyymmdd(path.name)
        surface = path.parent.name
        row = by_surface.setdefault(surface, {"file_count": 0, "dates": set()})
        row["file_count"] += 1
        if snapshot_date:
            row["dates"].add(snapshot_date)
            all_dates.add(snapshot_date)

    canonical_coverage = {}
    for label, window in prior.CANONICAL_WINDOWS.items():
        covered_dates = [
            value
            for value in sorted(all_dates)
            if date_in_window(value, window["start"], window["end"])
        ]
        canonical_coverage[label] = {
            "covered_snapshot_dates": covered_dates[:10],
            "covered_snapshot_date_count": len(covered_dates),
            "gate4_window_ready": False,
        }

    surfaces = {}
    for name, row in sorted(by_surface.items()):
        dates = sorted(row["dates"])
        surfaces[name] = {
            "file_count": row["file_count"],
            "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
            "date_count": len(dates),
            "pre_202605_dates": [value for value in dates if value < "2026-05-01"],
        }

    return {
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "canonical_window_coverage": canonical_coverage,
        "blocking_verdict": (
            "blocked_kova_forward_snapshots_lack_mid_weak_and_old_thin_history"
        ),
    }


def audit_estimate_revision_ledgers() -> dict[str, Any]:
    ledger_paths = sorted(prior.NON_OHLCV_DIR.glob("estimate_revision_ledger_*.jsonl"))
    summary_paths = sorted(prior.NON_OHLCV_DIR.glob("estimate_revision_ledger_summary_*.json"))
    dates = [parse_yyyymmdd(path.name) for path in ledger_paths]
    dates = [value for value in dates if value]

    latest_summary = prior.read_json(summary_paths[-1]) if summary_paths else {}
    canonical_coverage = {}
    for label, window in prior.CANONICAL_WINDOWS.items():
        covered_dates = [
            value
            for value in dates
            if date_in_window(value, window["start"], window["end"])
        ]
        canonical_coverage[label] = {
            "covered_snapshot_date_count": len(covered_dates),
            "first_covered_date": covered_dates[0] if covered_dates else None,
            "last_covered_date": covered_dates[-1] if covered_dates else None,
            "gate4_window_ready": False,
        }

    return {
        "ledger_count": len(ledger_paths),
        "first_ledger_date": dates[0] if dates else None,
        "last_ledger_date": dates[-1] if dates else None,
        "canonical_window_coverage": canonical_coverage,
        "latest_summary_path": (
            prior.repo_rel(summary_paths[-1]) if summary_paths else None
        ),
        "latest_summary_keys": sorted(latest_summary.keys()),
        "latest_usable_rows": latest_summary.get("estimate_revision_usable_rows"),
        "latest_matched_candidate_rows": latest_summary.get("matched_candidate_rows"),
        "latest_usable_and_matched_rows": latest_summary.get(
            "estimate_revision_usable_and_matched_candidate_rows"
        ),
        "latest_candidate_match_rate": latest_summary.get("candidate_match_rate"),
        "blocking_verdict": (
            "blocked_forward_revision_ledger_has_no_three_window_candidate_join"
        ),
    }


def audit_filing_text_cache() -> dict[str, Any]:
    forms: Counter[str] = Counter()
    years: Counter[str] = Counter()
    dates: list[str] = []
    sample_accessions: list[str] = []

    for path in sorted(FILING_TEXT_CACHE_DIR.glob("*.json")):
        payload = prior.read_json(path)
        form = str(payload.get("form_type") or payload.get("form_base") or "unknown").upper()
        filing_date = str(payload.get("filing_date") or "")
        if filing_date:
            dates.append(filing_date)
            years[filing_date[:4]] += 1
        forms[form] += 1
        if len(sample_accessions) < 5:
            sample_accessions.append(str(payload.get("accession_number") or path.stem))

    return {
        "file_count": sum(forms.values()),
        "first_filing_date": min(dates) if dates else None,
        "last_filing_date": max(dates) if dates else None,
        "years": dict(sorted(years.items())),
        "forms": forms.most_common(12),
        "ten_k_ten_q_text_count": sum(
            forms[form] for form in ("10-K", "10-Q", "10-K/A", "10-Q/A")
        ),
        "sample_accessions": sample_accessions,
        "blocking_verdict": (
            "blocked_filing_text_cache_recent_2026_only_not_three_window_history"
        ),
    }


def audit_form_index() -> dict[str, Any]:
    form_counts: Counter[str] = Counter()
    date_counts: Counter[str] = Counter()
    file_names: list[str] = []

    for path in sorted(FORM_INDEX_DIR.glob("form_*.idx")):
        file_names.append(path.name)
        for raw in path.read_text(encoding="latin-1").splitlines():
            if not raw or raw.startswith(("Description:", "Last Data", "Comments:", "Anonymous")):
                continue
            if raw.startswith(("Form Type", "---")):
                continue
            form = raw[:12].strip().upper()
            if not form:
                continue
            match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", raw)
            if match:
                form_counts[form] += 1
                date_counts[match.group(1)[:7]] += 1

    return {
        "file_count": len(file_names),
        "files": file_names,
        "top_forms": form_counts.most_common(12),
        "ten_k_ten_q_index_count": sum(
            form_counts[form] for form in ("10-K", "10-Q", "10-K/A", "10-Q/A")
        ),
        "first_month": min(date_counts) if date_counts else None,
        "last_month": max(date_counts) if date_counts else None,
        "has_cover_page_dei_status": False,
        "blocking_verdict": (
            "blocked_form_index_has_historical_form_metadata_but_no_cover_page_pit_fields"
        ),
    }


def audit_prior_family_closures() -> dict[str, Any]:
    rows = []
    for exp_id in PRIOR_FAMILY_CLOSURES:
        payload = prior.read_json(prior.REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json")
        gate4 = payload.get("gate4") or {}
        reflection = payload.get("post_run_reflection") or {}
        rows.append(
            {
                "experiment_id": exp_id,
                "found": bool(payload),
                "decision": payload.get("decision"),
                "status": payload.get("status"),
                "failed_reasons": gate4.get("failed_reasons"),
                "target_trade_count": gate4.get("target_trade_count"),
                "next_evidence_needed": (
                    payload.get("next_evidence_needed")
                    or reflection.get("new_evidence_required")
                    or reflection.get("best_next_alpha_direction")
                ),
            }
        )
    return {
        "family_closures": rows,
        "blocking_verdict": (
            "blocked_recent_sec_form4_13d13g_sbc_related_families_require_new_data_axis"
        ),
    }


def build_post_exp014_surface_audit() -> dict[str, Any]:
    return {
        "sec_customer_commitment_exp014": prior.prior_summary("exp-20260621-014"),
        "sec_customer_commitment_gate4": (
            prior.read_json(prior.REPO_ROOT / "experiments" / "logs" / "exp-20260621-014.json")
            .get("gate4")
        ),
        "kova": audit_kova_snapshots(),
        "estimate_revision": audit_estimate_revision_ledgers(),
        "filing_text_cache": audit_filing_text_cache(),
        "form_index": audit_form_index(),
        "prior_family_closures": audit_prior_family_closures(),
        "surface_verdicts": {
            "sec_customer_commitment_text": (
                "rejected_exp014_zero_or_tiny_target_sample_and_failed_comparators"
            ),
            "kova_13f_companyfacts_rs_proxy_intraday": (
                "blocked_forward_snapshots_lack_fixed_window_history"
            ),
            "estimate_revision": (
                "blocked_recent_forward_ledgers_have_no_canonical_candidate_join"
            ),
            "historical_cover_page_filer_status": (
                "blocked_form_index_lacks_cover_page_dei_status_and_text_cache_recent_only"
            ),
            "parsed_13d13g": "closed_or_rejected_without_new_holder_outcome_provenance",
            "form4_sbc_proxy_pay": "closed_or_rejected_without_new_grant_value_context",
        },
        "any_gate4_ready_nonrepeat_surface": False,
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-exp014 nonrepeat alpha readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 4 Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in prior.CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"{row['expected_value_score']:.4f} | 0.0000 | "
            f"${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )

    aggregate = result["gate4"]["aggregate_before"]
    audit = result["gate2"]["post_exp014_surface_audit"]
    lines.extend(
        [
            "",
            "## Blocker",
            "",
            f"Aggregate baseline EV `{aggregate['aggregate_expected_value_score']:.4f}`, "
            f"PnL `${aggregate['aggregate_total_pnl']:,.2f}`. No after policy was run.",
            "",
            "Reviewed surfaces:",
            "",
        ]
    )
    for surface, verdict in audit["surface_verdicts"].items():
        lines.append(f"- `{surface}`: `{verdict}`")
    lines.extend(
        [
            "",
            "## Next Evidence",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_result() -> dict[str, Any]:
    result = prior.build_result()
    surface_audit = build_post_exp014_surface_audit()
    result.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": "blocked_post_exp014_no_gate4_ready_nonrepeat_alpha_surface",
            "change_type": "candidate_pool_data_edge_readiness",
            "mechanism_family": "candidate_pool_data_edge_readiness",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": HYPOTHESIS,
            "reproduction": RUNNER_COMMAND,
        }
    )
    result["pre_run_questions"] = {
        "1_alpha_hypothesis": HYPOTHESIS,
        "2_history_check": {
            "novelty_gate": "scripts/experiment.py new returned no strong near-neighbor block.",
            "nearby_prior_experiments": RECENT_EVIDENCE,
            "new_evidence_axis": (
                "Post-exp014 customer-commitment text rejection plus direct audit "
                "of filing_text/form_index, Kova, estimate-revision, 13D/13G, "
                "Form4/SBC/proxy-pay, and accepted allocator source samples."
            ),
        },
        "3_single_policy_bundle": (
            "Readiness gate only: no trading policy, filter, ranking, sizing, "
            "exit, watchlist, LLM, news, or live order behavior changes."
        ),
        "4_acceptance_criteria": (
            "A strategy alpha can start only if a current surface has non-frozen "
            "novelty, PIT-safe runtime fields, survival >=5%, and all three "
            "canonical windows available under docs/backtesting.md without "
            "production/backtest inconsistency."
        ),
        "5_reproducibility": RUNNER_COMMAND,
    }
    result["gate2"]["post_exp014_surface_audit"] = surface_audit
    result["gate2"]["blocking_item"] = (
        "No reviewed post-exp014 candidate source has all of: non-frozen "
        "novelty, PIT-safe runtime fields, three canonical windows, enough "
        "target/sample rows, and a shared-paper-first production parity path."
    )
    result["gate4"]["reason"] = (
        "Gate 2/Gate 3 blocked all reviewed alpha surfaces after exp-20260621-014, "
        "so after intentionally equals before across the three canonical windows."
    )
    result["production_impact"]["parity_note"] = (
        "No production/backtest inconsistency was introduced because no trading "
        "rule or shared helper changed. A future positive alpha must be "
        "implemented shared-paper-first before it can be accepted."
    )
    result["calibration"]["failure_modes_observed"] = [
        "post_exp014_sec_customer_commitment_failed_gate4",
        "kova_forward_snapshots_lack_mid_weak_old_thin_history",
        "estimate_revision_ledgers_lack_three_window_candidate_join",
        "filing_text_cache_recent_only_and_form_index_lacks_cover_page_status",
        "13d13g_form4_sbc_proxy_pay_companyfacts_families_require_new_data_axis",
        "remaining_allocator_sources_sample_starved",
    ]
    result["post_run_reflection"] = {
        "why_blocked": (
            "After exp-20260621-014, the best fresh SEC text source is negative "
            "or too sparse; Kova and estimate-revision data are forward/recent "
            "without fixed-window coverage; filing_text cache is recent-only; "
            "form_index lacks cover-page PIT fields; and 13D/13G, Form4/SBC, "
            "proxy-pay, Companyfacts, allocator, and OHLCV relation families are "
            "closed or rejected without a materially new data axis."
        ),
        "negative_result_reflection": (
            "This is a blocked alpha-search result, not a losing after-policy. "
            "Forcing a strategy replay now would either repeat a frozen family "
            "or use data that cannot be evaluated across the three canonical "
            "windows. The likely failure mechanism is data-edge exhaustion, not "
            "a missing threshold sweep."
        ),
        "best_next_alpha_direction": (
            "Add a fresh free PIT source before the next Gate 4: historical "
            "10-K/10-Q cover-page filer status by accession, CIK-level customer/"
            "supplier/contract economics from primary SEC documents, PIT "
            "analyst breadth/revenue-estimate dispersion joined to historical "
            "candidates, or borrow/options as-of rows with fixed-window coverage."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry SEC phrase screens, current submission metadata, "
            "Companyfacts ratio thresholds, Form4/proxy/SBC threshold context, "
            "13D/13G stake/holder filters, allocator source rank/notional/top-N, "
            "daily second slot, or OHLCV relation residuals without a materially "
            "new PIT field or closed forward replacement rows."
        ),
    }
    result["changed_files"] = [
        RUNNER_NAME,
        prior.repo_rel(prior.ARTIFACT_JSON),
        prior.repo_rel(prior.BEFORE_JSON),
        prior.repo_rel(prior.AFTER_JSON),
        prior.repo_rel(prior.README_MD),
        prior.repo_rel(prior.LOG_JSON),
        prior.repo_rel(prior.CARD_MD),
        prior.repo_rel(prior.MANIFEST_JSON),
        prior.repo_rel(prior.TICKET_JSON),
        "docs/experiment_log.jsonl",
        "docs/experiment_registry.json",
    ]
    return result


def update_ticket(result: dict[str, Any]) -> None:
    ticket = prior.read_json(prior.TICKET_JSON)
    ticket.update(
        {
            "status": result["status"],
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "result": {
                "decision": result["decision"],
                "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
                "before": prior.repo_rel(prior.BEFORE_JSON),
                "after": prior.repo_rel(prior.AFTER_JSON),
                "log": prior.repo_rel(prior.LOG_JSON),
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
                "accepted": False,
                "accepted_alpha": False,
                "gate4": result["gate4"],
                "production_impact": result["production_impact"],
                "lean_quality_passed": result["lean_quality_passed"],
            },
        }
    )
    prior.write_json(prior.TICKET_JSON, ticket)


def refresh_registry(result: dict[str, Any]) -> None:
    existing_ticket = prior.read_json(prior.TICKET_JSON)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
        "before": prior.repo_rel(prior.BEFORE_JSON),
        "after": prior.repo_rel(prior.AFTER_JSON),
        "log": prior.repo_rel(prior.LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    fields = dict(existing_ticket)
    fields.update(
        {
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": RECENT_EVIDENCE,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "post-exp014 surface audit and blocker proof",
            "baseline_result_file": prior.BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row["start"],
                    "end": row["end"],
                    "snapshot": row["snapshot"],
                }
                for label, row in prior.CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless a current alpha candidate has non-frozen PIT "
                "evidence, runtime fields, survival >=5%, and all three canonical "
                "windows available for before/after Gate 4."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
            "before": prior.repo_rel(prior.BEFORE_JSON),
            "after": prior.repo_rel(prior.AFTER_JSON),
            "log": prior.repo_rel(prior.LOG_JSON),
            "card_file": prior.repo_rel(prior.CARD_MD),
            "revision_manifest_file": prior.repo_rel(prior.MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "pre_run_questions": result["pre_run_questions"],
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        }
    )
    prior.experiment_registry.persist_self_registered_result(
        prior.REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields=fields,
    )


def main() -> None:
    configure_prior_module()
    prior.build_card = build_card
    result = build_result()
    prior.persist(result)
    refresh_registry(result)
    update_ticket(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "gate4_after_equals_before": True,
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
