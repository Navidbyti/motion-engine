import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.pdf_assets import extract_pdf_images


def test_export_pdf_images_keeps_hashes_and_each_page_placement(tmp_path):
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    source = tmp_path / "images.pdf"
    page = canvas.Canvas(str(source))
    red = ImageReader(Image.new("RGB", (8, 8), "red"))
    page.drawImage(red, 72, 600, 40, 40)
    page.drawImage(red, 150, 500, 80, 60)
    page.showPage()
    page.drawImage(ImageReader(Image.new("RGB", (6, 9), "blue")), 100, 400, 30, 45)
    page.save()

    output = tmp_path / "extracted"
    manifest = extract_pdf_images(source, output)
    assert manifest["sourceSha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["imageCount"] == 2
    assert manifest["issues"] == []
    first, second = manifest["images"]
    assert first["page"] == 1 and len(first["placements"]) == 2
    assert first["pixelSize"] == [8, 8]
    assert second["page"] == 2 and second["pixelSize"] == [6, 9]
    for item in manifest["images"]:
        data = (output / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert item["placements"][0]["coordinateSystem"] == "top-left PDF points"
    assert (output / "manifest.json").is_file()
    with pytest.raises(ValueError, match="already exists"):
        extract_pdf_images(source, output)


def test_export_pdf_images_enforces_limits_without_publishing_partial_dir(tmp_path):
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    source = tmp_path / "one.pdf"
    page = canvas.Canvas(str(source))
    page.drawImage(ImageReader(Image.new("RGB", (8, 8), "red")), 72, 600, 40, 40)
    page.save()
    output = tmp_path / "limited"
    with pytest.raises(ValueError, match="byte limit"):
        extract_pdf_images(source, output, max_total_bytes=1)
    assert not output.exists()
    assert not list(tmp_path.glob(".limited.*"))
