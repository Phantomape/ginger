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
