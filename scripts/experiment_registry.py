"""Small registry helpers for coordinating multi-agent experiments."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
DEFAULT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
ACTIVE_STATUSES = {"claimed", "running"}
FINAL_STATUSES = {"accepted", "rejected", "observed_only"}
SHARED_COORDINATION_SCOPES = {
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
}
VALID_LANES = {
    "alpha_discovery",
    "loss_attribution",
    "universe_scout",
    "measurement_repair",
}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_relative(path):
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix()


def load_registry(path=DEFAULT_REGISTRY):
    path = Path(path)
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "experiments": []}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", None)
    data.setdefault("experiments", [])
    return data


def save_registry(registry, path=DEFAULT_REGISTRY):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = utc_now_iso()
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")


def latest_backtest_result(data_dir=None):
    data_dir = Path(data_dir or (REPO_ROOT / "data"))
    files = sorted(data_dir.glob("backtest_results_*.json"))
    if not files:
        return None
    return _repo_relative(files[-1])


def next_experiment_id(registry, today=None):
    today = today or datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"exp-{today}-"
    max_seen = 0
    for exp in registry.get("experiments", []):
        eid = exp.get("experiment_id", "")
        if eid.startswith(prefix):
            try:
                max_seen = max(max_seen, int(eid.rsplit("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}{max_seen + 1:03d}"


def parse_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_windows(values):
    windows = []
    for raw in values or []:
        if ":" not in raw:
            raise ValueError(f"window must be START:END, got {raw!r}")
        start, end = raw.split(":", 1)
        windows.append({"start": start, "end": end})
    return windows


def get_experiment(registry, experiment_id):
    for exp in registry.get("experiments", []):
        if exp.get("experiment_id") == experiment_id:
            return exp
    return None


def create_ticket(
    registry,
    *,
    lane,
    hypothesis,
    change_type,
    single_causal_variable,
    baseline_result_file=None,
    allowed_write_scope=None,
    must_not_touch=None,
    locked_variables=None,
    evaluation_windows=None,
    acceptance_rule=None,
    owner=None,
):
    if lane not in VALID_LANES:
        raise ValueError(f"lane must be one of {sorted(VALID_LANES)}")
    baseline = baseline_result_file or latest_backtest_result()
    ticket = {
        "experiment_id": next_experiment_id(registry),
        "status": "proposed",
        "lane": lane,
        "owner": owner,
        "hypothesis": hypothesis,
        "change_type": change_type,
        "single_causal_variable": single_causal_variable,
        "baseline_result_file": baseline,
        "allowed_write_scope": allowed_write_scope or [],
        "must_not_touch": must_not_touch or [],
        "locked_variables": locked_variables or (
            [single_causal_variable] if single_causal_variable else []
        ),
        "evaluation_windows": evaluation_windows or [],
        "acceptance_rule": acceptance_rule or "Use AGENTS.md Gate 4.",
        "created_at": utc_now_iso(),
        "claimed_at": None,
        "completed_at": None,
        "result": None,
    }
    registry.setdefault("experiments", []).append(ticket)
    return ticket


def _path_overlaps(left, right):
    a = _normalize_scope(left)
    b = _normalize_scope(right)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _normalize_scope(scope):
    return _repo_relative(scope).replace("\\", "/").rstrip("/").lower()


def _is_shared_coordination_scope(scope):
    return _normalize_scope(scope) in SHARED_COORDINATION_SCOPES


def _conflict_scopes(scopes):
    return [scope for scope in (scopes or []) if not _is_shared_coordination_scope(scope)]


def find_conflicts(registry, experiment):
    conflicts = []
    scopes = _conflict_scopes(experiment.get("allowed_write_scope") or [])
    locked = set(experiment.get("locked_variables") or [])
    for other in registry.get("experiments", []):
        if other is experiment:
            continue
        if other.get("status") not in ACTIVE_STATUSES:
            continue
        other_scopes = _conflict_scopes(other.get("allowed_write_scope") or [])
        scope_hits = [
            [s, o]
            for s in scopes
            for o in other_scopes
            if _path_overlaps(s, o)
        ]
        locked_hits = sorted(locked.intersection(other.get("locked_variables") or []))
        if scope_hits or locked_hits:
            conflicts.append({
                "experiment_id": other.get("experiment_id"),
                "owner": other.get("owner"),
                "status": other.get("status"),
                "scope_conflicts": scope_hits,
                "locked_variable_conflicts": locked_hits,
            })
    return conflicts


def claim_ticket(registry, experiment_id, owner, force=False):
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    conflicts = find_conflicts(registry, exp)
    if conflicts and not force:
        return exp, conflicts
    exp["owner"] = owner
    exp["status"] = "claimed"
    exp["claimed_at"] = utc_now_iso()
    return exp, []


def metric_snapshot(result):
    benchmarks = result.get("benchmarks") or {}
    total_return = benchmarks.get("strategy_total_return_pct")
    sharpe_daily = result.get("sharpe_daily")
    ev = result.get("expected_value_score")
    if ev is None and total_return is not None and sharpe_daily is not None:
        ev = round(total_return * sharpe_daily, 4)
    return {
        "expected_value_score": ev,
        "sharpe": result.get("sharpe"),
        "sharpe_daily": sharpe_daily,
        "total_return_pct": total_return,
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "total_pnl": result.get("total_pnl"),
    }


def _delta(after, before, key):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(a - b, 6)


def evaluate_gate(before_metrics, after_metrics):
    reasons = []
    before_ev = before_metrics.get("expected_value_score")
    after_ev = after_metrics.get("expected_value_score")
    if before_ev not in (None, 0) and after_ev is not None:
        ev_pct = (after_ev - before_ev) / abs(before_ev)
        if ev_pct > 0.10:
            reasons.append(f"expected_value_score improved {ev_pct:.2%}")

    sharpe_delta = _delta(after_metrics, before_metrics, "sharpe")
    if sharpe_delta is not None and sharpe_delta > 0.1:
        reasons.append(f"sharpe improved {sharpe_delta:.4f}")

    dd_delta = _delta(after_metrics, before_metrics, "max_drawdown_pct")
    if dd_delta is not None and dd_delta < -0.01:
        reasons.append(f"max_drawdown_pct fell {-dd_delta:.4f}")

    before_pnl = before_metrics.get("total_pnl")
    after_pnl = after_metrics.get("total_pnl")
    if before_pnl not in (None, 0) and after_pnl is not None:
        pnl_pct = (after_pnl - before_pnl) / abs(before_pnl)
        if pnl_pct > 0.05:
            reasons.append(f"total_pnl improved {pnl_pct:.2%}")

    trade_delta = _delta(after_metrics, before_metrics, "trade_count")
    win_delta = _delta(after_metrics, before_metrics, "win_rate")
    if trade_delta is not None and win_delta is not None:
        if trade_delta > 0 and win_delta >= 0:
            reasons.append("trade_count increased while win_rate did not decline")

    return {
        "decision": "accepted" if reasons else "rejected",
        "acceptance_reasons": reasons,
    }


def judge_results(before_path, after_path):
    with Path(before_path).open(encoding="utf-8") as f:
        before_raw = json.load(f)
    with Path(after_path).open(encoding="utf-8") as f:
        after_raw = json.load(f)
    before = metric_snapshot(before_raw)
    after = metric_snapshot(after_raw)
    delta = {
        key: _delta(after, before, key)
        for key in before
        if isinstance(before.get(key), (int, float)) or isinstance(after.get(key), (int, float))
    }
    gate = evaluate_gate(before, after)
    return {
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        **gate,
    }


def final_decision(judgement, status_override=None):
    if status_override is None:
        return judgement["decision"]
    if status_override not in FINAL_STATUSES:
        raise ValueError(f"status_override must be one of {sorted(FINAL_STATUSES)}")
    return status_override


def build_log_draft(
    experiment,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
    change_summary=None,
    notes=None,
):
    decision = final_decision(judgement, status_override)
    return {
        "experiment_id": experiment.get("experiment_id"),
        "timestamp": utc_now_iso(),
        "status": decision,
        "hypothesis": experiment.get("hypothesis"),
        "change_summary": change_summary or (
            "Generated by scripts/judge_experiment.py; fill in code changes before appending."
        ),
        "change_type": experiment.get("change_type"),
        "component": ", ".join(experiment.get("allowed_write_scope") or []),
        "parameters": {
            "single_causal_variable": experiment.get("single_causal_variable"),
            "locked_variables": experiment.get("locked_variables") or [],
        },
        "date_range": (experiment.get("evaluation_windows") or [{}])[0],
        "secondary_windows": (experiment.get("evaluation_windows") or [])[1:],
        "market_regime_summary": {},
        "before_metrics": judgement["before_metrics"],
        "after_metrics": judgement["after_metrics"],
        "delta_metrics": judgement["delta_metrics"],
        "llm_metrics": {"used_llm": False},
        "decision": decision,
        "rejection_reason": (
            None if decision in {"accepted", "observed_only"}
            else "No AGENTS.md Gate 4 acceptance condition was met."
        ),
        "next_retry_requires": [],
        "related_files": [_repo_relative(before_path), _repo_relative(after_path)],
        "notes": notes if notes is not None else "; ".join(judgement.get("acceptance_reasons") or []),
    }


def update_result(
    registry,
    experiment_id,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
):
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    decision = final_decision(judgement, status_override)
    exp["status"] = decision
    exp["completed_at"] = utc_now_iso()
    exp["result"] = {
        "decision": decision,
        "acceptance_reasons": judgement.get("acceptance_reasons") or [],
        "before_result_file": _repo_relative(before_path),
        "after_result_file": _repo_relative(after_path),
        "delta_metrics": judgement.get("delta_metrics") or {},
    }
    return exp


def experiment_id_exists_in_log(log_path, experiment_id):
    path = Path(log_path)
    if not path.exists():
        return False
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == experiment_id:
                return True
    return False


def append_log_entry(log_path, row, *, allow_duplicate=False):
    experiment_id = row.get("experiment_id")
    if not experiment_id:
        raise ValueError("log row must include experiment_id")
    if not allow_duplicate and experiment_id_exists_in_log(log_path, experiment_id):
        raise ValueError(f"experiment_id already exists in log: {experiment_id}")

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def add_common_registry_arg(parser):
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to experiment registry JSON.",
    )
