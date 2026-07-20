import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


@pytest.mark.parametrize(
    "text",
    [
        "sec_sc_to_t_target_cash_settlement_spread with ORTEX delisted OHLCV",
        "SC TO-T target cash conversion with Moomoo execution feasibility",
        "third-party cash tender lifecycle: actual completion higher-bid "
        "termination cash settlement and window-end mark-to-market",
    ],
)
def test_cash_tender_contract_keeps_sec_source_and_cash_conversion_shape(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] == "sec_text_event"
    assert result["gate_shape"] == "corporate_action_cash_conversion"


def test_generic_ortex_borrow_still_keeps_borrow_source():
    result = fp.infer_fingerprint(
        "ORTEX cost-to-borrow utilization and loan availability observer"
    )

    assert result["data_source"] == "ortex_borrow"


@pytest.mark.parametrize(
    "text",
    [
        "nvd_cve_change_history Initial Analysis entry exclusion",
        "Official NVD CVE change history Initial Analysis Added CPE Configuration",
        "National Vulnerability Database change history cluster3 next-session gate",
        "cvehistory/2.0 eventName=Initial Analysis",
    ],
)
def test_nvd_cve_change_history_has_dedicated_fingerprint(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] == "nvd_cve_change_history"
    assert result["data_source"] != "other"


@pytest.mark.parametrize(
    "text",
    [
        "CISA KEV entry risk gate",
        "NVDA OHLCV momentum candidate pool",
        "generic CVE security news sentiment",
    ],
)
def test_nvd_keywords_do_not_capture_adjacent_security_or_nvda_sources(text):
    assert fp.infer_fingerprint(text)["data_source"] != "nvd_cve_change_history"


TICKET_20260717_004_HYPOTHESIS = (
    "Shared-paper-first weekly relative-value alpha: the sum of "
    "small-minus-large-bank four-week log-growth spreads in Other deposits "
    "and Commercial and industrial loans from each official Federal Reserve "
    "H.8 dated release predicts the next week KRE versus KBE relative return; "
    "hash-bind as-released Table 6/8 vintages, enter one equal-gross 4000 "
    "USD-per-leg default-off pair at the first session open after publication, "
    "and rebalance only after the next release."
)


@pytest.mark.parametrize(
    "text",
    [
        TICKET_20260717_004_HYPOTHESIS,
        "fed_h8_weekly_release_bank_size_pair",
        "fed_h8_small_large_bank_deposit_c_and_i_lag4_weekly_kre_kbe_pair_v1",
        "81 Federal Reserve H.8 dated release vintages parsed as a weekly "
        "market-neutral KRE/KBE relative-value allocator",
    ],
)
def test_fed_h8_weekly_allocator_has_dedicated_fingerprint(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] == "fed_h8_weekly_release_vintages"
    assert result["gate_shape"] == "weekly_relative_value_allocator"


@pytest.mark.parametrize(
    "text",
    [
        "SEC Companyfacts commercial and industrial loans, other deposits, "
        "and lease growth ratio",
        "SEC Companyfacts bank-size deposit and loan ratio weekly allocator",
        "generic KRE/KBE relative-value bank ETF pair",
    ],
)
def test_fed_h8_keywords_do_not_capture_nearby_non_h8_text(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] != "fed_h8_weekly_release_vintages"


TICKET_20260717_005_HYPOTHESIS = (
    "Shared-paper-first candidate-pool alpha: when an official TSA FOIA "
    "weekly checkpoint-throughput report shows national passenger volume "
    "remains above the same weekdays 52 weeks earlier and that year-over-year "
    "growth accelerates versus the preceding week, a fixed all-window-liquid "
    "air-travel revenue basket should continue from the first strictly later "
    "regular-session open through the fifth-session close."
)


@pytest.mark.parametrize(
    "text",
    [
        TICKET_20260717_005_HYPOTHESIS,
        "tsa_checkpoint_throughput_paper_sleeve",
        "tsa_weekly_checkpoint_throughput_travel_demand_basket",
        "Transportation Security Administration checkpoint throughput report",
    ],
)
def test_tsa_checkpoint_throughput_has_dedicated_fingerprint(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] == "tsa_checkpoint_throughput"


@pytest.mark.parametrize(
    "text",
    [
        "generic airport checkpoint passenger-volume report",
        "distributed transaction throughput acceleration candidate pool",
        "TSA PreCheck enrollment growth candidate pool",
    ],
)
def test_tsa_checkpoint_keywords_do_not_capture_generic_text(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] != "tsa_checkpoint_throughput"


def test_nearby_companyfacts_text_keeps_companyfacts_source():
    result = fp.infer_fingerprint(
        "SEC Companyfacts commercial and industrial loans, other deposits, "
        "and lease growth ratio for a weekly bank allocator"
    )

    assert result["data_source"] == "companyfacts_ratio"


TICKET_20260717_003_HYPOTHESIS = (
    "The active cash-feasible Gate-1 carries today's legacy-core and "
    "current-position membership backward; replaying only Git-proven "
    "effective-dated core entry eligibility on the identical frozen behavior, "
    "cash, and OHLCV context will establish an auditable lower-bound "
    "measurement surface."
)


@pytest.mark.parametrize(
    "text",
    [
        TICKET_20260717_003_HYPOTHESIS,
        "legacy_core_pit_universe_measurement_repair",
        "backtest core entry eligibility source",
        "core entry-eligibility identity: current static watchlist versus "
        "immutable effective-dated manifest",
        "entry_universe_ledger Git effective lower bound",
    ],
)
def test_core_universe_membership_ticket_has_dedicated_fingerprint(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] == "core_universe_membership_ledger"
    assert result["gate_shape"] == "point_in_time_entry_eligibility"


def test_core_universe_membership_frozen_family_inputs_stay_classified():
    result = fp.infer_fingerprint(
        "legacy_core_pit_universe_measurement_repair",
        "backtest core entry eligibility source",
        "v1_git_effective_lower_bound_and_forward_membership_ledger",
    )

    assert result["data_source"] == "core_universe_membership_ledger"
    assert result["gate_shape"] == "point_in_time_entry_eligibility"


@pytest.mark.parametrize(
    "text",
    [
        "generic broad universe entry ranking candidate pool",
        "pilot universe eligible tickers as of date",
        "entry eligibility for a generic candidate source",
    ],
)
def test_core_universe_membership_keywords_do_not_capture_generic_text(text):
    result = fp.infer_fingerprint(text)

    assert result["data_source"] != "core_universe_membership_ledger"
    assert result["gate_shape"] != "point_in_time_entry_eligibility"


def test_core_entry_admission_keeps_existing_fingerprint():
    result = fp.infer_fingerprint(
        "core entry admission gate for the current trading universe"
    )

    assert result["data_source"] == "core_entry_admission"
    assert result["gate_shape"] == "entry_admission"


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


def test_sec_form_nport_public_holdings_precedes_sec13f_holder_language():
    result = fp.infer_fingerprint(
        "Risk-allocation alpha from SEC Form N-PORT public as-filed registered-"
        "fund holdings: split-adjusted aggregate holder shares control a fixed "
        "opening-notional scalar"
    )

    assert result["data_source"] == "sec_form_nport_public_holdings"
    assert result["gate_shape"] == "notional_scalar"
    assert fp.infer_fingerprint(
        "sec_nport continuous-fund QoQ aggregate-share sign"
    )["data_source"] == "sec_form_nport_public_holdings"


def test_sec_form_nport_keywords_do_not_capture_sec13f_or_cftc_sources():
    assert fp.infer_fingerprint(
        "SEC 13F institutional sponsorship holder signal"
    )["data_source"] == "sec13f_ownership"
    assert fp.infer_fingerprint(
        "CFTC TFF Traders in Financial Futures institutional positioning"
    )["data_source"] == "cftc_tff_positioning"


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


@pytest.mark.parametrize(
    "text",
    [
        "production_visible_finra_venue_short_crowding_core_entry_admission",
        "finra_venue_short_crowding_core_entry_exclusion",
        "finra_ats_otc_x_short_interest_crowding_core_entry_exclusion_v1",
        "Entry-admission alpha using ATS plus OTC volume and the latest "
        "strictly prior-day global FINRA short-interest release as a core "
        "entry exclusion",
    ],
)
def test_finra_venue_short_interest_join_precedes_component_sources(text):
    fingerprint = fp.infer_fingerprint(text)

    assert fingerprint["data_source"] == "finra_venue_short_interest"
    assert fingerprint["gate_shape"] == "entry_admission"


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


def test_rejected_joint_preflight_stays_on_parked_portfolio_surface():
    """Frozen-family rebuild sees family/variable/variant, not the hypothesis."""

    fingerprint = fp.infer_fingerprint(
        "joint_chronological_covariance_capacity_portfolio_overlay",
        "old_train_frozen_joint_covariance_capacity_weights_v1",
        "old_train_capped_inverse_vol_core_corr_10pct_v1",
    )

    assert fingerprint["data_source"] == "portfolio_covariance_lane"
    assert fingerprint["gate_shape"] == "portfolio_daily_equity_overlay"


def test_portfolio_contribution_gate_is_a_distinct_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "owner-authorized capital-conserving portfolio-contribution Gate 4-P "
        "for the portfolio covariance lane"
    )

    assert fingerprint["data_source"] == "portfolio_covariance_lane"
    assert fingerprint["gate_shape"] == "portfolio_contribution"


def test_portfolio_contribution_trial_family_does_not_fall_to_other_source():
    fingerprint = fp.infer_fingerprint(
        "portfolio_contribution_gate_complete_panel_v1 "
        "owner_authorized_capital_conserving_complete31_v1"
    )

    assert fingerprint["data_source"] == "portfolio_covariance_lane"
    assert fingerprint["gate_shape"] == "portfolio_contribution"


def test_microstructure_viability_attribution_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "tick_to_atr vol_normalized_tick microstructure viability attribution"
    )

    assert fingerprint["data_source"] == "microstructure_viability"
    assert fingerprint["gate_shape"] == "microstructure_attribution"


def test_cash_conflict_oldest_incumbent_has_dedicated_surface_and_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "cash_conflict_oldest_incumbent_full_rotation funds a fresh core entry "
        "through execution_cash_opportunity_cost_rotation after settled-cash "
        "admission"
    )

    assert fingerprint["data_source"] == "cash_feasible_core_book"
    assert fingerprint["gate_shape"] == "incumbent_rotation"


def test_cash_conflict_persistent_queue_has_distinct_surface_and_gate_shape():
    fingerprint = fp.infer_fingerprint(
        "cash_conflict_persistent_order_queue keeps the unfilled entry remainder "
        "in a cash_conflict_deferred_queue until the original band is invalid"
    )

    assert fingerprint["data_source"] == "cash_feasible_core_book"
    assert fingerprint["gate_shape"] == "cash_conflict_deferred_queue"
    assert fingerprint["gate_shape"] != "incumbent_rotation"

    changed_variable = fp.infer_fingerprint(
        "cash_conflict_unfilled_entry_fifo_persistence_until_price_thesis_invalid_v1"
    )
    assert changed_variable["data_source"] == "cash_feasible_core_book"
    assert changed_variable["gate_shape"] == "cash_conflict_deferred_queue"


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


def test_sec_same_cik_dual_class_spread_has_dedicated_source_and_pair_shape():
    fingerprint = fp.infer_fingerprint(
        "Shared-paper-first market-neutral alpha: for a frozen official-SEC "
        "same-CIK whitelist of liquid dual-class common equities with "
        "substantially shared economics but different voting rights, a class "
        "premium at least 1.0 percent away from its strictly-prior 120-session "
        "robust median and robust MAD z-score at least 2.5 should converge; "
        "buy the cheap class and short the rich class at the next open with "
        "equal cash-collateralized whole-share notionals, then exit on premium "
        "convergence, a 3 percent adverse-spread stop, or ten-session timeout.",
        "sec_same_issuer_dual_class_spread_convergence",
        "sec_same_cik_dual_class_robust_premium_spread_v1",
        "robust120_z250_abs100bp_nextopen_converge25bp_stop300bp_timeout10_v1",
    )

    assert fingerprint["data_source"] == "sec_same_cik_share_class_identity"
    assert fingerprint["gate_shape"] == "pair_spread"


@pytest.mark.parametrize(
    "text",
    [
        "sec_same_cik frozen common-share pair whitelist",
        "official same-CIK dual-class issuer identity",
        "same issuer dual class rights whitelist",
        "official share-class identity linkage",
    ],
)
def test_sec_same_cik_share_class_identity_compound_spellings(text):
    assert fp.infer_fingerprint(text)["data_source"] == (
        "sec_same_cik_share_class_identity"
    )


def test_sec_same_cik_identity_without_spread_is_not_pair_spread():
    fingerprint = fp.infer_fingerprint(
        "official SEC same-CIK share-class identity materialization audit"
    )

    assert fingerprint["data_source"] == "sec_same_cik_share_class_identity"
    assert fingerprint["gate_shape"] != "pair_spread"


@pytest.mark.parametrize(
    ("text", "expected_source"),
    [
        ("CIK-linked customer-supplier graph for Item 1.01 rows", "sec_contract_relation"),
        ("SEC cover-page filer-status issuer class identity", "sec_filer_status"),
        ("SEC 8-K issuer class identity item 3.01", "sec_text_event"),
        ("SEC Companyfacts issuer share count", "companyfacts_ratio"),
    ],
)
def test_sec_same_cik_keywords_do_not_capture_adjacent_sec_sources(
    text, expected_source
):
    fingerprint = fp.infer_fingerprint(text)

    assert fingerprint["data_source"] == expected_source
    assert fingerprint["data_source"] != "sec_same_cik_share_class_identity"


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


def test_treasury_indirect_bidder_share_routes_to_auction_results_surface():
    fingerprint = fp.infer_fingerprint(
        "treasury_auction_indirect_bidder_share_tbt_event_response "
        "treasury_auction_demand_microstructure"
    )

    assert fingerprint["data_source"] == "treasury_auction_results"
    assert fingerprint["gate_shape"] == "event_driven_inverse_treasury_etf_5d"


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


def test_pcaob_form_ap_peer_substitution_has_own_source_and_20d_gate_shape():
    result = fp.infer_fingerprint(
        "pcaob_form_ap_partner_change_peer_substitution shared-paper-first: "
        "official PCAOB Form AP engagement-partner change selects an "
        "unaffected same-industry ADV60 peer for top1 20d"
    )

    assert result["data_source"] == "pcaob_form_ap"
    assert result["gate_shape"] == "peer_substitution_candidate_pool_top1_20d"


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


def test_faers_quarterly_safety_basket_has_own_source_and_gate_shape():
    result = fp.infer_fingerprint(
        "Shared-paper-first candidate-pool alpha: among strictly mapped liquid "
        "Healthcare issuers, a quarter-over-quarter decline in official FDA "
        "FAERS serious-outcome share is a safety-quality signal; rank only "
        "improving issuers, cap the ten largest improvements per quarterly "
        "release, allocate one equal-weight 10000 USD event basket at the first "
        "PIT session open, and close at the twentieth-session close with 35 bps "
        "round-trip cost."
    )

    assert result["data_source"] == "faers"
    assert result["gate_shape"] == "standalone_quarterly_candidate_pool"
    assert result["data_source"] != "companyfacts_ratio"
    assert result["gate_shape"] != "allocator_source"


def test_faers_keywords_do_not_capture_adjacent_fda_sources():
    assert fp.infer_fingerprint(
        "FDA adverse-event monitoring system quarterly candidate pool"
    )["data_source"] == "faers"
    assert fp.infer_fingerprint(
        "Drugs@FDA original NDA/BLA approval candidate pool"
    )["data_source"] == "drugsfda_approval"
    assert fp.infer_fingerprint(
        "official FDA Orange Book monthly Additions/Deletions PDF NEWA basket"
    )["data_source"] == "fda_orange_book_monthly_additions_deletions"
    assert fp.infer_fingerprint(
        "FDA approval news sentiment around a biotech catalyst candidate pool"
    )["data_source"] == "other"


def test_clinicaltrials_results_use_distinct_versioned_source():
    assert fp.infer_fingerprint(
        "ClinicalTrials.gov Phase 3 ResultsFirstPostDate candidate pool"
    )["data_source"] == "clinicaltrials_results"
    assert fp.infer_fingerprint(
        "clinicaltrials_results version-history replay"
    )["data_source"] == "clinicaltrials_results"
    assert fp.infer_fingerprint(
        "results_first_post_date shared paper snapshot"
    )["data_source"] == "clinicaltrials_results"


def test_duplicate_reservation_accounting_does_not_consume_named_source():
    result = fp.infer_fingerprint(
        "duplicate_reservation_accounting for a ClinicalTrials.gov Phase 3 "
        "ResultsFirstPostDate candidate pool"
    )

    assert result["data_source"] == "duplicate_reservation_accounting"


def test_clinicaltrials_keywords_do_not_capture_adjacent_surfaces():
    assert fp.infer_fingerprint(
        "Drugs@FDA original NDA/BLA approval"
    )["data_source"] == "drugsfda_approval"
    assert fp.infer_fingerprint(
        "generic Phase 3 trial results biotech news"
    )["data_source"] != "clinicaltrials_results"
    for text in (
        "supplier contract event candidate pool",
        "Python function result observer",
        "distinct issuer ranking",
    ):
        assert fp.infer_fingerprint(text)["data_source"] != "clinicaltrials_results"


def test_usaspending_obligation_fields_use_distinct_transaction_source():
    ticket = fp.infer_fingerprint(
        "A non-DoD federal contract transaction first visible in USAspending "
        "adds positive federal_action_obligation while "
        "base_and_all_options_value does not increase."
    )

    assert ticket["data_source"] == "usaspending_obligation"
    assert fp.infer_fingerprint(
        "base_and_all_options_value obligation conversion first-seen observer"
    )["data_source"] == "usaspending_obligation"


def test_usaspending_keywords_do_not_capture_generic_or_dod_contracts():
    assert fp.infer_fingerprint(
        "DoD contract award winner revenue materiality"
    )["data_source"] == "dod_contract_award"
    assert fp.infer_fingerprint(
        "generic federal contract award news"
    )["data_source"] != "usaspending_obligation"


def test_fda_device_enforcement_uses_distinct_official_source():
    for text in (
        "official_openfda_device_enforcement_report_class1 candidate pool",
        "openFDA device enforcement Class I report_date replay",
        "FDA weekly Device Enforcement Report Class 1 paper snapshot",
        "fda_device_enforcement event-level dedupe",
        "production_visible_fda_device_class1_enforcement_candidate_pool",
    ):
        assert fp.infer_fingerprint(text)["data_source"] == "fda_device_enforcement"


def test_fda_device_enforcement_keywords_do_not_capture_adjacent_surfaces():
    assert fp.infer_fingerprint(
        "Drugs@FDA original NDA/BLA approval"
    )["data_source"] == "drugsfda_approval"
    for text in (
        "generic Class I medical-device recall news",
        "FDA drug approval enforcement news",
        "report_date based candidate pool",
    ):
        assert fp.infer_fingerprint(text)["data_source"] != "fda_device_enforcement"


def test_fda_510k_clearance_uses_distinct_official_source():
    for text in (
        "official FDA 510(k) clearance decision-date candidate pool",
        "Releasable 510(k) database k_number historical replay",
        "openFDA device clearance shared default-off observer",
        "fda_510k_clearance issuer mapping",
        "fda_510k_traditional_clearance_candidate_pool",
        "open.fda.gov/apis/device/510k decision surface",
    ):
        assert fp.infer_fingerprint(text)["data_source"] == "fda_510k_clearance"


def test_fda_orange_book_monthly_newa_uses_distinct_official_source():
    for text in (
        "official FDA Orange Book monthly Additions/Deletions PDF NEWA basket",
        "orange_book_newa_release_basket next-open 10d",
        "fda_orange_book_fresh_newa_equal_weight_release_basket_nextopen_10d_v1",
    ):
        result = fp.infer_fingerprint(text)
        assert result["data_source"] == (
            "fda_orange_book_monthly_additions_deletions"
        )
        assert result["gate_shape"] == "event_basket_10d"


def test_fda_orange_book_precedes_companyfacts_release_substring():
    result = fp.infer_fingerprint(
        "FDA Orange Book NEWA product release basket candidate_pool"
    )

    assert result["data_source"] == (
        "fda_orange_book_monthly_additions_deletions"
    )
    assert result["data_source"] != "companyfacts_ratio"


def test_fda_510k_clearance_precedes_relation_without_adjacent_overmatch():
    assert fp.infer_fingerprint(
        "openFDA device clearance issuer peer relation candidate pool"
    )["data_source"] == "fda_510k_clearance"
    assert fp.infer_fingerprint(
        "openFDA device enforcement Class I report_date replay"
    )["data_source"] == "fda_device_enforcement"
    assert fp.infer_fingerprint(
        "Drugs@FDA original NDA/BLA approval"
    )["data_source"] == "drugsfda_approval"
    assert fp.infer_fingerprint(
        "generic medical-device clearance news"
    )["data_source"] != "fda_510k_clearance"
    assert fp.infer_fingerprint(
        "peer relation medical-device candidate pool"
    )["data_source"] == "ohlcv_relation"


def test_federal_product_safety_batch_uses_distinct_official_surface():
    hypothesis = (
        "Batch private scout: across the complete audit-ready remaining federal "
        "product-safety sources, NHTSA defect-investigation openings and CPSC "
        "recall publications, an issuer that is green and ahead of SPY on the "
        "first strictly subsequent trading session may show absorbed adverse "
        "news and continue from the next open through the tenth-session close."
    )

    assert fp.infer_fingerprint(hypothesis)["data_source"] == (
        "federal_product_safety_official_events"
    )
    for text in (
        "NHTSA ODATE defect-investigation opening PIT surface",
        "CPSC RecallDate LastPublishDate recall publication PIT surface",
    ):
        assert fp.infer_fingerprint(text)["data_source"] == (
            "federal_product_safety_official_events"
        )


def test_federal_product_safety_keywords_do_not_capture_fda_or_clinicaltrials():
    fda_hypothesis = (
        "After an FDA weekly Device Enforcement Report publicly lists a mapped "
        "issuer's Class I recall, an issuer that closes green and ahead of SPY "
        "on the first strictly subsequent trading session should continue."
    )
    clinicaltrials_hypothesis = (
        "A mapped public drug sponsor's first ClinicalTrials.gov Phase 3 "
        "ResultsFirstPostDate, confirmed by a green day ahead of SPY, should "
        "continue from the next open through the tenth close."
    )

    assert fp.infer_fingerprint(fda_hypothesis)["data_source"] == (
        "fda_device_enforcement"
    )
    assert fp.infer_fingerprint(clinicaltrials_hypothesis)["data_source"] == (
        "clinicaltrials_results"
    )


def test_fdic_call_report_candidate_pool_precedes_companyfacts_and_allocator():
    hypothesis = (
        "Shared-paper-first candidate-pool alpha: after each official FDIC "
        "Quarterly Banking Profile release, publicly listed bank parents whose "
        "dominant insured-bank subsidiary exceeds 10 billion USD assets, grows "
        "core deposits year over year, and lowers its uninsured-deposit share "
        "year over year may have a strengthening deposit franchise that "
        "continues to reprice; exclude merger-like asset jumps, rank the five "
        "largest uninsured-share improvements, enter the first strictly later "
        "open, and hold 20 sessions."
    )
    result = fp.infer_fingerprint(
        hypothesis,
        "fdic_qbp_deposit_franchise_repair_candidate_pool",
        "fdic_deposit_franchise_repair_quarterly_ranking",
        "production_visible_fdic_call_report_deposit_quality_candidate_pool",
    )

    assert result["data_source"] == "fdic_call_report_financials"
    assert result["data_source"] != "companyfacts_ratio"
    assert result["gate_shape"] == "candidate_pool_top5_20d"
    assert result["gate_shape"] != "allocator_source"


def test_fdic_frozen_family_builder_inputs_keep_the_real_source_key():
    """The derived-memory builder fingerprints family/variable/variant only."""

    result = fp.infer_fingerprint(
        "fdic_qbp_deposit_franchise_repair_candidate_pool",
        "fdic_deposit_franchise_repair_quarterly_ranking",
        "coredep_growth_uninsured_share_improvement_top5_20d_v1",
    )

    assert result["data_source"] == "fdic_call_report_financials"
    assert result["gate_shape"] == "candidate_pool_top5_20d"


@pytest.mark.parametrize(
    "text",
    [
        "fdic_call_report_financials quarterly candidate pool",
        "FDIC Quarterly Banking Profile deposit-franchise ranking",
        "FDIC QBP deposit quality candidate pool",
        "BankFind Call Report quarterly bank ranking",
    ],
)
def test_fdic_call_report_compound_source_spellings(text):
    assert fp.infer_fingerprint(text)["data_source"] == (
        "fdic_call_report_financials"
    )


def test_fdic_keywords_do_not_capture_bare_asset_or_deposit_language():
    assert fp.infer_fingerprint(
        "SEC Companyfacts asset_growth and deposit liabilities candidate pool"
    )["data_source"] == "companyfacts_ratio"
    assert fp.infer_fingerprint(
        "accepted helper deposit source_priority allocator"
    )["data_source"] == "allocator"


def test_eia_wpsr_event_basket_precedes_inventory_and_notional_fallbacks():
    hypothesis = (
        "Shared-paper-first candidate-pool alpha: an official EIA WPSR "
        "first-release broad de-stocking shock across commercial crude, "
        "gasoline, and distillate inventories enters a fixed equal-notional "
        "energy equity basket for ten sessions."
    )
    result = fp.infer_fingerprint(
        hypothesis,
        "eia_wpsr_first_release_destocking_energy_basket",
        "eia_wpsr_physical_inventory_shock_candidate_pool",
        "production_visible_eia_wpsr_physical_supply_shock_energy_basket",
    )

    assert result["data_source"] == "eia_wpsr_inventory"
    assert result["data_source"] != "companyfacts_ratio"
    assert result["gate_shape"] == "event_basket_10d"
    assert result["gate_shape"] != "notional_scalar"
    assert result["gate_shape"] != "candidate_pool_top1_10d"


def test_eia_wpsr_frozen_family_builder_inputs_keep_distinct_fingerprint():
    """The derived-memory builder fingerprints family/variable/variant only."""

    result = fp.infer_fingerprint(
        "eia_wpsr_first_release_destocking_energy_basket",
        "eia_wpsr_physical_inventory_shock_candidate_pool",
        "three_series_seasonal_p80_fixed10_10d_v1",
    )

    assert result["data_source"] == "eia_wpsr_inventory"
    assert result["gate_shape"] == "event_basket_10d"


@pytest.mark.parametrize(
    "text",
    [
        "EIA Weekly Petroleum Status Report first-release inventory shock",
        "eia_wpsr_inventory archived issue replay",
        "WPSR Table 4 first-release physical-supply event",
    ],
)
def test_eia_wpsr_compound_source_spellings(text):
    assert fp.infer_fingerprint(text)["data_source"] == "eia_wpsr_inventory"


def test_eia_wpsr_keywords_do_not_capture_adjacent_inventory_surfaces():
    assert fp.infer_fingerprint(
        "SEC Companyfacts inventory turnover candidate pool"
    )["data_source"] == "companyfacts_ratio"
    for text in (
        "generic crude oil inventory news candidate pool",
        "EIA Short-Term Energy Outlook candidate pool",
        "petroleum producer inventory accounting",
    ):
        assert fp.infer_fingerprint(text)["data_source"] != "eia_wpsr_inventory"


def test_usda_fas_export_sales_event_basket_precedes_fallbacks():
    hypothesis = (
        "Shared-paper-first alpha: USDA Foreign Agricultural Service weekly "
        "Export Sales Reporting as-published archived corn and soybean "
        "current-plus-next marketing-year net-sales strength, measured only "
        "against prior seasonal observations and prior composite scores, may "
        "add after-cost ten-session value through one fixed ten-leg agriculture "
        "value-chain event basket entered at the first regular open after the "
        "official 08:30 ET publication; no revised API values, price "
        "confirmation, or post-result retuning."
    )
    result = fp.infer_fingerprint(
        hypothesis,
        "usda_fas_export_sales_as_published_agriculture_basket",
        "usda_fas_export_sales_physical_demand_candidate_pool",
        "corn_soy_seasonal_midrank_prior104_p75_fixed10_10d_v1",
        "production_visible_usda_fas_export_sales_physical_demand_agriculture_basket",
    )

    assert fp.infer_fingerprint(hypothesis)["data_source"] == (
        "usda_fas_export_sales"
    )
    assert result["data_source"] == "usda_fas_export_sales"
    assert result["data_source"] != "companyfacts_ratio"
    assert result["gate_shape"] == "event_basket_10d"
    assert result["gate_shape"] != "notional_scalar"
    assert result["gate_shape"] != "allocator_source"


def test_usda_fas_frozen_family_builder_inputs_keep_distinct_fingerprint():
    """The derived-memory builder fingerprints family/variable/variant only."""

    result = fp.infer_fingerprint(
        "usda_fas_export_sales_as_published_agriculture_basket",
        "usda_fas_export_sales_physical_demand_candidate_pool",
        "corn_soy_seasonal_midrank_prior104_p75_fixed10_10d_v1",
    )

    assert result["data_source"] == "usda_fas_export_sales"
    assert result["gate_shape"] == "event_basket_10d"


@pytest.mark.parametrize(
    "text",
    [
        "usda_fas_export_sales as-published archive",
        "USDA FAS Export Sales Reporting weekly release",
        "USDA Foreign Agricultural Service weekly Export Sales Reporting",
        "Foreign Agricultural Service Export Sales Reporting Program",
        "USDA weekly export sales report",
    ],
)
def test_usda_fas_export_sales_compound_source_spellings(text):
    assert fp.infer_fingerprint(text)["data_source"] == "usda_fas_export_sales"


def test_usda_fas_keywords_do_not_capture_adjacent_sources():
    assert fp.infer_fingerprint(
        "USAspending USDA federal_action_obligation transaction"
    )["data_source"] == "usaspending_obligation"
    assert fp.infer_fingerprint(
        "SEC Companyfacts revenue and company export-sales growth candidate_pool"
    )["data_source"] == "companyfacts_ratio"
    for text in (
        "USDA WASDE crop balance candidate_pool",
        "U.S. Census Bureau monthly exports candidate_pool",
        "company export-sales growth candidate_pool",
    ):
        assert fp.infer_fingerprint(text)["data_source"] != (
            "usda_fas_export_sales"
        )


def test_usda_fas_top1_policy_does_not_claim_event_basket_gate():
    result = fp.infer_fingerprint(
        "USDA Foreign Agricultural Service weekly Export Sales Reporting "
        "candidate_pool top1 issuer continuation"
    )

    assert result["data_source"] == "usda_fas_export_sales"
    assert result["gate_shape"] == "candidate_pool_top1_10d"
    assert result["gate_shape"] != "event_basket_10d"


def test_event_basket_10d_keywords_do_not_capture_adjacent_gate_shapes():
    assert fp.infer_fingerprint(
        "entity_theme_news event-decision-basket URL event basket"
    )["gate_shape"] == "event_decision_basket"
    assert fp.infer_fingerprint(
        "macro relief candidate_pool top1 ten-day leadership"
    )["gate_shape"] == "candidate_pool_top1_10d"
    assert fp.infer_fingerprint(
        "fixed equal-notional energy basket held for ten sessions"
    )["gate_shape"] == "notional_scalar"


def test_hacker_news_owned_domain_attention_has_dedicated_source_and_top3_gate():
    result = fp.infer_fingerprint(
        "A completed UTC week's Hacker News owned-domain attention acceleration "
        "ranks the top three liquid issuers by weekly count for a next-open "
        "ten-session candidate pool.",
        "hacker_news_owned_domain_attention_acceleration",
        "hn_owned_domain_weekly_attention_top3_candidate_pool_v1",
        "exact_host_current_ge2_above_prior4w_top3_next_open_h10_v1",
    )

    assert result["data_source"] == "hacker_news_owned_domain_attention"
    assert result["gate_shape"] == "candidate_pool_top3_10d"


def test_hacker_news_keywords_do_not_capture_adjacent_news_or_pageview_sources():
    assert fp.infer_fingerprint(
        "entity_theme_news exact URL forward replacement observer"
    )["data_source"] == "entity_theme_news"
    assert fp.infer_fingerprint(
        "Wikimedia pageviews issuer attention candidate pool"
    )["data_source"] == "wikimedia_pageviews"


def test_deps_dev_maven_releases_have_dedicated_source_and_top3_gate():
    result = fp.infer_fingerprint(
        "A completed Monday-Sunday week of deps.dev Maven package releases "
        "strictly above the issuer prior-eight-week median ranks the top three "
        "at next open for a ten-session candidate pool.",
        "deps_dev_maven_release_acceleration_top3_10d",
        "deps_dev_maven_release_acceleration_top3_nextopen_h10_shared_v1",
        "complete_week_current_ge2_above_prior8median_top3_next_open_h10_v1",
    )

    assert result["data_source"] == "deps_dev_maven_package_releases"
    assert result["gate_shape"] == "candidate_pool_top3_10d"


@pytest.mark.parametrize(
    ("text", "expected_source"),
    [
        ("SEC Companyfacts operating lease accounting", "companyfacts_ratio"),
        (
            "FDA Orange Book NEWA product release basket candidate_pool",
            "fda_orange_book_monthly_additions_deletions",
        ),
        ("entity_theme_news software release event", "entity_theme_news"),
    ],
)
def test_deps_dev_maven_release_keywords_do_not_capture_adjacent_sources(
    text, expected_source
):
    assert fp.infer_fingerprint(text)["data_source"] == expected_source


def test_linux_mainline_signed_rc_hypothesis_has_dedicated_source_and_top3_20d_gate():
    hypothesis = (
        "Signed Linux mainline RC tags whose exact corporate-domain non-merge "
        "contribution count is at least 3 and strictly above the issuer's "
        "prior-eight-RC median identify accelerating platform engineering "
        "before the market fully prices product delivery and infrastructure "
        "adoption; select the top 3 positive count-minus-median issuers at the "
        "first strictly later regular-session open and hold 20 sessions as a "
        "shared default-off candidate pool."
    )

    result = fp.infer_fingerprint(hypothesis)

    assert result["data_source"] == "linux_mainline_signed_rc_contributions"
    assert result["gate_shape"] == "candidate_pool_top3_20d"


def test_linux_mainline_signed_rc_frozen_family_builder_inputs_keep_fingerprint():
    result = fp.infer_fingerprint(
        "linux_mainline_signed_rc_candidate_pool",
        "admit standalone candidates from signed Linux mainline RC "
        "contribution acceleration",
        "top3_h20_prior8_median_v1",
    )

    assert result["data_source"] == "linux_mainline_signed_rc_contributions"
    assert result["gate_shape"] == "candidate_pool_top3_20d"


@pytest.mark.parametrize(
    "text",
    [
        "generic Linux kernel CVE security news sentiment candidate pool",
        "entity_theme_news Linux kernel CVE disclosure forward observer",
        "NVD CVE change history for a Linux kernel vulnerability",
        "Linux mainline release news and vulnerability coverage",
    ],
)
def test_linux_cve_and_news_text_does_not_match_signed_rc_contribution_source(text):
    assert fp.infer_fingerprint(text)["data_source"] != (
        "linux_mainline_signed_rc_contributions"
    )
