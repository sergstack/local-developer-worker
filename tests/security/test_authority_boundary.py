from pathlib import Path


ROOT = Path(__file__).parents[2]
ADVISORY_PHRASE = "гарантия advisory, действует только при вызове инструмента по промпту"


def test_authority_boundary_discloses_advisory_test_parse_enforcement():
    boundary = (ROOT / "docs" / "authority-boundary.md").read_text()

    assert "no technical mechanism" in boundary
    assert "bypassing `ldw test parse`" in boundary
    assert ADVISORY_PHRASE in boundary
    assert "no hook, shell wrapper, or test-runner interception" in boundary
