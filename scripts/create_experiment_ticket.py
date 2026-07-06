"""Create a proposed multi-agent experiment ticket."""

import json
import os
import re
import sys
from pathlib import Path

from experiment_registry import (
    add_common_registry_arg,
    normalize_prediction,
    parse_csv,
    parse_windows,
    print_json,
    reserve_experiment,
)

ALPHA_LANES = {"alpha_search", "alpha_discovery", "universe_scout"}

COMMON_SURFACE_TOKENS = {
    "alpha",
    "audit",
    "candidate",
    "condition",
    "context",
    "daily",
    # "default"/"off"/"paper"/"sleeve" appear in nearly every default-off
    # paper-sleeve ticket; matching a parked surface on them alone falsely
    # blocks unrelated reservations (recurrence of the exp-20260704-018
    # false-mapping family, root-caused 2026-07-05).
    "default",
    "entry",
    "experiment",
    "forward",
    "gate",
    "logger",
    "notional",
    "off",
    "paper",
    "park",
    "parked",
    "ranking",
    "readiness",
    "reopen",
    "response",
    "risk",
    "scalar",
    "search",
    "shared",
    "sizing",
    "sleeve",
    "surface",
    "trade",
}


def _repo_root():
    return Path(__file__).resolve().parents[1]


def _normalize_text(value):
    text = str(value or "").lower().replace("_", " ").replace("-", " ").replace("/", " ")
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(text.split())


def _tokens(value):
    return {
        token
        for token in _normalize_text(value).split()
        if len(token) >= 3 and token not in COMMON_SURFACE_TOKENS
    }


def _surface_aliases(surface_text):
    aliases = {surface_text}
    tokens = surface_text.split()
    token_set = set(tokens)
    if {"sec", "ftd", "finra"}.issubset(token_set):
        aliases.update({"sec ftd finra", "ftd finra"})
    if "form4" in token_set or "form4" in surface_text.replace(" ", ""):
        aliases.add("form4")
    if "form144" in token_set or "form144" in surface_text.replace(" ", ""):
        aliases.add("form144")
    return sorted((alias for alias in aliases if alias), key=len, reverse=True)


def _surface_negated_in_text(surface_text, proposed_text):
    """Return True when text explicitly says it is not targeting a surface."""
    for alias in _surface_aliases(surface_text):
        alias_pattern = re.escape(alias).replace(r"\ ", r"\s+")
        if re.search(rf"\bnot\b(?:\s+\w+){{0,3}}\s+{alias_pattern}\b", proposed_text):
            return True
        if re.search(rf"\bunrelated\s+to\b(?:\s+\w+){{0,3}}\s+{alias_pattern}\b", proposed_text):
            return True
        if re.search(rf"\bother\s+than\b(?:\s+\w+){{0,3}}\s+{alias_pattern}\b", proposed_text):
            return True
    return False


def _is_number(value):
    return type(value) in (int, float)


def _iter_reopen_conditions(value):
    """Yield nested reopen_condition dicts from an experiment log payload."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            condition = item.get("reopen_condition")
            if isinstance(condition, dict):
                yield condition
            for child in item.values():
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(child for child in item if isinstance(child, (dict, list)))


def load_reopen_conditions(repo_root=None):
    """Load machine-counted reopen conditions from closed experiment logs."""
    root = Path(repo_root) if repo_root is not None else _repo_root()
    log_dir = root / "experiments" / "logs"
    conditions = []
    seen = set()
    if not log_dir.exists():
        return conditions
    for path in sorted(log_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        experiment_id = payload.get("experiment_id") if isinstance(payload, dict) else None
        for condition in _iter_reopen_conditions(payload):
            if not isinstance(condition.get("current_counts"), dict):
                continue
            if not isinstance(condition.get("required_to_reopen"), dict):
                continue
            if not condition.get("surface"):
                continue
            key = (
                str(path),
                json.dumps(condition, sort_keys=True, default=str),
            )
            if key in seen:
                continue
            seen.add(key)
            item = dict(condition)
            item["source_log"] = str(path.relative_to(root)).replace("\\", "/")
            item["experiment_id"] = experiment_id or path.stem
            conditions.append(item)
    return conditions


def surface_matches_text(surface, text):
    """Return True when a proposed ticket text appears to target a parked surface."""
    surface_text = _normalize_text(surface)
    proposed_text = _normalize_text(text)
    surface_collapsed = surface_text.replace(" ", "")
    proposed_collapsed = proposed_text.replace(" ", "")

    if _surface_negated_in_text(surface_text, proposed_text):
        return False

    if "form4" in surface_collapsed:
        return "form4" in proposed_collapsed and any(
            term in proposed_text for term in ("sale", "10b5", "officer", "overhang")
        )
    if "form144" in surface_collapsed:
        return "form144" in proposed_collapsed

    surface_tokens = _tokens(surface)
    proposed_tokens = _tokens(text)
    if not surface_tokens:
        return False
    overlap = surface_tokens & proposed_tokens
    required = 1 if len(surface_tokens) <= 2 else 2
    return len(overlap) >= required


def _find_current_count(current_counts, required_key):
    base = required_key
    if base.endswith("_min") or base.endswith("_max"):
        base = base.rsplit("_", 1)[0]
    if base in current_counts and (_is_number(current_counts[base]) or current_counts[base] is None):
        return base, current_counts[base]

    base_tokens = _tokens(base)
    best_key = None
    best_value = None
    best_score = 0
    for key, value in current_counts.items():
        if not (_is_number(value) or value is None):
            continue
        key_tokens = _tokens(key)
        score = len(base_tokens & key_tokens)
        if score > best_score:
            best_key = key
            best_value = value
            best_score = score
    required_score = 1 if len(base_tokens) <= 2 else 2
    if best_key is not None and best_score >= required_score:
        return best_key, best_value
    return None, None


def reopen_condition_numeric_checks(condition):
    """Compare a reopen_condition's current_counts to numeric thresholds."""
    current_counts = condition.get("current_counts") or {}
    required = condition.get("required_to_reopen") or {}
    checks = []
    for key, threshold in sorted(required.items()):
        if not _is_number(threshold):
            continue
        if key.endswith("_min"):
            current_key, current_value = _find_current_count(current_counts, key)
            passed = _is_number(current_value) and current_value >= threshold
            checks.append(
                {
                    "required_key": key,
                    "current_key": current_key,
                    "current_value": current_value,
                    "operator": ">=",
                    "threshold": threshold,
                    "passed": bool(passed),
                }
            )
        elif key.endswith("_max"):
            current_key, current_value = _find_current_count(current_counts, key)
            passed = _is_number(current_value) and current_value <= threshold
            checks.append(
                {
                    "required_key": key,
                    "current_key": current_key,
                    "current_value": current_value,
                    "operator": "<=",
                    "threshold": threshold,
                    "passed": bool(passed),
                }
            )
    return checks


def evaluate_reopen_condition_guard(args, repo_root=None):
    """Evaluate the parked-surface reopen rule for a proposed reservation."""
    alpha_lane = getattr(args, "lane", None) in ALPHA_LANES
    result = {
        "applicable": alpha_lane,
        "blocked": False,
        "override_accepted": False,
        "matched_conditions": [],
        "rule": (
            "If a parked surface has a quantitative reopen_condition, alpha-lane "
            "reservations that target that surface are blocked until the numeric "
            "reopen checks pass, unless the ticket names a genuinely new data "
            "source or a new gate shape."
        ),
    }
    if not alpha_lane:
        return result

    ticket_text = " ".join(
        str(getattr(args, name, "") or "")
        for name in (
            "hypothesis",
            "single_causal_variable",
            "changed_variable",
            "trial_family",
            "trial_variant_id",
            "mechanism_family",
            "file_slug",
            "new_evidence_axis",
        )
    )
    axis_class = classify_saturated_source_axis(getattr(args, "new_evidence_axis", ""))
    result["new_evidence_axis"] = axis_class

    for condition in load_reopen_conditions(repo_root=repo_root):
        if not surface_matches_text(condition.get("surface"), ticket_text):
            continue
        checks = reopen_condition_numeric_checks(condition)
        satisfied = bool(checks) and all(check["passed"] for check in checks)
        result["matched_conditions"].append(
            {
                "experiment_id": condition.get("experiment_id"),
                "source_log": condition.get("source_log"),
                "surface": condition.get("surface"),
                "status": condition.get("status"),
                "blocking_reason": condition.get("blocking_reason"),
                "checks_satisfied": satisfied,
                "numeric_checks": checks,
                "reopen_rule": condition.get("reopen_rule"),
            }
        )

    blocked_matches = [
        item for item in result["matched_conditions"] if not item["checks_satisfied"]
    ]
    if not blocked_matches:
        return result

    categories = set(axis_class.get("categories") or [])
    if categories & {"new_data_source", "new_gate_shape"}:
        result["override_accepted"] = True
        result["override_reason"] = (
            "Declared evidence axis names a new data source or new gate shape."
        )
        return result

    result["blocked"] = True
    result["blocking_matches"] = blocked_matches
    return result


def classify_saturated_source_axis(axis):
    """Classify whether a saturated-source override names a legal evidence axis.

    AGENTS.md is stricter than the ordinary novelty override: once a
    ``(gate_shape, data_source)`` cell is saturated, an untried same-source field
    no longer counts as new evidence. The override must name a new data source, a
    new gate shape, or materially more closed/settled forward rows.
    """
    raw = str(axis or "").strip()
    text = raw.lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    categories = []
    if any(
        phrase in text
        for phrase in (
            "new data source",
            "different data source",
            "genuinely new source",
            "new source",
            "new external source",
        )
    ):
        categories.append("new_data_source")
    if any(
        phrase in text
        for phrase in (
            "new gate shape",
            "different gate shape",
            "non scan gate shape",
            "non scan gateshape",
            "new gateshape",
        )
    ):
        categories.append("new_gate_shape")
    if any(
        phrase in text
        for phrase in (
            "materially more closed",
            "substantially more closed",
            "closed forward row",
            "closed forward rows",
            "settled forward row",
            "settled forward rows",
            "mature forward row",
            "mature forward rows",
            "matured forward row",
            "matured forward rows",
            "new forward row",
            "new forward rows",
            "forward replacement row",
            "forward replacement rows",
        )
    ):
        categories.append("materially_more_forward_rows")
    field_only_markers = (
        "field" in text
        or "tag" in text
        or "xbrl" in text
        or "concept" in text
        or "label" in text
    )
    return {
        "axis": raw or None,
        "valid": bool(categories),
        "categories": categories,
        "invalid_same_source_field_only": bool(field_only_markers and not categories),
        "rule": (
            "For saturated (gate_shape, data_source) cells, legal override axes "
            "are limited to a new data source, a new gate shape, or materially "
            "more closed/settled forward rows. Same-source new fields/tags do "
            "not qualify."
        ),
    }


_EXPERIMENT_LOG_NAME = re.compile(r"^exp-(\d{8})-\d+\.json$")


def _iter_closed_logs(repo_root=None):
    """Yield (id_date_str, payload) for closed experiment logs, oldest first.

    Only real dated experiment ids participate (``exp-YYYYMMDD-NNN.json``);
    placeholders like ``exp-next-001.json`` and lock residue are skipped.
    Fails safe: unreadable/unparseable shards are silently ignored.
    """
    root = Path(repo_root) if repo_root is not None else _repo_root()
    log_dir = root / "experiments" / "logs"
    if not log_dir.exists():
        return
    for path in sorted(log_dir.glob("exp-*.json")):
        match = _EXPERIMENT_LOG_NAME.match(path.name)
        if not match:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            yield match.group(1), payload


def _log_is_observed_only_probe(payload):
    status = str(payload.get("status") or "").lower()
    decision = str(payload.get("decision") or "").lower()
    return status.startswith("observed_only") or decision.startswith("observed_only")


def _log_data_source(payload):
    try:
        import experiment_fingerprint as efp

        return efp.infer_fingerprint(
            payload.get("hypothesis") or "",
            payload.get("change_type") or "",
            payload.get("component") or "",
        ).get("data_source")
    except Exception:
        return None


def evaluate_observed_only_streak_guard(args, proposal_source, repo_root=None):
    """Machine form of the AGENTS.md §2.4 forward-attribution row.

    After N consecutive observed-only "no edge / not allocation_ready" closes on
    the same data_source population, another observed-only attribution probe on
    that population is not new evidence: the binding constraint is the number of
    settled rows, not another join/condition field. Block the reservation unless
    the ticket declares a legal axis (materially more closed forward rows, a new
    data source, or a new gate shape) together with --observed-only-override.
    """
    try:
        max_probes = int(os.environ.get("GINGER_OBSERVED_ONLY_MAX_PROBES", "3"))
    except (TypeError, ValueError):
        max_probes = 3
    result = {
        "applicable": False,
        "blocked": False,
        "override_accepted": False,
        "source": proposal_source,
        "streak": 0,
        "max_probes": max_probes,
        "streak_experiments": [],
        "rule": (
            "AGENTS.md §2.4 forward-row attribution: after "
            f"{max_probes} consecutive observed-only closes on one data_source "
            "population, a further observed-only probe needs materially more "
            "settled rows, a new data source, or a new gate shape."
        ),
    }
    try:
        proposal_text = " ".join(
            str(getattr(args, name, "") or "")
            for name in ("change_type", "hypothesis", "trial_family")
        ).lower()
        proposal_is_observed_probe = (
            "observed" in str(getattr(args, "change_type", "") or "").lower()
            or "observed only" in proposal_text.replace("-", " ").replace("_", " ")
        )
        if not proposal_is_observed_probe:
            return result
        if not proposal_source or proposal_source == "other":
            return result
        result["applicable"] = True

        streak = []
        for _, payload in _iter_closed_logs(repo_root):
            if _log_data_source(payload) != proposal_source:
                continue
            if _log_is_observed_only_probe(payload):
                streak.append(payload.get("experiment_id"))
            else:
                streak = []
        result["streak"] = len(streak)
        result["streak_experiments"] = streak[-max_probes:]
        if len(streak) < max_probes:
            return result

        axis = classify_saturated_source_axis(getattr(args, "new_evidence_axis", ""))
        if getattr(args, "observed_only_override", False) and axis["valid"]:
            result["override_accepted"] = True
            result["override_axis_categories"] = axis["categories"]
            return result
        result["blocked"] = True
    except Exception:
        return result
    return result


_ROUTINE_MATERIALIZATION_VERBS = (
    "enrich",
    "materializ",
    "refresh",
    "backfill",
    "append",
)
_ROUTINE_LEDGER_MARKERS = (
    "forward",
    "observer",
    "ledger",
    "settle",
    "closed row",
    "closed rows",
    "outcome",
    "snapshot",
    "replacement",
)
_FAULT_RECOVERY_MARKERS = (
    "orphan",
    "corrupt",
    "contaminat",
    "upstream format",
    "format change",
    "schema change",
    "recover",
    "crash",
    "lock residue",
    "publish anomaly",
)
_PIPELINE_WIRING_MARKERS = (
    "run py",
    "pipeline",
    "wire",
    "wiring",
    "scheduled task",
    "cron",
    "automat",
    "daily job",
)


def classify_routine_materialization(text):
    """Classify whether text describes routine forward-ledger delta materialization.

    Routine = a materialization verb (enrich/materialize/refresh/backfill/append)
    applied to a forward-ledger surface (forward rows, observer outcomes, settled
    replacement values, snapshots). Fault recovery and one-time pipeline wiring
    are the two legal shapes and are classified separately.
    """
    normalized = _normalize_text(text)
    return {
        "routine": (
            any(verb in normalized for verb in _ROUTINE_MATERIALIZATION_VERBS)
            and any(marker in normalized for marker in _ROUTINE_LEDGER_MARKERS)
        ),
        "fault_recovery": any(m in normalized for m in _FAULT_RECOVERY_MARKERS),
        "pipeline_wiring": any(m in normalized for m in _PIPELINE_WIRING_MARKERS),
    }


def _log_is_routine_materialization(payload):
    status = str(payload.get("status") or "").lower()
    if status not in {"accepted_measurement_repair", "accepted"}:
        return False
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("hypothesis", "change_type", "change_summary", "decision")
    )
    verdict = classify_routine_materialization(text)
    return verdict["routine"] and not verdict["fault_recovery"] and not verdict["pipeline_wiring"]


def evaluate_routine_materialization_guard(args, repo_root=None, today=None):
    """Machine form of the AGENTS.md §2.4 routine-delta-materialization row.

    Manually re-running the same append/refresh/enrichment for accepted
    observer / default-off sleeve forward ledgers is cron work wearing an
    experiment coat: rows are real but there is no attributable hypothesis.
    After the budget is spent (>= max_ids on one surface, or >= max_ids
    same-shape closes across surfaces within the recent window), the only legal
    next reservation is the one-time pipeline wiring (run.py / scheduled task)
    or a genuine fault recovery — both pass this gate by classification.
    """
    try:
        max_ids = int(os.environ.get("GINGER_ROUTINE_MATERIALIZATION_MAX_IDS", "3"))
    except (TypeError, ValueError):
        max_ids = 3
    try:
        window_days = int(
            os.environ.get("GINGER_ROUTINE_MATERIALIZATION_WINDOW_DAYS", "7")
        )
    except (TypeError, ValueError):
        window_days = 7
    result = {
        "applicable": False,
        "blocked": False,
        "override_accepted": False,
        "max_ids": max_ids,
        "window_days": window_days,
        "per_source_count": 0,
        "recent_cross_surface_count": 0,
        "recent_experiments": [],
        "rule": (
            "AGENTS.md §2.4 routine delta materialization: after "
            f"{max_ids} routine forward-ledger materialization IDs (one surface, "
            f"or same-shape across surfaces within {window_days} days), wire the "
            "materialization into run.py / the settlement pipeline once instead "
            "of reserving further manual IDs. Fault recovery is exempt."
        ),
    }
    try:
        # Only measurement-shaped tickets can BE routine materialization. An
        # alpha-lane full-stack ticket whose hypothesis merely mentions
        # "backfill" or "forward returns" is testing a hypothesis, not
        # re-running a ledger append; without this shape check the gate
        # false-blocks alpha reservations (found on first live use 2026-07-05).
        lane = str(getattr(args, "lane", "") or "").lower()
        change_type = str(getattr(args, "change_type", "") or "").lower()
        measurement_shaped = lane not in ALPHA_LANES or any(
            marker in change_type
            for marker in (
                "repair",
                "materializ",
                "refresh",
                "enrich",
                "backfill",
                "observation_delta",
                "wiring",
            )
        )
        if not measurement_shaped:
            return result
        proposal_text = " ".join(
            str(getattr(args, name, "") or "")
            for name in ("hypothesis", "change_type", "single_causal_variable", "trial_family")
        )
        verdict = classify_routine_materialization(proposal_text)
        result["proposal_classification"] = verdict
        if not verdict["routine"] or verdict["fault_recovery"] or verdict["pipeline_wiring"]:
            return result
        result["applicable"] = True

        import datetime as _dt

        current = today or _dt.date.today()
        cutoff = current - _dt.timedelta(days=window_days)
        try:
            import experiment_fingerprint as efp

            proposal_source = efp.infer_fingerprint(proposal_text).get("data_source")
        except Exception:
            proposal_source = None

        per_source = 0
        recent = []
        for id_date_str, payload in _iter_closed_logs(repo_root):
            if not _log_is_routine_materialization(payload):
                continue
            if proposal_source and proposal_source != "other":
                if _log_data_source(payload) == proposal_source:
                    per_source += 1
            try:
                id_date = _dt.datetime.strptime(id_date_str, "%Y%m%d").date()
            except ValueError:
                continue
            if id_date >= cutoff:
                recent.append(payload.get("experiment_id"))
        result["per_source_count"] = per_source
        result["recent_cross_surface_count"] = len(recent)
        result["recent_experiments"] = recent[-8:]
        if per_source < max_ids and len(recent) < max_ids:
            return result

        if getattr(args, "routine_materialization_override", False):
            result["override_accepted"] = True
            return result
        result["blocked"] = True
    except Exception:
        return result
    return result


def _novelty_check(args):
    """Advisory near-neighbor check at reservation time. Fails safe.

    Warn-only by default: prints the fingerprint and nearest frozen/explored
    families to stderr (stdout stays clean JSON). Becomes a soft gate when
    --enforce-novelty or env GINGER_NOVELTY_GATE is set: an alpha-lane
    near-neighbor is blocked unless --novelty-override with --new-evidence-axis
    is supplied. Any import/lookup failure silently skips the check so it can
    never break a reservation.
    """
    try:
        import check_experiment_novelty as cen
        import experiment_fingerprint as efp
    except Exception:
        return None
    try:
        fingerprint = efp.infer_fingerprint(
            args.hypothesis or "",
            args.single_causal_variable or "",
            args.trial_family or "",
            args.mechanism_family or "",
            args.file_slug or "",
        )
        result = cen.check(fingerprint)
    except Exception:
        return None

    # Blocking is the default for alpha lanes. Precedence: explicit per-call
    # flags win, then the env switch, else block by default.
    gate_env = os.environ.get("GINGER_NOVELTY_GATE", "").strip().lower()
    if args.no_enforce_novelty:
        enforce = False
    elif args.enforce_novelty:
        enforce = True
    elif gate_env in {"off", "0", "warn", "false", "no"}:
        enforce = False
    elif gate_env in {"1", "block", "true", "yes"}:
        enforce = True
    else:
        enforce = True
    alpha_lane = args.lane in ALPHA_LANES
    nearest = result.get("nearest") or []

    print(
        "[novelty] fingerprint:"
        f" source={fingerprint['data_source']} gate={fingerprint['gate_shape']}"
        f" tags={','.join(fingerprint['field_tags'][:10])}",
        file=sys.stderr,
    )
    if result.get("warn"):
        print(
            f"[novelty] WARN near-neighbor of a frozen/explored/prior-failed family"
            f" (threshold {result['warn_threshold']}):",
            file=sys.stderr,
        )
        for n in nearest[:3]:
            print(
                f"[novelty]   {n['score']:.3f} [{n['status']}] {n['family_key']}"
                f" (trials={n['trials']}, accept={n['accept_rate']})",
                file=sys.stderr,
            )
    else:
        print("[novelty] ok: no strong near-neighbor.", file=sys.stderr)

    # Source-saturation penalty: independent of the near-neighbor gate. Each new
    # field is a distinct fingerprint so the near-neighbor gate waves it through,
    # but re-scanning a data source that history shows is dry (low accept rate
    # over enough trials) is pure token churn. Thresholds tunable via env.
    try:
        min_tr = int(os.environ.get("GINGER_SATURATION_MIN_TRIALS", "12"))
    except (TypeError, ValueError):
        min_tr = 12
    try:
        max_ar = float(os.environ.get("GINGER_SATURATION_MAX_ACCEPT", "0.05"))
    except (TypeError, ValueError):
        max_ar = 0.05
    try:
        # gate_shape for the saturation decision must come from the STRUCTURED
        # identifiers (trial_family / changed_variable / decision-variable /
        # file_slug), not the free-text hypothesis. Prose like "ranking" matches
        # the allocator gate_shape first (first-match-wins) and would silently
        # mislabel a candidate-pool scan as allocator_source, skipping the
        # saturation gate. The structured slugs reliably carry the
        # candidate_pool marker, so re-infer gate_shape from them alone.
        struct_shape = efp.infer_fingerprint(
            args.trial_family or "",
            args.changed_variable or "",
            args.single_causal_variable or "",
            args.file_slug or "",
        ).get("gate_shape")
        sat_fp = dict(fingerprint)
        if struct_shape and struct_shape != "other":
            sat_fp["gate_shape"] = struct_shape
        saturation = cen.source_saturation(
            sat_fp, min_trials=min_tr, max_accept_rate=max_ar
        )
    except Exception:
        saturation = {"applicable": False, "saturated": False}

    out = {
        "fingerprint": fingerprint,
        "warn": bool(result.get("warn")),
        "warn_threshold": result.get("warn_threshold"),
        "nearest": nearest[:5],
        "blocking_matches": result.get("blocking_matches") or [],
        "new_evidence_axis": (args.new_evidence_axis or "").strip() or None,
        "override": bool(args.novelty_override),
        "enforced": enforce,
        "source_saturation": saturation,
        "saturated_source_override": bool(getattr(args, "saturated_source_override", False)),
        "saturated_source_axis": classify_saturated_source_axis(args.new_evidence_axis),
    }

    reopen_guard = evaluate_reopen_condition_guard(args)
    out["reopen_condition_guard"] = reopen_guard
    if reopen_guard.get("matched_conditions"):
        print(
            "[reopen] matched parked surface(s): "
            + ", ".join(
                str(item.get("surface"))
                for item in reopen_guard["matched_conditions"][:3]
            ),
            file=sys.stderr,
        )
    if reopen_guard.get("blocked") and enforce and alpha_lane:
        first = (reopen_guard.get("blocking_matches") or [{}])[0]
        failed_checks = [
            f"{check.get('current_key') or check.get('required_key')}="
            f"{check.get('current_value')} {check.get('operator')} "
            f"{check.get('threshold')}"
            for check in first.get("numeric_checks", [])
            if not check.get("passed")
        ]
        raise SystemExit(
            "reopen-condition gate blocked this reservation: the proposed "
            f"alpha-lane ticket targets parked surface '{first.get('surface')}' "
            f"from {first.get('experiment_id')}, but its quantitative reopen "
            "checks are not satisfied"
            + (": " + "; ".join(failed_checks) + "." if failed_checks else ".")
            + " Reopen only after the counts advance in the recorded "
            "reopen_condition, or declare a genuinely new data source or a new "
            "gate shape in --new-evidence-axis. Do not spend a new experiment ID "
            "on a readiness audit or response-curve retune for the same parked "
            "surface."
        )
    if reopen_guard.get("override_accepted"):
        print(
            "[reopen] override accepted; "
            f"new_evidence_axis={out['new_evidence_axis']}",
            file=sys.stderr,
        )

    observed_guard = evaluate_observed_only_streak_guard(
        args, fingerprint.get("data_source")
    )
    out["observed_only_streak_guard"] = observed_guard
    if observed_guard.get("streak"):
        print(
            f"[observed-only] {observed_guard['streak']} consecutive observed-only "
            f"close(s) on data_source '{observed_guard['source']}' "
            f"(block at >= {observed_guard['max_probes']}): "
            + ", ".join(str(e) for e in observed_guard["streak_experiments"]),
            file=sys.stderr,
        )
    if observed_guard.get("blocked") and enforce and alpha_lane:
        raise SystemExit(
            "observed-only saturation gate blocked this reservation: data_source "
            f"'{observed_guard['source']}' already has "
            f"{observed_guard['streak']} consecutive observed-only closes "
            f"({', '.join(str(e) for e in observed_guard['streak_experiments'])}). "
            "Another join/condition-field slice on the same row population is not "
            "new evidence — the binding constraint is settled-row count, not "
            "field dimension. Legal next steps: materially more closed/settled "
            "forward rows, a genuinely new data source, or a new gate shape. To "
            "proceed, re-run with --observed-only-override and "
            '--new-evidence-axis "<materially more closed forward rows | new '
            'data source | new gate shape>".'
        )
    if observed_guard.get("override_accepted"):
        print(
            "[observed-only] override accepted; "
            f"axis={out['new_evidence_axis']}",
            file=sys.stderr,
        )

    routine_guard = evaluate_routine_materialization_guard(args)
    out["routine_materialization_guard"] = routine_guard
    if routine_guard.get("applicable"):
        print(
            "[routine-materialization] proposal classifies as routine "
            "forward-ledger delta materialization; prior routine IDs: "
            f"same-source={routine_guard['per_source_count']}, "
            f"cross-surface last {routine_guard['window_days']}d="
            f"{routine_guard['recent_cross_surface_count']} "
            f"(block at >= {routine_guard['max_ids']}).",
            file=sys.stderr,
        )
    if routine_guard.get("blocked") and enforce:
        raise SystemExit(
            "routine-materialization gate blocked this reservation: routine "
            "forward-ledger delta materialization (append/refresh/enrichment) "
            "has already consumed its ID budget ("
            f"same-source={routine_guard['per_source_count']}, cross-surface "
            f"last {routine_guard['window_days']}d="
            f"{routine_guard['recent_cross_surface_count']}, threshold "
            f"{routine_guard['max_ids']}; recent: "
            f"{', '.join(str(e) for e in routine_guard['recent_experiments'])}). "
            "This is cron work wearing an experiment coat. Legal next step: one "
            "measurement-repair ID that wires the materialization into run.py / "
            "the settlement pipeline (mention the wiring in the hypothesis), "
            "after which routine rows land automatically without IDs. Genuine "
            "fault recovery (orphan temp, upstream format change, contaminated "
            "snapshot) is exempt when named. To proceed anyway, re-run with "
            "--routine-materialization-override."
        )
    if routine_guard.get("override_accepted"):
        print("[routine-materialization] override accepted.", file=sys.stderr)

    if result.get("warn") and enforce and alpha_lane:
        if not (args.novelty_override and (args.new_evidence_axis or "").strip()):
            raise SystemExit(
                "novelty gate blocked this reservation: it is a near-neighbor of a "
                "frozen/explored or prior-failed (tried >=1x, never accepted) "
                "family. Re-run with --novelty-override and "
                '--new-evidence-axis "<what is genuinely new>" if justified, or '
                "pick a different decision hypothesis. See docs/frozen_families.jsonl."
            )
        print(
            f"[novelty] override accepted; new_evidence_axis={out['new_evidence_axis']}",
            file=sys.stderr,
        )

    if saturation.get("saturated"):
        print(
            f"[saturation] data_source '{saturation['source']}' is dry for "
            f"{saturation['gate_shape']} scans: "
            f"{saturation['accepts']}/{saturation['trials']} accepted "
            f"({100 * saturation['accept_rate']:.1f}%, threshold "
            f"{100 * saturation['max_accept_rate']:.1f}% over >= "
            f"{saturation['min_trials']} trials).",
            file=sys.stderr,
        )
    if saturation.get("saturated") and enforce and alpha_lane:
        if not (
            getattr(args, "saturated_source_override", False)
            and (args.new_evidence_axis or "").strip()
        ):
            raise SystemExit(
                "saturation gate blocked this reservation: candidate-pool scans on "
                f"data_source '{saturation['source']}' are historically dry "
                f"({saturation['accepts']}/{saturation['trials']} accepted, "
                f"{100 * saturation['accept_rate']:.1f}% over "
                f">= {saturation['min_trials']} trials). Stop swapping fields on a "
                "proven-dry source. Prefer a genuinely new data source, a new "
                "gate_shape, or materially more closed/settled forward rows. "
                "To proceed anyway, re-run with --saturated-source-override "
                'and --new-evidence-axis "<new data source | new gate shape | '
                'materially more closed forward rows>". Same-source new fields '
                "or tags do not qualify."
            )
        axis_class = out["saturated_source_axis"]
        if not axis_class["valid"]:
            raise SystemExit(
                "saturation gate blocked this reservation: the declared "
                "--new-evidence-axis does not satisfy the saturated-source hard "
                "rule. Same-source untried fields/tags/XBRL labels are not a "
                "legal override after a dry (gate_shape, data_source) cell is "
                "saturated. Name a genuinely new data source, a new gate shape, "
                "or materially more closed/settled forward rows."
            )
        print(
            f"[saturation] override accepted on dry source '{saturation['source']}'"
            f" ({100 * saturation['accept_rate']:.1f}%); "
            f"axis={out['new_evidence_axis']} "
            f"categories={','.join(axis_class['categories'])}",
            file=sys.stderr,
        )
    return out


def _attach_novelty(ticket, novelty):
    """Best-effort: record the novelty result on the created ticket for audit."""
    if not isinstance(ticket, dict) or not novelty:
        return
    path = ticket.get("ticket_file")
    if not path:
        return
    try:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        data["novelty"] = novelty
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        ticket["novelty"] = novelty
    except Exception:
        pass


def main(description=__doc__):
    import argparse

    parser = argparse.ArgumentParser(description=description)
    add_common_registry_arg(parser)
    parser.add_argument(
        "--experiment-id",
        help=(
            "Optional explicit ID to reserve. If omitted, the next collision-safe "
            "ID is allocated from all known identity sources."
        ),
    )
    parser.add_argument("--lane", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--change-type", required=True)
    parser.add_argument(
        "--single-causal-variable",
        "--decision-variable",
        dest="single_causal_variable",
        required=True,
        help=(
            "Single attributable decision hypothesis or fixed policy bundle "
            "under test. The old --single-causal-variable name is kept for "
            "compatibility; --decision-variable is preferred."
        ),
    )
    parser.add_argument(
        "--causal-components",
        default="",
        help=(
            "Comma-separated fixed components inside a predeclared policy "
            "bundle. Components are not individually accepted unless later "
            "ablated."
        ),
    )
    parser.add_argument("--mechanism-family")
    parser.add_argument("--trial-family")
    parser.add_argument("--trial-variant-id")
    parser.add_argument("--changed-variable")
    parser.add_argument("--prior-trial-count", type=int, default=0)
    parser.add_argument("--nearby-prior-experiments", default="")
    parser.add_argument(
        "--multiple-testing-risk-bucket",
        choices=["minimal", "low", "moderate", "high"],
        default="minimal",
    )
    parser.add_argument("--new-evidence-type", default="not_declared")
    parser.add_argument("--baseline-result-file")
    parser.add_argument("--allowed-write-scope", default="")
    parser.add_argument(
        "--file-slug",
        help=(
            "Optional short slug for auto-generated runner/artifact names. "
            "Defaults to a slug from --single-causal-variable."
        ),
    )
    parser.add_argument(
        "--exclusive-scope-ok",
        action="store_true",
        help="Allow broad directory scopes such as data/ or quant/.",
    )
    parser.add_argument("--must-not-touch", default="")
    parser.add_argument("--locked-variables", default="")
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        help="Evaluation window as START:END. May be repeated.",
    )
    parser.add_argument("--acceptance-rule")
    parser.add_argument("--owner")
    parser.add_argument(
        "--success-probability",
        type=float,
        help="Pre-run probability that Gate 4 or the ticket acceptance rule will pass, from 0 to 1.",
    )
    parser.add_argument(
        "--expected-ev-delta",
        type=float,
        help="Pre-run expected aggregate expected_value_score delta.",
    )
    parser.add_argument(
        "--expected-pnl-delta",
        type=float,
        help="Pre-run expected aggregate PnL delta in dollars.",
    )
    parser.add_argument(
        "--main-failure-modes",
        default="",
        help="Comma-separated pre-run failure modes to audit after the result.",
    )
    parser.add_argument(
        "--confidence-reason",
        help="Short reason for the pre-run confidence estimate.",
    )
    parser.add_argument(
        "--new-evidence-axis",
        default="",
        help=(
            "What is genuinely new versus prior/frozen families (new data source, "
            "a field no prior family used, a new gate shape, or forward rows). "
            "Required to override a near-neighbor warning under --enforce-novelty. "
            "For saturated-source overrides, same-source new fields/tags do not "
            "qualify; name a new data source, new gate shape, or materially more "
            "closed/settled forward rows."
        ),
    )
    parser.add_argument(
        "--novelty-override",
        action="store_true",
        help="Proceed despite a near-neighbor warning (records the override).",
    )
    parser.add_argument(
        "--saturated-source-override",
        action="store_true",
        help=(
            "Proceed despite a source-saturation block (re-scanning a data source "
            "whose candidate-pool history is dry). Distinct from --novelty-override "
            "on purpose: also requires --new-evidence-axis naming a genuinely new "
            "data source, a new gate shape, or materially more closed/settled "
            "forward rows. Same-source new fields/tags are blocked."
        ),
    )
    parser.add_argument(
        "--observed-only-override",
        action="store_true",
        help=(
            "Proceed despite the observed-only saturation block (>= N consecutive "
            "observed-only closes on the same data_source population). Requires "
            "--new-evidence-axis naming materially more closed/settled forward "
            "rows, a new data source, or a new gate shape; another join/condition "
            "field on the same rows does not qualify."
        ),
    )
    parser.add_argument(
        "--routine-materialization-override",
        action="store_true",
        help=(
            "Proceed despite the routine-materialization block (forward-ledger "
            "delta materialization past its ID budget). Prefer instead a ticket "
            "that wires the materialization into run.py / the settlement "
            "pipeline, or that names a genuine fault recovery — both pass the "
            "gate without an override."
        ),
    )
    parser.add_argument(
        "--enforce-novelty",
        action="store_true",
        help=(
            "Force the blocking novelty gate for this reservation (redundant: "
            "blocking is now the default for alpha lanes)."
        ),
    )
    parser.add_argument(
        "--no-enforce-novelty",
        action="store_true",
        help=(
            "Force warn-only for this reservation, overriding the block-by-"
            "default. Also: env GINGER_NOVELTY_GATE in {off,0,warn} disables "
            "blocking globally; {1,block,true} forces it on."
        ),
    )
    args = parser.parse_args()

    novelty = _novelty_check(args)

    prediction = normalize_prediction(
        success_probability=args.success_probability,
        expected_ev_delta=args.expected_ev_delta,
        expected_pnl_delta=args.expected_pnl_delta,
        main_failure_modes=parse_csv(args.main_failure_modes),
        confidence_reason=args.confidence_reason,
    )

    # registry-decontention step 1: reserve via the lock-free O_EXCL ticket path
    # (the heavy id-collision scan no longer runs under the global registry lock).
    ticket = reserve_experiment(
        args.registry,
        experiment_id=args.experiment_id,
        lane=args.lane,
        hypothesis=args.hypothesis,
        change_type=args.change_type,
        single_causal_variable=args.single_causal_variable,
        causal_components=parse_csv(args.causal_components),
        mechanism_family=args.mechanism_family,
        trial_family=args.trial_family,
        trial_variant_id=args.trial_variant_id,
        changed_variable=args.changed_variable,
        prior_trial_count=args.prior_trial_count,
        nearby_prior_experiments=parse_csv(args.nearby_prior_experiments),
        multiple_testing_risk_bucket=args.multiple_testing_risk_bucket,
        new_evidence_type=args.new_evidence_type,
        baseline_result_file=args.baseline_result_file,
        allowed_write_scope=parse_csv(args.allowed_write_scope),
        must_not_touch=parse_csv(args.must_not_touch),
        locked_variables=parse_csv(args.locked_variables),
        evaluation_windows=parse_windows(args.window),
        acceptance_rule=args.acceptance_rule,
        owner=args.owner,
        file_slug=args.file_slug,
        exclusive_scope_ok=args.exclusive_scope_ok,
        prediction=prediction,
        timeout_seconds=args.lock_timeout_seconds,
    )
    _attach_novelty(ticket, novelty)
    print_json(ticket)


if __name__ == "__main__":
    main()
