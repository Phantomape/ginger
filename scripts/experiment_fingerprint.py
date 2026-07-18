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
    # Duplicate reservations are accounting rows, not evidence from the
    # substantive source named in the losing ticket. Route them first so one
    # duplicate cannot relabel the shared accounting family and consume that
    # source's saturation budget.
    ("duplicate_reservation_accounting", (
        "duplicate_reservation_accounting", "duplicate reservation accounting",
    )),
    # NVD CVE Change History is a point-in-time vulnerability-analysis source,
    # distinct from CISA's already-exploited KEV subset and generic security
    # news. Keep compound phrases here: bare "nvd" would also match NVDA.
    ("nvd_cve_change_history", (
        "nvd_cve_change_history", "nvd cve change history",
        "official nvd cve", "nvd initial analysis",
        "national vulnerability database change history",
        "cvehistory/2.0", "cvehistory 2.0", "cvehistory",
        "cve change history initial analysis",
        "initial analysis added cpe configuration",
        "nvd_initial_analysis", "nvd initial-analysis",
    )),
    # Effective-dated core membership is a measurement ledger, not a generic
    # universe expansion or entry-admission rule.  Keep only compound policy,
    # module, and ticket spellings here so ordinary entry/universe experiments
    # continue to route to their existing populations.
    ("core_universe_membership_ledger", (
        "core_universe_membership_ledger", "core universe membership ledger",
        "entry_universe_ledger", "entry universe ledger",
        "legacy_core_pit_universe_measurement_repair",
        "core_universe_membership_identity",
        "git-proven effective-dated core entry eligibility",
        "git proven effective dated core entry eligibility",
        "backtest core entry eligibility source",
        "core entry-eligibility identity", "core entry eligibility identity",
        "git_effective_lower_bound_and_forward_membership_ledger",
    )),
    # Federal Reserve H.8 dated releases are a weekly, as-published bank-size
    # balance-sheet source. Keep the official source and policy spellings
    # coupled: bare bank, deposit, loan, KRE, or KBE fragments would capture
    # Companyfacts ratios and unrelated bank-ETF experiments.
    ("fed_h8_weekly_release_vintages", (
        "fed_h8_weekly_release_vintages",
        "fed h8 weekly release vintages",
        "federal reserve h.8 dated release",
        "federal reserve h8 dated release",
        "federal reserve h.8 weekly release",
        "federal reserve h8 weekly release",
        "h.8 bank-size release vintage",
        "h8 bank-size release vintage",
        "h8 bank size release vintage",
        "fed_h8_weekly_release_bank_size_pair",
        "fed h8 weekly release bank size pair",
        "fed_h8_small_large_bank",
        "fed h8 small large bank",
        "fed_h8_weekly_kre_kbe",
        "fed h8 weekly kre kbe",
    )),
    # TSA checkpoint-throughput reports are an official passenger-volume
    # source, distinct from generic airport, travel, staffing, or distributed-
    # system throughput wording. Keep the agency and checkpoint/throughput
    # terms coupled so broad fragments cannot consume unrelated source budgets.
    ("tsa_checkpoint_throughput", (
        "tsa_checkpoint_throughput",
        "tsa checkpoint-throughput",
        "tsa checkpoint throughput",
        "tsa_weekly_checkpoint_throughput",
        "tsa weekly checkpoint-throughput",
        "tsa weekly checkpoint throughput",
        "official tsa foia weekly checkpoint-throughput",
        "official tsa foia weekly checkpoint throughput",
        "transportation security administration checkpoint throughput",
    )),
    # NHTSA defect-investigation openings and CPSC recall publications are one
    # federal product-safety event surface. Keep agency names coupled to their
    # official event/field spellings: bare words such as "recall", "defect",
    # or "investigation" would collide with FDA enforcement and generic news.
    ("federal_product_safety_official_events", (
        "federal_product_safety_official_events",
        "federal product safety official events",
        "official_product_safety_event", "official product safety event",
        "remaining_official_safety_source_batch",
        "remaining official safety source batch",
        "nhtsa defect-investigation", "nhtsa defect investigation",
        "nhtsa investigation opening", "nhtsa investigation openings",
        "nhtsa odate",
        "cpsc recall publication", "cpsc recall publications",
        "cpsc recalldate", "cpsc lastpublishdate",
    )),
    # ClinicalTrials.gov first-result postings are a versioned regulatory
    # event source, distinct from generic biotech news and Drugs@FDA approval
    # records. Keep the official source/field spellings near the front and do
    # not use broad fragments such as "trial", "phase3", or "results".
    ("clinicaltrials_results", (
        "clinicaltrials_results", "clinicaltrials results",
        "clinicaltrials.gov", "clinicaltrials gov", "clinicaltrials",
        "resultsfirstpostdate", "results_first_post_date",
    )),
    # FDA Orange Book monthly Additions/Deletions PDFs are a versioned drug-
    # product release source, distinct from the current-snapshot Drugs@FDA
    # application table and generic FDA approval news.  Keep this ahead of
    # Companyfacts because the word "release" contains its broad "lease"
    # keyword and would otherwise route the source into the wrong population.
    ("fda_orange_book_monthly_additions_deletions", (
        "fda_orange_book", "fda orange book",
        "orange_book_newa", "orange book newa",
        "orange_book_newa_release_basket",
        "orange book newa release basket",
        "orange book monthly additions/deletions",
        "orange book monthly additions deletions",
        "fda orange book additions/deletions",
        "fda orange book additions deletions",
        "official fda orange book",
    )),
    # FDA FAERS quarterly adverse-event extracts are a post-market safety
    # monitoring source, distinct from approval decisions, Orange Book product
    # releases, and device-enforcement reports.  Keep only the official acronym
    # and compound system names here; bare "FDA", "adverse", or "event" would
    # over-match several adjacent regulatory surfaces.
    ("faers", (
        "faers_serious_outcome_share", "faers serious-outcome share",
        "faers serious outcome share", "official fda faers",
        "fda faers quarterly", "faers quarterly ascii",
        "fda adverse-event reporting system",
        "fda adverse event reporting system",
        "fda adverse-event monitoring system",
        "fda adverse event monitoring system",
    )),
    # FDA 510(k) clearances are a releasable device-decision source, distinct
    # from weekly Device Enforcement Reports and generic device/news wording.
    # Keep compound source phrases ahead of enforcement and OHLCV relations;
    # never use bare "FDA", "device", "clearance", or "510" fragments.
    ("fda_510k_clearance", (
        "fda_510k_clearance", "fda 510k clearance",
        "fda_510k_traditional_clearance", "fda 510k traditional clearance",
        "fda 510(k) clearance", "fda 510k", "fda 510(k)",
        "releasable_510k", "releasable 510k", "releasable 510(k)",
        "releasable 510(k) database", "releasable 510k database",
        "openfda_device_clearance", "openfda device clearance",
        "openfda device 510k", "openfda device 510(k)",
        "open.fda.gov/apis/device/510k", "open.fda.gov device 510k",
    )),
    # FDA Device Enforcement Reports are a weekly, public recall source,
    # distinct from Drugs@FDA application approvals and generic recall news.
    # Keep only compound official-source phrases here: broad fragments such as
    # "FDA", "Class I", "recall", or "report_date" would over-match adjacent
    # regulatory and news surfaces.
    ("fda_device_enforcement", (
        "fda_device_enforcement", "fda device enforcement",
        "fda_device_class1_enforcement", "fda device class i enforcement",
        "fda device class 1 enforcement",
        "openfda_device_enforcement", "openfda device enforcement",
        "official_openfda_device_enforcement",
        "official openfda device enforcement",
        "fda weekly device enforcement report",
        "device enforcement report class i",
        "device enforcement report class 1",
    )),
    # A complete, aligned panel of attempted strategy return streams is its
    # own research-governance surface.  Keep it ahead of generic OHLCV and
    # portfolio MTM wording so DSR/PSR work cannot silently fall into `other`.
    ("trial_return_panel", (
        "trial_return_panel", "trial return panel", "deflated sharpe",
        "deflated_sharpe", "dsr probability", "probabilistic sharpe",
        "probabilistic_sharpe", "effective trial count",
        "complete sharpe selection pool",
        "trial-adjusted sharpe", "trial adjusted sharpe",
        "trial_adjusted_sharpe",
    )),
    # Drugs@FDA original-application approvals are an official regulatory
    # source, not generic FDA-approval news. Keep the distinctive product and
    # CDER/NDA/BLA phrases narrow so ordinary biotech headlines do not consume
    # this source's novelty/saturation budget.
    ("drugsfda_approval", (
        "drugsfda_approval", "drugsfda approval", "drugsfda",
        "drugs@fda", "drugsatfda", "official_drugsfda",
        "official drugsfda", "drugsfda cder", "drugsfda bulk",
        "cder original nda/bla", "cder original nda bla",
        "official fda original nda/bla", "official fda original nda bla",
    )),
    # CFTC Traders in Financial Futures (TFF) annual positioning files are a
    # distinct weekly source. Keep this ahead of generic macro/OHLCV and
    # allocator wording so ranking consumers cannot escape through `other` or
    # be counted against a proxy-price surface.
    ("cftc_tff_positioning", (
        "cftc_tff_positioning", "cftc_tff", "cftc tff",
        "traders in financial futures", "cftc commitments of traders",
        "cftc cot positioning", "fut_fin_txt",
        "asset_mgr_positions", "asset mgr positions",
        "lev_money_positions", "lev money positions",
        "institutional positioning", "leveraged funds positioning",
    )),
    # Wikimedia per-article reader counts are an issuer-attention source, not
    # estimate-revision ``surprise`` or generic event/news attention. Keep the
    # source near the front so those downstream mechanism words cannot route a
    # Wikimedia trial into an unrelated frozen population.
    ("wikimedia_pageviews", (
        "wikimedia_pageviews", "wikimedia pageviews",
        "wikimedia analytics api", "wikipedia pageviews",
        "wikipedia page views", "enwiki pageviews", "enwiki page views",
        "pageviews per article", "pageviews/per-article",
        "canonical issuer pageviews", "canonical company pageviews",
    )),
    # Official Treasury auction-result XML is a discrete demand/microstructure
    # source, not FRED yield-curve context or generic forward replacement
    # attribution. Keep compound auction-result and bid-to-cover spellings near
    # the front; avoid bare "Treasury" or "auction" tokens, which would collide
    # with curve/macroeconomic studies and unrelated auction mechanisms.
    ("treasury_auction_results", (
        "treasury_auction_results", "treasury auction results",
        "official treasury auction result xml",
        "official treasury auction results xml",
        "treasury auction result xml", "treasury auction results xml",
        "treasury_auction_bid_to_cover", "treasury auction bid-to-cover",
        "treasury auction bid to cover", "auction bid-to-cover",
        "auction bid to cover", "treasury_nominal_auction_btc",
        "treasury nominal auction btc", "bid-to-cover microstructure",
        "bid to cover microstructure", "auction demand microstructure",
        "treasury auction demand", "treasury auction microstructure",
        "bid_to_cover_ratio", "indirect_bidder_accepted",
        "treasury_auction_demand_microstructure",
        "treasury_auction_indirect_bidder_share",
        "treasury auction indirect bidder share",
        "direct_bidder_accepted", "primary_dealer_accepted",
    )),
    # Chicago Fed NFCI is an official weekly composite of money, debt,
    # equity, and banking conditions. Keep it ahead of generic Companyfacts
    # financial/earn keywords and macro proxy families so NFCI trials share
    # their true evidence surface.
    ("chicago_fed_nfci", (
        "chicago_fed_nfci", "chicago fed nfci",
        "chicago fed national financial conditions index",
        "national financial conditions index", "nfci easing",
        "nfci_below_zero", "lagged_nfci", "fred series nfci",
    )),
    # Freddie Mac's weekly primary mortgage-rate survey is a direct housing
    # demand source, not generic OHLCV momentum or Treasury-curve context.
    ("fred_mortgage_rate", (
        "fred_mortgage_rate", "fred mortgage rate", "mortgage30us",
        "primary mortgage market survey", "weekly mortgage-rate",
        "weekly mortgage rate", "mortgage rate relief",
    )),
    # FRED's 10Y-minus-2Y Treasury spread is an official yield-curve source,
    # not generic OHLCV relation context or a Companyfacts margin ratio. Keep
    # it ahead of those families so curve experiments share one true surface.
    ("fred_treasury_curve", (
        "fred_treasury_curve", "fred treasury curve", "t10y2y",
        "2s10s treasury", "2s10s curve", "treasury spread",
        "treasury curve steepening", "yield curve steepening",
        "term spread",
    )),
    # Direct ICE BofA credit-spread observations are economically distinct
    # from HYG/JNK ETF-price proxies. Keep the official FRED series ahead of
    # credit_risk_etf so future trials and saturation checks use the true
    # risk-transfer source rather than the proxy population.
    ("direct_credit_spread", (
        "direct_credit_spread", "direct credit spread",
        "bamlh0a0hym2", "high-yield oas", "high yield oas",
        "option-adjusted spread", "option adjusted spread",
        "ice bofa us high yield index", "fred high yield oas",
        "fred_high_yield_oas", "oas20_cross_below",
    )),
    # Cboe SKEW is an option-implied equity tail-risk-premium source, not
    # generic forward replacement or cross-sectional return skew. Keep it
    # above those broad families so source saturation counts the real surface.
    ("cboe_skew", (
        "cboe_skew", "cboe skew", "skew index", "skew20",
        "equity-tail-risk", "equity tail risk", "tail-risk premium",
        "tail risk premium",
    )),
    # Cboe VVIX measures equity volatility-of-volatility and is distinct from
    # both the VIX9D/VIX term-structure surface and generic replacement-value
    # wording. Keep it first so candidate-pool trials share one true source key.
    ("cboe_vvix", (
        "cboe_vvix", "cboe vvix", "vvix", "vol-of-vol", "vol of vol",
        "volatility of volatility", "vvix20", "vvix 20-session",
    )),
    # Cboe OVX measures oil/USO option-implied volatility. Keep it ahead of
    # generic forward-replacement and OHLCV relation wording so oil-risk
    # candidate pools share their real evidence surface.
    ("cboe_ovx", (
        "cboe_ovx", "cboe ovx", "ovx", "ovx20", "ovx 20-session",
        "crude oil etf volatility index", "oil volatility", "oil-volatility",
        "oil risk relief", "oil-risk relief",
    )),
    # ICE BofA MOVE is an option-implied Treasury-rate-volatility source, not
    # generic forward replacement or OHLCV regime context. Keep it first so
    # downstream candidate/replacement wording cannot hide the source surface.
    ("move_rate_volatility", (
        "move_rate_volatility", "move rate volatility", "move index",
        "ice bofa move", "ice bofaml move", "treasury rate volatility",
        "treasury-rate-volatility", "move20", "move 20-session",
        "move relief", "move-relief", "move_relief",
    )),
    # Credit-risk ETF context is a separate cross-asset population. Keep this
    # above generic forward-replacement wording so HYG/JNK materialization and
    # fixed credit-relief candidate tests share one saturation key.
    ("credit_risk_etf", (
        "credit_risk_etf", "credit risk etf", "credit-relief", "credit relief",
        "credit_relief", "hyg/jnk", "hyg_jnk", "hyg and jnk", "hyg jnk",
        "hyg versus jnk",
        "high-yield credit relief", "high yield credit relief",
    )),
    # Cboe option-implied volatility term structure is an independent market
    # state source.  Keep it above core-entry/regime/OHLCV families so a
    # downstream admission gate is counted against the Cboe surface rather
    # than whichever response shape consumes it (exp-20260710-020).
    ("cboe_volatility_term_structure", (
        "cboe_volatility_term_structure", "cboe volatility term structure",
        "vix9d", "vix9d/vix", "vix9d versus vix", "vix9d vs vix",
        "vix term structure", "volatility term structure backwardation",
    )),
    # Kova snapshot rows are their own population: probes on the same Kova
    # current-row batch must share one machine key (the observed-only streak
    # gate counts per data_source), and they are not the canonical SEC13F/
    # rs-proxy surfaces even when the joined field comes from those.
    ("kova_snapshot", ("kova",)),
    # GDELT 2.0 DOC/GKG historical news tone/volume archive (exp-20260709-020).
    ("gdelt_news_tone", (
        "gdelt", "gdelt_news_tone", "gdelt news tone", "news_tone_archive",
        "tone_shock", "tone shock",
    )),
    # USAspending transaction obligations are a structured federal-spending
    # source, distinct from agency-authored DoD contract announcements. Keep
    # its source/field names ahead of the DoD press-release family and avoid
    # broad words such as "contract", "award", or "obligation" on their own.
    ("usaspending_obligation", (
        "usaspending_obligation", "usaspending obligation",
        "usaspending", "usaspending.gov", "usaspending gov",
        "federal_action_obligation", "federal action obligation",
        "base_and_all_options_value", "base and all options value",
    )),
    # Official DoD/war.gov daily Contracts press release (exp-20260711-020):
    # the awarding agency's own same-day publication, not SEC filing text.
    # Keep it above generic contract/companyfacts wording so award-source
    # probes share one machine key for streak/saturation accounting.
    ("dod_contract_award", (
        "dod_contract_award", "dod contract award", "dod contract-award",
        "dod daily contract", "dod_daily_contract", "war.gov contracts",
        "dod_new_contract", "dod new contract",
        "dod_new_contract_revenue", "dod contract revenue materiality",
        "war.gov/news/contracts", "defense.gov contracts",
        "department of war contracts", "department of defense contracts",
        "contract-award announcement", "contract award announcement",
        "contract_award_announcement", "dod award", "dod_award",
        "pentagon contract",
    )),
    ("candidate_meta_label", (
        "candidate_meta_label", "candidate meta label", "candidate_meta_labeling",
        "candidate meta labeling", "meta_label", "meta label", "meta-label",
        "meta_labeler", "meta labeler", "candidate_training_table",
        "candidate training table", "training_table_readiness",
        "training table readiness", "model_readiness", "model readiness",
        "candidate_meta_label_v1",
    )),
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
    # Broker-authoritative executions are a separate evidence population from
    # quote-side capital flow, borrow, and the derived live-drift consumer.
    # Keep this specific key first so future lifecycle/fee/exit-drift work is
    # counted against the materialized deal-history surface created by
    # exp-20260712-001 instead of escaping through ``other``.
    ("moomoo_execution_history", (
        "moomoo_execution_history", "moomoo execution history",
        "broker_execution_ledger", "broker execution ledger",
        "broker_authoritative_execution", "broker-authoritative execution",
        "broker_authoritative_exit", "broker-authoritative exit",
        "broker deal history", "broker fill ledger", "broker fills ledger",
        "order_fee_snapshots", "order fee snapshots",
        "fill_lifecycle_links", "fill lifecycle links",
    )),
    ("moomoo_capital_flow", (
        "moomoo_capital_flow", "moomoo capital flow", "capital_flow", "capital-flow", "fund_flow",
        "large_order_flow",
    )),
    ("crypto_sleeve", (
        "crypto_sleeve", "crypto sleeve", "btc_spot", "btc spot", "btc/usd", "btc-usd", "btc usd",
        "bitcoin spot", "crypto_positions", "daily_ema20_ema100_spot_trend",
    )),
    ("ortex_borrow", (
        "ortex", "borrow_fee", "borrow fee", "loan_fee", "loan fee", "utilization",
        "iborrowdesk", "shortable_stock", "shortable stock", "lendable availability",
    )),
    ("borrow_availability", (
        "moomoo_borrow", "moomoo borrow", "borrow_availability", "borrow availability",
        "loan_availability", "loan availability", "short_sell_rate", "short sell rate",
        "short_available_volume", "short available volume",
    )),
    ("space_catalyst", (
        "space_catalyst", "space catalyst", "space_catalyst_event_state",
        "space catalyst event state", "space_catalyst_shadow", "space catalyst shadow",
        "space_catalyst_event_ledger", "space catalyst event ledger",
        "space_catalyst_observation_slot", "space catalyst observation slot",
    )),
    ("chop_forward_observer", (
        "chop_forward_observer", "chop forward observer",
        "chop_forward", "chop forward",
        "forward_chop", "forward chop",
        "chop-labeled forward", "chop labeled forward",
        "chop-day forward", "chop day forward",
        "chop_row", "chop row", "chop rows",
    )),
    ("sec13d_ownership", (
        "sec13d", "sec_13d", "sec 13d", "schedule 13d", "sc 13d",
        "13d13g", "13d/13g", "13d 13g", "sec_13d13g", "sec 13d13g",
        "13d", "13g", "item4_governance", "item4 governance",
        "item-4 governance", "item4_campaign", "item4 campaign",
        "item-4 campaign", "campaign_provenance", "campaign provenance",
        "holder_stake", "holder stake",
    )),
    ("sec_filing_features", (
        "sec_filing_features", "sec filing features",
        "sec_filing_text_plus_companyfacts", "sec filing text plus companyfacts",
        "filing_feature_mosaic", "filing feature mosaic",
        "sec filing feature mosaic", "source_credibility_bucket",
        "source credibility bucket", "predictability_mosaic_bucket",
        "predictability mosaic bucket", "low_volume_predictability_bucket",
        "low volume predictability bucket", "text_direction_vs_price_bucket",
        "text direction vs price bucket", "same_accession_facts",
        "same accession facts",
    )),
    # Entity-theme news ledgers can also discuss settled replacement value.
    # Keep their explicit observer/family names ahead of the generic forward
    # replacement source so the underlying evidence surface remains stable.
    ("entity_theme_news", (
        "entity_theme_news", "entity-theme news", "entity theme news",
        "entity_theme_news_observer", "entity-theme news observer",
        "entity theme news observer",
    )),
    ("forward_replacement_value", (
        "forward_replacement", "forward replacement", "forward_replacement_value",
        "replacement_value", "replacement value", "settled forward", "closed forward",
        "entry_exhaustion", "entry exhaustion", "entry_regime", "entry regime",
    )),
    ("cisa_kev", ("cisa_kev", "cisa", "kev", "known_exploited_vulnerabilities")),
    ("intraday_structured_news", (
        "intraday_structured_news", "intraday structured news",
        "intraday_news_structured", "intraday news structured",
        "intraday_structured_event", "intraday structured event",
        "intraday_structured_relation", "intraday structured relation",
        "intraday_trade_news", "intraday trade news",
    )),
    ("exit_lifecycle", (
        "exit_lifecycle", "exit lifecycle", "exit_lifecycle_shadow",
        "exit lifecycle shadow", "exit_lifecycle_shadow_log",
        "exit lifecycle shadow log", "exit advisory lifecycle",
        "advisory lifecycle", "has_advisory_event", "has advisory event",
        "no_advisory_event", "no advisory event", "breach_status",
        "breach status", "trailing_stop_from_hwm", "trailing stop from hwm",
        "drawdown_from_hwm", "drawdown from hwm",
    )),
    ("intraday_advisory", (
        "intraday_advisory", "intraday advisory", "intraday_review", "intraday review",
        "intraday risk review", "risk-review", "shadow_action", "shadow action",
        "advisory_shadow_action", "advisory shadow action",
        "primary_advisory_shadow_action", "primary advisory shadow action",
        "exit advisory", "breached", "approaching",
    )),
    ("news_event_exposure", (
        "news_event_exposure", "news event exposure",
        "news_event_second_order", "news event second order",
        "news_second_order", "news second order",
        "second_order_exposure", "second-order exposure", "second order exposure",
        "structured-news exposure", "structured news exposure",
    )),
    ("prediction_market_event", (
        "prediction_market", "prediction-market", "prediction market", "kalshi", "polymarket",
        "event_odds", "event odds",
    )),
    ("entity_theme_news", ("entity_theme", "entity-theme", "entity theme", "theme_news", "news_theme", "event_theme")),
    ("live_position_control", (
        "live_position_control", "live position control", "live position-control",
        "position_control", "position control", "position-control",
        "source_signal_rejected_alpha", "rejected-source live", "rejected source live",
        "discretionary_live_mirror", "broker_order_coverage",
        "manual_bracket_orders", "open live positions",
    )),
    ("live_drift_reconciliation", ("live_drift", "live drift", "fill_drift", "trajectory_drift", "live_reconciliation")),
    ("pilot_scorecard", (
        "pilot_scorecard", "pilot scorecard", "pilot_recommendations", "pilot recommendations",
        "scorecard_kill", "scorecard kill", "kill_rule_readiness", "kill rule readiness",
        "graduation_readiness", "graduation readiness", "graduate_rule", "graduate rule",
    )),
    ("portfolio_covariance_lane", (
        "portfolio_covariance", "portfolio covariance", "portfolio-lane", "portfolio lane",
        "portfolio_contribution", "portfolio contribution", "portfolio-contribution",
        "portfolio_contribution_gate", "gate 4-p",
        "daily_equity_overlay", "daily equity overlay", "mark_to_market", "mark-to-market",
        "daily mark to market", "mtm_overlay", "mtm overlay",
        "joint_chronological_covariance_capacity_portfolio_overlay",
        "old_train_frozen_joint_covariance_capacity_weights",
    )),
    ("microstructure_viability", (
        "microstructure_viability", "microstructure viability", "vol_normalized_tick",
        "vol-normalized tick", "tick_to_atr", "tick-to-atr", "tick_size_atr",
        "tick size atr", "small_tick", "small tick", "spread_to_atr", "spread-to-atr",
        "impact_reinforcement", "impact reinforcement",
    )),
    ("cash_feasible_core_book", (
        "cash_conflict_oldest_incumbent", "cash conflict oldest incumbent",
        "execution_cash_opportunity_cost_rotation",
        "cash opportunity cost rotation", "settled-cash admission",
        "settled cash admission", "cash_conflict_persistent_order_queue",
        "cash conflict persistent order queue", "cash_conflict_deferred_queue",
        "cash conflict deferred queue",
        "cash_conflict_unfilled_entry_fifo_persistence",
        "cash conflict unfilled entry fifo persistence",
    )),
    ("core_entry_admission", (
        "core_entry_admission", "core entry admission", "entry_admission",
        "entry admission", "admission_gate", "admission gate", "no_entry",
        "admission_overlay", "admission overlay", "core_admission", "core admission",
        "no-entry", "no entry", "pre_entry_no_entry", "pre-entry no-entry",
        "saved_trade_counterfactual", "saved trade counterfactual",
        "saved-trade counterfactual", "saved_trade_diagnostic",
        "saved trade diagnostic", "saved-trade diagnostic",
        "severe_haircut_no_entry", "severe haircut no-entry",
        "low_vol_quality_core_admission", "low-vol quality core admission",
        "high_vol_high_beta_admission", "high-vol high-beta admission",
    )),
    ("relative_value_spread", (
        "relative_value_spread", "relative value spread",
        "chop_pairs_spread", "chop pairs spread",
        "pair_spread", "pair-spread", "pair spread",
        "pairs_spread", "pairs-spread", "pairs spread",
        "pair_zscore", "pair zscore", "pair z-score",
        "spread_zscore", "spread zscore", "spread z-score",
        "long_short_spread", "long-short spread", "long short spread",
        "market_neutral_pair", "market-neutral pair", "market neutral pair",
        "cointegrated_pair", "cointegrated pair", "cointegration pair",
    )),
    ("deep_drawdown", ("deep_drawdown", "deep-drawdown", "deep drawdown", "drawdown_capitulation", "drawdown_breadth", "capitulation_breadth")),
    ("finra_short_interest", ("finra", "short_interest", "shortinterest", "borrow", "days_to_cover", "dtc")),
    ("form4_insider", ("form4", "form_4", "insider")),
    # Public Form N-PORT holdings are a registered-fund portfolio source,
    # distinct from Form 13F institutional ownership. Keep the spellings
    # narrow and ahead of 13F's broad ``holder`` keyword; bare "portfolio",
    # "fund", "holdings", or "holder" would collide with adjacent surfaces.
    ("sec_form_nport_public_holdings", (
        "sec_form_nport_public_holdings", "sec form n-port public holdings",
        "sec_nport", "sec n-port", "sec form n-port", "sec form nport",
        "form_n_port", "form n-port", "form nport",
        "nport public holdings", "n-port public holdings", "nport",
    )),
    ("sec13f_ownership", ("13f", "sec13f", "sponsorship", "holder")),
    ("filing_timeliness", ("timeliness", "filing_lag", "early_disclosure", "filing_recency", "recency", "disclosure_timing")),
    ("sec_filer_status", (
        "filer_status", "filer status", "filer-status", "accelerated_filer", "accelerated filer",
        "large_accelerated", "large accelerated", "non_accelerated", "non-accelerated",
        "smaller_reporting", "smaller reporting", "emerging_growth_company",
        "emerging growth company", "dei_status", "dei status", "dei_cover", "dei cover", "dei_cover_status",
        "cover_page_filer", "cover page filer", "cover_page_status", "cover page status",
        "cover_page_materialization", "cover page materialization", "cover_xbrl", "cover xbrl",
        "periodic_cover", "periodic cover", "entityfilercategory",
    )),
    ("sec_contract_relation", (
        "sec_contract_relation", "sec contract relation",
        "sec_contract_relation_provenance", "contract relation provenance",
        "sec_item101_contract_relation", "sec item101 contract relation",
        "item101 contract relation", "item101_contract_relation",
        "item 1.01 contract relation", "item 1.01 contract-relation",
        "item 1.01 contract", "public counterparty target",
        "public-counterparty target", "cik-linked customer-supplier",
        "cik linked customer supplier", "customer-supplier graph",
        "customer supplier graph",
    )),
    ("sec_text_event", ("sec_text", "8k", "item", "filing_text", "contract_economics", "backlog", "rpo", "guidance", "narrative", "complexity", "submissions")),
    # USDA Foreign Agricultural Service Export Sales Reporting releases are
    # an official physical-demand source, distinct from issuer accounting and
    # generic trade data. Keep only compound program/source spellings here:
    # bare agency, commodity, export, or sales words would over-match adjacent
    # USDA reports, Census trade data, and Companyfacts growth hypotheses.
    ("usda_fas_export_sales", (
        "usda_fas_export_sales", "usda fas export sales",
        "usda foreign agricultural service weekly export sales reporting",
        "usda foreign agricultural service export sales reporting",
        "foreign agricultural service weekly export sales reporting",
        "foreign agricultural service export sales reporting program",
        "usda weekly export sales report",
    )),
    # EIA Weekly Petroleum Status Report first-release inventory rows are an
    # official physical-supply event source, distinct from SEC Companyfacts
    # inventory accounting. Keep agency and report names coupled: bare "EIA",
    # "inventory", "crude", or "petroleum" would capture adjacent surfaces.
    ("eia_wpsr_inventory", (
        "eia_wpsr_inventory", "eia wpsr inventory",
        "eia_wpsr", "eia wpsr",
        "eia weekly petroleum status report",
        "weekly petroleum status report",
        "wpsr table 4", "wpsr first-release", "wpsr first release",
    )),
    # FDIC Call Report financials and their official QBP publication calendar
    # are a bank-funding source distinct from SEC Companyfacts ratios. Keep
    # compound source phrases ahead of generic asset/debt/allocator wording;
    # bare "asset" or "deposit" would over-match unrelated fundamentals.
    ("fdic_call_report_financials", (
        "fdic_call_report_financials", "fdic call report financials",
        "fdic_call_report_deposit", "fdic call report deposit",
        "fdic_qbp_deposit", "fdic qbp deposit",
        "fdic_deposit_franchise", "fdic deposit franchise",
        "fdic quarterly banking profile",
        "bankfind call report",
    )),
    # PCAOB Form AP identifies the audit firm and engagement partner attached
    # to an issuer audit.  This is regulatory personnel provenance, not an
    # OHLCV peer relation merely because a downstream policy buys a peer.
    # Keep compound source spellings narrow and ahead of the generic `peer`
    # route so this surface gets its own saturation / observed-only budget.
    ("pcaob_form_ap", (
        "pcaob_form_ap", "pcaob form ap",
        "official pcaob form ap", "pcaob firmfilings",
        "pcaob firm filings", "pcaob engagement-partner",
        "pcaob engagement partner", "form ap engagement-partner",
        "form ap engagement partner", "firmfilings.zip",
        "regulatory_audit_uncertainty_peer_substitution",
    )),
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
        "session semivariance", "session_semivariance", "downside semivariance",
        "overnight-versus-intraday", "overnight versus intraday",
        "transfer entropy", "transfer_entropy", "directed information",
    )),
    ("ohlcv_momentum", ("momentum", "winner", "continuation", "extension", "alpha_score", "rs20")),
]

_GATE_SHAPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # One weekly H.8 release chooses the direction of an equal-gross KRE/KBE
    # pair until the next release. Require a compound policy/family spelling
    # so generic pair spreads and issuer-ranking allocators keep their routes.
    ("weekly_relative_value_allocator", (
        "weekly_relative_value_allocator",
        "weekly relative-value allocator",
        "weekly relative value allocator",
        "fed_h8_small_large_bank_deposit_c_and_i_lag4_weekly_kre_kbe_pair_v1",
        "fed_h8_weekly_kre_kbe_pair_direction",
        "fed_h8_weekly_release_bank_size_pair",
        "next week kre versus kbe relative return",
        "weekly market-neutral kre/kbe relative-value allocator",
        "weekly market neutral kre kbe relative value allocator",
    )),
    # Replaying membership eligibility as of each decision date is a distinct
    # measurement shape from either static candidate-pool expansion or an
    # alpha entry-admission filter.  Exact compound spellings avoid capturing
    # generic uses of "entry", "eligibility", or "universe".
    ("point_in_time_entry_eligibility", (
        "point_in_time_entry_eligibility", "point in time entry eligibility",
        "point-in-time entry eligibility",
        "entry_universe_ledger", "entry universe ledger",
        "legacy_core_pit_universe_measurement_repair",
        "git-proven effective-dated core entry eligibility",
        "git proven effective dated core entry eligibility",
        "backtest core entry eligibility source",
        "core entry-eligibility identity", "core entry eligibility identity",
        "immutable daily entry-eligibility replay",
        "immutable daily entry eligibility replay",
        "git_effective_lower_bound_and_forward_membership_ledger",
    )),
    ("trial_adjusted_significance", (
        "trial_adjusted_significance", "trial adjusted significance",
        "deflated sharpe", "deflated_sharpe", "dsr probability",
        "probabilistic sharpe", "probabilistic_sharpe",
        "effective trial count", "selection pool complete",
        "trial_adjusted_sharpe",
    )),
    # A publication-dated Treasury auction event drives one inverse-duration
    # ETF position from the next session open through the fifth session close.
    # Require the explicit policy/family or TBT-event spelling so generic 5d,
    # ETF, replacement-value, and macro-event experiments keep their routes.
    ("event_driven_inverse_treasury_etf_5d", (
        "event_driven_inverse_treasury_etf_5d",
        "event driven inverse treasury etf 5d",
        "event-driven inverse treasury etf 5d",
        "treasury_auction_bid_to_cover_tbt_event_response",
        "treasury auction bid-to-cover tbt event response",
        "treasury auction bid to cover tbt event response",
        "treasury_nominal_auction_btc_trailing12_weak_tbt_5session",
        "treasury nominal auction btc trailing12 weak tbt 5session",
        "tbt event response", "tbt_event_response",
        "tbt 5-session event sleeve", "tbt five-session event sleeve",
        "next-session-open to fifth-session-close tbt",
        "next session open to fifth session close tbt",
    )),
    # One publication event enters a fixed basket and holds it for ten
    # sessions. This is neither per-name top-1 candidate selection nor a
    # notional scalar; use only explicit policy-family spellings so generic
    # event, basket, energy, or holding-period text keeps its existing route.
    ("event_basket_10d", (
        "event_basket_10d", "event basket 10d", "event-to-basket 10d",
        "event to basket 10d", "fixed_event_basket_10d",
        "fixed event basket 10d",
        "eia_wpsr_first_release_destocking_energy_basket",
        "eia wpsr first release destocking energy basket",
        "production_visible_eia_wpsr_physical_supply_shock_energy_basket",
        "production visible eia wpsr physical supply shock energy basket",
        "eia_wpsr_first_release_three_inventory_destocking_fixed_energy_basket_10d",
        "usda_fas_export_sales_as_published_agriculture_basket",
        "usda fas export sales as published agriculture basket",
        "production_visible_usda_fas_export_sales_physical_demand_agriculture_basket",
        "production visible usda fas export sales physical demand agriculture basket",
        "usda_fas_export_sales_physical_demand_candidate_pool",
        "orange_book_newa_release_basket",
        "orange book newa release basket",
        "fda orange book monthly additions/deletions pdf newa basket",
        "fda orange book monthly additions deletions pdf newa basket",
        "fda_orange_book_fresh_newa_equal_weight_release_basket_nextopen_10d_v1",
    )),
    # A FAERS release ranks improving issuers into one standalone quarterly
    # basket.  Its explicit source/policy spellings must precede the generic
    # allocator "rank" fallback and the generic top-1 candidate-pool bucket.
    ("standalone_quarterly_candidate_pool", (
        "faers_serious_outcome_share_improvement_quarterly_candidate_pool",
        "faers serious-outcome share improvement quarterly candidate pool",
        "faers serious outcome share improvement quarterly candidate pool",
        "faers_serious_share_improvement_basket",
        "faers serious-share improvement basket",
        "faers serious-outcome share is a safety-quality signal",
        "faers quarterly safety-quality candidate pool",
        "fda adverse-event monitoring system quarterly candidate pool",
    )),
    # A Form-AP event selects one unaffected industry peer and holds it for
    # twenty sessions.  Keep the explicit family/policy spellings ahead of the
    # older generic peer-substitution top-1/10-day bucket.
    ("peer_substitution_candidate_pool_top1_20d", (
        "peer_substitution_candidate_pool_top1_20d",
        "peer substitution candidate pool top1 20d",
        "pcaob_form_ap_partner_change_peer_substitution",
        "pcaob form ap partner change peer substitution",
        "pcaob_partner_change_unaffected_industry_peer_candidate_source",
        "pcaob partner change unaffected industry peer candidate source",
        "original_issuer_primary_partner_change_same_industry_adv60_top1_h20",
        "original issuer primary partner change same industry adv60 top1 h20",
    )),
    ("peer_propagation_top1_10d", (
        "peer_propagation_top1_10d", "peer propagation top1 10d",
        "peer-substitution", "peer substitution", "peer_substitution",
        "winner-to-peer", "winner to peer", "winner_to_peer",
        "non-awarded peer", "non awarded peer", "non_awarded_peer",
        "sector-budget-validation", "sector budget validation",
        "budget_validation",
    )),
    ("exit_kill_switch", (
        "exit_kill_switch", "exit kill switch", "lifecycle kill switch",
        "kill-switch", "kill switch", "reentry next open",
        "re-entry next-open", "relief invalidation exit",
        "relief_kill_switch", "sma20_reentry_next_open_kill_switch",
    )),
    # The FDIC policy is a fixed quarterly top-5 / 20-session candidate pool,
    # not an instance of the older top-1 / 10-day saturation cell. Keep only
    # its compound policy-family spellings here and ahead of generic ranking.
    ("candidate_pool_top5_20d", (
        "fdic_qbp_deposit_franchise_repair",
        "fdic qbp deposit franchise repair",
        "fdic_call_report_deposit_quality_candidate_pool",
        "fdic call report deposit quality candidate pool",
    )),
    # This source is first introduced as a fixed top-2 candidate pool. Keep
    # its explicit family key above generic "replacement value" wording so
    # saturation accounting follows the tested response shape.
    ("candidate_pool_top1_10d", (
        "mortgage_rate_relief_residential_leadership",
        "mortgage rate relief residential leadership",
        "mortgage30us_two_consecutive_weekly_declines_residential_construction_leadership",
        "high_yield_oas_credit_relief_shared_paper",
        "high yield oas credit relief stock leadership",
        "high-yield oas credit-relief stock leadership",
        "fred_high_yield_oas20_first_cross_below_credit_relief",
        "cboe_skew_relief_stock_leadership",
        "cboe skew index equity-tail-risk relief stock leadership",
        "skew20_cross_below_tail_risk_relief_stock_leadership",
        "cboe_vvix_relief_stock_leadership",
        "cboe vvix vol-of-vol relief stock leadership",
        "vvix20_cross_below_vol_of_vol_relief_stock_leadership",
        "cboe_ovx_oil_volatility_relief_energy_leadership",
        "cboe ovx oil-volatility relief energy leadership",
        "ovx20_cross_below_energy_leadership",
        "move_rate_volatility_relief_stock_leadership",
        "move20_cross_below_rate_volatility_relief_stock_leadership",
    )),
    ("forward_observer", (
        "chop_forward_observer", "chop forward observer",
        "forward_observer", "forward observer",
        "forward-row reopen", "forward row reopen",
        "forward rows accrue", "forward-row materialization",
        "forward row materialization",
    )),
    ("microstructure_attribution", (
        "microstructure_viability", "microstructure viability", "vol_normalized_tick",
        "vol-normalized tick", "tick_to_atr", "tick-to-atr", "tick_size_atr",
        "tick size atr", "spread_to_atr", "spread-to-atr",
    )),
    ("portfolio_contribution", (
        "portfolio_contribution", "portfolio contribution",
        "portfolio_contribution_gate", "funded portfolio contribution",
        "capital_conserving_portfolio_contribution",
        "capital-conserving portfolio-contribution", "gate 4-p",
    )),
    ("portfolio_daily_equity_overlay", (
        "portfolio_covariance", "portfolio covariance", "daily_equity_overlay",
        "daily equity overlay", "mark_to_market", "mark-to-market",
        "daily mark to market", "mtm_overlay", "mtm overlay",
        "joint_chronological_covariance_capacity_portfolio_overlay",
        "old_train_frozen_joint_covariance_capacity_weights",
    )),
    # One exact URL is one event-level portfolio decision. Require explicit
    # basket wording so ordinary entity-theme row attribution continues to use
    # the generic forward-attribution response shape.
    ("event_decision_basket", (
        "event_decision_basket", "event-decision-basket", "event decision basket",
        "exact-url-deduplicated event decision",
        "exact url deduplicated event decision",
        "url event basket", "url_event_basket",
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
    ("model_readiness", (
        "candidate_meta_label", "candidate meta label", "candidate_meta_labeling",
        "candidate meta labeling", "meta_label", "meta label", "meta-label",
        "candidate_training_table", "candidate training table",
        "training_table_readiness", "training table readiness",
        "model_readiness", "model readiness",
    )),
    ("incumbent_rotation", (
        "cash_conflict_oldest_incumbent", "cash conflict oldest incumbent",
        "execution_cash_opportunity_cost_rotation",
        "cash opportunity cost rotation", "oldest incumbent rotation",
    )),
    ("cash_conflict_deferred_queue", (
        "cash_conflict_persistent_order_queue",
        "cash conflict persistent order queue",
        "cash_conflict_deferred_queue", "cash conflict deferred queue",
        "cash_conflict_unfilled_entry_fifo_persistence",
        "cash conflict unfilled entry fifo persistence",
    )),
    ("entry_admission", (
        "core_entry_admission", "core entry admission", "entry_admission",
        "entry admission", "admission_gate", "admission gate", "no_entry",
        "entry_exclusion", "entry exclusion", "core_entry_exclusion",
        "core entry exclusion",
        "admission_overlay", "admission overlay", "core_admission", "core admission",
        "no-entry", "no entry", "pre_entry_no_entry", "pre-entry no-entry",
        "saved_trade_counterfactual", "saved trade counterfactual",
        "saved-trade counterfactual", "saved_trade_diagnostic",
        "saved trade diagnostic", "saved-trade diagnostic",
    )),
    ("pair_spread", (
        "relative_value_spread", "relative value spread",
        "chop_pairs_spread", "chop pairs spread",
        "pair_spread", "pair-spread", "pair spread",
        "pairs_spread", "pairs-spread", "pairs spread",
        "pair_zscore", "pair zscore", "pair z-score",
        "spread_zscore", "spread zscore", "spread z-score",
        "long_short_spread", "long-short spread", "long short spread",
        "market_neutral_pair", "market-neutral pair", "market neutral pair",
        "cointegrated_pair", "cointegrated pair", "cointegration pair",
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
