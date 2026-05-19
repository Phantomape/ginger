"""Meta research engine for experiment history.

This module studies the research process itself. It reads structured experiment
logs and summarizes which change families have historically worked, failed, or
should be frozen until new evidence appears.

It is read-only: no trading logic, backtest logic, or production policy changes.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"_parse_error": True, "raw": line[:500]})
    return rows


def load_experiment_logs(root=DEFAULT_ROOT):
    """Load experiment records from JSONL and per-experiment JSON logs."""
    root = Path(root)
    records = []

    jsonl_path = root / "docs" / "experiment_log.jsonl"
    for row in _read_jsonl(jsonl_path):
        row.setdefault("_source", str(jsonl_path))
        records.append(row)

    logs_dir = root / "docs" / "experiments" / "logs"
    if logs_dir.exists():
        for path in sorted(logs_dir.glob("*.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                row.setdefault("_source", str(path))
                records.append(row)

    return records


def _decision(record):
    return str(record.get("decision") or record.get("status") or "unknown").lower()


def _change_type(record):
    value = record.get("change_type") or record.get("category") or "unknown"
    return str(value).lower().replace(" ", "_")


def _component(record):
    return str(record.get("component") or record.get("primary_component") or "unknown")


def _delta(record, key):
    delta = record.get("delta_metrics") or record.get("deltas") or {}
    if key in delta:
        return _float(delta.get(key), 0.0)

    before = record.get("before_metrics") or record.get("baseline_metrics") or {}
    after = record.get("after_metrics") or record.get("candidate_metrics") or {}
    if key in before or key in after:
        return _float(after.get(key), 0.0) - _float(before.get(key), 0.0)
    return 0.0


def _metric(record, bucket, key):
    values = record.get(bucket) or {}
    return _float(values.get(key), None)


def _experiment_id(record):
    return str(record.get("experiment_id") or record.get("id") or Path(record.get("_source", "unknown")).stem)


def _sample_count(record):
    for bucket in ("after_metrics", "candidate_metrics", "delta_metrics", "before_metrics"):
        value = _metric(record, bucket, "trade_count")
        if value is not None:
            return value
        value = _metric(record, bucket, "trades")
        if value is not None:
            return value
    return None


def classify_research_family(record):
    """Infer a durable research family from log metadata and text."""
    text = " ".join(
        str(record.get(k, ""))
        for k in ["experiment_id", "hypothesis", "change_summary", "change_type", "component", "notes"]
    ).lower()

    if "cap" in text or "position_cap" in text:
        return "position_cap_or_cap_release"
    if "topup" in text or "top-up" in text or "risk_scalar" in text or "risk_budget" in text:
        return "risk_scalar_or_topup"
    if "slot" in text or "ranking" in text or "priority" in text:
        return "slot_or_ranking"
    if "filter" in text or "gate" in text or "guard" in text:
        return "filter_or_gate"
    if "exit" in text or "target" in text or "trailing" in text or "time_stop" in text:
        return "exit_policy"
    if "llm" in text or "prompt" in text or "news" in text or "event" in text:
        return "event_or_llm"
    if "space" in text or "pilot" in text or "sleeve" in text:
        return "pilot_or_sleeve"
    if "ticker" in text or "tsm" in text or "isrg" in text:
        return "ticker_specific"
    return _change_type(record)


def score_experiment(record):
    """Score one experiment as research evidence, not as live PnL."""
    ev_delta = _delta(record, "expected_value_score")
    pnl_delta = _delta(record, "total_pnl") or _delta(record, "pnl")
    dd_delta = _delta(record, "max_drawdown_pct")
    survival_delta = _delta(record, "survival_rate")
    trade_delta = _delta(record, "trade_count") or _delta(record, "trades")
    decision = _decision(record)
    sample = _sample_count(record)

    score = 0.0
    score += ev_delta * 10.0
    score += pnl_delta / 10000.0
    score -= max(0.0, dd_delta) * 20.0
    score += max(0.0, -dd_delta) * 5.0
    score += max(0.0, survival_delta) * 0.5
    score -= max(0.0, -survival_delta) * 1.0

    if decision in {"accepted", "accept", "promoted"}:
        score += 2.0
    elif decision in {"rejected", "rolled_back", "reject"}:
        score -= 1.0

    if sample is not None and sample < 5:
        score -= 1.0
    if abs(trade_delta) > 5:
        score -= 0.25

    return round(score, 4)


def _aggregate(records, key_fn):
    groups = defaultdict(list)
    for record in records:
        groups[key_fn(record)].append(record)

    out = []
    for key, rows in groups.items():
        accepted = [r for r in rows if _decision(r) in {"accepted", "accept", "promoted"}]
        rejected = [r for r in rows if _decision(r) in {"rejected", "reject", "rolled_back"}]
        scores = [score_experiment(r) for r in rows]
        ev_deltas = [_delta(r, "expected_value_score") for r in rows]
        pnl_deltas = [_delta(r, "total_pnl") or _delta(r, "pnl") for r in rows]
        out.append({
            "name": key,
            "experiments": len(rows),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "accept_rate": round(len(accepted) / len(rows), 4) if rows else 0.0,
            "avg_meta_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "sum_ev_delta": round(sum(ev_deltas), 4),
            "sum_pnl_delta": round(sum(pnl_deltas), 2),
            "recent_examples": [_experiment_id(r) for r in rows[-5:]],
        })
    return sorted(out, key=lambda r: (r["avg_meta_score"], r["sum_ev_delta"]), reverse=True)


def build_freeze_candidates(records):
    """Find families/components with repeated rejection or bad meta score."""
    candidates = []
    for row in _aggregate(records, classify_research_family):
        if row["experiments"] >= 3 and row["accept_rate"] <= 0.2:
            candidates.append({
                "scope": "family",
                "name": row["name"],
                "reason": "low_accept_rate",
                "accept_rate": row["accept_rate"],
                "experiments": row["experiments"],
            })
        if row["experiments"] >= 3 and row["avg_meta_score"] < -0.5:
            candidates.append({
                "scope": "family",
                "name": row["name"],
                "reason": "negative_average_meta_score",
                "avg_meta_score": row["avg_meta_score"],
                "experiments": row["experiments"],
            })
    return candidates


def build_recommendations(records):
    by_family = _aggregate(records, classify_research_family)
    recs = []
    if by_family:
        best = by_family[0]
        recs.append({
            "type": "continue_high_prior_family",
            "family": best["name"],
            "why": "highest average meta score in recorded experiments",
            "avg_meta_score": best["avg_meta_score"],
            "accept_rate": best["accept_rate"],
        })

    for row in by_family:
        if row["name"] in {"position_cap_or_cap_release", "risk_scalar_or_topup"} and row["accept_rate"] > 0.3:
            recs.append({
                "type": "prefer_allocation_over_filtering",
                "family": row["name"],
                "why": "allocation-style changes show positive evidence; keep candidate set fixed when possible",
                "sum_ev_delta": row["sum_ev_delta"],
            })
            break

    for freeze in build_freeze_candidates(records)[:5]:
        recs.append({
            "type": "freeze_or_require_new_evidence",
            "family": freeze["name"],
            "why": freeze["reason"],
            "next_retry_requires": [
                "new forward evidence",
                "materially different production-visible discriminator",
                "not a nearby scalar retry",
            ],
        })

    return recs


def build_meta_report(root=DEFAULT_ROOT):
    records = [r for r in load_experiment_logs(root) if not r.get("_parse_error")]
    scored = []
    for record in records:
        scored.append({
            "experiment_id": _experiment_id(record),
            "decision": _decision(record),
            "change_type": _change_type(record),
            "family": classify_research_family(record),
            "component": _component(record),
            "meta_score": score_experiment(record),
            "ev_delta": round(_delta(record, "expected_value_score"), 4),
            "pnl_delta": round(_delta(record, "total_pnl") or _delta(record, "pnl"), 2),
            "source": record.get("_source"),
        })

    return {
        "schema_version": 1,
        "read_only": True,
        "records_loaded": len(records),
        "by_family": _aggregate(records, classify_research_family),
        "by_change_type": _aggregate(records, _change_type),
        "by_component": _aggregate(records, _component),
        "top_experiments": sorted(scored, key=lambda r: r["meta_score"], reverse=True)[:20],
        "worst_experiments": sorted(scored, key=lambda r: r["meta_score"])[:20],
        "freeze_candidates": build_freeze_candidates(records),
        "recommendations": build_recommendations(records),
        "notes": [
            "This is a research-prior engine, not a trading signal.",
            "Scores are intentionally coarse and should guide what to test next, not what to trade.",
            "Low-quality or missing delta_metrics reduce precision; improve experiment logs before treating rankings as strong evidence.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = build_meta_report(args.root)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text)


if __name__ == "__main__":
    main()
