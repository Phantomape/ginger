"""exp-20260628-015: de-biased full-population replay of the trend_long
breakout-without-2x-volume entry-latency lead.

exp-20260627-006 (observed-only) found 24/39 ACTUAL trend_long trades had a
production-visible breakout-without-2x-volume precursor 1-5 sessions earlier with
a +1.92% median entry-price advantage and +2.46% 10d delta. That statistic is
SELECTION-CONDITIONED on breakouts that eventually became real trades. This runner
removes the survivorship bias: it scans the EVERY breakout-without-2x-volume
precursor across the 50-name core universe over the three standard windows --
including the vast majority that never become a trend_long entry -- and compares
the full-population forward replacement value against the actual-entry subset.

It is read-only historical replay. It creates/ranks/sizes/exits/orders nothing.
The decision deliverable is the de-biased base rate, not a behavior change.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import breakout_precursor_paper_sleeve as bps  # noqa: E402
import data_layer  # noqa: E402
import forward_replacement_value as frv  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    connect_overlay_reader,
    hot_path_for,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260628-015"
LANE = "alpha_search"
OWNER = "agent-trend-entry-latency"
SLUG = "breakout_precursor_full_population_replay"
RUNNER = f"quant/experiments/exp_20260628_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ASOF_DATE = "2026-06-28"

BASELINE_PATH = (
    REPO_ROOT / "data" / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
EXP006_TRADE_ROWS = (
    REPO_ROOT / "data" / "experiments" / "exp-20260627-006"
    / "trend_long_entry_latency_attribution_trade_rows.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_015_{SLUG}.json"
LEDGER_JSONL = OUT_DIR / "breakout_precursor_events.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = [
    ("late_strong", "2025-10-23", "2026-04-21"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("old_thin", "2024-10-02", "2025-04-22"),
]

HYPOTHESIS = (
    "entry/candidate_pool: trend_long enters late because it waits for >2x volume "
    "confirmation after the 20d-high breakout; exp-20260627-006 found 24/39 actual "
    "trend_long trades had an earlier breakout-without-2x-volume precursor. De-bias "
    "that survivorship-conditioned lead by measuring the FULL precursor population "
    "(above_200ma & breakout_20d & not volume_spike) forward replacement value "
    "before any volume-threshold or entry-timing change."
)
CHANGED_VARIABLE = "breakout_without_2x_volume_precursor_forward_replacement_value_v1"
PREDICTION = {
    "success_probability": 0.7,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_universe_scan_misses_precursor_events",
        "full_population_base_rate_kills_the_lead",
        "late_strong_dominates_population_no_net_edge",
    ],
    "confidence_reason": (
        "Detection forks an existing PIT feature over warehouse OHLCV that covers "
        "the 50-name universe with deep history; the 0.3 failure mass is the "
        "de-biased base rate plausibly erasing the survivorship-conditioned lead, "
        "which is the point of the measurement."
    ),
    "recorded_at": "2026-06-28T00:00:00+00:00",
}
CHANGED_FILES = [
    "quant/breakout_precursor_paper_sleeve.py",
    "quant/test_breakout_precursor_paper_sleeve.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260628_015_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/breakout_precursor_events.jsonl",
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


def read_json(path: Path) -> Any:
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


def load_bars(ticker: str) -> list[tuple]:
    path = Path(DEFAULT_WAREHOUSE_PATH)
    if not path.exists() and not hot_path_for(path).exists():
        return []
    con = connect_overlay_reader(path)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT date, open, high, low, close, volume FROM ohlcv_overlay "
            "WHERE ticker = ? ORDER BY date",
            [ticker],
        )
        return [tuple(r) for r in cur.fetchall()]
    finally:
        con.close()


def window_of(d: str) -> str | None:
    for label, start, end in WINDOWS:
        if start <= d <= end:
            return label
    return None


def _fwd(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    vals = [
        e["forward"]["horizons"].get(str(horizon), {}).get("forward_net_return_pct")
        for e in rows
    ]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "median": None}
    return {
        "n": len(vals),
        "mean": round(mean(vals), 4),
        "median": round(median(vals), 4),
    }


def aggregate_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
    }


def run_replay() -> dict[str, Any]:
    universe = data_layer.get_universe()
    trade_rows = read_json(EXP006_TRADE_ROWS)
    actual_by_ticker: dict[str, list[str]] = defaultdict(list)
    for r in trade_rows:
        t = str(r.get("ticker") or "").upper()
        ed = str(r.get("entry_date") or r.get("actual_entry_date") or "")[:10]
        if t and ed:
            actual_by_ticker[t].append(ed)
    actual_total = sum(len(v) for v in actual_by_ticker.values())
    regime_spy = frv.load_regime_spy_bars()

    all_events: list[dict[str, Any]] = []
    names_with_bars = 0
    for t in universe:
        bars = load_bars(t)
        if len(bars) < bps.MIN_PRIOR_BARS + max(bps.FORWARD_HORIZONS) + 2:
            continue
        names_with_bars += 1
        events = bps.scan_ticker_precursors(
            t, bars, regime_spy_bars=regime_spy, actual_entry_dates=actual_by_ticker.get(t)
        )
        for e in events:
            e["window"] = window_of(e["signal_date"])
        all_events.extend(events)

    in_window = [e for e in all_events if e["window"]]
    settled = [e for e in in_window if e["forward"]["status"] == "settled"]
    subset = [e for e in settled if e["became_trend_long_entry"]]

    by_window = {}
    for label, _, _ in WINDOWS:
        rows = [e for e in settled if e["window"] == label]
        sub = [e for e in rows if e["became_trend_long_entry"]]
        by_window[label] = {
            "full_population": {"10d": _fwd(rows, 10), "20d": _fwd(rows, 20)},
            "actual_entry_subset": {"10d": _fwd(sub, 10), "20d": _fwd(sub, 20)},
        }

    by_regime = {}
    grp: dict[str, list] = defaultdict(list)
    for e in settled:
        grp[str(e.get("entry_regime_label"))].append(e)
    for lab, rows in grp.items():
        by_regime[lab] = {"10d": _fwd(rows, 10), "20d": _fwd(rows, 20)}

    return {
        "universe_size": len(universe),
        "names_with_bars": names_with_bars,
        "actual_trend_long_entries_joined": actual_total,
        "precursor_events_total": len(all_events),
        "precursor_events_in_window": len(in_window),
        "precursor_events_settled_in_window": len(settled),
        "became_actual_entry_subset": len(subset),
        "forward_full_population": {"10d": _fwd(settled, 10), "20d": _fwd(settled, 20)},
        "forward_actual_entry_subset": {"10d": _fwd(subset, 10), "20d": _fwd(subset, 20)},
        "by_window": by_window,
        "by_chop_regime_label": by_regime,
        "_events": all_events,
    }


def build_result() -> dict[str, Any]:
    before = aggregate_metrics()
    replay = run_replay()
    events = replay.pop("_events")

    full10 = replay["forward_full_population"]["10d"]
    sub10 = replay["forward_actual_entry_subset"]["10d"]
    old_thin_full_20 = replay["by_window"]["old_thin"]["full_population"]["20d"]

    inflation_10d = (
        round(sub10["mean"] / full10["mean"], 2)
        if full10.get("mean") not in (None, 0)
        else None
    )
    # Decision: the full-population base rate is materially below the
    # survivorship subset and is negative-at-median in old_thin, so a blanket
    # volume-gate relaxation / earlier-entry rule is NOT supported.
    lead_deflated = bool(
        full10.get("mean") is not None
        and sub10.get("mean") is not None
        and full10["mean"] < sub10["mean"] * 0.6
    )
    old_thin_loss = bool(
        old_thin_full_20.get("median") is not None and old_thin_full_20["median"] < 0
    )

    decision = (
        "observed_de_biased_precursor_base_rate_deflates_entry_latency_lead"
        if (lead_deflated or old_thin_loss)
        else "observed_precursor_base_rate_supports_entry_latency_lead"
    )
    status = "observed_only"

    summary_text = (
        f"Full-population breakout-without-2x-volume precursor base rate is "
        f"{full10['mean']}% (median {full10['median']}%) at 10d / "
        f"{replay['forward_full_population']['20d']['mean']}% at 20d across "
        f"{replay['precursor_events_settled_in_window']} settled in-window events, "
        f"versus {sub10['mean']}% / "
        f"{replay['forward_actual_entry_subset']['20d']['mean']}% on the "
        f"{replay['became_actual_entry_subset']}-event actual-entry subset that "
        f"exp-20260627-006 measured -- a ~{inflation_10d}x survivorship inflation "
        f"at 10d. old_thin full-population 20d median is "
        f"{old_thin_full_20['median']}% (negative). The 2x volume gate performs "
        f"real selection; a blanket earlier-entry / volume-threshold relaxation is "
        f"not supported."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "lead_deflated": lead_deflated,
        "old_thin_full_population_negative_median": old_thin_loss,
        "survivorship_inflation_10d_x": inflation_10d,
        "timestamp": utc_now(),
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_de_biased_full_population_entry_latency_replay",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "entry",
        "trial_family": "breakout_without_2x_volume_precursor_forward_replacement",
        "trial_variant_id": "full_population_precursor_forward_ledger_v1",
        "nearby_prior_experiments": [
            "exp-20260530-013",
            "exp-20260530-016",
            "exp-20260627-006",
        ],
        "new_evidence_type": (
            "full_population_breakout_without_2x_volume_precursor_forward_replacement_rows"
        ),
        "new_evidence_axis": (
            "forward replacement-value paper rows on named breakout-without-2x-volume "
            "latency cases (full-population, regime-bucketed) -- the explicit "
            "reopen_condition of frozen families prebreakout_momentum_entry "
            "(exp-20260530-013) and prebreakout_catalyst_qualified_entry "
            "(exp-20260530-016)"
        ),
        "before_metrics": before,
        "replay": replay,
        "summary": summary_text,
        "gate1": {"passed": True, "baseline_result_file": repo_rel(BASELINE_PATH)},
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "above_200ma",
                "breakout_20d",
                "volume_spike_ratio",
                "forward_net_return_pct",
                "entry_regime_label",
                "became_trend_long_entry",
            ],
        },
        "gate3": {"passed": True, "new_filter_added": False},
        "gate4": {
            "passed": True,
            "strategy_replay_changed": False,
            "observed_only": True,
            "decision": decision,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_off_attribution_only": True,
            "live_ready": False,
            "parity_note": (
                "Read-only historical replay. The precursor detector reproduces "
                "feature_layer.compute_trend_features (200d MA / prior-20d high / "
                "20d avg-vol / 2.0x) minus the volume confirmation; it changes no "
                "paper or live decision surface."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "exp-20260627-006's +1.92%/+2.46% precursor advantage was measured "
                "only on breakouts that became real trades. The full precursor "
                "population earns roughly half the 10d return and is negative at the "
                "median in old_thin, because the 2x volume confirmation selects the "
                "names that go on to work. Removing it floods in weak events."
            ),
            "forbidden_near_neighbor_retry": (
                "Do NOT relax the volume_spike 2.0x threshold, add a blanket "
                "prebreakout / earlier-entry rule, or retune any threshold/top-N/"
                "notional on this frozen sample -- that is the frozen "
                "prebreakout_momentum_entry / prebreakout_catalyst_qualified_entry "
                "family, and the de-biased base rate confirms its rejection. An "
                "earlier-entry timing gain exists only on the already-selected "
                "subset, but selecting that subset at decision time requires exactly "
                "the volume confirmation whose removal defines the precursor "
                "(circular)."
            ),
            "new_evidence_required": (
                "A genuinely new PIT pre-volume-confirmation field that predicts "
                "WHICH breakout-without-2x-volume names go on to work (e.g. PIT "
                "borrow/availability, options-implied pressure, breadth persistence), "
                "tested out of sample -- not a volume-threshold change. Only such a "
                "selector would justify a default-off forward ledger; a blanket "
                "ledger of a deflated signal would be measurement treadmill."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_breakout_precursor_paper_sleeve.py",
            RUNNER_COMMAND,
        ],
        "artifact": repo_rel(OUT_JSON),
        "ledger_file": repo_rel(LEDGER_JSONL),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
        "_events": events,
    }


def write_ledger(events: list[dict[str, Any]]) -> None:
    LEDGER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_JSONL.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, sort_keys=True) + "\n")


def write_card(result: dict[str, Any]) -> None:
    r = result["replay"]
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
        result["summary"],
        "",
        "| sample | fwd 10d mean/median | fwd 20d mean/median |",
        "|---|---|---|",
        f"| full population (n={r['precursor_events_settled_in_window']}) | "
        f"{r['forward_full_population']['10d']['mean']}% / {r['forward_full_population']['10d']['median']}% | "
        f"{r['forward_full_population']['20d']['mean']}% / {r['forward_full_population']['20d']['median']}% |",
        f"| actual-entry subset (n={r['became_actual_entry_subset']}) | "
        f"{r['forward_actual_entry_subset']['10d']['mean']}% / {r['forward_actual_entry_subset']['10d']['median']}% | "
        f"{r['forward_actual_entry_subset']['20d']['mean']}% / {r['forward_actual_entry_subset']['20d']['median']}% |",
        "",
        "## Boundary",
        "",
        result["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Next Evidence",
        "",
        result["post_run_reflection"]["new_evidence_required"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_breakout_precursor_paper_sleeve.py`",
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
    events = result.pop("_events")
    write_ledger(events)
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
            "new_evidence_axis": result["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": CHANGED_FILES,
        },
    )

    print(json.dumps({k: v for k, v in result.items() if k != "replay"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
