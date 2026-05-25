from datetime import date, timedelta

from quant.experiments.exp_20260525_032_volatility_contraction_volume_dryup import (
    VOLUME_DRYUP_RULE_VERSION,
    compute_pre_signal_volume_dryup_context,
)


def _volume_rows(volumes, *, start=date(2026, 1, 1)):
    rows = []
    for idx, volume in enumerate(volumes):
        close = 100.0 + idx
        rows.append(
            {
                "Date": (start + timedelta(days=idx)).isoformat(),
                "Open": close,
                "High": close * 1.01,
                "Low": close * 0.99,
                "Close": close,
                "Volume": volume,
            }
        )
    return rows


def test_volume_dryup_passes_when_prior_10_avg_is_low_vs_prior_50():
    rows = _volume_rows([100.0] * 40 + [50.0] * 10 + [1000.0])

    context = compute_pre_signal_volume_dryup_context(rows, rows[50]["Date"])

    assert context["pre_signal_volume_dryup_rule_version"] == VOLUME_DRYUP_RULE_VERSION
    assert context["pre_signal_volume_dryup_ratio_10v50"] == 0.555556
    assert context["pre_signal_volume_dryup_passed"] is True
    assert context["volume_dryup_status"] == "available"
    assert context["trade_enabled"] is False
    assert context["alters_orders"] is False


def test_volume_dryup_fails_when_prior_10_avg_is_not_low_enough():
    rows = _volume_rows([100.0] * 40 + [90.0] * 10 + [1000.0])

    context = compute_pre_signal_volume_dryup_context(rows, rows[50]["Date"])

    assert context["pre_signal_volume_dryup_ratio_10v50"] == 0.918367
    assert context["pre_signal_volume_dryup_passed"] is False
    assert context["volume_dryup_status"] == "available"


def test_volume_dryup_excludes_signal_day_volume():
    rows = _volume_rows([100.0] * 40 + [50.0] * 10 + [10_000.0])

    context = compute_pre_signal_volume_dryup_context(rows, rows[50]["Date"])

    assert context["pre_signal_volume_dryup_ratio_10v50"] == 0.555556
    assert context["pre_signal_volume_dryup_passed"] is True


def test_volume_dryup_does_not_inspect_future_rows():
    rows = _volume_rows([100.0] * 40 + [90.0] * 10 + [1000.0] + [1.0] * 20)

    context = compute_pre_signal_volume_dryup_context(rows, rows[50]["Date"])

    assert context["pre_signal_volume_dryup_ratio_10v50"] == 0.918367
    assert context["pre_signal_volume_dryup_passed"] is False


def test_volume_dryup_insufficient_history_is_unavailable_false():
    rows = _volume_rows([100.0] * 49)

    context = compute_pre_signal_volume_dryup_context(rows, rows[48]["Date"])

    assert context["pre_signal_volume_dryup_ratio_10v50"] is None
    assert context["pre_signal_volume_dryup_passed"] is False
    assert context["volume_dryup_status"] == "insufficient_history"


def test_volume_dryup_missing_or_zero_volume_is_unavailable_false():
    rows = _volume_rows([100.0] * 50 + [1000.0])
    rows[42]["Volume"] = 0

    context = compute_pre_signal_volume_dryup_context(rows, rows[50]["Date"])

    assert context["pre_signal_volume_dryup_ratio_10v50"] is None
    assert context["pre_signal_volume_dryup_passed"] is False
    assert context["volume_dryup_status"] == "insufficient_valid_volume_history"
