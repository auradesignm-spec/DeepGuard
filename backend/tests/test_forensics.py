"""m3 — forensic checks: states, measurements, hash-DB settle rules."""

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.services import forensics as F


def _image(size=(200, 150), color=(120, 80, 40), fmt="PNG", quality=None, exif=None):
    img = Image.new("RGB", size, color)
    arr = np.asarray(img).copy()
    arr[:, :, 0] = (np.arange(size[1])[:, None] * 3 % 256).astype(np.uint8)
    arr[50:100, 40:120] = (220, 30, 30)
    img = Image.fromarray(arr)
    import io
    buf = io.BytesIO()
    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality or 85
    if exif is not None:
        save_kwargs["exif"] = exif
    img.save(buf, format=fmt, **save_kwargs)
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    return out


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata_reads_exif_facts():
    exif = Image.Exif()
    exif[271] = "Canon"
    exif[272] = "EOS 5D"
    exif[306] = "2024:05:01 10:00:00"
    img = _image(fmt="JPEG", exif=exif.tobytes())
    card = F.scan_metadata(img, None)
    assert card["status"] == "ok"
    assert card["data"]["exif"]["make"] == "Canon"
    assert card["data"]["exif"]["datetime"].startswith("2024")
    assert card["flag"] is False          # no generator signature
    assert card["vote_capable"] is True


def test_metadata_flags_generator_signature_in_bytes():
    raw = b"\x89PNG\r\n\x1a\n" + b"some chunk Midjourney prompt metadata" + b"\x00" * 32
    card = F.scan_metadata(_image(), raw)
    assert card["status"] == "ok"
    assert card["flag"] is True
    assert card["data"]["generator_signatures"]


def test_metadata_without_exif_still_ok():
    card = F.scan_metadata(_image(fmt="PNG"), None)
    assert card["status"] == "ok"
    assert card["data"]["exif_present"] is False


# ---------------------------------------------------------------------------
# JPEG quality
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quality", [40, 60, 85])
def test_jpeg_quality_estimate_close_to_true(quality):
    img = _image(fmt="JPEG", quality=quality)
    est = F.estimate_jpeg_quality(img)
    assert est is not None
    assert abs(est - quality) <= 15  # classic estimator, loose tolerance


def test_jpeg_check_not_applicable_for_png():
    card = F.check_jpeg(_image(fmt="PNG"))
    assert card["status"] == "not_applicable"
    assert "not JPEG" in card["reason"]


# ---------------------------------------------------------------------------
# Hashes + known-forgery DB
# ---------------------------------------------------------------------------

def test_hashes_deterministic_and_discriminative():
    a = _image()
    assert F.phash_hex(a) == F.phash_hex(a)
    assert F.dhash_hex(a) == F.dhash_hex(a)
    assert len(F.phash_hex(a)) == 16 and len(F.dhash_hex(a)) == 16

    other = _image(color=(5, 250, 100), size=(300, 90))
    assert F.hamming(F.phash_hex(a), F.phash_hex(other)) > 8
    assert F.hamming(F.dhash_hex(a), F.dhash_hex(other)) > 8
    assert F.hamming(F.phash_hex(a), F.phash_hex(a)) == 0


def test_lookup_requires_both_hashes(tmp_path):
    a, b = _image(), _image(color=(10, 200, 5), size=(240, 120))
    db = [
        # phash matches a, dhash matches b -> must NOT match either fully
        {"id": "x", "label": "AI Detected", "phash": F.phash_hex(a), "dhash": F.dhash_hex(b)},
    ]
    assert F.lookup_forgery(F.phash_hex(a), F.dhash_hex(a), db, max_hamming=4) is None
    # exact entry matches
    db = [{"id": "y", "label": "AI Detected", "phash": F.phash_hex(a), "dhash": F.dhash_hex(a)}]
    match = F.lookup_forgery(F.phash_hex(a), F.dhash_hex(a), db, max_hamming=4)
    assert match is not None
    assert match["hamming"] == 0
    # too far on one hash
    assert F.lookup_forgery(F.phash_hex(a), F.dhash_hex(b), db, max_hamming=4) is None


def test_forgery_db_loader_handles_missing_and_bad(tmp_path):
    assert F.load_forgery_db(str(tmp_path / "nope.json")) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert F.load_forgery_db(str(bad)) == []


def test_hash_check_produces_settle_when_db_matches(tmp_path, monkeypatch):
    a = _image()
    db_path = tmp_path / "db.json"
    import json
    db_path.write_text(json.dumps({"entries": [
        {"id": "e1", "label": "AI Detected", "phash": F.phash_hex(a),
         "dhash": F.dhash_hex(a), "reference": "unit-test"}
    ]}), encoding="utf-8")
    monkeypatch.setattr(settings, "FORGERY_DB_PATH", str(db_path))
    card = F.check_hashes(a)
    assert card["status"] == "ok"
    assert card["data"]["match"] is not None
    settle = card["data"]["settle"]
    assert settle["phash_match"] and settle["dhash_match"]
    assert settle["entry_label"] == "AI Detected"
    assert settle["hamming"] == 0
    assert card["vote_capable"] is False  # settle goes through direct-settle, not k-of-N


def test_hash_check_empty_db_reports_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "FORGERY_DB_PATH", str(tmp_path / "none.json"))
    card = F.check_hashes(_image())
    assert card["status"] == "ok"
    assert card["data"]["db_entries"] == 0
    assert card["data"]["match"] is None
    assert "settle" not in card["data"]


# ---------------------------------------------------------------------------
# QR + info-only checks
# ---------------------------------------------------------------------------

def test_qr_check_runs_and_reports_honestly():
    card = F.check_qr(_image())
    assert card["status"] == "ok"
    assert card["data"]["found"] is False   # no QR in a synthetic gradient
    assert card["vote_capable"] is False


@pytest.mark.parametrize("fn,check_id", [
    (F.check_vanishing, "vanishing"),
    (F.check_shadows, "shadows"),
    (F.check_fft, "fft"),
])
def test_info_only_checks_never_vote(fn, check_id):
    card = fn(_image(size=(320, 240)))
    assert card["status"] == "ok"
    assert card["id"] == check_id
    assert card["vote_capable"] is False
    assert card["flag"] is None           # measurement only, no invented threshold
    assert card["data"] is not None


def test_watermark_skipped_without_templates(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WATERMARK_TEMPLATES_DIR", str(tmp_path / "empty"))
    card = F.check_watermark(_image())
    assert card["status"] == "skipped"
    assert "template" in card["reason"].lower()


# ---------------------------------------------------------------------------
# Orchestrator + technical info
# ---------------------------------------------------------------------------

def test_run_forensics_returns_all_checks_with_valid_states():
    result = F.run_forensics(_image(fmt="JPEG"), b"\x89PNG\r\n")
    ids = [c["id"] for c in result["checks"]]
    assert ids == F.CHECK_ORDER
    assert result["state"] == "ok"
    assert isinstance(result["total_ms"], int)
    for card in result["checks"]:
        assert card["status"] in ("ok", "not_applicable", "skipped", "error")
        if card["status"] == "skipped":
            assert card["reason"]
        if card["status"] == "error":
            assert card["error"]


def test_run_forensics_survives_a_crashing_check(monkeypatch):
    def boom(_img):
        raise RuntimeError("sabotaged")
    monkeypatch.setattr(F, "check_qr", boom)
    result = F.run_forensics(_image())
    ids = [c["id"] for c in result["checks"]]
    assert ids == F.CHECK_ORDER            # full plan preserved
    qr = next(c for c in result["checks"] if c["id"] == "qr")
    assert qr["status"] == "error" and "sabotaged" in qr["error"]
    others = [c for c in result["checks"] if c["id"] != "qr"]
    assert all(c["status"] != "error" for c in others)


def test_technical_info_facts():
    img = _image(size=(640, 480), fmt="JPEG", quality=75)
    info = F.build_technical_info(img, b"x" * 1234)
    assert info["state"] == "ok"
    data = info["data"]
    assert data["dimensions"] == {"width": 640, "height": 480}
    assert data["format"] == "JPEG"
    assert data["size_bytes"] == 1234
    assert data["aspect_ratio"] == "4:3"
    assert data["jpeg_quality_estimate"] is not None
    assert data["color_profile"] in ("ICC profile present", "No ICC profile")


def test_technical_info_png_has_no_quality_estimate():
    info = F.build_technical_info(_image(fmt="PNG"))
    assert info["state"] == "ok"
    assert info["data"]["jpeg_quality_estimate"] is None
