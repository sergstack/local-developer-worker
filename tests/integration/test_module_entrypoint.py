import subprocess
import sys


def test_module_entrypoint_exposes_help():
    completed = subprocess.run([sys.executable, "-m", "local_developer_worker", "--help"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    assert "Deterministic local developer evidence worker" in completed.stdout
