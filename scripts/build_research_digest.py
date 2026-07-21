"""Build the research consumption digest (exp-20260721-006).

Contract: docs/research_digest_pipeline.md. Two modes:

  --backfill   One-time: assign stable ``entry_id: res-YYYYMMDD-slug`` lines to
               every ### section of docs/alpha_external_research_map.md that
               lacks one, and seed one append-only ``fresh`` event per new
               entry in data/research_digest/ledger.jsonl. Idempotent.

  (default)    Parse the map + ledger, run the recipe-lane precheck (reusing
               classify_recipe_lane_match from create_experiment_ticket.py --
               the same classifier the reservation guard uses), append
               ``lane_blocked`` events for fresh entries that match a burned
               lane, rank eligible entries, and emit
               data/research_digest/latest_digest.md and .json, each strictly
               under DIGEST_BYTE_CAP bytes. Idempotent across reruns.

Consumption state = latest ledger event per entry_id (append-only; never edit
history). The digest carries only entries an alpha agent may still propose:
``fresh`` first, ``declined`` downweighted; ``lane_blocked`` / ``proposed`` /
``rejected`` / ``accepted`` / ``parked`` are excluded.

Frozen-family screening is the SCAN task's job at extraction time (it has the
source context); this builder enforces only the recipe-lane precheck, which is
machine-checkable from text alone.

Run:
    .\\.venv\\Scripts\\python.exe -B scripts\\build_research_digest.py [--backfill]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from create_experiment_ticket import (  # noqa: E402
    _load_recipe_lanes,
    classify_recipe_lane_match,
)

REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
MAP_PATH = os.path.join(REPO_ROOT, "docs", "alpha_external_research_map.md")
DIGEST_DIR = os.path.join(REPO_ROOT, "data", "research_digest")
LEDGER_PATH = os.path.join(DIGEST_DIR, "ledger.jsonl")
DIGEST_MD_PATH = os.path.join(DIGEST_DIR, "latest_digest.md")
DIGEST_JSON_PATH = os.path.join(DIGEST_DIR, "latest_digest.json")

DIGEST_BYTE_CAP = 8192
TOP_K = 10
ACTOR = "build_research_digest"

# Optional structured markers future scan runs may embed in a section body
# (per contract section D). Missing proxy => downweighted, never excluded.
_FIELD_MARKERS = {
    "expectation_proxy": re.compile(r"^expectation_proxy:\s*(.+)$", re.M),
    "crowding": re.compile(r"^crowding:\s*(low|medium|high)\s*$", re.M | re.I),
    "falsifier": re.compile(r"^falsifier:\s*(.+)$", re.M),
    "pit_feasibility": re.compile(r"^pit_feasibility:\s*(.+)$", re.M),
}
_ENTRY_ID_RE = re.compile(r"^entry_id:\s*(res-\d{8}-[a-z0-9-]+)\s*$", re.M)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(title, used, max_len=48):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:max_len].rstrip("-")
    slug = slug or "entry"
    base, n = slug, 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def parse_map_sections(text):
    """Yield dicts {title, body, entry_id, span} for each ### section."""
    sections = []
    matches = list(re.finditer(r"^### (.+)$", text, re.M))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # A section body stops early at a ## heading (new top-level part).
        h2 = re.search(r"^## ", text[start:end], re.M)
        if h2:
            end = start + h2.start()
        body = text[start:end]
        id_match = _ENTRY_ID_RE.search(body)
        sections.append(
            {
                "title": m.group(1).strip(),
                "body": body,
                "entry_id": id_match.group(1) if id_match else None,
                "span": (start, end),
            }
        )
    return sections


def read_ledger():
    events = []
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def latest_status(events):
    state = {}
    for e in events:
        state[e["entry_id"]] = e
    return state


def append_events(new_events):
    if not new_events:
        return
    os.makedirs(DIGEST_DIR, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        for e in new_events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def backfill(date_tag="20260721"):
    """Assign entry_ids to sections lacking one; seed fresh ledger events."""
    text = open(MAP_PATH, encoding="utf-8").read()
    sections = parse_map_sections(text)
    used = {s["entry_id"].split("-", 2)[2] for s in sections if s["entry_id"]}
    inserts = []  # (position, entry_id)
    for s in sections:
        if s["entry_id"]:
            continue
        slug = _slugify(s["title"], used)
        entry_id = f"res-{date_tag}-{slug}"
        # Insert the id line at the end of the section body, before trailing
        # blank lines, so it stays inside the section on reparse.
        end = s["span"][1]
        insert_at = len(text[: end].rstrip()) if end == len(text) else end
        if end != len(text):
            trailing = text[s["span"][0]: end]
            insert_at = s["span"][0] + len(trailing.rstrip())
        inserts.append((insert_at, entry_id))
        s["entry_id"] = entry_id
    for pos, entry_id in sorted(inserts, reverse=True):
        text = text[:pos] + f"\n\nentry_id: {entry_id}" + text[pos:]
    if inserts:
        tmp = MAP_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, MAP_PATH)

    state = latest_status(read_ledger())
    now = _now_iso()
    seeds = [
        {
            "entry_id": s["entry_id"],
            "status": "fresh",
            "exp_id": None,
            "reason": "backfill seed",
            "actor": ACTOR,
            "ts": now,
        }
        for s in sections
        if s["entry_id"] and s["entry_id"] not in state
    ]
    append_events(seeds)
    return {"ids_assigned": len(inserts), "ledger_seeded": len(seeds), "sections": len(sections)}


def _excerpt(body, limit=220):
    body = _ENTRY_ID_RE.sub("", body)
    for marker in _FIELD_MARKERS.values():
        body = marker.sub("", body)
    para = next(
        (p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith(("-", "#", "```", "["))),
        "",
    )
    para = re.sub(r"\s+", " ", para)
    return para[:limit] + ("…" if len(para) > limit else "")


def _digest_lane_matches(text, lanes):
    """Digest-side lane precheck: STRICTER than the reservation guard.

    Papers describe burned-lane source domains in academic vocabulary without
    trading-recipe response phrases (found on first live run: the 8-K item-code
    entry had 2 source hits, 0 response hits). At digest stage a block is cheap
    (the agent simply doesn't propose from that entry), so >=2 distinct
    source-cluster hits from one lane suffice even without response hits. The
    shared reservation guard keeps its response-hit requirement — false blocks
    are expensive there. Full recipe matches are honored either way.
    """
    from create_experiment_ticket import _recipe_normalize, _recipe_phrase_hits

    matches = {m["lane_key"]: m for m in classify_recipe_lane_match(text, lanes)}
    normalized = _recipe_normalize(text)
    for lane in lanes:
        key = lane.get("lane_key")
        if key in matches:
            continue
        src_hits = _recipe_phrase_hits(normalized, lane.get("source_cluster"))
        if len(src_hits) >= 2:
            matches[key] = {
                "lane_key": key,
                "status": lane.get("status"),
                "source_hits": src_hits[:6],
                "response_hits": [],
                "digest_source_only": True,
            }
    return list(matches.values())


def build_digest():
    text = open(MAP_PATH, encoding="utf-8").read()
    sections = [s for s in parse_map_sections(text) if s["entry_id"]]
    events = read_ledger()
    state = latest_status(events)
    lanes = [
        l for l in _load_recipe_lanes(REPO_ROOT)
        if str(l.get("status", "")).lower() in {"parked", "triggered"}
    ]

    now = _now_iso()
    new_events = []
    entries = []
    for order, s in enumerate(sections):
        entry_id = s["entry_id"]
        status = (state.get(entry_id) or {}).get("status", "fresh")
        lane_matches = _digest_lane_matches(s["title"] + " " + s["body"], lanes)
        if lane_matches and status == "fresh":
            new_events.append(
                {
                    "entry_id": entry_id,
                    "status": "lane_blocked",
                    "exp_id": None,
                    "reason": "recipe precheck: " + ", ".join(m["lane_key"] for m in lane_matches[:2]),
                    "actor": ACTOR,
                    "ts": now,
                }
            )
            status = "lane_blocked"
        fields = {
            name: (rx.search(s["body"]).group(1).strip() if rx.search(s["body"]) else None)
            for name, rx in _FIELD_MARKERS.items()
        }
        entries.append(
            {
                "entry_id": entry_id,
                "title": s["title"],
                "status": status,
                "lane_matches": [m["lane_key"] for m in lane_matches],
                "has_expectation_proxy": bool(fields["expectation_proxy"]),
                "crowding": (fields["crowding"] or "").lower() or None,
                "expectation_proxy": fields["expectation_proxy"],
                "falsifier": fields["falsifier"],
                "pit_feasibility": fields["pit_feasibility"],
                "excerpt": _excerpt(s["body"]),
                "map_order": order,
            }
        )
    append_events(new_events)

    eligible = [e for e in entries if e["status"] in ("fresh", "declined")]

    def rank_key(e):
        crowd_rank = {"low": 0, "medium": 1, "high": 2}.get(e["crowding"], 1)
        return (
            0 if e["status"] == "fresh" else 1,
            0 if e["has_expectation_proxy"] else 1,
            crowd_rank,
            -e["map_order"],  # later sections are newer scans
        )

    ranked = sorted(eligible, key=rank_key)[:TOP_K]

    def render(entries_subset):
        lines = [
            "# Research Digest",
            "",
            f"generated_at: {now}  (exp-20260721-006 contract: docs/research_digest_pipeline.md)",
            f"eligible: {len(eligible)} of {len(entries)} entries; showing top {len(entries_subset)}.",
            "Consumption rule: for each entry below, pick or decline with a one-line",
            "reason appended to data/research_digest/ledger.jsonl; cite the entry_id in",
            "the ticket research_refs field. Digest grants NO guard exemptions.",
            "",
        ]
        for e in entries_subset:
            flags = []
            if not e["has_expectation_proxy"]:
                flags.append("no_expectation_proxy")
            if e["crowding"]:
                flags.append(f"crowding={e['crowding']}")
            lines.append(f"## {e['entry_id']} [{e['status']}{' ' + ' '.join(flags) if flags else ''}]")
            lines.append(f"**{e['title']}** — {e['excerpt']}")
            if e["expectation_proxy"]:
                lines.append(f"expectation_proxy: {e['expectation_proxy']}")
            if e["falsifier"]:
                lines.append(f"falsifier: {e['falsifier']}")
            lines.append("")
        return "\n".join(lines)

    subset = list(ranked)
    md = render(subset)
    while len(md.encode("utf-8")) >= DIGEST_BYTE_CAP and subset:
        subset.pop()
        md = render(subset)

    payload = {
        "schema_version": 1,
        "generated_at": now,
        "entry_count_total": len(entries),
        "eligible_count": len(eligible),
        "lane_blocked_total": sum(1 for e in entries if e["status"] == "lane_blocked"),
        "shown": [
            {k: e[k] for k in ("entry_id", "title", "status", "lane_matches", "has_expectation_proxy", "crowding", "expectation_proxy", "falsifier", "excerpt")}
            for e in subset
        ],
    }
    js = json.dumps(payload, ensure_ascii=False, indent=1)
    while len(js.encode("utf-8")) >= DIGEST_BYTE_CAP and payload["shown"]:
        payload["shown"].pop()
        js = json.dumps(payload, ensure_ascii=False, indent=1)

    os.makedirs(DIGEST_DIR, exist_ok=True)
    for path, content in ((DIGEST_MD_PATH, md), (DIGEST_JSON_PATH, js)):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content + "\n")
        os.replace(tmp, path)
    return {
        "entries": len(entries),
        "eligible": len(eligible),
        "lane_blocked": payload["lane_blocked_total"],
        "new_lane_blocked_events": len(new_events),
        "shown": len(subset),
        "md_bytes": len(md.encode("utf-8")) + 1,
        "json_bytes": len(js.encode("utf-8")) + 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true", help="Assign entry_ids and seed the ledger (one-time; idempotent).")
    args = parser.parse_args()
    if args.backfill:
        print(json.dumps(backfill(), indent=1))
    print(json.dumps(build_digest(), indent=1))


if __name__ == "__main__":
    main()
