"""Build data/reopen_readiness.json: machine-readable reopen counters for parked lanes.

Experiment: exp-20260721-004 (measurement_repair, alpha-enabling tooling).

Every parked lane in this repo declares a quantitative reopen_condition, but the
counters live scattered across ticket reflections, park notes, and memory files.
Each scheduled session re-derives them by hand (30+ min) and has already misread
one threshold (Q5>=12 experiment acceptance vs the governing Q5>=20 frozen-family
reopen). This builder computes every machine-derivable counter from canonical
ledgers, carries manual lanes with their last hand-verified values, and flags
lanes whose counters have stopped advancing (park deadlock candidates).

Contract:
- read-only over ledgers; the only write is data/reopen_readiness.json;
- per-lane fail-open: a broken ledger schema marks that lane status=error and
  never crashes the whole build;
- thresholds carry a threshold_source citation so the next agent can audit the
  transcription instead of trusting it;
- history: prior snapshots are kept (capped) so days_since_progress can flag
  structurally stalled reopen conditions per the park-expiry concern.

Run:
    .\\.venv\\Scripts\\python.exe -B scripts\\build_reopen_readiness.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "reopen_readiness.json")
SCHEMA_VERSION = 1
HISTORY_CAP = 60


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _latest(pattern):
    files = sorted(glob.glob(os.path.join(REPO_ROOT, pattern)))
    return files[-1] if files else None


def lane_exit_lifecycle_advisory():
    """Parked exit-advisory lane. Reopen: post-2026-06-30 cohort settled>=101,
    hard_stop>=8, advisory (hard_stop+high_urgency) >= 20."""
    path = _latest("data/exit_lifecycle/outcome_ledgers/exit_lifecycle_outcomes_*.jsonl")
    rows = _read_jsonl(path)
    post = [r for r in rows if str(r.get("observed_date", "")).replace("-", "") > "20260630"]
    closed = [r for r in post if r.get("h5_status") == "closed"]
    adv = Counter(r.get("advisory_bucket") for r in closed)
    advisory_total = adv.get("hard_stop", 0) + adv.get("high_urgency", 0)
    pending_adv = [
        r for r in post
        if r.get("h5_status") != "closed"
        and r.get("advisory_bucket") in ("hard_stop", "high_urgency")
    ]
    counters = {
        "settled": len(closed),
        "hard_stop": adv.get("hard_stop", 0),
        "high_urgency": adv.get("high_urgency", 0),
        "advisory_total": advisory_total,
        "pending_advisory_in_pipeline": len(pending_adv),
    }
    thresholds = {"settled": 101, "hard_stop": 8, "advisory_total": 20}
    ready = all(counters[k] >= v for k, v in thresholds.items())
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "park declaration recorded in the 2026-07-19 reopen sweep "
            "(post-06-30 cohort; see project memory residual-cash-funding-closed-2026-07-19)"
        ),
        "counter_source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "note": (
            "Pending advisory rows settle on an h5 horizon; pipeline count above "
            "estimates how soon advisory_total can reach 20."
        ),
    }


def lane_short_volume_q5_soft_tilt():
    """Rejected exp-20260716-007. Governing reopen (exp-20260716-007 reflection):
    >=20 PIT-tagged Q5 closed forward rows AND max single-ticker Q5 share <=40%."""
    path = os.path.join(REPO_ROOT, "data", "paper_sleeves", "forward_replacement_value.jsonl")
    rows = _read_jsonl(path)
    uniq = {r["decision_id"]: r for r in rows}
    settled = [
        r for r in uniq.values()
        if r.get("exit_date") and r.get("replacement_value_vs_cash_usd") is not None
    ]
    tagged = [r for r in settled if r.get("entry_short_volume_status") == "ok"]
    q5 = [r for r in tagged if r.get("entry_short_volume_quintile") == 5]
    shares = Counter(r.get("ticker") for r in q5)
    top_ticker, top_n = (shares.most_common(1)[0] if q5 else (None, 0))
    max_share = round(top_n / len(q5), 4) if q5 else 0.0
    counters = {
        "tagged_settled": len(tagged),
        "q5_settled": len(q5),
        "max_q5_ticker_share": max_share,
        "max_q5_ticker": top_ticker,
    }
    thresholds = {"q5_settled": 20, "max_q5_ticker_share_max": 0.40}
    ready = len(q5) >= 20 and max_share <= 0.40
    concentration_blocked = len(q5) > 0 and max_share > 0.40
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "exp-20260716-007 post_run_reflection (Q5>=20 AND max ticker share <=40%); "
            "NOTE the ticket's own acceptance_rule said Q5>=12 -- the reflection is governing"
        ),
        "counter_source": "data/paper_sleeves/forward_replacement_value.jsonl",
        "note": (
            "Concentration currently breached (deadlock risk): even at Q5>=20 the lane "
            "stays blocked while one ticker holds >40% of Q5 rows."
            if concentration_blocked
            else "Both count and concentration must pass together."
        ),
    }


def lane_move_relief_forward():
    """Accepted MOVE relief sleeve (exp-20260711-004); live activation waits on
    ~30 settled forward rows (project memory move-relief-sleeve-accepted-2026-07-11)."""
    path = os.path.join(
        REPO_ROOT, "data", "paper_sleeves", "move_rate_volatility_relief", "snapshots.jsonl"
    )
    rows = _read_jsonl(path)
    last = rows[-1] if rows else {}
    counters = {
        "closed_position_count": int(last.get("closed_position_count") or 0),
        "pending_count": int(last.get("new_pending_count") or 0),
        "snapshot_asof": last.get("asof_date"),
    }
    thresholds = {"closed_position_count": 30}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if counters["closed_position_count"] >= 30 else "not_ready",
        "threshold_source": "live-activation bar noted at exp-20260711-004 acceptance (~30 forward rows)",
        "counter_source": "data/paper_sleeves/move_rate_volatility_relief/snapshots.jsonl",
        "note": "Sleeve only fires on MOVE relief trigger days; zero rows is trigger drought, not breakage.",
    }


def lane_prediction_market_postfix():
    """Observer fetch repaired 2026-07-18 (exp-20260718-002); reopen counting
    restarts with rows observed on/after 2026-07-18."""
    path = _latest(
        "data/non_ohlcv/prediction_market_event_observer/outcome_ledgers/"
        "prediction_market_event_observer_outcomes_*.jsonl"
    )
    rows = _read_jsonl(path)
    post = [r for r in rows if str(r.get("observed_date", "")) >= "2026-07-18"]
    settled = [
        r for r in post
        if r.get("exit_date") and str(r.get("outcome_status", "")).lower() in ("settled", "closed", "ok")
    ]
    counters = {"postfix_rows": len(post), "postfix_settled": len(settled)}
    return {
        "counters": counters,
        "thresholds": {},
        "status": "accumulating",
        "threshold_source": (
            "exp-20260718-002: counts restart post-2026-07-18; no numeric reopen bar declared yet "
            "(10d horizon => earliest settlements ~early August 2026)"
        ),
        "counter_source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "note": "Declare a numeric bar when the first post-fix cohort settles.",
    }


def lane_entity_theme_axis_c():
    """Observed-only refresh exp-20260719-004 baseline: 47512 settled rows.
    Axis-(c) requires >=+50% growth (>=71268) before a same-face re-probe."""
    path = os.path.join(
        REPO_ROOT, "data", "non_ohlcv", "entity_theme_news_observer", "latest_outcome_summary.json"
    )
    d = json.load(open(path, encoding="utf-8"))
    baseline = 47512
    current = int(d.get("settled_count") or 0)
    counters = {
        "settled_count": current,
        "baseline_at_last_probe": baseline,
        "growth_pct": round((current - baseline) / baseline * 100, 2),
    }
    thresholds = {"settled_count": int(baseline * 1.5)}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if current >= baseline * 1.5 else "not_ready",
        "threshold_source": "AGENTS.md section 2.4 axis (c): >=+50% and >=+10 settled rows vs exp-20260719-004 baseline",
        "counter_source": "data/non_ohlcv/entity_theme_news_observer/latest_outcome_summary.json",
        "note": None,
    }


def lane_flow_options_lead():
    """exp-20260721-001 lead. Reopen: >=10 additional genuine forward PIT flow
    collection dates (after 2026-07-20) AND >=20 settled paired disagreement
    decisions. Only the collection-date half is machine-derivable here."""
    path = os.path.join(REPO_ROOT, "data", "non_ohlcv", "moomoo_capital_flow_day", "rows.jsonl")
    first_fetch_by_date = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            fd = str(r.get("flow_date", ""))
            if fd <= "2026-07-20":
                continue
            fa = str(r.get("fetched_at", ""))[:10]
            prev = first_fetch_by_date.get(fd)
            if prev is None or fa < prev:
                first_fetch_by_date[fd] = fa
    pit_dates = [
        fd for fd, fa in first_fetch_by_date.items()
        if fa and (datetime.fromisoformat(fa) - datetime.fromisoformat(fd)).days <= 2
    ]
    counters = {
        "forward_pit_flow_dates_post_20260720": len(pit_dates),
        "settled_paired_disagreement_decisions": None,
    }
    thresholds = {"forward_pit_flow_dates_post_20260720": 10, "settled_paired_disagreement_decisions": 20}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "not_ready",
        "threshold_source": "exp-20260721-001 post_run_reflection new_evidence_required",
        "counter_source": "data/non_ohlcv/moomoo_capital_flow_day/rows.jsonl (flow archive confirmed daily-refreshing 2026-07-21)",
        "note": (
            "Paired-disagreement settlement count is not machine-derivable from a single "
            "ledger yet; recount it manually (owner codex-root) before declaring ready."
        ),
    }


def lane_allocator_cross_source_conflict():
    """Parked exp-20260720-004. Reopen: >=20 settled forward same-day core-entry x
    sleeve-candidate conflict rows, or a genuinely new allocator funding mechanism."""
    return {
        "counters": {"settled_conflict_rows_last_manual": 9},
        "thresholds": {"settled_conflict_rows": 20},
        "status": "manual_check_required",
        "threshold_source": "exp-20260720-004 park declaration",
        "counter_source": "manual join over allocator forward face (last hand-verified 2026-07-20: 9 closed, conflict rate ~0)",
        "note": "No single canonical ledger exposes the conflict join; automate only if the lane matters again.",
    }


def lane_news_propagation_negative_side():
    """Inverted-polarity news propagation lead. Reopen: 200 closed negative-side
    forward rows before reading direction again (do not re-slice earlier)."""
    return {
        "counters": {"negative_side_closed_last_manual": 56},
        "thresholds": {"negative_side_closed": 200},
        "status": "manual_check_required",
        "threshold_source": "news-propagation line park note (project memory, 2026-07-19: 56/200, early mean excess_10d ~ -946bp)",
        "counter_source": "manual count over news propagation forward ledger (polarity field mapping unresolved)",
        "note": "Early direction is OPPOSITE the replay lead; record-only until 200 rows.",
    }


def lane_phase2_estimate_revision():
    """Discovery-layer Phase 2 NO-GO (exp-20260721-002). Reopen requires ALL of:
    >=30 qualified non-flat independent decisions, >=10 mapped tickers, >=10
    structured actual cash conflicts, >=30 settled decisions at each of H5/H10/H20,
    passing source contracts, and a fresh outcome-blind D0-D3 scope that selects."""
    return {
        "counters": {
            "qualified_nonflat_decisions": 0,
            "mapped_tickers": 0,
            "actual_cash_conflicts": 0,
            "settled_h5": 0,
            "settled_h10": 0,
            "settled_h20": 0,
        },
        "thresholds": {
            "qualified_nonflat_decisions": 30,
            "mapped_tickers": 10,
            "actual_cash_conflicts": 10,
            "settled_h5": 30,
            "settled_h10": 30,
            "settled_h20": 30,
        },
        "status": "manual_check_required",
        "threshold_source": "docs/alpha_search_phase1_handoff.md Phase 1.5 (exp-20260721-002)",
        "counter_source": "new-contract estimate-revision qualification surface (owner codex-root)",
        "note": (
            "All counters were zero at contract creation and the 38,494 legacy rows are "
            "quarantined (not retro-qualified). UNVERIFIED whether the new qualification "
            "surface is wired into the daily pipeline -- if it is not, these counters never "
            "advance and Phase 2 NO-GO is permanent, not pending. The legacy "
            "estimate_revision_outcome_summary_*.json files still refresh daily via run.py "
            "but do NOT count toward these thresholds."
        ),
    }


LANES = {
    "exit_lifecycle_advisory": lane_exit_lifecycle_advisory,
    "short_volume_q5_soft_tilt": lane_short_volume_q5_soft_tilt,
    "move_relief_forward": lane_move_relief_forward,
    "prediction_market_postfix": lane_prediction_market_postfix,
    "entity_theme_axis_c": lane_entity_theme_axis_c,
    "flow_options_lead": lane_flow_options_lead,
    "allocator_cross_source_conflict": lane_allocator_cross_source_conflict,
    "news_propagation_negative_side": lane_news_propagation_negative_side,
    "phase2_estimate_revision": lane_phase2_estimate_revision,
}

STALL_DAYS = 7  # counters unchanged this long => flag as potential park deadlock


def _load_previous():
    if os.path.exists(OUTPUT_PATH):
        try:
            return json.load(open(OUTPUT_PATH, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _numeric_counters(counters):
    return {k: v for k, v in counters.items() if isinstance(v, (int, float))}


def build():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now[:10]
    prev = _load_previous()
    prev_lanes = {l["lane"]: l for l in (prev or {}).get("lanes", [])}

    lanes_out = []
    for name, fn in LANES.items():
        try:
            lane = fn()
        except Exception as exc:  # per-lane fail-open by contract
            lane = {
                "counters": {},
                "thresholds": {},
                "status": "error",
                "threshold_source": None,
                "counter_source": None,
                "note": f"builder error: {type(exc).__name__}: {exc}",
            }
        lane["lane"] = name

        history = list(prev_lanes.get(name, {}).get("history", []))
        numeric = _numeric_counters(lane["counters"])
        if not history or _numeric_counters(history[-1].get("counters", {})) != numeric:
            history.append({"as_of": today, "counters": numeric})
        history = history[-HISTORY_CAP:]
        lane["history"] = history

        last_change = history[-1]["as_of"] if history else today
        days_stale = (datetime.fromisoformat(today) - datetime.fromisoformat(last_change)).days
        lane["days_since_progress"] = days_stale
        lane["stalled"] = (
            days_stale >= STALL_DAYS and lane["status"] not in ("ready", "error")
        )
        lanes_out.append(lane)

    order = {"ready": 0, "not_ready": 1, "accumulating": 2, "manual_check_required": 3, "error": 4}
    lanes_out.sort(key=lambda l: (order.get(l["status"], 9), l["lane"]))

    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "generator": "scripts/build_reopen_readiness.py (exp-20260721-004)",
        "stall_flag_days": STALL_DAYS,
        "lanes": lanes_out,
    }
    tmp = OUTPUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, OUTPUT_PATH)
    return out


def main():
    out = build()
    print(f"wrote {os.path.relpath(OUTPUT_PATH, REPO_ROOT)}  ({len(out['lanes'])} lanes)")
    width = max(len(l["lane"]) for l in out["lanes"]) + 2
    for l in out["lanes"]:
        gaps = []
        for k, bar in l["thresholds"].items():
            if k.endswith("_max"):
                cur = l["counters"].get(k[: -len("_max")])
                if isinstance(cur, (int, float)) and cur > bar:
                    gaps.append(f"{k[:-4]}={cur}>{bar}")
                continue
            cur = l["counters"].get(k)
            if isinstance(cur, (int, float)) and cur < bar:
                gaps.append(f"{k}={cur}/{bar}")
        flag = " [STALLED]" if l.get("stalled") else ""
        print(f"  {l['lane']:<{width}} {l['status']:<22} {'; '.join(gaps) or '-'}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
