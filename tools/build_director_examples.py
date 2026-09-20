"""Rebuild the two reviewed public director-plan examples."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.director import compile_director_plan


def build(name: str, assets_file: str | None = None) -> None:
    examples = ROOT / "examples"
    prompt = examples / "assets" / f"{name}.txt"
    proposal_file = examples / f"{name}.plan.json"
    proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    assets = json.loads((examples / assets_file).read_text(encoding="utf-8")) if assets_file else None
    output = examples / f"{name}.motion.json"
    spec = compile_director_plan(prompt, output, proposal, project_id=name.replace("-", "_"),
                                 width=320, height=180, fps=24, assets=assets,
                                 proposal_path=proposal_file)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build("director-abstract")
    build("director-plate", "director-plate.assets.json")
