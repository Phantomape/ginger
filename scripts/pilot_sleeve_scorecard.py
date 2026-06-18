"""Read-only fire-rate / conviction scorecard for default-off paper sleeves.

Phase 0 of closing the forward-feedback loop: you cannot validate a sleeve that
never fires. This scans data/paper_sleeves/*/snapshots.jsonl and ranks sleeves
by how often they actually emit a candidate (fire rate) alongside their closed
forward outcomes, so a live/forward pilot is chosen by conviction x fire-rate,
not by frozen-window EV. Pure read-only; writes a scorecard JSON for reference.

Usage:
    .\\.venv\\Scripts\\python.exe -B scripts\\pilot_sleeve_scorecard.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"
OUT_PATH = REPO_ROOT / "data" / "live_pilot" / "sleeve_scorecard.json"
RECENT_DAYS = 60


def _iter_snapshots(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _num(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    cards: list[dict[str, Any]] = []
    for snap_path in sorted(SLEEVES_DIR.glob("*/snapshots.jsonl")):
        sleeve = snap_path.parent.name
        snaps = _iter_snapshots(snap_path)
        if not snaps:
            continue
        # dedupe by asof_date, keep the last snapshot per day
        by_day: dict[str, dict[str, Any]] = {}
        for s in snaps:
            day = str(s.get("asof_date") or "")[:10]
            if day:
                by_day[day] = s
        days = sorted(by_day)
        if not days:
            continue
        n = len(days)
        fired = sum(1 for d in days if _num(by_day[d].get("candidate_count")) >= 1)
        recent = days[-RECENT_DAYS:]
        fired_recent = sum(1 for d in recent if _num(by_day[d].get("candidate_count")) >= 1)
        latest = by_day[days[-1]]
        closed = int(_num(latest.get("closed_position_count")))
        win_rate = latest.get("win_rate")
        realized = _num(latest.get("realized_pnl_to_date"))
        gate = latest.get("forward_paper_gate") or {}
        cards.append(
            {
                "sleeve": sleeve,
                "snapshot_days": n,
                "fire_rate": round(fired / n, 4),
                "fire_rate_recent60": round(fired_recent / len(recent), 4) if recent else 0.0,
                "days_fired": fired,
                "closed_rows": closed,
                "win_rate": round(float(win_rate), 4) if isinstance(win_rate, (int, float)) else None,
                "realized_pnl_to_date": round(realized, 2),
                "forward_gate_passed": bool(gate.get("passed")),
                "first_day": days[0],
                "last_day": days[-1],
            }
        )

    # Rank: prefer sleeves that fire often AND have some closed evidence.
    cards.sort(key=lambda c: (c["fire_rate_recent60"], c["fire_rate"], c["closed_rows"]), reverse=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump({"recent_days": RECENT_DAYS, "sleeves": cards}, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"{'sleeve':42} {'fire60':>7} {'fireAll':>7} {'closed':>6} {'win':>5} {'realPnL':>9}")
    print("-" * 84)
    for c in cards:
        win = f"{c['win_rate']:.2f}" if c["win_rate"] is not None else "  - "
        print(f"{c['sleeve'][:42]:42} {c['fire_rate_recent60']:>7.2f} {c['fire_rate']:>7.2f} "
              f"{c['closed_rows']:>6} {win:>5} {c['realized_pnl_to_date']:>9.0f}")

    fireable = [c for c in cards if c["fire_rate_recent60"] >= 0.25]
    print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"sleeves firing >=25% of recent {RECENT_DAYS} days: {len(fireable)}")
    if fireable:
        print("pilot candidates (fire often enough to accumulate forward rows):")
        for c in fireable[:5]:
            print(f"  - {c['sleeve']}  (fire60={c['fire_rate_recent60']:.2f}, closed={c['closed_rows']})")
    else:
        print("NONE fire >=25% recently -> this is exactly why forward rows never accumulate.")
        print("Either loosen a high-conviction sleeve to a daily-ranked signal feed, or")
        print("log the top-ranked candidate every day regardless of the top-1 trade gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
