"""Shared wrapper for the repetitive paper-sleeve invocation boilerplate in
``run.py``.

Every sleeve in run.py's Step 6 follows the same shape:

    try:
        snap = build_<X>_sleeve_snapshot(...)
        if snap has any activity: log.info("<X> sleeve: ...", ...)
    except Exception as e:
        log.warning("<X> sleeve unavailable: %s", e)
        snap = empty_<X>_sleeve_snapshot(today_iso, "<X>_build_failed")

``run_sleeve`` extracts exactly that try / activity-gated-log / except-fallback
boilerplate so each call site collapses to a single statement. The sleeve's
actual build call (and any per-sleeve input prep) stays at the call site inside
the ``build`` closure, so the parity-critical snapshot output is produced by the
unchanged builder -- this wrapper is purely structural.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

# The keys run.py uses to decide whether a sleeve did anything worth logging.
DEFAULT_ACTIVITY_KEYS = (
    "candidate_count",
    "pending_count",
    "open_position_count",
    "closed_count_today",
)


def run_sleeve(
    build: Callable[[], Any],
    empty_fn: Callable[[str, str], Any],
    *,
    logger,
    today_iso: str,
    log_label: str,
    fail_reason: str,
    log_metrics: Sequence[tuple[str, str]] = (),
    activity_keys: Sequence[str] = DEFAULT_ACTIVITY_KEYS,
):
    """Run one paper sleeve with the standard boilerplate.

    Parameters
    ----------
    build:
        Zero-arg callable returning the sleeve snapshot dict. It captures the
        sleeve's specific inputs/prep at the call site.
    empty_fn:
        Empty-snapshot factory, invoked as ``empty_fn(today_iso, fail_reason)``
        when ``build`` raises.
    log_metrics:
        ``(label, snapshot_key)`` pairs logged (in order) when the sleeve is
        active. Empty -> just log that the sleeve was active.
    activity_keys:
        Snapshot keys whose presence (>0) marks the sleeve as active.
    """
    try:
        snap = build()
        if isinstance(snap, dict) and any((snap.get(k) or 0) for k in activity_keys):
            if log_metrics:
                fmt = "%s sleeve: " + " ".join(f"{label}=%s" for label, _ in log_metrics)
                logger.info(fmt, log_label, *(snap.get(key) for _, key in log_metrics))
            else:
                logger.info("%s sleeve active", log_label)
        return snap
    except Exception as exc:  # noqa: BLE001 - mirror run.py's broad guard
        logger.warning("%s sleeve unavailable: %s", log_label, exc)
        return empty_fn(today_iso, fail_reason)
