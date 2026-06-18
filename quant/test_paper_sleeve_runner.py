import logging

from paper_sleeve_runner import run_sleeve


class _CapLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, fmt, *args):
        self.infos.append(fmt % args if args else fmt)

    def warning(self, fmt, *args):
        self.warnings.append(fmt % args if args else fmt)


def _empty(today_iso, reason):
    return {"_empty": True, "as_of": today_iso, "reason": reason}


def test_run_sleeve_returns_build_result_and_logs_when_active():
    log = _CapLogger()
    snap = {"candidate_count": 3, "pending_count": 0, "realized_pnl_to_date": 12.5}
    out = run_sleeve(
        lambda: snap,
        _empty,
        logger=log,
        today_iso="2026-06-16",
        log_label="State-surface paper",
        fail_reason="state_surface_build_failed",
        log_metrics=[("candidates", "candidate_count"), ("pnl", "realized_pnl_to_date")],
    )
    assert out is snap
    assert log.infos == ["State-surface paper sleeve: candidates=3 pnl=12.5"]
    assert log.warnings == []


def test_run_sleeve_no_log_when_inactive():
    log = _CapLogger()
    snap = {"candidate_count": 0, "pending_count": 0, "open_position_count": 0, "closed_count_today": 0}
    out = run_sleeve(
        lambda: snap, _empty, logger=log, today_iso="2026-06-16",
        log_label="X", fail_reason="x_failed",
        log_metrics=[("candidates", "candidate_count")],
    )
    assert out is snap
    assert log.infos == []


def test_run_sleeve_noun_queue_wording_in_active_and_failure_logs():
    log = _CapLogger()
    snap = {"candidate_count": 4}
    out = run_sleeve(
        lambda: snap, _empty, logger=log, today_iso="2026-06-16",
        log_label="Form 4 forward event", fail_reason="form4_event_queue_build_failed",
        log_metrics=[("candidates", "candidate_count")],
        activity_keys=("candidate_count",), noun="queue",
    )
    assert out is snap
    assert log.infos == ["Form 4 forward event queue: candidates=4"]

    log = _CapLogger()

    def boom():
        raise RuntimeError("kaboom")

    run_sleeve(
        boom, _empty, logger=log, today_iso="2026-06-16",
        log_label="Form 4 forward event", fail_reason="form4_event_queue_build_failed",
        noun="queue",
    )
    assert "Form 4 forward event queue unavailable: kaboom" in log.warnings[0]


def test_run_sleeve_falls_back_to_empty_on_exception():
    log = _CapLogger()

    def boom():
        raise RuntimeError("kaboom")

    out = run_sleeve(
        boom, _empty, logger=log, today_iso="2026-06-16",
        log_label="Core-misfit paper", fail_reason="core_misfit_build_failed",
    )
    assert out == {"_empty": True, "as_of": "2026-06-16", "reason": "core_misfit_build_failed"}
    assert log.infos == []
    assert len(log.warnings) == 1
    assert "Core-misfit paper sleeve unavailable: kaboom" in log.warnings[0]
