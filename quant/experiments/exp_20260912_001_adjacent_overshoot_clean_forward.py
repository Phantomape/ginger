"""exp-20260912-001: adjacent pre-event overshoot clean-forward falsification (observed-only ceiling).

Frozen contract: data/alpha_search/phase2_adjacent_overshoot_clean_forward_contract_20260831.json
(d-0014, sha256 50ee0360...). Trigger: data/alpha_search/phase2_adjacent_overshoot_trigger_recount_20260912.json.
Promotion: data/alpha_search/promotions/phase2_adjacent_overshoot_clean_forward_20260912.json.

Cohort (frozen 2026-08-31, verbatim from the 2026-08-29 registration wording):
  clean      = qualified non-flat mapped estimate-revision decisions whose decision_id is outside the
               1352-id contamination fence (ids with h5_status closed in the freeze-commit fileset);
  conditioned= constant-multiple update-implied repricing overshoot:
               implied = |delta / (eps - delta)|, overshoot iff dir_sign * ln(close_A / close_{A-5}) > implied,
               A = last warehouse session <= as_of_date; guards |eps - delta| >= 0.10, delta sign == direction,
               >= 6 pre-event bars; exclude fail-closed. No sigma/volatility envelope.
Gates: >= 30 settled conditioned clean decisions at h5 AND h10, >= 10 per direction leg at each; no partial run.
Bars (ALL must pass for observed_only_positive_lead; any failure -> rejected):
  B1 mean(h_ret | down_overshoot) - mean(h_ret | up_overshoot) > 0 at BOTH h5 and h10
  B2 sum(h10_replacement_value_vs_cash_usd | down_overshoot) > 0   (h5 reported)
  B3 sum(h10_rv_vs_spy | down) > 0 AND sum(h10_rv_vs_qqq | down) > 0
  B4 date placebo (h10, 200 draws, seed 20260901): real simple-methodology reversion spread > p90 placebo
  B5 ticker shuffle within session (h10, 200 draws): real > p90 shuffle
  h20 reported only; displaced-core comparator reported only (no per-decision series exists).
Outcome fields are read ONLY for clean conditioned decisions; contaminated ids are dropped before any
outcome key is touched. Read-only against production data; trade_enabled stays false.
"""
import collections
import glob
import hashlib
import json
import math
import random
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

EXPERIMENT_ID = 'exp-20260912-001'
CANDIDATE_ID = 'cand-68d2f5dad2f903488307'
REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / 'data' / 'experiments' / EXPERIMENT_ID
WAREHOUSE = REPO / 'data' / 'warehouse' / 'warehouse_main_hot.sqlite'
CONTRACT = REPO / 'data' / 'alpha_search' / 'phase2_adjacent_overshoot_clean_forward_contract_20260831.json'
RECOUNT = REPO / 'data' / 'alpha_search' / 'phase2_adjacent_overshoot_trigger_recount_20260912.json'
PROMOTION = REPO / 'data' / 'alpha_search' / 'promotions' / 'phase2_adjacent_overshoot_clean_forward_20260912.json'
FREEZE_COMMIT = '5967838ae'
PATH_SESSIONS = 5
MIN_PRIOR_EPS_ABS = 0.10
SEED = 20260901
N_DRAWS = 200
ALLOWED = {'decision_id', 'ticker', 'instrument_ticker', 'as_of_date',
           'revision_direction', 'decision_qualified', 'instrument_mapping_qualified',
           'actual_entry_date', 'usable_entry_date', 'entry_date',
           'eps_estimate', 'eps_estimate_delta_prev',
           'h5_status', 'h10_status', 'h20_status'}
OUTCOME_KEYS = {f'{h}_{k}' for h in ('h5', 'h10', 'h20') for k in (
    'return_pct', 'replacement_value_vs_cash_usd', 'replacement_value_vs_spy_usd', 'replacement_value_vs_qqq_usd')}


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def iter_rows(blobs):
    for _name, raw in blobs:
        for line in raw.decode('utf-8').splitlines():
            if line.strip():
                yield json.loads(line)


def qualified(r):
    return (r.get('decision_qualified') and r.get('revision_direction') in ('up', 'down')
            and r.get('instrument_mapping_qualified') and r.get('decision_id'))


def committed_blobs():
    names = subprocess.check_output(
        ['git', '-C', str(REPO), 'ls-tree', '-r', '--name-only', FREEZE_COMMIT, '--', 'data/non_ohlcv/'],
        text=True).split()
    names = sorted(n for n in names if Path(n).name.startswith('estimate_revision_outcomes_') and n.endswith('.jsonl'))
    return [(n, subprocess.check_output(['git', '-C', str(REPO), 'show', f'{FREEZE_COMMIT}:{n}'])) for n in names]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contract = json.load(open(CONTRACT, encoding='utf-8'))
    fence = contract['contamination_fence']

    # --- contamination fence, re-derived from the freeze commit (identity projection only)
    seen = set()
    contaminated = []
    for r in iter_rows(committed_blobs()):
        r = {k: v for k, v in r.items() if k in ALLOWED}
        if not qualified(r) or r['decision_id'] in seen:
            continue
        seen.add(r['decision_id'])
        if r.get('h5_status') == 'closed':
            contaminated.append(r['decision_id'])
    contaminated.sort()
    cont_sha = hashlib.sha256('\n'.join(contaminated).encode()).hexdigest()
    if cont_sha != fence['contaminated_decision_ids_sha256'] or len(contaminated) != fence['contaminated_decision_count']:
        raise SystemExit(f'fence mismatch: {cont_sha} / {len(contaminated)}')
    contaminated = set(contaminated)

    # --- live ledgers: identity projection first, outcome keys only for clean conditioned rows
    files = sorted(glob.glob(str(REPO / 'data/non_ohlcv/estimate_revision_outcomes_*.jsonl')))
    live_blobs = [(f, open(f, 'rb').read()) for f in files]
    fileset = hashlib.sha256()
    for _f, raw in live_blobs:
        fileset.update(hashlib.sha256(raw).digest())
    ident = {}
    raw_by_id = {}
    for r in iter_rows(live_blobs):
        if not qualified(r) or r['decision_id'] in ident:
            continue
        did = r['decision_id']
        ident[did] = {k: v for k, v in r.items() if k in ALLOWED}
        if did not in contaminated:
            raw_by_id[did] = r  # held unread until conditioning decides membership

    con = sqlite3.connect(f'file:{WAREHOUSE.as_posix()}?mode=ro', uri=True)
    cur = con.cursor()
    bars_cache = {}

    def bars(t):
        if t not in bars_cache:
            bars_cache[t] = cur.execute(
                'SELECT date, open, close FROM ohlcv WHERE ticker=? ORDER BY date', (t,)).fetchall()
        return bars_cache[t]

    counts = {'overshoot': 0, 'not_overshoot': 0, 'excluded_prior_eps_guard': 0,
              'excluded_insufficient_bars': 0, 'excluded_delta_sign_mismatch': 0}
    price_rows = []
    cohort = []
    for did, r in ident.items():
        if did in contaminated:
            continue
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
        pre = [b for b in bars(t) if b[0] <= r['as_of_date']][-(PATH_SESSIONS + 1):]
        if len(pre) < PATH_SESSIONS + 1:
            counts['excluded_insufficient_bars'] += 1
            continue
        for d, _o, c in pre:
            price_rows.append((t, d, repr(c)))
        closes = [c for _d, _o, c in pre]
        if dir_sign * math.log(closes[-1] / closes[0]) > implied:
            counts['overshoot'] += 1
            full = raw_by_id[did]  # first and only outcome access: clean + conditioned
            rec = {'decision_id': did, 'ticker': t, 'as_of': r['as_of_date'],
                   'direction': r['revision_direction'],
                   'entry_date': r.get('actual_entry_date') or r.get('usable_entry_date') or r.get('entry_date')}
            for h in ('h5', 'h10', 'h20'):
                rec[h + '_status'] = full.get(h + '_status')
                if full.get(h + '_status') == 'closed':
                    rec[h + '_ret'] = full.get(h + '_return_pct')
                    rec[h + '_rv_cash'] = full.get(h + '_replacement_value_vs_cash_usd')
                    rec[h + '_rv_spy'] = full.get(h + '_replacement_value_vs_spy_usd')
                    rec[h + '_rv_qqq'] = full.get(h + '_replacement_value_vs_qqq_usd')
            cohort.append(rec)
        else:
            counts['not_overshoot'] += 1
    price_sha = hashlib.sha256('\n'.join('\t'.join(p) for p in sorted(set(price_rows))).encode()).hexdigest()

    # --- sample gates
    gates = contract['sample_gates']
    hmin, lmin = gates['per_gated_horizon_min_settled_conditioned_clean'], gates['per_direction_leg_min']
    settled = {}
    for h in ('h5', 'h10', 'h20'):
        rows = [x for x in cohort if x.get(h + '_ret') is not None]
        settled[h] = {'n': len(rows), 'up': sum(1 for x in rows if x['direction'] == 'up'),
                      'down': sum(1 for x in rows if x['direction'] == 'down'),
                      'entry_dates': len({x['entry_date'] for x in rows})}
    gates_hold = all(settled[h]['n'] >= hmin and settled[h]['up'] >= lmin and settled[h]['down'] >= lmin
                     for h in contract['treatment']['horizons_gated'])

    def leg(h, direction, key='_ret'):
        return [x[h + key] for x in cohort if x['direction'] == direction and x.get(h + key) is not None]

    def spread(h):
        dn, up = leg(h, 'down'), leg(h, 'up')
        if not dn or not up:
            return None, len(dn), len(up)
        return mean(dn) - mean(up), len(dn), len(up)

    result = {
        'schema_version': 1,
        'record_type': 'clean_forward_falsification_result',
        'experiment_id': EXPERIMENT_ID,
        'candidate_id': CANDIDATE_ID,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'inputs': {
            'contract': str(CONTRACT.relative_to(REPO)).replace('\\', '/'),
            'contract_sha256': sha_file(CONTRACT),
            'recount_artifact': str(RECOUNT.relative_to(REPO)).replace('\\', '/'),
            'recount_artifact_sha256': sha_file(RECOUNT),
            'promotion': str(PROMOTION.relative_to(REPO)).replace('\\', '/'),
            'promotion_sha256': sha_file(PROMOTION),
            'freeze_commit': FREEZE_COMMIT,
            'contaminated_ids_sha256': cont_sha,
            'contaminated_ids_count': len(contaminated),
            'live_outcome_files': len(files),
            'live_outcome_fileset_sha256': fileset.hexdigest(),
            'pre_event_close_rows': len(set(price_rows)),
            'pre_event_close_rows_sha256': price_sha,
            'warehouse': 'data/warehouse/warehouse_main_hot.sqlite',
            'seed': SEED, 'n_draws': N_DRAWS,
        },
        'frozen_rule_conditioned_stock': counts,
        'cohort': {'clean_qualified': len(raw_by_id), 'conditioned_overshoot': len(cohort),
                   'up': sum(1 for x in cohort if x['direction'] == 'up'),
                   'down': sum(1 for x in cohort if x['direction'] == 'down'),
                   'settled': settled},
        'sample_gates': {'per_gated_horizon_min': hmin, 'per_leg_min': lmin, 'hold': gates_hold},
        'trade_enabled': False,
    }
    if not gates_hold:
        result.update({'verdict': 'gates_not_met_no_evaluation', 'all_bars_pass': False, 'disposition': 'rejected'})
        (OUT_DIR / 'adjacent_overshoot_clean_forward_result.json').write_text(
            json.dumps(result, indent=1, sort_keys=True), encoding='utf-8')
        print(json.dumps({'verdict': result['verdict']}))
        return

    # --- B1
    b1 = {}
    for h in ('h5', 'h10', 'h20'):
        s, nd, nu = spread(h)
        b1[h] = {'spread_pct_down_minus_up': s, 'n_down': nd, 'n_up': nu, 'pass': (s is not None and s > 0)}
    b1_pass = b1['h5']['pass'] and b1['h10']['pass']
    # --- B2 / B3 (down-overshoot tradable long leg)
    b2 = {}
    for h in ('h5', 'h10'):
        vals = leg(h, 'down', '_rv_cash')
        b2[h] = {'sum_rv_vs_cash_usd': sum(vals) if vals else None, 'n': len(vals), 'pass': bool(vals) and sum(vals) > 0}
    b2_pass = b2['h10']['pass']
    spy10, qqq10 = leg('h10', 'down', '_rv_spy'), leg('h10', 'down', '_rv_qqq')
    b3 = {'sum_rv_vs_spy_h10_usd': sum(spy10) if spy10 else None, 'sum_rv_vs_qqq_h10_usd': sum(qqq10) if qqq10 else None,
          'n_spy': len(spy10), 'n_qqq': len(qqq10)}
    b3_pass = bool(spy10) and bool(qqq10) and sum(spy10) > 0 and sum(qqq10) > 0

    # --- B4 / B5: simple methodology on the h10-settled conditioned clean cohort
    def simple_ret(ticker, as_of):
        rows = bars(ticker)
        idx = next((i for i, b in enumerate(rows) if b[0] > as_of), None)
        if idx is None or idx + 9 >= len(rows):
            return None
        entry_open, exit_close = rows[idx][1], rows[idx + 9][2]
        if not entry_open or entry_open <= 0 or exit_close is None:
            return None
        return exit_close / entry_open - 1.0

    def simple_spread(assignments):
        dn, up = [], []
        for ticker, as_of, direction in assignments:
            v = simple_ret(ticker, as_of)
            if v is None:
                continue
            (dn if direction == 'down' else up).append(v)
        if not dn or not up:
            return None
        return mean(dn) - mean(up)

    gated = [x for x in cohort if x.get('h10_ret') is not None]
    real_assign = [(x['ticker'], x['as_of'], x['direction']) for x in gated]
    real_simple = simple_spread(real_assign)
    sessions = sorted({x['as_of'] for x in gated})
    rng = random.Random(SEED)
    placebo = []
    for _ in range(N_DRAWS):
        assign = []
        for x in gated:
            others = [s for s in sessions if s != x['as_of']]
            assign.append((x['ticker'], rng.choice(others), x['direction']))
        v = simple_spread(assign)
        if v is not None:
            placebo.append(v)
    placebo.sort()
    p90_placebo = placebo[int(0.9 * len(placebo))] if placebo else None
    b4_pass = real_simple is not None and p90_placebo is not None and real_simple > p90_placebo

    by_session = collections.defaultdict(list)
    for x in gated:
        by_session[x['as_of']].append(x)
    shuffled = []
    for _ in range(N_DRAWS):
        assign = []
        for s, members in by_session.items():
            tickers = [m['ticker'] for m in members]
            rng.shuffle(tickers)
            for m, t in zip(members, tickers):
                assign.append((t, s, m['direction']))
        v = simple_spread(assign)
        if v is not None:
            shuffled.append(v)
    shuffled.sort()
    p90_shuffle = shuffled[int(0.9 * len(shuffled))] if shuffled else None
    b5_pass = real_simple is not None and p90_shuffle is not None and real_simple > p90_shuffle

    all_pass = all([b1_pass, b2_pass, b3_pass, b4_pass, b5_pass])
    result.update({
        'bars': {
            'B1_residual_decay': {**b1, 'rule': 'down minus up spread > 0 at BOTH h5 and h10; h20 reported', 'pass': b1_pass},
            'B2_long_leg_vs_cash': {**b2, 'rule': 'sum h10 rv vs cash (down leg) > 0; h5 reported', 'pass': b2_pass},
            'B3_vs_spy_qqq_h10': {**b3, 'pass': b3_pass},
            'B4_date_placebo_h10': {'real_simple_spread': real_simple, 'p90_placebo': p90_placebo,
                                    'n_draws_valid': len(placebo), 'n_sessions': len(sessions),
                                    'n_gated_decisions': len(gated), 'pass': b4_pass},
            'B5_ticker_shuffle_h10': {'real_simple_spread': real_simple, 'p90_shuffle': p90_shuffle,
                                      'n_draws_valid': len(shuffled), 'pass': b5_pass},
        },
        'reported_only': {
            'h20': b1['h20'],
            'displaced_core_comparator': 'no per-decision displaced-core series exists in the outcome ledger; not evaluable',
        },
        'verdict': 'observed_only_positive_lead' if all_pass else 'rejected',
        'disposition': 'observed_only' if all_pass else 'rejected',
        'all_bars_pass': all_pass,
    })
    out = OUT_DIR / 'adjacent_overshoot_clean_forward_result.json'
    out.write_text(json.dumps(result, indent=1, sort_keys=True), encoding='utf-8')
    nulls = {k: None for k in ('expected_value_score', 'max_drawdown_pct', 'sharpe', 'sharpe_daily',
                               'survival_rate', 'total_pnl', 'total_return_pct', 'trade_count', 'win_rate')}
    for name in ('before_metrics.json', 'after_metrics.json'):
        (OUT_DIR / name).write_text(json.dumps(nulls, indent=1), encoding='utf-8')
    print(json.dumps({'verdict': result['verdict'], 'B1': b1_pass, 'B2': b2_pass, 'B3': b3_pass,
                      'B4': b4_pass, 'B5': b5_pass, 'cohort': result['cohort']}, indent=1))
    print('written', out)


if __name__ == '__main__':
    main()
