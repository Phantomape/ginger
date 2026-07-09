"""exp-20260707-013: entity/theme news more-settled forward value.

Observed-only alpha refresh. This reuses the fixed source-bundle attribution
shape from exp-20260706-012, but points it at the 2026-07-06 entity/theme news
observer outcome ledger. The evidence axis is materially more settled forward
rows, not any query, theme, ticker, horizon, notional, or response retune.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260706_012_entity_theme_news_more_settled_forward_value.py"
)


def _load_base() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260706_012_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load base runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = _load_base()


EXPERIMENT_ID = "exp-20260707-013"
SLUG = "entity_theme_news_more_settled_forward_value_20260706"
RUNNER = f"quant/experiments/exp_20260707_013_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

base.EXPERIMENT_ID = EXPERIMENT_ID
base.SLUG = SLUG
base.RUNNER = RUNNER
base.RUNNER_PS = RUNNER_PS
base.RUNNER_COMMAND = RUNNER_COMMAND
base.LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260706.jsonl"
)
base.SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_summaries"
    / "entity_theme_news_observer_outcome_summary_20260706.json"
)
base.PRIOR_SOURCE_BUNDLE_LOG = (
    REPO_ROOT / "experiments" / "logs" / "exp-20260706-012.json"
)
base.PRIOR_SEC_CONFIRM_LOG = (
    REPO_ROOT / "experiments" / "logs" / "exp-20260705-017.json"
)
base.OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260707_013_{SLUG}.json"
base.LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
base.CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
base.MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
base.TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

base.HYPOTHESIS = (
    "Observed-only alpha refresh: with materially more settled entity/theme "
    "observer rows as of 2026-07-06, the unchanged fixed entity/theme source "
    "bundle may show stable 10-day replacement value versus cash, SPY, and QQQ "
    "before any shared helper is reconsidered."
)
base.ALPHA_HYPOTHESIS = (
    "If the entity/theme observer contains deployable event-relation alpha, "
    "the 2026-07-06 larger settled forward ledger should clear the unchanged "
    "fixed source-bundle bar without relying on any retuned query or theme map."
)
base.TRIAL_VARIANT_ID = "materially_more_settled_rows_20260706_v1"
base.CHANGED_VARIABLE = "entity_theme_news_source_bundle_more_settled_rows_20260706_v1"
base.NEW_EVIDENCE_AXIS = (
    "Materially more closed forward rows / settled forward rows: 2026-07-06 "
    "entity_theme_news outcome summary reports 13799 settled forward rows "
    "versus 8158 in exp-20260706-012 (+69.1%); fixed source manifest, horizon, "
    "notional, query/theme/ticker maps, and acceptance rule remain unchanged."
)
base.NEARBY_PRIORS = [
    "exp-20260703-014",
    "exp-20260705-017",
    "exp-20260706-012",
]
base.CAUSAL_COMPONENTS = [
    "read-only 2026-07-06 entity_theme_news observer outcome ledger analysis",
    "unchanged fixed source-bundle aggregate checks from exp-20260706-012",
    "materially-more-settled-row comparison versus prior ledgers",
    "theme/query/ticker/date concentration audit",
    "no strategy behavior change",
]
base.CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260707_013_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
base.REPRODUCTION_COMMANDS = [
    f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def _read_log(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def prior_counts() -> dict[str, Any]:
    source = _read_log(REPO_ROOT / "experiments" / "logs" / "exp-20260706-012.json")
    original = _read_log(REPO_ROOT / "experiments" / "logs" / "exp-20260703-014.json")
    confirm = _read_log(REPO_ROOT / "experiments" / "logs" / "exp-20260705-017.json")

    def row(exp: dict[str, Any]) -> dict[str, Any]:
        summary = exp.get("summary") or {}
        return {
            "settled_rows": summary.get("settled_rows"),
            "candidate_outcome_rows": summary.get("candidate_outcome_rows"),
            "decision": exp.get("decision"),
        }

    return {
        "exp-20260703-014": row(original),
        "exp-20260705-017": row(confirm),
        "exp-20260706-012": row(source),
    }


base.prior_counts = prior_counts
_base_build_result = base.build_result


def build_result() -> dict[str, Any]:
    result = _base_build_result()
    prior = prior_counts()
    previous_settled = int((prior["exp-20260706-012"] or {}).get("settled_rows") or 0)
    current_settled = int(result["summary"]["settled_rows"])
    result["delta_metrics"]["settled_rows_vs_exp_20260706_012"] = (
        current_settled - previous_settled
    )
    result["delta_metrics"]["settled_row_growth_vs_exp_20260706_012_pct"] = (
        round((current_settled - previous_settled) / previous_settled, 6)
        if previous_settled
        else None
    )
    result["prior_comparison"] = prior
    result["related_files"] = [
        RUNNER,
        base.repo_rel(BASE_RUNNER),
        base.repo_rel(base.LEDGER_JSONL),
        base.repo_rel(base.SUMMARY_JSON),
        "experiments/logs/exp-20260706-012.json",
        "experiments/logs/exp-20260705-017.json",
        "experiments/logs/exp-20260703-014.json",
    ]
    if result["gate4"]["failed_reasons"]:
        result["post_run_reflection"]["new_evidence_required"] = (
            "A true PIT historical news archive with observation-time availability, "
            "or another material batch of prospectively logged daily rows with at "
            "least +50% new settled cash/SPY/QQQ replacement-value outcomes under "
            "the same fixed manifest."
        )
    return result


base.build_result = build_result


if __name__ == "__main__":
    raise SystemExit(base.main())
