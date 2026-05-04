from __future__ import annotations

from quant.experiments.exp_20260503_053_form4_owner_role_discriminator import (
    MIN_PURCHASE_VALUE,
    _base_event_matches,
    _select_best_role_variant,
    _variant_summary,
)


def _event(
    *,
    ticker: str = "ABC",
    window: str = "late_strong",
    value: float = MIN_PURCHASE_VALUE,
    meaningful: bool = True,
    director: bool = True,
    officer: bool = False,
    ceo_cfo: bool = False,
    owner_count: int = 1,
    gross_return: float = 5.0,
    excess_return: float = 3.0,
) -> dict:
    return {
        "ticker": ticker,
        "window": window,
        "usable_trade_date": "2025-11-03",
        "meaningful_purchase_v1": meaningful,
        "total_purchase_value": value,
        "any_director": director,
        "any_officer": officer,
        "any_ceo_cfo_or_president": ceo_cfo,
        "owner_count": owner_count,
        "outcomes": {
            "10": {
                "return_pct": gross_return,
                "excess_vs_spy_pct": excess_return,
            }
        },
    }


def test_base_event_matches_requires_meaningful_ge_500k() -> None:
    assert _base_event_matches(_event())
    assert not _base_event_matches(_event(value=499_999.0))
    assert not _base_event_matches(_event(meaningful=False, value=2_000_000.0))


def test_variant_summary_filters_role_predicate_after_base_filter() -> None:
    events = [
        _event(window="late_strong", ticker="AAA", director=True, officer=False, excess_return=1.0),
        _event(window="mid_weak", ticker="BBB", director=True, officer=True, excess_return=5.0),
        _event(window="old_thin", ticker="CCC", director=True, officer=False, excess_return=0.5),
        _event(window="old_thin", ticker="DDD", value=100_000.0, director=True, officer=False, excess_return=20.0),
    ]

    summary = _variant_summary(events, lambda event: event["any_director"] and not event["any_officer"])

    assert summary["aggregate"]["valid_event_count"] == 2
    assert summary["aggregate"]["positive_excess_windows"] == 2
    assert summary["aggregate"]["all_valid_windows_positive"] is False
    assert summary["by_window"]["mid_weak"]["valid_event_count"] == 0


def test_select_best_role_variant_ignores_baseline_variant() -> None:
    variants = {
        "baseline_ge500k_any_role": {
            "aggregate": {
                "all_valid_windows_positive": True,
                "avg_excess_vs_spy_pct": 10.0,
                "valid_event_count": 10,
            }
        },
        "role_a": {
            "aggregate": {
                "all_valid_windows_positive": True,
                "avg_excess_vs_spy_pct": 2.0,
                "valid_event_count": 3,
            }
        },
        "role_b": {
            "aggregate": {
                "all_valid_windows_positive": False,
                "avg_excess_vs_spy_pct": 8.0,
                "valid_event_count": 20,
            }
        },
    }

    assert _select_best_role_variant(variants) == "role_a"
