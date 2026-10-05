"""m5 — research sections: real search links, location and next-step guidance.

This module **never fetches anything**. It only shapes data the analysis
record already carries (file name, EXIF, C2PA signatures, verdict) into:

* real search URLs — every host and pattern here was verified reachable
  before it was written down, and the test suite pins them to an allow-list
  so a typo can never ship as a link,
* an coordinates link when EXIF GPS actually decoded,
* guidance lines generated from the record's own facts (rule-driven, never
  a claim about what a search returned).

When the record carries no usable signal the section reports ``skipped``
with a reason instead of inventing a query — project constants #4 and #5:
no value without a real source, no accuracy claim without evidence.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from app.analysis_schema import set_section

# Every URL this module emits must come from one of these hosts.
ALLOWED_HOSTS = (
    "www.google.com",
    "google.com",
    "duckduckgo.com",
    "yandex.com",
    "www.yandex.com",
    "www.bing.com",
    "bing.com",
    "www.youtube.com",
    "youtube.com",
    "www.reddit.com",
    "reddit.com",
    "x.com",
    "news.google.com",
    "lens.google.com",
    "tineye.com",
    "www.snopes.com",
    "snopes.com",
    "www.politifact.com",
    "politifact.com",
    "fullfact.org",
    "www.fullfact.org",
    "www.openstreetmap.org",
    "archive.org",
    "web.archive.org",
)

# Tokens that carry no search value on their own (camera/OS naming noise).
_GENERIC_TOKENS = {
    "img", "imgs", "image", "images", "photo", "photos", "pic", "pics",
    "picture", "dsc", "dscn", "screenshot", "screen", "shot", "shots",
    "copy", "final", "new", "old", "untitled", "received", "whatsapp",
    "telegram", "download", "downloads", "file", "files", "document",
    "scan", "jpeg", "jpg", "png", "webp", "heic", "gif", "mp4", "vid",
    "capture", "untitled", "sample", "specimen", "test", "demo",
}


def _q(text: str) -> str:
    return quote_plus(text)


def searchable_query(name: Optional[str]) -> Optional[str]:
    """Extract a defensible search phrase from the file's own name.

    Downloaded files often keep a meaningful slug from the page they came
    from ("ronaldo-fan-photo.jpg"); camera and OS names do not
    ("IMG_1234.jpg", "Screenshot_20240101.png"). Only meaningful tokens
    survive, so a generic name yields ``None`` and the caller must report
    ``skipped`` rather than search for noise.
    """
    if not name:
        return None
    stem = name.rsplit(".", 1)[0]
    keep: List[str] = []
    for token in re.split(r"[-_.\s]+", stem):
        if not token or token.isdigit():
            continue
        low = token.lower()
        if low in _GENERIC_TOKENS or len(token) < 3 or len(set(low)) < 3:
            continue
        keep.append(token)
    if not keep:
        return None
    if len(keep) == 1 and len(keep[0]) < 5:
        return None
    return " ".join(keep[:8])


# ---------------------------------------------------------------------------


def web_search_links(query: str) -> List[Dict[str, str]]:
    """General web search shortcuts (verified patterns, no API called)."""
    q = _q(query)
    return [
        {"id": "google", "label": "Google",
         "url": f"https://www.google.com/search?q={q}"},
        {"id": "bing", "label": "Bing",
         "url": f"https://www.bing.com/search?q={q}"},
        {"id": "yandex", "label": "Yandex",
         "url": f"https://yandex.com/search/?text={q}"},
        {"id": "duckduckgo", "label": "DuckDuckGo",
         "url": f"https://duckduckgo.com/?q={q}"},
        {"id": "reddit", "label": "Reddit",
         "url": f"https://www.reddit.com/search/?q={q}"},
        {"id": "google_news", "label": "Google News",
         "url": f"https://news.google.com/search?q={q}"},
        {"id": "bing_news", "label": "Bing News",
         "url": f"https://www.bing.com/news/search?q={q}"},
        {"id": "youtube", "label": "YouTube",
         "url": f"https://www.youtube.com/results?search_query={q}"},
    ]


def dated_query(query: str, when: Optional[str]) -> Optional[Dict[str, str]]:
    """X/Twitter search bounded around a real capture date, if we have one.

    Returns ``None`` unless EXIF actually carried a parseable date, so the
    date filter never shows a range we invented.
    """
    if not when:
        return None
    try:
        capture = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
    except ValueError:
        try:
            capture = datetime.strptime(str(when)[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            return None
    since = (capture - timedelta(days=7)).date().isoformat()
    until = (capture + timedelta(days=7)).date().isoformat()
    q = _q(f"{query} since:{since} until:{until}")
    return {
        "id": "x_dated",
        "label": f"X — posts {since} → {until}",
        "url": f"https://x.com/search?q={q}&f=live",
    }


def fact_check_links(query: str) -> List[Dict[str, str]]:
    """Fact-checker site searches — a search, never a fact-check result."""
    q = _q(query)
    return [
        {"id": "snopes", "label": "Snopes",
         "url": f"https://www.snopes.com/?s={q}"},
        {"id": "politifact", "label": "PolitiFact",
         "url": f"https://www.politifact.com/search/?query={q}"},
        {"id": "fullfact", "label": "Full Fact",
         "url": f"https://fullfact.org/search/?q={q}"},
        {"id": "google_fc", "label": "Google — fact check",
         "url": f"https://www.google.com/search?q={q}+fact+check"},
    ]


def reverse_search_engines() -> List[Dict[str, str]]:
    """Reverse-image engines. None of them accepts a local file over a GET
    parameter, so each entry links to that engine's own upload page and the
    card tells the user the file stays on their device."""
    return [
        {"id": "google_lens", "label": "Google Lens",
         "url": "https://lens.google.com/"},
        {"id": "google_images", "label": "Google Images",
         "url": "https://www.google.com/search?tbm=isch"},
        {"id": "yandex", "label": "Yandex Images",
         "url": "https://yandex.com/images/"},
        {"id": "bing", "label": "Bing visual search",
         "url": "https://www.bing.com/images/search?view=detailv2&iss=sbiupload"},
        {"id": "tineye", "label": "TinEye",
         "url": "https://tineye.com/"},
    ]


def location_links(lat: float, lon: float) -> List[Dict[str, str]]:
    return [
        {"id": "osm", "label": "OpenStreetMap",
         "url": (
             "https://www.openstreetmap.org/"
             f"?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"
         )},
        {"id": "gmaps", "label": "Google Maps",
         "url": f"https://www.google.com/maps?q={lat},{lon}"},
    ]


def archive_links(query: str) -> List[Dict[str, str]]:
    q = _q(query)
    return [
        {"id": "wayback", "label": "Wayback Machine",
         "url": f"https://web.archive.org/web/*/{q}"},
    ]


# ---------------------------------------------------------------------------


def _what_to_do(verdict_label: Optional[str]) -> List[Dict[str, str]]:
    """Immediate actions driven only by the verdict label (rules, not prose
    written per image)."""
    by_label = {
        "AI Detected": [
            {"id": "not_a_photo",
             "en": "Treat it as machine-generated: do not present it as a real photograph.",
             "ar": "تعامل معها كصورة مولَّدة: لا تعرضها كتصوير حقيقي."},
            {"id": "find_origin",
             "en": "Find the original posting and the generator behind it before quoting it.",
             "ar": "ابحث عن النشر الأصلي والمولِّد الذي صنعها قبل الاقتباس بها."},
        ],
        "No AI Detected": [
            {"id": "no_warning_not_proof",
             "en": "No AI warning was raised — that is not proof the image is authentic.",
             "ar": "لم يظهر إنذار ذكاء اصطناعي — وهذا لا يثبت أصالة الصورة."},
            {"id": "reverse_search",
             "en": "Reverse-search the image to see where else it appears and in what context.",
             "ar": "ابحث بصورة عكسة لترى أين ظهرت وفي أي سياق."},
        ],
        "Investigate": [
            {"id": "conflicting_signals",
             "en": "Signals conflict, so no automatic conclusion is safe — read the scores yourself.",
             "ar": "الإشارات متعارضة ولا يصح استنتاج آلي — اقرأ الدرجات بنفسك."},
            {"id": "better_copy",
             "en": "Get a sharper copy if you can: a weak specimen lowers every signal.",
             "ar": "احصل على نسخة أوضح إن أمكن: العينة الضعيفة تخفض كل الإشارات."},
        ],
        "Possible Edits": [
            {"id": "compare_original",
             "en": "Editing is suspected — compare it against a known-original copy.",
             "ar": "يشتبه بتعديل — قارنها بنسخة أصلية معروفة."},
        ],
    }
    return list(by_label.get(verdict_label or "", [
        {"id": "verify_source",
         "en": "Verify where the image came from before relying on it.",
         "ar": "تحقّق من مصدر الصورة قبل الاعتماد عليها."},
    ]))


def _fact_steps(
    *,
    exif_present: bool,
    camera: Optional[str],
    generators: List[str],
    gps: bool,
    disagreement: bool,
    quality_tier: str,
    provenance_hit: str,
) -> List[Dict[str, str]]:
    """Extra guidance lines, each produced by one real signal in the record."""
    steps: List[Dict[str, str]] = []
    if generators:
        joined = ", ".join(g for g in generators if g)
        steps.append({
            "id": "generator_signature",
            "en": f"Generator signature inside the metadata: {joined} — treat the file as AI-generated.",
            "ar": f"توقيع مولِّد داخل البيانات الوصفية: {joined} — تعامل مع الملف كمولَّد بالذكاء الاصطناعي.",
        })
    if provenance_hit:
        steps.append({
            "id": "known_forgery_hash",
            "en": "Its perceptual hash matches a known-forgery entry — confirm against an independent copy.",
            "ar": "تجزئته الإدراكية تطابق سجل تزييف معروف — أكّد مقابل نسخة مستقلة.",
        })
    if disagreement:
        steps.append({
            "id": "models_disagree",
            "en": "The detectors disagree — do not rely on the combined number alone.",
            "ar": "الكواشف متضاربة — لا تعتمد على الرقم المدمج وحده.",
        })
    if gps:
        steps.append({
            "id": "gps_claim",
            "en": "GPS coordinates are present — compare them with the claimed place and date.",
            "ar": "توجد إحداثيات جغرافية — قارنها بالمكان والتاريخ المدّعيان.",
        })
    if exif_present and camera:
        steps.append({
            "id": "camera_exif",
            "en": f"Camera EXIF is present ({camera}) — ask whether that camera could have shot this scene.",
            "ar": f"توجد بيانات كاميرا ({camera}) — اسأل إن كان هذا الكاميرا قد صوّر هذا المشهد.",
        })
    elif not exif_present:
        steps.append({
            "id": "no_exif",
            "en": "No EXIF at all: the file was re-saved or exported, so capture metadata is gone.",
            "ar": "لا EXIF إطلاقًا: أُعيد حفظ الملف أو تصديره، فبيانات التصوير الأصلية اختفت.",
        })
    if quality_tier in ("poor", "fair"):
        steps.append({
            "id": "weak_specimen",
            "en": f"Specimen quality is {quality_tier}: re-upload a sharper copy for a steadier result.",
            "ar": f"جودة العينة {quality_tier}: أعد رفع نسخة أوضح لنتيجة أكثر ثباتًا.",
        })
    return steps[:5]


_FURTHER_BASE = [
    {"id": "ask_for_original",
     "en": "Ask whoever posted it for the original file — an unedited original settles most questions.",
     "ar": "اطلب من الناشر الملف الأصلي — الأصل غير المعدَّل يحسم معظم الأسئلة."},
    {"id": "find_more_copies",
     "en": "Look for other copies: many copies usually mean a traceable origin.",
     "ar": "ابحث عن نسخ أخرى: كثرة النسخ تعني أصلًا يمكن تتبّعه."},
    {"id": "read_the_context",
     "en": "Read the caption, date and surrounding posts — an image is often genuine but used out of context.",
     "ar": "اقرأ التعليق والتاريخ والمنشورات المحيطة — الصورة غالبًا ما تكون حقيقية لكن مستخدمة خارج سياقها."},
]


# ---------------------------------------------------------------------------


def apply_research(
    record: Dict[str, Any],
    *,
    exif_data: Optional[Dict[str, Any]] = None,
    quality_tier: str = "good",
    provenance_hit: str = "",
) -> None:
    """Fill the m5 sections and the ``external`` card of a record.

    Every section lands in ``ok`` or ``skipped``(reason) — never in a
    permanent ``loading`` state and never in ``error`` for "not built yet".
    """
    exif_data = exif_data or {}
    exif_tags = exif_data.get("exif") or {}
    exif_present = bool(exif_data.get("exif_present"))
    gps = exif_data.get("gps") or {}
    lat, lon = gps.get("lat"), gps.get("lon")
    generators = [g for g in (exif_data.get("generator_signatures") or []) if g]
    camera = " ".join(
        str(exif_tags.get(k, "")).strip() for k in ("make", "model")
    ).strip() or None

    verdict = record.get("verdict") or {}
    verdict_label = verdict.get("label") if verdict.get("state") == "ok" else None
    disagreement = bool(verdict.get("disagreement"))

    query = searchable_query((record.get("image") or {}).get("name"))

    # ---- reverse search: engines are always real, the file never moves ----
    set_section(
        record, "reverse_search", "ok",
        data={
            "engines": reverse_search_engines(),
            "note_en": (
                "Your image is not uploaded anywhere: open an engine and attach "
                "the file from your device."
            ),
            "note_ar": (
                "لم تُرفع صورتك إلى أي مكان: افتح المحرّك ثم أرفق الملف من جهازك."
            ),
        },
    )
    record["external"]["links"] = {"state": "ok"}

    # ---- links on the web: needs real text to search for ----
    if query:
        links = web_search_links(query)
        dated = dated_query(query, exif_tags.get("datetime"))
        if dated:
            links.append(dated)
        set_section(
            record, "links_on_web", "ok",
            data={
                "query": query,
                "links": links,
                "note_en": (
                    "Shortcuts to search engines — we did not crawl the web, "
                    "and a hit here proves nothing by itself."
                ),
                "note_ar": (
                    "اختصارات لمحركات البحث — لم نتصفّح الويب، ووجود نتيجة هنا "
                    "لا يثبت شيئًا بذاته."
                ),
            },
        )
        record["external"]["web_presence"] = {"state": "ok"}
    else:
        reason = (
            "The file name carries no searchable text; use reverse image "
            "search instead."
        )
        set_section(
            record, "links_on_web", "skipped", reason=reason,
            data={
                "reason_en": reason,
                "reason_ar": "اسم الملف لا يحمل نصًا قابلًا للبحث؛ استخدم البحث "
                             "العكسي بالصورة بدلاً منه.",
            },
        )
        record["external"]["web_presence"] = {"state": "skipped", "reason": reason}

    # ---- fact-check monitor: a search, never a fact-check verdict ----
    if query:
        set_section(
            record, "fact_check_monitor", "ok",
            data={
                "query": query,
                "links": fact_check_links(query),
                "note_en": (
                    "No fact-check API was called: these open searches on "
                    "fact-checking sites for you to read."
                ),
                "note_ar": (
                    "لم يُستدعَ أي واجهة تحقق: هذه تفتح بحثًا في مواقع التحقق "
                    "لتقرأها بنفسك."
                ),
            },
        )
        record["external"]["fact_check"] = {"state": "ok"}
    else:
        reason = "No claim text in this file to search fact-checkers with."
        set_section(
            record, "fact_check_monitor", "skipped", reason=reason,
            data={
                "reason_en": reason,
                "reason_ar": "لا نص ادعاء في هذا الملف لبحث مواقع التحقق به.",
            },
        )
        record["external"]["fact_check"] = {"state": "skipped", "reason": reason}

    # ---- location: only when EXIF GPS actually decoded ----
    if lat is not None and lon is not None:
        set_section(
            record, "location", "ok",
            data={
                "lat": lat,
                "lon": lon,
                "links": location_links(float(lat), float(lon)),
                "note_en": (
                    "Coordinates come from EXIF GPS — they say where the file "
                    "claims to have been captured, not where it was posted."
                ),
                "note_ar": (
                    "الإحداثيات من GPS داخل EXIF — تقول أين يدّعي الملف أنه "
                    "صُوِّر، لا أين نُشر."
                ),
            },
        )
        record["external"]["location"] = {"state": "ok"}
    else:
        reason = (
            "No GPS coordinates in EXIF — nothing to place."
            if exif_present else
            "No EXIF in this file — nothing to place."
        )
        reason_ar = (
            "لا إحداثيات GPS في EXIF — لا شيء ليُحدَّد موقعه."
            if exif_present else
            "لا توجد بيانات EXIF في هذا الملف — لا شيء ليُحدَّد موقعه."
        )
        set_section(
            record, "location", "skipped", reason=reason,
            data={"reason_en": reason, "reason_ar": reason_ar},
        )
        record["external"]["location"] = {"state": "skipped", "reason": reason}

    # ---- what to do next (verdict rules + record facts) ----
    steps = _what_to_do(verdict_label)
    steps += _fact_steps(
        exif_present=exif_present,
        camera=camera,
        generators=generators,
        gps=bool(lat is not None and lon is not None),
        disagreement=disagreement,
        quality_tier=quality_tier,
        provenance_hit=provenance_hit,
    )
    set_section(
        record, "what_to_do_next", "ok",
        data={"steps": steps[:7], "rule": "verdict_label + record signals"},
    )

    # ---- further investigation ----
    data: Dict[str, Any] = {
        "steps": list(_FURTHER_BASE),
        "rule": "fixed checklist, extended with record signals",
    }
    if query:
        data["links"] = fact_check_links(query) + archive_links(query)
    set_section(record, "further_investigation", "ok", data=data)

    # ---- external card: one honest roll-up ----
    subs = [
        record["external"]["web_presence"],
        record["external"]["fact_check"],
        record["external"]["links"],
        record["external"]["location"],
    ]
    if any(s.get("state") == "ok" for s in subs):
        record["external"].update(
            state="ok",
            summary={
                "en": "Search shortcuts and metadata-derived links only — nothing was queried for you.",
                "ar": "اختصارات بحث وروابط مشتقة من البيانات الوصفية فقط — لم يُسأل أي خدمة نيابةً عنك.",
            },
        )
    else:
        record["external"].update(
            state="skipped",
            reason="No searchable text and no GPS coordinates in this file.",
            reason_ar="لا نص قابل للبحث ولا إحداثيات GPS في هذا الملف.",
        )


__all__ = [
    "ALLOWED_HOSTS",
    "apply_research",
    "archive_links",
    "dated_query",
    "fact_check_links",
    "location_links",
    "reverse_search_engines",
    "searchable_query",
    "web_search_links",
]
