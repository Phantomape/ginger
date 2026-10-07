"""Outcome-blind recount for exp-20260912-001 reopen condition (a).

exp-20260912-001 (rejected, already_priced) may only be re-read on "a fully disjoint
forward window of decisions first settled after 2026-09-11 reaching >=60 settled
conditioned clean decisions per gated horizon (h5 and h10) with >=10 entry dates under
the unchanged rule and fence, counted outcome-blind before any ID".

Read-only. Same ALLOWED identity whitelist as the 2026-09-12 recount plus the two
settlement-clock identity fields (h5_exit_date / h10_exit_date); never loads a return,
PnL or replacement-value field. Conditioning rule, guards, fence derivation and price
source are byte-for-byte the 2026-09-12 logic (quant/experiments/
adjacent_overshoot_clean_forward_recount_20260912.py); the only addition is the
disjoint-window filter: a decision belongs to the reopen window iff its h5 settlement
session is strictly after 2026-09-11 (so neither gated horizon was settled when the
2026-09-12 cohort was read). Does NOT touch the frozen contract or the 0912 result.
"""
import glob
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WAREHOUSE = REPO / 'data' / 'warehouse' / 'warehouse_main_hot.sqlite'
CONTRACT = REPO / 'data' / 'alpha_search' / 'phase2_adjacent_overshoot_clean_forward_contract_20260831.json'
PRIOR_RESULT = REPO / 'data' / 'experiments' / 'exp-20260912-001' / 'adjacent_overshoot_clean_forward_result.json'
FREEZE_COMMIT = '5967838ae'
CONSUMED_WINDOW_LAST_SETTLEMENT = '2026-09-11'
REOPEN_MIN_PER_GATED_HORIZON = 60
REOPEN_MIN_ENTRY_DATES = 10
PATH_SESSIONS = 5
MIN_PRIOR_EPS_ABS = 0.10
ALLOWED = {'decision_id', 'ticker', 'instrument_ticker', 'as_of_date',
           'revision_direction', 'decision_qualified', 'instrument_mapping_qualified',
           'actual_entry_date', 'usable_entry_date', 'entry_date',
           'eps_estimate', 'eps_estimate_delta_prev',
           'h5_status', 'h10_status', 'h20_status',
           'h5_exit_date', 'h10_exit_date'}


def project_rows(blobs):
    rows = {}
    for _name, raw in blobs:
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
    return rows


def committed_blobs():
    names = subprocess.check_output(
        ['git', '-C', str(REPO), 'ls-tree', '-r', '--name-only', FREEZE_COMMIT, '--', 'data/non_ohlcv/'],
        text=True).split()
    names = sorted(n for n in names if Path(n).name.startswith('estimate_revision_outcomes_') and n.endswith('.jsonl'))
    for n in names:
        yield n, subprocess.check_output(['git', '-C', str(REPO), 'show', f'{FREEZE_COMMIT}:{n}'])


def main():
    contract = json.load(open(CONTRACT, encoding='utf-8'))
    contract_sha = hashlib.sha256(open(CONTRACT, 'rb').read()).hexdigest()
    fence = contract['contamination_fence']
    prior = json.load(open(PRIOR_RESULT, encoding='utf-8'))
    prior_sha = hashlib.sha256(open(PRIOR_RESULT, 'rb').read()).hexdigest()

    committed_rows = project_rows(list(committed_blobs()))
    contaminated = sorted(d for d, r in committed_rows.items() if r.get('h5_status') == 'closed')
    cont_sha = hashlib.sha256('\n'.join(contaminated).encode()).hexdigest()
    fence_verified = (cont_sha == fence['contaminated_decision_ids_sha256']
                      and len(contaminated) == fence['contaminated_decision_count'])
    contaminated = set(contaminated)

    files = sorted(glob.glob(str(REPO / 'data/non_ohlcv/estimate_revision_outcomes_*.jsonl')))
    live_blobs = [(f, open(f, 'rb').read()) for f in files]
    fileset_sha = hashlib.sha256(b''.join(hashlib.sha256(b).digest() for _, b in live_blobs)).hexdigest()
    rows = project_rows(live_blobs)
    clean = {d: r for d, r in rows.items() if d not in contaminated}

    # disjoint reopen window: h5 settlement strictly after the consumed window's last settlement
    window, consumed_or_unsettled_h5 = {}, {'h5_closed_on_or_before_cutoff': 0, 'h5_open_no_exit_date': 0}
    for d, r in clean.items():
        x = r.get('h5_exit_date')
        if r.get('h5_status') == 'closed' and x and str(x) <= CONSUMED_WINDOW_LAST_SETTLEMENT:
            consumed_or_unsettled_h5['h5_closed_on_or_before_cutoff'] += 1
            continue
        if not x:
            consumed_or_unsettled_h5['h5_open_no_exit_date'] += 1
        window[d] = r

    con = sqlite3.connect(f'file:{WAREHOUSE.as_posix()}?mode=ro', uri=True)
    cur = con.cursor()
    warehouse_max_date = cur.execute('SELECT MAX(date) FROM ohlcv').fetchone()[0]
    cache = {}

    def closes_upto(t, as_of, n):
        if t not in cache:
            cache[t] = cur.execute('SELECT date, close FROM ohlcv WHERE ticker=? ORDER BY date', (t,)).fetchall()
        return [r for r in cache[t] if r[0] <= as_of][-n:]

    counts = {'overshoot': 0, 'not_overshoot': 0, 'excluded_prior_eps_guard': 0,
              'excluded_insufficient_bars': 0, 'excluded_delta_sign_mismatch': 0}
    settled = {h: {'up': 0, 'down': 0} for h in ('h5', 'h10', 'h20')}
    entry_dates_settled = {h: set() for h in ('h5', 'h10')}
    conditioned_unsettled = {'h5': 0, 'h10': 0}
    for did, r in window.items():
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
            e = str(r.get('actual_entry_date') or r.get('usable_entry_date') or r.get('entry_date'))
            for h in ('h5', 'h10', 'h20'):
                if r.get(f'{h}_status') == 'closed':
                    settled[h][r['revision_direction']] += 1
                    if h in entry_dates_settled:
                        entry_dates_settled[h].add(e)
                elif h in conditioned_unsettled:
                    conditioned_unsettled[h] += 1
        else:
            counts['not_overshoot'] += 1

    leg_min = contract['sample_gates']['per_direction_leg_min']
    bar_state = {}
    for h in contract['treatment']['horizons_gated']:
        tot = settled[h]['up'] + settled[h]['down']
        bar_state[h] = {'settled': tot, 'up': settled[h]['up'], 'down': settled[h]['down'],
                        'entry_dates': len(entry_dates_settled[h]),
                        'conditioned_unsettled': conditioned_unsettled[h],
                        'holds': (tot >= REOPEN_MIN_PER_GATED_HORIZON
                                  and len(entry_dates_settled[h]) >= REOPEN_MIN_ENTRY_DATES
                                  and settled[h]['up'] >= leg_min and settled[h]['down'] >= leg_min)}
    trigger_fires = all(v['holds'] for v in bar_state.values())

    out = {
        'record_type': 'exp20260912_001_reopen_condition_a_recount',
        'outcome_blind': True,
        'contract_path': str(CONTRACT.relative_to(REPO)).replace('\\', '/'),
        'contract_sha256': contract_sha,
        'prior_result_path': str(PRIOR_RESULT.relative_to(REPO)).replace('\\', '/'),
        'prior_result_sha256': prior_sha,
        'prior_disposition': prior.get('disposition'),
        'reopen_rule': {
            'window': f'clean decisions whose h5 settlement session is strictly after {CONSUMED_WINDOW_LAST_SETTLEMENT}',
            'min_settled_conditioned_clean_per_gated_horizon': REOPEN_MIN_PER_GATED_HORIZON,
            'min_entry_dates_per_gated_horizon': REOPEN_MIN_ENTRY_DATES,
            'per_direction_leg_min': leg_min,
            'conditioning_rule': 'unchanged (contract frozen_conditioning_rule)',
        },
        'identity': {
            'freeze_commit': FREEZE_COMMIT,
            'contaminated_ids_recomputed': len(contaminated),
            'contaminated_ids_sha256_recomputed': cont_sha,
            'fence_verified': fence_verified,
        },
        'live_fileset': {'files': len(files), 'first': Path(files[0]).name, 'last': Path(files[-1]).name,
                         'fileset_sha256': fileset_sha,
                         'qualified_rows': len(rows), 'clean_rows': len(clean),
                         'excluded_from_window': consumed_or_unsettled_h5,
                         'window_rows': len(window)},
        'conditioning_price_identity': {'warehouse': str(WAREHOUSE.relative_to(REPO)).replace('\\', '/'),
                                        'warehouse_max_date': warehouse_max_date},
        'frozen_rule_conditioned_stock': counts,
        'settled_conditioned_clean': settled,
        'bars': bar_state,
        'trigger_fires': trigger_fires and fence_verified,
    }
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
