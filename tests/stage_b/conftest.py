from __future__ import annotations

import subprocess

import pytest


@pytest.fixture(autouse=True)
def verified_local_ollama_process(monkeypatch):
    def process_probe(command, **_kwargs):
        if command[0] == "lsof":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ollama 21661 user 10u IPv4 0t0 TCP 127.0.0.1:11435 (LISTEN)\n",
                stderr="",
            )
        if command[0] == "ps":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="/usr/local/bin/ollama\n",
                stderr="",
            )
        raise AssertionError(f"unexpected locality probe: {command[0]}")

    monkeypatch.setattr("local_developer_worker.policy._PROCESS_RUNNER", process_probe)
