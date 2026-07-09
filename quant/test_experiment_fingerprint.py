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
        ("Moomoo borrow availability readiness gate", "borrow_availability"),
        ("daily non-OHLCV borrow_availability forward collection", "borrow_availability"),
        ("short_sell_rate_pct and short_available_volume sidecar rows", "borrow_availability"),
        ("ORTEX borrow fee sidecar readiness gate", "ortex_borrow"),
        ("ORTEX short-interest sidecar readiness with utilization and loan availability", "ortex_borrow"),
        ("space_catalyst event state shadow ledger", "space_catalyst"),
        ("space catalyst observation slot forward supply", "space_catalyst"),
        ("space_catalyst_event_ledger closed decision attribution", "space_catalyst"),
        ("chop_forward_observer daily wiring", "chop_forward_observer"),
        ("future chop forward-row reopen checks", "chop_forward_observer"),
        ("chop-labeled forward rows accrue", "chop_forward_observer"),
        ("CISA KEV entry risk gate", "cisa_kev"),
        ("live drift reconciliation fill drift monitor", "live_drift_reconciliation"),
        ("prediction-market event odds observer", "prediction_market_event"),
        ("intraday structured news relation observer", "intraday_structured_news"),
        ("intraday_news_structured_event forward observation", "intraday_structured_news"),
        ("intraday trade news target relation quality", "intraday_structured_news"),
        ("intraday structured relation quality short horizon read", "intraday_structured_news"),
        ("intraday advisory shadow action forward outcome", "intraday_advisory"),
        ("primary advisory shadow action risk-review attribution", "intraday_advisory"),
        ("news_event_exposure observer daily pipeline wiring", "news_event_exposure"),
        ("news event second-order exposure attribution", "news_event_exposure"),
        ("news_second_order negative top1 candidate source", "news_event_exposure"),
        ("portfolio covariance daily mark-to-market overlay", "portfolio_covariance_lane"),
        ("vol_normalized_tick size microstructure viability attribution", "microstructure_viability"),
        ("core_entry_admission_gate severe haircut no-entry saved trade diagnostic", "core_entry_admission"),
        ("core high-vol high-beta admission overlay saved-trade counterfactual", "core_entry_admission"),
        ("chop pair-spread long-short market-neutral zscore entry sleeve", "relative_value_spread"),
        ("relative_value_spread pair_zscore spread entry probe", "relative_value_spread"),
        ("cointegrated pair spread sleeve", "relative_value_spread"),
        ("forward replacement value entry_exhaustion attribution", "forward_replacement_value"),
        ("pilot_scorecard kill graduate readiness", "pilot_scorecard"),
        ("SEC cover-page filer-status upgrade candidate pool", "sec_filer_status"),
        ("10-K/10-Q DEI cover status materialization audit", "sec_filer_status"),
        ("sec_periodic_historical_dei_status_materialization", "sec_filer_status"),
        ("sec_periodic_cover_xbrl_doc_priority", "sec_filer_status"),
        ("large accelerated filer transition parser", "sec_filer_status"),
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
    assert fp.infer_fingerprint("short_interest_borrow_pressure_overlay")["data_source"] == "finra_short_interest"


def test_borrow_and_ortex_sources_precede_generic_finra_borrow_keyword():
    assert fp.infer_fingerprint("moomoo_borrow_availability_readiness_gate")["data_source"] == "borrow_availability"
    assert fp.infer_fingerprint("daily_non_ohlcv_borrow_availability_forward_collection")["data_source"] == "borrow_availability"
    assert fp.infer_fingerprint("ortex_borrow_fee_sidecar_readiness_gate")["data_source"] == "ortex_borrow"
    assert fp.infer_fingerprint("ortex_short_interest_sidecar_readiness_gate")["data_source"] == "ortex_borrow"


def test_space_catalyst_precedes_generic_forward_replacement_value():
    fingerprint = fp.infer_fingerprint(
        "space_catalyst_event_state_shadow forward replacement attribution rows"
    )

    assert fingerprint["data_source"] == "space_catalyst"
    assert fingerprint["gate_shape"] == "forward_attribution"


def test_chop_forward_observer_precedes_core_admission_and_regime_chop():
    fingerprint = fp.infer_fingerprint(
        "Repair novelty fingerprint coverage so chop forward observer wiring "
        "and future chop forward-row reopen checks classify away from "
        "core_entry_admission / entry_admission."
    )

    assert fingerprint["data_source"] == "chop_forward_observer"
    assert fingerprint["gate_shape"] == "forward_observer"


def test_chop_forward_observer_does_not_capture_other_chop_surfaces():
    assert fp.infer_fingerprint(
        "chop pair-spread long-short market-neutral zscore entry sleeve"
    )["data_source"] == "relative_value_spread"
    assert fp.infer_fingerprint("regime chop daily breadth wiring")["data_source"] == "regime_state"


def test_intraday_structured_news_precedes_generic_relation_and_news_sources():
    assert fp.infer_fingerprint("intraday structured news relation observer")["data_source"] == "intraday_structured_news"
    assert fp.infer_fingerprint("entity-theme news relation observer")["data_source"] == "entity_theme_news"
    assert fp.infer_fingerprint("lead_lag peer rolling_corr relation candidate pool")["data_source"] == "ohlcv_relation"


def test_intraday_advisory_is_not_structured_news_or_other():
    fingerprint = fp.infer_fingerprint(
        "Post-exp024 intraday primary advisory shadow actions may identify "
        "existing positions with worse next-1d and next-3d returns than OK/no-action "
        "positions under a fixed forward attribution recipe"
    )

    assert fingerprint["data_source"] == "intraday_advisory"
    assert fingerprint["gate_shape"] == "forward_attribution"


def test_news_event_exposure_precedes_generic_relation_without_overmatching():
    assert fp.infer_fingerprint("news_event_exposure observer daily pipeline")["data_source"] == "news_event_exposure"
    assert fp.infer_fingerprint("news second order exposure attribution")["data_source"] == "news_event_exposure"
    assert fp.infer_fingerprint("entity-theme news relation observer")["data_source"] == "entity_theme_news"
    assert fp.infer_fingerprint("intraday structured news relation observer")["data_source"] == "intraday_structured_news"
    assert fp.infer_fingerprint("lead_lag peer rolling_corr relation candidate pool")["data_source"] == "ohlcv_relation"
    assert fp.infer_fingerprint("thematic second order supply chain candidate pool")["data_source"] == "other"


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


def test_core_entry_admission_gate_shape_and_source():
    fingerprint = fp.infer_fingerprint(
        "core_entry_admission_gate saved-trade counterfactual severe haircut "
        "pre-entry no-entry admission diagnostic"
    )

    assert fingerprint["data_source"] == "core_entry_admission"
    assert fingerprint["gate_shape"] == "entry_admission"


def test_core_entry_admission_precedes_generic_ohlcv_momentum():
    fingerprint = fp.infer_fingerprint(
        "core high-vol high-beta admission overlay for crowded momentum entries"
    )

    assert fingerprint["data_source"] == "core_entry_admission"
    assert fingerprint["gate_shape"] == "entry_admission"


def test_microstructure_admission_still_uses_microstructure_source():
    fingerprint = fp.infer_fingerprint(
        "microstructure tick_to_atr admission gate vol_normalized_tick"
    )

    assert fingerprint["data_source"] == "microstructure_viability"
    assert fingerprint["gate_shape"] == "microstructure_attribution"


def test_pair_spread_surface_precedes_generic_chop_and_notional():
    fingerprint = fp.infer_fingerprint(
        "chop pair-spread long-short market-neutral zscore entry sleeve "
        "with notional cap"
    )

    assert fingerprint["data_source"] == "relative_value_spread"
    assert fingerprint["gate_shape"] == "pair_spread"


def test_microstructure_spread_to_atr_is_not_pair_spread():
    fingerprint = fp.infer_fingerprint(
        "microstructure spread_to_atr tick_to_atr viability attribution"
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


def test_sec_filer_status_precedes_generic_sec_text_event():
    fingerprint = fp.infer_fingerprint(
        "sec_cover_page_filer_status_upgrade_candidate_pool "
        "sec_cover_page_filer_status_upgrade_candidate_source_v1"
    )

    assert fingerprint["data_source"] == "sec_filer_status"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"


def test_generic_sec_text_event_still_resolves_to_sec_text_event():
    fingerprint = fp.infer_fingerprint(
        "SEC 8-K item 3.01 listing noncompliance entry risk"
    )

    assert fingerprint["data_source"] == "sec_text_event"
