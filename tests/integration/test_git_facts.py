import subprocess

from local_developer_worker.tools import git_facts


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def test_git_facts_separates_staged_unstaged_and_untracked(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "tracked.txt").write_text("base")
    _git(tmp_path, "add", "tracked.txt"); _git(tmp_path, "commit", "-m", "base")
    (tmp_path / "tracked.txt").write_text("changed")
    (tmp_path / "staged.txt").write_text("stage"); _git(tmp_path, "add", "staged.txt")
    (tmp_path / "new file.txt").write_text("new")
    data = git_facts({"repository_root": str(tmp_path)})["data"]
    assert data["staged_files"] == ["staged.txt"]
    assert data["unstaged_files"] == ["tracked.txt"]
    assert data["untracked_files"] == ["new file.txt"]


def test_git_facts_handles_repository_without_initial_commit(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / "new.txt").write_text("new")
    data = git_facts({"repository_root": str(tmp_path)})["data"]
    assert data["comparison_base"] is None
    assert data["untracked_files"] == ["new.txt"]
