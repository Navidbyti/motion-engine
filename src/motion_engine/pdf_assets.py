"""Export embedded PDF images with hashes and page placement evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


def extract_pdf_images(source: str | Path, output_dir: str | Path,
                       max_images: int = 1000, max_total_bytes: int = 100_000_000) -> dict[str, Any]:
    import pdfplumber
    from pypdf import PdfReader

    pdf = Path(source).resolve()
    destination = Path(output_dir).resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError("source must be an existing PDF")
    if destination.exists():
        raise ValueError("image output directory already exists")
    if max_images < 1 or max_total_bytes < 1:
        raise ValueError("image and byte limits must be positive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf))
    if reader.is_encrypted:
        raise ValueError("encrypted PDF requires an unlocked source")
    source_digest = hashlib.sha256()
    with pdf.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            source_digest.update(block)
    source_hash = source_digest.hexdigest()
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)).resolve()
    if not stage.is_relative_to(destination.parent):
        raise ValueError("temporary image directory escaped its output parent")
    try:
        images: list[dict[str, Any]] = []
        issues: list[dict[str, str]] = []
        total_bytes = 0
        with pdfplumber.open(str(pdf)) as layout_doc:
            if len(reader.pages) != len(layout_doc.pages):
                raise ValueError("PDF page counts disagree between image and layout parsers")
            for page_number, (page, layout) in enumerate(zip(reader.pages, layout_doc.pages), 1):
                regions: dict[str, list[dict[str, Any]]] = {}
                for region in layout.images:
                    name = str(region.get("name", ""))
                    regions.setdefault(name, []).append({
                        "bbox": [region[key] for key in ("x0", "top", "x1", "bottom")],
                        "pageSize": [layout.width, layout.height],
                        "coordinateSystem": "top-left PDF points",
                    })
                matched: set[str] = set()
                for index, image in enumerate(page.images, 1):
                    if len(images) >= max_images:
                        raise ValueError(f"PDF image count exceeds limit {max_images}")
                    data = image.data
                    total_bytes += len(data)
                    if total_bytes > max_total_bytes:
                        raise ValueError(f"decoded PDF images exceed byte limit {max_total_bytes}")
                    digest = hashlib.sha256(data).hexdigest()
                    extension = Path(image.name).suffix.lower()
                    if extension not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".jp2", ".bmp"}:
                        extension = ".bin"
                    filename = f"page-{page_number:04d}-image-{index:04d}-{digest[:12]}{extension}"
                    (stage / filename).write_bytes(data)
                    object_name = Path(image.name).stem
                    placements = regions.get(object_name, [])
                    if placements:
                        matched.add(object_name)
                    else:
                        issues.append({"code": "pdf_image_placement_unmatched",
                                       "message": f"Page {page_number} image {index} has no verified page region"})
                    images.append({"page": page_number, "pageImageIndex": index,
                                   "sourceObjectName": image.name, "file": filename,
                                   "sha256": digest, "byteLength": len(data),
                                   "pixelSize": list(image.image.size), "placements": placements})
                for name in regions.keys() - matched:
                    issues.append({"code": "pdf_image_region_unmatched",
                                   "message": f"Page {page_number} region {name!r} has no exported image"})
                layout.close()
        manifest = {"source": str(pdf), "sourceSha256": source_hash,
                    "images": images, "issues": issues, "imageCount": len(images)}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
        if destination.exists():
            raise ValueError("image output directory appeared during extraction")
        stage.rename(destination)
        return manifest
    except BaseException:
        if stage.is_relative_to(destination.parent) and stage.exists():
            shutil.rmtree(stage)
        raise
