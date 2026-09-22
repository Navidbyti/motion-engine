from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_readme_supports_link_only_onboarding_above_the_fold():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    opening = readme[:4000]
    assert "Start here — send only this link" in opening
    assert "https://github.com/Navidbyti/motion-engine" in opening
    assert "First production prompt" in opening
    assert "Instructions for the coding agent receiving only the URL" in opening
    for command in ("motion-engine doctor", "motion-engine init-project", "motion-engine produce"):
        assert command in opening


def test_public_editor_feedback_form_warns_about_private_inputs():
    template = (ROOT / ".github/ISSUE_TEMPLATE/editor-alpha.yml").read_text(encoding="utf-8")
    assert "Editor alpha report" in template
    assert "private" in template.casefold()
    assert "motion-engine doctor" in template
