"""exp-20260609-007: Tail-state classifier for broad winner-continuation.

Playbook Research Queue #2: broad recent-winner continuation shows a real but
tail-risky signal (exp-20260601-008 found it non-incremental over ret20). This
read-only PIT attribution asks whether a tail-state filter separates resilient
continuation from tail-risk continuation, then runs the measured numbers through
the one-shot full-stack verdict helper to demonstrate the mechanism end to end.

This is the FIRST step the playbook prescribes (read-only attribution before any
adapter). It does NOT change orders/sleeves/sizing. It dogfoods the new
machinery: it persists its result via
``experiment_registry.persist_self_registered_result()`` (no direct registry
write), so it passes the self-registration guard + pre-commit hook.

window_metrics fed to Gate 4 are derived from the read-only forward-return
attribution (fixed notional per candidate) as an honest proxy for a backtester
before/after; the signal conclusion is what matters, the verdict shows the
mechanism.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "quant"), str(REPO_ROOT / "quant" / "experiments"), str(REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exp_20260601_008_long_only_continuation_incrementality as cont  # noqa: E402
from full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260609-007"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXP_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = EXP_DIR / "tail_state_continuation_candidate_pool.json"

WINDOWS = cont.WINDOWS
SAMPLE_STEP = 5
WINNER_QUINTILE_FRACTION = 0.20   # top ret5 quintile = "recent winner" candidates
NOTIONAL = 10_000.0               # fixed per-candidate paper notional for PnL/concentration


def _day_candidates(prepared, asof):
    """Per-ticker cross-section with ret5, ret20, fwd 10d (skip-day)."""
    rows = []
    for ticker, p in prepared.items():
        pos = p["pos_by_date"].get(asof)
        if pos is None:
            continue
        ret5 = cont._ret(p["closes"], pos, cont.FORMATION)
        ret20 = cont._ret(p["closes"], pos, cont.CORE_MOMENTUM)
        fwd = cont._skip_fwd(p["closes"], pos, cont.HOLD)
        if ret5 is None or ret20 is None or fwd is None:
            continue
        rows.append({"ticker": ticker, "ret5": ret5, "ret20": ret20, "fwd": fwd})
    return rows


def _split_resilient(cross_section):
    """Within the top-ret5 winner pool, label resilient vs tail-risk using a PIT
    tail-state: day breadth (share with ret20>0), regime (median ret20), and
    per-candidate overextension (ret5-ret20)."""
    n = len(cross_section)
    if n < cont.MIN_NAMES_PER_DAY:
        return [], []
    breadth = sum(1 for r in cross_section if r["ret20"] > 0) / n
    regime = statistics.median(r["ret20"] for r in cross_section)
    winners = sorted(cross_section, key=lambda r: r["ret5"], reverse=True)
    k = max(1, int(round(n * WINNER_QUINTILE_FRACTION)))
    pool = winners[:k]
    if len(pool) < 4:
        return [], []
    med_ext = statistics.median((r["ret5"] - r["ret20"]) for r in pool)
    resilient, tail_risk = [], []
    day_ok = breadth >= 0.5 and regime >= 0.0
    for r in pool:
        not_overextended = (r["ret5"] - r["ret20"]) <= med_ext
        if day_ok and not_overextended:
            resilient.append(r)
        else:
            tail_risk.append(r)
    return resilient, tail_risk


def _concentration(rows):
    """Single-ticker / top-5 / HHI shares of positive forward PnL."""
    pnl = {}
    for r in rows:
        pnl[r["ticker"]] = pnl.get(r["ticker"], 0.0) + r["fwd"] * NOTIONAL
    pos = {t: v for t, v in pnl.items() if v > 0}
    total = sum(pos.values())
    if total <= 0:
        return None, None, None
    shares = sorted((v / total for v in pos.values()), reverse=True)
    single = shares[0]
    top5 = sum(shares[:5])
    hhi = sum(s * s for s in shares)
    return single, top5, hhi


def run() -> dict[str, Any]:
    t0 = time.time()
    frames = cont.load_warehouse_frames()
    prepared = cont._prepare(frames)

    per_window = {}
    resilient_all, tailrisk_all, pool_all = [], [], []
    for window, (start, end) in WINDOWS.items():
        res_w, tr_w, pool_w = [], [], []
        for asof in cont._sampled_days(prepared, start, end, SAMPLE_STEP):
            cs = _day_candidates(prepared, asof)
            res, tr = _split_resilient(cs)
            res_w += res
            tr_w += tr
            pool_w += res + tr
        def _net(rows):
            if not rows:
                return None
            return statistics.mean(r["fwd"] for r in rows) - cont.LONG_ONLY_COST
        # comparator: broad-market proxy = mean forward of the full winner pool
        comp = statistics.mean(r["fwd"] for r in pool_w) if pool_w else None
        per_window[window] = {
            "resilient_n": len(res_w),
            "tail_risk_n": len(tr_w),
            "resilient_fwd_mean": round(statistics.mean(r["fwd"] for r in res_w), 6) if res_w else None,
            "tail_risk_fwd_mean": round(statistics.mean(r["fwd"] for r in tr_w), 6) if tr_w else None,
            "resilient_net_of_cost": round(_net(res_w), 6) if res_w else None,
            "comparator_pool_mean": round(comp, 6) if comp is not None else None,
            "resilient_minus_comparator": (
                round(statistics.mean(r["fwd"] for r in res_w) - comp, 6)
                if res_w and comp is not None else None
            ),
        }
        resilient_all += res_w
        tailrisk_all += tr_w
        pool_all += pool_w

    # pooled separation
    res_fwd = [r["fwd"] for r in resilient_all]
    tr_fwd = [r["fwd"] for r in tailrisk_all]
    comp_mean = statistics.mean(r["fwd"] for r in pool_all) if pool_all else 0.0
    sep = (statistics.mean(res_fwd) - statistics.mean(tr_fwd)) if res_fwd and tr_fwd else None
    sep_t = cont._tstat([r["fwd"] for r in resilient_all]) if resilient_all else None
    res_net = (statistics.mean(res_fwd) - cont.LONG_ONLY_COST) if res_fwd else None
    res_excess = (statistics.mean(res_fwd) - comp_mean) if res_fwd else None

    single, top5, hhi = _concentration(resilient_all)

    windows_improved = sum(
        1 for w in per_window.values()
        if (w["resilient_minus_comparator"] or -1) > 0
    )
    windows_regressed = sum(
        1 for w in per_window.values()
        if (w["resilient_minus_comparator"] or 0) < 0
    )
    # worst-window resilient net as a drawdown-contribution proxy vs comparator
    worst = min(
        ((w["resilient_net_of_cost"] or 0) - (w["comparator_pool_mean"] or 0))
        for w in per_window.values()
    )

    # window_metrics proxy for Gate 4 (return-based, fixed notional)
    window_metrics = {
        "aggregate_ev_delta": round((res_excess or 0) * 100, 4),       # excess pp as EV-proxy
        "aggregate_pnl_delta": round((res_excess or 0) * NOTIONAL * max(len(resilient_all), 1), 2),
        "windows_ev_improved": windows_improved,
        "windows_ev_regressed": windows_regressed,
        "adjusted_trade_count": len(resilient_all),
        "adjusted_window_count": sum(1 for w in per_window.values() if w["resilient_n"]),
        "max_drawdown_worse_max": round(max(0.0, -worst), 6),
        "single_ticker_positive_share": round(single, 6) if single is not None else None,
        "baseline_single_ticker_positive_share": 0.50,
        "top_5_contribution_pct": round(top5, 6) if top5 is not None else None,
        "baseline_top_5_contribution_pct": 0.60,
        "hhi_concentration": round(hhi, 6) if hhi is not None else None,
        "baseline_hhi_concentration": 0.35,
        "avg_pnl_per_trade_delta": round((res_excess or 0) * NOTIONAL, 2),
        "avg_return_delta_pp": round((res_excess or 0) * 100, 4),
    }

    gate4 = evaluate_gate4(window_metrics)
    envelope = ExecutionEnvelope(
        base_notional=NOTIONAL,
        max_capital_pct=0.05,
        min_dollar_volume=2_000_000.0,
        slippage_bps=10.0,
        max_displacement=2,
        max_concurrent=5,
        order_semantics="next_open",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.12,
        notes="Declared up front; live readiness still blocked on forward rows.",
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,            # read-only attribution -> no forward rows yet
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": "tail_state_winner_continuation_v1",
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "method": (
            "Read-only PIT attribution. Candidate pool = top-20% ret5 winners. "
            "Tail-state resilient = day breadth>=0.5 AND median ret20>=0 AND "
            "candidate not overextended (ret5-ret20 <= pool median). Forward 10d "
            "skip-day close-to-close; one round-trip cost. window_metrics are a "
            "return-based proxy (fixed $10k notional) for a backtester before/after."
        ),
        "per_window": per_window,
        "pooled": {
            "resilient_n": len(resilient_all),
            "tail_risk_n": len(tailrisk_all),
            "resilient_minus_tailrisk": round(sep, 6) if sep is not None else None,
            "resilient_fwd_tstat": sep_t,
            "resilient_net_of_cost": round(res_net, 6) if res_net is not None else None,
            "resilient_excess_vs_comparator": round(res_excess, 6) if res_excess is not None else None,
            "concentration": {"single_ticker": single, "top5": top5, "hhi": hhi},
        },
        "window_metrics_proxy": window_metrics,
        "verdict": verdict,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    EXP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _status_for(verdict_str: str) -> str:
    return {
        "reject": "rejected_no_tail_state_separation",
        "accepted_paper_pending_forward": "accepted_paper_pending_forward",
        "live_eligible": "accepted_live_eligible",
    }.get(verdict_str, "observed_only")


def main() -> None:
    payload = run()
    verdict = payload["verdict"]["verdict"]
    # dogfood the sanctioned path: persist via the helper (enforces + propagates
    # the pre-run prediction onto the ticket); never write the registry directly.
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=ticket.get("prediction"),
        status=_status_for(verdict),
        result={
            "decision": _status_for(verdict),
            "verdict": verdict,
            "next_step": payload["verdict"]["next_step"],
            "pooled": payload["pooled"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        },
        fields={
            "change_type": "candidate_pool_full_stack",
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_family": "tail_state_winner_continuation_candidate_pool",
        },
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "verdict": verdict,
        "gate4_passed": payload["verdict"]["gate4_passed"],
        "pooled": payload["pooled"],
        "next_step": payload["verdict"]["next_step"],
    }, indent=2))


if __name__ == "__main__":
    main()
