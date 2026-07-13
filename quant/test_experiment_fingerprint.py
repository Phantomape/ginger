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
        ("session semivariance overnight-versus-intraday attribution", "ohlcv_relation"),
        ("intraindustry transfer entropy directional edge", "ohlcv_relation"),
        ("broker-authoritative execution fact ledger", "moomoo_execution_history"),
        ("Moomoo broker deal history order fee snapshots", "moomoo_execution_history"),
        ("Moomoo borrow availability readiness gate", "borrow_availability"),
        ("daily non-OHLCV borrow_availability forward collection", "borrow_availability"),
        ("short_sell_rate_pct and short_available_volume sidecar rows", "borrow_availability"),
        ("ORTEX borrow fee sidecar readiness gate", "ortex_borrow"),
        ("ORTEX short-interest sidecar readiness with utilization and loan availability", "ortex_borrow"),
        ("iBorrowDesk IBKR shortable stock daily archive avoidance context", "ortex_borrow"),
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
        ("GDELT 2.0 DOC timelinetone timelinevolraw news tone archive", "gdelt_news_tone"),
        ("gdelt_news_tone company news tone_shock archive coverage", "gdelt_news_tone"),
        ("exit_lifecycle_shadow_log daily position lifecycle rows", "exit_lifecycle"),
        ("exit advisory lifecycle breach_status forward attribution", "exit_lifecycle"),
        ("has_advisory_event trailing_stop_from_hwm position lifecycle", "exit_lifecycle"),
        ("live_position_control source_signal_rejected_alpha risk bucket", "live_position_control"),
        ("rejected-source live mirror position control ledger", "live_position_control"),
        ("portfolio covariance daily mark-to-market overlay", "portfolio_covariance_lane"),
        ("vol_normalized_tick size microstructure viability attribution", "microstructure_viability"),
        ("core_entry_admission_gate severe haircut no-entry saved trade diagnostic", "core_entry_admission"),
        ("core high-vol high-beta admission overlay saved-trade counterfactual", "core_entry_admission"),
        ("chop pair-spread long-short market-neutral zscore entry sleeve", "relative_value_spread"),
        ("relative_value_spread pair_zscore spread entry probe", "relative_value_spread"),
        ("cointegrated pair spread sleeve", "relative_value_spread"),
        ("forward replacement value entry_exhaustion attribution", "forward_replacement_value"),
        ("pilot_scorecard kill graduate readiness", "pilot_scorecard"),
        ("candidate_meta_label_v1 training table readiness audit", "candidate_meta_label"),
        ("candidate meta-labeling model_readiness gate", "candidate_meta_label"),
        ("SEC cover-page filer-status upgrade candidate pool", "sec_filer_status"),
        ("10-K/10-Q DEI cover status materialization audit", "sec_filer_status"),
        ("sec_periodic_historical_dei_status_materialization", "sec_filer_status"),
        ("sec_periodic_cover_xbrl_doc_priority", "sec_filer_status"),
        ("large accelerated filer transition parser", "sec_filer_status"),
        ("parsed SEC 13D Item-4 campaign-provenance board appointment candidate pool", "sec13d_ownership"),
        ("SEC 13D/13G holder stake action readiness", "sec13d_ownership"),
        ("Schedule 13D Item4 governance terms candidate pool", "sec13d_ownership"),
        ("sec_filing_features source_credibility_bucket forward attribution", "sec_filing_features"),
        ("sec_filing_text_plus_companyfacts predictability mosaic source", "sec_filing_features"),
        ("SEC filing feature mosaic low volume predictability bucket", "sec_filing_features"),
        ("SEC Item 1.01 contract-relation provenance surface", "sec_contract_relation"),
        ("sec_contract_relation_provenance daily source key", "sec_contract_relation"),
        ("SEC item101 contract relation public-counterparty target", "sec_contract_relation"),
        ("CIK-linked customer-supplier graph for Item 1.01 rows", "sec_contract_relation"),
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


def test_cftc_tff_positioning_precedes_generic_ranking_and_ohlcv_sources():
    fingerprint = fp.infer_fingerprint(
        "CFTC TFF Traders in Financial Futures institutional positioning "
        "scarce-slot ranking against an OHLCV relation"
    )

    assert fingerprint["data_source"] == "cftc_tff_positioning"
    assert fingerprint["gate_shape"] == "allocator_source"
    assert fp.infer_fingerprint(
        "fut_fin_txt Asset_Mgr_Positions versus Lev_Money_Positions rank"
    )["data_source"] == "cftc_tff_positioning"
    assert fp.infer_fingerprint(
        "cftc_tff_equity_index_asset_manager_positioning"
    )["data_source"] == "cftc_tff_positioning"


def test_wikimedia_pageviews_precedes_revision_attention_and_news_words():
    ticket_hypothesis = (
        "Observed-only ticker-level attention attribution: among the common-stock "
        "issuers appearing in accepted core trades, a strictly lagged Wikimedia "
        "Analytics API canonical-company-page attention surprise should identify "
        "stronger information persistence."
    )

    assert fp.infer_fingerprint(ticket_hypothesis)["data_source"] == "wikimedia_pageviews"
    assert fp.infer_fingerprint(
        "wikimedia_pageviews_canonical_issuer_attention_surprise"
    )["data_source"] == "wikimedia_pageviews"
    assert fp.infer_fingerprint(
        "Wikipedia pageviews per article news-attention revision surprise"
    )["data_source"] == "wikimedia_pageviews"


def test_wikimedia_keywords_do_not_capture_other_attention_surfaces():
    assert fp.infer_fingerprint(
        "Form 4 insider open-market purchase attention confluence"
    )["data_source"] == "form4_insider"
    assert fp.infer_fingerprint(
        "event attention persistence context notional scalar"
    )["data_source"] == "other"
    assert fp.infer_fingerprint(
        "entity-theme news relation observer"
    )["data_source"] == "entity_theme_news"


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
    assert fp.infer_fingerprint("iborrowdesk shortable stock lendable availability archive")["data_source"] == "ortex_borrow"


def test_execution_history_precedes_capital_flow_and_live_drift_consumers():
    assert fp.infer_fingerprint(
        "broker_execution_ledger order_fee_snapshots for live drift"
    )["data_source"] == "moomoo_execution_history"
    assert fp.infer_fingerprint(
        "moomoo_execution_history lifecycle built beside moomoo capital flow"
    )["data_source"] == "moomoo_execution_history"
    assert fp.infer_fingerprint(
        "broker_authoritative_exit_fill_h5_avoidance"
    )["data_source"] == "moomoo_execution_history"


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


def test_entity_theme_event_decision_basket_precedes_generic_forward_shapes():
    ticket = fp.infer_fingerprint(
        "entity_theme_news_observer exact-url-deduplicated event decision "
        "basket with 10-session replacement-value candidate attribution"
    )
    ticket_hypothesis = fp.infer_fingerprint(
        "Observed-only event-decision-basket alpha: collapse settled "
        "entity_theme_news observer rows by exact URL, then measure positive "
        "10-session replacement value across canonical windows"
    )
    family = fp.infer_fingerprint(
        "entity_theme_news_event_decision_basket URL event basket"
    )

    assert ticket["data_source"] == "entity_theme_news"
    assert ticket["gate_shape"] == "event_decision_basket"
    assert ticket_hypothesis["data_source"] == "entity_theme_news"
    assert ticket_hypothesis["gate_shape"] == "event_decision_basket"
    assert family["data_source"] == "entity_theme_news"
    assert family["gate_shape"] == "event_decision_basket"


def test_ordinary_entity_theme_forward_attribution_is_not_an_event_basket():
    ordinary = fp.infer_fingerprint(
        "entity_theme_news observer settled replacement value forward attribution"
    )
    generic_news = fp.infer_fingerprint(
        "entity-theme news relation observer"
    )

    assert ordinary["data_source"] == "entity_theme_news"
    assert ordinary["gate_shape"] == "forward_attribution"
    assert generic_news["data_source"] == "entity_theme_news"
    assert generic_news["gate_shape"] != "event_decision_basket"


def test_intraday_advisory_is_not_structured_news_or_other():
    fingerprint = fp.infer_fingerprint(
        "Post-exp024 intraday primary advisory shadow actions may identify "
        "existing positions with worse next-1d and next-3d returns than OK/no-action "
        "positions under a fixed forward attribution recipe"
    )

    assert fingerprint["data_source"] == "intraday_advisory"
    assert fingerprint["gate_shape"] == "forward_attribution"


def test_exit_lifecycle_precedes_intraday_advisory_without_stealing_shadow_actions():
    exit_lifecycle = fp.infer_fingerprint(
        "exit advisory lifecycle breach_status and trailing_stop_from_hwm "
        "read-only position rows"
    )
    intraday = fp.infer_fingerprint(
        "intraday advisory shadow action risk-review attribution"
    )

    assert exit_lifecycle["data_source"] == "exit_lifecycle"
    assert intraday["data_source"] == "intraday_advisory"


def test_news_event_exposure_precedes_generic_relation_without_overmatching():
    assert fp.infer_fingerprint("news_event_exposure observer daily pipeline")["data_source"] == "news_event_exposure"
    assert fp.infer_fingerprint("news second order exposure attribution")["data_source"] == "news_event_exposure"
    assert fp.infer_fingerprint("entity-theme news relation observer")["data_source"] == "entity_theme_news"
    assert fp.infer_fingerprint("intraday structured news relation observer")["data_source"] == "intraday_structured_news"
    assert fp.infer_fingerprint("lead_lag peer rolling_corr relation candidate pool")["data_source"] == "ohlcv_relation"
    assert fp.infer_fingerprint("thematic second order supply chain candidate pool")["data_source"] == "other"


def test_gdelt_news_tone_archive_source_without_news_overmatch():
    assert fp.infer_fingerprint(
        "GDELT 2.0 DOC timelinetone timelinevolraw company news tone shock archive"
    )["data_source"] == "gdelt_news_tone"
    assert fp.infer_fingerprint(
        "news_event_exposure observer daily pipeline"
    )["data_source"] == "news_event_exposure"
    assert fp.infer_fingerprint(
        "entity-theme news relation observer"
    )["data_source"] == "entity_theme_news"
    assert fp.infer_fingerprint(
        "prediction-market event odds observer"
    )["data_source"] == "prediction_market_event"


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


def test_cboe_volatility_term_structure_precedes_entry_admission_and_regime():
    fingerprint = fp.infer_fingerprint(
        "CBOE VIX9D versus VIX volatility term structure backwardation "
        "core no-entry admission gate"
    )

    assert fingerprint["data_source"] == "cboe_volatility_term_structure"
    assert fingerprint["gate_shape"] == "entry_admission"
    assert fp.infer_fingerprint(
        "cboe_vix9d_gt_vix_core_entry_exclusion_v1"
    )["gate_shape"] == "entry_admission"
    assert fp.infer_fingerprint(
        "generic market regime state_surface risk gate"
    )["data_source"] == "regime_state"


def test_cboe_vvix_precedes_forward_replacement_and_term_structure():
    fingerprint = fp.infer_fingerprint(
        "CBOE VVIX vol-of-vol relief stock leadership forward replacement "
        "value candidate pool"
    )

    assert fingerprint["data_source"] == "cboe_vvix"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "vvix20_cross_below_vol_of_vol_relief_stock_leadership_v1"
    )["data_source"] == "cboe_vvix"


def test_cboe_skew_precedes_forward_replacement_and_broad_skew():
    fingerprint = fp.infer_fingerprint(
        "CBOE SKEW Index equity-tail-risk relief stock leadership forward "
        "replacement value candidate pool"
    )

    assert fingerprint["data_source"] == "cboe_skew"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "skew20_cross_below_tail_risk_relief_stock_leadership_v1"
    )["data_source"] == "cboe_skew"
    assert fp.infer_fingerprint(
        "broad cross-sectional return skew forward attribution"
    )["data_source"] != "cboe_skew"


def test_move_rate_volatility_precedes_forward_replacement_and_ohlcv_relation():
    fingerprint = fp.infer_fingerprint(
        "move_rate_volatility_relief_stock_leadership ICE BofA MOVE Index "
        "forward replacement value candidate pool"
    )

    assert fingerprint["data_source"] == "move_rate_volatility"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "move20_cross_below_rate_volatility_relief_stock_leadership_v1"
    )["data_source"] == "move_rate_volatility"


def test_cboe_ovx_precedes_forward_replacement_and_ohlcv_relation():
    fingerprint = fp.infer_fingerprint(
        "CBOE OVX oil-volatility relief Energy leadership forward replacement "
        "value candidate pool"
    )

    assert fingerprint["data_source"] == "cboe_ovx"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "ovx20_cross_below_energy_leadership_candidate_pool_v1"
    )["data_source"] == "cboe_ovx"


def test_move_relief_kill_switch_has_dedicated_source_and_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "move_relief_sma20_reentry_next_open_kill_switch_v1 lifecycle kill switch"
    )

    assert fingerprint["data_source"] == "move_rate_volatility"
    assert fingerprint["gate_shape"] == "exit_kill_switch"
    assert fp.infer_fingerprint(
        "move_rate_volatility_relief_kill_switch"
    )["gate_shape"] == "exit_kill_switch"


def test_credit_risk_etf_precedes_generic_forward_replacement_value():
    fingerprint = fp.infer_fingerprint(
        "HYG/JNK credit-relief stock leadership forward replacement value"
    )

    assert fingerprint["data_source"] == "credit_risk_etf"
    assert fp.infer_fingerprint(
        "high-yield credit relief candidate pool"
    )["data_source"] == "credit_risk_etf"
    assert fp.infer_fingerprint(
        "credit_relief_stock_leadership_candidate_pool hyg_jnk_full_coverage"
    )["data_source"] == "credit_risk_etf"


def test_direct_credit_spread_precedes_credit_risk_etf_proxy():
    fingerprint = fp.infer_fingerprint(
        "FRED BAMLH0A0HYM2 direct ICE BofA US high-yield OAS credit-relief "
        "stock leadership forward replacement value candidate pool"
    )

    assert fingerprint["data_source"] == "direct_credit_spread"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "fred_high_yield_oas20_first_cross_below_credit_relief_shared_paper_v1"
    )["data_source"] == "direct_credit_spread"
    assert fp.infer_fingerprint(
        "HYG/JNK credit-relief stock leadership"
    )["data_source"] == "credit_risk_etf"


def test_fred_treasury_curve_precedes_ohlcv_relation_and_companyfacts():
    fingerprint = fp.infer_fingerprint(
        "FRED T10Y2Y 2s10s Treasury curve steepening Financial-sector "
        "stock leadership candidate pool"
    )

    assert fingerprint["data_source"] == "fred_treasury_curve"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "t10y2y20_first_cross_above_financial_leadership_v1"
    )["data_source"] == "fred_treasury_curve"
    assert fp.infer_fingerprint(
        "SEC Companyfacts free cash flow margin quality"
    )["data_source"] == "companyfacts_ratio"


def test_fred_mortgage_rate_precedes_ohlcv_momentum_and_treasury_curve():
    fingerprint = fp.infer_fingerprint(
        "FRED MORTGAGE30US weekly mortgage rate relief Residential "
        "Construction leadership candidate pool"
    )

    assert fingerprint["data_source"] == "fred_mortgage_rate"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "mortgage30us_two_consecutive_weekly_declines_residential_construction_leadership_v1"
    )["data_source"] == "fred_mortgage_rate"
    assert fp.infer_fingerprint(
        "FRED T10Y2Y Treasury curve steepening"
    )["data_source"] == "fred_treasury_curve"


def test_chicago_fed_nfci_precedes_companyfacts_and_macro_proxies():
    fingerprint = fp.infer_fingerprint(
        "lagged weekly Chicago Fed NFCI financial conditions easing "
        "Financials leadership candidate pool"
    )

    assert fingerprint["data_source"] == "chicago_fed_nfci"
    assert fingerprint["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "Chicago Fed National Financial Conditions Index below zero and falling"
    )["data_source"] == "chicago_fed_nfci"


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


def test_candidate_meta_label_readiness_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "candidate_meta_label_v1 training table readiness model_readiness "
        "for candidate meta-labeling"
    )

    assert fingerprint["data_source"] == "candidate_meta_label"
    assert fingerprint["gate_shape"] == "model_readiness"


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


def test_sec_contract_relation_precedes_generic_sec_text_event_and_ohlcv_relation():
    assert fp.infer_fingerprint(
        "SEC Item 1.01 contract-relation provenance candidate pool"
    )["data_source"] == "sec_contract_relation"
    assert fp.infer_fingerprint(
        "sec_contract_relation_provenance public counterparty target"
    )["data_source"] == "sec_contract_relation"
    assert fp.infer_fingerprint(
        "CIK-linked customer-supplier graph for Item 1.01 rows"
    )["data_source"] == "sec_contract_relation"
    assert fp.infer_fingerprint(
        "lead_lag peer rolling_corr relation candidate pool"
    )["data_source"] == "ohlcv_relation"
    assert fp.infer_fingerprint(
        "SEC 8-K item 3.01 listing noncompliance entry risk"
    )["data_source"] == "sec_text_event"


def test_sec_filing_features_precedes_generic_forward_sec_text_and_companyfacts():
    feature_forward = fp.infer_fingerprint(
        "sec_filing_features source_credibility_bucket predictability_mosaic_bucket "
        "forward replacement value attribution"
    )
    feature_pool = fp.infer_fingerprint(
        "SEC filing feature mosaic low_volume_predictability_bucket candidate pool"
    )

    assert feature_forward["data_source"] == "sec_filing_features"
    assert feature_forward["gate_shape"] == "forward_attribution"
    assert feature_pool["data_source"] == "sec_filing_features"
    assert feature_pool["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "sec_cover_page_filer_status_upgrade_candidate_pool"
    )["data_source"] == "sec_filer_status"
    assert fp.infer_fingerprint(
        "SEC 8-K item 3.01 listing noncompliance entry risk"
    )["data_source"] == "sec_text_event"
    assert fp.infer_fingerprint(
        "SEC Companyfacts free cash flow margin quality"
    )["data_source"] == "companyfacts_ratio"
    assert fp.infer_fingerprint(
        "forward replacement value entry_exhaustion attribution"
    )["data_source"] == "forward_replacement_value"


def test_sec13d_ownership_precedes_sec13f_sec_text_and_forward_replacement():
    assert fp.infer_fingerprint(
        "parsed SEC 13D Item-4 campaign-provenance board appointment candidate pool"
    )["data_source"] == "sec13d_ownership"
    assert fp.infer_fingerprint(
        "SEC 13D/13G holder stake action readiness"
    )["data_source"] == "sec13d_ownership"
    assert fp.infer_fingerprint(
        "Schedule 13D item4 campaign forward replacement rows"
    )["data_source"] == "sec13d_ownership"
    assert fp.infer_fingerprint(
        "SEC 13F institutional sponsorship holder signal"
    )["data_source"] == "sec13f_ownership"


def test_dod_contract_award_peer_substitution_has_distinct_gate_shape():
    result = fp.infer_fingerprint(
        "DoD contract award winner-to-peer substitution selects the strongest "
        "non-awarded peer for 10 days"
    )
    assert result["data_source"] == "dod_contract_award"
    assert result["gate_shape"] == "peer_propagation_top1_10d"


def test_dod_new_contract_revenue_materiality_stays_on_award_surface():
    result = fp.infer_fingerprint(
        "dod_new_contract_revenue_materiality_candidate_pool ranks new awards "
        "by latest filed annual revenue for top1 10d"
    )
    assert result["data_source"] == "dod_contract_award"


def test_deflated_sharpe_uses_trial_panel_surface_and_gate_shape():
    result = fp.infer_fingerprint(
        "Bailey-Lopez de Prado probabilistic Sharpe and Deflated Sharpe "
        "with a complete selection pool and effective trial count"
    )

    assert result["data_source"] == "trial_return_panel"
    assert result["gate_shape"] == "trial_adjusted_significance"


def test_plain_daily_sharpe_does_not_claim_complete_trial_panel():
    result = fp.infer_fingerprint("persist daily Sharpe from one backtest")

    assert result["data_source"] != "trial_return_panel"
    assert fp.infer_fingerprint(
        "candidate selection pool for top1 10d"
    )["data_source"] != "trial_return_panel"


def test_trial_adjusted_sharpe_family_key_uses_dsr_surface():
    result = fp.infer_fingerprint("trial_adjusted_sharpe_measurement")

    assert result["data_source"] == "trial_return_panel"
    assert result["gate_shape"] == "trial_adjusted_significance"


def test_drugsfda_original_approval_ticket_uses_distinct_official_source():
    result = fp.infer_fingerprint(
        "Alpha-enabling new-source hypothesis: a first official CDER original "
        "NDA/BLA approval can create post-regulatory-de-risking stock drift; "
        "freeze the Drugs@FDA source and persist a shared default-off "
        "first-seen application ledger."
    )

    assert result["data_source"] == "drugsfda_approval"


def test_generic_fda_approval_news_does_not_claim_drugsfda_source():
    result = fp.infer_fingerprint(
        "FDA approval news sentiment around a biotech catalyst candidate pool"
    )

    assert result["data_source"] == "other"
