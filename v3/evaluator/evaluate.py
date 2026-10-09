"""V3 evaluator entry point: lock check, dev runs, budgeted submissions, reachability.

  python v3/evaluator/evaluate.py verify
  python v3/evaluator/evaluate.py dev v3/strategies/<name>.py [--layer trading|evidence]
  python v3/evaluator/evaluate.py submit v3/strategies/<name>.py
  python v3/evaluator/evaluate.py reachability
  python v3/evaluator/evaluate.py lock          (only when no lock exists; changes need the user)

Strategy module contract (architecture doc sections 2 and 4):
  CLASS = "A" | "B";  FAMILY = "<family name>";  FREQ = "M" (rebalance frequency)
  SIGNALS = {"trading": fn, "evidence": fn}   at least one layer; fn(hist) -> {asset: weight}
  at most 200 lines.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
REPO = V3.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(V3 / "portfolio"))

import baselines  # noqa: E402
import data  # noqa: E402
import engine  # noqa: E402
import metrics  # noqa: E402
from combine import portfolio_signal  # noqa: E402

LOCK = V3 / "evaluator.lock"
LEDGER = V3 / "ledger"
TRIALS = LEDGER / "trials.jsonl"
DEV_RUNS = LEDGER / "dev_runs.jsonl"

DEV_END = "2016-12-31"
VALID_START = "2017-01-01"
FREEZE_END = "2026-06-30"
WARMUP_MONTHS = 13
B_BUDGET_PER_QUARTER = 12
MAX_STRATEGY_LINES = 200

GATE_CONF = 0.95
GATE_SHARPE = 0.3
GATE_MAX_DD = 0.25
# 2026-10-08 (user-approved): the comparator gate changed from "beat S0 and S1 alone at matched
# volatility" to "adding the candidate to an S1 core raises Sharpe".  Applies to submissions made
# with this rule version; the five A-class records made under rule v1 are not re-judged.
GATE_RULE_VERSION = 2
LAYER_SETTINGS = {
    "trading": {"cost_kind": "etf", "exec_lag": 1},
    "evidence": {"cost_kind": "evidence", "exec_lag": 0},
}


# ---------------------------------------------------------------- lock

def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def current_fingerprint() -> dict:
    files = sorted(list(HERE.glob("*.py")) + list((V3 / "portfolio").glob("*.py")))
    m = data.manifest()
    frozen = {k: v["freeze_sha256"] for k, v in m["files"].items() if "freeze_sha256" in v}
    return {"code": {f.relative_to(V3).as_posix(): file_sha(f) for f in files}, "data_freeze": frozen}


def make_lock() -> dict:
    if LOCK.exists():
        raise SystemExit("evaluator.lock exists; replacing it is a user decision (commit message must carry "
                         "'evaluator-change-approved-by-user').  Delete it by hand first if the user approved.")
    m = data.manifest()
    fp = current_fingerprint()
    fp["french"] = {k: {"path": v["versions"][-1]["path"], "sha256": v["versions"][-1]["sha256"]}
                    for k, v in m["files"].items() if k.startswith("french/")}
    fp["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    LOCK.write_text(json.dumps(fp, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return fp


def verify_lock() -> dict:
    if not LOCK.exists():
        raise SystemExit("evaluator.lock missing; refusing to evaluate")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    fp = current_fingerprint()
    problems = [f"code {k}" for k in set(lock["code"]) | set(fp["code"]) if lock["code"].get(k) != fp["code"].get(k)]
    problems += [f"data {k}" for k, v in lock["data_freeze"].items() if fp["data_freeze"].get(k) != v]
    for k, v in lock["french"].items():
        p = data.DATA / v["path"]
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        if hashlib.sha256(text.encode()).hexdigest() != v["sha256"]:
            problems.append(f"data {k} pinned version")
    if problems:
        raise SystemExit("evaluator.lock mismatch, refusing to run: " + ", ".join(sorted(problems)))
    return lock


# ---------------------------------------------------------------- panels and runs

def panels(lock: dict) -> dict:
    tr, cash = data.etf_panel()
    ev, rf = data.evidence_panel({k: v["path"] for k, v in lock["french"].items()})
    return {"trading": (tr, cash), "evidence": (ev, rf)}


def first_start(returns: pd.DataFrame) -> pd.Timestamp:
    return returns.dropna(how="all").index[0] + pd.DateOffset(months=WARMUP_MONTHS)


def run_layer(signal, layer: str, panel, start, end, freq: str, cost_mult: float = 1.0):
    returns, cash = panel
    returns, cash = returns.loc[:end], cash.loc[:end]
    return engine.run(signal, returns, cash, start=start, end=end, freq=freq, cost_mult=cost_mult,
                      **LAYER_SETTINGS[layer])


def load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location(f"v3_strategy_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("CLASS", "FAMILY", "FREQ", "SIGNALS"):
        if not hasattr(mod, attr):
            raise SystemExit(f"{path}: missing {attr}")
    if mod.CLASS not in ("A", "B") or not set(mod.SIGNALS) <= set(LAYER_SETTINGS) or not mod.SIGNALS:
        raise SystemExit(f"{path}: CLASS must be A/B and SIGNALS keys trading/evidence")
    lines = path.read_text(encoding="utf-8").count("\n") + 1
    if lines > MAX_STRATEGY_LINES:
        raise SystemExit(f"{path}: {lines} lines > {MAX_STRATEGY_LINES}")
    return mod


def append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def describe(res, cash, base_runs=None) -> dict:
    out = metrics.summary(res.net, cash)
    out["avg_annual_turnover"] = float(res.turnover.sum() / out["years"])
    out["cost_drag_ann"] = float(res.cost.sum() / out["years"])
    for name, b in (base_runs or {}).items():
        out[f"vs_{name}"] = metrics.vol_matched(res.net, b.net, cash)
        out[f"{name}_sharpe"] = metrics.sharpe(b.net, cash)
    return out


# ---------------------------------------------------------------- commands

def cmd_dev(path: Path, layer: str | None) -> dict:
    lock = verify_lock()
    mod = load_strategy(path)
    pn = panels(lock)
    report = {}
    for lay, sig in mod.SIGNALS.items():
        if layer and lay != layer:
            continue
        returns, cash = pn[lay]
        returns, cash = returns.loc[:DEV_END], cash.loc[:DEV_END]  # dev never sees later data
        start = first_start(returns)
        res = run_layer(sig, lay, (returns, cash), start, DEV_END, mod.FREQ)
        bases = {}
        if lay == "trading":
            bases = {n: run_layer(f, lay, (returns, cash), start, DEV_END, "M")
                     for n, f in (("S0", baselines.s0_spy), ("S1", baselines.s1_spy_200dma))}
        report[lay] = describe(res, cash, bases)
    append(DEV_RUNS, {"at_utc": datetime.now(timezone.utc).isoformat(), "strategy": path.as_posix(),
                      "config_hash": file_sha(path), "layers": sorted(report)})
    return report


def git_dirty(paths: list[Path]) -> str:
    out = subprocess.run(["git", "status", "--porcelain", "--", *[str(p) for p in paths]],
                         cwd=REPO, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def quarter(ts: str) -> str:
    t = pd.Timestamp(ts)
    return f"{t.year}Q{t.quarter}"


def cmd_submit(path: Path) -> dict:
    lock = verify_lock()
    dirty = git_dirty([path, HERE, V3 / "portfolio", LOCK])
    if dirty:
        raise SystemExit("commit the strategy and leave evaluator/portfolio clean before submitting:\n" + dirty)
    mod = load_strategy(path)
    cfg = file_sha(path)
    trials = read_jsonl(TRIALS)
    if any(t["config_hash"] == cfg for t in trials):
        raise SystemExit("this exact strategy file was already submitted; resubmission is not allowed")
    now = datetime.now(timezone.utc).isoformat()
    weight = 1
    if mod.CLASS == "B":
        accepted_a = [t for t in trials if t["class"] == "A" and t["passed"]]
        if not accepted_a:
            raise SystemExit("B-class submissions open only after an A-class portfolio exists (doc section 4)")
        if any(t["family"] == mod.FAMILY and t["class"] == "B" and not t["passed"] for t in trials):
            weight = 2
        used = sum(t["count"] for t in trials if t["class"] == "B" and quarter(t["at_utc"]) == quarter(now))
        if used + weight > B_BUDGET_PER_QUARTER:
            raise SystemExit(f"B budget for {quarter(now)} exhausted ({used}/{B_BUDGET_PER_QUARTER})")
        n_trials = sum(t["count"] for t in trials if t["class"] == "B") + weight
    else:
        n_trials = sum(1 for t in trials if t["class"] == "A") + 1

    pn = panels(lock)
    layers = {}
    for lay, sig in mod.SIGNALS.items():
        returns, cash = pn[lay]
        start = VALID_START if mod.CLASS == "B" else first_start(returns)
        res = run_layer(sig, lay, pn[lay], start, FREEZE_END, mod.FREQ)
        res2 = run_layer(sig, lay, pn[lay], start, FREEZE_END, mod.FREQ, cost_mult=2.0)
        ex = res.net - cash.reindex(res.net.index).fillna(0.0)
        info = describe(res, cash)
        info["sharpe_2x_cost"] = metrics.sharpe(res2.net, cash)
        info["dsr"] = metrics.dsr(ex, n_trials)
        layers[lay] = (info, res, start)

    longest = max(layers, key=lambda k: layers[k][0]["years"])
    gates = {"significance": layers[longest][0]["dsr"] >= GATE_CONF}
    if "trading" in layers:
        info, res, start = layers["trading"]
        returns, cash = pn["trading"]
        bases = {n: run_layer(f, "trading", pn["trading"], start, FREEZE_END, "M")
                 for n, f in (("S0", baselines.s0_spy), ("S1", baselines.s1_spy_200dma))}
        for n, b in bases.items():
            info[f"vs_{n}"] = metrics.vol_matched(res.net, b.net, cash)
            info[f"{n}_sharpe"] = metrics.sharpe(b.net, cash)
        gates["trading_sharpe"] = info["sharpe"] >= GATE_SHARPE and info["sharpe_2x_cost"] > 0
        core = bases["S1"].net
        info["s1_core_sharpe"] = metrics.sharpe(core, cash)
        info["s1_core_plus_candidate_sharpe"] = metrics.sharpe(metrics.core_satellite(core, res.net), cash)
        gates["improves_s1_core"] = info["s1_core_plus_candidate_sharpe"] > info["s1_core_sharpe"]
        gates["max_drawdown"] = info["max_drawdown"] >= -GATE_MAX_DD
        members = [load_strategy(REPO / t["strategy"]).SIGNALS["trading"]
                   for t in trials if t["passed"] and "trading" in t["layers"]]
        for t in trials:
            if t["passed"] and file_sha(REPO / t["strategy"]) != t["config_hash"]:
                raise SystemExit(f"portfolio member {t['strategy']} changed after acceptance")
        with_c = run_layer(portfolio_signal(members + [mod.SIGNALS["trading"]]), "trading", pn["trading"], start, FREEZE_END, "M")
        sh_with = metrics.sharpe(with_c.net, cash)
        sh_without = metrics.sharpe(run_layer(portfolio_signal(members), "trading", pn["trading"], start,
                                              FREEZE_END, "M").net, cash) if members else 0.0
        info["portfolio_sharpe_with"], info["portfolio_sharpe_without"] = sh_with, sh_without
        gates["portfolio_increment"] = sh_with > sh_without
    else:
        gates["trading_layer_present"] = False  # every candidate must be tradable to be deployed
    record = {
        "at_utc": now, "strategy": path.relative_to(REPO).as_posix(), "config_hash": cfg,
        "class": mod.CLASS, "family": mod.FAMILY, "count": weight, "n_trials": n_trials,
        "layers": {k: v[0] for k, v in layers.items()}, "significance_layer": longest,
        "gates": gates, "passed": all(gates.values()), "gate_rule_version": GATE_RULE_VERSION,
    }
    append(TRIALS, record)
    return record


def cmd_reachability() -> str:
    rows = [
        ("证据层全历史（月频 1927-2026）", 99.0, 12),
        ("交易层全历史（日频，SPY 1994-2026）", 32.0, 252),
        ("交易层全历史（日频，多数 ETF 2003-2026）", 23.0, 252),
        ("Validation（日频 2017-2026-06）", 9.5, 252),
    ]
    table = metrics.reachability_table(rows)
    text = ("# 门槛可达性表（自动生成）\n\nDSR ≥ 0.95 需要的年化 Sharpe（正态收益，试验离散度取零假设 1/√T）。\n"
            "A 类候选文献里的典型 Sharpe 约 0.3–0.8。\n\n" + table + "\n")
    (LEDGER / "reachability.md").parent.mkdir(parents=True, exist_ok=True)
    (LEDGER / "reachability.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    sub.add_parser("lock")
    sub.add_parser("reachability")
    d = sub.add_parser("dev")
    d.add_argument("strategy", type=Path)
    d.add_argument("--layer", choices=sorted(LAYER_SETTINGS))
    s = sub.add_parser("submit")
    s.add_argument("strategy", type=Path)
    a = ap.parse_args()
    if a.cmd == "verify":
        verify_lock()
        print("evaluator.lock ok")
    elif a.cmd == "lock":
        make_lock()
        print("evaluator.lock written")
    elif a.cmd == "reachability":
        print(cmd_reachability())
    elif a.cmd == "dev":
        print(json.dumps(cmd_dev(a.strategy.resolve(), a.layer), indent=1, default=str))
    elif a.cmd == "submit":
        print(json.dumps(cmd_submit(a.strategy.resolve()), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
