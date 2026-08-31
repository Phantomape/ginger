"""Clean-forward falsification contract freeze for cand-68d2f5dad2f903488307
(pre-event overshoot partial reversion), 2026-08-31.

Outcome-blind by construction: reads ONLY identity/status fields from the
estimate-revision outcome ledgers (decision ids, tickers, dates, direction,
eps identity fields, h*_status) plus pre-event OHLCV closes. No return,
PnL, or replacement-value field is ever loaded.

Why this exists: exp-20260831-001's pre-registered secondary report exposed
the non-quiet cohort's directional spreads, contaminating every decision with
a settled horizon as of the 2026-08-31 outcome fileset. This freeze binds the
adjacent candidate's falsification to (a) its own 2026-08-29 registration
wording and (b) decisions whose FIRST settlement (h5 close) happens after
2026-08-31. Bars below are frozen before any outcome access on the clean
slice and may not be changed afterwards.
"""
import json, glob, math, sqlite3, hashlib
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WAREHOUSE = REPO / 'data' / 'warehouse' / 'warehouse_main_hot.sqlite'
OUT = REPO / 'data' / 'alpha_search' / 'phase2_adjacent_overshoot_clean_forward_contract_20260831.json'
POOL = REPO / 'data' / 'alpha_search' / 'phase2_estimate_revision_candidate_pool_20260829.json'
CANDIDATE_ID = 'cand-68d2f5dad2f903488307'

PATH_SESSIONS = 5
MIN_PRIOR_EPS_ABS = 0.10

ALLOWED = {'decision_id', 'ticker', 'instrument_ticker', 'as_of_date',
           'revision_direction', 'decision_qualified', 'instrument_mapping_qualified',
           'actual_entry_date', 'usable_entry_date', 'entry_date',
           'eps_estimate', 'eps_estimate_delta_prev',
           'h5_status', 'h10_status', 'h20_status'}


def main():
    pool = json.load(open(POOL, encoding='utf-8'))
    cand = next(c for c in pool['candidates'] if c['candidate_id'] == CANDIDATE_ID)
    cand_sha = hashlib.sha256(json.dumps(cand, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    files = sorted(glob.glob(str(REPO / 'data/non_ohlcv/estimate_revision_outcomes_*.jsonl')))
    fileset = hashlib.sha256()
    rows = {}
    for f in files:
        raw = open(f, 'rb').read()
        fileset.update(hashlib.sha256(raw).digest())
        for line in raw.decode('utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            r = {k: v for k, v in r.items() if k in ALLOWED}
            if not r.get('decision_qualified') or r.get('revision_direction') not in ('up', 'down'):
                continue
            if not r.get('instrument_mapping_qualified'):
                continue
            did = r.get('decision_id')
            if not did or did in rows:
                continue
            rows[did] = r

    contaminated = sorted(d for d, r in rows.items() if r.get('h5_status') == 'closed')
    clean = {d: r for d, r in rows.items() if r.get('h5_status') != 'closed'}
    cont_sha = hashlib.sha256('\n'.join(contaminated).encode()).hexdigest()

    con = sqlite3.connect(WAREHOUSE)
    cur = con.cursor()
    cache = {}

    def closes_upto(t, as_of, n):
        if t not in cache:
            cache[t] = cur.execute(
                "SELECT date, close FROM ohlcv WHERE ticker=? ORDER BY date", (t,)).fetchall()
        return [r for r in cache[t] if r[0] <= as_of][-n:]

    counts = {'overshoot': 0, 'not_overshoot': 0, 'excluded_prior_eps_guard': 0,
              'excluded_insufficient_bars': 0, 'excluded_delta_sign_mismatch': 0}
    dirsplit = {'up': 0, 'down': 0}
    entries = {}
    for did, r in clean.items():
        t = r.get('instrument_ticker') or r.get('ticker')
        delta, eps = r.get('eps_estimate_delta_prev'), r.get('eps_estimate')
        if delta is None or eps is None or abs(eps - delta) < MIN_PRIOR_EPS_ABS:
            counts['excluded_prior_eps_guard'] += 1
            continue
        dir_sign = 1.0 if r['revision_direction'] == 'up' else -1.0
        if dir_sign * delta <= 0:
            counts['excluded_delta_sign_mismatch'] += 1
            continue
        implied = abs(delta / (eps - delta))
        bars = closes_upto(t, r['as_of_date'], PATH_SESSIONS + 1)
        if len(bars) < PATH_SESSIONS + 1:
            counts['excluded_insufficient_bars'] += 1
            continue
        closes = [c for _, c in bars]
        if dir_sign * math.log(closes[-1] / closes[0]) > implied:
            counts['overshoot'] += 1
            dirsplit[r['revision_direction']] += 1
            e = r.get('actual_entry_date') or r.get('usable_entry_date') or r.get('entry_date')
            entries[str(e)] = entries.get(str(e), 0) + 1
        else:
            counts['not_overshoot'] += 1

    contract = {
        'schema_version': 1,
        'artifact_kind': 'clean_forward_falsification_contract',
        'candidate_id': CANDIDATE_ID,
        'candidate_title': cand['title'],
        'frozen_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'generated_by': 'quant/experiments/adjacent_overshoot_clean_forward_contract_freeze_20260831.py',
        'outcome_blind': True,
        'registration_binding': {
            'source': str(POOL.relative_to(REPO)).replace('\\', '/'),
            'candidate_sha256': cand_sha,
            'registered_at': cand['created_at'],
            'note': 'All bar wording derives from this 2026-08-29 registration; the 2026-08-31 observed non-quiet contrast is contamination and shaped nothing here.'
        },
        'contamination_fence': {
            'reason': "exp-20260831-001's pre-registered secondary report exposed non-quiet cohort directional spreads on all decisions settled as of the 2026-08-31 fileset",
            'rule': "eligible decisions are exactly those whose h5_status != 'closed' in the frozen fileset below, plus every future qualified decision; equivalently, first settlement after 2026-08-31",
            'outcome_fileset_files': len(files),
            'outcome_fileset_sha256': fileset.hexdigest(),
            'contaminated_decision_count': len(contaminated),
            'contaminated_decision_ids_sha256': cont_sha
        },
        'frozen_conditioning_rule': {
            'wording_source': "registration gap_definition: 'Excess of the pre-event five-session price move over the repricing implied by the frozen consensus EPS update, in the update's direction.'",
            'market_prior_path': 'R5 = ln(close_A / close_{A-5}), A = last warehouse session <= as_of_date (registration market_prior units)',
            'implied_repricing': 'constant-multiple mapping: implied = |eps_estimate_delta_prev / (eps_estimate - eps_estimate_delta_prev)|; the only parameter-free reading of the registration wording',
            'overshoot_iff': 'dir_sign * R5 > implied, dir_sign = +1 (up) / -1 (down)',
            'guards': {
                'min_abs_prior_eps': MIN_PRIOR_EPS_ABS,
                'delta_sign_must_match_direction': True,
                'min_pre_event_bars': PATH_SESSIONS + 1,
                'fail_mode': 'exclude fail-closed'
            },
            'forbidden': 'no sigma/volatility envelope (that is the rejected quiet-tape family conditioning), no threshold moves after this freeze'
        },
        'treatment': {
            'wording_source': 'registration treatment.policy, frozen 2026-08-29',
            'down_overshoot': 'long cash-equity from the following tradable session (ledger entry clock), tradable leg',
            'up_overshoot': 'foregone-long avoidance evidence, no borrow, evidence-only leg',
            'horizons_gated': ['h5', 'h10'],
            'h20': 'reported only (registration half-life is H5-H10)',
            'costs': 'frozen outcome-ledger pipeline values (h*_return_pct / h*_replacement_value_* as persisted); no re-costing'
        },
        'falsifier_bars': {
            'wording_source': "registration falsifier: 'Exact-clock placebo on shuffled event dates, ticker shuffle within the mapped set, absence of decay in the unjustified residual, or failure to beat cash, SPY, QQQ and the displaced core sleeve under identical capital constraints.'",
            'B1_residual_decay': 'mean(h_ret | down_overshoot) - mean(h_ret | up_overshoot) > 0 at BOTH h5 and h10 on the clean conditioned slice',
            'B2_vs_cash': 'sum(h_replacement_value_vs_cash_usd | down_overshoot tradable leg) > 0 at h10; h5 reported',
            'B3_vs_spy_qqq': 'sum(h10_rv_vs_spy | down_overshoot) > 0 AND sum(h10_rv_vs_qqq | down_overshoot) > 0',
            'B4_date_placebo': 'real h10 reversion spread (simple next-open->10th-close methodology) > p90 of 200 shuffled-event-date draws',
            'B5_ticker_shuffle': 'real h10 reversion spread > p90 of 200 within-session ticker-shuffle draws',
            'seed': 20260901,
            'n_draws': 200,
            'all_bars_must_pass': True,
            'displaced_core_comparator': 'reported only: no per-decision displaced-core series exists in the outcome ledger; gating on it is structurally impossible (documented limitation, not a waived bar)',
            'result_ceiling': 'observed_only (research_pit price context; research_replay admission class)'
        },
        'sample_gates': {
            'per_gated_horizon_min_settled_conditioned_clean': 30,
            'per_direction_leg_min': 10,
            'fail_mode': 'do not run the falsification until every gate holds; no partial evaluation'
        },
        'reachability_evidence': {
            'clean_pool_h5_not_closed': len(clean),
            'frozen_rule_conditioned_stock': counts,
            'direction_split': dirsplit,
            'entry_dates': dict(sorted(entries.items())),
            'zero_arrival_conservative_eta': {
                'h5_ge_30': '2026-09-08 (33 decisions entered by 2026-08-26 close h5 by ~09-02; full 57 by ~09-08)',
                'h10_ge_30': '2026-09-11 (24 entered 08-24 close h10 ~09-08; cumulative 33 by ~09-10, 56 by ~09-11)'
            },
            'observed_arrival_rate': 'last-10-session qualified arrivals mean ~45/session (lumpy daily-batch feed); frozen-rule overshoot share of clean flow 57/166 evaluated'
        },
        'evaluation_trigger': {
            'event': 'daily outcome append brings clean conditioned settled counts to >=30 at h5 AND >=30 at h10 with both direction legs >=10 at each gated horizon, counted under the frozen conditioning rule and contamination fence',
            'then': 'reserve -> claim -> run the frozen falsification within the next alpha execution slot, <=24h wall clock',
            'recheck': 'constant-time count recomputation per hourly unit; no other work on this candidate before trigger'
        },
        'forbidden_after_freeze': [
            'any bar, threshold, seed, horizon, or conditioning change',
            'any evaluation touching contaminated decision ids',
            'any peek at clean-slice outcome values before the trigger fires and an experiment ID is reserved',
            'quiet-tape envelope reuse as conditioning (d-0013 family closure)'
        ],
        'trade_enabled': False
    }
    OUT.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('wrote', OUT)
    print('conditioned stock:', counts['overshoot'], dirsplit)
    print('candidate_sha256:', cand_sha)
    print('fileset_sha256:', fileset.hexdigest())


if __name__ == '__main__':
    main()
