#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_GUARDRAILS = Path("docs/research_queue_guardrails.json")


def _norm(text: str | None) -> str:
    return (text or "").casefold()


def _hits(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _norm(term) in text]


def load_guardrails(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify(proposal_text: str, guardrails: dict[str, Any]) -> dict[str, Any]:
    text = _norm(proposal_text)
    matches = []
    hard_blocks = []
    redirects = []

    for rule in guardrails.get("guardrail_rules", []):
        matched = _hits(text, [str(term) for term in rule.get("match_terms", [])])
        if not matched:
            continue
        overrides = _hits(text, [str(term) for term in rule.get("evidence_override_terms", [])])
        record = {
            "id": rule.get("id"),
            "severity": rule.get("severity"),
            "matched_terms": matched,
            "override_terms": overrides,
            "blocked_next_work": rule.get("blocked_next_work", []),
            "required_new_evidence": rule.get("required_new_evidence", []),
            "next_allowed_work": rule.get("next_allowed_work", []),
            "source_experiments": rule.get("source_experiments", []),
        }
        matches.append(record)
        if rule.get("mode") == "redirect_to_forward_maturation":
            redirects.append(record)
        elif rule.get("mode") == "block_unless_new_evidence" and not overrides:
            hard_blocks.append(record)

    if hard_blocks:
        status = "blocked_nearby_repeat"
        message = "Proposal matches a frozen or repeatedly failed direction."
    elif redirects:
        status = "redirect_forward_maturation"
        message = "Proposal should be redirected to forward maturation or replacement value."
    elif matches:
        status = "requires_extra_evidence"
        message = "Proposal matches guarded territory and needs explicit new evidence."
    else:
        status = "clear"
        message = "No guardrail match found; continue with AGENTS.md questions and Gate 1-4."

    return {
        "status": status,
        "message": message,
        "matched_rules": matches,
        "hard_blocks": hard_blocks,
        "redirects": redirects,
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [f"status: {result['status']}", result["message"]]
    for rule in result["matched_rules"]:
        lines.append(f"\n- rule: {rule['id']} ({rule['severity']})")
        lines.append("  matched_terms: " + ", ".join(rule["matched_terms"]))
        if rule["override_terms"]:
            lines.append("  override_terms: " + ", ".join(rule["override_terms"]))
        for key in ["blocked_next_work", "required_new_evidence", "next_allowed_work"]:
            if rule[key]:
                lines.append(f"  {key}:")
                lines.extend(f"    - {item}" for item in rule[key])
        if rule["source_experiments"]:
            lines.append("  source_experiments: " + ", ".join(rule["source_experiments"]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guardrails", type=Path, default=DEFAULT_GUARDRAILS)
    parser.add_argument("--hypothesis", default="")
    parser.add_argument("--lane", default="")
    parser.add_argument("--mechanism-family", default="")
    parser.add_argument("--changed-variable", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()

    proposal_text = " ".join([
        args.hypothesis,
        args.lane,
        args.mechanism_family,
        args.changed_variable,
        args.notes,
    ]).strip()
    if not proposal_text:
        parser.error("provide at least --hypothesis or --notes")

    result = classify(proposal_text, load_guardrails(args.guardrails))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    return 2 if result["status"] == "blocked_nearby_repeat" and not args.allow_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
