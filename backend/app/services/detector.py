import logging
import os
import io
import struct
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple, Union

from app.config import settings

logger = logging.getLogger(__name__)

# Decision thresholds (tuned to cut false positives on real photos):
#   fake > 0.70 -> "fake"
#   fake < 0.45 -> "real"
#   otherwise   -> "uncertain" (human review recommended)
#
# Calibrated 2026-09-29: heavily-recompressed real photos (e.g. an official
# portrait at 0.37 bits/pixel) land ~0.66 — compression wipes sensor noise
# and the face specialist misreads smoothness as GAN artifacts. The 0.60-0.70
# zone is therefore honest-review territory, not condemnation. Confirmed fakes
# are unaffected: provenance-anchored media sits at >= 0.92, strong ensemble
# fakes (Flux) at ~0.87.
VERDICT_FAKE_THRESHOLD = 0.70
VERDICT_REAL_THRESHOLD = 0.45

# Quality-gated thresholds: low-quality uploads wipe sensor noise, so the
# condemnation bar rises instead of trusting shaky votes. Recompressed real
# portraits (0.37 bpp) measured ~0.66; strong fakes sit >= 0.87, so there is
# wide safe margin on both sides.
QUALITY_TIER_THRESHOLDS = {"good": 0.70, "degraded": 0.75, "poor": 0.80}
# bits/pixel floors (JPEG-grade heuristics): below these, forensic texture
# cues are unreliable.
QUALITY_BPP_GOOD = 1.2
QUALITY_BPP_DEGRADED = 0.55
QUALITY_MIN_SIDE_GOOD = 480
QUALITY_MIN_SIDE_DEGRADED = 260
QUALITY_SHARP_GOOD = 55.0    # Laplacian variance on grayscale
QUALITY_SHARP_DEGRADED = 18.0

# Label keywords per polarity. The exact "ai" class (3-class models) is
# matched first; substring matching then covers binary-model labels.
FAKE_LABELS = ["ai", "deepfake", "artificial", "fake", "generated", "synthesized", "spoof", "manipulated"]
REAL_LABELS = ["realism", "real", "human", "natural", "original", "bonafide", "authentic"]

FAKE_PROB_FLOOR = 0.02  # numerical floor so geometric mean never collapses to 0

# Provenance signature bytes that identify AI-generated media at the file
# level. Hard standard signatures (C2PA/JUMBF/SynthID) are decisive evidence:
# OpenAI (ChatGPT/DALL-E), Adobe Firefly, Google (SynthID) and others embed
# signed provenance manifests directly in the file. Generator-name signatures
# are treated as provenance evidence only when found inside real metadata
# segments (see _extract_metadata_segments).
AI_PROVENANCE_SIGNATURES = [b"c2pa", b"C2PA", b"jumbf", b"JUMBF", b"synthid", b"SynthID"]
AI_GENERATOR_SIGNATURES = [
    b"openai", b"OpenAI", b"DALL", b"chatgpt", b"ChatGPT", b"StableDiffusion",
    b"stability.ai", b"midjourney", b"Midjourney", b"Adobe Firefly", b"firefly",
    b"Gemini", b"Imagen", b"FLUX", b"black-forest-labs",
]
C2PA_FAKE_FLOOR = 0.92  # provenance hit pushes fake probability at least here

# ---- BlazeFace face detection (mediapipe 1.x tasks API) --------------------
BLAZEFACE_MODEL = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "blaze_face_short_range.tflite")
)
FACE_MARGIN = 0.25          # extra crop margin around the detected face box
FACE_MIN_DETECTION_CONF = 0.4
FACE_MIN_SIZE = 224         # don't feed v2 a crop smaller than this

# ---- Real forensic metrics configuration -----------------------------------
ELA_QUALITY = 90            # JPEG requantize quality for Error Level Analysis
METRIC_MIN, METRIC_MAX = 10.0, 99.0

# Thread-safe-ish single-slot provenance result for the API layer
_PROVENANCE_RESULT: str = ""
# Single-slot arbiter audit + quality gate results for the API layer
_LAST_AUDIT: List[str] = []
_LAST_QUALITY: Dict = {}
_LAST_FACE_FOUND: bool = False
# Per-detector fake probabilities from the last analysis. Read-only side
# channel for scoring/calibration (m2/m4); fusion behavior is untouched.
_LAST_VOTES: Dict[str, float] = {}


def last_votes() -> Dict[str, float]:
    """Per-detector fake probabilities observed in the last analysis.

    Detectors that did not vote (failed to load / errored) are absent from
    the mapping. Adding this stash cannot change any model output: it only
    copies the dict the arbiter already consumed.
    """
    return _LAST_VOTES


def last_audit() -> List[str]:
    """Human-readable arbiter notes from the last analysis."""
    return _LAST_AUDIT


def last_quality() -> Dict:
    """Quality-gate assessment of the last analyzed specimen."""
    return _LAST_QUALITY


# ============================================================================
# Provenance scanning (metadata-segment scoped)
# ============================================================================

def _extract_metadata_segments(raw: bytes) -> List[bytes]:
    """Extract only metadata-carrying byte segments from an image file.

    Matching inside EXIF/XMP/comment/text chunks rather than the whole file
    means a pixel dump or random filename that happens to contain e.g.
    b"openai" can no longer produce a false provenance condemnation.
    """
    segments: List[bytes] = []

    # JPEG: walk markers; collect COM and APPn payload segments
    if raw[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 <= len(raw):
            if raw[pos] != 0xFF:
                break
            marker = raw[pos + 1]
            if marker == 0xD9:            # EOI - stop walking
                break
            if 0xD0 <= marker <= 0xD7:    # standalone RST markers
                pos += 2
                continue
            if marker in (0x01, 0xDA):    # TEM / SOS: entropy-coded data follows
                break
            seg_len = struct.unpack(">H", raw[pos + 2:pos + 4])[0]
            payload = raw[pos + 4:pos + 2 + seg_len]
            if marker == 0xFE or 0xE0 <= marker <= 0xEF:  # COM / APPn
                segments.append(payload)
            pos += 2 + seg_len
        return segments

    # PNG: 8-byte signature then chunks; collect tEXt / iTXt / zTXt
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        pos = 8
        while pos + 8 <= len(raw):
            length = struct.unpack(">I", raw[pos:pos + 4])[0]
            ctype = raw[pos + 4:pos + 8]
            if length > len(raw) - pos:
                break
            if ctype in (b"tEXt", b"iTXt", b"zTXt", b"caBX", b"eXIf"):
                segments.append(raw[pos + 8:pos + 8 + length])
            pos += 8 + length + 4  # header + data + CRC
        return segments

    # WebP: RIFF container; grab XMP and EXIF chunks
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        pos = 12
        while pos + 8 <= len(raw):
            fourcc = raw[pos:pos + 4]
            size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
            if size > len(raw) - pos:
                break
            if fourcc in (b"XMP ", b"EXIF", b"caBX"):
                segments.append(raw[pos + 8:pos + 8 + size])
            pos += 8 + size + (size & 1)  # chunks are even-padded
        return segments

    # Unknown container: bounded head window only (manifests live in header
    # metadata blocks, not deep in pixel data).
    segments.append(raw[:256 * 1024])
    return segments


def scan_ai_provenance(image_input: Union[str, Image.Image]) -> Tuple[bool, str]:
    """Scan metadata segments of the original file bytes for provenance signatures.

    Returns (hit, detail). Hard signatures (C2PA/JUMBF/SynthID) stay decisive:
    a hit inside any metadata segment condemns regardless of pixel editing.
    Generator-name signatures (openai/chatgpt/...) also require a metadata-
    segment context, so plain pixel data cannot trigger them. The ChatGPT-
    edited PNG (c2pa manifest in an iTXt chunk) remains verified.
    """
    path = None
    if isinstance(image_input, str):
        path = image_input
    elif isinstance(image_input, Image.Image):
        path = getattr(image_input, "filename", None)
        if path and not os.path.exists(path):
            path = None
    if not path:
        return False, ""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(16 * 1024 * 1024)
    except Exception as read_err:
        logger.warning("Provenance scan failed to read %s: %s", path, read_err)
        return False, ""
    return provenance_scan_bytes(raw)


def provenance_scan_bytes(raw: bytes) -> Tuple[bool, str]:
    """Provenance scan over an in-memory upload payload.

    Two-tier policy:
    - Hard standard signatures (C2PA/JUMBF/SynthID) are scanned against the
      FULL raw bytes: they are binary manifest standards, accidental pixel-
      data collisions are implausible, and they must stay decisive exactly
      as verified in the v3 live matrix (ChatGPT-edited PNG => c2pa hit).
    - Generator-name signatures (openai/chatgpt/...) require a real metadata
      segment (EXIF/XMP/text/caBX chunks), so a stray name in pixel data or
      a filename cannot condemn a clean image.
    """
    if not raw:
        return False, ""
    for sig in AI_PROVENANCE_SIGNATURES:
        if sig in raw:
            return True, sig.decode("latin1")
    segments = _extract_metadata_segments(raw)
    for sig in AI_GENERATOR_SIGNATURES:
        for seg in segments:
            if sig in seg:
                return True, sig.decode("latin1")
    return False, ""


def last_provenance_hit() -> str:
    """Return a human-readable provenance detail from the last analysis."""
    return _PROVENANCE_RESULT


# ============================================================================
# Detector loading (v3 ensemble: unchanged voting logic)
# ============================================================================

def _load_detector(model_id: str):
    try:
        logger.info("Loading AI deepfake detector: %s ...", model_id)
        detector = pipeline("image-classification", model=model_id)
        logger.info("Detector loaded successfully: %s", model_id)
        return detector
    except Exception as e:
        logger.error("Failed to load detector %s: %s", model_id, e)
        return None


def load_advanced_detector():
    return _load_detector(settings.DETECTOR_MODEL_ID)


def load_secondary_detector():
    if not getattr(settings, "DETECTOR_ENSEMBLE_ENABLED", False):
        return None
    return _load_detector(settings.DETECTOR_MODEL_ID_SECONDARY)


def load_quaternary_detector():
    """Fourth voter: dima806/deepfake_vs_real — compact independent ViT.

    Adds a cheap independent opinion for the arbiter; failure returns None
    and the fusion simply proceeds with the remaining voters.
    """
    if not getattr(settings, "DETECTOR_QUATERNARY_ENABLED", False):
        return None
    return _load_detector(settings.DETECTOR_MODEL_ID_QUATERNARY)


from transformers import pipeline  # noqa: E402  (import kept next to loader use)

GLOBAL_DETECTOR = load_advanced_detector()
GLOBAL_SECONDARY_DETECTOR = load_secondary_detector()
GLOBAL_QUATERNARY_DETECTOR = load_quaternary_detector()

# ---- Community Forensics (CVPR 2025) third voter ----
# ViT-small/384 trained on 4,803 generators (2.7M images); strongest open
# detector in the independent zero-shot benchmark. Loaded from local
# safetensors via timm; p_fake = sigmoid(logit).
COMMFOR_WEIGHTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "commfor_384.safetensors")
)


def _remap_commfor_keys(sd: Dict[str, "torch.Tensor"]) -> Tuple[Dict[str, "torch.Tensor"], List[str]]:
    """Align CommFor safetensors keys with the load target (idempotent).

    The weight file stores tensors under ``vit.*`` — the key naming of the
    full ``_CommForViT`` wrapper. Loading therefore MUST target the wrapper;
    targeting the inner ``vit`` submodule against these keys is what produced
    the historical "152 missing keys" (the inner module expects bare names
    like ``cls_token``, so every ``vit.*`` key is unexpected and every bare
    name missing — the file was silently only partially applied).

    Under COMMFOR_REMAP_ENABLED=True we retarget the load to the wrapper by
    returning the file's own ``vit.*`` keys unchanged (mapping is a no-op on
    an already-correct file: keys not starting with ``vit.`` are left as-is,
    ``vit.vit.*`` keys are preserved, so calling twice never double-prefixes).
    Under False we strip the ``vit.`` prefix, reproducing the legacy broken
    load (152 missing / 152 unexpected) for before/after comparison.

    Returns (state_dict_for_loader, notes). Notes record the deliberate head
    replacement (the file's 1-logit linear head over timm's 1000-class ImageNet
    head) and any key that could not be placed.
    """
    notes: List[str] = []
    out: Dict[str, "torch.Tensor"] = {}
    for k, v in sd.items():
        if k.startswith("vit.vit."):          # already wrapper-named (idempotency)
            out[k] = v
        elif k.startswith("vit."):
            out[k] = v                        # wrapper keys — keep as-is (remap target)
        else:
            notes.append(f"unprefixed key kept as-is: {k}")
            out[k] = v
    if "vit.head.weight" in out and "vit.head.bias" in out:
        notes.append(
            "head replaced deliberately: file's 1-logit linear head loaded "
            "in place of timm's 1000-class ImageNet head"
        )
    return out, notes


def _legacy_commfor_keys(sd: Dict[str, "torch.Tensor"]) -> Dict[str, "torch.Tensor"]:
    """Reproduce the pre-fix broken keying (strip ``vit.``) for REMAP=off.

    The legacy code loaded the file into the inner ``vit`` submodule while the
    file keys were wrapper-named, so nothing matched (152 missing / 152
    unexpected) and the effective weights stayed random-init. Stripping the
    prefix here is what the legacy loader effectively needed — but since it
    never did this, REMAP=off must produce the SAME numerical behavior as
    before the fix: load into the inner submodule with wrapper-named keys.
    We therefore return the dict unchanged; the caller chooses the load target.
    """
    return dict(sd)


def load_commfor_detector():
    try:
        if not os.path.exists(COMMFOR_WEIGHTS):
            logger.warning("Community Forensics weights not found at %s", COMMFOR_WEIGHTS)
            return None
        import torch
        import torch.nn as nn
        import timm
        from safetensors.torch import load_file
        import torchvision.transforms as transforms

        class _CommForViT(nn.Module):
            def __init__(self):
                super().__init__()
                self.vit = timm.create_model(
                    "vit_small_patch16_384.augreg_in21k_ft_in1k", pretrained=False
                )
                self.vit.head = nn.Linear(in_features=384, out_features=1, bias=True)
                self.pre = transforms.Compose([
                    transforms.Resize(440),
                    transforms.CenterCrop(384),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ])

            def prob_fake(self, pil_img: Image.Image) -> float:
                x = self.pre(pil_img.convert("RGB")).unsqueeze(0)
                with torch.no_grad():
                    return float(torch.sigmoid(self.vit(x)).item())

            def logit(self, pil_img: Image.Image) -> float:
                x = self.pre(pil_img.convert("RGB")).unsqueeze(0)
                with torch.no_grad():
                    return float(self.vit(x).reshape(-1)[0].item())

        model = _CommForViT()
        sd = load_file(COMMFOR_WEIGHTS)
        if settings.COMMFOR_REMAP_ENABLED:
            # Correct path: load the wrapper-named file into the WRAPPER.
            sd, remap_notes = _remap_commfor_keys(sd)
            for note in remap_notes:
                logger.info("CommFor remap: %s", note)
            missing, unexpected = model.load_state_dict(sd, strict=False)
        else:
            # Legacy path (REMAP=off): exact pre-fix behavior — wrapper-named
            # keys loaded into the inner vit submodule => 152/152 mismatch,
            # random-init weights. Kept only for before/after comparison.
            sd = _legacy_commfor_keys(sd)
            missing, unexpected = model.vit.load_state_dict(sd, strict=False)
        if missing:
            logger.warning("CommFor load: %d missing keys (sample: %s)", len(missing), missing[:3])
        if unexpected:
            logger.warning("CommFor load: %d unexpected keys (sample: %s)", len(unexpected), unexpected[:3])
        model.eval()
        logger.info(
            "Community Forensics detector loaded from %s (remap=%s, missing=%d, unexpected=%d)",
            COMMFOR_WEIGHTS, settings.COMMFOR_REMAP_ENABLED, len(missing), len(unexpected),
        )
        return model
    except Exception as e:
        logger.error("Failed to load Community Forensics: %s", e)
        return None


GLOBAL_COMMFOR_DETECTOR = load_commfor_detector()


def _commfor_prob(model, img: Image.Image) -> float:
    """Community Forensics fake probability; 0.5 on failure (neutral vote)."""
    try:
        return model.prob_fake(img)
    except Exception as e:
        logger.error("CommFor inference error: %s", e)
        return 0.5


# ============================================================================
# BlazeFace face localization (used for the face-specialist vote only)
# ============================================================================

_FACE_DETECTOR = None
_FACE_DETECTOR_FAILED = False


def _get_face_detector():
    """Lazy-load the mediapipe tasks FaceDetector with the bundled tflite.

    Returns None on any failure so analysis falls back to the full image -
    a broken face detector must never break the ensemble.
    """
    global _FACE_DETECTOR, _FACE_DETECTOR_FAILED
    if _FACE_DETECTOR is not None or _FACE_DETECTOR_FAILED:
        return _FACE_DETECTOR
    try:
        if not os.path.exists(BLAZEFACE_MODEL):
            logger.warning("BlazeFace model not found at %s; face crop disabled", BLAZEFACE_MODEL)
            _FACE_DETECTOR_FAILED = True
            return None
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        base_opts = mp_python.BaseOptions(model_asset_path=BLAZEFACE_MODEL)
        opts = mp_vision.FaceDetectorOptions(
            base_options=base_opts,
            running_mode=mp_vision.RunningMode.IMAGE,
            min_detection_confidence=FACE_MIN_DETECTION_CONF,
        )
        _FACE_DETECTOR = mp_vision.FaceDetector.create_from_options(opts)
        logger.info("BlazeFace face detector loaded from %s", BLAZEFACE_MODEL)
    except Exception as e:
        logger.warning("BlazeFace unavailable (%s); face crop disabled", e)
        _FACE_DETECTOR_FAILED = True
        _FACE_DETECTOR = None
    return _FACE_DETECTOR


def _crop_faces(img: Image.Image) -> Tuple[Image.Image, bool]:
    """Return (face crop or original, face_found flag).

    Used for the face-deepfake specialist vote (v2): literature reports
    +5-15% on face deepfakes with tight crops. sdxl-detector and CommFor
    were trained on full scenes, so they keep the full frame. The flag lets
    the arbiter demote the face vote when no face was actually localized.
    """
    try:
        detector = _get_face_detector()
        if detector is None:
            return img, False
        import mediapipe as mp
        rgb = np.array(img.convert("RGB"))
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_img)
        if not result.detections:
            return img, False
        # Largest (highest-confidence, biggest area) detection wins
        h, w = rgb.shape[:2]
        best, best_area = None, 0.0
        for det in result.detections:
            bbox = det.bounding_box
            area = float(bbox.width) * float(bbox.height)
            score = float(getattr(det, "categories", [{}])[0].score) if getattr(det, "categories", None) else 0.5
            if area * max(score, 0.1) > best_area:
                best, best_area = bbox, area * max(score, 0.1)
        if best is None:
            return img
        x, y = float(best.origin_x), float(best.origin_y)
        bw, bh = float(best.width), float(best.height)
        mx, my = bw * FACE_MARGIN, bh * FACE_MARGIN
        left = max(0, int(x - mx))
        top = max(0, int(y - my))
        right = min(w, int(x + bw + mx))
        bottom = min(h, int(y + bh + my))
        if right - left < FACE_MIN_SIZE or bottom - top < FACE_MIN_SIZE:
            return img, False
        return img.crop((left, top, right, bottom)), True
    except Exception as e:
        logger.warning("Face crop failed (%s); using full image", e)
        return img, False


# ============================================================================
# Real forensic metrics (replace the old linear std/mean proxies)
# ============================================================================

def _clip_metric(value: float) -> float:
    return round(float(min(max(value, METRIC_MIN), METRIC_MAX)), 2)


def _ela_map(img: Image.Image) -> np.ndarray:
    """Error Level Analysis: JPEG-recompress and diff against the original."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=ELA_QUALITY)
    buf.seek(0)
    recompressed = np.array(Image.open(buf).convert("RGB"), dtype=np.float32)
    original = np.array(img.convert("RGB"), dtype=np.float32)
    return np.abs(original - recompressed)


def _laplacian_residual(gray: np.ndarray) -> np.ndarray:
    """3x3 Laplacian high-pass residual (denoising proxy)."""
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    padded = np.pad(gray, 1, mode="edge")
    stack = (
        kernel[0, 1] * padded[:-2, 1:-1]
        + kernel[1, 0] * padded[1:-1, :-2]
        + kernel[1, 1] * padded[1:-1, 1:-1]
        + kernel[1, 2] * padded[1:-1, 2:]
        + kernel[2, 1] * padded[2:, 1:-1]
    )
    return np.abs(stack)


def _edge_transition_score(gray: np.ndarray) -> float:
    """Edge sharpness/noise ratio along strong gradients (0-1, higher=cleaner)."""
    gy, gx = np.gradient(gray.astype(np.float32))
    grad_mag = np.sqrt(gx * gx + gy * gy)
    strong = grad_mag > np.percentile(grad_mag, 97)
    if not strong.any():
        return 0.5
    edge_pixels = gray[strong]
    # Clean camera edges are sharp but locally coherent; synthetic seams tend
    # to be either overly smooth or noisy. Use local std of edge magnitudes.
    local_noise = float(np.std(grad_mag[strong]))
    mean_edge = float(np.mean(edge_pixels))
    ratio = local_noise / max(mean_edge, 1.0)
    return float(np.clip(1.0 - ratio / 2.0, 0.0, 1.0))


def _compute_forensic_metrics(img: Image.Image) -> Dict[str, float]:
    """Five real forensic metrics on the 0-99 scale the frontend charts.

    Keys match frontend/components/MultiAspectChart.tsx exactly:
      lighting, texture, color_consistency, background_artifacts,
      facial_distortion.
    Semantics: HIGH = anomalous (red), LOW = nominal (green) per getStatus().
    """
    rgb = np.array(img.convert("RGB"), dtype=np.float32)
    gray = rgb.mean(axis=2)
    h, w = gray.shape

    # --- ELA (real error level analysis) ---
    ela = _ela_map(img)
    ela_mean = float(np.mean(ela))
    ela_p99 = float(np.percentile(ela, 99))

    # --- Noise residual ---
    lap = _laplacian_residual(gray)
    lap_mean = float(np.mean(lap))
    lap_std = float(np.std(lap))
    lap_var = float(np.var(lap))  # focus/sharpness proxy for quality gating

    # --- Chroma statistics ---
    cb = 0.5 * rgb[:, :, 2] - 0.419 * rgb[:, :, 0] - 0.081 * rgb[:, :, 1]
    cr = 0.5 * rgb[:, :, 0] - 0.336 * rgb[:, :, 1] - 0.169 * rgb[:, :, 2]
    chroma_var = float((np.var(cb) + np.var(cr)) / 2.0)

    # --- Lighting: ELA energy + specular highlight share ---
    specular = float(np.mean(gray > 245)) * 100.0
    lighting = 30.0 + ela_mean * 9.0 + min(specular, 30.0)

    # --- Texture: high-frequency residual energy ---
    texture = 25.0 + lap_mean * 3.2 + lap_std * 0.35

    # --- Color consistency: chroma dispersion (very low or extreme = odd) ---
    if chroma_var < 8.0:
        color_consistency = 35.0 + (8.0 - chroma_var) * 4.0
    elif chroma_var > 900.0:
        color_consistency = 35.0 + min((chroma_var - 900.0) / 60.0, 45.0)
    else:
        color_consistency = 20.0

    # --- Background artifacts: border-band ELA + edge transition sanity ---
    band = max(8, int(min(h, w) * 0.06))
    border_ela = float(np.mean(np.concatenate([ela[:band].ravel(), ela[-band:].ravel()])))
    interior_ela = float(np.mean(ela[band:-band, band:-band])) if h > 2 * band and w > 2 * band else ela_mean
    seam_ratio = border_ela / max(interior_ela, 0.05)
    edge_score = _edge_transition_score(gray)
    background_artifacts = 30.0 + max(seam_ratio - 1.0, 0.0) * 18.0 + (1.0 - edge_score) * 25.0

    # --- Facial distortion: face-region ELA focus vs global (uses BlazeFace) ---
    facial_distortion = 32.0
    face_crop = None
    try:
        detector = _get_face_detector()
        if detector is not None:
            import mediapipe as mp
            face_rgb = np.array(img.convert("RGB"))
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=face_rgb)
            res = detector.detect(mp_img)
            if res.detections:
                det = max(res.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                b = det.bounding_box
                x0 = max(0, int(b.origin_x)); y0 = max(0, int(b.origin_y))
                x1 = min(w, int(b.origin_x + b.width)); y1 = min(h, int(b.origin_y + b.height))
                if x1 - x0 > 16 and y1 - y0 > 16:
                    face_ela = float(np.mean(ela[y0:y1, x0:x1]))
                    ratio = face_ela / max(ela_mean, 0.05)
                    facial_distortion = 25.0 + max(ratio - 0.9, 0.0) * 45.0
                    face_crop = (x0, y0, x1, y1)
    except Exception as face_err:
        logger.debug("Facial metric fallback: %s", face_err)
    if face_crop is None:
        # No face detectable: fall back to center-region ELA focus
        ch, cw = h // 2, w // 2
        center_ela = float(np.mean(ela[ch - h // 4:ch + h // 4, cw - w // 4:cw + w // 4]))
        facial_distortion = 25.0 + max(center_ela / max(ela_mean, 0.05) - 0.9, 0.0) * 45.0

    return {
        "lighting": _clip_metric(lighting),
        "texture": _clip_metric(texture),
        "color_consistency": _clip_metric(color_consistency),
        "background_artifacts": _clip_metric(background_artifacts),
        "facial_distortion": _clip_metric(facial_distortion),
    }, lap_var


def assess_image_quality(img: Image.Image, lap_var: float, file_size: int = None) -> Dict:
    """Specimen quality gate: does this upload carry enough signal for a
    confident forensic verdict?

    Dimensions: resolution (min side), bits-per-pixel (compression level),
    and sharpness (Laplacian variance). Returns tier + per-axis detail.
    """
    w, h = img.size
    min_side = int(min(w, h))
    if file_size and w * h > 0:
        bpp = float(file_size * 8) / float(w * h)
    else:
        bpp = QUALITY_BPP_GOOD * 2  # unknown size: don't punish
    sharpness = float(lap_var)

    reasons: List[str] = []
    if bpp < QUALITY_BPP_DEGRADED:
        reasons.append(f"extreme compression ({bpp:.2f} bits/pixel)")
    elif bpp < QUALITY_BPP_GOOD:
        reasons.append(f"moderate compression ({bpp:.2f} bits/pixel)")
    if min_side < QUALITY_MIN_SIDE_DEGRADED:
        reasons.append(f"low resolution ({min_side}px shortest side)")
    elif min_side < QUALITY_MIN_SIDE_GOOD:
        reasons.append(f"modest resolution ({min_side}px shortest side)")
    if sharpness < QUALITY_SHARP_DEGRADED:
        reasons.append("very soft focus / heavy smoothing")
    elif sharpness < QUALITY_SHARP_GOOD:
        reasons.append("reduced sharpness")

    hard_hits = sum([
        bpp < QUALITY_BPP_DEGRADED,
        min_side < QUALITY_MIN_SIDE_DEGRADED,
        sharpness < QUALITY_SHARP_DEGRADED,
    ])
    soft_hits = sum([
        bpp < QUALITY_BPP_GOOD,
        min_side < QUALITY_MIN_SIDE_GOOD,
        sharpness < QUALITY_SHARP_GOOD,
    ])
    if hard_hits >= 1 or soft_hits >= 2:
        tier = "poor"
    elif soft_hits >= 1:
        tier = "degraded"
    else:
        tier = "good"

    return {
        "tier": tier,
        "resolution": {"width": w, "height": h, "min_side": min_side},
        "bits_per_pixel": round(bpp, 3),
        "sharpness": round(sharpness, 1),
        "notes": reasons,
    }


def classify_verdict_calibrated(fake_prob: float, quality_tier: str = "good") -> str:
    """Verdict with quality-gated condemnation bar.

    Poor specimens need stronger evidence to condemn (the compression itself
    mimmics some synthetic cues), while clean uploads use the base threshold.
    """
    threshold = QUALITY_TIER_THRESHOLDS.get(quality_tier, VERDICT_FAKE_THRESHOLD)
    if fake_prob > threshold:
        return "fake"
    if fake_prob < VERDICT_REAL_THRESHOLD:
        return "real"
    return "uncertain"


# ============================================================================
# v3 ensemble (unchanged voting logic)
# ============================================================================

def _label_probs(detector, img: Image.Image) -> Tuple[float, float]:
    """Run one detector and return (fake_prob, real_prob) normalized to sum 1.

    Accumulates all fake-ish and real-ish label scores (supports 2-class and
    3-class models), then normalizes. Returns (0.5, 0.5) on inference failure
    so one broken model cannot swing the ensemble alone.
    """
    fake = 0.0
    real = 0.0
    try:
        predictions = detector(img)
        logger.info("Raw predictions [%s]: %s", detector.model.name_or_path, predictions)
        for pred in predictions:
            label = str(pred["label"]).strip().lower()
            score = float(pred["score"])
            if label == "ai" or label.startswith("ai "):
                fake += score
            elif any(k in label for k in FAKE_LABELS):
                fake += score
            elif any(k in label for k in REAL_LABELS):
                real += score
        total = fake + real
        if total > 0:
            return fake / total, real / total
    except Exception as pred_err:
        logger.error("Inference error [%s]: %s", detector.model.name_or_path, pred_err)
    return 0.5, 0.5


def _arbiter_fuse(votes: Dict[str, float], quality_tier: str, face_present: bool) -> Tuple[float, List[str]]:
    """Arbiter: adaptive weighted geometric fusion + human-readable audit.

    Base weights encode measured strengths on our live matrix: CommFor
    (4,803-generator specialist) leads, the face specialist is trusted fully
    when BlazeFace actually found a face, sdxl-detector anchors real-photo
    safety, the quaternary ViT is a tiebreaker.

    Quality coupling: poor specimens get their face-vote weight halved
    (compression masquerades as GAN smoothness) — the arbiter *demotes*
    shaky evidence instead of letting a shaky vote condemn.
    """
    base = {
        "commfor": 1.25,
        "face_v2": 1.0 if face_present else 0.55,
        "sdxl": 1.0,
        "dima806": 0.7,
    }
    if quality_tier == "poor" and "face_v2" in votes:
        base["face_v2"] = min(base.get("face_v2", 1.0), 0.5)
    if quality_tier == "degraded":
        base["face_v2"] = base.get("face_v2", 1.0) * 0.8

    audit: List[str] = []
    total_w = 0.0
    log_sum = 0.0
    for name, v in votes.items():
        w = base.get(name, 1.0)
        total_w += w
        log_sum += w * np.log(max(v, FAKE_PROB_FLOOR))
        audit.append(f"{name}: {v:.3f} (w={w:.2f})")
    if total_w <= 0:
        return 0.5, ["arbiter: no weighted votes available"]
    fused = float(np.exp(log_sum / total_w))
    fused = min(max(fused, 0.0), 1.0)

    vals = list(votes.values())
    if len(vals) >= 2:
        spread = max(vals) - min(vals)
        if spread > 0.45:
            audit.append(f"DISAGREEMENT: spread {spread:.2f} between voters")
        agreement = sum(1 for v in vals if (v > 0.6) == (max(vals) > 0.6))
        if agreement == len(vals):
            audit.append("consensus: all voters lean the same direction")
    if quality_tier != "good":
        audit.append(f"quality tier '{quality_tier}' demoted weaker evidence")
    return fused, audit


def analyze_image_forgery(
    image_input: Union[str, Image.Image], raw_bytes: bytes = None
) -> Tuple[float, float, float, Dict[str, float]]:
    if isinstance(image_input, str):
        img = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        img = image_input
    else:
        img = Image.open(image_input)
    img.load()

    file_size = None
    try:
        if raw_bytes:
            file_size = len(raw_bytes)
        elif isinstance(image_input, str) and os.path.exists(image_input):
            file_size = os.path.getsize(image_input)
    except Exception:
        file_size = None

    # ---- Real forensic metrics for the UI (replaces std/mean proxies) ----
    lap_var = QUALITY_SHARP_GOOD * 2  # default: assume sharp unless measured
    try:
        multi_aspect_scores, lap_var = _compute_forensic_metrics(img)
    except Exception as metric_err:
        logger.error("Forensic metrics failed (%s); neutral values used", metric_err)
        neutral = (METRIC_MIN + METRIC_MAX) / 2.0
        multi_aspect_scores = {
            "lighting": round(neutral, 2),
            "texture": round(neutral, 2),
            "color_consistency": round(neutral, 2),
            "background_artifacts": round(neutral, 2),
            "facial_distortion": round(neutral, 2),
        }

    # ---- Specimen quality gate (per user request: minimum-quality regime) --
    quality = assess_image_quality(img, lap_var, file_size)

    # ---- Hard provenance signal (C2PA / AI-generator signatures) ----
    if raw_bytes:
        provenance_hit, provenance_detail = provenance_scan_bytes(raw_bytes)
    else:
        provenance_hit, provenance_detail = scan_ai_provenance(image_input)
    if provenance_hit:
        logger.info("AI provenance signature found: %s", provenance_detail)
    global _PROVENANCE_RESULT
    _PROVENANCE_RESULT = provenance_detail if provenance_hit else ""

    # ---- Ensemble votes with arbiter (named, weighted, audited) ----
    votes: Dict[str, float] = {}
    face_found = False
    if GLOBAL_DETECTOR is not None:
        face_crop, face_found = _crop_faces(img)  # tight crop for the face specialist
        f1, _ = _label_probs(GLOBAL_DETECTOR, face_crop)
        votes["face_v2"] = f1

    if GLOBAL_SECONDARY_DETECTOR is not None:
        f2, _ = _label_probs(GLOBAL_SECONDARY_DETECTOR, img)
        votes["sdxl"] = f2

    if GLOBAL_COMMFOR_DETECTOR is not None:
        votes["commfor"] = _commfor_prob(GLOBAL_COMMFOR_DETECTOR, img)

    if GLOBAL_QUATERNARY_DETECTOR is not None:
        f4, _ = _label_probs(GLOBAL_QUATERNARY_DETECTOR, img)
        votes["dima806"] = f4

    if not votes:
        fake_prob, real_prob = 0.5, 0.5
        arbiter_audit = ["arbiter: no detectors loaded — neutral verdict"]
    elif len(votes) == 1:
        (only, v), = votes.items()
        fake_prob, real_prob = v, 1.0 - v
        arbiter_audit = [f"single voter {only}: {v:.3f}"]
    else:
        fake_prob, arbiter_audit = _arbiter_fuse(votes, quality["tier"], face_found)
        real_prob = 1.0 - fake_prob

    # Provenance hit anchors fake probability at/above the C2PA floor.
    if provenance_hit:
        fake_prob = max(fake_prob, C2PA_FAKE_FLOOR)
        real_prob = 1.0 - fake_prob
        arbiter_audit.append(f"provenance anchor: {provenance_detail} => floor {C2PA_FAKE_FLOOR}")

    final_fake_prob = round(float(fake_prob), 4)
    final_real_prob = round(float(real_prob), 4)
    confidence = round(max(final_fake_prob, final_real_prob), 4)

    # stash the audit + quality for the API layer
    global _LAST_AUDIT, _LAST_QUALITY, _LAST_FACE_FOUND, _LAST_VOTES
    _LAST_AUDIT = arbiter_audit
    _LAST_QUALITY = quality
    _LAST_FACE_FOUND = face_found
    _LAST_VOTES = dict(votes)

    return final_real_prob, final_fake_prob, confidence, multi_aspect_scores


def classify_verdict(fake_prob: float) -> str:
    """Map a fake probability to a verdict label with an uncertain review band."""
    if fake_prob > VERDICT_FAKE_THRESHOLD:
        return "fake"
    if fake_prob < VERDICT_REAL_THRESHOLD:
        return "real"
    return "uncertain"
