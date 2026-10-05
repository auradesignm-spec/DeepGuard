"""News misinformation detector (v2) — forensic pipeline for screenshots.

Input: a news screenshot (social post, headline card, WhatsApp forward).
Pipeline (seven signals, weighted arbiter — mirrors detector.py's design):

  1. OCR (RapidOCR, ar+en)           -> extracted text for analysis
  2. Arabic text-manipulation score  -> local heuristics: urgency bait,
                                        unsourced claims, engagement bait,
                                        missing provenance markers
  3. Source provenance               -> URLs: shorteners, suspicious TLDs,
                                        named agencies vs anonymous attribution
  4. Date analysis                   -> impossible future dates, stale-news
                                        sold as breaking, missing timestamps
  5. Logical coherence               -> absolutist overreach, unfalsifiable
                                        framing, fear-without-evidence
  6. Agenda framing                  -> conspiracy, us-vs-them, financial
                                        bait, incitement
  7. Image forensics                 -> reuse detector.analyze_image_forgery;
                                        a doctored/generated screenshot raises doubt
  + External fact-check              -> Google Fact Check Tools claims:search;
                                        disputed claims anchor the verdict
                                        (mirrors the C2PA provenance anchor)

Output: misinformation_prob in [0,1], verdict, arbiter audit, extracted text,
deep_analysis breakdown. All local signals run offline; the fact-check call is
optional and fails safe.
"""
import logging
import os
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights & thresholds (calibrated conservatively: text signals accuse only
# when several independent families of cues agree; deep analyzers contribute
# narrowly and never condemn alone)
# ---------------------------------------------------------------------------
W_TEXT = 0.28
W_FORENSIC = 0.18
W_FACTCHECK = 0.18
W_SOURCE = 0.12
W_DATE = 0.08
W_LOGIC = 0.08
W_AGENDA = 0.08

NEWS_FAKE_ANCHOR = 0.90      # disputed claim with authoritative ratings
NEWS_TRUE_FLOOR = 0.25       # claim verified true by multiple publishers
UNCERTAIN_BAND = (0.40, 0.65)

# ---------------------------------------------------------------------------
# Arabic + English manipulation cue lexicons (local, offline)
# ---------------------------------------------------------------------------
URGENCY_BAIT = [
    "عاجل", "حصرياً", "حصري", "الآن فقط", "قبل فوات الأوان", "في الساعات الأخيرة",
    "طوارئ", "عاجل جدا", "بالفيديو والصور", "انطلق", "اخيرا", "أخيراً",
    "breaking", "urgent", "exclusive", "shocking", "you won't believe",
]
ENGAGEMENT_BAIT = [
    "شارك قبل الحذف", "انشر", "شير", "احفظ المنشور", "لا تحذف", "قبل أن يحذفوه",
    "شارك على نطاق واسع", "أرسل لكل من تعرف", "share before they delete",
    "repost", "share this", "forward this",
]
UNSOURCED_AUTHORITY = [
    "مصادر مؤكدة", "مصادر موثوقة", "مصادر خاصة", "مصادرنا", "شخص مطلع",
    "تسريبات", "وفق مصادر", "sources say", "insiders reveal", "leaked",
    "وثائق مسربة", "كشف سر",
]
EMOTIONAL_SHOCK = [
    "صادم", "مرعب", "فضيحة", "كارثة", "مخيف", "فضيحة كبرى", "جنون",
    "scandal", "terrifying", "insane", "unbelievable", "استفزاز",
]

# Legitimacy markers whose PRESENCE lowers the score
LEGIT_MARKERS = [
    "المصدر:", "source:", "وقالت وكالة", "صرح", "أكد", "نفى", "بحسب",
    "الرابط", "reuters", "ap", "afp", "bbc", "aljazeera", "الجزيرة",
    "alarabiya", "العربية", "وفا", "و.أ.ف", "رويترز",
]

# --- deep analyzer lexicons -------------------------------------------------
# Named, checkable institutions — their presence supports source credibility
NAMED_SOURCES = [
    "رويترز", "وكالة الأنباء", "وكالة أنباء", "الوكالة", "وزارة", "الجامعة",
    "البورصة", "البنك المركزي", "بلدية", "المستشفى", "شرطة", "الدفاع المدني",
    "reuters", "apnews", "afp", "bbc", "cnn", "aljazeera", "alarabiya",
    "arabnews", "asharq", "associated press",
]
URL_SHORTENERS = [
    "bit.ly", "tinyurl", "t.co", "cutt.us", "is.gd", "rebrand.ly", "t.ly",
    "shorturl.at", "rb.gy", "ow.ly", "cutt.ly", "shorte.st",
]
SUSPICIOUS_TLDS = [
    ".xyz", ".top", ".info", ".click", ".link", ".loan", ".work", ".gq",
    ".tk", ".ml", ".cf", ".buzz", ".surf",
]
ABSOLUTES = [
    "الكل", "الجميع", "دائماً", "دائما", "أبداً", "أبدا", "بلا استثناء",
    "كل الناس", "everyone knows", "everyone is", "always", "never", "100%",
]
UNFALSIFIABLE = [
    "لا أحد يجرؤ", "الجميع يعلم", "الحقيقة المطلقة", "ممنوع النشر",
    "ممنوع من النشر", "محظور النشر", "الحقيقة التي يخفونها",
    "no one dares", "banned from publishing", "the truth they hide",
]
CONSPIRACY = [
    "مؤامرة", "المؤامرة", "يخفون عنك", "إعلام كاذب", "الإعلام الكاذب",
    "يدبرون ضد", "خطة شريرة", "التنسيق الخفي", "يتآمرون",
    "conspiracy", "they don't want you", "hidden agenda", "puppet masters",
]
US_VS_THEM = [
    "أعداءنا", "خونة", "عملاء", "الأنذال", "أعداء الأمت", "خيانة عظمى",
    "traitors", "enemies of the", "sellouts",
]
FINANCIAL_BAIT = [
    "استثمر الآن", "اربح", "مضاعفة أموالك", "أرباح سريعة", "عملات رقمية مجانية",
    "هدية مجانية", "giveaway", "invest now", "double your money",
    "free crypto", "get rich quick",
]
INCITEMENT = [
    "انتقم", "احرقوا", "اهدموا", "اضربوا", "جهزوا نفسكم", "انزلوا للشارع",
    "rise up", "take to the streets", "burn it down",
]

_DATE_PAT = re.compile(r"\b(20\d{2})[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}[-/]\d{1,2}[-/](20\d{2})\b")
_ISO_PAT = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
_DMY_PAT = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b")
_ARABIC_REVERSED = True  # the bundled ar rec model emits visual (LTR) order
_AR_CHAR_PAT = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_AR_PAGE_PAT = re.compile(r"[\u0600-\u06FF]+", re.IGNORECASE)
_AR_MONTH_NAMES = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
_AR_DATE_PAT = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_AR_MONTH_NAMES) + r")\s+(20\d{2})\b"
)
_RELATIVE_DATE_WORDS = ["اليوم", "أمس", "الصباح", "مساء اليوم", "today", "yesterday"]
_URL_PAT = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_HASHTAG_PAT = re.compile(r"#\w+")
_HANDLE_PAT = re.compile(r"@\w{2,}")
# Arabic question-mark intrigue: "هل تعلم؟", "ماذا يحدث؟؟"
_QUESTION_RAIN = re.compile(r"[؟?]{1,}")


def _contains_any(text_lower: str, phrases: List[str]) -> List[str]:
    return [p for p in phrases if p.lower() in text_lower]


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
_OCR_ENGINE = None
_AR_OCR_ENGINE = None
_OCR_FAILED = False
_AR_OCR_FAILED = False


def _get_ocr():
    """Lazy-load the default RapidOCR (zh/en models). None on any failure."""
    global _OCR_ENGINE, _OCR_FAILED
    if _OCR_ENGINE is not None or _OCR_FAILED:
        return _OCR_ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        _OCR_ENGINE = RapidOCR()
        logger.info("RapidOCR engine loaded (zh/en ONNX)")
    except Exception as exc:
        logger.warning("RapidOCR unavailable (%s); OCR disabled", exc)
        _OCR_FAILED = True
        _OCR_ENGINE = None
    return _OCR_ENGINE


def _get_arabic_ocr():
    """Lazy-load an Arabic recognizer on top of the default det/cls models.

    rapidocr_onnxruntime 1.4.4 ships ONLY chinese/english recognition models,
    and its kwargs path mangles ``rec_keys_path`` so a custom dictionary can
    never reach CTCLabelDecode (the charmap bug behind "19j: 16\""). We build
    the TextRecognizer directly with ``keys_path`` - the kwarg it actually
    reads. Model files are local (backend/models/ocr); nothing is downloaded
    at request time. Returns None when the files are missing.
    """
    global _AR_OCR_ENGINE, _AR_OCR_FAILED
    if _AR_OCR_ENGINE is not None or _AR_OCR_FAILED:
        return _AR_OCR_ENGINE
    rec_path = settings.OCR_ARABIC_REC_MODEL
    keys_path = settings.OCR_ARABIC_KEYS
    if not rec_path or not keys_path or not os.path.exists(rec_path) or not os.path.exists(keys_path):
        logger.info("Arabic OCR model not found (%s); Arabic pass skipped", rec_path)
        _AR_OCR_FAILED = True
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        from rapidocr_onnxruntime.ch_ppocr_v3_rec.text_recognize import TextRecognizer  # type: ignore

        base = _get_ocr()
        if base is None:
            _AR_OCR_FAILED = True
            return None
        engine = RapidOCR()
        engine.text_recognizer = TextRecognizer({
            "model_path": rec_path,
            "keys_path": keys_path,
            "rec_img_shape": [3, 48, 320],
            "rec_batch_num": 6,
            "use_cuda": False,
        })
        _AR_OCR_ENGINE = engine
        logger.info("Arabic OCR recognizer loaded (%s)", os.path.basename(rec_path))
    except Exception as exc:
        logger.warning("Arabic OCR unavailable (%s); single-pass OCR only", exc)
        _AR_OCR_FAILED = True
        _AR_OCR_ENGINE = None
    return _AR_OCR_ENGINE


def _iter_engines():
    """Yield (engine, is_arabic) passes; Arabic first, default zh/en second."""
    if settings.OCR_ARABIC_ENABLED:
        ar = _get_arabic_ocr()
        if ar is not None:
            yield ar, True
    base = _get_ocr()
    if base is not None:
        yield base, False


def _arabic_ratio(text: str) -> float:
    """Share of non-space chars that are Arabic-script."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if _AR_CHAR_PAT.match(c)) / len(chars)


def _visual_to_logical(line: str) -> str:
    """Convert one visual-order (LTR) line of Arabic text to logical order.

    The rec model reads pixels left-to-right, so an RTL line comes out with
    both its words and its letters mirrored ("لجاع" for "عاجل"). Recovery:
    reverse the word order, and reverse the characters inside every chunk that
    contains Arabic script. Non-Arabic chunks (2026, OpenAI, ":") survive
    intact because their natural order is already left-to-right.
    """
    if not _AR_CHAR_PAT.search(line) or _arabic_ratio(line) < 0.3:
        return line
    chunks = re.findall(r"\S+", line)
    if not chunks:
        return line
    if len(chunks) == 1:
        return chunks[0][::-1] if _AR_CHAR_PAT.search(chunks[0]) else line
    fixed = []
    for chunk in reversed(chunks):
        if _AR_CHAR_PAT.search(chunk):
            chunk = chunk[::-1]
        fixed.append(chunk)
    return " ".join(fixed)


def _strip_pages(text: str) -> str:
    """Fix Arabic lines emitted in visual (LTR) order by the rec model.

    Arabic script runs right-to-left, but the converter of the bundled
    PP-OCRv3 arabic model wrote the glyphs left-to-right, so every line comes
    out reversed ("19j" garbage with the chinese model, "لجاع" with the
    arabic one). Reversing each run of Arabic characters restores the logical
    order ("عاجل"). Only the Arabic runs are reversed so embedded numbers and
    Latin fragments keep their own order.
    """
    if not _ARABIC_REVERSED:
        return text
    return "\n".join(_visual_to_logical(line) for line in text.splitlines())


def extract_text(image: Image.Image) -> str:
    """Extract text from a screenshot. Returns "" when OCR unavailable.

    Two-pass: the Arabic recognizer runs first; when the page is not Arabic
    (or the pass yields almost no Arabic), the default zh/en recognizer runs
    on the same image. Lines are merged in top-to-bottom order.
    """
    engine = _get_ocr()
    if engine is None:
        return ""
    try:
        import numpy as _np

        arr = _np.array(image.convert("RGB"))
        lines: List[str] = []
        boxes_seen = 0
        for eng, is_arabic in _iter_engines():
            try:
                result, _ = eng(arr)
            except Exception as exc:
                logger.warning("OCR engine (arabic=%s) failed: %s", is_arabic, exc)
                continue
            if not result:
                continue
            rows = []
            for row in result:
                if len(row) < 2 or not str(row[1]).strip():
                    continue
                text = str(row[1]).strip()
                # rapidocr may return the score as str ("0.79...") or float
                try:
                    conf = float(row[2]) if len(row) > 2 else 0.0
                except (TypeError, ValueError):
                    conf = 0.0
                if conf and conf < 0.35:
                    continue
                box = row[0] if len(row) > 2 and hasattr(row[0], "__len__") else None
                y = min(pt[1] for pt in box) if box else 0.0
                rows.append((y, text))
            rows.sort(key=lambda r: r[0])
            lines = [t for _, t in rows]
            boxes_seen = len(lines)
            arabic_lines = sum(1 for t in lines if _AR_CHAR_PAT.search(t))
            if arabic_lines >= max(1, int(0.3 * boxes_seen)):
                break  # the Arabic pass captured this page
        # Single RTL fix point: visual->logical order correction happens once,
        # here - not per row (double reversal would flip the text back).
        return _strip_pages("\n".join(lines))
    except Exception as exc:
        logger.error("OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Text-manipulation analysis (local heuristics)
# ---------------------------------------------------------------------------
def analyze_text_manipulation(text: str) -> Tuple[float, Dict]:
    """Score how manipulative the news text reads, 0..1, with cue detail.

    Deliberately conservative: a single cue family alone never pushes past
    0.55; condemnation requires several independent families + missing
    legitimacy markers.
    """
    detail = {
        "chars": len(text),
        "cues": {},
        "legit_markers": [],
        "has_date": bool(_DATE_PAT.search(text)),
        "has_url": bool(_URL_PAT.search(text)),
        "has_social_handles": bool(_HASHTAG_PAT.search(text) or _HANDLE_PAT.search(text)),
    }
    if len(text.strip()) < 20:
        detail["cues"]["insufficient_text"] = 0.0
        return 0.0, detail

    lower = text.lower()

    urgency = _contains_any(lower, URGENCY_BAIT)
    engagement = _contains_any(lower, ENGAGEMENT_BAIT)
    authority = _contains_any(lower, UNSOURCED_AUTHORITY)
    shock = _contains_any(lower, EMOTIONAL_SHOCK)
    legit = _contains_any(lower, LEGIT_MARKERS)
    detail["legit_markers"] = legit

    # question-mark rain: >=3 question marks per 100 chars is intrigue-bait
    q_marks = len(_QUESTION_RAIN.findall(text))
    q_density = q_marks / max(len(text) / 100.0, 1.0)

    caps_words = sum(1 for w in re.findall(r"[A-Za-z]{3,}", text) if w.isupper())
    exclaims = text.count("!")

    fam = 0  # independent cue families present
    score = 0.0
    if urgency:
        fam += 1
        score += min(0.18 * len(urgency), 0.30)
    if engagement:
        fam += 1
        score += min(0.22 * len(engagement), 0.38)
    if authority:
        fam += 1
        score += min(0.15 * len(authority), 0.30)
    if shock:
        fam += 1
        score += min(0.10 * len(shock), 0.20)
    if q_density >= 1.5:
        fam += 1
        score += 0.12
    if exclaims >= 3:
        fam += 1
        score += 0.08
    if caps_words >= 3:
        fam += 1
        score += 0.08

    # missing provenance markers is itself a mild signal
    if not legit and not detail["has_url"] and not detail["has_date"]:
        fam += 1
        score += 0.12
    detail["cues"] = {
        "urgency": urgency,
        "engagement_bait": engagement,
        "unsourced_authority": authority,
        "emotional_shock": shock,
        "question_density": round(q_density, 2),
        "exclamations": exclaims,
        "caps_words": caps_words,
        "cue_families": fam,
    }

    # require multi-family agreement for a high score
    if fam <= 1:
        score = min(score, 0.35)
    elif fam == 2:
        score = min(score, 0.55)
    # legitimacy markers pull back
    if legit:
        score *= 0.72
    if detail["has_url"]:
        score *= 0.9
    if detail["has_date"]:
        score *= 0.95

    return round(min(score, 1.0), 4), detail


# ---------------------------------------------------------------------------
# Deep signal: source provenance
# ---------------------------------------------------------------------------
def _extract_urls(text: str) -> List[str]:
    return [m.group(0).rstrip(".,;:)]") for m in _URL_PAT.finditer(text)]


# Bare-domain patterns: shorteners and suspicious TLDs often appear without
# a protocol in screenshots ("bit.ly/xyz", "news-leak.xyz")
_SHORTENER_PAT = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in URL_SHORTENERS) + r")\b\S*",
    re.IGNORECASE,
)
_SUSPICIOUS_TLD_PAT = re.compile(
    r"[\w-]+(" + "|".join(re.escape(t) for t in SUSPICIOUS_TLDS) + r")\b\S*",
    re.IGNORECASE,
)


def analyze_source_provenance(text: str) -> Optional[Tuple[float, Dict]]:
    """Score how checkable the quoted sources are, 0..1 (None if no text).

    0 = named institutions / official domains; higher = shorteners hiding the
    destination, suspicious TLDs, or purely anonymous attribution.
    """
    if len(text.strip()) < 20:
        return None
    lower = text.lower()
    urls = _extract_urls(text)
    shorteners = sorted(
        {*(u for u in urls if any(s in u.lower() for s in URL_SHORTENERS)),
         *(m.group(0) for m in _SHORTENER_PAT.finditer(text))}
    )
    suspicious = sorted(
        {*(u for u in urls if any(t in u.lower() for t in SUSPICIOUS_TLDS)),
         *(m.group(0) for m in _SUSPICIOUS_TLD_PAT.finditer(text))}
    )
    named = _contains_any(lower, NAMED_SOURCES)
    anonymous_authority = _contains_any(lower, UNSOURCED_AUTHORITY)

    score = 0.0
    score += min(0.50 * len(shorteners), 0.65)
    score += min(0.40 * len(suspicious), 0.70)
    has_any_link = bool(urls)
    if not has_any_link and not shorteners and not named:
        score += 0.35  # claim with no checkable source at all
    if anonymous_authority and not named:
        score += 0.20  # "sources confirm" with nobody named
    if named:
        score *= 0.40
    if urls and not shorteners and not suspicious:
        score *= 0.80  # a real link is a checkable path

    detail = {
        "urls": urls[:5],
        "shorteners": shorteners[:5],
        "suspicious_tlds": suspicious[:5],
        "named_sources": named[:5],
        "anonymous_only": bool(anonymous_authority and not named),
        "no_source": bool(not urls and not named),
    }
    return round(min(score, 1.0), 4), detail


# ---------------------------------------------------------------------------
# Deep signal: dates
# ---------------------------------------------------------------------------
def _parse_dates(text: str) -> List[date]:
    found: List[date] = []
    for m in _ISO_PAT.finditer(text):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    for m in _DMY_PAT.finditer(text):
        try:
            found.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            continue
    month_idx = {name: i + 1 for i, name in enumerate(_AR_MONTH_NAMES)}
    for m in _AR_DATE_PAT.finditer(text):
        try:
            found.append(date(int(m.group(3)), month_idx.get(m.group(2), 0), int(m.group(1))))
        except ValueError:
            continue
    return found


def analyze_dates(text: str) -> Optional[Tuple[float, Dict]]:
    """Score date credibility, 0..1 (None if no text).

    Flags: impossible future dates, 'breaking' news riding a stale date,
    and claims with no timestamp at all.
    """
    if len(text.strip()) < 20:
        return None
    lower = text.lower()
    dates = _parse_dates(text)
    today = date.today()

    future = [d.isoformat() for d in dates if d > today]
    stale = [d.isoformat() for d in dates if (today - d).days > 30]
    urgency = _contains_any(lower, URGENCY_BAIT)
    stale_with_urgency = bool(urgency and stale)
    has_relative = any(w in lower for w in _RELATIVE_DATE_WORDS)
    missing = not dates and not has_relative

    score = 0.0
    if future:
        score += 0.55  # impossible date = fabrication marker
    if stale_with_urgency:
        score += 0.30  # old story sold as breaking
    if missing:
        score += 0.15  # no timestamp anywhere
    if has_relative and not dates:
        score = min(score + 0.05, score + 0.05)  # vague "today" only

    detail = {
        "dates_found": [d.isoformat() for d in dates[:5]],
        "future_dates": future[:3],
        "stale_with_urgency": stale_with_urgency,
        "missing_date": missing,
    }
    return round(min(score, 1.0), 4), detail


# ---------------------------------------------------------------------------
# Deep signal: logical coherence
# ---------------------------------------------------------------------------
def analyze_logic(text: str) -> Optional[Tuple[float, Dict]]:
    """Score logical red flags, 0..1 (None if no text).

    Absolutist overreach, unfalsifiable framing, and raw fear with zero
    concrete entities or numbers to check.
    """
    if len(text.strip()) < 20:
        return None
    lower = text.lower()

    absolutes = _contains_any(lower, ABSOLUTES)
    unfalsifiable = _contains_any(lower, UNFALSIFIABLE)
    shock = _contains_any(lower, EMOTIONAL_SHOCK)
    has_numbers = bool(re.search(r"\d", text))
    named = _contains_any(lower, NAMED_SOURCES)
    fear_over_evidence = len(shock) >= 2 and not has_numbers and not named

    fam = 0
    if len(absolutes) >= 2:
        fam += 1
    if unfalsifiable:
        fam += 1
    if fear_over_evidence:
        fam += 1

    score = round(min(0.15 * fam, 0.60), 4)
    detail = {
        "absolutes": absolutes[:5],
        "unfalsifiable": unfalsifiable[:5],
        "fear_over_evidence": fear_over_evidence,
        "families": fam,
    }
    return score, detail


# ---------------------------------------------------------------------------
# Deep signal: agenda framing
# ---------------------------------------------------------------------------
def analyze_agenda(text: str) -> Optional[Tuple[float, Dict]]:
    """Score agenda-driven framing, 0..1 (None if no text).

    Conspiracy narratives, us-vs-them polarization, financial bait,
    and calls to action/incitement.
    """
    if len(text.strip()) < 20:
        return None
    lower = text.lower()

    conspiracy = _contains_any(lower, CONSPIRACY)
    us_them = _contains_any(lower, US_VS_THEM)
    financial = _contains_any(lower, FINANCIAL_BAIT)
    incite = _contains_any(lower, INCITEMENT)

    fam = sum(bool(x) for x in (conspiracy, us_them, financial, incite))
    score = round(min(0.20 * fam, 0.80), 4)
    if conspiracy and us_them:
        score = min(score + 0.10, 0.90)  # classic radicalization pairing

    detail = {
        "conspiracy": conspiracy[:5],
        "us_vs_them": us_them[:5],
        "financial_bait": financial[:5],
        "incitement": incite[:5],
        "families": fam,
    }
    return score, detail


# ---------------------------------------------------------------------------
# External fact-check (Google Fact Check Tools) — optional, fails safe
# ---------------------------------------------------------------------------
def _claim_candidates(text: str, max_len: int = 180) -> List[str]:
    """Pull headline-like claim sentences to query the fact-check index."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    claims: List[str] = []
    for ln in lines:
        if 25 <= len(ln) <= max_len and not _URL_PAT.match(ln):
            claims.append(ln)
        if len(claims) >= 3:
            break
    if not claims and len(text.strip()) >= 25:
        claims.append(text.strip()[:max_len])
    return claims


def fact_check_claims(text: str) -> Dict:
    """Query Google Fact Check Tools for published claim reviews.

    Returns {status, disputed, verified, results:[...]}.
    status: "disabled" | "unavailable" | "no_coverage" | "ok"
    Any network/auth problem fails safe (status != "ok" => weight 0).
    """
    out: Dict = {"status": "disabled", "disputed": 0, "verified": 0, "results": []}
    if not settings.NEWS_FACT_CHECK_ENABLED:
        return out
    api_key = settings.GOOGLE_FACT_CHECK_API_KEY
    if not api_key:
        out["status"] = "unavailable"
        return out

    import requests  # local import: only needed on this path

    claims = _claim_candidates(text)
    if not claims:
        out["status"] = "no_coverage"
        return out

    try:
        any_result = False
        for claim in claims:
            resp = requests.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"query": claim, "key": api_key, "pageSize": 5},
                timeout=6,
            )
            if resp.status_code != 200:
                out["status"] = "unavailable"
                logger.warning("Fact-check API HTTP %s", resp.status_code)
                return out
            data = resp.json() or {}
            for review in data.get("results", []):
                any_result = True
                claim_rev = review.get("claimReview", [{}])[0] if review.get("claimReview") else {}
                rating = str(claim_rev.get("textualRating", "")).lower()
                url = claim_rev.get("url", "")
                publisher = claim_rev.get("publisher", {}).get("name", "")
                disputed_kw = ["false", "fake", "miscaptioned", "fabricated", "كاذب", "مضلل", "غير صحيح", "تلاعب"]
                verified_kw = ["true", "correct", "accurate", "صحيح", "حقيقي", "دقيق"]
                if any(k in rating for k in disputed_kw):
                    out["disputed"] += 1
                elif any(k in rating for k in verified_kw):
                    out["verified"] += 1
                out["results"].append({
                    "rating": claim_rev.get("textualRating", ""),
                    "publisher": publisher,
                    "url": url,
                })
        out["status"] = "ok" if any_result else "no_coverage"
    except Exception as exc:
        logger.warning("Fact-check call failed (fails safe): %s", exc)
        out["status"] = "unavailable"
    return out


# ---------------------------------------------------------------------------
# Arbiter — weighted fusion with anchors
# ---------------------------------------------------------------------------
def _news_arbiter(
    text_score: float,
    forensic_fake: float,
    factcheck: Dict,
    ocr_ok: bool,
    deep: Optional[Dict[str, Tuple[float, Dict]]] = None,
) -> Tuple[float, List[str]]:
    """Weighted fusion -> (misinformation_prob, audit lines)."""
    audit: List[str] = []
    weights: Dict[str, float] = {}
    parts: Dict[str, float] = {}

    if ocr_ok:
        weights["text"] = W_TEXT
        parts["text"] = text_score
        audit.append(f"text-manipulation: {text_score:.2f} (w={W_TEXT})")
    else:
        audit.append("text-manipulation: OCR unavailable — excluded from fusion")

    weights["forensic"] = W_FORENSIC
    parts["forensic"] = forensic_fake
    audit.append(f"image-forensics: {forensic_fake:.2f} (w={W_FORENSIC})")

    fc_status = factcheck.get("status", "disabled")
    disputed = factcheck.get("disputed", 0)
    verified = factcheck.get("verified", 0)
    if fc_status == "ok" and (disputed or verified):
        weights["factcheck"] = W_FACTCHECK
        fc_score = 1.0 if disputed > verified else (0.0 if verified > disputed else 0.5)
        parts["factcheck"] = fc_score
        audit.append(
            f"fact-check: {disputed} disputed / {verified} verified (w={W_FACTCHECK})"
        )
    else:
        audit.append(f"fact-check: {fc_status} — no external evidence fused")

    # --- deep analytical voters (source / date / logic / agenda) ---
    if deep:
        src = deep.get("source")
        if src:
            s, d = src
            weights["source"] = W_SOURCE
            parts["source"] = s
            audit.append(
                f"source-provenance: {s:.2f} (w={W_SOURCE})"
                f" — shorteners={len(d.get('shorteners', []))},"
                f" suspicious_tld={len(d.get('suspicious_tlds', []))},"
                f" named={bool(d.get('named_sources'))},"
                f" no_source={d.get('no_source', False)}"
            )
        dt = deep.get("date")
        if dt:
            s, d = dt
            weights["date"] = W_DATE
            parts["date"] = s
            audit.append(
                f"date-analysis: {s:.2f} (w={W_DATE})"
                f" — future={bool(d.get('future_dates'))},"
                f" stale+urgency={d.get('stale_with_urgency', False)},"
                f" missing={d.get('missing_date', False)}"
            )
        lg = deep.get("logic")
        if lg:
            s, d = lg
            weights["logic"] = W_LOGIC
            parts["logic"] = s
            audit.append(
                f"logic-coherence: {s:.2f} (w={W_LOGIC})"
                f" — absolutes={len(d.get('absolutes', []))},"
                f" unfalsifiable={len(d.get('unfalsifiable', []))},"
                f" fear_over_evidence={d.get('fear_over_evidence', False)}"
            )
        ag = deep.get("agenda")
        if ag:
            s, d = ag
            weights["agenda"] = W_AGENDA
            parts["agenda"] = s
            audit.append(
                f"agenda-framing: {s:.2f} (w={W_AGENDA})"
                f" — conspiracy={bool(d.get('conspiracy'))},"
                f" us_vs_them={bool(d.get('us_vs_them'))},"
                f" financial={bool(d.get('financial_bait'))},"
                f" incitement={bool(d.get('incitement'))}"
            )

    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.5, audit + ["arbiter: no signals available — neutral"]
    # Plain weighted mean: log-fusion overweights tiny forensic probs when the
    # text voter drops out (0.1^0.3 => 0.5 — reads as alarm for no reason).
    fused = float(sum(w * parts[k] for k, w in weights.items()) / total_w)
    fused = min(max(fused, 0.0), 1.0)

    # --- anchors (mirror the provenance anchor in detector.py) ---
    if disputed >= 2:
        fused = max(fused, NEWS_FAKE_ANCHOR)
        audit.append(f"anchor: {disputed} independent disputed reviews => floor {NEWS_FAKE_ANCHOR}")
    elif disputed == 1:
        fused = max(fused, 0.75)
        audit.append("anchor: 1 disputed review => floor 0.75")
    if verified >= 2 and disputed == 0:
        fused = min(fused, NEWS_TRUE_FLOOR)
        audit.append(f"anchor: {verified} verified-true reviews => ceiling {NEWS_TRUE_FLOOR}")

    audit.append(f"misinformation_prob: {fused:.4f}")
    return round(fused, 4), audit


def classify_news_verdict(p: float) -> str:
    if p > UNCERTAIN_BAND[1]:
        return "misleading"
    if p < UNCERTAIN_BAND[0]:
        return "likely_fine"
    return "suspicious"


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def analyze_news_screenshot(image: Image.Image, raw_bytes: bytes = None) -> Dict:
    """Run the news-misinformation pipeline on a screenshot upload."""
    # 1) OCR
    extracted_text = extract_text(image)
    ocr_ok = bool(extracted_text.strip())

    # 2) Text manipulation score (0 if OCR failed)
    if ocr_ok:
        text_score, text_detail = analyze_text_manipulation(extracted_text)
    else:
        text_score, text_detail = 0.0, {"chars": 0, "cues": {"ocr_unavailable": True}}

    # 3-6) Deep analytical voters: sources, dates, logic, agenda
    deep: Dict[str, Tuple[float, Dict]] = {}
    if ocr_ok:
        for key, fn in (
            ("source", analyze_source_provenance),
            ("date", analyze_dates),
            ("logic", analyze_logic),
            ("agenda", analyze_agenda),
        ):
            try:
                res = fn(extracted_text)
                if res is not None:
                    deep[key] = res
            except Exception as exc:  # a broken analyzer must not sink the scan
                logger.warning("deep analyzer %s failed: %s", key, exc)

    # 7) Image forensics (reuse the deepfake ensemble + provenance)
    try:
        from app.services.detector import analyze_image_forgery, last_provenance_hit

        _, forensic_fake, _, _ = analyze_image_forgery(image, raw_bytes=raw_bytes)
        provenance = last_provenance_hit()
    except Exception as exc:
        logger.error("Forensic sub-scan failed: %s", exc)
        forensic_fake, provenance = 0.5, ""

    # +) External fact-check (optional, fails safe)
    factcheck = fact_check_claims(extracted_text) if ocr_ok else {"status": "disabled", "disputed": 0, "verified": 0, "results": []}

    # Arbiter fusion + anchors
    misinfo_prob, audit = _news_arbiter(text_score, forensic_fake, factcheck, ocr_ok, deep=deep)

    if provenance:  # AI-generated screenshot content itself: raise doubt
        misinfo_prob = max(misinfo_prob, 0.80)
        audit.append(f"anchor: image provenance '{provenance}' => floor 0.80")

    verdict = classify_news_verdict(misinfo_prob)
    confidence = round(max(misinfo_prob, 1.0 - misinfo_prob), 4)

    deep_out = {
        k: {"score": s, "detail": d}
        for k, (s, d) in deep.items()
    }

    return {
        "status": "success",
        "verdict": verdict,
        "misinformation_prob": misinfo_prob,
        "confidence": confidence,
        "extracted_text": extracted_text,
        "ocr_available": ocr_ok,
        "text_analysis": text_detail,
        "deep_analysis": deep_out,
        "forensic_fake_prob": round(float(forensic_fake), 4),
        "image_provenance": provenance,
        "fact_check": factcheck,
        "arbiter_audit": audit,
        "thresholds": {
            "misleading_above": UNCERTAIN_BAND[1],
            "suspicious_band": list(UNCERTAIN_BAND),
            "weights": {
                "text": W_TEXT,
                "forensic": W_FORENSIC,
                "factcheck": W_FACTCHECK,
                "source": W_SOURCE,
                "date": W_DATE,
                "logic": W_LOGIC,
                "agenda": W_AGENDA,
            },
        },
    }
