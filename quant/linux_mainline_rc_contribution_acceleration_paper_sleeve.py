"""Shared default-off Linux mainline RC contribution-acceleration policy.

The evidence source is a hash-bound bundle extracted from the official
``git.kernel.org`` Torvalds repository.  Only cryptographically verified,
annotated RC tags are admitted.  Each RC interval starts at the immediately
preceding signed mainline tag and contains non-merge commits only.  Issuer
attribution uses the commit object's raw author email, an exact lowercase
domain match, and a frozen effective-dated map; ``.mailmap`` and fuzzy suffix
matching are deliberately forbidden.

Historical replay and the daily paper snapshot share the same selector.  The
module never enables trading or creates an executable order.
"""

from __future__ import annotations

import hashlib
import gzip
import json
import math
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT, atomic_write_text
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT, atomic_write_text
    from quant.fill_model import (
        SLIPPAGE_BPS_ENTRY,
        SLIPPAGE_BPS_TARGET,
        apply_slippage,
    )


SLEEVE_NAME = "LINUX_MAINLINE_RC_CONTRIBUTION_ACCELERATION_PAPER"
RULE_VERSION = "linux_mainline_signed_rc_contribution_top3_nextopen_h20_shared_v1"
SOURCE_RULE_VERSION = "linux_signed_annotated_rc_exact_raw_domain_prior8_v1"
SOURCE_BUNDLE_SCHEMA = "linux_mainline_rc_source_bundle_v1"
STATE_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = "linux_mainline_rc_default_off_snapshot_v1"

PAPER_NOTIONAL_USD = 4_000.0
HOLD_SESSIONS = 20
MAX_RC_CANDIDATES = 3
MAX_ACTIVE_POSITIONS = 6
MIN_CURRENT_CONTRIBUTION_COUNT = 3
PRIOR_RC_INTERVALS = 8
# Public alias used by experiment runners and artifacts.
PRIOR_RC_COUNT = PRIOR_RC_INTERVALS
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5
TRADE_ENABLED = False

DEFAULT_SOURCE_BUNDLE_DIR = (
    DATA_ROOT / "non_ohlcv" / "linux_mainline_rc_contribution_acceleration"
)
DEFAULT_STATE_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "linux_mainline_rc_contribution_acceleration"
    / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "linux_mainline_rc_contribution_acceleration"
    / "snapshots.jsonl"
)

TAG_FILE_NAME = "rc_tags.jsonl"
COMMIT_FILE_NAME = "mapped_nonmerge_commits.jsonl.gz"
CROSSCHECK_FILE_NAME = "github_crosscheck.json"
MANIFEST_FILE_NAME = "source_bundle_manifest.json"
OFFICIAL_REMOTE_URL = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git"
GITHUB_CROSSCHECK_URL = "https://github.com/torvalds/linux.git"
MAP_EFFECTIVE_FROM = "2024-01-01"
SIGNING_KEY_FINGERPRINT = "ABAF11C65A2970B130ABE3C479BE3E4300411886"
SIGNATURE_PROVENANCE_URL = "https://www.kernel.org/signature.html"
AUDITED_FIRST_RC_TAG = "v6.8-rc1"
AUDITED_LAST_RC_TAG = "v7.2-rc3"
AUDITED_RC_TAG_COUNT = 102
AUDITED_ENDPOINT_COUNT = 117


# Frozen before any price replay.  Keys are exact lowercase domains extracted
# from raw author emails.  Parent acquisitions predate the covered event
# horizon and are retained as explicit provenance, not inferred dynamically.
DOMAIN_TO_ISSUER: dict[str, dict[str, str]] = {
    "amd.com": {"ticker": "AMD", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "amazon.com": {"ticker": "AMZN", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "google.com": {"ticker": "GOOG", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "linux.ibm.com": {"ticker": "IBM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "ibm.com": {"ticker": "IBM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "redhat.com": {"ticker": "IBM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "IBM acquired Red Hat 2019-07-09"},
    "intel.com": {"ticker": "INTC", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "linux.intel.com": {"ticker": "INTC", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "linutronix.de": {"ticker": "INTC", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "Intel acquired Linutronix 2022-02"},
    "linux.microsoft.com": {"ticker": "MSFT", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "microsoft.com": {"ticker": "MSFT", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "nvidia.com": {"ticker": "NVDA", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "oracle.com": {"ticker": "ORCL", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "oss.qualcomm.com": {"ticker": "QCOM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "quicinc.com": {"ticker": "QCOM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "qualcomm.com": {"ticker": "QCOM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "meta.com": {"ticker": "META", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "fb.com": {"ticker": "META", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "linux.alibaba.com": {"ticker": "BABA", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "broadcom.com": {"ticker": "AVGO", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "vmware.com": {"ticker": "AVGO", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "Broadcom acquired VMware 2023-11-22"},
    "ti.com": {"ticker": "TXN", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "nxp.com": {"ticker": "NXPI", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "oss.nxp.com": {"ticker": "NXPI", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "microchip.com": {"ticker": "MCHP", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "analog.com": {"ticker": "ADI", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "opensource.cirrus.com": {"ticker": "CRUS", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "cirrus.com": {"ticker": "CRUS", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "marvell.com": {"ticker": "MRVL", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "purestorage.com": {"ticker": "PSTG", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "wdc.com": {"ticker": "WDC", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "cisco.com": {"ticker": "CSCO", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "arm.com": {"ticker": "ARM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "st.com": {"ticker": "STM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "foss.st.com": {"ticker": "STM", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "micron.com": {"ticker": "MU", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "synopsys.com": {"ticker": "SNPS", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "cadence.com": {"ticker": "CDNS", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "apple.com": {"ticker": "AAPL", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "dell.com": {"ticker": "DELL", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "hpe.com": {"ticker": "HPE", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "netapp.com": {"ticker": "NTAP", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "nokia.com": {"ticker": "NOK", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "ericsson.com": {"ticker": "ERIC", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
    "cloudflare.com": {"ticker": "NET", "effective_from": MAP_EFFECTIVE_FROM, "provenance": "first_party"},
}


class LinuxMainlineRCContractError(ValueError):
    """Raised when source, mapping, market, or point-in-time identity conflicts."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _payload_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _date10(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as error:
        raise LinuxMainlineRCContractError(f"invalid date: {value!r}") from error


def _utc_datetime(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    else:
        text = str(value or "").strip()
        if not text:
            raise LinuxMainlineRCContractError(f"{field} missing")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as error:
            raise LinuxMainlineRCContractError(
                f"invalid {field}: {value!r}"
            ) from error
    if parsed.tzinfo is None:
        raise LinuxMainlineRCContractError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical_timestamp(value: Any, *, field: str) -> str:
    return _utc_datetime(value, field=field).isoformat().replace("+00:00", "Z")


def _raw_email_domain(email: Any) -> str:
    text = str(email or "").strip()
    if text.count("@") != 1:
        raise LinuxMainlineRCContractError(f"invalid raw author email: {email!r}")
    local, domain = text.rsplit("@", 1)
    if not local or not domain or domain != domain.lower():
        raise LinuxMainlineRCContractError(
            f"raw author email domain must already be lowercase: {email!r}"
        )
    return domain


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    opener = gzip.open if path.suffix == ".gz" else Path.open
    if path.suffix == ".gz":
        handle_context = opener(path, "rt", encoding="utf-8")
    else:
        handle_context = opener(path, "r", encoding="utf-8")
    with handle_context as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as error:
                raise LinuxMainlineRCContractError(
                    f"invalid JSONL {path.name}:{line_number}"
                ) from error
            if not isinstance(row, dict):
                raise LinuxMainlineRCContractError(
                    f"non-object JSONL {path.name}:{line_number}"
                )
            rows.append(row)
    return rows


def _atomic_write_bytes(payload: bytes, path: Path) -> None:
    """Atomically replace one generated binary bundle member."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def load_linux_mainline_rc_source_bundle(
    bundle_dir: Path | str = DEFAULT_SOURCE_BUNDLE_DIR,
    *,
    verify_hashes: bool = True,
) -> dict[str, Any]:
    """Load and verify the immutable source bundle before returning any rows."""

    root = Path(bundle_dir)
    manifest_path = root / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        raise LinuxMainlineRCContractError(f"source manifest missing: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or manifest.get("schema") != SOURCE_BUNDLE_SCHEMA:
        raise LinuxMainlineRCContractError("unexpected source bundle schema")
    if manifest.get("official_remote_url") != OFFICIAL_REMOTE_URL:
        raise LinuxMainlineRCContractError("official remote identity mismatch")
    if manifest.get("mapping_sha256") != _payload_sha256(DOMAIN_TO_ISSUER):
        raise LinuxMainlineRCContractError("frozen domain map hash mismatch")
    signature_audit = manifest.get("signature_audit")
    if (
        manifest.get("tag_signature_verification_passed") is not True
        or not isinstance(signature_audit, Mapping)
        or signature_audit.get("selected_rc_tag_count") != AUDITED_RC_TAG_COUNT
        or signature_audit.get("verified_endpoint_count") != AUDITED_ENDPOINT_COUNT
        or signature_audit.get("count") != AUDITED_ENDPOINT_COUNT
        or signature_audit.get("good") != AUDITED_ENDPOINT_COUNT
        or signature_audit.get("exit_code") != 0
        or signature_audit.get("key_fingerprint") != SIGNING_KEY_FINGERPRINT
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(signature_audit.get("verification_output_sha256") or ""),
        )
    ):
        raise LinuxMainlineRCContractError("102-tag official signature audit incomplete")
    if manifest.get("effective_dated_mapping_pit_audit_passed") is not True:
        raise LinuxMainlineRCContractError("effective-dated mapping/PIT audit incomplete")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise LinuxMainlineRCContractError("source manifest files missing")
    for name in (TAG_FILE_NAME, COMMIT_FILE_NAME, CROSSCHECK_FILE_NAME):
        path = root / name
        expected = files.get(name)
        if not path.exists() or not isinstance(expected, Mapping):
            raise LinuxMainlineRCContractError(f"source bundle file missing: {name}")
        if verify_hashes and _file_sha256(path) != expected.get("sha256"):
            raise LinuxMainlineRCContractError(f"source bundle hash mismatch: {name}")
    commit_meta = files[COMMIT_FILE_NAME]
    if (
        commit_meta.get("compression") != "gzip"
        or commit_meta.get("gzip_mtime") != 0
    ):
        raise LinuxMainlineRCContractError("commit bundle compression contract mismatch")
    if verify_hashes:
        decompressed_digest = hashlib.sha256()
        decompressed_bytes = 0
        with gzip.open(root / COMMIT_FILE_NAME, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                decompressed_digest.update(chunk)
                decompressed_bytes += len(chunk)
        if (
            decompressed_digest.hexdigest() != commit_meta.get("uncompressed_sha256")
            or decompressed_bytes != commit_meta.get("uncompressed_bytes")
        ):
            raise LinuxMainlineRCContractError("decompressed commit bundle hash mismatch")
    manifest_projection = {
        key: value
        for key, value in manifest.items()
        if key not in {"bundle_sha256", "generated_at"}
    }
    if verify_hashes and manifest.get("bundle_sha256") != _payload_sha256(
        manifest_projection
    ):
        raise LinuxMainlineRCContractError("source manifest self-hash mismatch")

    tags = _jsonl_rows(root / TAG_FILE_NAME)
    commits = _jsonl_rows(root / COMMIT_FILE_NAME)
    with (root / CROSSCHECK_FILE_NAME).open("r", encoding="utf-8") as handle:
        crosscheck = json.load(handle)
    if len(tags) != int(files[TAG_FILE_NAME].get("rows", -1)):
        raise LinuxMainlineRCContractError("RC tag row count mismatch")
    normalise_linux_mainline_rc_tag_rows(tags, require_frozen_sequence=True)
    if len(commits) != int(files[COMMIT_FILE_NAME].get("rows", -1)):
        raise LinuxMainlineRCContractError("commit row count mismatch")
    if (
        not isinstance(crosscheck, Mapping)
        or not crosscheck.get("all_tags_match")
        or int(crosscheck.get("mismatch_count", -1)) != 0
        or int(crosscheck.get("overlap_count", -1)) <= 0
    ):
        raise LinuxMainlineRCContractError("GitHub object cross-check incomplete")
    return {"manifest": manifest, "tags": tags, "commit_rows": commits, "crosscheck": crosscheck}


def normalise_linux_mainline_rc_tag_rows(
    rc_tag_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any | None = None,
    require_frozen_sequence: bool = True,
) -> list[dict[str, Any]]:
    """Validate the authoritative complete signed-RC sequence."""

    as_of_date = _date10(as_of) if as_of is not None else None
    by_name: dict[str, dict[str, Any]] = {}
    raw_rows = list(rc_tag_rows or [])
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("tag_name") or "")
        if not re.fullmatch(r"v\d+\.\d+-rc\d+", name):
            raise LinuxMainlineRCContractError(f"invalid RC tag name: {name!r}")
        if raw.get("tag_object_type") != "tag" or raw.get("signature_verified") is not True:
            raise LinuxMainlineRCContractError(f"unverified annotated tag: {name}")
        object_sha = str(raw.get("tag_object_sha") or "")
        commit_sha = str(raw.get("tag_commit_sha") or raw.get("peeled_commit_sha") or "")
        prior_name = str(raw.get("prior_tag_name") or "")
        prior_object = str(raw.get("prior_tag_object_sha") or "")
        prior_commit = str(raw.get("prior_tag_commit_sha") or "")
        if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (object_sha, commit_sha, prior_object, prior_commit)):
            raise LinuxMainlineRCContractError(f"invalid tag object identity: {name}")
        if not re.fullmatch(r"v\d+\.\d+(?:-rc\d+)?", prior_name):
            raise LinuxMainlineRCContractError(f"invalid prior mainline tag: {prior_name}")
        tagger_at = _canonical_timestamp(raw.get("tagger_at"), field="tagger_at")
        canonical = {
            "tag_name": name,
            "tag_object_type": "tag",
            "tag_object_sha": object_sha,
            "tag_commit_sha": commit_sha,
            "peeled_commit_sha": commit_sha,
            "tagger_at": tagger_at,
            "signal_date": tagger_at[:10],
            "signature_verified": True,
            "prior_tag_name": prior_name,
            "prior_tag_object_sha": prior_object,
            "prior_tag_commit_sha": prior_commit,
            "source_rule_version": SOURCE_RULE_VERSION,
        }
        prior = by_name.get(name)
        if prior is not None and prior != canonical:
            raise LinuxMainlineRCContractError(f"moved tag conflict: {name}")
        by_name[name] = canonical
    complete = sorted(by_name.values(), key=lambda row: (row["tagger_at"], row["tag_name"]))
    if len(raw_rows) != len(complete):
        raise LinuxMainlineRCContractError("duplicate RC tag row in authoritative sequence")
    for prior, current in zip(complete, complete[1:]):
        if current["tagger_at"] <= prior["tagger_at"]:
            raise LinuxMainlineRCContractError("RC tagger timestamps are not strictly increasing")
    for row in complete:
        match = re.fullmatch(r"(v\d+\.\d+)-rc(\d+)", row["tag_name"])
        assert match is not None
        rc_number = int(match.group(2))
        expected_prior = f"{match.group(1)}-rc{rc_number - 1}"
        if rc_number > 1 and row["prior_tag_name"] != expected_prior:
            raise LinuxMainlineRCContractError(
                f"RC predecessor discontinuity: {row['tag_name']} expected {expected_prior}"
            )
        if rc_number > 1:
            prior_row = by_name.get(expected_prior)
            if prior_row is None:
                raise LinuxMainlineRCContractError(
                    f"RC predecessor discontinuity: {row['tag_name']} missing {expected_prior}"
                )
            if (
                row["prior_tag_object_sha"] != prior_row["tag_object_sha"]
                or row["prior_tag_commit_sha"] != prior_row["tag_commit_sha"]
            ):
                raise LinuxMainlineRCContractError(
                    f"RC predecessor object mismatch: {row['tag_name']}"
                )
        if rc_number == 1 and not re.fullmatch(r"v\d+\.\d+", row["prior_tag_name"]):
            raise LinuxMainlineRCContractError(
                f"rc1 prior endpoint is not a final mainline tag: {row['tag_name']}"
            )
    if require_frozen_sequence and (
        len(complete) != AUDITED_RC_TAG_COUNT
        or not complete
        or complete[0]["tag_name"] != AUDITED_FIRST_RC_TAG
        or complete[-1]["tag_name"] != AUDITED_LAST_RC_TAG
    ):
        raise LinuxMainlineRCContractError(
            "authoritative frozen RC sequence is incomplete"
        )
    if as_of_date is not None:
        complete = [row for row in complete if row["signal_date"] <= as_of_date]
    return complete


def normalise_linux_mainline_rc_contribution_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any | None = None,
) -> list[dict[str, Any]]:
    """Validate exact raw-email mapped commit rows and fail on identity conflict."""

    as_of_date = _date10(as_of) if as_of is not None else None
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    tag_identity: dict[str, tuple[str, str]] = {}
    for raw in source_rows or []:
        if not isinstance(raw, Mapping):
            continue
        tag_name = str(raw.get("tag_name") or "")
        if not re.fullmatch(r"v\d+\.\d+-rc\d+", tag_name):
            raise LinuxMainlineRCContractError(f"invalid RC tag name: {tag_name!r}")
        if raw.get("tag_object_type") != "tag" or raw.get("signature_verified") is not True:
            raise LinuxMainlineRCContractError(f"unverified annotated tag: {tag_name}")
        tag_object_sha = str(raw.get("tag_object_sha") or "")
        tag_commit_sha = str(raw.get("tag_commit_sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", tag_object_sha) or not re.fullmatch(
            r"[0-9a-f]{40}", tag_commit_sha
        ):
            raise LinuxMainlineRCContractError(f"invalid tag object identity: {tag_name}")
        prior_tag_name = str(raw.get("prior_tag_name") or "")
        prior_tag_object_sha = str(raw.get("prior_tag_object_sha") or "")
        prior_tag_commit_sha = str(raw.get("prior_tag_commit_sha") or "")
        if not re.fullmatch(r"v\d+\.\d+(?:-rc\d+)?", prior_tag_name):
            raise LinuxMainlineRCContractError(f"invalid prior mainline tag: {prior_tag_name}")
        if not re.fullmatch(r"[0-9a-f]{40}", prior_tag_object_sha) or not re.fullmatch(
            r"[0-9a-f]{40}", prior_tag_commit_sha
        ):
            raise LinuxMainlineRCContractError(f"invalid prior tag identity: {tag_name}")
        identity = (tag_object_sha, tag_commit_sha)
        prior_identity = tag_identity.get(tag_name)
        if prior_identity is not None and prior_identity != identity:
            raise LinuxMainlineRCContractError(f"moved tag conflict: {tag_name}")
        tag_identity[tag_name] = identity
        tagger_at = _canonical_timestamp(raw.get("tagger_at"), field="tagger_at")
        signal_date = tagger_at[:10]
        if as_of_date is not None and signal_date > as_of_date:
            continue
        commit_sha = str(raw.get("commit_sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise LinuxMainlineRCContractError(f"invalid commit SHA: {commit_sha!r}")
        author_email = str(raw.get("author_email") or "").strip()
        author_domain = _raw_email_domain(author_email)
        if author_domain != raw.get("author_domain"):
            raise LinuxMainlineRCContractError("raw email/domain disagreement")
        mapping = DOMAIN_TO_ISSUER.get(author_domain)
        if mapping is None:
            raise LinuxMainlineRCContractError(f"unmapped bundled domain: {author_domain}")
        if signal_date < mapping["effective_from"]:
            continue
        ticker = str(raw.get("ticker") or "")
        if ticker != mapping["ticker"]:
            raise LinuxMainlineRCContractError(
                f"mapping ambiguity for {author_domain}: {ticker} != {mapping['ticker']}"
            )
        authored_at = _canonical_timestamp(raw.get("authored_at"), field="authored_at")
        committed_at = _canonical_timestamp(raw.get("committed_at"), field="committed_at")
        if raw.get("parent_count") != 1:
            raise LinuxMainlineRCContractError(f"merge/root commit rejected: {commit_sha}")
        if _utc_datetime(committed_at, field="committed_at") > _utc_datetime(
            tagger_at, field="tagger_at"
        ):
            raise LinuxMainlineRCContractError(
                f"future-visible commit in {tag_name}: {commit_sha}"
            )
        canonical = {
            "tag_name": tag_name,
            "tag_object_type": "tag",
            "tag_object_sha": tag_object_sha,
            "tag_commit_sha": tag_commit_sha,
            "tagger_at": tagger_at,
            "signal_date": signal_date,
            "signature_verified": True,
            "prior_tag_name": prior_tag_name,
            "prior_tag_object_sha": prior_tag_object_sha,
            "prior_tag_commit_sha": prior_tag_commit_sha,
            "commit_sha": commit_sha,
            "parent_count": 1,
            "author_email": author_email,
            "author_domain": author_domain,
            "authored_at": authored_at,
            "committed_at": committed_at,
            "ticker": ticker,
            "mapping_effective_from": mapping["effective_from"],
            "mapping_provenance": mapping["provenance"],
            "source_rule_version": SOURCE_RULE_VERSION,
        }
        canonical["source_record_sha256"] = _payload_sha256(canonical)
        key = (tag_name, commit_sha)
        prior = by_key.get(key)
        if prior is not None and prior != canonical:
            raise LinuxMainlineRCContractError(
                f"natural-key conflict for {tag_name}:{commit_sha}"
            )
        by_key[key] = canonical
    return sorted(by_key.values(), key=lambda row: (row["tagger_at"], row["tag_name"], row["commit_sha"]))


def evaluate_linux_mainline_rc_contribution_acceleration_decisions(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    rc_tag_rows: Iterable[Mapping[str, Any]],
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    require_frozen_sequence: bool = True,
) -> dict[str, Any]:
    """Apply the prior-eight-RC median and deterministic Top3 policy."""

    canonical = normalise_linux_mainline_rc_contribution_rows(source_rows, as_of=as_of)
    as_of_date = _date10(as_of)
    start_date = _date10(start) if start is not None else None
    end_date = _date10(end) if end is not None else None

    ordered_tags = normalise_linux_mainline_rc_tag_rows(
        rc_tag_rows,
        as_of=as_of,
        require_frozen_sequence=require_frozen_sequence,
    )
    tag_meta = {row["tag_name"]: row for row in ordered_tags}
    counts: Counter[tuple[str, str]] = Counter()
    commit_ids: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for row in canonical:
        tag_name = row["tag_name"]
        prior_meta = tag_meta.get(tag_name)
        if prior_meta is None:
            raise LinuxMainlineRCContractError(f"commit references absent RC tag: {tag_name}")
        for field in ("tag_object_sha", "tag_commit_sha", "tagger_at", "prior_tag_name", "prior_tag_object_sha", "prior_tag_commit_sha"):
            if row[field] != prior_meta[field]:
                raise LinuxMainlineRCContractError(f"tag metadata conflict: {tag_name}:{field}")
        key = (tag_name, row["ticker"])
        counts[key] += 1
        commit_ids[key].append(row["commit_sha"])

    eligible_rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for tag_index, tag in enumerate(ordered_tags):
        signal_date = tag["signal_date"]
        if signal_date > as_of_date:
            continue
        if start_date is not None and signal_date < start_date:
            continue
        if end_date is not None and signal_date > end_date:
            continue
        if tag_index < PRIOR_RC_INTERVALS:
            continue
        prior_tags = ordered_tags[tag_index - PRIOR_RC_INTERVALS : tag_index]
        tickers = sorted({ticker for (name, ticker) in counts if name == tag["tag_name"]})
        ranked: list[dict[str, Any]] = []
        for ticker in tickers:
            current_count = counts[(tag["tag_name"], ticker)]
            prior_counts = [counts[(prior["tag_name"], ticker)] for prior in prior_tags]
            prior_median = float(median(prior_counts))
            acceleration = float(current_count) - prior_median
            if current_count < MIN_CURRENT_CONTRIBUTION_COUNT or acceleration <= 0.0:
                continue
            ranked.append({
                **tag,
                "ticker": ticker,
                "current_contribution_count": int(current_count),
                "prior_eight_rc_tags": [row["tag_name"] for row in prior_tags],
                "prior_eight_rc_counts": [int(value) for value in prior_counts],
                "prior_eight_rc_median": round(prior_median, 8),
                "contribution_acceleration": round(acceleration, 8),
                "commit_shas": sorted(commit_ids[(tag["tag_name"], ticker)]),
                "source_rule_version": SOURCE_RULE_VERSION,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
            })
        ranked.sort(key=lambda row: (-float(row["contribution_acceleration"]), -int(row["current_contribution_count"]), str(row["ticker"])))
        for rank, row in enumerate(ranked, start=1):
            decision = {
                **row,
                "rc_rank": rank,
                "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{row['tag_name']}:{row['ticker']}",
                "selected": rank <= MAX_RC_CANDIDATES,
            }
            eligible_rows.append(decision)
            if decision["selected"]:
                selected.append(decision)
    return {
        "eligible_rows": eligible_rows,
        "decisions": selected,
        "signals_generated": len(eligible_rows),
        "signals_survived": len(selected),
        "survival_rate": round(len(selected) / len(eligible_rows), 6) if eligible_rows else 0.0,
        "normalised_commit_count": len(canonical),
        "rc_interval_count": len(ordered_tags),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
    }


def select_linux_mainline_rc_contribution_acceleration_decisions(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    rc_tag_rows: Iterable[Mapping[str, Any]],
    as_of: Any,
    start: Any | None = None,
    end: Any | None = None,
    require_frozen_sequence: bool = True,
) -> list[dict[str, Any]]:
    return evaluate_linux_mainline_rc_contribution_acceleration_decisions(
        source_rows,
        rc_tag_rows=rc_tag_rows,
        as_of=as_of,
        start=start,
        end=end,
        require_frozen_sequence=require_frozen_sequence,
    )["decisions"]


def _normalise_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        try:
            day = _date10(raw.get("date") or raw.get("Date"))
        except LinuxMainlineRCContractError:
            continue
        if date.fromisoformat(day).weekday() >= 5:
            continue
        values: dict[str, float] = {}
        valid = True
        for field in ("open", "high", "low", "close"):
            value = raw.get(field) if field in raw else raw.get(field.title())
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                valid = False
                break
            if not math.isfinite(parsed) or parsed <= 0.0:
                valid = False
                break
            values[field] = parsed
        if not valid or values["high"] < values["low"]:
            continue
        row = {"date": day, **values}
        prior = by_date.get(day)
        if prior is not None and prior != row:
            raise LinuxMainlineRCContractError(f"conflicting OHLCV date: {day}")
        by_date[day] = row
    return [by_date[day] for day in sorted(by_date)]


def _normalise_trading_dates(values: Iterable[Any]) -> list[str]:
    output: set[str] = set()
    for raw in values or []:
        value = raw
        if isinstance(raw, Mapping):
            if raw.get("is_regular_session") is False:
                continue
            session_type = str(raw.get("session_type") or "").strip().lower()
            if session_type and session_type not in {"regular", "regular_session"}:
                continue
            value = raw.get("date") or raw.get("session_date")
        day = _date10(value)
        if date.fromisoformat(day).weekday() >= 5:
            raise LinuxMainlineRCContractError(f"weekend cannot be a regular session: {day}")
        output.add(day)
    return sorted(output)


def _prepare_market_inputs(
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    trading_dates: Iterable[Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    bars = {str(ticker).upper(): _normalise_bars(rows) for ticker, rows in (ohlcv_by_ticker or {}).items()}
    if trading_dates is not None:
        calendar = _normalise_trading_dates(trading_dates)
    elif bars.get("SPY"):
        calendar = [row["date"] for row in bars["SPY"]]
    else:
        calendar = sorted({row["date"] for rows in bars.values() for row in rows})
    return bars, calendar


def _atr14_before_entry(rows: Sequence[Mapping[str, Any]], entry_date: str) -> float | None:
    prior = [row for row in rows if str(row["date"]) < entry_date]
    if len(prior) < ATR_PERIOD:
        return None
    sample = prior[-ATR_PERIOD:]
    index_by_date = {str(row["date"]): index for index, row in enumerate(rows)}
    true_ranges: list[float] = []
    for row in sample:
        index = index_by_date[str(row["date"])]
        previous_close = float(rows[index - 1]["close"]) if index > 0 else float(row["close"])
        true_ranges.append(max(float(row["high"]) - float(row["low"]), abs(float(row["high"]) - previous_close), abs(float(row["low"]) - previous_close)))
    atr = sum(true_ranges) / len(true_ranges)
    return atr if math.isfinite(atr) and atr > 0.0 else None


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "production_signal_path_changed": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def build_linux_mainline_rc_contribution_acceleration_historical_trades(
    *,
    source_rows: Iterable[Mapping[str, Any]],
    rc_tag_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: Any,
    end: Any,
    as_of: Any | None = None,
    trading_dates: Iterable[Any] | None = None,
    require_frozen_sequence: bool = True,
) -> dict[str, Any]:
    """Replay fixed Top3 RC decisions at the first strictly later open."""

    start_iso, end_iso = _date10(start), _date10(end)
    as_of_iso = _date10(as_of or end_iso)
    if start_iso > end_iso:
        raise LinuxMainlineRCContractError("start is after end")
    evaluation = evaluate_linux_mainline_rc_contribution_acceleration_decisions(
        source_rows,
        rc_tag_rows=rc_tag_rows,
        as_of=as_of_iso,
        require_frozen_sequence=require_frozen_sequence,
    )
    bars, calendar = _prepare_market_inputs(ohlcv_by_ticker, trading_dates)
    calendar_index = {day: index for index, day in enumerate(calendar)}
    bars_by_ticker_date = {ticker: {row["date"]: row for row in rows} for ticker, rows in bars.items()}
    rejects: Counter[str] = Counter()
    window_decisions: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    accepted_intervals: list[dict[str, Any]] = []

    for decision in sorted(evaluation["decisions"], key=lambda row: (row["tagger_at"], row["rc_rank"], row["ticker"])):
        entry_date = next((day for day in calendar if day > decision["signal_date"]), None)
        if entry_date is None:
            rejects["next_regular_session_unavailable"] += 1
            continue
        if entry_date < start_iso or entry_date > end_iso:
            continue
        window_decisions.append(decision)
        entry_index = calendar_index[entry_date]
        ticker = decision["ticker"]
        if any(row["ticker"] == ticker and row["entry_index"] <= entry_index and (row["exit_index"] is None or row["exit_index"] >= entry_index) for row in accepted_intervals):
            rejects["same_ticker_active"] += 1
            continue
        active_count = sum(row["entry_index"] <= entry_index and (row["exit_index"] is None or row["exit_index"] >= entry_index) for row in accepted_intervals)
        if active_count >= MAX_ACTIVE_POSITIONS:
            rejects["max_active_positions"] += 1
            continue
        ticker_rows = bars.get(ticker) or []
        entry_row = bars_by_ticker_date.get(ticker, {}).get(entry_date)
        if entry_row is None:
            rejects["missing_exact_entry_open"] += 1
            continue
        atr14 = _atr14_before_entry(ticker_rows, entry_date)
        if atr14 is None:
            rejects["missing_prior_atr14"] += 1
            continue
        raw_entry_open = float(entry_row["open"])
        entry_price = float(apply_slippage(raw_entry_open, SLIPPAGE_BPS_ENTRY, "buy", notional=PAPER_NOTIONAL_USD))
        exit_index = entry_index + HOLD_SESSIONS - 1
        planned_exit_date = calendar[exit_index] if exit_index < len(calendar) else None
        candidate = {
            **decision,
            "entry_date": entry_date,
            "entry_open_price_raw": round(raw_entry_open, 4),
            "entry_price": round(entry_price, 4),
            "atr14_as_of_entry": round(atr14, 8),
            "target_price": round(entry_price + ATR_TARGET_MULTIPLE * atr14, 4),
            "target_price_role": "3.5x_atr14_signal_contract_sentinel_not_exit_driver",
            "planned_exit_date": planned_exit_date,
            "hold_sessions": HOLD_SESSIONS,
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "trade_enabled": False,
            "alters_orders": False,
        }
        candidates.append(candidate)
        accepted_intervals.append({"ticker": ticker, "entry_index": entry_index, "exit_index": exit_index if planned_exit_date else None})
        if planned_exit_date is None or planned_exit_date > end_iso:
            unsettled.append({**candidate, "unsettled_reason": "incomplete_20_session_horizon"})
            continue
        exit_row = bars_by_ticker_date.get(ticker, {}).get(planned_exit_date)
        if exit_row is None:
            unsettled.append({**candidate, "unsettled_reason": "missing_exact_exit_close"})
            continue
        raw_exit_close = float(exit_row["close"])
        exit_price = float(apply_slippage(raw_exit_close, SLIPPAGE_BPS_TARGET, "sell", notional=PAPER_NOTIONAL_USD))
        gross = exit_price / entry_price - 1.0
        net = gross - ROUND_TRIP_COST_PCT
        trades.append({
            **candidate,
            "exit_date": planned_exit_date,
            "exit_close_price_raw": round(raw_exit_close, 4),
            "exit_price": round(exit_price, 4),
            "hold_sessions_realized": HOLD_SESSIONS,
            "exit_reason": "scheduled_20_session_horizon_close",
            "pnl_pct_gross": round(gross, 10),
            "pnl_pct_net": round(net, 10),
            "net_return": round(net, 10),
            "pnl": round(PAPER_NOTIONAL_USD * net, 2),
        })

    window_eligible = []
    for row in evaluation["eligible_rows"]:
        entry_date = next((day for day in calendar if day > row["signal_date"]), None)
        if entry_date is not None and start_iso <= entry_date <= end_iso:
            window_eligible.append(row)
    generated = len(window_eligible)
    return {
        "schema": "linux_mainline_rc_contribution_acceleration_historical_replay_v1",
        "start": start_iso,
        "end": end_iso,
        "as_of": as_of_iso,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "paper_notional_usd": PAPER_NOTIONAL_USD,
        "rc_decisions": evaluation["decisions"],
        "eligible_rc_rows": evaluation["eligible_rows"],
        "window_eligible_rows": window_eligible,
        "window_decisions": window_decisions,
        "trade_candidates": candidates,
        "trades": trades,
        "unsettled": unsettled,
        "reject_totals": dict(sorted(rejects.items())),
        "normalised_commit_count": evaluation["normalised_commit_count"],
        "rc_interval_count": evaluation["rc_interval_count"],
        "signals_generated": generated,
        "signals_survived": len(candidates),
        "survival_rate": round(len(candidates) / generated, 6) if generated else 0.0,
        "production_impact": _production_impact(),
    }


def empty_linux_mainline_rc_contribution_acceleration_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "processed_decision_ids": [],
    }


def load_linux_mainline_rc_contribution_acceleration_state(path: Path | str = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_linux_mainline_rc_contribution_acceleration_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_linux_mainline_rc_contribution_acceleration_state()
    if isinstance(payload, Mapping):
        state.update(payload)
    return state


def save_linux_mainline_rc_contribution_acceleration_state(state: dict[str, Any], path: Path | str = DEFAULT_STATE_PATH) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now_iso()
    atomic_write_text(json.dumps(state, indent=2, sort_keys=True, default=str) + "\n", state_path)


def append_linux_mainline_rc_contribution_acceleration_snapshot(snapshot: Mapping[str, Any], path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")


def build_linux_mainline_rc_contribution_acceleration_snapshot(
    *,
    source_rows: Iterable[Mapping[str, Any]],
    rc_tag_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    as_of: Any,
    start: Any | None = None,
    trading_dates: Iterable[Any] | None = None,
    state: dict[str, Any] | None = None,
    persist: bool = False,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
    require_frozen_sequence: bool = True,
) -> dict[str, Any]:
    """Build one deterministic daily default-off snapshot from shared policy."""

    as_of_iso = _date10(as_of)
    start_iso = _date10(start or MAP_EFFECTIVE_FROM)
    bounded_rows = normalise_linux_mainline_rc_contribution_rows(source_rows, as_of=as_of_iso)
    bounded_bars = {ticker: [row for row in rows if _date10(row.get("date") or row.get("Date")) <= as_of_iso] for ticker, rows in (ohlcv_by_ticker or {}).items()}
    bounded_calendar = None
    if trading_dates is not None:
        bounded_calendar = [raw for raw in trading_dates if _date10((raw.get("date") or raw.get("session_date")) if isinstance(raw, Mapping) else raw) <= as_of_iso]
    replay = build_linux_mainline_rc_contribution_acceleration_historical_trades(
        source_rows=bounded_rows,
        rc_tag_rows=rc_tag_rows,
        ohlcv_by_ticker=bounded_bars,
        start=start_iso,
        end=as_of_iso,
        as_of=as_of_iso,
        trading_dates=bounded_calendar,
        require_frozen_sequence=require_frozen_sequence,
    )
    working_state = deepcopy(state if state is not None else (load_linux_mainline_rc_contribution_acceleration_state(state_path) if persist else empty_linux_mainline_rc_contribution_acceleration_state()))
    closed_by_id = {str(row.get("decision_id")): row for row in working_state.get("closed_positions") or [] if row.get("decision_id")}
    closed_by_id.update({row["decision_id"]: row for row in replay["trades"]})
    open_positions = [row for row in replay["trade_candidates"] if row["decision_id"] not in closed_by_id and row["entry_date"] <= as_of_iso]
    working_state.update({
        "updated_at": _utc_now_iso(),
        "pending_entries": [],
        "open_positions": open_positions,
        "closed_positions": sorted(closed_by_id.values(), key=lambda row: (row.get("exit_date") or "", row["decision_id"])),
        "processed_decision_ids": sorted({*working_state.get("processed_decision_ids", []), *(row["decision_id"] for row in replay["trade_candidates"])}),
    })
    snapshot = {
        "schema": SNAPSHOT_SCHEMA_VERSION,
        "as_of": as_of_iso,
        "generated_at": _utc_now_iso(),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "execution_envelope": {
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "max_concurrent_positions": MAX_ACTIVE_POSITIONS,
            "one_active_position_per_ticker": True,
            "hold_sessions": HOLD_SESSIONS,
            "entry_order_semantics": "first_strictly_later_regular_session_open_paper_only",
            "exit_order_semantics": "twentieth_session_close_paper_only",
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "kill_switch": "trade_enabled_false",
            "failure_handling": "unverified_source_or_missing_exact_bar_or_atr_fails_closed",
        },
        "source_contract": {
            "signed_annotated_rc_tags_only": True,
            "immediate_prior_mainline_tag_interval": True,
            "non_merge_commits_only": True,
            "raw_author_email_exact_domain": True,
            "mailmap_forbidden": True,
            "mapping_sha256": _payload_sha256(DOMAIN_TO_ISSUER),
            "prior_rc_intervals": PRIOR_RC_INTERVALS,
            "minimum_current_count": MIN_CURRENT_CONTRIBUTION_COUNT,
        },
        "replay": replay,
        "state": working_state,
        "production_impact": _production_impact(),
    }
    snapshot["snapshot_sha256"] = _payload_sha256({key: value for key, value in snapshot.items() if key != "generated_at"})
    if persist:
        save_linux_mainline_rc_contribution_acceleration_state(working_state, state_path)
        append_linux_mainline_rc_contribution_acceleration_snapshot(snapshot, snapshot_log_path)
    return snapshot


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args]
    result = subprocess.run(command, text=True, encoding="utf-8", errors="strict", capture_output=True, check=False)
    if check and result.returncode != 0:
        raise LinuxMainlineRCContractError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def build_hash_bound_linux_mainline_rc_source_bundle(
    *,
    official_repo: Path | str,
    github_repo: Path | str,
    output_dir: Path | str = DEFAULT_SOURCE_BUNDLE_DIR,
    as_of: Any,
    earliest_rc_date: Any = MAP_EFFECTIVE_FROM,
) -> dict[str, Any]:
    """Extract a deterministic verified source bundle from two pinned clones."""

    official = Path(official_repo).resolve()
    github = Path(github_repo).resolve()
    output = Path(output_dir)
    as_of_iso = _date10(as_of)
    earliest_iso = _date10(earliest_rc_date)
    remote_lines = _git(official, "remote", "get-url", "origin").stdout.strip()
    if remote_lines != OFFICIAL_REMOTE_URL:
        raise LinuxMainlineRCContractError(f"unexpected official remote: {remote_lines}")
    github_remote = _git(github, "remote", "get-url", "origin").stdout.strip()
    if github_remote != GITHUB_CROSSCHECK_URL:
        raise LinuxMainlineRCContractError(f"unexpected GitHub remote: {github_remote}")
    fmt = "%(refname:short)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%(taggerdate:iso-strict)%00"
    raw = _git(official, "for-each-ref", "refs/tags", "--sort=taggerdate", f"--format={fmt}").stdout
    fields = raw.split("\x00")
    tags_all: list[dict[str, Any]] = []
    for index in range(0, len(fields) - 5, 5):
        name, object_type, object_sha, peeled_sha, tagger_at = (part.strip() for part in fields[index : index + 5])
        if not re.fullmatch(r"v\d+\.\d+(?:-rc\d+)?", name):
            continue
        canonical_tagger = _canonical_timestamp(tagger_at, field="tagger_at")
        tags_all.append({"tag_name": name, "tag_object_type": object_type, "tag_object_sha": object_sha, "tag_commit_sha": peeled_sha, "tagger_at": canonical_tagger})
    tags_all.sort(key=lambda row: (row["tagger_at"], row["tag_name"]))
    selected_tags = [
        row
        for row in tags_all
        if re.fullmatch(r"v\d+\.\d+-rc\d+", row["tag_name"])
        and earliest_iso <= row["tagger_at"][:10] <= as_of_iso
    ]
    if (
        len(selected_tags) != AUDITED_RC_TAG_COUNT
        or selected_tags[0]["tag_name"] != AUDITED_FIRST_RC_TAG
        or selected_tags[-1]["tag_name"] != AUDITED_LAST_RC_TAG
    ):
        raise LinuxMainlineRCContractError(
            "extracted RC set does not equal the required 102-tag audit scope"
        )
    tag_index_by_name = {
        row["tag_name"]: index for index, row in enumerate(tags_all)
    }
    verification_name_set = {row["tag_name"] for row in selected_tags}
    for row in selected_tags:
        index = tag_index_by_name[row["tag_name"]]
        if index == 0:
            raise LinuxMainlineRCContractError(
                f"prior mainline endpoint unavailable: {row['tag_name']}"
            )
        verification_name_set.add(tags_all[index - 1]["tag_name"])
    verification_tag_names = [
        row["tag_name"]
        for row in tags_all
        if row["tag_name"] in verification_name_set
    ]
    if len(verification_tag_names) != AUDITED_ENDPOINT_COUNT:
        raise LinuxMainlineRCContractError(
            "signature endpoint union is not the expected 117 tags"
        )
    # Bind the signature evidence to the exact refs materialized in this run.
    # The caller must provide an isolated GNUPGHOME containing the official WKD
    # key; there is intentionally no signature-present or hardcoded fallback.
    verification = _git(
        official,
        "verify-tag",
        "--raw",
        *verification_tag_names,
        check=False,
    )
    verification_output = verification.stdout + verification.stderr
    valid_fingerprints = re.findall(
        r"\[GNUPG:\]\s+VALIDSIG\s+([0-9A-F]+)", verification_output
    )
    good_signatures = re.findall(r"\[GNUPG:\]\s+GOODSIG\s+", verification_output)
    if (
        verification.returncode != 0
        or len(valid_fingerprints) != AUDITED_ENDPOINT_COUNT
        or len(good_signatures) != AUDITED_ENDPOINT_COUNT
        or any(value != SIGNING_KEY_FINGERPRINT for value in valid_fingerprints)
    ):
        raise LinuxMainlineRCContractError(
            "fresh 117-endpoint git verify-tag audit failed or used an unexpected key"
        )
    verification_output_sha256 = hashlib.sha256(
        verification_output.encode("utf-8")
    ).hexdigest()
    rc_tags: list[dict[str, Any]] = []
    commit_rows: list[dict[str, Any]] = []
    cross_rows: list[dict[str, Any]] = []
    for index, tag in enumerate(tags_all):
        if not re.fullmatch(r"v\d+\.\d+-rc\d+", tag["tag_name"]):
            continue
        signal_date = tag["tagger_at"][:10]
        if signal_date < earliest_iso or signal_date > as_of_iso:
            continue
        if index == 0:
            raise LinuxMainlineRCContractError(f"prior mainline tag unavailable: {tag['tag_name']}")
        prior = tags_all[index - 1]
        if tag["tag_object_type"] != "tag":
            raise LinuxMainlineRCContractError(f"lightweight RC tag rejected: {tag['tag_name']}")
        if prior["tag_object_type"] != "tag":
            raise LinuxMainlineRCContractError(
                f"lightweight prior mainline tag rejected: {prior['tag_name']}"
            )
        ancestry = _git(official, "merge-base", "--is-ancestor", prior["tag_commit_sha"], tag["tag_commit_sha"], check=False)
        if ancestry.returncode != 0:
            raise LinuxMainlineRCContractError(f"non-ancestral interval: {prior['tag_name']}..{tag['tag_name']}")
        current_official_object = _git(
            official, "rev-parse", "--verify", f"refs/tags/{tag['tag_name']}"
        ).stdout.strip()
        if current_official_object != tag["tag_object_sha"]:
            raise LinuxMainlineRCContractError(
                f"official tag moved during extraction: {tag['tag_name']}"
            )
        current_prior_object = _git(
            official, "rev-parse", "--verify", f"refs/tags/{prior['tag_name']}"
        ).stdout.strip()
        if current_prior_object != prior["tag_object_sha"]:
            raise LinuxMainlineRCContractError(
                f"official prior tag moved during extraction: {prior['tag_name']}"
            )
        github_object_result = _git(
            github, "rev-parse", "--verify", f"refs/tags/{tag['tag_name']}", check=False
        )
        github_commit_result = _git(
            github, "rev-parse", "--verify", f"refs/tags/{tag['tag_name']}^{{}}", check=False
        )
        mirror_present = (
            github_object_result.returncode == 0 and github_commit_result.returncode == 0
        )
        github_object = github_object_result.stdout.strip() if mirror_present else None
        github_commit = github_commit_result.stdout.strip() if mirror_present else None
        mirror_match = (
            mirror_present
            and github_object == tag["tag_object_sha"]
            and github_commit == tag["tag_commit_sha"]
        )
        if mirror_present and not mirror_match:
            raise LinuxMainlineRCContractError(f"GitHub tag identity mismatch: {tag['tag_name']}")
        tag_row = {
            **tag,
            "signal_date": signal_date,
            "signature_verified": True,
            "signature_key_fingerprint": SIGNING_KEY_FINGERPRINT,
            "signature_provenance_url": SIGNATURE_PROVENANCE_URL,
            "signature_audit_method": "fresh git verify-tag --raw with inherited isolated WKD keyring",
            "peeled_commit_sha": tag["tag_commit_sha"],
            "prior_tag_name": prior["tag_name"],
            "prior_tag_object_sha": prior["tag_object_sha"],
            "prior_tag_commit_sha": prior["tag_commit_sha"],
            "prior_tag_signature_verified": True,
            "source_rule_version": SOURCE_RULE_VERSION,
        }
        tag_row["source_record_sha256"] = _payload_sha256(tag_row)
        rc_tags.append(tag_row)
        cross_rows.append({"tag_name": tag["tag_name"], "official_tag_object_sha": tag["tag_object_sha"], "github_tag_object_sha": github_object, "official_tag_commit_sha": tag["tag_commit_sha"], "github_tag_commit_sha": github_commit, "mirror_present": mirror_present, "match": mirror_match if mirror_present else None})
        log_format = "%H%x00%P%x00%ae%x00%aI%x00%cI%x00"
        log_output = _git(official, "log", "--no-merges", f"--format={log_format}", f"{prior['tag_commit_sha']}..{tag['tag_commit_sha']}").stdout
        log_fields = log_output.split("\x00")
        for pos in range(0, len(log_fields) - 5, 5):
            commit_sha, parents, author_email, authored_at, committed_at = (part.strip() for part in log_fields[pos : pos + 5])
            if not commit_sha:
                continue
            parent_list = parents.split()
            if len(parent_list) == 0:
                # Partial/shallow clones suppress parents at traversal
                # boundaries in ``%P`` even though the immutable commit object
                # still records them.  Inspect the object itself so a hidden
                # merge is never admitted as a root/non-merge commit.
                object_text = _git(official, "cat-file", "-p", commit_sha).stdout
                parent_list = [
                    line[7:].strip()
                    for line in object_text.splitlines()
                    if line.startswith("parent ")
                ]
            if len(parent_list) != 1:
                # ``--no-merges`` normally removes these; this second check is
                # required for shallow-boundary merge objects.
                continue
            try:
                domain = _raw_email_domain(author_email)
            except LinuxMainlineRCContractError:
                continue
            mapping = DOMAIN_TO_ISSUER.get(domain)
            if mapping is None or signal_date < mapping["effective_from"]:
                continue
            canonical_committed = _canonical_timestamp(committed_at, field="committed_at")
            if _utc_datetime(canonical_committed, field="committed_at") > _utc_datetime(tag["tagger_at"], field="tagger_at"):
                raise LinuxMainlineRCContractError(f"future-visible commit: {commit_sha}")
            row = {
                **{key: tag_row[key] for key in ("tag_name", "tag_object_type", "tag_object_sha", "tag_commit_sha", "tagger_at", "signal_date", "signature_verified", "prior_tag_name", "prior_tag_object_sha", "prior_tag_commit_sha")},
                "commit_sha": commit_sha,
                "parent_count": 1,
                "author_email": author_email,
                "author_domain": domain,
                "authored_at": _canonical_timestamp(authored_at, field="authored_at"),
                "committed_at": canonical_committed,
                "ticker": mapping["ticker"],
                "mapping_effective_from": mapping["effective_from"],
                "mapping_provenance": mapping["provenance"],
                "source_rule_version": SOURCE_RULE_VERSION,
            }
            row["source_record_sha256"] = _payload_sha256(row)
            commit_rows.append(row)

    tag_keys = {(row["tag_name"], row["tag_object_sha"]) for row in rc_tags}
    if len(tag_keys) != len(rc_tags):
        raise LinuxMainlineRCContractError("duplicate or moved RC tag in extraction")
    commit_keys = {(row["tag_name"], row["commit_sha"]) for row in commit_rows}
    if len(commit_keys) != len(commit_rows):
        raise LinuxMainlineRCContractError("duplicate commit natural key in extraction")
    rc_tags.sort(key=lambda row: (row["tagger_at"], row["tag_name"]))
    commit_rows.sort(key=lambda row: (row["tagger_at"], row["tag_name"], row["commit_sha"]))
    output.mkdir(parents=True, exist_ok=True)
    tag_path, commit_path, cross_path = output / TAG_FILE_NAME, output / COMMIT_FILE_NAME, output / CROSSCHECK_FILE_NAME
    atomic_write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rc_tags), tag_path)
    commit_jsonl = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in commit_rows
    ).encode("utf-8")
    _atomic_write_bytes(gzip.compress(commit_jsonl, compresslevel=9, mtime=0), commit_path)
    mirror_rows = [row for row in cross_rows if row["mirror_present"]]
    official_only = [row["tag_name"] for row in cross_rows if not row["mirror_present"]]
    crosscheck = {"schema": "linux_mainline_rc_github_crosscheck_v1", "official_remote_url": OFFICIAL_REMOTE_URL, "github_remote_url": GITHUB_CROSSCHECK_URL, "all_tags_match": all(row["match"] for row in mirror_rows), "official_tag_count": len(cross_rows), "overlap_count": len(mirror_rows), "mismatch_count": sum(not row["match"] for row in mirror_rows), "official_only_count": len(official_only), "official_only_tags": official_only, "coverage_caveat": "GitHub clone is shallow; absent early tags are not treated as divergent", "rows": cross_rows}
    atomic_write_text(json.dumps(crosscheck, indent=2, sort_keys=True) + "\n", cross_path)
    manifest = {
        "schema": SOURCE_BUNDLE_SCHEMA,
        "generated_at": _utc_now_iso(),
        "as_of": as_of_iso,
        "earliest_rc_date": earliest_iso,
        "official_remote_url": OFFICIAL_REMOTE_URL,
        "official_head_sha": _git(official, "rev-parse", "HEAD").stdout.strip(),
        "github_remote_url": GITHUB_CROSSCHECK_URL,
        "github_head_sha": _git(github, "rev-parse", "HEAD").stdout.strip(),
        "mapping_sha256": _payload_sha256(DOMAIN_TO_ISSUER),
        "source_rule_version": SOURCE_RULE_VERSION,
        "tag_signature_verification_passed": True,
        "effective_dated_mapping_pit_audit_passed": True,
        "signature_audit": {
            "selected_rc_tag_count": AUDITED_RC_TAG_COUNT,
            "verified_endpoint_count": AUDITED_ENDPOINT_COUNT,
            "count": AUDITED_ENDPOINT_COUNT,
            "good": AUDITED_ENDPOINT_COUNT,
            "exit_code": 0,
            "first_tag": AUDITED_FIRST_RC_TAG,
            "last_tag": AUDITED_LAST_RC_TAG,
            "key_fingerprint": SIGNING_KEY_FINGERPRINT,
            "key_retrieval": "WKD into isolated GNUPG home",
            "method": "git verify-tag --raw",
            "provenance_url": SIGNATURE_PROVENANCE_URL,
            "verification_output_sha256": verification_output_sha256,
        },
        "pit_audit": {
            "raw_author_email_exact_domain": True,
            "effective_dated_map": True,
            "future_committer_timestamp_rejected": True,
            "natural_key_conflicts_rejected": True,
            "mapping_ambiguity_rejected": True,
        },
        "contracts": {"signed_annotated_rc_tags_only": True, "immediate_prior_mainline_tag": True, "non_merge_commits_only": True, "raw_author_email_exact_domain": True, "mailmap_used": False, "future_visibility_rejected": True},
        "files": {
            TAG_FILE_NAME: {"sha256": _file_sha256(tag_path), "rows": len(rc_tags)},
            COMMIT_FILE_NAME: {
                "sha256": _file_sha256(commit_path),
                "rows": len(commit_rows),
                "compression": "gzip",
                "gzip_mtime": 0,
                "uncompressed_sha256": hashlib.sha256(commit_jsonl).hexdigest(),
                "uncompressed_bytes": len(commit_jsonl),
            },
            CROSSCHECK_FILE_NAME: {"sha256": _file_sha256(cross_path), "rows": len(cross_rows)},
        },
    }
    manifest["bundle_sha256"] = _payload_sha256({key: value for key, value in manifest.items() if key not in {"bundle_sha256", "generated_at"}})
    atomic_write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", output / MANIFEST_FILE_NAME)
    legacy_commit_path = output / "mapped_nonmerge_commits.jsonl"
    if legacy_commit_path.exists():
        # This exact file is an obsolete generated predecessor of the
        # hash-bound gzip member.  Remove it only after the new member and
        # manifest have both been atomically installed.
        legacy_commit_path.unlink()
    return {"manifest": manifest, "tags": rc_tags, "commit_rows": commit_rows, "crosscheck": crosscheck}


__all__ = [
    "COMMIT_FILE_NAME", "CROSSCHECK_FILE_NAME", "DEFAULT_SNAPSHOT_LOG_PATH",
    "DEFAULT_SOURCE_BUNDLE_DIR", "DEFAULT_STATE_PATH", "DOMAIN_TO_ISSUER",
    "HOLD_SESSIONS", "MANIFEST_FILE_NAME", "MAX_ACTIVE_POSITIONS",
    "MAX_RC_CANDIDATES", "MIN_CURRENT_CONTRIBUTION_COUNT", "PAPER_NOTIONAL_USD",
    "PRIOR_RC_COUNT", "PRIOR_RC_INTERVALS", "RULE_VERSION", "SOURCE_RULE_VERSION", "TAG_FILE_NAME",
    "TRADE_ENABLED", "LinuxMainlineRCContractError",
    "append_linux_mainline_rc_contribution_acceleration_snapshot",
    "build_hash_bound_linux_mainline_rc_source_bundle",
    "build_linux_mainline_rc_contribution_acceleration_historical_trades",
    "build_linux_mainline_rc_contribution_acceleration_snapshot",
    "empty_linux_mainline_rc_contribution_acceleration_state",
    "evaluate_linux_mainline_rc_contribution_acceleration_decisions",
    "load_linux_mainline_rc_contribution_acceleration_state",
    "load_linux_mainline_rc_source_bundle",
    "normalise_linux_mainline_rc_contribution_rows",
    "normalise_linux_mainline_rc_tag_rows",
    "save_linux_mainline_rc_contribution_acceleration_state",
    "select_linux_mainline_rc_contribution_acceleration_decisions",
]
