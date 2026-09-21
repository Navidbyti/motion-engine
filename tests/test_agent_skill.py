import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_motion_engine_production_skill_is_complete_and_self_consistent():
    skill = (ROOT / "skills/motion-engine-production/SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", skill, re.DOTALL)
    assert match
    fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip()
              for line in match.group(1).splitlines() if ":" in line}
    assert fields.keys() == {"name", "description"}
    assert fields["name"] == "motion-engine-production"
    assert 0 < len(fields["description"]) <= 1024
    assert "[TODO:" not in skill
    for path in ("AGENTS.md", "docs/desktop-agent-workflow.md", "docs/product-roadmap.md",
                 "docs/research.md", "docs/adobe-adapters.md"):
        assert (ROOT / path).is_file()

    metadata = (ROOT / "skills/motion-engine-production/agents/openai.yaml").read_text(encoding="utf-8")
    assert 'display_name: "Motion Engine Production"' in metadata
