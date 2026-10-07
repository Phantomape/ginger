"""North-star baseline (read-only): live moomoo account flow-adjusted TWR vs SPY,
and the aggregate of all closed paper-sleeve trades vs a same-notional, same-window SPY comparator.

Usage: python scripts/northstar_baseline.py   -> writes data/northstar/baseline_<last_session>.json
Caveats: the live account mixes system-recommended and discretionary trades (no strategy tag on orders);
paper sleeves are independent books, so overlapping trades are not a single portfolio."""
import json, os, sqlite3, math, collections
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BE = os.path.join(ROOT, "data/live_pilot/broker_execution")
out = {}

# ---------- SPY closes ----------
con = sqlite3.connect(f"file:{ROOT}/data/warehouse/warehouse_main_hot.sqlite?mode=ro", uri=True)
spy = dict(con.execute("select date, close from ohlcv where ticker='SPY'").fetchall())
qqq = dict(con.execute("select date, close from ohlcv where ticker='QQQ'").fetchall())
sdates = sorted(spy)

def prev_session(d):
    """Last SPY session strictly before calendar date d (snapshot at ~03:00Z on d = close of prior US session)."""
    ds = d.isoformat()
    cands = [x for x in sdates if x < ds]
    return cands[-1]

# ---------- Live account ----------
snaps = [json.loads(l) for l in open(os.path.join(BE, "account_snapshots.jsonl"), encoding="utf-8")]
nav = {}  # session_date -> total_assets (last snapshot per obs date)
for s in snaps:
    a = s["fact"]["account_info"][0]
    obs = date.fromisoformat(s["observed_at_utc"][:10])
    nav[prev_session(obs)] = float(a["total_assets"])
cfs = [json.loads(l)["fact"] for l in open(os.path.join(BE, "cash_flows.jsonl"), encoding="utf-8")]
ext = collections.defaultdict(float)  # external transfers keyed to the session in which they first show up
for c in cfs:
    if c["cashflow_type"] == "资金调拨":
        cd = date.fromisoformat(c["clearing_date"])
        # first snapshot observed after clearing date
        sess = prev_session(cd + timedelta(days=1))
        ext[sess] += float(c["cashflow_amount"])
days = sorted(nav)
twr = 1.0; spy_g = 1.0; qqq_g = 1.0; rows = []
peak = 1.0; mdd = 0.0; rets = []; srets = []
for p, d in zip(days, days[1:]):
    flow = sum(v for k, v in ext.items() if p < k <= d)
    r = (nav[d] - flow) / nav[p] - 1
    sr = spy[d] / spy[p] - 1
    qr = qqq[d] / qqq[p] - 1
    twr *= 1 + r; spy_g *= 1 + sr; qqq_g *= 1 + qr
    peak = max(peak, twr); mdd = min(mdd, twr / peak - 1)
    rets.append(r); srets.append(sr)
    rows.append((d, nav[d], flow, r, sr))

def stats(x):
    m = sum(x) / len(x); v = sum((a - m) ** 2 for a in x) / (len(x) - 1)
    return m, math.sqrt(v)

m, sd = stats(rets); sm, ssd = stats(srets)
cov = sum((a - m) * (b - sm) for a, b in zip(rets, srets)) / (len(rets) - 1)
beta = cov / ssd ** 2
spy_peak = 1; spy_mdd = 0; g = 1
for r in srets:
    g *= 1 + r; spy_peak = max(spy_peak, g); spy_mdd = min(spy_mdd, g / spy_peak - 1)
pnl_usd = nav[days[-1]] - nav[days[0]] - sum(ext.values())
out["live"] = {
    "window": [days[0], days[-1]], "intervals": len(rets),
    "start_nav": nav[days[0]], "end_nav": nav[days[-1]], "net_external_transfers": sum(ext.values()),
    "pnl_usd_flow_adjusted": pnl_usd,
    "twr": twr - 1, "spy": spy_g - 1, "qqq": qqq_g - 1, "excess_vs_spy": twr - spy_g,
    "beta_vs_spy": beta, "alpha_daily_mean": m - beta * sm,
    "ann_vol": sd * math.sqrt(252), "spy_ann_vol": ssd * math.sqrt(252),
    "max_dd": mdd, "spy_max_dd": spy_mdd,
    "sharpe_ann": m / sd * math.sqrt(252), "spy_sharpe_ann": sm / ssd * math.sqrt(252),
    "last_snapshot_observed": snaps[-1]["observed_at_utc"],
}
# fees actually paid
fee_by_order = {}
for l in open(os.path.join(BE, "order_fee_snapshots.jsonl"), encoding="utf-8"):
    f = json.loads(l)["fact"]
    try:
        fee_by_order[f.get("order_id")] = float(f.get("fee_amount") or 0)
    except Exception:
        pass
out["live"]["fee_orders"] = len(fee_by_order)
out["live"]["fee_sum_usd_dedup_by_order"] = sum(fee_by_order.values())
# dividends net
out["live"]["dividends_net_usd"] = sum(float(c["cashflow_amount"]) for c in cfs if c["cashflow_type"] not in ("其他", "资金调拨"))
out["live_daily"] = rows

# ---------- Paper sleeves ----------
PS = os.path.join(ROOT, "data/paper_sleeves")
def num(x):
    try: return float(x)
    except Exception: return None
def notional_of(r):
    for k in ("notional", "replacement_value_notional_usd", "intended_notional", "base_paper_notional_usd", "base_event_notional_usd"):
        v = num(r.get(k))
        if v: return v
    c = r.get("candidate") or {}
    for k in ("intended_notional", "base_paper_notional_usd"):
        v = num(c.get(k))
        if v: return v
    if r.get("shares") and r.get("entry_price"):
        return float(r["shares"]) * float(r["entry_price"])
    return None

per = {}; allrows = []
for d in sorted(os.listdir(PS)):
    p = os.path.join(PS, d, "state.json")
    if not os.path.isfile(p): continue
    s = json.load(open(p, encoding="utf-8"))
    cp = s.get("closed_positions") or s.get("closed_outcomes") or []
    rs = []
    for r in cp:
        pnl = num(r.get("pnl"))
        if pnl is None: pnl = num(r.get("realized_pnl"))
        if pnl is None: continue
        rs.append(dict(sleeve=d, pnl=pnl, notional=notional_of(r), entry=r.get("entry_date"), exit=r.get("exit_date"),
                       rv_spy=num(r.get("replacement_value_vs_spy_usd")), rv_qqq=num(r.get("replacement_value_vs_qqq_usd")),
                       ticker=r.get("ticker")))
    if not rs: continue
    allrows += rs
    n = len(rs); pn = sum(x["pnl"] for x in rs); nt = sum(x["notional"] or 0 for x in rs)
    rvs = [x["rv_spy"] for x in rs if x["rv_spy"] is not None]
    per[d] = dict(n=n, pnl=pn, notional=nt, ret_on_notional=pn / nt if nt else None,
                  hit=sum(x["pnl"] > 0 for x in rs) / n, rv_spy=sum(rvs) if rvs else None, rv_spy_n=len(rvs),
                  first_exit=min(x["exit"] or "9" for x in rs), last_exit=max(x["exit"] or "" for x in rs))
tot_n = len(allrows); tot_pnl = sum(x["pnl"] for x in allrows); tot_not = sum(x["notional"] or 0 for x in allrows)
rv = [x for x in allrows if x["rv_spy"] is not None]
spy_pnl_same = sum(x["pnl"] - x["rv_spy"] for x in rv)
out["paper"] = dict(sleeves_with_closed=len(per), closed=tot_n, pnl=tot_pnl, notional=tot_not,
                    ret_per_dollar_traded=tot_pnl / tot_not, hit=sum(x["pnl"] > 0 for x in allrows) / tot_n,
                    rv_rows=len(rv), rv_spy_sum=sum(x["rv_spy"] for x in rv),
                    pnl_on_rv_rows=sum(x["pnl"] for x in rv), spy_same_notional_same_window_pnl=spy_pnl_same,
                    rv_qqq_sum=sum(x["rv_qqq"] for x in rv if x["rv_qqq"] is not None),
                    first_exit=min(x["exit"] for x in allrows if x["exit"]), last_exit=max(x["exit"] for x in allrows if x["exit"]),
                    winners_sleeves_vs_spy=sum(1 for v in per.values() if (v["rv_spy"] or 0) > 0),
                    sleeves_with_rv=sum(1 for v in per.values() if v["rv_spy"] is not None))
# per-trade t-stat of excess vs SPY (per $ notional)
ex = [x["rv_spy"] / x["notional"] for x in rv if x["notional"]]
mm, ssd2 = stats(ex)
out["paper"]["excess_per_trade_mean"] = mm; out["paper"]["excess_per_trade_t"] = mm / (ssd2 / math.sqrt(len(ex)))
# monthly by exit
mon = collections.defaultdict(lambda: [0, 0.0, 0.0])
for x in rv:
    k = x["exit"][:7]; mon[k][0] += 1; mon[k][1] += x["pnl"]; mon[k][2] += x["rv_spy"]
out["paper_monthly"] = dict(sorted(mon.items()))
out["paper_per_sleeve"] = dict(sorted(per.items(), key=lambda kv: -(kv[1]["rv_spy"] or -1e9)))
os.makedirs(os.path.join(ROOT, "data/northstar"), exist_ok=True)
dest = os.path.join(ROOT, "data/northstar", f"baseline_{days[-1].replace('-', '')}.json")
json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print("wrote", dest)
o = {k: v for k, v in out.items() if k not in ("live_daily", "paper_per_sleeve")}
print(json.dumps(o, indent=1, ensure_ascii=False, default=str))
for k, v in out["paper_per_sleeve"].items():
    print(f"{k:45s} n={v['n']:4d} pnl={v['pnl']:9.0f} not={v['notional']:9.0f} r={(v['ret_on_notional'] or 0)*100:6.2f}% hit={v['hit']:.2f} rvSPY={v['rv_spy'] if v['rv_spy'] is None else round(v['rv_spy'])} ({v['rv_spy_n']}) {v['first_exit']}..{v['last_exit']}")
