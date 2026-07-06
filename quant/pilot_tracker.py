"""Manual small-live PILOT tracker (read-only over data/paper_sleeves/*/state.json).

Operating model (owner decision 2026-06-15, see memory incremental-sleeve-capital):
the default-off paper-maturation pipeline does not accumulate enough true-trigger
forward rows to ever clear the >=20 gate, so promising sleeves are promoted
straight to a small MANUAL live book ($10k) from day one. The owner executes
fills by hand and is the kill switch. This module does NOT trade and does NOT
recompute signals; it reads the existing sleeve state the daily pipeline already
writes and produces the two things a manual operator needs:

  1. a daily RECOMMENDATION SHEET per pilot - today's held + to-enter picks,
     logged point-in-time (the sleeve state is already PIT);
  2. a running SCORECARD per pilot - realized PnL and replacement value vs
     cash / SPY / QQQ, hit rate, trade count, and a pre-committed graduate/kill
     verdict.

Discipline kept from the retired heavy machinery (the real point of it):
  - signal stays rule-based and PIT (we read it, never override with hindsight);
  - every trade scored vs cash/SPY/QQQ (replacement value), not absolute PnL;
  - graduate/kill rule is pre-committed below, evaluated automatically.

Selection (owner): pilots are chosen by conviction x FIRE RATE, not in-sample EV.
  - allocator_top1: accepted source-priority allocator, capped to max 1 concurrent
    position ("top-1", owner does not want dispersion). ~18 picks/mo -> readable
    in ~5-6 weeks.
  - distribution_absorption: clean single-name sleeve, ~6/mo, drawdown ~0.
  - fundamental_growth_rs: the only sleeve currently firing live (already has
    closed/open rows), so it is the cheapest to take over as a manual pilot.

Run:
  .venv\\Scripts\\python.exe -B quant\\pilot_tracker.py
Outputs under data/pilots/.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import broad_market_sector_map
except ImportError:  # pragma: no cover - package-style import
    from quant import broad_market_sector_map


REPO_ROOT = Path(__file__).resolve().parents[1]
SLEEVE_DIR = REPO_ROOT / "data" / "paper_sleeves"
OUT_DIR = REPO_ROOT / "data" / "pilots"

# Per-position live book size. The owner allocates $10k per pilot position.
PILOT_NOTIONAL_USD = 10_000.0

PILOTS: list[dict[str, Any]] = [
    {
        "key": "allocator_top1",
        "label": "Source-priority allocator (TOP-1 only)",
        "sleeve": "accepted_helper_source_priority_allocator",
        "max_concurrent": 1,  # owner: do not disperse; hold at most one
    },
    {
        "key": "distribution_absorption",
        "label": "Distribution-day absorption leadership",
        "sleeve": "distribution_day_absorption_leadership",
        "max_concurrent": None,
    },
    {
        "key": "fundamental_growth_rs",
        "label": "Fundamental growth + RS",
        "sleeve": "fundamental_growth_rs",
        "max_concurrent": None,
    },
]

# Pre-committed graduate / kill rule (decide BEFORE collecting, per the model).
GRADUATE_MIN_CLOSED = 20          # or use elapsed >= ~3 months operationally
GRADUATE_MIN_RV_SPY_USD = 0.0     # must beat same-day SPY after costs (sum > 0)
GRADUATE_MAX_BOOK_DD_PCT = 0.15   # realized-curve drawdown ceiling

# Manual RISK OVERLAY only - does NOT change the sleeve's measured 10-day-hold
# logic. The sleeves carry no stop; this flags a held position that has fallen
# this far below entry so the operator can cut it by hand. Stop-fires should be
# logged separately so naive-10d vs 10d+stop can be compared later.
STOP_LOSS_PCT = 0.15              # cut a held position down -15% from entry

# Cross-pilot THEME concentration (exp-20260706-001). Ticker-level overlap
# missed the 2026-07 semiconductor pile-up (CRDO/MU/WDC/NVMI/INTC across three
# pilots, all Technology) because no two pilots held the same name. Alert when
# one sector or industry group carries this many positions, or this share of
# the total actionable pilot exposure. Report-only; the operator decides.
CONCENTRATION_ALERT_MIN_POSITIONS = 3
CONCENTRATION_ALERT_MIN_EXPOSURE_SHARE = 0.5


# ---- schema-tolerant field extraction ------------------------------------

def _first(row: dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _ticker(row: dict[str, Any]) -> str:
    return str(_first(row, "ticker") or "?").upper()


def _notional(row: dict[str, Any]) -> float:
    v = _num(_first(row, "notional_usd", "notional", "paper_notional_usd",
                    "safe_paper_notional_usd", "baseline_safe_paper_notional_usd"))
    return v if v and v > 0 else 4000.0


def _return_pct(row: dict[str, Any]) -> float | None:
    return _num(_first(row, "return_pct_net", "net_return_pct", "gross_return_pct"))


def _scale(row: dict[str, Any]) -> float:
    """Rescale sleeve-notional dollars to the pilot's $10k book."""
    return PILOT_NOTIONAL_USD / _notional(row)


def _pilot_pnl(row: dict[str, Any]) -> float | None:
    ret = _return_pct(row)
    if ret is not None:
        return round(ret * PILOT_NOTIONAL_USD, 2)
    pnl = _num(_first(row, "pnl"))
    return round(pnl * _scale(row), 2) if pnl is not None else None


def _rv(row: dict[str, Any], field: str) -> float | None:
    v = _num(row.get(field))
    return round(v * _scale(row), 2) if v is not None else None


# ---- load + select --------------------------------------------------------

def _load_state(sleeve: str) -> dict[str, Any]:
    p = SLEEVE_DIR / sleeve / "state.json"
    if not p.exists():
        return {"_missing": True}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def _rank_key(row: dict[str, Any]) -> tuple:
    rank = _num(_first(row, "source_priority_rank"))
    score = _num(_first(row, "candidate_score", "source_priority_score"))
    entry = str(_first(row, "entry_date", "signal_date", "date") or "")
    return (rank if rank is not None else 1e9,
            -(score if score is not None else -1e9),
            entry)


def _apply_concurrency(open_rows: list[dict[str, Any]], cap: int | None):
    if cap is None or len(open_rows) <= cap:
        return list(open_rows), []
    ordered = sorted(open_rows, key=_rank_key)
    return ordered[:cap], ordered[cap:]


# ---- scorecard ------------------------------------------------------------

def _book_drawdown(closed: list[dict[str, Any]]) -> dict[str, float]:
    rows = sorted(closed, key=lambda r: str(_first(r, "exit_date", "entry_date") or ""))
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rows:
        p = _pilot_pnl(r) or 0.0
        cum += p
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    denom = max(peak, PILOT_NOTIONAL_USD)
    return {"realized_pnl": round(cum, 2),
            "max_drawdown_usd": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd / denom, 4) if denom else 0.0}


def _scorecard(pilot: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    closed = [r for r in (state.get("closed_positions") or []) if isinstance(r, dict)]
    open_rows = [r for r in (state.get("open_positions") or []) if isinstance(r, dict)]
    pending = [r for r in (state.get("pending_entries") or []) if isinstance(r, dict)]

    n = len(closed)
    wins = sum(1 for r in closed if (_pilot_pnl(r) or 0.0) > 0)
    rv_cash = sum((_rv(r, "replacement_value_vs_cash_usd") or 0.0) for r in closed)
    rv_spy = sum((_rv(r, "replacement_value_vs_spy_usd") or 0.0) for r in closed)
    rv_qqq = sum((_rv(r, "replacement_value_vs_qqq_usd") or 0.0) for r in closed)
    rv_rows = sum(1 for r in closed if r.get("replacement_value_vs_spy_usd") is not None)
    dd = _book_drawdown(closed)

    drawdown_breached = dd["max_drawdown_pct"] >= GRADUATE_MAX_BOOK_DD_PCT

    # pre-committed verdict. The drawdown kill switch applies immediately;
    # sample-size gates only decide whether a surviving pilot can graduate.
    if drawdown_breached:
        verdict = "KILL"
        verdict_note = (
            "book drawdown {actual:.1%} breaches {limit:.0%} ceiling -> stop pilot"
        ).format(
            actual=dd["max_drawdown_pct"],
            limit=GRADUATE_MAX_BOOK_DD_PCT,
        )
    elif n < GRADUATE_MIN_CLOSED:
        verdict = "COLLECTING"
        verdict_note = f"{n}/{GRADUATE_MIN_CLOSED} closed trades; keep tracking"
    elif rv_spy > GRADUATE_MIN_RV_SPY_USD and dd["max_drawdown_pct"] < GRADUATE_MAX_BOOK_DD_PCT:
        verdict = "GRADUATE"
        verdict_note = "beats SPY after costs within drawdown ceiling -> scale up"
    else:
        verdict = "KILL"
        verdict_note = "sample reached but does not beat SPY / breaches drawdown -> stop"

    return {
        "pilot": pilot["key"],
        "label": pilot["label"],
        "sleeve": pilot["sleeve"],
        "as_of": state.get("updated_at"),
        "closed_trades": n,
        "open_positions": len(open_rows),
        "pending_entries": len(pending),
        "hit_rate": round(wins / n, 3) if n else None,
        "realized_pilot_pnl_usd": dd["realized_pnl"],
        "replacement_value_rows": rv_rows,
        "rv_vs_cash_usd": round(rv_cash, 2),
        "rv_vs_spy_usd": round(rv_spy, 2),
        "rv_vs_qqq_usd": round(rv_qqq, 2),
        "book_max_drawdown_usd": dd["max_drawdown_usd"],
        "book_max_drawdown_pct": dd["max_drawdown_pct"],
        "drawdown_ceiling_breached": drawdown_breached,
        "verdict": verdict,
        "verdict_note": verdict_note,
    }


# ---- recommendation sheet -------------------------------------------------

def _days_remaining(row: dict[str, Any]) -> int | None:
    hold = _num(_first(row, "hold_days"))
    obs = _num(_first(row, "observed_trading_days"))
    if hold is None or obs is None:
        return None
    return int(hold - obs)


def _hold_status(row: dict[str, Any]) -> str:
    rem = _days_remaining(row)
    if rem is None:
        return "HOLD"
    if rem <= 0:
        return "EXIT_NOW"          # hold elapsed -> sell at next open
    if rem == 1:
        return "EXIT_NEXT_SESSION"  # one trading day left
    return "HOLD"


def _rec_row(row: dict[str, Any], status: str) -> dict[str, Any]:
    entry = _num(_first(row, "entry_price", "entry_raw_open"))
    last = _num(_first(row, "last_price", "decision_close_price"))
    unreal_pct = (last / entry - 1.0) if (entry and last and entry > 0) else None
    if unreal_pct is None:
        stop_status = "no_price"          # e.g. allocator rows carry no last_price
    elif unreal_pct <= -STOP_LOSS_PCT:
        stop_status = "STOP_HIT"
    else:
        stop_status = "OK"
    return {
        "status": status,
        "ticker": _ticker(row),
        "signal_date": _first(row, "signal_date", "date"),
        "entry_date": _first(row, "entry_date"),
        "exit_date": _first(row, "exit_date"),
        "entry_price": entry,
        "exit_price": _num(_first(row, "exit_price")),
        "last_price": last,
        "unrealized_pct": round(unreal_pct, 4) if unreal_pct is not None else None,
        "stop_loss_pct": STOP_LOSS_PCT,
        "stop_status": stop_status,
        "hold_days": _first(row, "hold_days"),
        "days_held": _first(row, "observed_trading_days"),
        "days_remaining": _days_remaining(row),
        "pilot_pnl_usd": _pilot_pnl(row),
        "pilot_notional_usd": PILOT_NOTIONAL_USD,
        "exit_rule": f"time exit after {_first(row, 'hold_days') or '?'} trading days held",
        "source": _first(row, "source", "primary_source", "strategy"),
        "source_priority_rank": _first(row, "source_priority_rank"),
        "candidate_score": _num(_first(row, "candidate_score", "source_priority_score")),
    }


def _recommendations(
    pilot: dict[str, Any],
    state: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    open_rows = [r for r in (state.get("open_positions") or []) if isinstance(r, dict)]
    pending = [r for r in (state.get("pending_entries") or []) if isinstance(r, dict)]
    closed = [r for r in (state.get("closed_positions") or []) if isinstance(r, dict)]
    as_of_day = str(state.get("updated_at") or "")[:10]
    cap = pilot.get("max_concurrent")
    held, skipped = _apply_concurrency(open_rows, cap)
    # If the scorecard has killed the pilot, continue showing held/exiting rows
    # but block new entries in the manual recommendation sheet.
    pend_allowed, pend_skipped = ([], pending)
    if scorecard.get("verdict") == "KILL":
        pend_allowed, pend_skipped = [], pending
        pending_skip_status = "SKIP_pilot_kill_verdict"
    else:
        pending_skip_status = "SKIP_concurrency_cap"
    # if we are at the concurrency cap, new pending entries are skipped too
    if scorecard.get("verdict") != "KILL" and (cap is None or len(held) < cap):
        room = None if cap is None else cap - len(held)
        if room is None:
            pend_allowed, pend_skipped = pending, []
        else:
            pend_ordered = sorted(pending, key=_rank_key)
            pend_allowed, pend_skipped = pend_ordered[:room], pend_ordered[room:]
    # exits the sleeve executed in its most recent update -> operator confirms sale
    exits_today = [
        _rec_row(r, "EXIT_EXECUTED")
        for r in closed
        if str(_first(r, "exit_date") or "")[:10] == as_of_day and as_of_day
    ]
    rows = (
        [_rec_row(r, _hold_status(r)) for r in held]
        + [_rec_row(r, "ENTER_NEXT_OPEN") for r in pend_allowed]
        + [_rec_row(r, "SKIP_concurrency_cap") for r in skipped]
        + [_rec_row(r, pending_skip_status) for r in pend_skipped]
    )
    return {
        "pilot": pilot["key"],
        "label": pilot["label"],
        "sleeve": pilot["sleeve"],
        "as_of": state.get("updated_at"),
        "max_concurrent": cap,
        "pilot_verdict": scorecard.get("verdict"),
        "pilot_verdict_note": scorecard.get("verdict_note"),
        "new_entries_blocked": scorecard.get("verdict") == "KILL",
        "actionable": [r for r in rows if not r["status"].startswith("SKIP")],
        "exits_executed_today": exits_today,
        "skipped": [r for r in rows if r["status"].startswith("SKIP")],
    }


# ---- cross-pilot overlap --------------------------------------------------

def _cross_pilot_overlap(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same ticker held/entered by more than one pilot = stacked real exposure."""
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        for a in r["actionable"]:
            by_ticker[a["ticker"]].append({
                "pilot": r["label"],
                "pilot_key": r["pilot"],
                "label": r["label"],
                "sleeve": r["sleeve"],
                "pilot_verdict": r.get("pilot_verdict"),
                "pilot_verdict_note": r.get("pilot_verdict_note"),
                "new_entries_blocked": bool(r.get("new_entries_blocked")),
                "status": a["status"],
                "actionable_status": a["status"],
                "stop_status": a.get("stop_status"),
                "entry_date": a.get("entry_date"),
                "days_held": a.get("days_held"),
                "days_remaining": a.get("days_remaining"),
                "unrealized_pct": a.get("unrealized_pct"),
                "pilot_notional_usd": a.get("pilot_notional_usd") or PILOT_NOTIONAL_USD,
            })
    overlaps = []
    for ticker, entries in sorted(by_ticker.items()):
        if len({e["pilot"] for e in entries}) > 1:
            pilot_statuses: dict[str, list[str]] = defaultdict(list)
            for entry in entries:
                pilot_statuses[str(entry["pilot_key"])].append(str(entry["status"]))
            overlaps.append({
                "ticker": ticker,
                "pilots": [e["pilot"] for e in entries],
                "participant_context": entries,
                "pilot_verdicts": {
                    str(e["pilot_key"]): e.get("pilot_verdict") for e in entries
                },
                "pilot_statuses": dict(pilot_statuses),
                "new_entries_blocked_by_pilot": {
                    str(e["pilot_key"]): bool(e.get("new_entries_blocked")) for e in entries
                },
                "positions": len(entries),
                "total_exposure_usd": round(
                    sum(float(e.get("pilot_notional_usd") or 0.0) for e in entries),
                    2,
                ),
            })
    return overlaps


def _cross_pilot_concentration(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """Sector/industry exposure across ALL actionable pilot positions.

    Catches stacked theme risk that ticker-level overlap cannot see (three
    pilots long three different semiconductor names is one bet, not three).
    """
    cache = broad_market_sector_map.load_cache()
    positions: list[dict[str, Any]] = []
    for r in recs:
        for a in r["actionable"]:
            ticker = str(a.get("ticker") or "").upper()
            lookup = broad_market_sector_map.lookup_sector(ticker, cache)
            ok = lookup.get("status") == broad_market_sector_map.OK_STATUS
            positions.append({
                "ticker": ticker,
                "pilot": r["pilot"],
                "status": a.get("status"),
                "exposure_usd": float(a.get("pilot_notional_usd") or PILOT_NOTIONAL_USD),
                "sector": (lookup.get("sector") if ok else None) or "UNKNOWN",
                "industry": (lookup.get("industry") if ok else None) or "UNKNOWN",
            })
    total_exposure = sum(p["exposure_usd"] for p in positions)

    def _groups(level: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for p in positions:
            grouped[p[level]].append(p)
        out = []
        for key, rows in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            exposure = sum(p["exposure_usd"] for p in rows)
            share = exposure / total_exposure if total_exposure else 0.0
            alert = key != "UNKNOWN" and (
                len(rows) >= CONCENTRATION_ALERT_MIN_POSITIONS
                or (len(rows) >= 2 and share >= CONCENTRATION_ALERT_MIN_EXPOSURE_SHARE)
            )
            out.append({
                level: key,
                "positions": len(rows),
                "tickers": sorted({p["ticker"] for p in rows}),
                "pilots": sorted({p["pilot"] for p in rows}),
                "exposure_usd": round(exposure, 2),
                "exposure_share": round(share, 4),
                "alert": alert,
            })
        return out

    by_sector = _groups("sector")
    by_industry = _groups("industry")
    return {
        "total_actionable_exposure_usd": round(total_exposure, 2),
        "position_count": len(positions),
        "alert_rule": {
            "min_positions": CONCENTRATION_ALERT_MIN_POSITIONS,
            "min_exposure_share": CONCENTRATION_ALERT_MIN_EXPOSURE_SHARE,
        },
        "by_sector": by_sector,
        "by_industry": by_industry,
        "alerts": [g for g in by_sector if g["alert"]]
        + [g for g in by_industry if g["alert"]],
    }


def _stop_alerts(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Held positions that have breached the manual stop -> cut by hand today."""
    alerts = []
    for r in recs:
        for a in r["actionable"]:
            if a.get("stop_status") == "STOP_HIT":
                alerts.append({
                    "pilot": r["label"], "ticker": a["ticker"],
                    "entry_price": a["entry_price"], "last_price": a["last_price"],
                    "unrealized_pct": a["unrealized_pct"], "stop_loss_pct": a["stop_loss_pct"],
                    "days_held": a["days_held"], "hold_days": a["hold_days"],
                })
    return alerts


# ---- render ---------------------------------------------------------------

def _fmt_usd(v: Any) -> str:
    return f"${v:,.0f}" if isinstance(v, (int, float)) else "-"


def _render_md(recs: list[dict[str, Any]], cards: list[dict[str, Any]],
               overlaps: list[dict[str, Any]], stop_alerts: list[dict[str, Any]],
               as_of: str,
               concentration: dict[str, Any] | None = None) -> str:
    L = [f"# Pilot tracker - as of {as_of}", "",
         f"Per-position book: {_fmt_usd(PILOT_NOTIONAL_USD)}. Read-only; manual execution.",
         "Graduate/kill rule (pre-committed): >= {} closed AND sum rv_vs_SPY > 0 AND book DD < {:.0%}."
         .format(GRADUATE_MIN_CLOSED, GRADUATE_MAX_BOOK_DD_PCT),
         "Manual stop overlay: cut a held position at -{:.0%} from entry (does not change the sleeve).".format(STOP_LOSS_PCT),
         ""]
    if stop_alerts:
        L += [f"## [!] STOP-LOSS alerts - cut by hand today (stop = -{STOP_LOSS_PCT:.0%})", ""]
        for s in stop_alerts:
            L.append("- **SELL {tk}** ({pl}): {up:+.1%} from entry {ep} -> last {lp}".format(
                tk=s["ticker"], pl=s["pilot"], up=s["unrealized_pct"],
                ep=f'{s["entry_price"]:.2f}' if isinstance(s["entry_price"], (int, float)) else "?",
                lp=f'{s["last_price"]:.2f}' if isinstance(s["last_price"], (int, float)) else "?"))
        L.append("")
    if overlaps:
        L += ["## [!] Cross-pilot overlap (stacked exposure on one name)", ""]
        for o in overlaps:
            L.append("- **{tk}**: held by {n} pilots ({pl}) -> {ex} real exposure".format(
                tk=o["ticker"], n=o["positions"], pl=", ".join(o["pilots"]),
                ex=_fmt_usd(o["total_exposure_usd"])))
            for p in o.get("participant_context") or []:
                blocked = ", new entries blocked" if p.get("new_entries_blocked") else ""
                L.append("  - {pilot}: {status}, verdict {verdict}{blocked}".format(
                    pilot=p.get("pilot"),
                    status=p.get("actionable_status") or p.get("status"),
                    verdict=p.get("pilot_verdict") or "UNKNOWN",
                    blocked=blocked,
                ))
        L.append("")
    conc_alerts = (concentration or {}).get("alerts") or []
    if conc_alerts:
        L += ["## [!] Cross-pilot theme concentration (one theme, stacked books)", ""]
        for g in conc_alerts:
            level = "sector" if "sector" in g else "industry"
            L.append("- **{key}** ({lv}): {n} positions across {np} pilot(s) "
                     "({tk}) -> {ex} ({sh:.0%} of actionable exposure)".format(
                         key=g.get("sector") or g.get("industry"), lv=level,
                         n=g["positions"], np=len(g["pilots"]),
                         tk=", ".join(g["tickers"]),
                         ex=_fmt_usd(g["exposure_usd"]), sh=g["exposure_share"]))
        L.append("")
    L += ["## Scorecard", "",
         "| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |",
         "|---|--:|--:|--:|--:|--:|--:|--:|---|"]
    for c in cards:
        L.append("| {label} | {n} | {hr} | {pnl} | {rc} | {rs} | {rq} | {dd} | **{v}** |".format(
            label=c["label"], n=c["closed_trades"],
            hr=f'{c["hit_rate"]:.0%}' if c["hit_rate"] is not None else "-",
            pnl=_fmt_usd(c["realized_pilot_pnl_usd"]), rc=_fmt_usd(c["rv_vs_cash_usd"]),
            rs=_fmt_usd(c["rv_vs_spy_usd"]), rq=_fmt_usd(c["rv_vs_qqq_usd"]),
            dd=f'{c["book_max_drawdown_pct"]:.1%}', v=c["verdict"]))
    def _px(v: Any) -> str:
        return f"{v:.2f}" if isinstance(v, (int, float)) else "next-open"

    order = {"EXIT_NOW": 0, "EXIT_NEXT_SESSION": 1, "ENTER_NEXT_OPEN": 2, "HOLD": 3}
    L += ["", "## Today's signals (BUY / HOLD / SELL)", ""]
    for r in recs:
        L.append(f"### {r['label']}  (`{r['sleeve']}`, max_concurrent={r['max_concurrent']})")
        acts = sorted(r["actionable"], key=lambda a: order.get(a["status"], 9))
        exits_done = r.get("exits_executed_today") or []
        if r.get("new_entries_blocked"):
            L.append("- _new entries blocked: KILL verdict_")
        if not acts and not exits_done:
            L.append("- _no position / no signal today_")
        for a in acts:
            if a["status"] in ("EXIT_NOW", "EXIT_NEXT_SESSION"):
                L.append("- **SELL ({st})** {tk}: hold elapsed (day {dh}/{hd}); entry {ep}, last {lp}".format(
                    st=a["status"], tk=a["ticker"], dh=a["days_held"], hd=a["hold_days"],
                    ep=_px(a["entry_price"]), lp=_px(a["last_price"])))
            elif a["status"] == "ENTER_NEXT_OPEN":
                L.append("- **BUY (next open)** {tk} (signal {sd}); {ex}; rank={rk} score={sc}".format(
                    tk=a["ticker"], sd=a["signal_date"], ex=a["exit_rule"],
                    rk=a["source_priority_rank"], sc=a["candidate_score"]))
            else:  # HOLD
                up = a.get("unrealized_pct")
                tag = " **[STOP_HIT -> SELL]**" if a.get("stop_status") == "STOP_HIT" else ""
                L.append("- hold {tk}: day {dh}/{hd} ({dr} left); entry {ep}, last {lp} ({up}){tag}".format(
                    tk=a["ticker"], dh=a["days_held"], hd=a["hold_days"], dr=a["days_remaining"],
                    ep=_px(a["entry_price"]), lp=_px(a["last_price"]),
                    up=f"{up:+.1%}" if isinstance(up, (int, float)) else "n/a", tag=tag))
        for e in exits_done:
            L.append("- _exited today_ {tk} @ {xp} on {xd} (pilot PnL {pnl}) - confirm the sale".format(
                tk=e["ticker"], xp=_px(e["exit_price"]), xd=e["exit_date"],
                pnl=_fmt_usd(e["pilot_pnl_usd"])))
        for s in r["skipped"]:
            L.append(f"- _skip_ {s['ticker']} ({s['status']})")
        L.append("")
    return "\n".join(L) + "\n"


def generate(write: bool = True) -> dict[str, Any]:
    """Build pilot scorecards + recommendations from sleeve state.

    Read-only. Safe to call from the daily run; never raises into the caller
    (callers should still wrap in try/except for defence in depth).
    """
    recs, cards = [], []
    as_of = ""
    for pilot in PILOTS:
        state = _load_state(pilot["sleeve"])
        if state.get("_missing") or state.get("_error"):
            cards.append({"pilot": pilot["key"], "label": pilot["label"],
                          "sleeve": pilot["sleeve"], "closed_trades": 0, "hit_rate": None,
                          "realized_pilot_pnl_usd": 0, "rv_vs_cash_usd": 0, "rv_vs_spy_usd": 0,
                          "rv_vs_qqq_usd": 0, "book_max_drawdown_pct": 0.0,
                          "verdict": "NO_STATE", "verdict_note": state.get("_error", "no state file")})
            recs.append({"pilot": pilot["key"], "label": pilot["label"], "sleeve": pilot["sleeve"],
                         "as_of": None, "max_concurrent": pilot.get("max_concurrent"),
                         "pilot_verdict": "NO_STATE",
                         "pilot_verdict_note": state.get("_error", "no state file"),
                         "new_entries_blocked": False,
                         "actionable": [], "skipped": []})
            continue
        as_of = max(as_of, str(state.get("updated_at") or ""))
        card = _scorecard(pilot, state)
        cards.append(card)
        recs.append(_recommendations(pilot, state, card))

    overlaps = _cross_pilot_overlap(recs)
    concentration = _cross_pilot_concentration(recs)
    stop_alerts = _stop_alerts(recs)
    scorecard_payload = {
        "as_of": as_of, "per_position_notional_usd": PILOT_NOTIONAL_USD,
        "graduate_rule": {"min_closed": GRADUATE_MIN_CLOSED,
                          "min_rv_spy_usd": GRADUATE_MIN_RV_SPY_USD,
                          "max_book_dd_pct": GRADUATE_MAX_BOOK_DD_PCT},
        "stop_loss_pct": STOP_LOSS_PCT,
        "cross_pilot_overlap": overlaps,
        "cross_pilot_concentration": concentration,
        "stop_alerts": stop_alerts,
        "scorecards": cards,
    }
    rec_payload = {"as_of": as_of, "cross_pilot_overlap": overlaps,
                   "cross_pilot_concentration": concentration,
                   "stop_alerts": stop_alerts, "recommendations": recs}
    md = _render_md(recs, cards, overlaps, stop_alerts, as_of or "latest",
                    concentration=concentration)
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "pilot_scorecard.json").write_text(json.dumps(scorecard_payload, indent=2), encoding="utf-8")
        (OUT_DIR / f"pilot_recommendations_{as_of[:10] or 'latest'}.json").write_text(
            json.dumps(rec_payload, indent=2), encoding="utf-8")
        (OUT_DIR / "pilot_tracker.md").write_text(md, encoding="utf-8")
    return {"as_of": as_of, "scorecards": cards, "recommendations": recs,
            "cross_pilot_overlap": overlaps,
            "cross_pilot_concentration": concentration,
            "stop_alerts": stop_alerts, "markdown": md}


def main() -> None:
    print(generate(write=True)["markdown"])


if __name__ == "__main__":
    main()
