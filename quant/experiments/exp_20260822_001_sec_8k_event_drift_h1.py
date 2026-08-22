"""exp-20260822-001: complete prior-day SEC 8-K frame H1 drift scout.

The candidate set, one-session horizon, costs, comparators, and acceptance
rule were frozen before this runner accessed any price outcome.  This is an
observed-only research replay: it cannot change policy, orders, paper, or live
behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from moomoo import AuType, KLType, OpenQuoteContext, RET_OK  # noqa: E402


EXPERIMENT_ID = "exp-20260822-001"
OWNER = "codex-edge-v2-experiment"
SLUG = "sec_8k_event_drift_h1"
SCOUT_DIR = ROOT / "data" / "v2" / "scouts" / "sec_8k_event_drift_h1_20260821"
POOL_FILE = SCOUT_DIR / "candidate_pool.json"
RECIPE_FILE = SCOUT_DIR / "market_data_recipe.json"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
RAW_FILE = OUT_DIR / "moomoo_rth_daily_query_results.json"
ARTIFACT = OUT_DIR / f"exp_20260822_001_{SLUG}.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
RUNNER_REL = "quant/experiments/exp_20260822_001_sec_8k_event_drift_h1.py"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _verify_frozen_inputs(
    ticket: dict[str, Any], pool: dict[str, Any], recipe: dict[str, Any]
) -> dict[str, str]:
    if ticket.get("status") != "claimed" or ticket.get("owner") != OWNER:
        raise RuntimeError("experiment ticket must be claimed by the frozen owner")
    if pool.get("outcome_blind") is not True:
        raise RuntimeError("candidate pool is not outcome-blind")
    if pool.get("candidate_count") != len(pool.get("candidates") or []):
        raise RuntimeError("candidate pool count mismatch")
    if recipe.get("bar_date") != "2026-08-21":
        raise RuntimeError("unexpected evaluation date")
    if recipe.get("entry_field") != "open" or recipe.get("exit_field") != "close":
        raise RuntimeError("unexpected entry/exit recipe")
    if recipe.get("trade_enabled") is not False:
        raise RuntimeError("evaluation recipe must remain trade-disabled")
    if recipe.get("result_ceiling") != "observed_only":
        raise RuntimeError("evaluation recipe must remain observed-only")

    snapshot_by_locator = {
        row.get("locator"): row.get("sha256")
        for row in (
            (ticket.get("alpha_promotion_claim_receipt") or {}).get(
                "research_artifact_snapshots"
            )
            or []
        )
    }
    identities = {
        _repo_rel(POOL_FILE): _sha256(POOL_FILE),
        _repo_rel(RECIPE_FILE): _sha256(RECIPE_FILE),
    }
    for locator, actual in identities.items():
        expected = snapshot_by_locator.get(locator)
        if expected != actual:
            raise RuntimeError(
                f"frozen input identity mismatch for {locator}: {expected} != {actual}"
            )
    return identities


def _fetch_bars(codes: list[str], recipe: dict[str, Any]) -> dict[str, Any]:
    host, port_text = str(recipe["opend_endpoint"]).rsplit(":", 1)
    bar_date = str(recipe["bar_date"])
    queried_at = _now()
    rows: list[dict[str, Any]] = []
    quote_ctx = OpenQuoteContext(host=host, port=int(port_text))
    try:
        for index, code in enumerate(codes, start=1):
            ret, data, _page_key = quote_ctx.request_history_kline(
                code,
                start=bar_date,
                end=bar_date,
                ktype=KLType.K_DAY,
                autype=AuType.NONE,
                max_count=10,
            )
            row: dict[str, Any] = {
                "code": code,
                "requested_date": bar_date,
                "provider_return_code": int(ret),
            }
            if ret != RET_OK:
                row.update({"status": "provider_error", "error": str(data)})
            elif getattr(data, "empty", True):
                row.update({"status": "missing", "error": "empty response"})
            else:
                exact = data[data["time_key"].astype(str).str.startswith(bar_date)]
                if exact.empty:
                    row.update(
                        {
                            "status": "missing",
                            "error": "requested session absent from response",
                        }
                    )
                else:
                    record = exact.iloc[0]
                    open_price = _finite_number(record.get("open"))
                    close_price = _finite_number(record.get("close"))
                    if open_price is None or close_price is None or open_price <= 0:
                        row.update(
                            {
                                "status": "invalid_bar",
                                "error": "non-finite or non-positive price",
                            }
                        )
                    else:
                        row.update(
                            {
                                "status": "usable",
                                "time_key": str(record.get("time_key")),
                                "open": open_price,
                                "close": close_price,
                                "volume": _finite_number(record.get("volume")),
                                "turnover": _finite_number(record.get("turnover")),
                            }
                        )
            rows.append(row)
            if index % 20 == 0 or index == len(codes):
                print(f"queried {index}/{len(codes)} codes", flush=True)
            if index != len(codes):
                time.sleep(0.55)
    finally:
        quote_ctx.close()

    payload = {
        "schema_version": 1,
        "record_type": "moomoo_rth_daily_query_results",
        "experiment_id": EXPERIMENT_ID,
        "provider": recipe["provider"],
        "sdk_version": recipe["sdk_version"],
        "opend_endpoint": recipe["opend_endpoint"],
        "bar_date": bar_date,
        "adjustment": recipe["adjustment"],
        "session": recipe["session"],
        "queried_at": queried_at,
        "completed_at": _now(),
        "query_count": len(codes),
        "rows": rows,
    }
    payload["result_identity"] = _stable_hash(payload["rows"])
    return payload


def _evaluate(
    raw: dict[str, Any], candidate_codes: list[str], recipe: dict[str, Any]
) -> dict[str, Any]:
    row_by_code = {row["code"]: row for row in raw["rows"]}
    cost = float(recipe["round_trip_cost_bps"]) / 10_000.0
    outcomes: list[dict[str, Any]] = []
    for code in candidate_codes:
        source = row_by_code[code]
        item = {"code": code, "status": source["status"]}
        if source["status"] == "usable":
            gross = float(source["close"]) / float(source["open"]) - 1.0
            item.update(
                {
                    "open": source["open"],
                    "close": source["close"],
                    "gross_return": gross,
                    "after_cost_return": gross - cost,
                }
            )
        else:
            item["error"] = source.get("error")
        outcomes.append(item)

    usable = [row for row in outcomes if row["status"] == "usable"]
    net_returns = [float(row["after_cost_return"]) for row in usable]
    benchmark_returns: dict[str, float | None] = {}
    for symbol in ("SPY", "QQQ"):
        row = row_by_code[f"US.{symbol}"]
        benchmark_returns[symbol] = (
            float(row["close"]) / float(row["open"]) - 1.0
            if row["status"] == "usable"
            else None
        )

    mean_return = sum(net_returns) / len(net_returns) if net_returns else None
    median_return = _median(net_returns) if net_returns else None
    positive_share = (
        sum(value > 0.0 for value in net_returns) / len(net_returns)
        if net_returns
        else None
    )
    mean_excess_spy = (
        mean_return - benchmark_returns["SPY"]
        if mean_return is not None and benchmark_returns["SPY"] is not None
        else None
    )
    mean_excess_qqq = (
        mean_return - benchmark_returns["QQQ"]
        if mean_return is not None and benchmark_returns["QQQ"] is not None
        else None
    )
    checks = {
        "usable_security_count_gte_60": len(usable) >= 60,
        "mean_after_cost_return_positive": mean_return is not None
        and mean_return > 0.0,
        "median_after_cost_return_positive": median_return is not None
        and median_return > 0.0,
        "positive_name_share_gt_half": positive_share is not None
        and positive_share > 0.5,
        "mean_excess_vs_spy_positive": mean_excess_spy is not None
        and mean_excess_spy > 0.0,
        "mean_excess_vs_qqq_positive": mean_excess_qqq is not None
        and mean_excess_qqq > 0.0,
    }
    accepted = all(checks.values())
    if len(usable) < 60:
        decision = "inconclusive_insufficient_sample"
    elif accepted:
        decision = "positive_replay_lead_not_promoted"
    else:
        decision = "rejected"
    return {
        "candidate_count": len(candidate_codes),
        "usable_security_count": len(usable),
        "missing_or_error_count": len(candidate_codes) - len(usable),
        "round_trip_cost_bps": recipe["round_trip_cost_bps"],
        "mean_after_cost_return": mean_return,
        "median_after_cost_return": median_return,
        "positive_name_share": positive_share,
        "benchmark_open_to_close_returns": benchmark_returns,
        "mean_excess_vs_spy": mean_excess_spy,
        "mean_excess_vs_qqq": mean_excess_qqq,
        "acceptance_checks": checks,
        "accepted": accepted,
        "decision": decision,
        "candidate_outcomes": outcomes,
    }


def main() -> int:
    ticket = _read_json(TICKET)
    pool = _read_json(POOL_FILE)
    recipe = _read_json(RECIPE_FILE)
    frozen_identities = _verify_frozen_inputs(ticket, pool, recipe)
    candidate_codes = [f"US.{row['symbol']}" for row in pool["candidates"]]
    expected_codes = set(candidate_codes) | {"US.SPY", "US.QQQ"}
    if set(recipe["codes"]) != expected_codes:
        raise RuntimeError("frozen recipe code set does not match candidate pool")

    raw = _fetch_bars(list(recipe["codes"]), recipe)
    _write_json(RAW_FILE, raw)
    evaluation = _evaluate(raw, candidate_codes, recipe)
    status = "observed_only" if evaluation["accepted"] else "rejected"
    completed_at = _now()
    payload = {
        "schema_version": 1,
        "record_type": "v2_private_replay_scout_result",
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": status,
        "decision": evaluation["decision"],
        "hypothesis": ticket["hypothesis"],
        "acceptance_rule": ticket["acceptance_rule"],
        "changed_variable": ticket["changed_variable"],
        "single_causal_variable": ticket["single_causal_variable"],
        "frozen_at": pool["frozen_at"],
        "completed_at": completed_at,
        "frozen_input_identities": frozen_identities,
        "raw_query_artifact": _repo_rel(RAW_FILE),
        "raw_query_artifact_sha256": _sha256(RAW_FILE),
        "raw_result_identity": raw["result_identity"],
        "evaluation": evaluation,
        "alpha_promotion": {
            "admission_class": "research_replay",
            "candidate_id": ticket["alpha_promotion"]["candidate_id"],
            "selection_scope_id": ticket["alpha_promotion"]["selection_scope_id"],
            "promotion_hash": ticket["alpha_promotion"]["promotion_hash"],
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
        },
        "production_impact": {
            "research_only": True,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_levels_changed": False,
            "shared_policy_changed": False,
            "trade_enabled": False,
        },
        "relaxed_scout_scope": {
            "user_directed": True,
            "relaxed_dimensions": [
                "single cross-section allowed",
                "weak fixed zero-excess prior allowed",
                "Engine 0 and market-wide coverage not required",
            ],
            "not_relaxed": [
                "outcome-blind freeze",
                "complete source disposition",
                "hash-bound inputs",
                "default-off trading",
            ],
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The complete exact-8-K frame mixes event signs; the frozen basket "
                "tests whether aggregate underreaction survives that heterogeneity."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep costs, holding minutes, subsets, item codes, or "
                "event-sign labels on the same 2026-08-20 frame after seeing this result."
            ),
            "new_evidence_required": (
                "A retry requires a separately frozen later complete SEC frame or an "
                "independent pre-outcome event-sign source, not threshold tuning."
            ),
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\experiments\\exp_20260822_001_sec_8k_event_drift_h1.py",
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260822_001_sec_8k_event_drift_h1.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    _write_json(ARTIFACT, payload)
    artifact_sha = _sha256(ARTIFACT)
    summary = {
        key: value
        for key, value in evaluation.items()
        if key not in {"candidate_outcomes"}
    }
    result = {
        "decision": evaluation["decision"],
        "artifact": _repo_rel(ARTIFACT),
        "artifact_sha256": artifact_sha,
        "summary": summary,
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
    }
    log_payload = {
        **payload,
        "artifact": _repo_rel(ARTIFACT),
        "artifact_sha256": artifact_sha,
        "evaluation": summary,
    }
    save_experiment_log_entry(
        log_payload, allow_duplicate=True, expected_experiment_id=EXPERIMENT_ID
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=ticket["prediction"],
        result=result,
        status=status,
        fields={
            "decision": evaluation["decision"],
            "artifact": _repo_rel(ARTIFACT),
            "card_file": _repo_rel(CARD),
            "revision_manifest_file": _repo_rel(MANIFEST),
            "production_impact": payload["production_impact"],
        },
    )
    _write_json(
        MANIFEST,
        {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": evaluation["decision"],
            "runner": RUNNER_REL,
            "runner_sha256": _sha256(ROOT / RUNNER_REL),
            "artifact": _repo_rel(ARTIFACT),
            "artifact_sha256": artifact_sha,
            "raw_query_artifact": _repo_rel(RAW_FILE),
            "raw_query_artifact_sha256": _sha256(RAW_FILE),
            "frozen_input_identities": frozen_identities,
            "completed_at": completed_at,
        },
    )
    CARD.write_text(
        f"# {EXPERIMENT_ID} SEC 8-K H1 Drift Scout\n\n"
        f"Status: `{status}`  \nDecision: `{evaluation['decision']}`\n\n"
        f"Usable names: `{evaluation['usable_security_count']}` / "
        f"`{evaluation['candidate_count']}`. Mean net return: "
        f"`{evaluation['mean_after_cost_return']:.6%}`; median: "
        f"`{evaluation['median_after_cost_return']:.6%}`; positive share: "
        f"`{evaluation['positive_name_share']:.2%}`. Mean excess vs SPY: "
        f"`{evaluation['mean_excess_vs_spy']:.6%}`; vs QQQ: "
        f"`{evaluation['mean_excess_vs_qqq']:.6%}`.\n\n"
        "Observed-only research replay. No policy, ranking, sizing, exit, order, "
        "paper, or live behavior changed; `trade_enabled=false`.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": status,
                "decision": evaluation["decision"],
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
