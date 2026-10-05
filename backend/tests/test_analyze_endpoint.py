"""m3 — /api/v1/analyze endpoint + legacy /api/v1/detect compatibility."""

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.analysis_schema import SCHEMA_VERSION, VERDICT_LABELS, validate_analysis
from app.config import settings
from app.main import app

client = TestClient(app)

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_PNG = os.path.abspath(os.path.join(_HERE, "..", "..", "news_test.png"))  # repo root
ASSET_JPG = os.path.join(_HERE, "assets", "salman_recompressed_real.jpg")

# Exact legacy response contract — must never drift.
LEGACY_KEYS = {
    "status", "verdict", "provenance", "real_prob", "fake_prob", "confidence",
    "quality", "arbiter_audit", "multi_aspect_scores", "forensic_analysis",
    "report_id",
}


def _upload(path):
    with open(path, "rb") as fh:
        return {"file": (os.path.basename(path), fh.read(), "application/octet-stream")}


# ---------------------------------------------------------------------------
# New full-analysis endpoint
# ---------------------------------------------------------------------------

def test_analyze_returns_valid_schema_record():
    resp = client.post("/api/v1/analyze", files=_upload(ASSET_PNG))
    assert resp.status_code == 200, resp.text
    record = resp.json()
    assert record["schema_version"] == SCHEMA_VERSION
    assert validate_analysis(record) == []

    # verdict card honest under test isolation (no models loaded)
    verdict = record["verdict"]
    assert verdict["state"] == "ok"
    assert verdict["label"] in VERDICT_LABELS
    assert verdict["why_rule"]["en"] and verdict["why_rule"]["ar"]
    assert verdict["reasoning"]["en"] and verdict["reasoning"]["ar"]
    assert [a["id"] for a in verdict["axes"]] == ["ai_generation", "editing_check", "source_check"]

    # four model entries with honest statuses
    assert len(record["models"]) == 4
    for model in record["models"]:
        assert model["status"] in ("ok", "error", "skipped")
        if model["status"] == "skipped":
            assert model["reason"]
        if model["status"] == "error":
            assert model["error"]


def test_analyze_runs_all_forensic_checks():
    resp = client.post("/api/v1/analyze", files=_upload(ASSET_JPG))
    assert resp.status_code == 200, resp.text
    record = resp.json()
    check_ids = [c["id"] for c in record["forensics"]["checks"]]
    assert set(check_ids) >= {"exif", "ela", "jpeg_quality", "hash_db", "qr", "c2pa"}
    for check in record["forensics"]["checks"]:
        assert check["status"] in ("ok", "not_applicable", "skipped", "error")
        assert check["why_en"] and check["why_ar"]

    # pipeline steps timed
    assert record["pipeline"]
    for step in record["pipeline"]:
        assert step["status"] in ("ok", "error")
        assert isinstance(step["duration_ms"], int)

    # technical info present
    assert record["technical_info"]["state"] == "ok"
    assert record["technical_info"]["data"]["dimensions"]["width"] > 0

    # unimplemented sections are honestly skipped, not fake-loading
    assert record["sections"]["spot_the_difference"]["state"] == "skipped"
    assert record["sections"]["spot_the_difference"]["reason"]
    assert record["sections"]["model_scores"]["state"] in ("ok", "error")


def test_analyze_rejects_non_image():
    resp = client.post(
        "/api/v1/analyze",
        files={"file": ("fake.png", b"this is definitely not an image", "image/png")},
    )
    assert resp.status_code == 400
    assert "decodable image" in resp.json()["detail"]


def test_analyze_enforces_size_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    payload = b"\x89PNG\r\n" + b"\x00" * (2 * 1024 * 1024)
    resp = client.post(
        "/api/v1/analyze",
        files={"file": ("big.png", payload, "image/png")},
    )
    assert resp.status_code == 413


def test_analyze_enforces_pixel_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_IMAGE_PIXELS", 1000)
    resp = client.post("/api/v1/analyze", files=_upload(ASSET_PNG))
    assert resp.status_code == 413
    assert "decompression-bomb" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Legacy endpoint compatibility (constant: same response shape + values)
# ---------------------------------------------------------------------------

def test_legacy_detect_shape_and_values_unchanged():
    resp = client.post("/api/v1/detect", files=_upload(ASSET_PNG))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data.keys()) == LEGACY_KEYS
    assert data["status"] == "success"
    # Models are blocked in tests (neutral 0.5 votes) -> the calibrated
    # classifier honestly lands in the uncertain band; the shape and key set
    # are what this contract locks.
    assert data["verdict"] == "uncertain"
    assert data["real_prob"] == 0.5 and data["fake_prob"] == 0.5
    assert isinstance(data["arbiter_audit"], list)
    assert data["report_id"].endswith(".pdf")
