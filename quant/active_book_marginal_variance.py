"""Pure helpers for the active-book marginal-variance sizing overlay.

The policy deliberately uses only point-in-time close returns and current
market-value notionals.  It does not select, rank, or exclude candidates: it
returns a continuous scalar that callers may apply to an already-sized entry.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from typing import Any


LOOKBACK_RETURNS = 60


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean_series(values: Mapping[Hashable, Any]) -> dict[Hashable, float]:
    cleaned: dict[Hashable, float] = {}
    for key, value in values.items():
        number = _finite(value)
        if number is not None:
            cleaned[key] = number
    return cleaned


def sample_covariance(left: Sequence[float], right: Sequence[float]) -> float:
    """Return unbiased sample covariance for two aligned finite sequences."""
    if len(left) != len(right):
        raise ValueError("sample covariance requires equal-length inputs")
    if len(left) < 2:
        raise ValueError("sample covariance requires at least two observations")
    if any(_finite(value) is None for value in (*left, *right)):
        raise ValueError("sample covariance requires finite inputs")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    return sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    ) / (len(left) - 1)


def evaluate_active_book_marginal_variance(
    candidate_returns_by_date: Mapping[Hashable, Any],
    candidate_notional_usd: float,
    active_positions: Sequence[Mapping[str, Any]],
    *,
    lookback: int = LOOKBACK_RETURNS,
) -> dict[str, Any]:
    """Evaluate the fixed raw-return covariance policy.

    Each active-position mapping must contain ``ticker``, ``notional_usd``,
    and ``returns_by_date``.  All inputs are aligned on their joint last
    ``lookback`` dates.  If the joint PIT history is incomplete the policy
    fails open with scalar 1.0.

    With candidate standalone variance contribution ``S`` and signed
    cross-covariance contribution ``C``::

        S = n0^2 * Var(candidate)
        C = 2 * n0 * sum(ni * Cov(candidate, active_i))

    the preregistered scalar is 1 when C <= 0, otherwise the positive root
    ``(-C + sqrt(C^2 + 4*S^2)) / (2*S)``.
    """
    if not isinstance(lookback, int) or lookback < 2:
        raise ValueError("lookback must be an integer >= 2")

    candidate_notional = _finite(candidate_notional_usd)
    if candidate_notional is None or candidate_notional <= 0:
        return _result("invalid_candidate_notional")
    if not active_positions:
        return _result("no_active_book")

    candidate = _clean_series(candidate_returns_by_date)
    cleaned_positions: list[dict[str, Any]] = []
    for position in active_positions:
        notional = _finite(position.get("notional_usd"))
        returns = position.get("returns_by_date")
        if notional is None or notional <= 0 or not isinstance(returns, Mapping):
            return _result("invalid_active_position")
        cleaned_positions.append(
            {
                "ticker": str(position.get("ticker") or "").upper(),
                "notional_usd": notional,
                "returns": _clean_series(returns),
            }
        )

    common_dates = set(candidate)
    for position in cleaned_positions:
        common_dates.intersection_update(position["returns"])
    try:
        aligned_dates = sorted(common_dates)[-lookback:]
    except TypeError:
        # Mixed, incomparable key types are an invalid alignment contract.
        return _result("invalid_date_alignment")
    if len(aligned_dates) < lookback:
        return _result(
            "insufficient_joint_history",
            joint_history_count=len(aligned_dates),
            required_history_count=lookback,
        )

    candidate_values = [candidate[day] for day in aligned_dates]
    candidate_variance = sample_covariance(candidate_values, candidate_values)
    standalone_variance = candidate_notional * candidate_notional * candidate_variance
    if not math.isfinite(standalone_variance) or standalone_variance <= 0:
        return _result(
            "zero_candidate_variance",
            joint_history_count=len(aligned_dates),
            required_history_count=lookback,
            candidate_variance=candidate_variance,
            standalone_variance=standalone_variance,
            aligned_start=str(aligned_dates[0]),
            aligned_end=str(aligned_dates[-1]),
        )

    contributions: list[dict[str, Any]] = []
    weighted_covariance_sum = 0.0
    for position in cleaned_positions:
        active_values = [position["returns"][day] for day in aligned_dates]
        covariance = sample_covariance(candidate_values, active_values)
        weighted = position["notional_usd"] * covariance
        weighted_covariance_sum += weighted
        contributions.append(
            {
                "ticker": position["ticker"],
                "notional_usd": position["notional_usd"],
                "covariance": covariance,
                "notional_weighted_covariance": weighted,
            }
        )

    cross_covariance = 2.0 * candidate_notional * weighted_covariance_sum
    if not math.isfinite(cross_covariance):
        return _result("invalid_cross_covariance")

    if cross_covariance <= 0:
        status = "nonpositive_cross_covariance"
        scalar = 1.0
    else:
        status = "applied"
        discriminant = (
            cross_covariance * cross_covariance
            + 4.0 * standalone_variance * standalone_variance
        )
        scalar = (
            -cross_covariance + math.sqrt(discriminant)
        ) / (2.0 * standalone_variance)
        scalar = min(1.0, max(0.0, scalar))

    active_notional = sum(row["notional_usd"] for row in contributions)
    return _result(
        status,
        scalar=scalar,
        joint_history_count=len(aligned_dates),
        required_history_count=lookback,
        aligned_start=str(aligned_dates[0]),
        aligned_end=str(aligned_dates[-1]),
        candidate_notional_usd=candidate_notional,
        active_notional_usd=active_notional,
        candidate_variance=candidate_variance,
        standalone_variance=standalone_variance,
        weighted_covariance_sum=weighted_covariance_sum,
        cross_covariance=cross_covariance,
        active_positions=contributions,
    )


def _result(status: str, *, scalar: float = 1.0, **values: Any) -> dict[str, Any]:
    return {
        "status": status,
        "scalar": scalar,
        "lookback_returns": values.pop(
            "required_history_count", LOOKBACK_RETURNS
        ),
        **values,
    }


def apply_scalar_to_sizing(
    sizing: Mapping[str, Any],
    scalar: float,
    *,
    minimum_shares: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copied sizing payload with the scalar applied to whole shares.

    The realized scalar is based on integer shares.  A positive candidate is
    kept at a minimum of one share so this continuous allocator does not become
    an implicit entry exclusion gate.
    """
    requested_scalar = _finite(scalar)
    if requested_scalar is None or requested_scalar < 0:
        raise ValueError("scalar must be finite and nonnegative")
    if not isinstance(minimum_shares, int) or minimum_shares < 0:
        raise ValueError("minimum_shares must be a nonnegative integer")

    updated = dict(sizing)
    raw_shares = _finite(sizing.get("shares_to_buy"))
    if raw_shares is None or raw_shares <= 0:
        audit = {
            "status": "no_positive_shares",
            "requested_scalar": requested_scalar,
            "realized_scalar": 1.0,
            "baseline_shares": sizing.get("shares_to_buy"),
            "scaled_shares": sizing.get("shares_to_buy"),
        }
        return updated, audit

    baseline_shares = int(raw_shares)
    scaled_shares = int(math.floor(baseline_shares * min(1.0, requested_scalar)))
    scaled_shares = max(minimum_shares, scaled_shares)
    scaled_shares = min(baseline_shares, scaled_shares)
    realized_scalar = scaled_shares / baseline_shares

    updated["shares_to_buy"] = scaled_shares
    for field in (
        "position_value_usd",
        "position_pct_of_portfolio",
        "risk_amount_usd",
        "risk_pct",
        "risk_pct_after",
    ):
        value = _finite(sizing.get(field))
        if value is not None:
            updated[field] = value * realized_scalar
    updated["active_book_marginal_variance_scalar"] = realized_scalar
    updated["active_book_marginal_variance_requested_scalar"] = requested_scalar
    updated["active_book_marginal_variance_baseline_shares"] = baseline_shares

    audit = {
        "status": "applied" if scaled_shares < baseline_shares else "unchanged",
        "requested_scalar": requested_scalar,
        "realized_scalar": realized_scalar,
        "baseline_shares": baseline_shares,
        "scaled_shares": scaled_shares,
        "minimum_shares": minimum_shares,
    }
    return updated, audit
