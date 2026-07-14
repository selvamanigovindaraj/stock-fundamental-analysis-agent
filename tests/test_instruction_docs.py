from pathlib import Path


def test_agent_instruction_files_stay_synchronized() -> None:
    root = Path(__file__).parent.parent
    assert (root / "AGENTS.md").read_text() == (root / "CLAUDE.md").read_text()
