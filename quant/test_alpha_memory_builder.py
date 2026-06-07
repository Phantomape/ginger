import json
import subprocess

import pytest

from scripts.build_alpha_memory import materialize_git_ref_logs, write_alpha_memory


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )


def _row(index, *, decision, ev_delta, mechanism="peer_shock", trial="peer_shock_core_flow"):
    return {
        "experiment_id": f"exp-20990101-{index:03d}",
        "lane": "alpha_search",
        "decision": decision,
        "hypothesis": "Peer shock should identify lagging correlated stocks with replacement value.",
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": mechanism,
        "trial_family": trial,
        "changed_variable": f"{trial}_policy",
        "prior_trial_count": index,
        "nearby_prior_experiments": [
            f"exp-20981231-{i:03d}" for i in range(min(index, 3))
        ],
        "new_evidence_type": "not_declared",
        "delta_metrics": {
            "expected_value_score": ev_delta,
            "total_pnl": ev_delta * 10000,
        },
        "after_metrics": {"trade_count": 12},
        "post_run_reflection": {
            "why_result_happened": "The relation added or failed to add independent replacement value.",
            "forbidden_near_neighbor_retry": "Do not retune thresholds on the frozen sample.",
            "new_evidence_required": "Require closed forward replacement-value rows.",
        },
    }


def test_alpha_memory_builder_uses_logs_without_registry(tmp_path):
    rows = [
        _row(1, decision="accepted", ev_delta=0.4),
        _row(2, decision="rejected", ev_delta=-0.1),
        _row(3, decision="accepted", ev_delta=0.2, mechanism="macro_relief"),
    ]
    _write_jsonl(tmp_path / "docs" / "experiment_log.jsonl", rows)

    result = write_alpha_memory(
        root=tmp_path,
        context_pack=tmp_path / "docs" / "alpha_context_pack.md",
        lessons_dir=tmp_path / "docs" / "lessons",
        lesson_count=2,
        recent_count=3,
    )

    context = (tmp_path / "docs" / "alpha_context_pack.md").read_text(
        encoding="utf-8"
    )
    assert result["records_counted"] == 3
    assert "Strategy records counted: `3`" in context
    assert "History fingerprint" in context
    assert "docs/current_state.md" in context
    assert len(context.splitlines()) <= 420
    assert (tmp_path / "docs" / "lessons" / "peer-shock.md").exists()
    assert (tmp_path / "docs" / "lessons" / "macro-relief.md").exists()
    assert str(tmp_path) not in context


def test_alpha_memory_lesson_cards_include_retry_guidance(tmp_path):
    rows = [
        _row(i, decision="rejected", ev_delta=-0.02)
        for i in range(10)
    ]
    rows.append(_row(10, decision="accepted", ev_delta=0.1))
    _write_jsonl(tmp_path / "docs" / "experiment_log.jsonl", rows)

    write_alpha_memory(
        root=tmp_path,
        context_pack=tmp_path / "docs" / "alpha_context_pack.md",
        lessons_dir=tmp_path / "docs" / "lessons",
        lesson_count=1,
        recent_count=4,
    )

    card = (tmp_path / "docs" / "lessons" / "peer-shock.md").read_text(
        encoding="utf-8"
    )
    assert "Retry Discipline" in card
    assert "freeze_nearby_retries_until_new_forward_or_field_evidence" in card
    assert "closed forward replacement-value rows" in card
    assert str(tmp_path) not in card


def test_alpha_memory_context_pack_enforces_line_budget(tmp_path):
    rows = [_row(i, decision="accepted", ev_delta=0.1) for i in range(4)]
    _write_jsonl(tmp_path / "docs" / "experiment_log.jsonl", rows)

    with pytest.raises(ValueError, match="above budget"):
        write_alpha_memory(
            root=tmp_path,
            context_pack=tmp_path / "docs" / "alpha_context_pack.md",
            lessons_dir=tmp_path / "docs" / "lessons",
            lesson_count=1,
            recent_count=4,
            context_line_budget=20,
        )


def test_git_ref_materialization_ignores_dirty_workspace_logs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_jsonl(repo / "docs" / "experiment_log.jsonl", [
        _row(1, decision="accepted", ev_delta=0.4),
    ])
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "docs/experiment_log.jsonl"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "seed logs",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    _write_jsonl(repo / "docs" / "experiment_log.jsonl", [
        _row(1, decision="accepted", ev_delta=0.4),
        _row(2, decision="accepted", ev_delta=0.5, mechanism="dirty_only"),
    ])
    source_root = tmp_path / "source"
    materialized = materialize_git_ref_logs("HEAD", source_root, repo_root=repo)
    second_source_root = tmp_path / "source_again"
    materialize_git_ref_logs("HEAD", second_source_root, repo_root=repo)

    result = write_alpha_memory(
        root=source_root,
        context_pack=tmp_path / "docs" / "alpha_context_pack.md",
        lessons_dir=tmp_path / "docs" / "lessons",
        lesson_count=4,
        recent_count=4,
    )
    second_result = write_alpha_memory(
        root=second_source_root,
        context_pack=tmp_path / "docs" / "alpha_context_pack_again.md",
        lessons_dir=tmp_path / "docs" / "lessons_again",
        lesson_count=4,
        recent_count=4,
    )

    context = (tmp_path / "docs" / "alpha_context_pack.md").read_text(
        encoding="utf-8"
    )
    assert materialized == ["docs/experiment_log.jsonl"]
    assert result["records_counted"] == 1
    assert second_result["fingerprint"] == result["fingerprint"]
    assert "dirty_only" not in context
