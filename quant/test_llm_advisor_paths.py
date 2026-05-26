from __future__ import annotations

from pathlib import Path


def test_save_prompt_file_uses_organized_path_inside_repo(tmp_path: Path, monkeypatch) -> None:
    import data_paths
    import llm_advisor

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)

    prompt_path = llm_advisor._save_prompt_file(
        "20260525",
        "system body",
        "user body",
        trade_news=[],
        trend_signals={"quant_signals": []},
    )

    assert Path(prompt_path) == data_root / "daily" / "llm" / "prompts" / "llm_prompt_20260525.txt"
    assert Path(prompt_path).exists()
    assert not (data_root / "llm_prompt_20260525.txt").exists()
