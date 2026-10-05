"""Free algorithmic forensic checks (m3).

Every check returns a card with explicit states (loading/ok/not_applicable/
skipped/error), bilingual "why it matters" text, and an honest ``flag``:

* ``vote_capable=True`` checks may count toward the verdict engine's k-of-N
  agreement — but the engine never lets them raise a verdict alone (they are
  supporting signals, max verdict Investigate unless a detector agrees),
* ``flag=None`` means the check only reports a measurement; no threshold was
  invented for it (project constant #4: no fabricated numbers),
* shadows / vanishing points / FFT / QR / watermark are **information only**
  (never vote) until measured on labeled samples.

All of it runs locally with free/open libraries (Pillow, numpy, OpenCV).
One failing check never aborts the others: each is wrapped and reports its
own error state.
"""

import hashlib
import io
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# Deterministic byte signatures shared with the provenance scanner.
from app.services.detector import (  # noqa: E402  (same source of truth)
    AI_GENERATOR_SIGNATURES,
    _ela_map,
)


# ---------------------------------------------------------------------------
# Card helpers
# ---------------------------------------------------------------------------

def _card(
    check_id: str,
    name_en: str,
    name_ar: str,
    *,
    status: str,
    why_en: str,
    why_ar: str,
    flag: Optional[bool] = None,
    vote_capable: bool = False,
    axes: Optional[List[str]] = None,
    data: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    card: Dict[str, Any] = {
        "id": check_id,
        "name_en": name_en,
        "name_ar": name_ar,
        "status": status,
        "flag": flag,
        "vote_capable": vote_capable,
        "axes": axes or [],
        "why_en": why_en,
        "why_ar": why_ar,
    }
    if data is not None:
        card["data"] = data
    if reason is not None:
        card["reason"] = reason
    if error is not None:
        card["error"] = error
    return card


def _failed(check_id: str, name_en: str, name_ar: str, why_en: str, why_ar: str,
            vote_capable: bool, axes: List[str], exc: Exception) -> Dict[str, Any]:
    logger.warning("forensic check %s failed: %s", check_id, exc)
    return _card(
        check_id, name_en, name_ar,
        status="error", why_en=why_en, why_ar=why_ar,
        vote_capable=vote_capable, axes=axes, error=str(exc),
    )


# ---------------------------------------------------------------------------
# 1. Metadata: EXIF / XMP / IPTC + generator signatures
# ---------------------------------------------------------------------------

def scan_metadata(img: Image.Image, raw: Optional[bytes]) -> Dict[str, Any]:
    """Read EXIF facts and look for AI-generator signatures in the bytes."""
    why_en = (
        "Metadata says which camera/software touched the file. Consistent camera "
        "EXIF is evidence of a real capture; generator signatures inside metadata "
        "are concrete provenance evidence."
    )
    why_ar = (
        "تقول البيانات الوصفية أي كاميرا/برنامج عالج الملف. اتساق EXIF مع كاميرا "
        "حقيقية دليل على تصوير فعلي، وتوقيعات المولّدات داخل البيانات دليل مباشر."
    )
    try:
        exif: Dict[str, Any] = {}
        exif_obj = img.getexif()
        if exif_obj:
            tag_names = {
                271: "make", 272: "model", 306: "datetime", 315: "artist",
                305: "software", 33432: "copyright",
            }
            for tag, key in tag_names.items():
                value = exif_obj.get(tag)
                if value:
                    exif[key] = str(value).strip()
        gps = exif_obj.get_ifd(34853) if exif_obj else {}
        has_gps = bool(gps)
        gps_coords: Optional[Dict[str, float]] = None
        if has_gps:
            def _to_deg(values):
                try:
                    d, m, s = float(values[0]), float(values[1]), float(values[2])
                    return d + m / 60.0 + s / 3600.0
                except Exception:
                    return None

            lat, lon = _to_deg(gps.get(2)), _to_deg(gps.get(4))
            lat_ref, lon_ref = gps.get(1), gps.get(3)
            if isinstance(lat_ref, bytes):
                lat_ref = lat_ref.decode("utf-8", errors="ignore")
            if isinstance(lon_ref, bytes):
                lon_ref = lon_ref.decode("utf-8", errors="ignore")
            if lat is not None and str(lat_ref or "N").upper().startswith("S"):
                lat = -lat
            if lon is not None and str(lon_ref or "E").upper().startswith("W"):
                lon = -lon
            if (
                lat is not None and lon is not None
                and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
            ):
                gps_coords = {"lat": round(lat, 6), "lon": round(lon, 6)}

        # Generator signatures in real metadata segments / raw bytes.
        generators: List[str] = []
        if raw:
            lowered = raw.lower()
            for sig in AI_GENERATOR_SIGNATURES:
                if sig.lower() in lowered:
                    generators.append(sig.decode("utf-8", errors="replace"))
        software = (exif.get("software") or "").lower()
        for known in ("chatgpt", "dall-e", "midjourney", "stable diffusion", "firefly", "gemini"):
            if known in software and known not in [g.lower() for g in generators]:
                generators.append(exif.get("software"))

        data = {
            "exif_present": bool(exif_obj),
            "exif": exif,
            "gps_present": has_gps,
            "gps": gps_coords,
            "generator_signatures": [g for g in generators if g],
        }
        flag = bool(data["generator_signatures"])
        return _card(
            "exif", "EXIF / metadata", "البيانات الوصفية EXIF",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=flag, vote_capable=True, axes=["ai_generation"],
            data=data,
        )
    except Exception as exc:
        return _failed("exif", "EXIF / metadata", "البيانات الوصفية EXIF",
                       why_en, why_ar, True, ["ai_generation"], exc)


# ---------------------------------------------------------------------------
# 2. JPEG quality estimation from quantization tables
# ---------------------------------------------------------------------------

_STD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]
_STD_CHROMA = [
    17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
]


def _scaled_table(quality: int, std: List[int]) -> List[int]:
    if quality < 50:
        scale = 5000 // quality
    else:
        scale = 200 - quality * 2
    return [max(1, min(255, (s * scale + 50) // 100)) for s in std]


def estimate_jpeg_quality(img: Image.Image) -> Optional[int]:
    """Classic qtable-matching quality estimate (1..100) or None for non-JPEG."""
    try:
        tables = getattr(img, "quantization", None)
        if not tables:
            return None
        best_quality, best_error = None, None
        for quality in range(1, 101):
            total_error = 0
            for table_idx, actual in tables.items():
                std = _STD_LUMA if table_idx == 0 else _STD_CHROMA
                predicted = _scaled_table(quality, std)
                if len(predicted) != len(actual):
                    continue
                total_error += sum(
                    abs(int(a) - int(p)) for a, p in zip(actual, predicted)
                )
            if best_error is None or total_error < best_error:
                best_error, best_quality = total_error, quality
        return best_quality
    except Exception:
        return None


def check_jpeg(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "JPEG quantization tables reveal the saving quality. Non-standard tables "
        "or very low quality can indicate re-encoding (a normal step in edits or "
        "compression by platforms) — a measurement, not a verdict."
    )
    why_ar = (
        "جداول التكميم في JPEG تكشف جودة الحفظ. جداول غير قياسية أو جودة منخفضة "
        "قد تدل على إعادة ترميز (خطوة طبيعية في التعديل أو ضغط المنصات) — قياس لا حكم."
    )
    fmt = (img.format or "").upper()
    if fmt != "JPEG":
        return _card(
            "jpeg_quality", "JPEG quality", "جودة JPEG",
            status="not_applicable", why_en=why_en, why_ar=why_ar,
            reason=f"Format is {fmt or 'unknown'}, not JPEG.",
        )
    try:
        quality = estimate_jpeg_quality(img)
        return _card(
            "jpeg_quality", "JPEG quality", "جودة JPEG",
            status="ok", why_en=why_en, why_ar=why_ar,
            data={"estimated_quality": quality},
        )
    except Exception as exc:
        return _failed("jpeg_quality", "JPEG quality", "جودة JPEG",
                       why_en, why_ar, False, [], exc)


# ---------------------------------------------------------------------------
# 3. ELA (measurement + map for the manipulation card)
# ---------------------------------------------------------------------------

def _ela_heat_png(ela: np.ndarray, max_side: int = 480) -> Optional[str]:
    """Downscaled black-red-yellow-white heat PNG of the ELA error, base64.

    Returns None when encoding fails — callers show 'map unavailable'
    instead of fabricating one.
    """
    try:
        import base64 as _b64

        energy = ela.mean(axis=2)
        ceiling = float(np.percentile(energy, 99)) or 1.0
        norm = np.clip(energy / ceiling, 0.0, 1.0)
        # piecewise heat ramp: black -> red -> yellow -> white
        r = np.clip(norm * 2.5, 0, 1)
        g = np.clip((norm - 0.4) * 1.8, 0, 1)
        b = np.clip((norm - 0.75) * 4.0, 0, 1)
        rgb = (np.stack([r, g, b], axis=2) * 255).astype(np.uint8)
        heat = Image.fromarray(rgb)
        if max(heat.size) > max_side:
            scale = max_side / max(heat.size)
            heat = heat.resize(
                (max(1, int(heat.width * scale)), max(1, int(heat.height * scale))),
                Image.BILINEAR,
            )
        buf = io.BytesIO()
        heat.save(buf, format="PNG", optimize=True)
        return _b64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as map_err:
        logger.warning("ELA map encoding failed: %s", map_err)
        return None


def check_ela(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "Error Level Analysis re-compresses the image and highlights regions that "
        "differ. Useful to *localize* possible edits; its threshold is not yet "
        "calibrated here, so it reports a measurement only and never votes."
    )
    why_ar = (
        "تحليل مستوى الخطأ يعيد ضغط الصورة ويُبرز المناطق المختلفة، وهو مفيد "
        "*لتحديد* مواضع التعديل المحتملة. عتباته غير معايَرة هنا بعد، لذا يعيد "
        "قياسًا فقط ولا يصوّت أبدًا."
    )
    try:
        ela = _ela_map(img)
        mean = float(np.mean(ela))
        p99 = float(np.percentile(ela, 99))
        rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
        gray = rgb.mean(axis=2)
        h, w = gray.shape
        band = max(8, int(min(h, w) * 0.06))
        border = float(np.mean(np.concatenate([ela[:band].ravel(), ela[-band:].ravel()])))
        interior = (
            float(np.mean(ela[band:-band, band:-band]))
            if h > 2 * band and w > 2 * band else mean
        )
        return _card(
            "ela", "Error Level Analysis", "تحليل مستوى الخطأ",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=True, axes=["editing_check"],
            data={
                "ela_mean": round(mean, 3),
                "ela_p99": round(p99, 3),
                "border_interior_ratio": round(border / max(interior, 0.05), 3),
                "map_png_base64": _ela_heat_png(ela),
                "map_note": (
                    "ELA heat map (bright = high recompression error). "
                    "Localisation aid only — no editing model is registered, "
                    "so no manipulation type is claimed."
                ),
            },
        )
    except Exception as exc:
        return _failed("ela", "Error Level Analysis", "تحليل مستوى الخطأ",
                       why_en, why_ar, True, ["editing_check"], exc)


# ---------------------------------------------------------------------------
# 4. Perceptual hashes vs local known-forgery DB
# ---------------------------------------------------------------------------

def _dct1(vec: np.ndarray) -> np.ndarray:
    """Orthonormal DCT-II along the last axis via matrix multiply."""
    n = vec.shape[-1]
    k = np.arange(n)
    basis = np.cos(np.pi * (2 * np.arange(n) + 1)[None, :] * k[:, None] / (2 * n))
    basis[0] *= np.sqrt(1 / n)
    basis[1:] *= np.sqrt(2 / n)
    return vec @ basis.T


def phash_hex(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """pHash (DCT-based) as hex — same family as imagehash.phash."""
    size = hash_size * highfreq_factor
    gray = np.asarray(img.convert("L").resize((size, size), Image.LANCZOS), dtype=np.float32)
    dct = _dct1(_dct1(gray.T).T)  # 2D DCT
    block = dct[:hash_size, :hash_size]
    med = float(np.median(block.flatten()[1:]))  # ignore DC
    bits = (block.flatten() > med).astype(np.uint8)
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def dhash_hex(img: Image.Image, hash_size: int = 8) -> str:
    """dHash (horizontal gradient) as hex."""
    gray = np.asarray(
        img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS), dtype=np.int16
    )
    bits = (gray[:, 1:] > gray[:, :-1]).astype(np.uint8)
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming(hex_a: str, hex_b: str) -> int:
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


def load_forgery_db(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Admin-populated known-forgery entries (empty list when absent/invalid)."""
    db_path = path or settings.FORGERY_DB_PATH
    try:
        with open(db_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        entries = payload.get("entries", [])
        return [e for e in entries if isinstance(e, dict) and e.get("phash") and e.get("dhash")]
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("forgery db unreadable: %s", exc)
        return []


def lookup_forgery(
    phash_value: str, dhash_value: str, db: List[Dict[str, Any]], max_hamming: int
) -> Optional[Dict[str, Any]]:
    """Settle requires BOTH hashes agreeing within the configured distance."""
    for entry in db:
        d1 = hamming(phash_value, str(entry["phash"]))
        d2 = hamming(dhash_value, str(entry["dhash"]))
        if d1 <= max_hamming and d2 <= max_hamming:
            return {
                **entry,
                "phash_distance": d1,
                "dhash_distance": d2,
                "hamming": max(d1, d2),
            }
    return None


def check_hashes(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "Perceptual hashes identify the same picture across edits. A match against "
        "the local known-forgery database is decisive (pHash AND dHash must agree); "
        "otherwise the hashes are just recorded for later comparison."
    )
    why_ar = (
        "البصمات الإدراكية تتعرّف على الصورة نفسها عبر التعديلات. التطابق مع قاعدة "
        "التزييفات المعروفة قاطع (يجب اتفاق pHash وdHash معًا)، وإلا تُسجَّل البصمات "
        "للقارن المستقبلي فقط."
    )
    try:
        ph = phash_hex(img)
        dh = dhash_hex(img)
        rules_max = 4
        try:
            from app.verdict_config import load_rules
            rules_max = load_rules()["direct_settle"]["known_forgery_hash"]["max_hamming"]
        except Exception:
            pass
        db = load_forgery_db()
        match = lookup_forgery(ph, dh, db, rules_max) if db else None
        data: Dict[str, Any] = {
            "phash": ph,
            "dhash": dh,
            "db_entries": len(db),
            "match": match,
        }
        if match:
            data["settle"] = {
                "phash_match": True,
                "dhash_match": True,
                "hamming": match["hamming"],
                "entry_label": match.get("label"),
                "entry_reference": match.get("reference") or match.get("id"),
            }
        return _card(
            "hash_db", "Known-forgery hash lookup", "البحث في قاعدة التزييفات المعروفة",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False, axes=[],
            data=data,
        )
    except Exception as exc:
        return _failed("hash_db", "Known-forgery hash lookup", "البحث في قاعدة التزييفات المعروفة",
                       why_en, why_ar, False, [], exc)


# ---------------------------------------------------------------------------
# 5. QR / barcode (information only)
# ---------------------------------------------------------------------------

def check_qr(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "QR codes and barcodes inside an image often link to the source. Their "
        "text is recorded as data; links are not fetched here (SSRF-guarded "
        "fetching happens only when you explicitly ask)."
    )
    why_ar = (
        "رموز QR والباركود داخل الصورة غالبًا تربط بمصدرها. يُسجَّل نصها كبيانات، "
        "ولا تُفتح الروابط هنا (الجلب المحمي يحدث فقط عند طلبك الصريح)."
    )
    try:
        import cv2

        rgb = np.asarray(img.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        texts: List[str] = []
        data, _points, _ = detector.detectAndDecode(bgr)
        if data:
            texts.append(str(data))
        return _card(
            "qr", "QR / barcode", "QR / الباركود",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False,
            data={"found": bool(texts), "contents": texts},
        )
    except Exception as exc:
        return _failed("qr", "QR / barcode", "QR / الباركود", why_en, why_ar, False, [], exc)


# ---------------------------------------------------------------------------
# 6-8. Information-only geometry/spectral checks (never vote)
# ---------------------------------------------------------------------------

def check_vanishing(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "Straight lines in a scene usually converge to vanishing points; absent or "
        "inconsistent perspective can occur in generated scenes. INFO ONLY: this "
        "heuristic is not calibrated, so it never affects the verdict."
    )
    why_ar = (
        "الخطوط المستقيمة تتقارب عادة نحو نقاط تلاشٍ؛ افتقار المشهد أو تناقضه في "
        "المنظور قد يظهر في الصور المولّدة. معلومة فقط: هذه الإشارة الاستنباطية غير معايَرة "
        "ولا تؤثر في الحكم أبدًا."
    )
    try:
        import cv2

        gray = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=max(30, min(gray.shape) // 20),
                                maxLineGap=10)
        n_lines = int(len(lines)) if lines is not None else 0
        return _card(
            "vanishing", "Perspective / vanishing points", "المنظور ونقاط التلاشي",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False,
            data={"line_segments": n_lines},
        )
    except Exception as exc:
        return _failed("vanishing", "Perspective / vanishing points", "المنظور ونقاط التلاشي",
                       why_en, why_ar, False, [], exc)


def check_shadows(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "Real scenes have a consistent dominant light direction; incoherent shadows "
        "can indicate composites. INFO ONLY: not calibrated, never affects the verdict."
    )
    why_ar = (
        "المشاهد الحقيقية لها اتجاه إضاءة سائد واحد؛ تعارض الظلال قد يدل على تركيب. "
        "معلومة فقط: غير معايَر ولا يؤثر في الحكم أبدًا."
    )
    try:
        gray = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
        gy, gx = np.gradient(gray)
        magnitude = np.sqrt(gx * gx + gy * gy)
        strong = magnitude > np.percentile(magnitude, 90)
        if not strong.any():
            return _card(
                "shadows", "Light direction", "اتجاه الإضاءة",
                status="ok", why_en=why_en, why_ar=why_ar,
                flag=None, vote_capable=False,
                data={"dominant_orientation_deg": None, "concentration": None},
            )
        angles = np.arctan2(gy[strong], gx[strong])
        # orientation concentration of edge normals (0 = diffuse, 1 = one direction)
        mean_vec = np.mean(np.exp(2j * angles))
        concentration = float(np.abs(mean_vec))
        dominant = float((np.angle(mean_vec) / 2.0) * 180.0 / np.pi % 180.0)
        return _card(
            "shadows", "Light direction", "اتجاه الإضاءة",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False,
            data={
                "dominant_orientation_deg": round(dominant, 1),
                "concentration": round(concentration, 3),
            },
        )
    except Exception as exc:
        return _failed("shadows", "Light direction", "اتجاه الإضاءة",
                       why_en, why_ar, False, [], exc)


def check_fft(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "The frequency spectrum exposes resampling or generator artifacts as "
        "abnormal energy rings. INFO ONLY: uncalibrated measurement, never votes."
    )
    why_ar = (
        "الطيف الترددي يكشف إعادة التحجيم أو نمط المولّدات كطاقات شاذة. معلومة فقط: "
        "قياس غير معايَر ولا يصوّت أبدًا."
    )
    try:
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        spec = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
        h, w = spec.shape
        cy, cx = h // 2, w // 2
        yy, xx = np.ogrid[:h, :w]
        radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        max_r = min(cy, cx)
        bands = []
        for lo in (0.0, 0.25, 0.5, 0.75):
            mask = (radius >= lo * max_r) & (radius < (lo + 0.25) * max_r)
            if mask.any():
                bands.append(round(float(np.mean(spec[mask])), 3))
        return _card(
            "fft", "Frequency spectrum", "الطيف الترددي",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False,
            data={"radial_energy_bands": bands},
        )
    except Exception as exc:
        return _failed("fft", "Frequency spectrum", "الطيف الترددي",
                       why_en, why_ar, False, [], exc)


# ---------------------------------------------------------------------------
# 9. Watermark template matching (needs user-provided templates)
# ---------------------------------------------------------------------------

def check_watermark(img: Image.Image) -> Dict[str, Any]:
    why_en = (
        "Known watermarks can be matched against templates you provide. No "
        "templates configured -> this check honestly reports skipped."
    )
    why_ar = (
        "يمكن مطابقة العلامات المائية المعروفة مع قوالب تقدّمها أنت. لا قوالب "
        "مضبوطة -> يعلن الفحص تخطّيه بصدق."
    )
    templates_dir = settings.WATERMARK_TEMPLATES_DIR
    try:
        templates = [
            os.path.join(templates_dir, f)
            for f in sorted(os.listdir(templates_dir))
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ] if os.path.isdir(templates_dir) else []
    except Exception:
        templates = []
    if not templates:
        return _card(
            "watermark", "Watermark match", "مطابقة العلامة المائية",
            status="skipped", why_en=why_en, why_ar=why_ar,
            reason="No watermark templates configured (backend/data/watermarks is empty).",
        )
    try:
        import cv2

        target = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        best_score, best_name = 0.0, None
        orb = cv2.ORB_create(500)
        kp1, des1 = orb.detectAndCompute(target, None)
        if des1 is None or len(kp1) < 10:
            return _card(
                "watermark", "Watermark match", "مطابقة العلامة المائية",
                status="ok", why_en=why_en, why_ar=why_ar,
                flag=None, vote_capable=False,
                data={"matched_template": None, "score": 0.0},
            )
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        for path in templates:
            tpl = cv2.cvtColor(np.asarray(Image.open(path).convert("RGB")), cv2.COLOR_RGB2GRAY)
            kp2, des2 = orb.detectAndCompute(tpl, None)
            if des2 is None or len(kp2) < 10:
                continue
            matches = bf.match(des1, des2)
            score = float(len(matches)) / max(len(kp1), len(kp2))
            if score > best_score:
                best_score, best_name = score, os.path.basename(path)
        return _card(
            "watermark", "Watermark match", "مطابقة العلامة المائية",
            status="ok", why_en=why_en, why_ar=why_ar,
            flag=None, vote_capable=False,
            data={"matched_template": best_name if best_score >= 0.3 else None,
                  "score": round(best_score, 3)},
        )
    except Exception as exc:
        return _failed("watermark", "Watermark match", "مطابقة العلامة المائية",
                       why_en, why_ar, False, [], exc)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

CHECK_ORDER = [
    "exif", "jpeg_quality", "ela", "hash_db", "qr",
    "vanishing", "shadows", "fft", "watermark",
]


def run_forensics(img: Image.Image, raw: Optional[bytes] = None) -> Dict[str, Any]:
    """Run every check; one failure never stops the rest.

    Returns ``{state, checks: [...], durations_ms: {...}}``. Each check runs
    through a wrapper that converts any exception into that check's own
    honest error card (its id is preserved).
    """
    started = time.perf_counter()
    checks: List[Dict[str, Any]] = []
    durations: Dict[str, int] = {}

    plan = [
        ("exif", "EXIF / metadata", "البيانات الوصفية EXIF", lambda: scan_metadata(img, raw)),
        ("jpeg_quality", "JPEG quality", "جودة JPEG", lambda: check_jpeg(img)),
        ("ela", "Error Level Analysis", "تحليل مستوى الخطأ", lambda: check_ela(img)),
        ("hash_db", "Known-forgery hash lookup", "البحث في قاعدة التزييفات المعروفة", lambda: check_hashes(img)),
        ("qr", "QR / barcode", "QR / الباركود", lambda: check_qr(img)),
        ("vanishing", "Perspective / vanishing points", "المنظور ونقاط التلاشي", lambda: check_vanishing(img)),
        ("shadows", "Light direction", "اتجاه الإضاءة", lambda: check_shadows(img)),
        ("fft", "Frequency spectrum", "الطيف الترددي", lambda: check_fft(img)),
        ("watermark", "Watermark match", "مطابقة العلامة المائية", lambda: check_watermark(img)),
    ]

    for check_id, name_en, name_ar, fn in plan:
        t0 = time.perf_counter()
        try:
            card = fn()
        except Exception as exc:  # individual cards are pre-wrapped; this is belt & braces
            card = _failed(check_id, name_en, name_ar, "", "", False, [], exc)
        durations[card["id"]] = int((time.perf_counter() - t0) * 1000)
        checks.append(card)

    return {
        "state": "ok",
        "checks": checks,
        "durations_ms": durations,
        "total_ms": int((time.perf_counter() - started) * 1000),
    }


# ---------------------------------------------------------------------------
# Technical info card [19]
# ---------------------------------------------------------------------------

def build_technical_info(img: Image.Image, raw: Optional[bytes] = None) -> Dict[str, Any]:
    """Dimensions, format+size, EXIF summary, JPEG quality, color profile, aspect."""
    try:
        img.load()
        width, height = img.size
        fmt = img.format or "UNKNOWN"
        size_bytes = len(raw) if raw else None

        exif = img.getexif()
        exif_summary: Dict[str, str] = {}
        if exif:
            for tag, key in {271: "make", 272: "model", 306: "datetime", 305: "software"}.items():
                value = exif.get(tag)
                if value:
                    exif_summary[key] = str(value).strip()

        icc = img.info.get("icc_profile")
        quality = estimate_jpeg_quality(img) if fmt == "JPEG" else None

        gcd = np.gcd(width, height)
        return {
            "state": "ok",
            "data": {
                "dimensions": {"width": width, "height": height},
                "format": fmt,
                "size_bytes": size_bytes,
                "exif": exif_summary,
                "exif_present": bool(exif),
                "jpeg_quality_estimate": quality,
                "color_profile": ("ICC profile present" if icc else "No ICC profile"),
                "aspect_ratio": f"{width // gcd}:{height // gcd}",
            },
        }
    except Exception as exc:
        logger.warning("technical info failed: %s", exc)
        return {"state": "error", "error": str(exc)}


__all__ = [
    "run_forensics",
    "build_technical_info",
    "scan_metadata",
    "check_jpeg",
    "estimate_jpeg_quality",
    "check_ela",
    "phash_hex",
    "dhash_hex",
    "hamming",
    "load_forgery_db",
    "lookup_forgery",
    "check_hashes",
    "check_qr",
    "check_vanishing",
    "check_shadows",
    "check_fft",
    "check_watermark",
    "CHECK_ORDER",
]
