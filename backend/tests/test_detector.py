"""Unit tests for the v3 detection engine (pure logic, no real models).

Covers: label matching polarity, broken-vote neutralization, geometric-mean
behavior, C2PA floor anchoring, verdict bands, metadata-segment extraction
(JPEG/PNG/WebP), and provenance scanning on real vs synthetic metadata.
"""
import io
import struct

import numpy as np
import pytest
from PIL import Image

import app.services.detector as det


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

class _FakePipeline:
    """Mimics the transformers image-classification pipeline interface."""

    def __init__(self, predictions, name="fake/model", raise_exc=False):
        self._predictions = predictions
        self._raise = raise_exc
        self.model = type("M", (), {"name_or_path": name})()

    def __call__(self, img):
        if self._raise:
            raise RuntimeError("inference exploded")
        return self._predictions


def _solid_png_bytes(color=(120, 120, 120), size=(64, 48)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Label matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "preds,expected_fake",
    [
        ([{"label": "Deepfake", "score": 0.8}, {"label": "Realism", "score": 0.2}], 0.8),
        ([{"label": "artificial", "score": 0.7}, {"label": "human", "score": 0.3}], 0.7),
        # exact "ai" class and "ai "-prefixed classes count as fake
        ([{"label": "ai", "score": 0.6}, {"label": "real", "score": 0.4}], 0.6),
        ([{"label": "ai generated", "score": 0.9}, {"label": "original", "score": 0.1}], 0.9),
        # unknown labels contribute nothing -> neutral fallback
        ([{"label": "label_0", "score": 0.5}, {"label": "label_1", "score": 0.5}], None),
    ],
)
def test_label_probs_polarity(preds, expected_fake):
    pipe = _FakePipeline(list(preds))
    fake, real = det._label_probs(pipe, Image.new("RGB", (8, 8)))
    if expected_fake is None:
        assert fake == 0.5 and real == 0.5
    else:
        assert fake == pytest.approx(expected_fake)
        assert real == pytest.approx(1.0 - expected_fake)


def test_label_probs_neutral_on_inference_error():
    pipe = _FakePipeline([], raise_exc=True)
    fake, real = det._label_probs(pipe, Image.new("RGB", (8, 8)))
    assert fake == 0.5 and real == 0.5


# ---------------------------------------------------------------------------
# Geometric-mean ensemble behavior
# ---------------------------------------------------------------------------

def _votes_mean(votes):
    """Mirror the production geometric mean over a vote list."""
    log_sum = sum(np.log(max(v, det.FAKE_PROB_FLOOR)) for v in votes)
    return float(np.exp(log_sum / len(votes)))


def test_single_loud_vote_cannot_condemn():
    # One model screams fake while the others lean real -> ensemble must stay
    # in the real/uncertain region, far from a confident condemnation.
    assert _votes_mean([0.99, 0.2, 0.2]) < det.VERDICT_REAL_THRESHOLD
    # Even two fully neutral (broken -> 0.5) votes cannot push one loud vote
    # beyond the strong-fake region.
    assert _votes_mean([0.99, 0.5, 0.5]) < 0.65


def test_agreed_votes_keep_fake_high():
    p = _votes_mean([0.95, 0.90, 0.97])
    assert p > 0.60


def test_votes_at_floor_stay_low():
    p = _votes_mean([0.02, 0.02, 0.02])
    assert p == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# Verdict bands
# ---------------------------------------------------------------------------

def test_verdict_bands():
    # Calibrated 2026-09-29: FAKE threshold raised to 0.70 so heavily
    # recompressed real photos (~0.66) land in honest-review territory.
    assert det.classify_verdict(0.92) == "fake"   # provenance-anchored
    assert det.classify_verdict(0.87) == "fake"   # strong ensemble fake (Flux)
    assert det.classify_verdict(0.71) == "fake"
    assert det.classify_verdict(0.66) == "uncertain"  # recompressed real portrait
    assert det.classify_verdict(0.55) == "uncertain"
    assert det.classify_verdict(0.46) == "uncertain"
    assert det.classify_verdict(0.44) == "real"
    assert det.classify_verdict(0.05) == "real"


# ---------------------------------------------------------------------------
# Metadata segment extraction
# ---------------------------------------------------------------------------

def _jpeg_with_com(comment: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")                     # SOI
    out += b"\xff\xe0\x00\x10" + b"JFIF\x00" + bytes(9)  # minimal APP0
    payload = comment
    out += b"\xff\xfe" + struct.pack(">H", len(payload) + 2) + payload  # COM
    out += b"\xff\xda\x00\x02" + b"\x01\x00" + b"\x00" * 8 + b"\xff\xd9"  # SOS stub + EOI
    return bytes(out)


def test_jpeg_com_segment_extracted():
    raw = _jpeg_with_com(b"hello world")
    segs = det._extract_metadata_segments(raw)
    assert any(b"hello world" in s for s in segs)


def test_jpeg_scanline_noise_not_scanned():
    # b"openai" buried AFTER SOS (entropy-coded data) must not be found
    raw = _jpeg_with_com(b"clean comment") + b"\x00" * 16 + b"openai"
    hit, detail = det.provenance_scan_bytes(raw)
    assert hit is False and detail == ""


def test_png_text_chunk_extracted():
    keyword = b"Comment\x00"
    text = b"generated by chatgpt"
    chunk_data = keyword + text
    raw = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(chunk_data)) + b"tEXt" + chunk_data
        + struct.pack(">I", 0)  # CRC placeholder
    )
    segs = det._extract_metadata_segments(raw)
    assert any(b"chatgpt" in s for s in segs)
    hit, detail = det.provenance_scan_bytes(raw)
    assert hit is True and detail.lower() == "chatgpt"


def test_webp_xmp_chunk_extracted():
    xmp = b"<x:xmpmeta>FLUX manifest</x:xmpmeta>"
    raw = (
        b"RIFF" + struct.pack("<I", 12 + 8 + len(xmp)) + b"WEBP"
        + b"XMP " + struct.pack("<I", len(xmp)) + xmp
    )
    segs = det._extract_metadata_segments(raw)
    assert any(b"FLUX" in s for s in segs)


def test_unknown_container_bounded_head_window():
    raw = b"\x00" * 300_000 + b"midjourney"  # signature deep in the tail
    hit, _ = det.provenance_scan_bytes(raw)
    assert hit is False


def test_c2pa_is_decisive_even_outside_metadata_segments():
    # C2PA manifests live in binary chunks (e.g. PNG caBX) our segment
    # walker may not collect; the hard tier scans full raw bytes so the
    # verified v3 behavior (ChatGPT-edited PNG => c2pa) cannot regress.
    raw = b"\x00" * 200_000 + b"urn:c2pa:manifest" + b"\x00" * 100
    hit, detail = det.provenance_scan_bytes(raw)
    assert hit is True and detail == "c2pa"


def test_generator_name_in_pixel_data_does_not_condemn():
    # "openai" inside the compressed pixel stream (after SOS) must NOT hit:
    # only metadata segments legitimize generator-name signatures.
    raw = _jpeg_with_com(b"innocent comment") + b"\x00" * 64 + b"chatgpt openai"
    hit, _ = det.provenance_scan_bytes(raw)
    assert hit is False


# ---------------------------------------------------------------------------
# Provenance anchoring in the full pipeline
# ---------------------------------------------------------------------------

def test_c2pa_hit_anchors_fake_prob():
    img = Image.new("RGB", (32, 32), (90, 90, 90))
    keyword = b"Standard\x00"
    payload = keyword + b"urn:c2pa:manifest"
    raw = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(payload)) + b"tEXt" + payload + struct.pack(">I", 0)
    )

    real_prob, fake_prob, confidence, metrics = det.analyze_image_forgery(img, raw_bytes=raw)

    assert fake_prob >= det.C2PA_FAKE_FLOOR
    assert real_prob == pytest.approx(1.0 - fake_prob)
    assert confidence == pytest.approx(max(fake_prob, real_prob))
    assert det.last_provenance_hit() == "c2pa"
    # real five-key metric contract for the frontend
    assert set(metrics.keys()) == {
        "lighting", "texture", "color_consistency", "background_artifacts", "facial_distortion"
    }
    for v in metrics.values():
        assert det.METRIC_MIN <= v <= det.METRIC_MAX


def test_clean_image_no_provenance_hit():
    img_bytes = _solid_png_bytes()
    img = Image.open(io.BytesIO(img_bytes))
    real_prob, fake_prob, _, metrics = det.analyze_image_forgery(img, raw_bytes=img_bytes)
    assert det.last_provenance_hit() == ""
    # No models loaded (conftest) -> neutral 0.5, no false condemnation
    assert fake_prob == pytest.approx(0.5)
    # imagenette-unique helper always returns the five-key dict when models absent
    assert isinstance(metrics, dict) and set(metrics.keys()) == {
        "lighting", "texture", "color_consistency", "background_artifacts", "facial_distortion"
    }
    # analyze_image_forgery returns a 4-tuple; lap_var surfaces via the quality gate
    assert isinstance(det.last_quality()["sharpness"], (int, float))


# ---------------------------------------------------------------------------
# Quality gate (per user request: minimum specimen quality regime)
# ---------------------------------------------------------------------------

def test_quality_gate_flags_extreme_compression():
    # The King-Salman case: 1200x800 at 44KB => ~0.37 bpp -> at least degraded
    img = Image.new("RGB", (1200, 800), (90, 90, 90))
    q = det.assess_image_quality(img, lap_var=100.0, file_size=44_359)
    assert q["tier"] in ("degraded", "poor")
    assert any("compression" in n for n in q["notes"])
    assert q["bits_per_pixel"] < det.QUALITY_BPP_GOOD


def test_quality_gate_good_specimen():
    img = Image.new("RGB", (1200, 900), (90, 90, 90))
    q = det.assess_image_quality(img, lap_var=200.0, file_size=1_500_000)
    assert q["tier"] == "good"
    assert q["notes"] == []


def test_calibrated_thresholds_by_tier():
    # good tier: 0.71 condemns; degraded: 0.71 stays review; poor: 0.76 review
    assert det.classify_verdict_calibrated(0.71, "good") == "fake"
    assert det.classify_verdict_calibrated(0.71, "degraded") == "uncertain"
    assert det.classify_verdict_calibrated(0.76, "degraded") == "fake"
    assert det.classify_verdict_calibrated(0.76, "poor") == "uncertain"
    assert det.classify_verdict_calibrated(0.81, "poor") == "fake"
    assert det.classify_verdict_calibrated(0.40, "poor") == "real"


# ---------------------------------------------------------------------------
# Arbiter fusion
# ---------------------------------------------------------------------------

def test_arbiter_demotes_face_vote_without_face():
    votes = {"face_v2": 0.9, "sdxl": 0.2, "commfor": 0.2}
    p_no_face, audit1 = det._arbiter_fuse(votes, "good", face_present=False)
    p_face, audit2 = det._arbiter_fuse(votes, "good", face_present=True)
    assert p_no_face < p_face  # demoted shaky loud vote
    assert any("face_v2" in a for a in audit1)


def test_arbiter_reports_disagreement():
    votes = {"face_v2": 0.95, "sdxl": 0.10, "commfor": 0.15}
    _, audit = det._arbiter_fuse(votes, "good", face_present=True)
    assert any("DISAGREEMENT" in a for a in audit)


def test_arbiter_reports_consensus():
    votes = {"face_v2": 0.9, "sdxl": 0.85, "commfor": 0.88}
    p, audit = det._arbiter_fuse(votes, "good", face_present=True)
    assert any("consensus" in a for a in audit)
    assert p > 0.7


# ---------------------------------------------------------------------------
# Forensic metrics sanity
# ---------------------------------------------------------------------------

def test_metrics_realistic_on_natural_gradient():
    # Smooth vertical gradient: ELA should be tiny, edges coherent
    arr = np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (96, 1))
    img = Image.fromarray(np.stack([arr] * 3, axis=-1), mode="RGB")
    metrics, lap_var = det._compute_forensic_metrics(img)
    assert metrics["lighting"] < 50.0       # smooth image -> low ELA energy
    assert metrics["background_artifacts"] < 60.0
    assert lap_var < det.QUALITY_SHARP_GOOD  # smooth => low sharpness energy
    assert all(det.METRIC_MIN <= v <= det.METRIC_MAX for v in metrics.values())


def test_metrics_flag_noisy_synthetic():
    # High-frequency noise: ELA and texture energy must spike
    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    metrics, lap_var = det._compute_forensic_metrics(img)
    assert metrics["texture"] > 60.0
    assert lap_var > det.QUALITY_SHARP_GOOD  # noisy => sharp by proxy
