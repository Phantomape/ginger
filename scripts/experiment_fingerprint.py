"""Coarse, transparent decision-fingerprint + near-neighbor distance.

Advisory only. Used by build_frozen_families.py and check_experiment_novelty.py
to flag when a proposed experiment is a near-neighbor of a frozen/rejected
family. Heuristic and tunable on purpose: this is the warn-only calibration
layer described in the experiment-mechanism review, NOT a hard gate. No ML, no
external deps, fully deterministic so it can later be imported by
scripts/experiment.py.
"""

from __future__ import annotations

import re
from typing import Any

# Ordered: first matching source wins. Keep specific before generic.
_DATA_SOURCE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # Kova snapshot rows are their own population: probes on the same Kova
    # current-row batch must share one machine key (the observed-only streak
    # gate counts per data_source), and they are not the canonical SEC13F/
    # rs-proxy surfaces even when the joined field comes from those.
    ("kova_snapshot", ("kova",)),
    # Keep newer source-specific surfaces above their generic parents so the
    # saturation guards count the actual population under test.
    ("finra_otc_internalization", (
        "finra_otc", "finra otc", "otc_internalization", "non_ats", "non-ats", "internalization",
    )),
    ("finra_ats_share", (
        "finra_ats", "finra ats", "ats_share", "weekly_dark_share", "dark_share", "dark share",
        "dark_pool", "dark pool",
    )),
    ("moomoo_short_volume", (
        "moomoo_short_volume", "moomoo_daily_short_volume", "moomoo daily short volume",
        "daily_short_volume", "daily short volume", "short_volume_activity", "short volume activity",
    )),
    ("moomoo_capital_flow", (
        "moomoo_capital_flow", "moomoo capital flow", "capital_flow", "capital-flow", "fund_flow",
        "large_order_flow",
    )),
    ("forward_replacement_value", (
        "forward_replacement", "forward replacement", "forward_replacement_value",
        "replacement_value", "replacement value", "settled forward", "closed forward",
        "entry_exhaustion", "entry exhaustion", "entry_regime", "entry regime",
    )),
    ("cisa_kev", ("cisa_kev", "cisa", "kev", "known_exploited_vulnerabilities")),
    ("prediction_market_event", (
        "prediction_market", "prediction-market", "prediction market", "kalshi", "polymarket",
        "event_odds", "event odds",
    )),
    ("entity_theme_news", ("entity_theme", "entity-theme", "entity theme", "theme_news", "news_theme", "event_theme")),
    ("live_drift_reconciliation", ("live_drift", "live drift", "fill_drift", "trajectory_drift", "live_reconciliation")),
    ("pilot_scorecard", (
        "pilot_scorecard", "pilot scorecard", "pilot_recommendations", "pilot recommendations",
        "scorecard_kill", "scorecard kill", "kill_rule_readiness", "kill rule readiness",
        "graduation_readiness", "graduation readiness", "graduate_rule", "graduate rule",
    )),
    ("portfolio_covariance_lane", (
        "portfolio_covariance", "portfolio covariance", "portfolio-lane", "portfolio lane",
        "daily_equity_overlay", "daily equity overlay", "mark_to_market", "mark-to-market",
        "daily mark to market", "mtm_overlay", "mtm overlay",
    )),
    ("microstructure_viability", (
        "microstructure_viability", "microstructure viability", "vol_normalized_tick",
        "vol-normalized tick", "tick_to_atr", "tick-to-atr", "tick_size_atr",
        "tick size atr", "small_tick", "small tick", "spread_to_atr", "spread-to-atr",
        "impact_reinforcement", "impact reinforcement",
    )),
    ("deep_drawdown", ("deep_drawdown", "deep-drawdown", "deep drawdown", "drawdown_capitulation", "drawdown_breadth", "capitulation_breadth")),
    ("finra_short_interest", ("finra", "short_interest", "shortinterest", "borrow", "days_to_cover", "dtc")),
    ("form4_insider", ("form4", "form_4", "insider")),
    ("sec13f_ownership", ("13f", "sec13f", "sponsorship", "holder")),
    ("filing_timeliness", ("timeliness", "filing_lag", "early_disclosure", "filing_recency", "recency", "disclosure_timing")),
    ("sec_text_event", ("sec_text", "8k", "item", "filing_text", "contract_economics", "backlog", "rpo", "guidance", "narrative", "complexity", "submissions")),
    ("companyfacts_ratio", (
        "companyfacts", "sbc", "accrual", "accruals", "capex", "depreciation", "amortization",
        "inventory", "dso", "dio", "dpo", "margin", "liability", "gross_profit", "cash_conversion",
        "warranty", "pension", "aoci", "deferred_tax", "impairment", "lease", "debt", "asset_growth",
        "operating_leverage", "reinvestment", "fundamental_growth", "rd_intensity", "working_capital",
        "receivable", "buyback", "shareholder_yield", "dilution", "free_cash_flow", "fcf",
    )),
    ("revision_expectation", ("revision", "estimate", "analyst", "surprise", "pead", "expectation")),
    ("allocator", ("allocator", "source_priority", "consensus")),
    ("regime_state", ("regime", "chop", "state_surface", "tail_state", "market_state")),
    ("ohlcv_relation", (
        "lead_lag", "leadlag", "peer", "laggard", "rolling_corr", "correlation", "industry_relative",
        "industry_stable", "industry_downshock", "macro_relief", "volatility_relief", "distribution",
        "compression", "breakout", "gap", "pocket_pivot", "reversal", "thrust", "breadth",
        "52_week", "fifty_two", "fiftytwo", "turn_of_month", "calendar", "relation", "core_flow",
    )),
    ("ohlcv_momentum", ("momentum", "winner", "continuation", "extension", "alpha_score", "rs20")),
]

_GATE_SHAPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("microstructure_attribution", (
        "microstructure_viability", "microstructure viability", "vol_normalized_tick",
        "vol-normalized tick", "tick_to_atr", "tick-to-atr", "tick_size_atr",
        "tick size atr", "spread_to_atr", "spread-to-atr",
    )),
    ("portfolio_daily_equity_overlay", (
        "portfolio_covariance", "portfolio covariance", "daily_equity_overlay",
        "daily equity overlay", "mark_to_market", "mark-to-market",
        "daily mark to market", "mtm_overlay", "mtm overlay",
    )),
    ("forward_attribution", (
        "forward_attribution", "forward attribution", "forward_replacement",
        "forward replacement", "replacement_value", "replacement value",
        "settled forward", "closed forward", "entry_exhaustion", "entry exhaustion",
    )),
    ("pilot_scorecard_readiness", (
        "pilot_scorecard", "pilot scorecard", "pilot_recommendations", "pilot recommendations",
        "graduation_readiness", "graduation readiness", "kill_rule_readiness",
        "kill rule readiness", "scorecard_kill", "scorecard kill", "graduate_rule",
        "graduate rule",
    )),
    ("allocator_source", ("allocator", "source_priority", "source_extension", "rank")),
    ("notional_scalar", ("notional", "scalar", "support", "top_up", "topup", "cap_release", "position_cap")),
    ("candidate_pool_top1_10d", ("candidate_pool", "candidate", "top1", "candidate_selection")),
]

_STOPWORDS = {
    "candidate", "pool", "source", "v1", "v2", "v3", "scout", "paper", "default", "off",
    "shared", "adapter", "top1", "next", "open", "10d", "day", "days", "replay", "the", "vs",
    "and", "for", "with", "candidate_pool", "selection", "broad", "universe", "free", "sec",
    "ohlcv", "production", "visible", "fixed", "improvement", "relief", "quality",
}


def _tokens(text: str) -> list[str]:
    raw = re.split(r"[^a-z0-9]+", str(text or "").lower())
    return [t for t in raw if t and t not in _STOPWORDS and not t.isdigit()]


def infer_fingerprint(*texts: str) -> dict[str, Any]:
    """Infer {data_source, field_tags, gate_shape} from family/variable strings."""
    blob = " ".join(str(t or "") for t in texts).lower()
    data_source = "other"
    for source, kws in _DATA_SOURCE_KEYWORDS:
        if any(kw in blob for kw in kws):
            data_source = source
            break
    gate_shape = "other"
    for shape, kws in _GATE_SHAPE_KEYWORDS:
        if any(kw in blob for kw in kws):
            gate_shape = shape
            break
    tags = sorted(set(_tokens(blob)))
    return {"data_source": data_source, "field_tags": tags, "gate_shape": gate_shape}


def distance(fp_a: dict[str, Any], fp_b: dict[str, Any]) -> float:
    """Similarity in [0,1]; higher = closer (more likely a near-neighbor).

    The catch-all "other" value is NOT treated as a shared source/shape: two
    unclassified items matching on "other" carries no information, so it must
    not inflate the score (otherwise every unclassified idea looks like a
    near-neighbor of every other one).
    """
    sa, sb = fp_a.get("data_source"), fp_b.get("data_source")
    ds = 1.0 if (sa == sb and sa not in (None, "other")) else 0.0
    a = set(fp_a.get("field_tags") or [])
    b = set(fp_b.get("field_tags") or [])
    jac = (len(a & b) / len(a | b)) if (a or b) else 0.0
    ga, gb = fp_a.get("gate_shape"), fp_b.get("gate_shape")
    gs = 1.0 if (ga == gb and ga not in (None, "other")) else 0.0
    return round(0.45 * ds + 0.40 * jac + 0.15 * gs, 4)


# Score >= this against a frozen/rejected family => emit a near-neighbor warning.
WARN_THRESHOLD = 0.55
