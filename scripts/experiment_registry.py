"""Small registry helpers for coordinating multi-agent experiments."""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_paths import backtest_result_glob  # noqa: E402

DEFAULT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
DEFAULT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
DEFAULT_EXPERIMENTS_DIR = REPO_ROOT / "experiments"
DEFAULT_TICKETS_DIR = DEFAULT_EXPERIMENTS_DIR / "tickets"
DEFAULT_EXPERIMENT_LOGS_DIR = DEFAULT_EXPERIMENTS_DIR / "logs"
DEFAULT_CARDS_DIR = DEFAULT_EXPERIMENTS_DIR / "cards"
DEFAULT_MANIFESTS_DIR = DEFAULT_EXPERIMENTS_DIR / "manifests"
DEFAULT_LOCK_TIMEOUT_SECONDS = 30
STALE_LOCK_SECONDS = 300
EXPERIMENT_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])exp[-_](\d{8})[-_](\d{3,})(?!\d)",
    re.IGNORECASE,
)
ACTIVE_STATUSES = {"claimed", "running"}
FINAL_STATUSES = {"accepted", "rejected", "observed_only"}
SHARED_COORDINATION_SCOPES = {
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
}
DISALLOWED_BROAD_SCOPES = {
    "data",
    "docs",
    "quant",
    "scripts",
}
VALID_LANES = {
    "alpha_search",
    "alpha_discovery",
    "loss_attribution",
    "universe_scout",
    "measurement_repair",
}
PREDICTION_REQUIRED_LANES = {
    "alpha_search",
    "alpha_discovery",
    "universe_scout",
}
PREDICTION_ENFORCEMENT_STARTED_AT = "2026-05-29T21:33:00+00:00"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_experiment_uid():
    return f"expuid-{uuid.uuid4().hex[:16]}"


def normalize_experiment_id(value):
    if value is None:
        return None
    match = EXPERIMENT_ID_RE.search(str(value))
    if not match:
        return None
    date, sequence = match.groups()
    return f"exp-{date}-{int(sequence):03d}"


def _repo_relative(path):
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix()


def load_registry(path=DEFAULT_REGISTRY):
    path = Path(path)
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "experiments": []}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", None)
    data.setdefault("experiments", [])
    return data


def _atomic_write_text(text, path):
    """Write text via same-directory temp file + atomic os.replace.

    Closes the corruption window where an unlocked reader sees a truncated or
    stale-tailed file, and where a shorter rewrite leaves an older file's
    trailing bytes (bug audit #9).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as f:
            tmp = f.name
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def save_registry(registry, path=DEFAULT_REGISTRY):
    path = Path(path)
    registry["updated_at"] = utc_now_iso()
    persisted = {k: v for k, v in registry.items() if not k.startswith("_")}
    _atomic_write_text(
        json.dumps(persisted, indent=2, ensure_ascii=False) + "\n", path)


def ticket_path(experiment_id, tickets_dir=DEFAULT_TICKETS_DIR):
    return Path(tickets_dir) / f"{experiment_id}.json"


def experiment_log_path(experiment_id, logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    return Path(logs_dir) / f"{experiment_id}.json"


def experiment_card_path(experiment_id, cards_dir=DEFAULT_CARDS_DIR):
    return Path(cards_dir) / f"{experiment_id}.md"


def revision_manifest_path(experiment_id, manifests_dir=DEFAULT_MANIFESTS_DIR):
    return Path(manifests_dir) / f"{experiment_id}.json"


def save_ticket(ticket, tickets_dir=DEFAULT_TICKETS_DIR, *, overwrite=True):
    path = ticket_path(ticket["experiment_id"], tickets_dir)
    if not overwrite and path.exists():
        raise FileExistsError(path)
    _atomic_write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", path)
    return path


def _registry_tickets_dir(registry):
    return Path(registry.get("_tickets_dir", DEFAULT_TICKETS_DIR))


def _registry_logs_dir(registry):
    return Path(registry.get("_logs_dir", DEFAULT_EXPERIMENT_LOGS_DIR))


def _registry_cards_dir(registry):
    if registry.get("_cards_dir"):
        return Path(registry["_cards_dir"])
    if registry.get("_tickets_dir"):
        return Path(registry["_tickets_dir"]).parent / "cards"
    return DEFAULT_CARDS_DIR


def _registry_manifests_dir(registry):
    if registry.get("_manifests_dir"):
        return Path(registry["_manifests_dir"])
    if registry.get("_tickets_dir"):
        return Path(registry["_tickets_dir"]).parent / "manifests"
    return DEFAULT_MANIFESTS_DIR


def _registry_repo_root(registry):
    value = registry.get("_repo_root")
    return Path(value) if value else None


def load_ticket(experiment_id, tickets_dir=DEFAULT_TICKETS_DIR):
    path = ticket_path(experiment_id, tickets_dir)
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _ticket_index_entry(ticket, tickets_dir=DEFAULT_TICKETS_DIR):
    return {
        "experiment_id": ticket.get("experiment_id"),
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": _repo_relative(ticket_path(ticket["experiment_id"], tickets_dir)),
        "card_file": ticket.get("card_file"),
        "revision_manifest_file": ticket.get("revision_manifest_file"),
        "updated_at": utc_now_iso(),
    }


def _sync_index_entry(registry, ticket):
    experiments = registry.setdefault("experiments", [])
    entry = _ticket_index_entry(ticket, _registry_tickets_dir(registry))
    for i, existing in enumerate(experiments):
        if existing.get("experiment_id") == ticket.get("experiment_id"):
            experiments[i] = {**existing, **entry}
            return experiments[i]
    experiments.append(entry)
    return entry


def materialize_experiment(entry):
    ticket_file = entry.get("ticket_file")
    if ticket_file:
        path = REPO_ROOT / ticket_file
        if path.exists():
            with path.open(encoding="utf-8-sig") as f:
                return json.load(f)
    return entry


def iter_experiments(registry):
    return [materialize_experiment(entry) for entry in registry.get("experiments", [])]


def lock_path_for(path):
    path = Path(path)
    return path.with_name(path.name + ".lock")


def _acquire_os_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError from exc
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise
    except OSError as exc:
        raise BlockingIOError from exc


def _release_os_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def file_lock(path, *, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
              stale_seconds=STALE_LOCK_SECONDS):
    lock_path = lock_path_for(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_seconds
    payload = {
        "pid": os.getpid(),
        "created_at": utc_now_iso(),
        "target": _repo_relative(path),
    }

    lock_path.touch(exist_ok=True)
    with lock_path.open("r+", encoding="utf-8") as handle:
        while True:
            try:
                _acquire_os_lock(handle)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    raise TimeoutError(f"timed out waiting for lock: {lock_path}")
                time.sleep(0.1)

        try:
            handle.seek(0)
            handle.truncate()
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            yield lock_path
        finally:
            released_payload = dict(payload)
            released_payload["released_at"] = utc_now_iso()
            handle.seek(0)
            handle.truncate()
            json.dump(released_payload, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            _release_os_lock(handle)


def locked_registry_update(path, mutator, *, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    with file_lock(path, timeout_seconds=timeout_seconds):
        path = Path(path)
        workspace_root = path.parent.parent if path.parent.name == "docs" else path.parent
        registry = load_registry(path)
        registry["_repo_root"] = str(workspace_root)
        registry["_tickets_dir"] = str(workspace_root / "experiments" / "tickets")
        registry["_logs_dir"] = str(workspace_root / "experiments" / "logs")
        registry["_cards_dir"] = str(workspace_root / "experiments" / "cards")
        registry["_manifests_dir"] = str(workspace_root / "experiments" / "manifests")
        result = mutator(registry)
        save_registry(registry, path)
        return result


def latest_backtest_result(data_dir=None):
    data_dir = Path(data_dir or (REPO_ROOT / "data"))
    files = backtest_result_glob(data_dir)
    if not files:
        return None
    return _repo_relative(files[-1])


def _remember_id_source(sources, experiment_id, source):
    normalized = normalize_experiment_id(experiment_id)
    if normalized:
        sources.setdefault(normalized, set()).add(source)


def _load_json_file(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _scan_json_id_file(path, sources, source_prefix, *, root):
    path = Path(path)
    _remember_id_source(sources, path.name, f"{source_prefix}:filename:{_repo_relative(path)}")
    data = _load_json_file(path)
    if isinstance(data, dict):
        _remember_id_source(
            sources,
            data.get("experiment_id"),
            f"{source_prefix}:json:{_repo_relative(path)}",
        )
        for key in (
            "artifact",
            "json",
            "ticket_file",
            "log_file",
            "card_file",
            "revision_manifest_file",
        ):
            value = data.get(key)
            if value:
                _remember_id_source(
                    sources,
                    value,
                    f"{source_prefix}:ref:{_repo_relative(path)}:{key}",
                )
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for match in EXPERIMENT_ID_RE.finditer(text):
        _remember_id_source(
            sources,
            match.group(0),
            f"{source_prefix}:text:{_repo_relative(path)}",
        )


def collect_experiment_id_sources(registry=None, *, root=None):
    registry = registry or {}
    include_filesystem = root is not None or bool(registry.get("_repo_root"))
    root = Path(root or registry.get("_repo_root", REPO_ROOT))
    sources = {}

    for exp in registry.get("experiments", []):
        _remember_id_source(sources, exp.get("experiment_id"), "registry")
        for key in ("ticket_file", "log_file", "card_file", "revision_manifest_file"):
            if exp.get(key):
                _remember_id_source(sources, exp[key], f"registry:{key}")
        result = exp.get("result")
        if isinstance(result, dict):
            for key in ("artifact", "json"):
                if result.get(key):
                    _remember_id_source(sources, result[key], f"registry:result:{key}")

    if not include_filesystem:
        return {experiment_id: sorted(values) for experiment_id, values in sources.items()}

    log_path = root / "docs" / "experiment_log.jsonl"
    if log_path.exists():
        try:
            with log_path.open(encoding="utf-8-sig") as f:
                for line_number, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        row = {}
                    if isinstance(row, dict):
                        _remember_id_source(
                            sources,
                            row.get("experiment_id"),
                            f"jsonl:{_repo_relative(log_path)}:{line_number}",
                        )
                    if "exp-" in line or "exp_" in line:
                        for match in EXPERIMENT_ID_RE.finditer(line):
                            _remember_id_source(
                                sources,
                                match.group(0),
                                f"jsonl:text:{_repo_relative(log_path)}:{line_number}",
                            )
        except OSError:
            pass

    json_dirs = [
        (root / "experiments" / "tickets", "ticket"),
        (root / "docs" / "experiments" / "tickets", "docs_ticket"),
        (root / "experiments" / "logs", "log"),
        (root / "docs" / "experiments" / "logs", "docs_log"),
        (root / "experiments" / "manifests", "manifest"),
    ]
    for directory, source_prefix in json_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            _scan_json_id_file(path, sources, source_prefix, root=root)

    path_dirs = [
        (root / "data" / "experiments", "data_experiment"),
        (root / "experiments" / "artifacts", "artifact"),
    ]
    for directory, source_prefix in path_dirs:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            _remember_id_source(
                sources,
                path.name,
                f"{source_prefix}:path:{_repo_relative(path)}",
                )

    cards_dir = root / "experiments" / "cards"
    if cards_dir.exists():
        for path in cards_dir.glob("*.md"):
            _remember_id_source(
                sources,
                path.name,
                f"card:filename:{_repo_relative(path)}",
            )
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in EXPERIMENT_ID_RE.finditer(text):
                _remember_id_source(
                    sources,
                    match.group(0),
                    f"card:text:{_repo_relative(path)}",
                )

    quant_experiments = root / "quant" / "experiments"
    if quant_experiments.exists():
        for path in quant_experiments.rglob("exp*"):
            if path.is_file():
                _remember_id_source(
                    sources,
                    path.name,
                    f"runner:path:{_repo_relative(path)}",
                )

    return {experiment_id: sorted(values) for experiment_id, values in sources.items()}


def next_experiment_id(registry, today=None, *, root=None):
    today = today or datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"exp-{today}-"
    max_seen = 0
    for eid in collect_experiment_id_sources(registry, root=root):
        if eid.startswith(prefix):
            max_seen = max(max_seen, int(eid.rsplit("-", 1)[1]))
    return f"{prefix}{max_seen + 1:03d}"


def require_available_experiment_id(experiment_id, registry, *, root=None):
    normalized = normalize_experiment_id(experiment_id)
    if not normalized:
        raise ValueError(
            "experiment_id must match exp-YYYYMMDD-NNN, got "
            f"{experiment_id!r}"
        )
    sources = collect_experiment_id_sources(registry, root=root)
    if normalized in sources:
        joined = ", ".join(sources[normalized])
        raise ValueError(f"experiment_id already exists: {normalized} ({joined})")
    return normalized


def parse_csv(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional_float(value, field_name):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number, got {value!r}") from exc


def normalize_prediction(
    prediction=None,
    *,
    success_probability=None,
    expected_ev_delta=None,
    expected_pnl_delta=None,
    main_failure_modes=None,
    confidence_reason=None,
):
    """Normalize an experiment pre-run prediction.

    The prediction is research-process metadata only. It must never be consumed
    by trading, ranking, sizing, or risk logic.
    """
    base = dict(prediction or {})
    if success_probability is not None:
        base["success_probability"] = success_probability
    if expected_ev_delta is not None:
        base["expected_ev_delta"] = expected_ev_delta
    if expected_pnl_delta is not None:
        base["expected_pnl_delta"] = expected_pnl_delta
    if main_failure_modes is not None:
        base["main_failure_modes"] = main_failure_modes
    if confidence_reason is not None:
        base["confidence_reason"] = confidence_reason

    probability = _optional_float(base.get("success_probability"), "success_probability")
    expected_ev = _optional_float(base.get("expected_ev_delta"), "expected_ev_delta")
    expected_pnl = _optional_float(base.get("expected_pnl_delta"), "expected_pnl_delta")
    failure_modes = parse_csv(base.get("main_failure_modes"))
    reason = str(base.get("confidence_reason") or "").strip()

    if probability is None and expected_ev is None and expected_pnl is None and not failure_modes and not reason:
        return None
    if probability is not None and not 0.0 <= probability <= 1.0:
        raise ValueError("success_probability must be between 0 and 1")

    normalized = {
        "success_probability": probability,
        "expected_ev_delta": expected_ev,
        "expected_pnl_delta": expected_pnl,
        "main_failure_modes": failure_modes,
        "confidence_reason": reason or None,
    }
    if base.get("recorded_at"):
        normalized["recorded_at"] = base["recorded_at"]
    else:
        normalized["recorded_at"] = utc_now_iso()
    return normalized


def prediction_required_for_lane(lane):
    return lane in PREDICTION_REQUIRED_LANES


def prediction_missing_reasons(ticket):
    if not prediction_required_for_lane(ticket.get("lane")):
        return []
    prediction = normalize_prediction(ticket.get("prediction"))
    if not prediction:
        return ["missing_prediction"]
    reasons = []
    if prediction.get("success_probability") is None:
        reasons.append("missing_success_probability")
    if not prediction.get("main_failure_modes"):
        reasons.append("missing_main_failure_modes")
    return reasons


def require_pre_run_prediction(ticket, *, allow_missing_prediction=False):
    reasons = prediction_missing_reasons(ticket)
    if not reasons or allow_missing_prediction:
        return
    experiment_id = ticket.get("experiment_id") or "new experiment"
    lane = ticket.get("lane")
    joined = ", ".join(reasons)
    raise ValueError(
        f"{lane} ticket {experiment_id} requires a pre-run prediction "
        f"before work can continue; missing: {joined}"
    )


def parse_windows(values):
    windows = []
    for raw in values or []:
        if ":" not in raw:
            raise ValueError(f"window must be START:END, got {raw!r}")
        start, end = raw.split(":", 1)
        windows.append({"start": start, "end": end})
    return windows


def _template_scope(scope, experiment_id, lane, change_type):
    return scope.format(
        experiment_id=experiment_id,
        lane=lane,
        change_type=change_type,
    )


def experiment_file_prefix(experiment_id):
    return experiment_id.replace("-", "_")


def slugify_file_part(value, fallback="experiment"):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value or "").strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    return slug[:80].strip("_") or fallback


def default_file_stem(experiment_id, single_causal_variable, file_slug=None):
    slug_source = file_slug or single_causal_variable
    return f"{experiment_file_prefix(experiment_id)}_{slugify_file_part(slug_source)}"


def _yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, (bool, int, float)):
        return json.dumps(value)
    return json.dumps(str(value), ensure_ascii=False)


def _metadata_tags(ticket):
    raw = [
        ticket.get("lane"),
        ticket.get("status"),
        ticket.get("change_type"),
        ticket.get("mechanism_family"),
        ticket.get("trial_family"),
        ticket.get("new_evidence_type"),
    ]
    tags = []
    for value in raw:
        slug = slugify_file_part(value, fallback="")
        if slug and slug not in tags:
            tags.append(slug)
    return tags


def build_experiment_card_markdown(ticket):
    metadata = {
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components") or [],
        "new_evidence_type": ticket.get("new_evidence_type"),
        "created_at": ticket.get("created_at"),
        "baseline_result_file": ticket.get("baseline_result_file"),
    }
    hub_identity = ticket.get("hub_identity") or {}
    if hub_identity.get("repo_id"):
        metadata["hub_repo_id"] = hub_identity["repo_id"]

    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("tags:")
    for tag in _metadata_tags(ticket):
        lines.append(f"  - {_yaml_scalar(tag)}")
    lines.extend([
        "---",
        "",
        f"# Experiment Card: {ticket.get('experiment_id')}",
        "",
        "## Summary",
        "",
        ticket.get("hypothesis") or "TODO: fill experiment hypothesis.",
        "",
        "## Identity",
        "",
        f"- Status: `{ticket.get('status')}`",
        f"- Lane: `{ticket.get('lane')}`",
        f"- Change type: `{ticket.get('change_type')}`",
        f"- Owner: `{ticket.get('owner') or 'unclaimed'}`",
        f"- UID: `{ticket.get('experiment_uid')}`",
        "",
        "## Decision Hypothesis",
        "",
        f"- Decision variable / policy bundle: `{ticket.get('single_causal_variable')}`",
        f"- Changed variable: `{ticket.get('changed_variable')}`",
        f"- Causal components: `{', '.join(ticket.get('causal_components') or []) or 'none'}`",
        f"- Locked variables: `{', '.join(ticket.get('locked_variables') or [])}`",
        "",
        "## Trial Accounting",
        "",
        f"- Mechanism family: `{ticket.get('mechanism_family')}`",
        f"- Trial family: `{ticket.get('trial_family')}`",
        f"- Trial variant: `{ticket.get('trial_variant_id')}`",
        f"- Prior trial count: `{ticket.get('prior_trial_count')}`",
        f"- Nearby prior experiments: `{', '.join(ticket.get('nearby_prior_experiments') or []) or 'none'}`",
        f"- New evidence type: `{ticket.get('new_evidence_type')}`",
        f"- Multiple-testing risk: `{ticket.get('multiple_testing_risk_bucket')}`",
        "",
        "## Evaluation Plan",
        "",
        f"- Baseline result file: `{ticket.get('baseline_result_file') or 'not set'}`",
        f"- Acceptance rule: {ticket.get('acceptance_rule')}",
        "",
        "## Reserved Files",
        "",
    ])
    for scope in ticket.get("allowed_write_scope") or []:
        lines.append(f"- `{scope}`")
    lines.extend([
        "",
        "## Pre-Run Prediction",
        "",
        "```json",
        json.dumps(ticket.get("prediction") or {}, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Closeout Notes",
        "",
        "- Decision: TODO",
        "- Before artifact: TODO",
        "- After artifact: TODO",
        "- Main blocker or acceptance basis: TODO",
        "- Next retry requires: TODO",
        "",
    ])
    return "\n".join(lines)


def save_experiment_card(ticket, cards_dir=DEFAULT_CARDS_DIR, *, overwrite=True):
    path = experiment_card_path(ticket["experiment_id"], cards_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as f:
        f.write(build_experiment_card_markdown(ticket))
    return path


def _sha256_file(path):
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_capture(root, *args):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_revision_snapshot(root):
    root = Path(root or REPO_ROOT)
    status = _git_capture(root, "status", "--short")
    return {
        "commit": _git_capture(root, "rev-parse", "HEAD"),
        "branch": _git_capture(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "status_short": status.splitlines() if status else [],
    }


def _resolve_workspace_path(value, root):
    if not value:
        return None
    path = Path(value)
    if path.is_absolute() or root is None:
        return path
    return Path(root) / path


def _file_manifest_entry(value, *, root=None):
    path = _resolve_workspace_path(value, root)
    if path is None:
        return None
    return {
        "path": _repo_relative(path),
        "exists": path.exists(),
        "sha256": _sha256_file(path),
    }


def build_revision_manifest(ticket, *, repo_root=None, ticket_file=None, card_file=None):
    repo_root = Path(repo_root or REPO_ROOT)
    files = {
        "ticket": _file_manifest_entry(ticket_file or ticket.get("ticket_file"), root=repo_root),
        "card": _file_manifest_entry(card_file or ticket.get("card_file"), root=repo_root),
        "baseline_result": _file_manifest_entry(ticket.get("baseline_result_file"), root=repo_root),
    }
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "generated_at": utc_now_iso(),
        "created_at": ticket.get("created_at"),
        "hub_identity": ticket.get("hub_identity") or {},
        "git": _git_revision_snapshot(repo_root),
        "files": {key: value for key, value in files.items() if value is not None},
        "artifact_roots": {
            "runner": f"quant/experiments/{experiment_file_prefix(ticket['experiment_id'])}_<slug>.py",
            "data": f"data/experiments/{ticket['experiment_id']}/",
            "artifact": f"experiments/artifacts/{ticket['experiment_id']}_<slug>.md",
            "log": f"experiments/logs/{ticket['experiment_id']}.json",
        },
        "reservation_note": (
            "Generated when the experiment ID was reserved. Update or regenerate "
            "after final artifacts exist if exact after-run hashes are required."
        ),
    }


def save_revision_manifest(
    ticket,
    manifests_dir=DEFAULT_MANIFESTS_DIR,
    *,
    repo_root=None,
    ticket_file=None,
    card_file=None,
    overwrite=True,
):
    path = revision_manifest_path(ticket["experiment_id"], manifests_dir)
    if not overwrite and path.exists():
        raise FileExistsError(path)
    manifest = build_revision_manifest(
        ticket,
        repo_root=repo_root,
        ticket_file=ticket_file,
        card_file=card_file,
    )
    _atomic_write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        path)
    return path


def default_allowed_write_scope(
    experiment_id,
    lane,
    single_causal_variable,
    file_slug=None,
):
    stem = default_file_stem(experiment_id, single_causal_variable, file_slug)
    return [
        f"quant/experiments/{stem}.py",
        f"data/experiments/{experiment_id}/{stem}.json",
        f"experiments/cards/{experiment_id}.md",
        f"experiments/manifests/{experiment_id}.json",
        f"experiments/tickets/{experiment_id}.json",
        f"experiments/logs/{experiment_id}.json",
        "docs/experiment_log.jsonl",
        "docs/experiment_registry.json",
    ]


def normalize_allowed_write_scope(
    scopes,
    *,
    experiment_id,
    lane,
    change_type,
    single_causal_variable,
    file_slug=None,
    exclusive_scope_ok=False,
):
    if not scopes:
        return default_allowed_write_scope(
            experiment_id,
            lane,
            single_causal_variable,
            file_slug,
        )

    normalized = [
        _template_scope(scope, experiment_id, lane, change_type)
        for scope in scopes
    ]
    if exclusive_scope_ok:
        return normalized

    broad = [
        scope for scope in normalized
        if _normalize_scope(scope) in DISALLOWED_BROAD_SCOPES
    ]
    if broad:
        raise ValueError(
            "broad allowed_write_scope entries require --exclusive-scope-ok: "
            + ", ".join(broad)
        )
    return normalized


def get_experiment(registry, experiment_id):
    for exp in registry.get("experiments", []):
        if exp.get("experiment_id") == experiment_id:
            return materialize_experiment(exp)
    return None


def create_ticket(
    registry,
    *,
    experiment_id=None,
    lane,
    hypothesis,
    change_type,
    single_causal_variable,
    causal_components=None,
    mechanism_family=None,
    trial_family=None,
    trial_variant_id=None,
    changed_variable=None,
    prior_trial_count=0,
    nearby_prior_experiments=None,
    multiple_testing_risk_bucket="minimal",
    new_evidence_type="not_declared",
    baseline_result_file=None,
    allowed_write_scope=None,
    must_not_touch=None,
    locked_variables=None,
    evaluation_windows=None,
    acceptance_rule=None,
    owner=None,
    file_slug=None,
    exclusive_scope_ok=False,
    prediction=None,
):
    if lane not in VALID_LANES:
        raise ValueError(f"lane must be one of {sorted(VALID_LANES)}")
    repo_root = _registry_repo_root(registry)
    baseline = baseline_result_file or latest_backtest_result()
    if experiment_id is None:
        experiment_id = next_experiment_id(registry, root=repo_root)
    experiment_id = require_available_experiment_id(
        experiment_id,
        registry,
        root=repo_root,
    )
    changed_variable = changed_variable or single_causal_variable
    mechanism_family = mechanism_family or change_type
    trial_family = trial_family or mechanism_family
    trial_variant_id = trial_variant_id or experiment_id
    created_at = utc_now_iso()
    file_part = slugify_file_part(file_slug or single_causal_variable)
    write_scope = normalize_allowed_write_scope(
        allowed_write_scope,
        experiment_id=experiment_id,
        lane=lane,
        change_type=change_type,
        single_causal_variable=single_causal_variable,
        file_slug=file_slug,
        exclusive_scope_ok=exclusive_scope_ok,
    )
    normalized_prediction = normalize_prediction(prediction)
    require_pre_run_prediction(
        {
            "experiment_id": experiment_id,
            "lane": lane,
            "prediction": normalized_prediction,
        }
    )
    ticket = {
        "experiment_id": experiment_id,
        "experiment_uid": new_experiment_uid(),
        "hub_identity": {
            "scheme": "hf_hub_local_v1",
            "namespace": "ginger/experiments",
            "repo_id": f"ginger/experiments/{experiment_id}",
            "slug": file_part,
            "reserved_at": created_at,
            "reservation_rule": (
                "Create the ticket under registry lock before writing runners, "
                "artifacts, data, or logs. Existing IDs are rejected across "
                "registry, JSONL, tickets, logs, artifacts, data, and runners."
            ),
        },
        "status": "proposed",
        "lane": lane,
        "owner": owner,
        "hypothesis": hypothesis,
        "change_type": change_type,
        "mechanism_family": mechanism_family,
        "trial_family": trial_family,
        "trial_variant_id": trial_variant_id,
        "single_causal_variable": single_causal_variable,
        "changed_variable": changed_variable,
        "causal_components": causal_components or [],
        "prior_trial_count": int(prior_trial_count or 0),
        "nearby_prior_experiments": nearby_prior_experiments or [],
        "multiple_testing_risk_bucket": multiple_testing_risk_bucket,
        "new_evidence_type": new_evidence_type,
        "baseline_result_file": baseline,
        "allowed_write_scope": write_scope,
        "must_not_touch": must_not_touch or [],
        "locked_variables": locked_variables or (
            [single_causal_variable] if single_causal_variable else []
        ),
        "evaluation_windows": evaluation_windows or [],
        "acceptance_rule": acceptance_rule or "Use AGENTS.md Gate 4.",
        "prediction": normalized_prediction,
        "created_at": created_at,
        "claimed_at": None,
        "completed_at": None,
        "result": None,
    }
    if "_tickets_dir" in registry:
        workspace_root = _registry_repo_root(registry)
        ticket_file = ticket_path(experiment_id, _registry_tickets_dir(registry))
        card_file = experiment_card_path(experiment_id, _registry_cards_dir(registry))
        manifest_file = revision_manifest_path(
            experiment_id,
            _registry_manifests_dir(registry),
        )
        ticket["ticket_file"] = _repo_relative(ticket_file)
        ticket["card_file"] = _repo_relative(card_file)
        ticket["revision_manifest_file"] = _repo_relative(manifest_file)
        for label, path in (
            ("experiment ticket", ticket_file),
            ("experiment card", card_file),
            ("revision manifest", manifest_file),
        ):
            if path.exists():
                raise ValueError(f"{label} already exists: {path}")
        try:
            save_ticket(ticket, _registry_tickets_dir(registry), overwrite=False)
            save_experiment_card(ticket, _registry_cards_dir(registry), overwrite=False)
            save_revision_manifest(
                ticket,
                _registry_manifests_dir(registry),
                repo_root=workspace_root,
                ticket_file=ticket_file,
                card_file=card_file,
                overwrite=False,
            )
        except FileExistsError as exc:
            raise ValueError(f"experiment identity artifact already exists: {exc}") from exc
        _sync_index_entry(registry, ticket)
    else:
        registry.setdefault("experiments", []).append(ticket)
    return ticket


def _path_overlaps(left, right):
    a = _normalize_scope(left)
    b = _normalize_scope(right)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _normalize_scope(scope):
    return _repo_relative(scope).replace("\\", "/").rstrip("/").lower()


def _is_shared_coordination_scope(scope):
    return _normalize_scope(scope) in SHARED_COORDINATION_SCOPES


def _conflict_scopes(scopes):
    return [scope for scope in (scopes or []) if not _is_shared_coordination_scope(scope)]


def find_conflicts(registry, experiment):
    conflicts = []
    scopes = _conflict_scopes(experiment.get("allowed_write_scope") or [])
    locked = set(experiment.get("locked_variables") or [])
    for other in iter_experiments(registry):
        if other is experiment:
            continue
        if other.get("status") not in ACTIVE_STATUSES:
            continue
        other_scopes = _conflict_scopes(other.get("allowed_write_scope") or [])
        scope_hits = [
            [s, o]
            for s in scopes
            for o in other_scopes
            if _path_overlaps(s, o)
        ]
        locked_hits = sorted(locked.intersection(other.get("locked_variables") or []))
        if scope_hits or locked_hits:
            conflicts.append({
                "experiment_id": other.get("experiment_id"),
                "owner": other.get("owner"),
                "status": other.get("status"),
                "scope_conflicts": scope_hits,
                "locked_variable_conflicts": locked_hits,
            })
    return conflicts


def claim_ticket(registry, experiment_id, owner, force=False):
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    conflicts = find_conflicts(registry, exp)
    if conflicts and not force:
        return exp, conflicts
    exp["owner"] = owner
    exp["status"] = "claimed"
    exp["claimed_at"] = utc_now_iso()
    if "_tickets_dir" in registry:
        save_ticket(exp, _registry_tickets_dir(registry))
        _sync_index_entry(registry, exp)
    return exp, []


def metric_snapshot(result):
    benchmarks = result.get("benchmarks") or {}
    total_return = benchmarks.get("strategy_total_return_pct")
    sharpe_daily = result.get("sharpe_daily")
    ev = result.get("expected_value_score")
    if ev is None and total_return is not None and sharpe_daily is not None:
        ev = round(total_return * sharpe_daily, 4)
    return {
        "expected_value_score": ev,
        "sharpe": result.get("sharpe"),
        "sharpe_daily": sharpe_daily,
        "total_return_pct": total_return,
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "total_pnl": result.get("total_pnl"),
    }


def _delta(after, before, key):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(a - b, 6)


def evaluate_gate(before_metrics, after_metrics):
    reasons = []
    before_ev = before_metrics.get("expected_value_score")
    after_ev = after_metrics.get("expected_value_score")
    if before_ev not in (None, 0) and after_ev is not None:
        ev_pct = (after_ev - before_ev) / abs(before_ev)
        if ev_pct > 0.10:
            reasons.append(f"expected_value_score improved {ev_pct:.2%}")

    sharpe_delta = _delta(after_metrics, before_metrics, "sharpe")
    if sharpe_delta is not None and sharpe_delta > 0.1:
        reasons.append(f"sharpe improved {sharpe_delta:.4f}")

    dd_delta = _delta(after_metrics, before_metrics, "max_drawdown_pct")
    if dd_delta is not None and dd_delta < -0.01:
        reasons.append(f"max_drawdown_pct fell {-dd_delta:.4f}")

    before_pnl = before_metrics.get("total_pnl")
    after_pnl = after_metrics.get("total_pnl")
    if before_pnl not in (None, 0) and after_pnl is not None:
        pnl_pct = (after_pnl - before_pnl) / abs(before_pnl)
        if pnl_pct > 0.05:
            reasons.append(f"total_pnl improved {pnl_pct:.2%}")

    trade_delta = _delta(after_metrics, before_metrics, "trade_count")
    win_delta = _delta(after_metrics, before_metrics, "win_rate")
    if trade_delta is not None and win_delta is not None:
        if trade_delta > 0 and win_delta >= 0:
            reasons.append("trade_count increased while win_rate did not decline")

    return {
        "decision": "accepted" if reasons else "rejected",
        "acceptance_reasons": reasons,
    }


def judge_results(before_path, after_path):
    with Path(before_path).open(encoding="utf-8-sig") as f:
        before_raw = json.load(f)
    with Path(after_path).open(encoding="utf-8-sig") as f:
        after_raw = json.load(f)
    before = metric_snapshot(before_raw)
    after = metric_snapshot(after_raw)
    delta = {
        key: _delta(after, before, key)
        for key in before
        if isinstance(before.get(key), (int, float)) or isinstance(after.get(key), (int, float))
    }
    gate = evaluate_gate(before, after)
    return {
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        **gate,
    }


def final_decision(judgement, status_override=None):
    if status_override is None:
        return judgement["decision"]
    if status_override not in FINAL_STATUSES:
        raise ValueError(f"status_override must be one of {sorted(FINAL_STATUSES)}")
    return status_override


def _actual_success_from_decision(decision):
    if decision in {"accepted"} or str(decision).startswith("accepted"):
        return 1
    if decision in {"rejected", "rolled_back"} or str(decision).startswith("rejected"):
        return 0
    return None


def _surprise_level(probability, actual_success):
    if probability is None or actual_success is None:
        return "not_scored"
    surprise = abs(probability - actual_success)
    if surprise >= 0.75:
        return "high"
    if surprise >= 0.50:
        return "medium"
    if surprise >= 0.25:
        return "low"
    return "very_low"


def _calibration_direction(probability, actual_success):
    if probability is None or actual_success is None:
        return "not_scored"
    predicted_success = probability >= 0.5
    if predicted_success and not actual_success:
        return "overconfident"
    if not predicted_success and actual_success:
        return "underconfident"
    return "directionally_calibrated"


def build_prediction_calibration(
    prediction,
    judgement,
    decision,
    *,
    realized_failure_mode=None,
    surprise_note=None,
):
    prediction = normalize_prediction(prediction)
    if not prediction:
        return None

    actual_success = _actual_success_from_decision(decision)
    probability = prediction.get("success_probability")
    brier_score = None
    if probability is not None and actual_success is not None:
        brier_score = round((probability - actual_success) ** 2, 6)

    deltas = judgement.get("delta_metrics") or {}
    actual_ev_delta = deltas.get("expected_value_score")
    actual_pnl_delta = deltas.get("total_pnl")
    expected_ev_delta = prediction.get("expected_ev_delta")
    expected_pnl_delta = prediction.get("expected_pnl_delta")

    ev_prediction_error = None
    if actual_ev_delta is not None and expected_ev_delta is not None:
        ev_prediction_error = round(actual_ev_delta - expected_ev_delta, 6)
    pnl_prediction_error = None
    if actual_pnl_delta is not None and expected_pnl_delta is not None:
        pnl_prediction_error = round(actual_pnl_delta - expected_pnl_delta, 2)

    predicted_modes = prediction.get("main_failure_modes") or []
    realized_mode = str(realized_failure_mode or "").strip() or None
    failure_mode_hit = None
    if realized_mode:
        failure_mode_hit = realized_mode in predicted_modes

    return {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier_score,
        "calibration_direction": _calibration_direction(probability, actual_success),
        "surprise_level": _surprise_level(probability, actual_success),
        "expected_ev_delta": expected_ev_delta,
        "actual_ev_delta": actual_ev_delta,
        "ev_prediction_error": ev_prediction_error,
        "expected_pnl_delta": expected_pnl_delta,
        "actual_pnl_delta": actual_pnl_delta,
        "pnl_prediction_error": pnl_prediction_error,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_mode": realized_mode,
        "predicted_failure_mode_hit": failure_mode_hit,
        "surprise_note": surprise_note,
    }


def build_log_draft(
    experiment,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
    change_summary=None,
    notes=None,
    realized_failure_mode=None,
    surprise_note=None,
    allow_missing_prediction=False,
):
    decision = final_decision(judgement, status_override)
    require_pre_run_prediction(
        experiment,
        allow_missing_prediction=allow_missing_prediction,
    )
    row = {
        "experiment_id": experiment.get("experiment_id"),
        "timestamp": utc_now_iso(),
        "status": decision,
        "hypothesis": experiment.get("hypothesis"),
        "change_summary": change_summary or (
            "Generated by scripts/judge_experiment.py; fill in code changes before appending."
        ),
        "change_type": experiment.get("change_type"),
        "mechanism_family": experiment.get("mechanism_family"),
        "trial_family": experiment.get("trial_family"),
        "trial_variant_id": experiment.get("trial_variant_id"),
        "changed_variable": experiment.get("changed_variable"),
        "prior_trial_count": experiment.get("prior_trial_count", 0),
        "nearby_prior_experiments": experiment.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": experiment.get("multiple_testing_risk_bucket"),
        "new_evidence_type": experiment.get("new_evidence_type"),
        "component": ", ".join(experiment.get("allowed_write_scope") or []),
        "parameters": {
            "single_causal_variable": experiment.get("single_causal_variable"),
            "locked_variables": experiment.get("locked_variables") or [],
        },
        "date_range": (experiment.get("evaluation_windows") or [{}])[0],
        "secondary_windows": (experiment.get("evaluation_windows") or [])[1:],
        "market_regime_summary": {},
        "before_metrics": judgement["before_metrics"],
        "after_metrics": judgement["after_metrics"],
        "delta_metrics": judgement["delta_metrics"],
        "llm_metrics": {"used_llm": False},
        "decision": decision,
        "rejection_reason": (
            None if decision in {"accepted", "observed_only"}
            else "No AGENTS.md Gate 4 acceptance condition was met."
        ),
        "next_retry_requires": [],
        "related_files": [_repo_relative(before_path), _repo_relative(after_path)],
        "notes": notes if notes is not None else "; ".join(judgement.get("acceptance_reasons") or []),
    }
    prediction = normalize_prediction(experiment.get("prediction"))
    if prediction:
        row["prediction"] = prediction
        row["calibration"] = build_prediction_calibration(
            prediction,
            judgement,
            decision,
            realized_failure_mode=realized_failure_mode,
            surprise_note=surprise_note,
        )
    return row


def update_result(
    registry,
    experiment_id,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
    realized_failure_mode=None,
    surprise_note=None,
    allow_missing_prediction=False,
):
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    decision = final_decision(judgement, status_override)
    require_pre_run_prediction(
        exp,
        allow_missing_prediction=allow_missing_prediction,
    )
    exp["status"] = decision
    exp["completed_at"] = utc_now_iso()
    exp["result"] = {
        "decision": decision,
        "acceptance_reasons": judgement.get("acceptance_reasons") or [],
        "before_result_file": _repo_relative(before_path),
        "after_result_file": _repo_relative(after_path),
        "delta_metrics": judgement.get("delta_metrics") or {},
    }
    prediction = normalize_prediction(exp.get("prediction"))
    if prediction:
        exp["result"]["calibration"] = build_prediction_calibration(
            prediction,
            judgement,
            decision,
            realized_failure_mode=realized_failure_mode,
            surprise_note=surprise_note,
        )
    if "_tickets_dir" in registry:
        save_ticket(exp, _registry_tickets_dir(registry))
        _sync_index_entry(registry, exp)
    return exp


def _load_json_file(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _closed_status(value):
    status = str(value or "")
    return status in FINAL_STATUSES or status.startswith(
        ("accepted", "rejected", "observed_only")
    )


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _experiment_id_date(experiment_id):
    normalized = normalize_experiment_id(experiment_id)
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized[4:12], "%Y%m%d").date()
    except ValueError:
        return None


def _prediction_enforcement_datetime():
    parsed = _parse_iso_datetime(PREDICTION_ENFORCEMENT_STARTED_AT)
    if parsed is None:
        raise ValueError("invalid PREDICTION_ENFORCEMENT_STARTED_AT")
    return parsed


def prediction_enforcement_bucket(ticket):
    """Classify prediction gaps as legacy or post-enforcement.

    Missing timestamps are treated as legacy because we cannot prove the agent
    saw the new code-enforced rule. A future-dated experiment ID still counts
    as post-enforcement even when a hand-written stub omits timestamps.
    """
    cutoff = _prediction_enforcement_datetime()
    for field in ("created_at", "reserved_at", "updated_at", "claimed_at", "completed_at"):
        parsed = _parse_iso_datetime(ticket.get(field))
        if parsed is not None:
            return (
                "post_enforcement"
                if parsed >= cutoff
                else "legacy_pre_enforcement"
            )

    hub_identity = ticket.get("hub_identity") or {}
    parsed = _parse_iso_datetime(hub_identity.get("reserved_at"))
    if parsed is not None:
        return "post_enforcement" if parsed >= cutoff else "legacy_pre_enforcement"

    experiment_date = _experiment_id_date(ticket.get("experiment_id"))
    if experiment_date and experiment_date > cutoff.date():
        return "post_enforcement"
    return "legacy_pre_enforcement"


def _ticket_records_for_audit(registry, tickets_dir=DEFAULT_TICKETS_DIR):
    records = {}
    for exp in iter_experiments(registry):
        experiment_id = exp.get("experiment_id")
        if experiment_id:
            records[experiment_id] = exp
    tickets_path = Path(tickets_dir)
    if tickets_path.exists():
        for path in sorted(tickets_path.glob("exp-*.json")):
            row = _load_json_file(path)
            if not isinstance(row, dict):
                continue
            experiment_id = row.get("experiment_id") or normalize_experiment_id(path.stem)
            if experiment_id:
                row.setdefault("experiment_id", experiment_id)
                records[experiment_id] = {**records.get(experiment_id, {}), **row}
    return records


def _log_records_for_audit(logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    records = {}
    logs_path = Path(logs_dir)
    if logs_path.exists():
        for path in sorted(logs_path.glob("exp-*.json")):
            row = _load_json_file(path)
            if not isinstance(row, dict):
                continue
            experiment_id = row.get("experiment_id") or normalize_experiment_id(path.stem)
            if experiment_id:
                records[experiment_id] = row
    return records


def audit_experiment_process(
    registry,
    *,
    tickets_dir=DEFAULT_TICKETS_DIR,
    logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR,
):
    """Audit whether experiment objects obey the code-enforced process contract."""
    tickets = _ticket_records_for_audit(registry, tickets_dir=tickets_dir)
    logs = _log_records_for_audit(logs_dir=logs_dir)
    alpha_ticket_count = 0
    legacy_alpha_ticket_count = 0
    post_alpha_ticket_count = 0
    closed_alpha_count = 0
    closed_legacy_alpha_count = 0
    closed_post_alpha_count = 0
    missing_prediction = []
    legacy_missing_prediction = []
    post_missing_prediction = []
    closed_missing_prediction = []
    closed_legacy_missing_prediction = []
    closed_post_missing_prediction = []
    closed_missing_calibration = []
    closed_legacy_missing_calibration = []
    closed_post_missing_calibration = []

    for experiment_id, ticket in sorted(tickets.items()):
        if not prediction_required_for_lane(ticket.get("lane")):
            continue
        alpha_ticket_count += 1
        bucket = prediction_enforcement_bucket(ticket)
        if bucket == "post_enforcement":
            post_alpha_ticket_count += 1
        else:
            legacy_alpha_ticket_count += 1
        reasons = prediction_missing_reasons(ticket)
        status = ticket.get("status")
        is_closed = _closed_status(status)
        if is_closed:
            closed_alpha_count += 1
            if bucket == "post_enforcement":
                closed_post_alpha_count += 1
            else:
                closed_legacy_alpha_count += 1
        if reasons:
            item = {
                "experiment_id": experiment_id,
                "lane": ticket.get("lane"),
                "status": status,
                "missing": reasons,
                "enforcement_bucket": bucket,
            }
            missing_prediction.append(item)
            if bucket == "post_enforcement":
                post_missing_prediction.append(item)
            else:
                legacy_missing_prediction.append(item)
            if is_closed:
                closed_missing_prediction.append(item)
                if bucket == "post_enforcement":
                    closed_post_missing_prediction.append(item)
                else:
                    closed_legacy_missing_prediction.append(item)

        log_row = logs.get(experiment_id) or {}
        result = ticket.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        has_calibration = bool(log_row.get("calibration") or result.get("calibration"))
        if is_closed and not has_calibration:
            item = {
                "experiment_id": experiment_id,
                "lane": ticket.get("lane"),
                "status": status,
                "enforcement_bucket": bucket,
            }
            closed_missing_calibration.append(item)
            if bucket == "post_enforcement":
                closed_post_missing_calibration.append(item)
            else:
                closed_legacy_missing_calibration.append(item)

    passed = not post_missing_prediction and not closed_post_missing_calibration
    return {
        "schema_version": 2,
        "checked_at": utc_now_iso(),
        "prediction_enforcement_started_at": PREDICTION_ENFORCEMENT_STARTED_AT,
        "tickets_checked": len(tickets),
        "logs_checked": len(logs),
        "alpha_ticket_count": alpha_ticket_count,
        "legacy_pre_enforcement_alpha_ticket_count": legacy_alpha_ticket_count,
        "post_enforcement_alpha_ticket_count": post_alpha_ticket_count,
        "closed_alpha_count": closed_alpha_count,
        "closed_legacy_pre_enforcement_alpha_count": closed_legacy_alpha_count,
        "closed_post_enforcement_alpha_count": closed_post_alpha_count,
        "alpha_missing_prediction_count": len(missing_prediction),
        "legacy_pre_enforcement_missing_prediction_count": len(legacy_missing_prediction),
        "post_enforcement_missing_prediction_count": len(post_missing_prediction),
        "closed_alpha_missing_prediction_count": len(closed_missing_prediction),
        "closed_legacy_pre_enforcement_missing_prediction_count": len(
            closed_legacy_missing_prediction
        ),
        "closed_post_enforcement_missing_prediction_count": len(
            closed_post_missing_prediction
        ),
        "closed_alpha_missing_calibration_count": len(closed_missing_calibration),
        "closed_legacy_pre_enforcement_missing_calibration_count": len(
            closed_legacy_missing_calibration
        ),
        "closed_post_enforcement_missing_calibration_count": len(
            closed_post_missing_calibration
        ),
        "prediction_coverage": (
            round((alpha_ticket_count - len(missing_prediction)) / alpha_ticket_count, 4)
            if alpha_ticket_count
            else None
        ),
        "legacy_pre_enforcement_prediction_coverage": (
            round(
                (legacy_alpha_ticket_count - len(legacy_missing_prediction))
                / legacy_alpha_ticket_count,
                4,
            )
            if legacy_alpha_ticket_count
            else None
        ),
        "post_enforcement_prediction_coverage": (
            round(
                (post_alpha_ticket_count - len(post_missing_prediction))
                / post_alpha_ticket_count,
                4,
            )
            if post_alpha_ticket_count
            else None
        ),
        "closed_calibration_coverage": (
            round(
                (closed_alpha_count - len(closed_missing_calibration))
                / closed_alpha_count,
                4,
            )
            if closed_alpha_count
            else None
        ),
        "legacy_pre_enforcement_closed_calibration_coverage": (
            round(
                (
                    closed_legacy_alpha_count
                    - len(closed_legacy_missing_calibration)
                )
                / closed_legacy_alpha_count,
                4,
            )
            if closed_legacy_alpha_count
            else None
        ),
        "post_enforcement_closed_calibration_coverage": (
            round(
                (closed_post_alpha_count - len(closed_post_missing_calibration))
                / closed_post_alpha_count,
                4,
            )
            if closed_post_alpha_count
            else None
        ),
        "missing_prediction_examples": missing_prediction[:25],
        "legacy_pre_enforcement_missing_prediction_examples": (
            legacy_missing_prediction[:25]
        ),
        "post_enforcement_missing_prediction_examples": post_missing_prediction[:25],
        "closed_missing_prediction_examples": closed_missing_prediction[:25],
        "closed_legacy_pre_enforcement_missing_prediction_examples": (
            closed_legacy_missing_prediction[:25]
        ),
        "closed_post_enforcement_missing_prediction_examples": (
            closed_post_missing_prediction[:25]
        ),
        "closed_missing_calibration_examples": closed_missing_calibration[:25],
        "closed_legacy_pre_enforcement_missing_calibration_examples": (
            closed_legacy_missing_calibration[:25]
        ),
        "closed_post_enforcement_missing_calibration_examples": (
            closed_post_missing_calibration[:25]
        ),
        "passed": passed,
        "strict_blocks_only_post_enforcement_gaps": True,
    }


def experiment_log_exists(experiment_id, logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    return experiment_log_path(experiment_id, logs_dir).exists()


def save_experiment_log_entry(row, *, allow_duplicate=False,
                              logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR,
                              timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    experiment_id = row.get("experiment_id")
    if not experiment_id:
        raise ValueError("log row must include experiment_id")
    path = experiment_log_path(experiment_id, logs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout_seconds=timeout_seconds):
        if path.exists() and not allow_duplicate:
            raise ValueError(f"experiment log already exists: {path}")
        _atomic_write_text(
            json.dumps(row, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            path)
    return path


def experiment_id_exists_in_log(log_path, experiment_id):
    path = Path(log_path)
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == experiment_id:
                return True
    return False


def append_log_entry(log_path, row, *, allow_duplicate=False,
                     timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    experiment_id = row.get("experiment_id")
    if not experiment_id:
        raise ValueError("log row must include experiment_id")
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with file_lock(path, timeout_seconds=timeout_seconds):
        if not allow_duplicate and experiment_id_exists_in_log(path, experiment_id):
            raise ValueError(f"experiment_id already exists in log: {experiment_id}")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def add_common_registry_arg(parser):
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to experiment registry JSON.",
    )
    parser.add_argument(
        "--lock-timeout-seconds",
        type=float,
        default=DEFAULT_LOCK_TIMEOUT_SECONDS,
        help="Seconds to wait for registry/log locks before failing.",
    )
