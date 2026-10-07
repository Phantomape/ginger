"""exp-20260915-005: old-versus-new settled-row split attribution of the consumed
exp-20260914-001 entity/theme axis-C cohort (loss_attribution / analysis_only).

Developmental diagnosis of an already-consumed fixed result.  The unchanged
208492-row settled cohort bound by exp-20260914-001 is split by identity key into
the OLD half (rows already settled at the exp-20260810-001 read) and the NEW half
(rows settled afterwards), and the unchanged exp-20260706-012 / exp-20260719-004
summary and acceptance arithmetic is applied to each half separately.  Nothing is
retuned, no prices are fetched, no reopen condition or threshold changes, the
result ceiling is observed_only and new_alpha_evidence is false by construction.
"""

from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260706_012_entity_theme_news_more_settled_forward_value.py"
)


def _load_base() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260706_012_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load base recipe: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = _load_base()
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

EXPERIMENT_ID = "exp-20260915-005"
UID = "expuid-792d6de6037d4663"
OWNER = "claude-scheduled-alpha"
LANE = "loss_attribution"
CHANGE_TYPE = "analysis_only"
TRIAL_FAMILY = "entity_theme_consumed_cohort_split_attribution"
SLUG = "entity_theme_axis_c_cohort_split_dilution_attribution_20260915"
RUNNER = f"quant/experiments/exp_20260915_005_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260915_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

LEDGER_NEW = (
    REPO_ROOT
    / "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260913.jsonl"
)
LEDGER_OLD = (
    REPO_ROOT
    / "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260810.jsonl"
)
ARTIFACT_0810 = (
    REPO_ROOT
    / "data/experiments/exp-20260810-001"
    / "exp_20260810_001_entity_theme_news_axis_c3_more_settled_forward_value_20260810.json"
)
ARTIFACT_0914 = (
    REPO_ROOT
    / "data/experiments/exp-20260914-001"
    / "exp_20260914_001_entity_theme_news_axis_c4_more_settled_forward_value_20260914.json"
)
PROTOCOL = REPO_ROOT / "docs" / "quant_agent_protocol_v2.md"

# Input identity pinned at freeze time (card measurement plan, 2026-09-15T16:18Z).
PINS = {
    "ledger_new": "1593fa0360aeb745f60232492fff685aa2c215a263a4f92c8e0f1701ece1c2e0",
    "ledger_old": "b5f02a24bfc6cbd16a2f0bd53e66bda333c7bee53097cec0b89f895928b6380d",
    "base_runner": "0b50bd27eca6a17c1a63969cef59e08267bff2fcbeb81e4bab647acfdb32b7a0",
    "artifact_0810": "094c4882171ec371044c5df6757a0368dc231e27884ece918ac0726082ede635",
    "artifact_0914": "c0be97c7184892db688d88c44b56fbc68e555befb40657381ba47ed4d782df6d",
}
OLD_EXIT_CUTOFF = "2026-08-07"
ID_FIELDS = (
    "observed_date",
    "entity_theme_query_id",
    "candidate_ticker",
    "candidate_item_index",
    "url",
    "entry_date",
    "exit_date",
    "horizon_trading_days",
    "published_at",
)
# Consumed values (read again from the pinned artifacts at runtime and cross-checked).
CONSUMED_0810 = {
    "settled_rows": 114541,
    "mean": {"cash": 47.5426, "spy": 25.2067, "qqq": 24.6434},
    "median": {"cash": 16.83, "spy": 18.12, "qqq": 13.30},
}
CONSUMED_0914 = {
    "settled_rows": 208492,
    "mean": {"cash": 48.4422, "spy": 24.0684, "qqq": 20.8692},
    "median": {"cash": 8.01, "spy": 3.12, "qqq": -1.50},
}
C0_COUNT_TOLERANCE = 0.001
C0_USD_TOLERANCE = 1.00

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260915_005_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRODUCTION_COMMANDS = [
    f"python -B -m py_compile {RUNNER_PS}",
    f"python -B {RUNNER_PS}",
    "python -B scripts\\experiment.py audit --lean-strict",
]

REFLECTION = {
    "source_decaying": {
        "why_result_happened": (
            "The NEW half (rows settled after the exp-20260810-001 read) carries negative "
            "row-mean replacement value versus both SPY and QQQ, so the 08-10 to 09-14 "
            "deterioration is not a dilution artifact: the more recent Jul-Sep 2026 rows of "
            "the unchanged six-query bundle lost benchmark-relative value while the OLD half "
            "reproduced the consumed 08-10 read within tolerance.  The 312738 same-face bar "
            "would by construction pool an already benchmark-negative recent slice with the "
            "old positive slice."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not reserve a regime-split, date-window, per-query, per-theme or per-ticker "
            "re-slice of this bundle as a separate face; do not retune queries, ticker maps, "
            "horizon, row size, response curves or thresholds; do not treat this diagnostic "
            "as alpha evidence or as a change to the frozen family reopen bar."
        ),
        "new_evidence_required": (
            "A separately pre-registered contract review (not enacted here) may make the "
            "fifth same-face override additionally require that the post-2026-09-13 "
            "incremental settled slice alone clears the unchanged median and breadth bars; "
            "otherwise the existing 312738 settled-row bar, a true canonical PIT historical "
            "news archive, or a materially richer independent entity-relation source."
        ),
    },
    "dilution_only": {
        "why_result_happened": (
            "The NEW half (rows settled after the exp-20260810-001 read) is not "
            "benchmark-negative on both SPY and QQQ row means but fails at least one of the "
            "unchanged median or breadth bars, so the 08-10 to 09-14 deterioration is near-zero "
            "heavy-tailed new rows diluting the older positive rows rather than a sign flip of "
            "the source; the OLD half reproduced the consumed 08-10 read within tolerance."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not reserve a regime-split, date-window, per-query, per-theme or per-ticker "
            "re-slice of this bundle as a separate face; do not retune queries, ticker maps, "
            "horizon, row size, response curves or thresholds; do not treat this diagnostic "
            "as alpha evidence or as a change to the frozen family reopen bar."
        ),
        "new_evidence_required": (
            "No change: the existing 312738 settled-row bar under the unchanged manifest, a "
            "true canonical PIT historical news archive, or a materially richer independent "
            "entity-relation source remain the only reopen paths."
        ),
    },
    "new_half_passes": {
        "why_result_happened": (
            "The NEW half alone passes the unchanged exp-20260719-004 acceptance rule while "
            "the pooled 208492-row cohort did not, so the pooled failure came from the OLD "
            "half's contribution; this is reported only, because a date-window face is a "
            "forbidden re-slice under exp-20260914-001."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not reserve the NEW half or any date-window slice as a separate face; do not "
            "retune queries, ticker maps, horizon, row size, response curves or thresholds; "
            "do not treat this diagnostic as alpha evidence."
        ),
        "new_evidence_required": (
            "The existing 312738 settled-row bar under the unchanged manifest, a true "
            "canonical PIT historical news archive, or a materially richer independent "
            "entity-relation source."
        ),
    },
    "identity_mismatch": {
        "why_result_happened": (
            "The OLD half reconstructed by identity key and exit_date cutoff did not "
            "reproduce the consumed exp-20260810-001 read within the frozen tolerance, so the "
            "split cannot be trusted and no dilution classification is reported."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not loosen the C0 tolerance or redefine the split after seeing values; do not "
            "reserve any re-slice of this bundle."
        ),
        "new_evidence_required": (
            "An identity-level repair that explains the ledger revision between the 08-10 "
            "read and the current 20260810 ledger file, registered as measurement_repair."
        ),
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def row_key(row: dict[str, Any]) -> tuple:
    return tuple(row.get(field) for field in ID_FIELDS)


def slim_summary(summary: dict[str, Any]) -> dict[str, Any]:
    observed = summary["observed_date_level"]
    return {
        "settled_rows": summary["settled_rows"],
        "query_group_count": summary["query_group_count"],
        "ticker_count": summary["ticker_count"],
        "theme_count": summary["theme_count"],
        "relation_type_count": summary["relation_type_count"],
        "row_level": summary["row_level"],
        "observed_date_level": {
            "observed_date_count": observed.get("observed_date_count"),
            "mean_of_date_mean_cash": observed.get("mean_of_date_mean_cash"),
            "mean_of_date_mean_spy": observed.get("mean_of_date_mean_spy"),
            "mean_of_date_mean_qqq": observed.get("mean_of_date_mean_qqq"),
        },
        "positive_query_groups_vs_spy_and_qqq": summary["positive_query_groups_vs_spy_and_qqq"],
        "positive_query_groups_vs_spy_and_qqq_ids": [
            row.get("entity_theme_query_id")
            for row in summary["positive_query_groups_vs_spy_and_qqq_sample"]
        ],
        "max_positive_cash_query_share": summary["max_positive_cash_query_share"],
        "max_positive_cash_ticker_share": summary["max_positive_cash_ticker_share"],
        "query_group_table": [
            {
                "entity_theme_query_id": row.get("entity_theme_query_id"),
                "row_count": row.get("row_count"),
                "mean_cash": row.get("mean_cash"),
                "mean_spy": row.get("mean_spy"),
                "mean_qqq": row.get("mean_qqq"),
                "median_cash": row.get("median_cash"),
            }
            for row in summary["top_queries_by_cash"]
        ],
    }


def half_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = base.current_summary(rows, rows)
    gate = base.acceptance(summary)
    return {"summary": slim_summary(summary), "acceptance": gate}


def classify(new_half: dict[str, Any]) -> str:
    row = new_half["summary"]["row_level"]
    spy_mean = row["spy"]["mean"] or 0.0
    qqq_mean = row["qqq"]["mean"] or 0.0
    if spy_mean < 0 and qqq_mean < 0:
        return "source_decaying"
    if new_half["acceptance"]["passed"]:
        return "new_half_passes"
    return "dilution_only"


def monthly_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, list[float]]] = collections.defaultdict(
        lambda: {"cash": [], "spy": [], "qqq": []}
    )
    for row in rows:
        bucket = by_date[row["observed_date"]]
        for key, field in base.VALUE_FIELDS.items():
            bucket[key].append(base.number(row.get(field)))
    by_month: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"row_count": 0, "date_means": {"cash": [], "spy": [], "qqq": []}, "cash_rows": []}
    )
    for observed_date, bucket in by_date.items():
        month = by_month[observed_date[:7]]
        month["row_count"] += len(bucket["cash"])
        month["cash_rows"].extend(bucket["cash"])
        for key in ("cash", "spy", "qqq"):
            month["date_means"][key].append(statistics.fmean(bucket[key]))
    out = []
    for month in sorted(by_month):
        item = by_month[month]
        out.append(
            {
                "observed_month": month,
                "row_count": item["row_count"],
                "observed_date_count": len(item["date_means"]["cash"]),
                "mean_of_date_mean_cash": round(statistics.fmean(item["date_means"]["cash"]), 4),
                "mean_of_date_mean_spy": round(statistics.fmean(item["date_means"]["spy"]), 4),
                "mean_of_date_mean_qqq": round(statistics.fmean(item["date_means"]["qqq"]), 4),
                "row_median_cash": round(statistics.median(item["cash_rows"]), 4),
            }
        )
    return out


def c0_check(old_half: dict[str, Any], consumed: dict[str, Any], count_expected: int) -> dict[str, Any]:
    row = old_half["summary"]["row_level"]
    count = int(old_half["summary"]["settled_rows"])
    checks = {
        "count_within_tolerance": abs(count - count_expected) <= C0_COUNT_TOLERANCE * count_expected,
    }
    deltas: dict[str, float] = {}
    for stat in ("mean", "median"):
        for key in ("cash", "spy", "qqq"):
            delta = round(float(row[key][stat]) - float(consumed[stat][key]), 4)
            deltas[f"{stat}_{key}"] = delta
            checks[f"{stat}_{key}_within_tolerance"] = abs(delta) <= C0_USD_TOLERANCE
    return {
        "count": count,
        "count_expected": count_expected,
        "count_delta": count - count_expected,
        "deltas_usd": deltas,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _toy_row(cash: float, spy: float, qqq: float, index: int, query: str = "q1") -> dict[str, Any]:
    return {
        "outcome_status": "settled",
        "horizon_trading_days": 10,
        "replacement_value_vs_cash_usd": cash,
        "replacement_value_vs_spy_usd": spy,
        "replacement_value_vs_qqq_usd": qqq,
        "observed_date": f"2026-01-{index:02d}",
        "entry_date": f"2026-01-{index + 1:02d}",
        "exit_date": f"2026-02-{index:02d}",
        "entity_theme_query_id": query,
        "candidate_ticker": f"T{index}",
        "candidate_item_index": index,
        "url": f"u{index}",
        "published_at": f"2026-01-{index:02d}T00:00:00Z",
        "theme": "t",
        "relation_type": "r",
    }


def synthetic_self_test() -> dict[str, Any]:
    old_rows = [_toy_row(10, 10, 10, 1), _toy_row(20, 20, 20, 2)]
    new_neg = [_toy_row(-5, -5, -5, 3), _toy_row(1, 1, 1, 4)]
    new_mixed = [_toy_row(-1, -1, -1, 5), _toy_row(2, 2, 2, 6)]
    pooled = base.settled_rows(old_rows + new_neg)
    old_keys = {row_key(row) for row in base.settled_rows(old_rows)}
    old_half = [row for row in pooled if row_key(row) in old_keys]
    new_half = [row for row in pooled if row_key(row) not in old_keys]
    assert len(old_half) == 2 and len(new_half) == 2
    assert base.stats(base.values_by_field(old_half)["cash"])["median"] == 15.0
    assert base.stats(base.values_by_field(new_half)["cash"])["median"] == -2.0
    assert base.stats(base.values_by_field(new_half)["cash"])["mean"] == -2.0
    assert base.stats(base.values_by_field(pooled)["cash"])["median"] == 5.5
    assert classify(half_report(new_half)) == "source_decaying"
    assert classify(half_report(new_mixed)) == "dilution_only"
    months = monthly_table(new_mixed)
    assert months[0]["row_count"] == 2 and months[0]["mean_of_date_mean_cash"] == 0.5
    return {
        "passed": True,
        "cases": [
            "OLD {+10,+20} median 15; NEW {-5,+1} median -2 mean -2; pooled median 5.5",
            "NEW {-5,+1} vs SPY/QQQ both negative -> source_decaying",
            "NEW {-1,+2} mean +0.5 breadth 1 of 1 < 4 -> dilution_only",
        ],
    }


def verify_pins() -> dict[str, str]:
    actual = {
        "ledger_new": digest(LEDGER_NEW),
        "ledger_old": digest(LEDGER_OLD),
        "base_runner": digest(BASE_RUNNER),
        "artifact_0810": digest(ARTIFACT_0810),
        "artifact_0914": digest(ARTIFACT_0914),
    }
    drift = {name: (PINS[name], actual[name]) for name in PINS if PINS[name] != actual[name]}
    if drift:
        raise RuntimeError(f"input hash drift, stop before output: {drift}")
    return actual


def consumed_from_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    row = payload["summary"]["row_level"]
    return {
        "settled_rows": int(payload["summary"]["settled_rows"]),
        "mean": {key: row[key]["mean"] for key in ("cash", "spy", "qqq")},
        "median": {key: row[key]["median"] for key in ("cash", "spy", "qqq")},
        "decision": payload.get("decision"),
        "failed_reasons": (payload.get("gate4") or {}).get("failed_reasons"),
    }


def build_result() -> dict[str, Any]:
    if OUT_JSON.exists():
        raise RuntimeError("one-shot artifact already exists; do not overwrite or rerun")
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
    expected = (UID, "claimed", OWNER, LANE, CHANGE_TYPE, TRIAL_FAMILY)
    actual = (
        ticket.get("experiment_uid"),
        ticket.get("status"),
        ticket.get("owner"),
        ticket.get("lane"),
        ticket.get("change_type"),
        ticket.get("trial_family"),
    )
    if actual != expected:
        raise RuntimeError(f"ticket identity mismatch: expected {expected}, got {actual}")
    ticket_sha = digest(TICKET_JSON)
    card_sha = digest(CARD_MD)
    pins = verify_pins()
    self_test = synthetic_self_test()
    consumed_0810 = consumed_from_artifact(ARTIFACT_0810)
    consumed_0914 = consumed_from_artifact(ARTIFACT_0914)
    for label, consumed, frozen in (
        ("exp-20260810-001", consumed_0810, CONSUMED_0810),
        ("exp-20260914-001", consumed_0914, CONSUMED_0914),
    ):
        if consumed["settled_rows"] != frozen["settled_rows"]:
            raise RuntimeError(f"{label} settled_rows drift vs frozen constant")
        for stat in ("mean", "median"):
            for key in ("cash", "spy", "qqq"):
                if abs(float(consumed[stat][key]) - float(frozen[stat][key])) > 1e-6:
                    raise RuntimeError(f"{label} {stat} {key} drift vs frozen constant")

    source_rows = base.read_jsonl(LEDGER_NEW)
    settled = base.settled_rows(source_rows)
    old_source_rows = base.read_jsonl(LEDGER_OLD)
    old_settled = base.settled_rows(old_source_rows)
    old_keys_all = {row_key(row) for row in old_settled}
    old_keys = {row_key(row) for row in old_settled if str(row.get("exit_date")) <= OLD_EXIT_CUTOFF}
    settled_keys = [row_key(row) for row in settled]
    duplicate_keys = len(settled_keys) - len(set(settled_keys))
    old_half_rows = [row for row in settled if row_key(row) in old_keys]
    new_half_rows = [row for row in settled if row_key(row) not in old_keys]
    identity = {
        "id_fields": list(ID_FIELDS),
        "old_exit_date_cutoff": OLD_EXIT_CUTOFF,
        "pooled_settled_rows": len(settled),
        "pooled_duplicate_keys": duplicate_keys,
        "old_ledger_settled_rows": len(old_settled),
        "old_ledger_settled_rows_exit_at_or_before_cutoff": len(old_keys),
        "old_ledger_settled_keys_still_present_in_pooled": len(old_keys_all & set(settled_keys)),
        "old_half_rows": len(old_half_rows),
        "new_half_rows": len(new_half_rows),
        "old_half_plus_new_half_equals_pooled": len(old_half_rows) + len(new_half_rows) == len(settled),
        "old_half_observed_date_range": [
            min(row["observed_date"] for row in old_half_rows),
            max(row["observed_date"] for row in old_half_rows),
        ],
        "new_half_observed_date_range": [
            min(row["observed_date"] for row in new_half_rows),
            max(row["observed_date"] for row in new_half_rows),
        ],
        "new_half_exit_date_range": [
            min(row["exit_date"] for row in new_half_rows),
            max(row["exit_date"] for row in new_half_rows),
        ],
    }
    if duplicate_keys or not identity["old_half_plus_new_half_equals_pooled"]:
        raise RuntimeError(f"identity split invalid: {identity}")

    pooled = half_report(settled)
    old_half = half_report(old_half_rows)
    new_half = half_report(new_half_rows)
    c0 = c0_check(old_half, CONSUMED_0810, CONSUMED_0810["settled_rows"])
    pooled_reproduction = c0_check(pooled, CONSUMED_0914, CONSUMED_0914["settled_rows"])

    if c0["passed"]:
        classification = classify(new_half)
        disposition = "developmental_diagnosis"
    else:
        classification = None
        disposition = "identity_mismatch"
    reflection_key = classification or "identity_mismatch"
    reflection = dict(REFLECTION[reflection_key])
    reflection["realized_failure_mode"] = {
        "source_decaying": "new_half_benchmark_relative_negative",
        "dilution_only": "new_half_near_zero_dilution",
        "new_half_passes": "none",
        None: "old_half_identity_mismatch",
    }[classification]

    decision = "observed_only"
    status = "observed_only"
    prediction = ticket.get("prediction")
    result = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": UID,
        "owner": OWNER,
        "lane": LANE,
        "change_type": CHANGE_TYPE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": ticket.get("trial_variant_id"),
        "mechanism_family": ticket.get("mechanism_family"),
        "record_type": "consumed_result_attribution",
        "status": status,
        "decision": decision,
        "disposition": disposition,
        "classification": classification,
        "timestamp": utc_now(),
        "hypothesis": ticket.get("hypothesis"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "prior_trial_count": ticket.get("prior_trial_count"),
        "new_alpha_evidence": False,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "paper_live_eligible": False,
        "trade_enabled": False,
        "order_intent_count": 0,
        "economic_progress": False,
        "gate_applicability": (
            "All checks are descriptive diagnostics of an already-consumed result; they are "
            "not strategy Gate metrics, not alpha acceptance evidence, and change no reopen "
            "condition or threshold."
        ),
        "metrics": {
            key: None
            for key in (
                "expected_value_score",
                "max_drawdown_pct",
                "sharpe",
                "sharpe_daily",
                "survival_rate",
                "total_pnl",
                "total_return_pct",
                "trade_count",
                "win_rate",
            )
        },
        "runtime": {
            "worktree": REPO_ROOT.as_posix(),
            "branch": "fix/alpha-score-sleeve-same-day-idempotency",
            "head": "f978e063a91b2621ac5c75341d868eca7eed5bf0",
            "authoritative_state_ref": "refs/heads/automation/edge-v2",
            "operational_role": "production_maintenance lane running a root-frozen fixed-result attribution",
            "protocol_path": repo_rel(PROTOCOL),
            "protocol_sha256": digest(PROTOCOL),
            "python": sys.version.split()[0],
        },
        "code": {"path": RUNNER, "sha256": digest(REPO_ROOT / RUNNER)},
        "claimed_ticket_sha256": ticket_sha,
        "measurement_plan_card_sha256_before_run": card_sha,
        "inputs": {
            "ledger_new": {"path": repo_rel(LEDGER_NEW), "sha256": pins["ledger_new"], "role": "exact cohort bound by exp-20260914-001"},
            "ledger_old": {
                "path": repo_rel(LEDGER_OLD),
                "sha256": pins["ledger_old"],
                "role": "identity source for the OLD half; byte image read by exp-20260810-001 (manifest sha 190dd09254dd650c7e48c25d97627e4108f083882f538f3fbaf57b49c0be8d06) was overwritten by the 2026-08-10 evening daily run, so exit_date <= 2026-08-07 approximates that read",
            },
            "base_runner": {"path": repo_rel(BASE_RUNNER), "sha256": pins["base_runner"], "role": "unchanged summary and acceptance arithmetic"},
            "artifact_0810": {"path": repo_rel(ARTIFACT_0810), "sha256": pins["artifact_0810"], "consumed": consumed_0810},
            "artifact_0914": {"path": repo_rel(ARTIFACT_0914), "sha256": pins["artifact_0914"], "consumed": consumed_0914},
        },
        "synthetic_self_test": self_test,
        "identity_split": identity,
        "c0_old_half_reproduction_of_exp_20260810_001": c0,
        "pooled_reproduction_of_exp_20260914_001": pooled_reproduction,
        "classification_rule": {
            "source_decaying": "NEW-half row means versus SPY and versus QQQ both negative",
            "new_half_passes": "NEW half alone passes the unchanged exp-20260719-004 acceptance rule",
            "dilution_only": "otherwise",
            "gated_on": "C0 passed",
        },
        "halves": {
            "pooled": pooled,
            "old_half": old_half,
            "new_half": new_half,
        },
        "descriptive_monthly_mean_of_date_means": {
            "old_half": monthly_table(old_half_rows),
            "new_half": monthly_table(new_half_rows),
        },
        "limitations": [
            "Fixed-result diagnosis of consumed rows; no fresh alpha evidence, no independent sample count.",
            "The OLD half approximates the 08-10 cohort by identity key and exit_date cutoff because the exact ledger bytes read on 08-10 were overwritten that evening; C0 tolerance bounds the approximation.",
            "Rows overlap in holding periods and share observed dates; halves are not independent samples.",
            "Original family status, streak and reopen conditions remain unchanged by this ticket.",
        ],
        "budget": {"attribution_executions": 1, "new_strategy_variants": 0, "external_spend": 0, "http_requests": 0},
        "prediction": prediction,
        "post_run_reflection": reflection,
        "next_retry_requires": reflection["new_evidence_required"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "related_files": [repo_rel(ARTIFACT_0914), repo_rel(OUT_JSON)],
        "research_refs": [],
        "notes": (
            "Developmental diagnosis of the consumed exp-20260914-001 result only; no new alpha "
            "evidence, no strategy change, no reopen-condition change; observed_only ceiling."
        ),
    }
    return result


def build_card_section(result: dict[str, Any]) -> str:
    c0 = result["c0_old_half_reproduction_of_exp_20260810_001"]
    new_half = result["halves"]["new_half"]["summary"]
    old_half = result["halves"]["old_half"]["summary"]
    lines = [
        "",
        "## Result (single execution)",
        "",
        f"- Status: `{result['status']}` / disposition `{result['disposition']}` / classification `{result['classification']}`",
        f"- Identity split: pooled `{result['identity_split']['pooled_settled_rows']}` = old `{result['identity_split']['old_half_rows']}` + new `{result['identity_split']['new_half_rows']}`; duplicate keys `{result['identity_split']['pooled_duplicate_keys']}`",
        f"- C0 (old half vs consumed 08-10): passed `{c0['passed']}`, count delta `{c0['count_delta']}`, deltas USD `{c0['deltas_usd']}`",
        f"- Old half row mean cash/SPY/QQQ: `{old_half['row_level']['cash']['mean']}` / `{old_half['row_level']['spy']['mean']}` / `{old_half['row_level']['qqq']['mean']}`; medians `{old_half['row_level']['cash']['median']}` / `{old_half['row_level']['spy']['median']}` / `{old_half['row_level']['qqq']['median']}`",
        f"- New half row mean cash/SPY/QQQ: `{new_half['row_level']['cash']['mean']}` / `{new_half['row_level']['spy']['mean']}` / `{new_half['row_level']['qqq']['mean']}`; medians `{new_half['row_level']['cash']['median']}` / `{new_half['row_level']['spy']['median']}` / `{new_half['row_level']['qqq']['median']}`; query groups beating SPY and QQQ `{new_half['positive_query_groups_vs_spy_and_qqq']}` of `{new_half['query_group_count']}`",
        f"- New half acceptance failed reasons: `{result['halves']['new_half']['acceptance']['failed_reasons']}`",
        f"- Artifact: `{result['artifact']}`",
        "",
        "### Reflection",
        "",
        f"- Why: {result['post_run_reflection']['why_result_happened']}",
        f"- Forbidden near-neighbor retry: {result['post_run_reflection']['forbidden_near_neighbor_retry']}",
        f"- New evidence required: {result['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def write_manifest(result: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LEDGER_NEW,
        LEDGER_OLD,
        BASE_RUNNER,
        ARTIFACT_0810,
        ARTIFACT_0914,
    ]
    base.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "experiment_uid": UID,
            "status": result["status"],
            "decision": result["decision"],
            "classification": result["classification"],
            "generated_at": utc_now(),
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "files": [
                {"path": repo_rel(path), "exists": path.exists(), "sha256": base.sha256(path)}
                for path in paths
            ],
        },
    )


def persist(result: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
    with OUT_JSON.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    save_experiment_log_entry(result, allow_duplicate=False, expected_experiment_id=EXPERIMENT_ID)
    with CARD_MD.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(build_card_section(result))
    persist_self_registered_result(
        base.REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": result["decision"],
            "disposition": result["disposition"],
            "classification": result["classification"],
            "artifact": result["artifact"],
            "artifact_sha256": digest(OUT_JSON),
            "log": result["log"],
            "runner": RUNNER,
            "c0": result["c0_old_half_reproduction_of_exp_20260810_001"],
            "new_half_acceptance": result["halves"]["new_half"]["acceptance"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "implementation_mode": "consumed_result_attribution",
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "card": result["card"],
            "manifest": result["manifest"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "lean_quality_passed": True,
        },
    )
    write_manifest(result)


def main() -> int:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "disposition": result["disposition"],
                "classification": result["classification"],
                "c0_passed": result["c0_old_half_reproduction_of_exp_20260810_001"]["passed"],
                "artifact": result["artifact"],
                "artifact_sha256": digest(OUT_JSON),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
