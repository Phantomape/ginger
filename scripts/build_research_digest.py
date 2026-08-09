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
import hashlib
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
MECHANISM_SCAN_PATH = os.path.join(DIGEST_DIR, "latest_mechanism_scan.json")

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
    # Versioned mechanism generators write these provenance markers.  They are
    # deliberately optional so the historical hand-curated map remains valid.
    "generator_id": re.compile(r"^generator_id:\s*([a-z0-9_-]+)\s*$", re.M | re.I),
    "generator_version": re.compile(r"^generator_version:\s*([^\s]+)\s*$", re.M),
    "mechanism_id": re.compile(r"^mechanism_id:\s*([a-z0-9_-]+)\s*$", re.M | re.I),
    "evidence_grade": re.compile(
        r"^evidence_grade:\s*(lead|observer|observed_only|gate_candidate)\s*$",
        re.M | re.I,
    ),
    "market_prior_status": re.compile(
        r"^market_prior_status:\s*(observable|unidentified)\s*$", re.M | re.I
    ),
    "source_authorization": re.compile(r"^source_authorization:\s*(.+)$", re.M),
    "scan_run_id": re.compile(r"^scan_run_id:\s*([a-z0-9_-]+)\s*$", re.M | re.I),
    "scan_completed_at": re.compile(r"^scan_completed_at:\s*(\S+)\s*$", re.M),
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


def _extract_fields(body):
    """Extract optional map markers without inventing missing provenance."""
    fields = {}
    for name, rx in _FIELD_MARKERS.items():
        match = rx.search(body)
        value = match.group(1).strip() if match else None
        if name in {"crowding", "evidence_grade", "market_prior_status"} and value:
            value = value.lower()
        fields[name] = value
    return fields


def _canonical_hash(value):
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_mechanism_scan_manifest(path=None, known_entry_ids=None):
    """Read and verify the published scan batch, including zero-lead runs.

    The sidecar is the JSON emitted by ``alpha_search.py build-mechanism-leads``.
    It is separate from map sections because a legitimate abstention has no
    section to carry a freshness marker.  A non-empty batch is considered
    published only when all rendered entry IDs are present in the map.
    """
    path = path or MECHANISM_SCAN_PATH
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict) or payload.get("record_type") != "external_mechanism_lead_batch":
        raise ValueError("invalid latest_mechanism_scan: expected external_mechanism_lead_batch")
    claimed_batch_hash = payload.get("batch_hash")
    unhashed_payload = dict(payload)
    unhashed_payload.pop("batch_hash", None)
    if claimed_batch_hash != _canonical_hash(unhashed_payload):
        raise ValueError("invalid latest_mechanism_scan: batch_hash mismatch")
    root_required = {
        "schema_version",
        "record_type",
        "generator_provenance",
        "history_policy",
        "history_read_before_generation",
        "history_veto_applied_after_generation",
        "outcome_blind",
        "lead_count",
        "research_map_sections",
        "scan_manifest",
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
        "panel_built",
        "batch_hash",
    }
    root_missing = sorted(root_required - set(payload))
    if root_missing:
        raise ValueError(f"invalid latest_mechanism_scan: missing root fields {root_missing}")
    if payload["schema_version"] != 1:
        raise ValueError("invalid latest_mechanism_scan: root schema mismatch")
    if payload["outcome_blind"] is not True:
        raise ValueError("invalid latest_mechanism_scan: root outcome_blind must be true")
    if payload["history_read_before_generation"] is not False:
        raise ValueError("invalid latest_mechanism_scan: root history order mismatch")
    if payload["history_veto_applied_after_generation"] is not True:
        raise ValueError("invalid latest_mechanism_scan: root history veto must be true")
    for field in (
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
        "panel_built",
    ):
        if payload[field] is not False:
            raise ValueError(f"invalid latest_mechanism_scan: root {field} must be false")
    manifest = payload.get("scan_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("invalid latest_mechanism_scan: missing scan_manifest")
    required = {
        "schema_version",
        "record_type",
        "status",
        "generator_id",
        "generator_version",
        "skill_sha256",
        "run_id",
        "research_date",
        "timezone",
        "data_cutoff",
        "completed_at",
        "lead_count",
        "outcome_blind",
        "history_read_before_generation",
        "history_veto_applied_after_generation",
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
        "panel_built",
        "manifest_hash",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ValueError(f"invalid latest_mechanism_scan: missing {missing}")
    if manifest["schema_version"] != 1 or manifest["record_type"] != "external_mechanism_scan_manifest":
        raise ValueError("invalid latest_mechanism_scan: schema or record_type mismatch")
    if manifest["status"] not in {"leads_generated", "no_new_lead"}:
        raise ValueError("invalid latest_mechanism_scan: unknown status")
    if manifest["outcome_blind"] is not True:
        raise ValueError("invalid latest_mechanism_scan: outcome_blind must be true")
    if manifest["history_read_before_generation"] is not False:
        raise ValueError(
            "invalid latest_mechanism_scan: history_read_before_generation must be false"
        )
    if manifest["history_veto_applied_after_generation"] is not True:
        raise ValueError(
            "invalid latest_mechanism_scan: history_veto_applied_after_generation must be true"
        )
    for field in (
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
        "panel_built",
    ):
        if manifest[field] is not False:
            raise ValueError(f"invalid latest_mechanism_scan: {field} must be false")
    lead_count = manifest["lead_count"]
    if not isinstance(lead_count, int) or isinstance(lead_count, bool) or not 0 <= lead_count <= 2:
        raise ValueError("invalid latest_mechanism_scan: lead_count must be 0..2")
    if (manifest["status"] == "no_new_lead") != (lead_count == 0):
        raise ValueError("invalid latest_mechanism_scan: status/lead_count mismatch")
    claimed_hash = manifest["manifest_hash"]
    unhashed = dict(manifest)
    unhashed.pop("manifest_hash", None)
    if claimed_hash != _canonical_hash(unhashed):
        raise ValueError("invalid latest_mechanism_scan: manifest_hash mismatch")
    rows = payload.get("research_map_sections")
    if not isinstance(rows, list) or len(rows) != lead_count:
        raise ValueError("invalid latest_mechanism_scan: section count mismatch")
    if payload["lead_count"] != lead_count:
        raise ValueError("invalid latest_mechanism_scan: root/manifest lead_count mismatch")
    provenance = payload["generator_provenance"]
    if not isinstance(provenance, dict):
        raise ValueError("invalid latest_mechanism_scan: generator_provenance must be an object")
    provenance_pairs = {
        "generator_id": "generator_id",
        "generator_version": "generator_version",
        "skill_sha256": "skill_sha256",
        "run_id": "run_id",
        "research_date": "research_date",
        "timezone": "timezone",
        "data_cutoff": "data_cutoff",
        "history_checked_at": "completed_at",
    }
    for root_key, manifest_key in provenance_pairs.items():
        if provenance.get(root_key) != manifest[manifest_key]:
            raise ValueError(
                f"invalid latest_mechanism_scan: provenance mismatch for {root_key}"
            )
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("record_type") != "research_map_mechanism_lead":
            raise ValueError(f"invalid latest_mechanism_scan: invalid section {index}")
        if not row.get("entry_id") or not isinstance(row.get("research_map_markdown"), str):
            raise ValueError(f"invalid latest_mechanism_scan: incomplete section {index}")
        if row.get("eligible_for_panel") is not False or row.get("gate_candidate") is not False:
            raise ValueError(f"invalid latest_mechanism_scan: section {index} escalates readiness")
        for field in (
            "experiment_id_reserved",
            "trade_enabled",
            "orders_enabled",
            "ranking_enabled",
            "strategy_changed",
        ):
            if row.get(field) is not False:
                raise ValueError(
                    f"invalid latest_mechanism_scan: section {index} {field} must be false"
                )
    if known_entry_ids is not None:
        batch_entry_ids = {
            row.get("entry_id") for row in rows if isinstance(row, dict) and row.get("entry_id")
        }
        if len(batch_entry_ids) != lead_count:
            raise ValueError("invalid latest_mechanism_scan: missing or duplicate entry_id")
        unpublished = sorted(batch_entry_ids - set(known_entry_ids))
        if unpublished:
            raise ValueError(f"invalid latest_mechanism_scan: unpublished map entries {unpublished}")
    return {
        "status": manifest["status"],
        "generator_id": manifest["generator_id"],
        "generator_version": manifest["generator_version"],
        "skill_sha256": manifest["skill_sha256"],
        "scan_run_id": manifest["run_id"],
        "research_date": manifest["research_date"],
        "timezone": manifest["timezone"],
        "data_cutoff": manifest["data_cutoff"],
        "scan_completed_at": manifest["completed_at"],
        "lead_count": lead_count,
        "manifest_hash": claimed_hash,
        "batch_hash": claimed_batch_hash,
    }


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
        fields = _extract_fields(s["body"])
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
                "generator_id": fields["generator_id"],
                "generator_version": fields["generator_version"],
                "mechanism_id": fields["mechanism_id"],
                "evidence_grade": fields["evidence_grade"],
                "market_prior_status": fields["market_prior_status"],
                "source_authorization": fields["source_authorization"],
                "scan_run_id": fields["scan_run_id"],
                "scan_completed_at": fields["scan_completed_at"],
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
            if e["generator_id"]:
                flags.append(f"generator={e['generator_id']}")
            if e["evidence_grade"]:
                flags.append(f"grade={e['evidence_grade']}")
            if e["market_prior_status"]:
                flags.append(f"prior={e['market_prior_status']}")
            lines.append(f"## {e['entry_id']} [{e['status']}{' ' + ' '.join(flags) if flags else ''}]")
            lines.append(f"**{e['title']}** — {e['excerpt']}")
            if e["expectation_proxy"]:
                lines.append(f"expectation_proxy: {e['expectation_proxy']}")
            if e["pit_feasibility"]:
                lines.append(f"pit_feasibility: {e['pit_feasibility']}")
            if e["source_authorization"]:
                lines.append(f"source_authorization: {e['source_authorization']}")
            if e["falsifier"]:
                lines.append(f"falsifier: {e['falsifier']}")
            lines.append("")
        return "\n".join(lines)

    subset = list(ranked)
    md = render(subset)
    while len(md.encode("utf-8")) >= DIGEST_BYTE_CAP and subset:
        subset.pop()
        md = render(subset)

    mechanism_scans = [
        e for e in entries
        if e["generator_id"] and e["scan_run_id"] and e["scan_completed_at"]
    ]
    latest_mechanism_scan = read_mechanism_scan_manifest(
        known_entry_ids={entry["entry_id"] for entry in entries}
    )
    if latest_mechanism_scan is None and mechanism_scans:
        latest = max(mechanism_scans, key=lambda e: (e["scan_completed_at"], e["map_order"]))
        latest_mechanism_scan = {
            "status": "map_marker_only",
            "generator_id": latest["generator_id"],
            "generator_version": latest["generator_version"],
            "scan_run_id": latest["scan_run_id"],
            "scan_completed_at": latest["scan_completed_at"],
        }

    payload = {
        "schema_version": 1,
        "generated_at": now,
        # ``generated_at`` is only the digest build clock.  This separate
        # marker proves when a versioned external mechanism scan actually ran,
        # so rerendering an unchanged map cannot masquerade as fresh research.
        "latest_mechanism_scan": latest_mechanism_scan,
        "entry_count_total": len(entries),
        "eligible_count": len(eligible),
        "lane_blocked_total": sum(1 for e in entries if e["status"] == "lane_blocked"),
        "shown": [
            {
                k: e[k]
                for k in (
                    "entry_id",
                    "title",
                    "status",
                    "lane_matches",
                    "has_expectation_proxy",
                    "crowding",
                    "expectation_proxy",
                    "pit_feasibility",
                    "source_authorization",
                    "generator_id",
                    "generator_version",
                    "mechanism_id",
                    "evidence_grade",
                    "market_prior_status",
                    "scan_run_id",
                    "scan_completed_at",
                    "falsifier",
                    "excerpt",
                )
            }
            for e in subset
        ],
    }
    js = json.dumps(payload, ensure_ascii=False, indent=1)
    while len(js.encode("utf-8")) >= DIGEST_BYTE_CAP and payload["shown"]:
        payload["shown"].pop()
        js = json.dumps(payload, ensure_ascii=False, indent=1)

    # The Markdown and JSON files are two representations of one ranked
    # digest, not independently truncated candidate lists.  JSON carries more
    # provenance per row and can therefore hit the shared byte cap first.  If
    # it retains fewer rows, rerender Markdown from that exact ordered subset
    # so human and machine consumers cannot silently evaluate different
    # research inputs.
    retained_ids = [entry["entry_id"] for entry in payload["shown"]]
    subset_ids = [entry["entry_id"] for entry in subset]
    if retained_ids != subset_ids:
        entries_by_id = {entry["entry_id"]: entry for entry in subset}
        subset = [entries_by_id[entry_id] for entry_id in retained_ids]
        md = render(subset)

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
