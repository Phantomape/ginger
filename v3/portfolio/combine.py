"""Fixed V3 portfolio rule (architecture doc section 2).

At each rebalance: every member strategy proposes weights; members are combined with
inverse-volatility (equal risk) weights, where a member's volatility is estimated from its
proposed weights and the trailing 252-day asset covariance.  Each asset is capped at 25%
(excess goes to cash), then the whole book is scaled toward a 10% volatility target.
No leverage: gross exposure never exceeds 100%.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluator"))
from engine import History  # noqa: E402

VOL_TARGET = 0.10
ASSET_CAP = 0.25
LOOKBACK = 252


def _vol(w: dict, cov: pd.DataFrame) -> float:
    if not w:
        return 0.0
    s = pd.Series(w)
    c = cov.loc[s.index, s.index].fillna(0.0)
    return math.sqrt(max(float(s @ c @ s), 0.0) * 252)


def portfolio_signal(members: list):
    """members: list of signal functions.  Returns a combined signal function."""

    def signal(hist: History) -> dict:
        cov = hist.returns.iloc[-LOOKBACK:].cov()
        proposals = [m(hist) for m in members]
        vols = [_vol(p, cov) for p in proposals]
        inv = [1 / v if v > 0 else 0.0 for v in vols]
        if sum(inv) == 0:
            return {}
        combined: dict = {}
        for p, a in zip(proposals, inv):
            for k, w in p.items():
                combined[k] = combined.get(k, 0.0) + w * a / sum(inv)
        combined = {k: min(w, ASSET_CAP) for k, w in combined.items() if w > 0}
        if not combined:
            return {}
        v = _vol(combined, cov)
        limit = min(1 / sum(combined.values()), ASSET_CAP / max(combined.values()))
        scale = min(VOL_TARGET / v, limit) if v > 0 else limit
        return {k: w * scale for k, w in combined.items()}

    return signal
