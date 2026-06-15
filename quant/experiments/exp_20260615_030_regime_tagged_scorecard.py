"""exp-20260615-030: build the regime-tagged forward/live-pilot scorecard.

Produces the out-of-sample accumulation surface for the regime_chop soft-tilt:
stamps each closed forward paper-sleeve row with its production-faithful
(stress-only) entry-time regime and exposure_scalar via the shared module and the
canonical warehouse SPY bars, then writes a re-runnable scorecard artifact.

With only a handful of closed rows today this is observation-only and must NOT
drive sizing. Read-only; changes no orders. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiment_registry  # noqa: E402
import exp_20260615_019_pit_regime_state_attribution as base019  # noqa: E402
import regime_tagged_scorecard as scorecard  # noqa: E402

EXPERIMENT_ID = "exp-20260615-030"
STEM = "regime_tagged_scorecard"
CHANGED_VARIABLE = "regime_tagged_forward_scorecard_surface"
OWNER = "alpha-search-automation"

WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_030_{STEM}.json"
SCORECARD_DIR = REPO_ROOT / "data" / "regime_scorecard"
SCORECARD_JSON = SCORECARD_DIR / "regime_tagged_scorecard_latest.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"


def _build_payload() -> dict[str, Any]:
    rows = scorecard.load_forward_paper_rows()
    regime_fn = scorecard.warehouse_spy_stress_regime_fn(WAREHOUSE)
    sc = scorecard.build_scorecard(rows, regime_fn)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": base019._utc_now(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "regime_tagged_scorecard_surface_built",
        "accepted": False,
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "regime_tagged_forward_scorecard",
        "rule_version": sc["rule_version"],
        "builds_on": ["exp-20260615-025", "exp-20260615-028"],
        "hypothesis": (
            "A reusable scorecard tagging each closed forward / live-pilot row with "
            "its production-faithful (stress-only) entry-time regime_chop and "
            "exposure_scalar builds the out-of-sample surface to later validate the "
            "chop soft-tilt without re-slicing the frozen windows."
        ),
        "tagging_fidelity": "stress_only_no_breadth (matches production daily field after exp-028)",
        "warehouse": scorecard.REPO_ROOT and str(WAREHOUSE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "scorecard": sc,
        "scorecard_artifact": str(SCORECARD_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_sizing": False,
            "uses_llm": False,
            "parity_note": (
                "Pure measurement surface. The scorecard tags closed forward rows "
                "with the same stress-only regime_chop fidelity the daily field "
                "emits; re-run it as rows accumulate. It changes no orders and is "
                "NOT acceptance evidence for any sizing change until enough closed "
                "rows exist for a separate Gate 1-4."
            ),
        },
        "interpretation": (
            "OBSERVE-ONLY: {} closed forward rows tagged ({} total). Tiny-sample "
            "warning: {}. The soft-tilt counterfactual and per-regime replacement "
            "value are directional only until many more closed rows accumulate; "
            "today nearly all forward rows fall in risk_on_trend (May-Jun 2026 was "
            "trending), so there is little chop exposure to evaluate yet.".format(
                sc["tagged_rows"], sc["total_rows"], sc["tiny_sample_warning"]
            )
        ),
        "next_evidence_needed": (
            "Accumulate closed forward / live-pilot rows across more regimes "
            "(especially choppy_range), then a separate Gate 1-4 can test whether "
            "the exposure_scalar soft tilt improves cost-adjusted replacement value "
            "out-of-sample. Re-run this scorecard to refresh tags."
        ),
        "related_files": [
            base019._repo_rel(Path(__file__)),
            "quant/regime_tagged_scorecard.py",
            "quant/test_regime_tagged_scorecard.py",
            str(SCORECARD_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            base019._repo_rel(OUT_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    sc = payload["scorecard"]
    lines = [
        f"# {EXPERIMENT_ID} Regime-Tagged Forward Scorecard",
        "",
        f"Status: `{payload['status']}`  Decision: `{payload['decision']}`  Builds on: exp-025, exp-028",
        f"Tagging fidelity: `{payload['tagging_fidelity']}`",
        "",
        f"- total rows: `{sc['total_rows']}`  tagged: `{sc['tagged_rows']}`  untagged: `{sc['untagged_rows']}`",
        f"- tiny-sample warning: `{sc['tiny_sample_warning']}` (needs >= {sc['min_rows_for_inference']} for inference)",
        "",
        "## Replacement value (vs SPY) by entry-time regime",
        "",
        "| regime | rows | mean RV vs SPY | mean exposure_scalar |",
        "|---|---:|---:|---:|",
    ]
    for label in ("risk_on_trend", "choppy_range", "risk_off_stress"):
        b = sc["by_regime"][label]
        lines.append(f"| {label} | {b['count']} | {b['mean_replacement_value_vs_spy_usd']} | {b['mean_exposure_scalar']} |")
    ct = sc["soft_tilt_counterfactual"]
    lines += [
        "",
        "## Soft-tilt counterfactual (observe-only)",
        "",
        f"- equal-weight mean RV vs SPY: `{ct['equal_weight_mean_rv_vs_spy_usd']}`",
        f"- exposure-weighted mean RV vs SPY: `{ct['exposure_weighted_mean_rv_vs_spy_usd']}`",
        f"- tilt gain: `{ct['tilt_gain_usd']}` USD (over {ct['rv_rows']} rows)",
        "",
        payload["interpretation"],
        "",
        "Re-run `quant/experiments/exp_20260615_030_regime_tagged_scorecard.py` to refresh as rows accumulate.",
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base019._write_json(OUT_JSON, payload)
    base019._write_json(SCORECARD_JSON, payload["scorecard"])
    base019._write_json(LOG_JSON, payload)
    base019._write_text(CARD_MD, _build_card(payload))
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "changed_variable": CHANGED_VARIABLE,
        "builds_on": payload["builds_on"],
        "hypothesis": payload["hypothesis"],
        "scorecard_summary": {
            "tagged_rows": payload["scorecard"]["tagged_rows"],
            "tiny_sample_warning": payload["scorecard"]["tiny_sample_warning"],
            "by_regime": payload["scorecard"]["by_regime"],
            "soft_tilt_counterfactual": payload["scorecard"]["soft_tilt_counterfactual"],
        },
        "production_impact": payload["production_impact"],
        "artifact": base019._repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    experiment_registry.append_log_entry(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": base019._repo_rel(OUT_JSON),
        "scorecard_artifact": payload["scorecard_artifact"],
        "tagged_rows": payload["scorecard"]["tagged_rows"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "summary": payload["decision"],
        "artifact": base019._repo_rel(OUT_JSON),
        "log": base019._repo_rel(LOG_JSON),
        "ticket_file": base019._repo_rel(TICKET_JSON),
        "card_file": base019._repo_rel(CARD_MD),
        "revision_manifest_file": base019._repo_rel(MANIFEST_JSON),
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    base019._write_json(MANIFEST_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
    })


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "scorecard": payload["scorecard"],
    }, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
