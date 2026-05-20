"""Meta research engine for experiment history.

This module studies the research process itself. It reads structured experiment
logs and summarizes which change families have historically worked, failed, or
should be frozen until new evidence appears.

It is read-only: no trading logic, backtest logic, or production policy changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]

PRIORITY_WEIGHTS = {
    "evidence_score": 0.35,
    "reproducibility_score": 0.25,
    "production_feasibility": 0.20,
    "novelty_score": 0.10,
    "risk_control_score": 0.10,
}

METRIC_BUCKETS = (
    "after_metrics",
    "candidate_metrics",
    "delta_metrics",
    "deltas",
    "before_metrics",
    "baseline_metrics",
)

DELTA_ALIASES = {
    "expected_value_score": (
        "expected_value_score",
        "expected_value_score_delta",
        "aggregate_ev_delta",
        "ev_delta",
    ),
    "total_pnl": ("total_pnl", "total_pnl_delta", "aggregate_pnl_delta", "pnl_delta"),
    "pnl": ("pnl", "pnl_delta", "total_pnl_delta", "aggregate_pnl_delta"),
    "max_drawdown_pct": ("max_drawdown_pct", "max_drawdown_pct_delta"),
    "survival_rate": ("survival_rate", "survival_rate_delta"),
    "trade_count": ("trade_count", "trade_count_delta", "trades_delta"),
    "trades": ("trades", "trades_delta", "trade_count_delta"),
}

ALLOCATION_FAMILIES = {
    "position_cap_or_cap_release",
    "risk_scalar_or_topup",
    "ticker_specific",
    "pilot_or_sleeve",
}

BROAD_OR_RISKY_FAMILIES = {
    "filter_or_gate",
    "slot_or_ranking",
    "exit_policy",
}

MEASUREMENT_REPAIR_TOKENS = (
    "measurement",
    "instrumentation",
    "logging",
    "documentation",
    "data_audit",
    "data audit",
    "coverage",
    "parity",
    "known_bias",
    "process",
    "replay_fix",
    "data_gap",
    "oracle_diagnostics",
    "observed_only",
    "diagnostic",
    "data_collection",
    "triage",
)

STRATEGY_ITERATION_TOKENS = (
    "alpha",
    "entry",
    "exit",
    "ranking",
    "rank",
    "slot",
    "queue",
    "allocation",
    "risk",
    "llm",
    "event",
    "sleeve",
    "candidate_pool",
    "universe",
    "target",
    "notional",
    "shadow",
)


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


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

    log_dirs = [
        root / "experiments" / "logs",
        root / "docs" / "experiments" / "logs",
    ]
    for logs_dir in log_dirs:
        if not logs_dir.exists():
            continue
        for path in sorted(logs_dir.glob("*.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                row.setdefault("_source", str(path))
                records.append(row)

    return records


def _decision(record):
    return str(record.get("decision") or record.get("status") or "unknown").lower()


def _record_text(record):
    return " ".join(
        str(record.get(k, ""))
        for k in [
            "experiment_id",
            "hypothesis",
            "change_summary",
            "change_type",
            "component",
            "notes",
            "lane",
            "decision",
            "status",
        ]
    ).lower()


def _is_accepted_decision(record):
    decision = _decision(record)
    return (
        decision in {"accepted", "accept", "promoted"}
        or decision.startswith("accepted_")
        or decision.startswith("accept_")
        or decision.startswith("promoted_")
    )


def _is_rejected_decision(record):
    decision = _decision(record)
    return (
        decision in {"rejected", "reject", "rolled_back"}
        or decision.startswith("rejected_")
        or decision.startswith("reject_")
        or decision.startswith("rolled_back_")
    )


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _change_type(record):
    value = record.get("change_type") or record.get("category") or "unknown"
    return str(value).lower().replace(" ", "_")


def _component(record):
    return str(record.get("component") or record.get("primary_component") or "unknown")


def _delta(record, key):
    delta = _as_dict(record.get("delta_metrics"))
    if not delta:
        delta = _as_dict(record.get("deltas"))
    for alias in DELTA_ALIASES.get(key, (key,)):
        if alias in delta:
            return _float(delta.get(alias), 0.0)
        if alias in record:
            return _float(record.get(alias), 0.0)

    before = _as_dict(record.get("before_metrics"))
    if not before:
        before = _as_dict(record.get("baseline_metrics"))
    after = _as_dict(record.get("after_metrics"))
    if not after:
        after = _as_dict(record.get("candidate_metrics"))
    if key in before or key in after:
        return _float(after.get(key), 0.0) - _float(before.get(key), 0.0)
    return 0.0


def _metric(record, bucket, key):
    values = _as_dict(record.get(bucket))
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


def _production_impact(record):
    impact = record.get("production_impact") or {}
    return impact if isinstance(impact, dict) else {}


def is_measurement_repair_record(record):
    return any(token in _record_text(record) for token in MEASUREMENT_REPAIR_TOKENS)


def is_strategy_iteration_record(record):
    text = _record_text(record)
    if is_measurement_repair_record(record):
        return False
    lane = str(record.get("lane") or "").lower()
    if "alpha" in lane or "universe_scout" in lane:
        return True
    return any(token in text for token in STRATEGY_ITERATION_TOKENS)


def _family_label_zh(family):
    labels = {
        "position_cap_or_cap_release": "仓位上限/释放",
        "risk_scalar_or_topup": "风险倍率/加仓",
        "ticker_specific": "个股特化规则",
        "pilot_or_sleeve": "试运行/子策略袖珍组合",
        "filter_or_gate": "过滤器/准入门槛",
        "slot_or_ranking": "槽位/排序",
        "exit_policy": "退出/止盈止损",
        "event_or_llm": "事件/LLM 判断",
        "known_bias_disclosure_repair": "已知偏差披露修复",
        "measurement_repair": "测量修复",
        "process_instrumentation": "流程观测与记录",
        "risk_allocation": "风险分配",
        "default_off_alpha_attribution_report_surface": "默认关闭的 Alpha 归因报告层",
        "default_off_paper_candidate_pool": "默认关闭的纸面候选池",
        "default_off_data_collection_harness": "默认关闭的数据采集框架",
        "new_strategy_shadow": "新策略影子实验",
        "failure_taxonomy": "失败类型归因",
        "default_off_harness": "默认关闭的实验框架",
        "replay_only_risk_allocation_discriminator": "仅回放的风险分配判别器",
        "entry_execution_replay_scout": "入场执行回放侦察",
        "forward_watch_adapter": "前向观察适配器",
        "unknown": "未知/未归类",
    }
    return labels.get(family, family.replace("_", " "))


def _priority_summary_zh(family, priority, row):
    return (
        f"{_family_label_zh(family)}：研究优先级 {priority:.4f}。"
        f"历史实验 {row['experiments']} 个，接受率 {row['accept_rate']:.2%}，"
        f"累计 EV 变化 {row['sum_ev_delta']:+.4f}。"
        "这个分数只用于决定下一轮先研究什么，不是交易信号。"
    )


def build_data_quality_warnings(records):
    metric_type_issues = []
    for record in records:
        for bucket in METRIC_BUCKETS:
            if bucket not in record:
                continue
            value = record.get(bucket)
            if value is None or isinstance(value, dict):
                continue
            metric_type_issues.append({
                "experiment_id": _experiment_id(record),
                "bucket": bucket,
                "actual_type": type(value).__name__,
                "value_preview": str(value)[:160],
                "source": record.get("_source"),
            })

    return {
        "non_dict_metric_buckets": {
            "count": len(metric_type_issues),
            "examples": metric_type_issues[:10],
            "meaning_zh": (
                "部分旧实验日志把 metrics 字段写成了字符串引用，而不是指标字典。"
                "meta report 会把这些字段当作缺失值处理，并在这里列出样例。"
            ),
        }
    }


def classify_research_family(record):
    """Infer a durable research family from log metadata and text."""
    text = _record_text(record)

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

    if _is_accepted_decision(record):
        score += 2.0
    elif _is_rejected_decision(record):
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
        accepted = [r for r in rows if _is_accepted_decision(r)]
        rejected = [r for r in rows if _is_rejected_decision(r)]
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


def _records_for_family(records, family):
    return [r for r in records if classify_research_family(r) == family]


def _multi_window_hint(record):
    if record.get("secondary_windows"):
        return True
    text = json.dumps(record, ensure_ascii=False).lower()
    return "late_strong" in text and "mid_weak" in text and "old_thin" in text


def _family_production_feasibility(records, family):
    rows = _records_for_family(records, family)
    if not rows:
        return 0.5, ["no direct records; neutral feasibility"]
    points = []
    why = []
    for r in rows:
        impact = _production_impact(r)
        if impact.get("shared_policy_changed") and impact.get("run_adapter_changed"):
            points.append(1.0)
        elif impact.get("replay_only"):
            points.append(0.55)
        elif impact.get("shared_policy_changed") and not impact.get("run_adapter_changed"):
            points.append(0.25)
        elif impact:
            points.append(0.70)
        else:
            points.append(0.50)
    avg = sum(points) / len(points)
    if avg >= 0.75:
        why.append("historically production-visible or parity-aware")
    elif avg <= 0.4:
        why.append("historically weak production/backtest parity evidence")
    else:
        why.append("mixed production feasibility evidence")
    return _clamp(avg), why


def _family_reproducibility(records, family):
    rows = _records_for_family(records, family)
    if not rows:
        return 0.4, ["no direct records; weak reproducibility"]
    multi_window = sum(1 for r in rows if _multi_window_hint(r))
    sufficient_sample = sum(1 for r in rows if (_sample_count(r) or 0) >= 10)
    accepted = sum(1 for r in rows if _is_accepted_decision(r))
    score = 0.25
    score += 0.35 * (multi_window / len(rows))
    score += 0.25 * (sufficient_sample / len(rows))
    score += 0.15 * (accepted / len(rows))
    why = []
    if multi_window:
        why.append(f"{multi_window}/{len(rows)} records show multi-window evidence")
    if sufficient_sample:
        why.append(f"{sufficient_sample}/{len(rows)} records have sample >= 10")
    if not why:
        why.append("limited multi-window/sample evidence")
    return _clamp(score), why


def _family_novelty(records, family):
    rows = _records_for_family(records, family)
    if not rows:
        return 0.8, ["new or underexplored family"]
    score = 0.75
    penalties = []
    if len(rows) >= 10:
        score -= 0.20
        penalties.append("heavily explored family; diminishing-return risk")
    if family in {"risk_scalar_or_topup", "ticker_specific"} and len(rows) >= 5:
        score -= 0.15
        penalties.append("nearby scalar/ticker retry risk")
    rejected = sum(1 for r in rows if _is_rejected_decision(r))
    if rows and rejected / len(rows) >= 0.6:
        score -= 0.20
        penalties.append("many prior rejections in this family")
    why = ["still has room for materially new fields"] if not penalties else []
    return _clamp(score), why, penalties


def _family_risk_control(records, family):
    rows = _records_for_family(records, family)
    score = 0.65
    why = []
    penalties = []
    if family in ALLOCATION_FAMILIES:
        score += 0.15
        why.append("usually changes sizing/allocation rather than broad candidate eligibility")
    if family in BROAD_OR_RISKY_FAMILIES:
        score -= 0.20
        penalties.append("can change survival, trade count, or exit distribution broadly")
    if rows:
        avg_dd_delta = sum(_delta(r, "max_drawdown_pct") for r in rows) / len(rows)
        avg_survival_delta = sum(_delta(r, "survival_rate") for r in rows) / len(rows)
        if avg_dd_delta <= 0:
            score += 0.05
            why.append("average drawdown delta is non-worsening")
        else:
            score -= min(0.20, avg_dd_delta * 5)
            penalties.append("average drawdown delta worsens")
        if avg_survival_delta < -0.02:
            score -= 0.10
            penalties.append("survival rate has tended to decline")
    return _clamp(score), why, penalties


def build_research_priorities(records):
    """Transparent research queue scoring by family.

    This is intentionally not optimized or fit. The weights are fixed constants
    and the component scores are exposed for audit.
    """
    family_rows = _aggregate(records, classify_research_family)
    if not family_rows:
        return []

    max_abs_ev = max(abs(row["sum_ev_delta"]) for row in family_rows) or 1.0
    priorities = []
    freeze_names = {item["name"] for item in build_freeze_candidates(records)}

    for row in family_rows:
        family = row["name"]
        why = []
        penalties = []

        # Evidence is a bounded mix of accept rate, average meta score, and EV delta.
        evidence_score = 0.0
        evidence_score += 0.45 * row["accept_rate"]
        evidence_score += 0.35 * _clamp((row["avg_meta_score"] + 1.0) / 4.0)
        evidence_score += 0.20 * _clamp((row["sum_ev_delta"] / max_abs_ev + 1.0) / 2.0)
        evidence_score = _clamp(evidence_score)
        if row["accept_rate"] > 0.3:
            why.append("historically non-trivial accept rate")
        if row["sum_ev_delta"] > 0:
            why.append("positive cumulative EV delta in logs")
        if row["avg_meta_score"] > 0:
            why.append("positive average meta score")

        reproducibility_score, repro_why = _family_reproducibility(records, family)
        why.extend(repro_why)

        production_feasibility, prod_why = _family_production_feasibility(records, family)
        why.extend(prod_why)

        novelty_score, novelty_why, novelty_penalties = _family_novelty(records, family)
        why.extend(novelty_why)
        penalties.extend(novelty_penalties)

        risk_control_score, risk_why, risk_penalties = _family_risk_control(records, family)
        why.extend(risk_why)
        penalties.extend(risk_penalties)

        if family in freeze_names:
            penalties.append("freeze candidate: require new evidence before retry")
            novelty_score = min(novelty_score, 0.25)
            evidence_score = min(evidence_score, 0.35)

        priority = (
            PRIORITY_WEIGHTS["evidence_score"] * evidence_score
            + PRIORITY_WEIGHTS["reproducibility_score"] * reproducibility_score
            + PRIORITY_WEIGHTS["production_feasibility"] * production_feasibility
            + PRIORITY_WEIGHTS["novelty_score"] * novelty_score
            + PRIORITY_WEIGHTS["risk_control_score"] * risk_control_score
        )

        priorities.append({
            "family": family,
            "priority": round(priority, 4),
            "summary_zh": _priority_summary_zh(family, priority, row),
            "component_scores": {
                "evidence_score": round(evidence_score, 4),
                "reproducibility_score": round(reproducibility_score, 4),
                "production_feasibility": round(production_feasibility, 4),
                "novelty_score": round(novelty_score, 4),
                "risk_control_score": round(risk_control_score, 4),
            },
            "weights": dict(PRIORITY_WEIGHTS),
            "why": sorted(set(why)),
            "penalties": sorted(set(penalties)),
            "evidence_summary": row,
        })

    return sorted(priorities, key=lambda r: r["priority"], reverse=True)


def _has_decision_grade_strategy_evidence(priority_item):
    summary = priority_item["evidence_summary"]
    has_metric_evidence = (
        abs(summary["sum_ev_delta"]) >= 0.0001
        or abs(summary["sum_pnl_delta"]) >= 1.0
    )
    if not has_metric_evidence:
        return False
    return (
        summary["experiments"] >= 3
        or abs(summary["sum_ev_delta"]) >= 0.25
        or abs(summary["sum_pnl_delta"]) >= 5000.0
    )


def build_strategy_research_priorities(records):
    """Build the alpha-search queue separately from measurement/process work."""
    strategy_records = [r for r in records if is_strategy_iteration_record(r)]
    priorities = build_research_priorities(strategy_records)
    return [item for item in priorities if _has_decision_grade_strategy_evidence(item)]


def build_measurement_repair_priorities(records):
    """Build a separate queue for work that improves evaluation quality."""
    return build_research_priorities([r for r in records if is_measurement_repair_record(r)])


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
    priorities = build_research_priorities(records)
    recs = []
    if priorities:
        best = priorities[0]
        recs.append({
            "type": "continue_high_priority_family",
            "family": best["family"],
            "why": best["why"][:5],
            "priority": best["priority"],
            "component_scores": best["component_scores"],
        })
    elif by_family:
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


def build_chinese_explanation(
    strategy_research_priorities,
    measurement_repair_priorities,
    recommendations,
    data_quality_warnings,
):
    top_priorities = []
    for item in strategy_research_priorities[:5]:
        top_priorities.append({
            "family": item["family"],
            "family_zh": _family_label_zh(item["family"]),
            "priority": item["priority"],
            "summary": item["summary_zh"],
        })

    top_measurement = []
    for item in measurement_repair_priorities[:3]:
        top_measurement.append({
            "family": item["family"],
            "family_zh": _family_label_zh(item["family"]),
            "priority": item["priority"],
            "summary": item["summary_zh"],
        })

    top_recommendations = []
    for rec in recommendations[:5]:
        family = rec.get("family")
        if family:
            top_recommendations.append({
                "type": rec.get("type"),
                "family": family,
                "family_zh": _family_label_zh(family),
                "meaning": (
                    "继续优先研究这个方向"
                    if rec.get("type") == "continue_high_priority_family"
                    else "冻结或要求新证据后再重试"
                ),
            })

    metric_warning_count = data_quality_warnings.get(
        "non_dict_metric_buckets", {}
    ).get("count", 0)

    return {
        "一句话": (
            "这个报告是在复盘实验历史，帮助决定下一轮研究什么；"
            "它不是交易信号，也不会改变下单、排序或仓位。"
        ),
        "怎么读": [
            "策略迭代先看 strategy_research_priorities，不要用 measurement_repair_priorities 代替 alpha 搜索。",
            "research_priorities 是原始全量队列，包含测量修复和流程记录，只适合审计，不适合直接指导下一轮策略。",
            "recommendations 会把策略队列最高优先级和应该暂缓的方向翻译成行动建议。",
            "freeze_candidates 表示历史证据弱或失败较多，重试前需要新证据。",
            "top_experiments / worst_experiments 只是历史实验样例，不等于未来收益保证。",
            "data_quality_warnings 如果不为 0，说明有旧日志字段质量问题，排序可信度要打折。",
        ],
        "字段说明": {
            "priority": "研究队列优先级，范围大致在 0 到 1；只用于排研究顺序。",
            "evidence_score": "历史接受率、meta score 和 EV delta 的综合证据分。",
            "reproducibility_score": "多窗口、样本数、可复现实验记录的质量。",
            "production_feasibility": "是否容易进入生产/回测一致的共享路径。",
            "novelty_score": "是否还有新信息，是否只是重复扫旧参数。",
            "risk_control_score": "是否容易控制回撤、存活率和尾部风险。",
            "meta_score": "单个实验的粗略历史证据分，不是收益预测。",
        },
        "当前前五策略研究方向": top_priorities,
        "当前测量修复方向": top_measurement,
        "当前建议": top_recommendations,
        "数据质量提醒": (
            f"发现 {metric_warning_count} 个非字典 metrics 字段；"
            "已按缺失值处理，避免旧日志把报告跑崩。"
        ),
    }


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

    strategy_records = [r for r in records if is_strategy_iteration_record(r)]
    measurement_records = [r for r in records if is_measurement_repair_record(r)]

    research_priorities = build_research_priorities(records)
    strategy_research_priorities = build_strategy_research_priorities(records)
    measurement_repair_priorities = build_measurement_repair_priorities(records)
    by_family = _aggregate(records, classify_research_family)
    by_change_type = _aggregate(records, _change_type)
    by_component = _aggregate(records, _component)
    freeze_candidates = build_freeze_candidates(records)
    recommendations = build_recommendations(strategy_records)
    data_quality_warnings = build_data_quality_warnings(records)

    return {
        "schema_version": 3,
        "read_only": True,
        "records_loaded": len(records),
        "record_counts": {
            "strategy_iteration_records": len(strategy_records),
            "measurement_repair_records": len(measurement_records),
        },
        "priority_formula": {
            "formula": "0.35*evidence + 0.25*reproducibility + 0.20*production_feasibility + 0.10*novelty + 0.10*risk_control",
            "weights": PRIORITY_WEIGHTS,
            "note": "Research queue priority only; never used as trade sizing or signal ranking.",
        },
        "chinese_explanation": build_chinese_explanation(
            strategy_research_priorities,
            measurement_repair_priorities,
            recommendations,
            data_quality_warnings,
        ),
        "data_quality_warnings": data_quality_warnings,
        "strategy_research_priorities": strategy_research_priorities,
        "measurement_repair_priorities": measurement_repair_priorities,
        "research_priorities": research_priorities,
        "by_family": by_family,
        "by_change_type": by_change_type,
        "by_component": by_component,
        "top_experiments": sorted(scored, key=lambda r: r["meta_score"], reverse=True)[:20],
        "worst_experiments": sorted(scored, key=lambda r: r["meta_score"])[:20],
        "freeze_candidates": freeze_candidates,
        "recommendations": recommendations,
        "notes": [
            "This is a research-prior engine, not a trading signal.",
            "Scores are intentionally coarse and should guide what to test next, not what to trade.",
            "Priority scores are transparent fixed-formula audit values, not optimized or fit parameters.",
            "Low-quality or missing delta_metrics reduce precision; improve experiment logs before treating rankings as strong evidence.",
        ],
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
