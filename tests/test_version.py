import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from motion_engine import __version__
from motion_engine.cli import main


def test_public_version_is_consistent_and_printable(capsys):
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    declared = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert declared and declared.group(1) == __version__
    assert f"Current build: v{__version__}" in readme
    assert f"Current build: v{__version__}" in start
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_agent_contract_has_bounded_idempotent_update_policy():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    policy = (ROOT / "docs" / "update-policy.md").read_text(encoding="utf-8")
    assert "once when starting a new coding-agent session" in agents
    assert "fast-forward-only" in agents
    assert "24 hours" in policy
    assert "git pull --ff-only origin main" in policy
    assert "must not create a new `runs/` project version" in policy
    assert "normal fast-forward pull does not require a new chat" in policy
