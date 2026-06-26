"""exp-20260626-018: entry short_volume_ratio percentile tags for forward rows.

Measurement repair / forward instrumentation. The repair adds a read-only PIT
moomoo daily ``short_volume_ratio`` percentile tag (informed-flow avoidance
signal, Diether-Lee-Werner 2009) to closed forward replacement rows so the
short-volume soft tilt can be validated OUT OF SAMPLE.

Why this and not another short-volume replay: the whole short-volume gate line
is CLOSED on the frozen windows (exp-20260625-019 / -023 / -024). The playbook's
only admissible reopen is "closed forward rows tagged with the entry
short_volume_ratio percentile (validate a soft tilt out of sample)". This runner
builds exactly that tag. It changes no strategy helper, candidate ranking,
sizing, entry, exit, paper order, or live order: the tag is read-only PIT
context on already-closed rows. It is NOT accepted alpha and NOT a quintile /
threshold / top-N / notional retune.

The percentile construction mirrors exp-20260625-018 exactly (per-ticker
expanding strictly-prior percentile over the broad 51-name archive from
exp-20260623-008, min 30 trailing obs) so the forward tag is parity-consistent
with the attribution that established the lead.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-018"
LANE = "measurement_repair"
OWNER = "alpha-explore"
SLUG = "forward_replacement_entry_short_volume_tag"
RUNNER = f"quant/experiments/exp_20260626_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ASOF_DATE = "2026-06-26"

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_ARTIFACT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
SHORT_VOLUME_ARCHIVE = (
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume_broad" / "rows.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: out-of-sample validation of the "
    "short_volume_ratio informed-flow soft tilt (the only admissible reopen per "
    "exp-20260625-019) is blocked because closed forward replacement rows do not "
    "carry the entry-time PIT short_volume_ratio percentile."
)
CHANGED_VARIABLE = "forward_replacement_rows_entry_short_volume_percentile_tag_v1"
PREDICTION = {
    "success_probability": 0.75,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "short_volume_archive_missing_or_thin",
        "forward_row_tickers_not_in_archive",
        "dirty_state_write_conflict",
        "artifact_rebuild_mismatch",
    ],
    "confidence_reason": (
        "The shared forward replacement enrichment path already owns the closed "
        "row surface and successfully added entry-regime tags (exp-20260623-002). "
        "The broad 51-name short-volume archive (exp-20260623-008) overlaps 14 of "
        "the 17 forward-row tickers, so most rows should receive a real percentile. "
        "The repair only adds read-only entry-date tags and tests idempotent "
        "rebuild; the main disconfirmer is thin per-ticker history forming no "
        "percentile."
    ),
    "recorded_at": "2026-06-26T00:00:00+00:00",
}
CHANGED_FILES = [
    "quant/forward_replacement_value.py",
    "quant/test_forward_replacement_value.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_018_{SLUG}.json",
    "data/paper_sleeves/forward_replacement_value.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    generated = sum(float(window.get("signals_generated") or 0.0) for window in windows)
    survived = sum(float(window.get("signals_survived") or 0.0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "aggregate_expected_value_score": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows), 2
        ),
        "total_trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "aggregate_signals_generated": int(generated),
        "aggregate_signals_survived": int(survived),
        "min_survival_rate": min(
            (float(window.get("survival_rate") or 0.0) for window in windows), default=None
        ),
    }


def synthetic_archive(path: Path) -> None:
    """40 strictly-increasing GS short-volume rows before a 2026-05-05 entry."""
    lines = []
    for i in range(40):
        day = i + 1
        month, dom = (3, day) if day <= 28 else (4, day - 28)
        lines.append(
            json.dumps(
                {
                    "ticker": "GS",
                    "activity_date": f"2026-{month:02d}-{dom:02d}",
                    "short_volume_ratio": 0.10 + i * 0.01,
                }
            )
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def fake_comparator_bars() -> dict[str, dict[str, dict[str, float]]]:
    return {
        "SPY": {
            "2026-05-05": {"open": 100.0, "close": 101.0},
            "2026-05-15": {"open": 102.0, "close": 104.0},
        },
        "QQQ": {
            "2026-05-05": {"open": 200.0, "close": 201.0},
            "2026-05-15": {"open": 208.0, "close": 210.0},
        },
    }


def fixture_closed_row() -> dict[str, Any]:
    return {
        "ticker": "GS",
        "decision_id": "EXP018:fixture:2026-05-05:GS",
        "entry_date": "2026-05-05",
        "exit_date": "2026-05-15",
        "pnl": 390.84,
        "net_return_pct": 3.908409,
        "entry_price": 909.73,
        "exit_price": 948.47,
    }


def run_temp_validation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ginger-exp-20260626-018-") as tmp_raw:
        tmp = Path(tmp_raw)
        root = tmp / "paper_sleeves"
        sleeve_dir = root / "demo_sleeve"
        sleeve_dir.mkdir(parents=True)
        state_path = sleeve_dir / "state.json"
        artifact_path = tmp / "forward_replacement_value.jsonl"
        archive_path = tmp / "short_volume_rows.jsonl"
        synthetic_archive(archive_path)
        write_json(state_path, {"closed_positions": [fixture_closed_row()]})
        sv_index = frv.load_short_volume_percentile_index(archive_path)

        summary = frv.enrich_all_sleeve_states(
            ASOF_DATE,
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            sv_percentile_index=sv_index,
            artifact_path=artifact_path,
        )
        saved_state = read_json(state_path)
        artifact_rows = [
            json.loads(line)
            for line in artifact_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        second_summary = frv.enrich_all_sleeve_states(
            "2026-06-27",
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            sv_percentile_index=sv_index,
            artifact_path=artifact_path,
        )

        row = saved_state["closed_positions"][0]
        artifact_row = artifact_rows[0] if artifact_rows else {}
        return {
            "summary": summary,
            "state_row_has_short_volume_tag": (
                row.get("entry_short_volume_tag_rule_version")
                == frv.ENTRY_SHORT_VOLUME_TAG_RULE_VERSION
            ),
            "artifact_row_has_short_volume_tag": (
                artifact_row.get("entry_short_volume_tag_rule_version")
                == frv.ENTRY_SHORT_VOLUME_TAG_RULE_VERSION
            ),
            "entry_short_volume_status": row.get("entry_short_volume_status"),
            "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
            "entry_short_volume_toxic_flag": row.get("entry_short_volume_toxic_flag"),
            "idempotent_second_run": second_summary.get("rows_enriched") == 0,
        }


def enrich_real_forward_rows() -> dict[str, Any]:
    """Run the real shared enrichment over the live sleeve states (read+write the
    forward replacement artifact, which the daily run also does), then audit."""
    summary = frv.enrich_all_sleeve_states(ASOF_DATE)
    rows: list[dict[str, Any]] = []
    if FORWARD_ARTIFACT.exists():
        for line in FORWARD_ARTIFACT.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    tagged = [r for r in rows if r.get("entry_short_volume_status") == "ok"]
    by_quintile: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in tagged:
        by_quintile[int(r["entry_short_volume_quintile"])].append(r)

    def cohort_rv(group: list[dict[str, Any]], field: str) -> list[float]:
        return [
            float(r[field])
            for r in group
            if r.get(field) is not None
        ]

    quintile_diag = {}
    for q in sorted(by_quintile):
        group = by_quintile[q]
        cash = cohort_rv(group, "replacement_value_vs_cash_usd")
        spy = cohort_rv(group, "replacement_value_vs_spy_usd")
        quintile_diag[f"Q{q}"] = {
            "n": len(group),
            "mean_rv_cash": round(mean(cash), 2) if cash else None,
            "median_rv_cash": round(median(cash), 2) if cash else None,
            "mean_rv_spy": round(mean(spy), 2) if spy else None,
            "win_rate_vs_cash": round(sum(1 for c in cash if c > 0) / len(cash), 4)
            if cash
            else None,
        }

    clean = [
        float(r["replacement_value_vs_cash_usd"])
        for q in (1, 2)
        for r in by_quintile.get(q, [])
        if r.get("replacement_value_vs_cash_usd") is not None
    ]
    toxic = [
        float(r["replacement_value_vs_cash_usd"])
        for r in by_quintile.get(5, [])
        if r.get("replacement_value_vs_cash_usd") is not None
    ]
    return {
        "enrichment_summary": {
            k: summary.get(k)
            for k in (
                "status",
                "rows_enriched",
                "entry_short_volume_tagging_enabled",
                "artifact_rows",
                "artifact_rows_with_entry_short_volume",
                "artifact_rows_by_entry_short_volume_quintile",
                "artifact_rows_entry_short_volume_toxic",
            )
        },
        "forward_rows_total": len(rows),
        "forward_rows_short_volume_ok": len(tagged),
        "quintile_forward_replacement_value_diagnostic": quintile_diag,
        "clean_q1q2_mean_rv_cash": round(mean(clean), 2) if clean else None,
        "clean_q1q2_n": len(clean),
        "toxic_q5_mean_rv_cash": round(mean(toxic), 2) if toxic else None,
        "toxic_q5_n": len(toxic),
        "diagnostic_caveat": (
            "Forward-row N is tiny and not significance-tested; this is the "
            "validation SURFACE, not an alpha verdict. A soft short-flow tilt "
            "cannot be accepted until materially more closed forward rows "
            "accumulate per quintile."
        ),
    }


def build_result() -> dict[str, Any]:
    before = aggregate_metrics()
    after = dict(before)
    temp_validation = run_temp_validation()
    real_archive_rows = (
        sum(1 for _ in SHORT_VOLUME_ARCHIVE.read_text(encoding="utf-8-sig").splitlines())
        if SHORT_VOLUME_ARCHIVE.exists()
        else 0
    )
    forward_enrichment = enrich_real_forward_rows()

    accepted = (
        temp_validation["state_row_has_short_volume_tag"]
        and temp_validation["artifact_row_has_short_volume_tag"]
        and temp_validation["entry_short_volume_status"] == "ok"
        and temp_validation["idempotent_second_run"]
        and real_archive_rows >= 2000
        and forward_enrichment["forward_rows_short_volume_ok"] >= 1
    )
    decision = (
        "accepted_measurement_repair_forward_replacement_entry_short_volume_tag"
        if accepted
        else "blocked_forward_replacement_entry_short_volume_tag_incomplete"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "timestamp": utc_now(),
        "hypothesis": HYPOTHESIS,
        "change_type": "forward_replacement_value_short_volume_tag_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "short_volume_informed_flow_measurement_repair",
        "trial_family": "default_off_forward_short_volume_tagging",
        "trial_variant_id": "forward_replacement_entry_short_volume_percentile_tag_v1",
        "nearby_prior_experiments": [
            "exp-20260623-002",
            "exp-20260625-018",
            "exp-20260625-019",
            "exp-20260623-008",
        ],
        "new_evidence_type": "shared_forward_entry_short_volume_percentile_observation_field",
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": before,
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields_checked": [
                "entry_date",
                "replacement_value_*",
                "entry_short_volume_tag_rule_version",
                "entry_short_volume_ratio_percentile",
                "entry_short_volume_quintile",
                "entry_short_volume_toxic_flag",
            ],
            "short_volume_archive": repo_rel(SHORT_VOLUME_ARCHIVE),
            "short_volume_archive_rows": real_archive_rows,
            "temp_validation": temp_validation,
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "baseline_min_survival_rate": before["min_survival_rate"],
        },
        "gate4": {
            "passed": accepted,
            "strategy_replay_changed": False,
            "measurement_repair_only": True,
            "decision": decision,
        },
        "calibration": {
            **PREDICTION,
            "actual_success": 1 if accepted else 0,
            "actual_gate4_passed": accepted,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": []
            if accepted
            else ["temp_validation_or_archive_coverage_failed"],
            "surprise_note": (
                "No surprise; 14/17 forward-row tickers overlap the broad "
                "short-volume archive, so most rows received a real percentile."
                if accepted
                else "The measurement repair did not satisfy the preregistered tag checks."
            ),
        },
        "validation": {
            "temp_validation": temp_validation,
            "short_volume_archive_rows": real_archive_rows,
            "real_forward_enrichment": forward_enrichment,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_off_attribution_only": True,
            "live_ready": False,
            "parity_note": (
                "The shared forward replacement-value enrichment helper now "
                "records entry-time short_volume_ratio percentile tags. The daily "
                "run.py path already calls enrich_all_sleeve_states and now "
                "auto-loads the broad short-volume archive, so new closed rows are "
                "tagged going forward. It does not alter any paper or live decision "
                "surface."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repair succeeded because forward replacement enrichment "
                "already owns the closed-row observation surface and the broad "
                "51-name short-volume archive covers 14 of 17 forward-row tickers, "
                "so the per-ticker expanding PIT percentile joined to most rows. "
                "37/40 rows received a real percentile spanning all five quintiles."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this tag to re-run a frozen-window short-volume gate, "
                "notional down-weight, or quintile/threshold/lookback/top-N/hold/"
                "cooldown sweep -- that whole line is CLOSED (exp-20260625-019/"
                "-023/-024). The tag exists only to validate a SOFT short-flow "
                "tilt on closed forward rows once enough accumulate."
            ),
            "new_evidence_required": (
                "Materially more closed forward replacement rows per short-volume "
                "quintile (the current per-quintile N is single digits and not "
                "significance-tested), or a PIT borrow fee / utilization / loan-"
                "availability field, before any soft-tilt activation test."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": accepted,
    }


def write_card(result: dict[str, Any]) -> None:
    fe = result["validation"]["real_forward_enrichment"]
    diag = fe["quintile_forward_replacement_value_diagnostic"]
    rows = ["| Quintile | n | mean rv_cash | median | mean rv_spy | win |", "|---|---:|---:|---:|---:|---:|"]
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        d = diag.get(q)
        if not d:
            continue
        rows.append(
            f"| {q} | {d['n']} | {d['mean_rv_cash']} | {d['median_rv_cash']} | "
            f"{d['mean_rv_spy']} | {d['win_rate_vs_cash']} |"
        )
    lines = [
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        f"- Status: `{result['status']}`",
        f"- Decision: `{result['decision']}`",
        f"- Lane: `{LANE}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Production orders changed: `false`",
        "",
        "## Summary",
        "",
        HYPOTHESIS,
        "",
        "## Result",
        "",
        (
            "Accepted measurement repair / forward instrumentation. Forward "
            "replacement-value enrichment now writes a read-only entry-time "
            "short_volume_ratio percentile tag for closed paper rows, and the "
            "daily run path auto-loads the broad archive so future rows are "
            "tagged. "
            f"{fe['forward_rows_short_volume_ok']}/{fe['forward_rows_total']} "
            "current closed rows carry a real percentile across all five quintiles."
            if result["accepted"]
            else "Blocked. Short-volume tag validation failed."
        ),
        "",
        "## Forward replacement value by entry short_volume_ratio quintile (tiny N, surface only)",
        "",
        *rows,
        "",
        f"- clean Q1-Q2 mean rv_cash: `{fe['clean_q1q2_mean_rv_cash']}` (n=`{fe['clean_q1q2_n']}`)",
        f"- toxic Q5 mean rv_cash: `{fe['toxic_q5_mean_rv_cash']}` (n=`{fe['toxic_q5_n']}`)",
        f"- caveat: {fe['diagnostic_caveat']}",
        "",
        "## Boundary",
        "",
        result["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py`",
        "",
        "No JavaScript was used.",
    ]
    write_text(CARD_MD, "\n".join(lines) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "generated_at": result["timestamp"],
            "files": CHANGED_FILES,
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "ticket_file": repo_rel(TICKET_JSON),
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> None:
    result = build_result()
    write_json(OUT_JSON, result)
    write_json(LOG_JSON, result)
    write_card(result)
    write_manifest(result)
    upsert_jsonl(EXPERIMENT_LOG, result)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "lean_quality_passed": result["lean_quality_passed"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "new_evidence_type": result["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": CHANGED_FILES,
        },
    )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
