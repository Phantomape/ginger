import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("deep-drawdown observer capitulation probe", "deep_drawdown"),
        ("entity-theme news relation observer", "entity_theme_news"),
        ("FINRA OTC internalization retreat candidate pool", "finra_otc_internalization"),
        ("FINRA ATS weekly dark share candidate pool", "finra_ats_share"),
        ("Moomoo capital-flow accumulation source", "moomoo_capital_flow"),
        ("Moomoo daily short volume activity helper", "moomoo_short_volume"),
        ("CISA KEV entry risk gate", "cisa_kev"),
        ("live drift reconciliation fill drift monitor", "live_drift_reconciliation"),
        ("prediction-market event odds observer", "prediction_market_event"),
        ("portfolio covariance daily mark-to-market overlay", "portfolio_covariance_lane"),
        ("vol_normalized_tick size microstructure viability attribution", "microstructure_viability"),
        ("forward replacement value entry_exhaustion attribution", "forward_replacement_value"),
        ("pilot_scorecard kill graduate readiness", "pilot_scorecard"),
    ],
)
def test_july_surface_keywords_have_specific_data_source(text, expected):
    assert fp.infer_fingerprint(text)["data_source"] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("FINRA short_interest days_to_cover candidate pool", "finra_short_interest"),
        ("Form 4 insider open-market purchase", "form4_insider"),
        ("SEC 13F institutional sponsorship holder signal", "sec13f_ownership"),
        ("SEC Companyfacts free cash flow margin quality", "companyfacts_ratio"),
    ],
)
def test_existing_source_mappings_still_resolve(text, expected):
    assert fp.infer_fingerprint(text)["data_source"] == expected


def test_specific_finra_surfaces_precede_generic_short_interest():
    assert fp.infer_fingerprint("FINRA OTC internalization retreat")["data_source"] == "finra_otc_internalization"
    assert fp.infer_fingerprint("FINRA ATS dark pool share")["data_source"] == "finra_ats_share"
    assert fp.infer_fingerprint("FINRA short interest borrow days to cover")["data_source"] == "finra_short_interest"


def test_portfolio_covariance_daily_equity_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "portfolio covariance lane fixed-asset turnover daily mark-to-market overlay"
    )

    assert fingerprint["data_source"] == "portfolio_covariance_lane"
    assert fingerprint["gate_shape"] == "portfolio_daily_equity_overlay"


def test_microstructure_viability_attribution_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "tick_to_atr vol_normalized_tick microstructure viability attribution"
    )

    assert fingerprint["data_source"] == "microstructure_viability"
    assert fingerprint["gate_shape"] == "microstructure_attribution"


def test_forward_replacement_value_attribution_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "forward replacement value entry_exhaustion settled forward attribution"
    )

    assert fingerprint["data_source"] == "forward_replacement_value"
    assert fingerprint["gate_shape"] == "forward_attribution"


def test_pilot_scorecard_readiness_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "pilot scorecard kill rule readiness with graduation_readiness rows"
    )

    assert fingerprint["data_source"] == "pilot_scorecard"
    assert fingerprint["gate_shape"] == "pilot_scorecard_readiness"
