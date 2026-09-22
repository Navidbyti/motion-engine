"""Generate a portable local review interface for a MotionSpec and its scene modules."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .revisions import file_sha256, spec_sha256
from .runs import verify_render_run
from .scene_assembly import SceneAssemblyError, _load_modules, _safe_artifact, _verify_candidate
from .scene_modules import scene_input_sha256


class ReviewSiteError(ValueError):
    pass


_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Motion Engine Review</title>
  <style>
    :root{color-scheme:dark;--bg:#090a0d;--panel:#111319;--raised:#181b22;--line:#2a2e38;--text:#f5f5f3;--muted:#a4a8b2;--accent:#ff6b2c;--accent2:#ffb36b;--ok:#55d68b;--warn:#ffd166;--bad:#ff6b6b;--radius:18px}
    *{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 18% -10%,#272019 0,transparent 32rem),var(--bg);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
    button,textarea,input{font:inherit}.shell{width:min(1500px,100%);margin:auto;padding:28px}.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:24px}.eyebrow{color:var(--accent2);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}.topbar h1{font-size:clamp(28px,4vw,52px);letter-spacing:-.045em;line-height:1;margin:.25rem 0}.subtle{color:var(--muted)}.badge{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:#151820;border-radius:999px;padding:7px 11px;font-size:12px}.badge::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--muted)}.badge.passed::before{background:var(--ok)}.badge.needs_review::before{background:var(--warn)}.badge.failed::before{background:var(--bad)}
    .summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 24px}.metric{border:1px solid var(--line);background:linear-gradient(145deg,#151820,#101217);border-radius:14px;padding:15px}.metric b{display:block;font-size:22px;letter-spacing:-.03em}.metric span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}
    .hero{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.6fr);gap:18px;margin-bottom:32px}.panel{border:1px solid var(--line);background:rgba(17,19,25,.92);border-radius:var(--radius);overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;padding:15px 17px;border-bottom:1px solid var(--line)}.panel-head h2,.scene h2{margin:0;font-size:15px}.player{aspect-ratio:16/9;background:#050506;display:grid;place-items:center;position:relative;overflow:hidden;min-height:0}.player video{width:100%;height:100%;object-fit:contain;position:absolute;inset:0}.notes{padding:18px}.notes h2{font-size:14px;margin:0 0 10px}.notes ul{padding-left:18px;color:var(--muted);margin:0}.timeline-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:0 0 14px}.timeline-head h2{font-size:24px;margin:0}.scene-list{display:grid;gap:16px}.scene{display:grid;grid-template-columns:minmax(260px,420px) minmax(0,1fr);border:1px solid var(--line);background:var(--panel);border-radius:var(--radius);overflow:hidden}.scene-media{background:#050506;min-height:230px;position:relative;display:grid;place-items:center}.scene-media video,.scene-media img{width:100%;height:100%;position:absolute;inset:0;object-fit:contain}.scene-index{position:absolute;left:12px;top:12px;z-index:2;background:rgba(5,5,6,.82);backdrop-filter:blur(8px);border:1px solid #ffffff1f;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:700}.scene-body{padding:18px;display:grid;gap:15px}.scene-title{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.scene-title h2{font-size:20px}.time{color:var(--accent2);white-space:nowrap;font-variant-numeric:tabular-nums}.copy-block{padding:12px 14px;border-left:3px solid var(--accent);background:var(--raised);border-radius:0 10px 10px 0;white-space:pre-wrap}.meta{display:flex;flex-wrap:wrap;gap:7px}.meta span{border:1px solid var(--line);border-radius:999px;padding:4px 8px;color:var(--muted);font-size:12px}.edit-box{display:grid;gap:8px}.edit-box label{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.edit-row{display:grid;grid-template-columns:1fr auto;gap:8px}.edit-row textarea{resize:vertical;min-height:72px;width:100%;border:1px solid var(--line);border-radius:12px;background:#0c0e12;color:var(--text);padding:11px 12px;outline:none}.edit-row textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px #ff6b2c2a}.button{border:0;border-radius:12px;background:var(--accent);color:#130905;font-weight:800;padding:0 16px;cursor:pointer}.button:hover{filter:brightness(1.08)}.button:focus-visible{outline:3px solid #fff;outline-offset:2px}.toast{position:fixed;right:20px;bottom:20px;background:#f5f5f3;color:#111;padding:10px 14px;border-radius:10px;box-shadow:0 12px 40px #0008;opacity:0;transform:translateY(8px);transition:.2s;pointer-events:none}.toast.show{opacity:1;transform:none}.empty{color:var(--muted);padding:32px;text-align:center}
    @media(max-width:900px){.shell{padding:18px}.summary{grid-template-columns:repeat(2,1fr)}.hero,.scene{grid-template-columns:1fr}.scene-media{aspect-ratio:16/9;min-height:0}.topbar{display:block}.topbar .badge{margin-top:12px}}@media(max-width:520px){.summary{grid-template-columns:1fr 1fr}.edit-row{grid-template-columns:1fr}.button{min-height:44px}.scene-body{padding:14px}}
  </style>
</head>
<body>
<main class="shell">
  <header class="topbar"><div><div class="eyebrow">Motion Engine review</div><h1 id="title"></h1><div class="subtle" id="identity"></div></div><div class="badge" id="status">Review pending</div></header>
  <section class="summary" aria-label="Project summary"><div class="metric"><b id="scene-count">0</b><span>Scenes</span></div><div class="metric"><b id="duration">0s</b><span>Duration</span></div><div class="metric"><b id="resolution"></b><span>Canvas</span></div><div class="metric"><b id="fps"></b><span>Frame rate</span></div></section>
  <section class="hero"><div class="panel"><div class="panel-head"><h2>Assembled preview</h2><span class="subtle" id="revision"></span></div><div class="player" id="full-player"></div></div><aside class="panel notes"><h2>Review flow</h2><ul><li>Watch the complete cut for story and pacing.</li><li>Review each scene for copy, motion, assets, and sound.</li><li>Write an instruction beside a scene and copy it into the same coding-agent chat.</li><li>The agent rerenders that scene and assembles a verified new version.</li></ul></aside></section>
  <div class="timeline-head"><div><div class="eyebrow">Scene timeline</div><h2>Review scene by scene</h2></div><div class="subtle">Stable IDs preserve targeted edits</div></div>
  <section class="scene-list" id="scenes"></section>
</main><div class="toast" role="status" aria-live="polite" id="toast">Copied edit prompt</div>
<script>window.REVIEW_DATA=__REVIEW_DATA__;</script>
<script>
const data=window.REVIEW_DATA;const $=s=>document.querySelector(s);const esc=s=>String(s??'');
$('#title').textContent=data.title;$('#identity').textContent=`${data.projectId} · ${data.locale} · build ${data.producerVersion}`;
$('#scene-count').textContent=data.scenes.length;$('#duration').textContent=`${data.durationSeconds.toFixed(1)}s`;$('#resolution').textContent=`${data.width}×${data.height}`;$('#fps').textContent=data.fps;
$('#revision').textContent=data.revisionSha256?data.revisionSha256.slice(0,10):'unfrozen';const status=$('#status');status.textContent=data.qaStatus.replace('_',' ');status.classList.add(data.qaStatus);
const full=$('#full-player');if(data.preview){const v=document.createElement('video');v.controls=true;v.preload='metadata';v.src=data.preview;full.append(v)}else{full.innerHTML='<div class="empty">No assembled preview was supplied</div>'}
const list=$('#scenes');for(const scene of data.scenes){const article=document.createElement('article');article.className='scene';const media=document.createElement('div');media.className='scene-media';const idx=document.createElement('span');idx.className='scene-index';idx.textContent=`${scene.order+1} · ${scene.id}`;media.append(idx);if(scene.video){const v=document.createElement('video');v.controls=true;v.preload='metadata';v.poster=scene.poster||'';v.src=scene.video;media.append(v)}else if(scene.poster){const img=document.createElement('img');img.src=scene.poster;img.alt=`Preview frame for ${scene.id}`;media.append(img)}else{const e=document.createElement('div');e.className='empty';e.textContent='No scene media';media.append(e)}
const body=document.createElement('div');body.className='scene-body';const heading=document.createElement('div');heading.className='scene-title';const h=document.createElement('h2');h.textContent=scene.purpose||scene.id;const t=document.createElement('span');t.className='time';t.textContent=`${scene.startSeconds.toFixed(1)}–${scene.endSeconds.toFixed(1)}s`;heading.append(h,t);body.append(heading);
if(scene.onScreen.length){const copy=document.createElement('div');copy.className='copy-block';copy.textContent=scene.onScreen.join('\n');body.append(copy)}const meta=document.createElement('div');meta.className='meta';for(const value of scene.meta){const chip=document.createElement('span');chip.textContent=value;meta.append(chip)}body.append(meta);
const box=document.createElement('div');box.className='edit-box';const label=document.createElement('label');const input=document.createElement('textarea');const button=document.createElement('button');const inputId=`edit-${scene.order}`;label.htmlFor=inputId;label.textContent='Prompt this scene';input.id=inputId;input.value=`Revise scene ${scene.id}: `;button.className='button';button.type='button';button.textContent='Copy prompt';button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(input.value)}catch{input.select();document.execCommand('copy')}const toast=$('#toast');toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),1400)});const row=document.createElement('div');row.className='edit-row';row.append(input,button);box.append(label,row);body.append(box);article.append(media,body);list.append(article)}
</script></body></html>'''


def _values(items: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in items:
        value = item.get("value")
        if isinstance(value, str) and value.strip() and value not in values:
            values.append(value)
    return values


def make_review_site(
    spec: dict[str, Any],
    module_dirs: list[str | Path],
    output_dir: str | Path,
    *,
    render_dir: str | Path | None = None,
    scale: float = 0.5,
    font_dirs: list[str | Path] | None = None,
    revision_sha256: str | None = None,
) -> dict[str, Any]:
    if not module_dirs:
        raise ReviewSiteError("at least one scene module directory is required")
    output = Path(output_dir).resolve()
    if output.exists():
        raise ReviewSiteError(f"output path {output} already exists; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, list[dict[str, Any]]] = {}
    try:
        for directory in module_dirs:
            root, manifest = _load_modules(directory)
            options = manifest.get("renderOptions", {})
            expected_fonts = [str(Path(path).resolve()) for path in (font_dirs or [])]
            if options.get("scale") != scale or options.get("fontDirs") != expected_fonts:
                raise ReviewSiteError(f"scene module render settings do not match review settings: {root}")
            for module in manifest["modules"]:
                candidates.setdefault(module.get("sceneId"), []).append(_verify_candidate(root, module))
    except SceneAssemblyError as exc:
        raise ReviewSiteError(str(exc)) from exc

    selected = []
    for scene in spec["timeline"]:
        expected = scene_input_sha256(spec, scene["id"], scale=scale, font_dirs=font_dirs)
        matches = [item for item in candidates.get(scene["id"], []) if item["module"].get("sceneInputSha256") == expected]
        if not matches:
            raise ReviewSiteError(f"no compatible module for scene {scene['id']}")
        signatures = {(item["framesSha256"], item["audioSha256"]) for item in matches}
        if len(signatures) != 1:
            raise ReviewSiteError(f"compatible modules for scene {scene['id']} disagree")
        selected.append(matches[0])

    verified_render = None
    if render_dir is not None:
        verified_render = verify_render_run(render_dir)
        if verified_render.get("specSha256") != spec_sha256(spec) or verified_render.get("revisionSha256") != revision_sha256:
            raise ReviewSiteError("assembled preview does not match the target MotionSpec revision")

    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        media_dir = staging / "media"
        media_dir.mkdir()
        scene_data = []
        rate = spec["canvas"]["frameRate"]
        fps_value = rate["numerator"] / rate["denominator"]
        for order, (scene, item) in enumerate(zip(spec["timeline"], selected)):
            module = item["module"]
            scene_media = media_dir / f"scene-{order:03d}"
            scene_media.mkdir()
            middle = max(0, module["frameCount"] // 2)
            poster_target = scene_media / "poster.png"
            shutil.copyfile(item["frames"] / f"{middle:06d}.png", poster_target)
            video_relative = None
            video_output = next((value for value in module["outputs"] if value["kind"] == "video/mp4"), None)
            if video_output is not None:
                video_source = _safe_artifact(item["root"], video_output["path"])
                if not video_source.is_file() or file_sha256(video_source) != video_output.get("sha256"):
                    raise ReviewSiteError(f"scene {scene['id']} video does not match its manifest")
                video_target = scene_media / "preview.mp4"
                shutil.copyfile(video_source, video_target)
                video_relative = video_target.relative_to(staging).as_posix()
            on_screen = []
            voice = []
            for beat in scene["beats"]:
                on_screen.extend(value for value in _values(beat.get("onScreen", [])) if value not in on_screen)
                voice_value = beat.get("voice", {}).get("value")
                if isinstance(voice_value, str) and voice_value.strip() and voice_value not in voice:
                    voice.append(voice_value)
            kinds = sorted({element["kind"] for element in scene["elements"]})
            scene_data.append({
                "id": scene["id"], "order": order,
                "purpose": scene.get("purpose"),
                "startSeconds": scene["startFrame"] / fps_value,
                "endSeconds": scene["endFrameExclusive"] / fps_value,
                "onScreen": on_screen,
                "voice": voice,
                "poster": poster_target.relative_to(staging).as_posix(),
                "video": video_relative,
                "meta": [f"{module['frameCount']} frames", *kinds, f"{len(scene.get('sourceRefs', []))} source refs"],
            })
        preview_relative = None
        if verified_render is not None:
            video_output = next((item for item in verified_render["outputs"] if item["kind"] == "video/mp4"), None)
            if video_output is not None:
                source = (Path(render_dir).resolve() / video_output["path"]).resolve()
                target = media_dir / "full-preview.mp4"
                shutil.copyfile(source, target)
                preview_relative = target.relative_to(staging).as_posix()
        qa_status = "needs_review"
        if render_dir is not None:
            qa_path = Path(render_dir).resolve() / "qa.json"
            if qa_path.is_file():
                try:
                    candidate_status = json.loads(qa_path.read_text(encoding="utf-8")).get("status")
                    if candidate_status in ("passed", "needs_review", "failed"):
                        qa_status = candidate_status
                except ValueError:
                    pass
        data = {
            "producerVersion": __version__, "projectId": spec["project"]["id"],
            "title": spec["project"]["title"], "locale": spec["project"]["locale"],
            "revisionSha256": revision_sha256, "qaStatus": qa_status,
            "width": spec["canvas"]["width"], "height": spec["canvas"]["height"],
            "fps": f"{rate['numerator']}/{rate['denominator']}",
            "durationSeconds": spec["canvas"]["durationFrames"] / fps_value,
            "preview": preview_relative, "scenes": scene_data,
        }
        serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (staging / "index.html").write_text(_HTML.replace("__REVIEW_DATA__", serialized), encoding="utf-8")
        manifest = {
            "formatVersion": 1, "producerVersion": __version__, "projectId": spec["project"]["id"],
            "specSha256": spec_sha256(spec), "revisionSha256": revision_sha256,
            "sceneCount": len(scene_data), "qaStatus": qa_status,
            "indexSha256": file_sha256(staging / "index.html"),
        }
        (staging / "review-site.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
        return manifest
