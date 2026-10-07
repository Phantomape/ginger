"""Outcome-blind identity check + constant-time trigger recount for the frozen
d-0014 clean-forward falsification contract (cand-68d2f5dad2f903488307).

Read-only. Projects every outcome-ledger row onto the contract's ALLOWED
identity/status whitelist before use; never loads a return, PnL or
replacement-value field. Does NOT rebuild or touch the frozen contract.

Identity: the contamination fence is re-derived from the 81 outcome files
committed in the freeze commit (5967838ae, 3 minutes after the freeze) and
compared to the contract's contaminated_decision_ids_sha256. The freeze-time
fileset sha256 covered 82 files; the 82nd was never committed and the ledgers
are rewritten in place daily, so that hash is documentary only.
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
FREEZE_COMMIT = '5967838ae'
PATH_SESSIONS = 5
MIN_PRIOR_EPS_ABS = 0.10
ALLOWED = {'decision_id', 'ticker', 'instrument_ticker', 'as_of_date',
           'revision_direction', 'decision_qualified', 'instrument_mapping_qualified',
           'actual_entry_date', 'usable_entry_date', 'entry_date',
           'eps_estimate', 'eps_estimate_delta_prev',
           'h5_status', 'h10_status', 'h20_status'}


def project_rows(blobs):
    """blobs: iterable of (name, raw_bytes) in sorted name order -> {decision_id: projected row}."""
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

    committed = list(committed_blobs())
    committed_rows = project_rows(committed)
    contaminated = sorted(d for d, r in committed_rows.items() if r.get('h5_status') == 'closed')
    cont_sha = hashlib.sha256('\n'.join(contaminated).encode()).hexdigest()
    fence_verified = (cont_sha == fence['contaminated_decision_ids_sha256']
                      and len(contaminated) == fence['contaminated_decision_count'])
    contaminated = set(contaminated)

    files = sorted(glob.glob(str(REPO / 'data/non_ohlcv/estimate_revision_outcomes_*.jsonl')))
    live_blobs = [(f, open(f, 'rb').read()) for f in files]
    rows = project_rows(live_blobs)
    clean = {d: r for d, r in rows.items() if d not in contaminated}

    con = sqlite3.connect(f'file:{WAREHOUSE.as_posix()}?mode=ro', uri=True)
    cur = con.cursor()
    warehouse_max_date = cur.execute('SELECT MAX(date) FROM ohlcv').fetchone()[0]
    cache = {}

    def closes_upto(t, as_of, n):
        if t not in cache:
            cache[t] = cur.execute(
                'SELECT date, close FROM ohlcv WHERE ticker=? ORDER BY date', (t,)).fetchall()
        return [r for r in cache[t] if r[0] <= as_of][-n:]

    counts = {'overshoot': 0, 'not_overshoot': 0, 'excluded_prior_eps_guard': 0,
              'excluded_insufficient_bars': 0, 'excluded_delta_sign_mismatch': 0}
    settled = {h: {'up': 0, 'down': 0} for h in ('h5', 'h10', 'h20')}
    entry_dates_settled = {h: set() for h in ('h5', 'h10')}
    price_rows = []
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
        for d, c in bars:
            price_rows.append((t, d, repr(c)))
        closes = [c for _, c in bars]
        if dir_sign * math.log(closes[-1] / closes[0]) > implied:
            counts['overshoot'] += 1
            e = str(r.get('actual_entry_date') or r.get('usable_entry_date') or r.get('entry_date'))
            for h in ('h5', 'h10', 'h20'):
                if r.get(f'{h}_status') == 'closed':
                    settled[h][r['revision_direction']] += 1
                    if h in entry_dates_settled:
                        entry_dates_settled[h].add(e)
        else:
            counts['not_overshoot'] += 1

    price_sha = hashlib.sha256('\n'.join('\t'.join(p) for p in sorted(set(price_rows))).encode()).hexdigest()
    gates = contract['sample_gates']
    hmin, lmin = gates['per_gated_horizon_min_settled_conditioned_clean'], gates['per_direction_leg_min']
    bar_state = {}
    for h in contract['treatment']['horizons_gated']:
        tot = settled[h]['up'] + settled[h]['down']
        bar_state[h] = {'settled': tot, 'up': settled[h]['up'], 'down': settled[h]['down'],
                        'entry_dates': len(entry_dates_settled[h]),
                        'holds': tot >= hmin and settled[h]['up'] >= lmin and settled[h]['down'] >= lmin}
    trigger_fires = all(v['holds'] for v in bar_state.values())

    out = {
        'record_type': 'd0014_clean_forward_trigger_recount',
        'outcome_blind': True,
        'contract_path': str(CONTRACT.relative_to(REPO)).replace('\\', '/'),
        'contract_sha256': contract_sha,
        'identity': {
            'freeze_commit': FREEZE_COMMIT,
            'committed_outcome_files': len(committed),
            'contract_fileset_files': fence['outcome_fileset_files'],
            'contaminated_ids_recomputed': len(contaminated),
            'contaminated_ids_sha256_recomputed': cont_sha,
            'contaminated_ids_sha256_contract': fence['contaminated_decision_ids_sha256'],
            'fence_verified': fence_verified,
            'fileset_sha256_reproducible': False,
            'fileset_note': '82nd freeze-time file never committed and ledgers are rewritten in place daily; the fence is fully determined by the verified id list',
        },
        'live_fileset': {'files': len(files), 'first': Path(files[0]).name, 'last': Path(files[-1]).name,
                         'qualified_rows': len(rows), 'clean_rows': len(clean)},
        'conditioning_price_identity': {'warehouse': str(WAREHOUSE.relative_to(REPO)).replace('\\', '/'),
                                        'warehouse_max_date': warehouse_max_date,
                                        'pre_event_close_rows': len(set(price_rows)),
                                        'pre_event_close_rows_sha256': price_sha},
        'frozen_rule_conditioned_stock': counts,
        'settled_conditioned_clean': settled,
        'bars': bar_state,
        'trigger_fires': trigger_fires and fence_verified,
    }
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
