"""Verdict engine — rules only, no model code, no invented text.

Inputs (all explicit; nothing is assumed):

* ``models``      — per-detector results: ``{id, status: ok|error|skipped,
                    prob_fake?, reason?, error?}`` (the four detectors' real
                    outputs, e.g. from ``detector.last_votes()``).
* ``forensics``   — algorithmic check results:
                    ``{id, status, flag?, axes?, detail?}`` (m3 producers).
* ``authenticity``— one-way signal: ``{present: bool, signal_ids: [...]}``.
* ``settle``      — direct-settle evidence (known-forgery hash, trusted C2PA,
                    fact-check article match).
* ``source``      — source-inspection facts for the Source Check axis
                    (EXIF/camera/date/GPS), or None when not run.

Decision order (rules from ``backend/verdict_config.json``):

1. **Direct settle** — decisive evidence bypasses k-of-N: known-forgery hash
   (pHash AND dHash agreeing within the configured Hamming distance), a C2PA
   manifest with a cryptographically valid signature declaring generation
   (trust-list status is reported in the text, never assumed), or a recorded
   fact-check article match.
2. **Insufficient evidence** — fewer than 2 working generation detectors
   (``min_working_generation_models``) => ``Investigate``.
3. **Escalation to "AI Detected"** — needs >= ``min_agreeing_signals`` (fixed
   k=2) agreeing signals AND at least one of them a *model* flag: algorithmic
   checks are supporting signals and can never raise a verdict alone, nor can
   they exceed ``Investigate``.
4. **One-way authenticity** — an authenticity signal blocks escalation toward
   AI (disputed evidence -> ``Investigate``); it never *causes* escalation and
   never forces clearance.
5. **Clearance to "No AI Detected"** — >= ``min_clearing_models`` clearing
   detectors with no counter-flags (``max_model_flags_allowed`` /
   ``max_forensic_flags_allowed``, both 0 by default). A single strong
   dissenting detector therefore prevents "No AI Detected" — the honest
   outcome is ``Investigate`` with the disagreement shown.

Per-model flag/clear bands reuse the EXISTING thresholds from detector.py
(``QUALITY_TIER_THRESHOLDS`` condemnation bar / ``VERDICT_REAL_THRESHOLD``
clear bar): the engine *classifies* model outputs, it never changes them.

"Possible Edits" is mechanically unreachable while the registry holds no
editing model (project constant #5): any rule that would emit it is
downgraded to ``Investigate``.

All displayed text (``why_rule``, ``reasoning``, ``human_line``, axis
summaries) is generated here, in English and Arabic, from the rule that fired
plus the actual counts — no verdict sentence is hand-written anywhere else.
"""

from typing import Any, Dict, List, Optional

from app.detectors.registry import editing_detectors
from app.verdict_config import load_rules

# Existing decision thresholds (read-only; owned by detector.py).
from app.services.detector import QUALITY_TIER_THRESHOLDS, VERDICT_REAL_THRESHOLD

FLAG_BAND = "flag"
CLEAR_BAND = "clear"
UNCERTAIN_BAND = "uncertain"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_model_prob(prob: float, quality_tier: str = "good") -> str:
    """Band one detector's fake probability with the EXISTING thresholds."""
    condemnation = QUALITY_TIER_THRESHOLDS.get(quality_tier, 0.70)
    if prob > condemnation:
        return FLAG_BAND
    if prob < VERDICT_REAL_THRESHOLD:
        return CLEAR_BAND
    return UNCERTAIN_BAND


def _valid_label(label: Any) -> bool:
    return isinstance(label, str) and label in (
        "AI Detected",
        "Possible Edits",
        "Investigate",
        "No AI Detected",
    )


def _apply_editing_reservation(label: str) -> str:
    """Constant #5: Possible Edits requires a registered editing model."""
    if label == "Possible Edits" and not editing_detectors():
        return "Investigate"
    return label


def _hash_settle_ok(hash_input: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    cfg = rules["direct_settle"]["known_forgery_hash"]
    if not cfg.get("enabled"):
        return False
    if not (hash_input.get("phash_match") and hash_input.get("dhash_match")):
        return False  # BOTH hashes must agree (constant #5)
    hamming = hash_input.get("hamming")
    if hamming is None:
        return False  # distance unknown -> no settle
    return isinstance(hamming, int) and not isinstance(hamming, bool) and hamming <= cfg["max_hamming"]


# ---------------------------------------------------------------------------
# Axes
# ---------------------------------------------------------------------------

def _axis_ai_generation(models: List[Dict[str, Any]], counts: Dict[str, int]) -> Dict[str, Any]:
    total = len(models)
    if counts["n_working"] == 0:
        return {
            "id": "ai_generation",
            "state": "skipped",
            "reason": {
                "en": "No generation detector produced a result (all failed or were skipped).",
                "ar": "لم ينتج أي كاشف توليد نتيجة (فشل جميعها أو تم تخطّيها).",
            },
        }
    working_note = ""
    working_note_ar = ""
    if counts["n_working"] != total:
        working_note = f" ({counts['n_working']} of {total} produced a result)"
        working_note_ar = f" ({counts['n_working']} من {total} أعطت نتيجة)"
    summary = {
        "en": (
            f"{counts['n_clear']} of {total} AI detectors clear, "
            f"{counts['n_flag']} flag, {counts['n_uncertain']} uncertain{working_note}."
        ),
        "ar": (
            f"{counts['n_clear']} من {total} كواشف التوليد تُصفّي، "
            f"{counts['n_flag']} تنذر، {counts['n_uncertain']} غير حاسمة{working_note_ar}."
        ),
    }
    return {"id": "ai_generation", "state": "ok", "summary": summary}


def _axis_editing_check(
    forensics: List[Dict[str, Any]], rules: Dict[str, Any]
) -> Dict[str, Any]:
    editing_model_registered = bool(editing_detectors())
    editing_checks = [
        c for c in forensics
        if isinstance(c, dict) and "editing_check" in (c.get("axes") or [])
    ]
    flagged = [c for c in editing_checks if c.get("status") == "ok" and c.get("flag")]

    if not editing_model_registered and not editing_checks:
        return {
            "id": "editing_check",
            "state": "not_applicable",
            "reason": {
                "en": (
                    "No editing model is registered and no algorithmic editing check ran; "
                    "algorithmic checks are supporting signals only and can never exceed "
                    "the Investigate verdict."
                ),
                "ar": (
                    "لا نموذج تعديل مسجَّل ولم يعمل أي فحص خوارزمي للتعديل؛ "
                    "الفحوصات الخوارزمية إشارات تعضيدية فقط ولا تتجاوز حكم Investigate أبدًا."
                ),
            },
        }
    if not editing_model_registered:
        cap = rules["escalation"]["algorithmic_checks_max_verdict"]
        return {
            "id": "editing_check",
            "state": "ok",
            "summary": {
                "en": (
                    f"{len(flagged)} of {len(editing_checks)} algorithmic editing checks flagged "
                    f"(supporting signals; verdict capped at {cap} until an editing model is registered)."
                ),
                "ar": (
                    f"{len(flagged)} من {len(editing_checks)} الفحوصات الخوارزمية للتعديل أنذرت "
                    f"(إشارات تعضيدية؛ الحكم مقيّد بـ {cap} حتى تسجيل نموذج تعديل)."
                ),
            },
        }
    # Future path: an editing model is registered (slot exists for it).
    return {
        "id": "editing_check",
        "state": "ok",
        "summary": {
            "en": f"{len(flagged)} of {len(editing_checks)} editing checks flagged.",
            "ar": f"{len(flagged)} من {len(editing_checks)} فحوصات التعديل أنذرت.",
        },
    }


def _axis_source_check(source: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not source:
        return {
            "id": "source_check",
            "state": "not_applicable",
            "reason": {
                "en": "Source inspection (EXIF/C2PA) was not run for this analysis.",
                "ar": "لم يُنفَّذ فحص المصدر (EXIF/C2PA) في هذا التحليل.",
            },
        }
    parts_en: List[str] = []
    parts_ar: List[str] = []
    if source.get("exif_present"):
        camera = source.get("camera")
        date = source.get("datetime")
        if camera:
            parts_en.append(f"EXIF present (camera: {camera})")
            parts_ar.append(f"EXIF موجود (الكاميرا: {camera})")
        else:
            parts_en.append("EXIF present")
            parts_ar.append("EXIF موجود")
        if date:
            parts_en.append(f"date: {date}")
            parts_ar.append(f"التاريخ: {date}")
    else:
        parts_en.append("no EXIF metadata")
        parts_ar.append("لا بيانات EXIF")
    if source.get("gps"):
        parts_en.append("GPS coordinates present")
        parts_ar.append("إحداثيات GPS موجودة")
    if source.get("c2pa"):
        parts_en.append("C2PA manifest present")
        parts_ar.append("بيان C2PA موجود")
    return {
        "id": "source_check",
        "state": "ok",
        "summary": {"en": "; ".join(parts_en) + ".", "ar": "؛ ".join(parts_ar) + "."},
    }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def evaluate(
    models: List[Dict[str, Any]],
    forensics: Optional[List[Dict[str, Any]]] = None,
    authenticity: Optional[Dict[str, Any]] = None,
    settle: Optional[Dict[str, Any]] = None,
    source: Optional[Dict[str, Any]] = None,
    quality_tier: str = "good",
    fused_prob: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply the configured rules to real inputs; return the verdict card."""
    rules = config if config is not None else load_rules()
    forensics = forensics or []
    authenticity = authenticity or {}
    settle = settle or {}

    esc = rules["escalation"]
    clearance = rules["clearance"]

    # ---- classify model votes ----
    disagreement: List[Dict[str, Any]] = []
    n_working = n_flag = n_clear = n_uncertain = 0
    for m in models:
        if not isinstance(m, dict) or m.get("status") != "ok":
            continue
        prob = m.get("prob_fake")
        if not isinstance(prob, (int, float)) or isinstance(prob, bool):
            continue
        n_working += 1
        call = classify_model_prob(float(prob), quality_tier)
        if call == FLAG_BAND:
            n_flag += 1
        elif call == CLEAR_BAND:
            n_clear += 1
        else:
            n_uncertain += 1
        disagreement.append({"id": m.get("id"), "prob_fake": round(float(prob), 4), "call": call})

    flagged_forensics = [
        c for c in forensics
        if isinstance(c, dict) and c.get("status") == "ok" and c.get("flag")
        and c.get("vote_capable") is True  # info-only checks never vote
    ]
    auth_present = bool(authenticity.get("present"))
    auth_ids = authenticity.get("signal_ids") or []

    counts = {
        "n_total": len(models),
        "n_working": n_working,
        "n_flag": n_flag,
        "n_clear": n_clear,
        "n_uncertain": n_uncertain,
        "forensic_flagged": len(flagged_forensics),
        "forensic_total": len([c for c in forensics if isinstance(c, dict) and c.get("status") == "ok"]),
        "authenticity_blocked": False,
        "signal_total": n_flag + len(flagged_forensics),
    }

    # disagreement list only matters when detectors actually disagree
    calls = {d["call"] for d in disagreement}
    has_disagreement = FLAG_BAND in calls and CLEAR_BAND in calls
    disagreement_out = disagreement if has_disagreement else []

    # ---- outlier badge (display-only; consumed by the scores UI) ----
    # Majority is decided among DECISIVE calls only (flag/clear): an
    # "uncertain" model neither votes for the majority nor can be branded an
    # outlier. A tie between decisive camps (or a single decisive camp)
    # yields no majority, so nobody gets the badge.
    decisive_counts: Dict[str, int] = {}
    for d in disagreement:
        if d["call"] in (FLAG_BAND, CLEAR_BAND):
            decisive_counts[d["call"]] = decisive_counts.get(d["call"], 0) + 1
    majority_call: Optional[str] = None
    if decisive_counts:
        top = max(decisive_counts.values())
        leaders = [c for c, n in decisive_counts.items() if n == top]
        if len(leaders) == 1 and len(decisive_counts) > 1:
            majority_call = leaders[0]
    for d in disagreement:
        d["outlier"] = (
            majority_call is not None
            and d["call"] in (FLAG_BAND, CLEAR_BAND)
            and d["call"] != majority_call
        )

    label: Optional[str] = None
    rule_id: Optional[str] = None
    why_rule: Dict[str, str] = {}
    reasoning: Dict[str, str] = {}

    # ---- 1. direct settle (decisive, bypasses k-of-N) ----
    hash_input = settle.get("known_forgery_hash") or {}
    c2pa_input = settle.get("c2pa") or {}
    fc_input = settle.get("fact_check") or {}

    if isinstance(hash_input, dict) and hash_input and _hash_settle_ok(hash_input, rules):
        entry_label = hash_input.get("entry_label")
        label = _apply_editing_reservation(entry_label) if _valid_label(entry_label) else "Investigate"
        rule_id = "direct_settle.known_forgery_hash"
        h = hash_input.get("hamming")
        max_h = rules["direct_settle"]["known_forgery_hash"]["max_hamming"]
        ref = hash_input.get("entry_reference") or ""
        if label == "Investigate":
            why_rule = {
                "en": (
                    f"Direct settle: pHash and dHash both match a known-forgery database entry "
                    f"(Hamming {h} <= {max_h}{', ' + ref if ref else ''}) but the entry declares no "
                    f"usable class, so the honest verdict is Investigate."
                ),
                "ar": (
                    f"حسم مباشر: تطابق pHash وdHash معًا مع قاعدة تزييفات معروفة "
                    f"(هامينغ {h} <= {max_h}{', ' + ref if ref else ''}) لكن المدخل بلا تصنيف صالح، "
                    f"ف الحكم الصادق Investigate."
                ),
            }
        else:
            why_rule = {
                "en": (
                    f"Direct settle: pHash and dHash both match a known-forgery database entry "
                    f"(Hamming {h} <= {max_h}{', ' + ref if ref else ''}); entry class: {label}."
                ),
                "ar": (
                    f"حسم مباشر: تطابق pHash وdHash معًا مع قاعدة تزييفات معروفة "
                    f"(هامينغ {h} <= {max_h}{', ' + ref if ref else ''}); تصنيف المدخل: {label}."
                ),
            }
    elif isinstance(c2pa_input, dict) and c2pa_input.get("hit") and c2pa_input.get("declares_generation") and c2pa_input.get("crypto_valid"):
        label = "AI Detected"
        rule_id = "direct_settle.c2pa_generation"
        detail = c2pa_input.get("detail") or ""
        if c2pa_input.get("trusted"):
            trust_en = "The signer is verified against the configured trust list."
            trust_ar = "تم التحقق من الموقّع مقابل قائمة الثقة المضبوطة."
        else:
            trust_en = "Signer trust was not verified (no configured trust list) — validity here means the signature is cryptographically sound."
            trust_ar = "لم يُتحقق من ثقة الموقّع (لا قائمة ثقة مضبوطة) — الصلاحية هنا تعني سلامة التوقيع تشفيريًا."
        why_rule = {
            "en": (
                "Direct settle: a Content Credentials (C2PA) manifest with a valid "
                f"signature declares this content was generated.{(' ' + detail) if detail else ''} "
                f"{trust_en}"
            ),
            "ar": (
                "حسم مباشر: بيان مصدقي (C2PA) بتوقيع صالح يعلن أن هذا المحتوى وُلّد."
                f"{' ' + detail if detail else ''} {trust_ar}"
            ),
        }
    elif isinstance(fc_input, dict) and fc_input.get("matched"):
        entry_label = fc_input.get("label")
        label = _apply_editing_reservation(entry_label) if _valid_label(entry_label) else "Investigate"
        rule_id = "direct_settle.fact_check_article_match"
        title = fc_input.get("title") or fc_input.get("url") or ""
        why_rule = {
            "en": (
                f"Direct settle: a recorded fact-check article matches this image"
                f"{(' — ' + title) if title else ''}; it settles the review as {label}."
            ),
            "ar": (
                f"حسم مباشر: مقال تدقيق مسجَّل يطابق هذه الصورة"
                f"{(' — ' + title) if title else ''}؛ يُحسم التراجع بـ {label}."
            ),
        }

    # ---- 2. insufficient working models ----
    if label is None and n_working < esc["min_working_generation_models"]:
        label = "Investigate"
        rule_id = "escalation.insufficient_working_models"
        why_rule = {
            "en": (
                f"Only {n_working} of {len(models)} generation detectors produced a result; the "
                f"engine requires at least {esc['min_working_generation_models']} working models "
                f"— verdict: Investigate (insufficient evidence)."
            ),
            "ar": (
                f"{n_working} من {len(models)} كواشف التوليد فقط أعطت نتيجة؛ المحرك يتطلب "
                f"على الأقل {esc['min_working_generation_models']} نماذج عاملة — "
                f"الحكم: Investigate (أدلة غير كافية)."
            ),
        }

    # ---- 3. escalation / clearance / default ----
    signal_total = counts["signal_total"]
    escalation = (
        signal_total >= esc["min_agreeing_signals"] and n_flag >= 1
    )
    if label is None and escalation and auth_present:
        label = "Investigate"
        rule_id = "escalation.blocked_by_authenticity"
        counts["authenticity_blocked"] = True
        why_rule = {
            "en": (
                f"Signals agree ({signal_total} >= {esc['min_agreeing_signals']} required) but an "
                f"authenticity signal is present ({', '.join(auth_ids)}); authenticity blocks "
                f"escalation toward AI — verdict: Investigate (disputed evidence)."
            ),
            "ar": (
                f"الإشارات متفقة ({signal_total} >= {esc['min_agreeing_signals']} المطلوب) لكن "
                f"إشارة أصالة حاضرة ({', '.join(auth_ids)})؛ الإشارة تمنع التصعيد نحو AI — "
                f"الحكم: Investigate (أدلة متنازع عليها)."
            ),
        }
    elif label is None and escalation:
        label = "AI Detected"
        rule_id = "escalation.k_of_n_agreement"
        why_rule = {
            "en": (
                f"{signal_total} independent signals agree ({n_flag} detector flag(s) + "
                f"{counts['forensic_flagged']} forensic flag(s) >= {esc['min_agreeing_signals']} "
                f"required, at least one from a detector) — verdict: AI Detected."
            ),
            "ar": (
                f"{signal_total} إشارة مستقلة متفقة ({n_flag} إنذار نموذج + "
                f"{counts['forensic_flagged']} إنذار جنائي >= {esc['min_agreeing_signals']} "
                f"المطلوب، أحدهما من نموذج) — الحكم: AI Detected."
            ),
        }
    elif label is None and (
        n_clear >= clearance["min_clearing_models"]
        and n_flag <= clearance["max_model_flags_allowed"]
        and counts["forensic_flagged"] <= clearance["max_forensic_flags_allowed"]
    ):
        label = "No AI Detected"
        rule_id = "clearance.model_consensus"
        why_rule = {
            "en": (
                f"{n_clear} of {len(models)} detectors clear (>= {clearance['min_clearing_models']} "
                f"required) with no detector or forensic flags — verdict: No AI Detected."
            ),
            "ar": (
                f"{n_clear} من {len(models)} كواشف تُصفّي (>= {clearance['min_clearing_models']} "
                f"المطلوب) دون أي إنذار من النماذج أو الفحوصات — الحكم: No AI Detected."
            ),
        }
    elif label is None:
        label = "Investigate"
        rule_id = "default.ambiguous_evidence"
        why_rule = {
            "en": (
                f"Evidence meets neither bar: escalation needs >= {esc['min_agreeing_signals']} "
                f"agreeing signals including >= 1 detector flag (have {signal_total}, {n_flag} "
                f"detector flags); clearance needs >= {clearance['min_clearing_models']} clearing "
                f"detectors with zero flags — verdict: Investigate."
            ),
            "ar": (
                f"الأدلة لا تحقق أي شرط: التصعيد يتطلب >= {esc['min_agreeing_signals']} إشارة "
                f"متفقة منها >= إنذار نموذج واحد (الموجود {signal_total}، إنذارات النماذج "
                f"{n_flag})؛ والإخلاء يتطلب >= {clearance['min_clearing_models']} كواشف مُصفّية "
                f"صفر إنذار — الحكم: Investigate."
            ),
        }

    # ---- build reasoning + human line from the counts ----
    parts_en: List[str] = [why_rule["en"]]
    parts_ar: List[str] = [why_rule["ar"]]
    if disagreement_out:
        flagged = [d for d in disagreement_out if d["call"] == FLAG_BAND]
        cleared = [d for d in disagreement_out if d["call"] == CLEAR_BAND]
        en_list = ", ".join(f"{d['id']} {d['prob_fake']:.2f}" for d in disagreement_out)
        ar_list = "، ".join(f"{d['id']} {d['prob_fake']:.2f}" for d in disagreement_out)
        parts_en.append(
            f"Detectors disagree: {en_list} "
            f"(flagged: {', '.join(d['id'] for d in flagged) or 'none'}; "
            f"cleared: {', '.join(d['id'] for d in cleared) or 'none'})."
        )
        parts_ar.append(
            f"الكواشف متنازعة: {ar_list} "
            f"(أنذرت: {', '.join(d['id'] for d in flagged) or 'لا شيء'}؛ "
            f"أُصفّيت: {', '.join(d['id'] for d in cleared) or 'لا شيء'})."
        )
    if quality_tier != "good":
        parts_en.append(f"Specimen quality tier: {quality_tier} (condemnation bar adjusted by existing thresholds).")
        parts_ar.append(f"فئة جودة العينة: {quality_tier} (عتبة الإدانة مضبوطة بالحدود الحالية).")
    if counts["forensic_flagged"]:
        parts_en.append(
            f"{counts['forensic_flagged']} of {counts['forensic_total']} algorithmic forensic checks flagged "
            f"(supporting signals only; they cannot raise a verdict alone)."
        )
        parts_ar.append(
            f"{counts['forensic_flagged']} من {counts['forensic_total']} الفحوصات الجنائية الخوارزمية أنذرت "
            f"(إشارات تعضيدية فقط؛ لا ترفع الحكم وحدها)."
        )
    if auth_present:
        parts_en.append(f"Authenticity signal(s) present: {', '.join(auth_ids)} (one-way: blocks escalation only).")
        parts_ar.append(f"إشارات أصالة حاضرة: {', '.join(auth_ids)} (اتجاه واحد: تمنع التصعيد فقط).")
    reasoning = {"en": " ".join(parts_en), "ar": " ".join(parts_ar)}

    human_parts_en: List[str] = []
    human_parts_ar: List[str] = []
    if n_flag:
        flagged_pairs = [d for d in disagreement if d["call"] == FLAG_BAND]
        flag_names = ", ".join(str(d["id"]) for d in flagged_pairs)
        flag_values = ", ".join(f"{d['id']}={d['prob_fake']:.2f}" for d in flagged_pairs)
        human_parts_en.append(f"Detectors that alerted: {flag_names} ({flag_values}).")
        human_parts_ar.append(f"الكواشف التي أنذرت: {flag_names} ({flag_values}).")
    else:
        human_parts_en.append("No detector crossed the alert threshold.")
        human_parts_ar.append("لم يتجاوز أي كاشف عتبة الإنذار.")
    if disagreement_out:
        human_parts_en.append("The detectors did not fully agree — see the disagreement above.")
        human_parts_ar.append("لم تتفق الكواشف تمامًا — راجع المنازعة أعلاه.")
    human_line = {"en": " ".join(human_parts_en), "ar": " ".join(human_parts_ar)}

    axes = [
        _axis_ai_generation(models, counts),
        _axis_editing_check(forensics, rules),
        _axis_source_check(source),
    ]

    return {
        "label": label,
        "rule_id": rule_id,
        "why_rule": why_rule,
        "reasoning": reasoning,
        "human_line": human_line,
        "axes": axes,
        "counts": counts,
        "disagreement": disagreement_out,
        "fused_prob": fused_prob,
        "models_banded": [d for d in disagreement],
    }


__all__ = [
    "FLAG_BAND",
    "CLEAR_BAND",
    "UNCERTAIN_BAND",
    "classify_model_prob",
    "evaluate",
]
