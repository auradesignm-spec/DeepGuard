"""Tests for the news-misinformation pipeline (pure logic; OCR + HTTP mocked)."""
from datetime import date, timedelta

import pytest

import app.services.news_detector as nd


# ---------------------------------------------------------------------------
# Text-manipulation heuristics
# ---------------------------------------------------------------------------

MANIPULATIVE_AR = (
    "عاجل جداً!! مصادر مؤكدة تكشف سر خطير!!! "
    "شارك قبل الحذف قبل فوات الأوان... هل تعلم ماذا يحدث؟؟؟"
)

CLEAN_NEWS_AR = (
    "المصدر: رويترز — قالت وزارة الصحة في بيان اليوم 2026-09-30 إن الفحوصات "
    "الروتينية لم تُظهر أي مخاطر، ونفت الشائعات المتداولة عبر الرابط الرسمي."
)


def test_manipulative_text_scores_high():
    score, detail = nd.analyze_text_manipulation(MANIPULATIVE_AR)
    assert score >= 0.6
    assert detail["cues"]["cue_families"] >= 3
    assert detail["cues"]["engagement_bait"]
    assert detail["cues"]["unsourced_authority"]


def test_clean_news_scores_low():
    score, detail = nd.analyze_text_manipulation(CLEAN_NEWS_AR)
    assert score <= 0.35
    assert detail["legit_markers"], "legitimacy markers should be detected"
    assert detail["has_date"]


def test_short_text_neutral():
    score, detail = nd.analyze_text_manipulation("قصير")
    assert score == 0.0
    assert "insufficient_text" in detail["cues"]


def test_single_cue_family_capped():
    # urgency only, no other family -> capped below suspicion
    text = "عاجل: اجتماع مجلس الوزراء ظهر اليوم. المصدر: وكالة الأنباء السعودية"
    score, detail = nd.analyze_text_manipulation(text)
    assert score <= 0.35


# ---------------------------------------------------------------------------
# Claim extraction + fact-check (mocked HTTP)
# ---------------------------------------------------------------------------

def test_claim_candidates_picks_lines():
    text = "عنوان الخبر المهم جداً هنا بجملة كافية للفحص\nhttps://example.com\nمصدر: رويترز"
    claims = nd._claim_candidates(text)
    assert len(claims) == 1
    assert claims[0].startswith("عنوان")


def test_fact_check_disabled_when_no_key(monkeypatch):
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", True)
    monkeypatch.setattr(nd.settings, "GOOGLE_FACT_CHECK_API_KEY", "")
    out = nd.fact_check_claims(MANIPULATIVE_AR)
    assert out["status"] == "unavailable"


def test_fact_check_disputed_anchor(monkeypatch):
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", True)
    monkeypatch.setattr(nd.settings, "GOOGLE_FACT_CHECK_API_KEY", "test-key")

    class FakeResp:
        status_code = 200
        def json(self):
            return {
                "results": [
                    {"claimReview": [{"textualRating": "False", "url": "https://x/1", "publisher": {"name": "AFP"}}]},
                    {"claimReview": [{"textualRating": "Fabricated", "url": "https://x/2", "publisher": {"name": "Reuters"}}]},
                ]
            }

    class FakeRequests:
        @staticmethod
        def get(*a, **k):
            return FakeResp()

    import sys, types
    fake_mod = types.ModuleType("requests")
    fake_mod.get = FakeRequests.get
    monkeypatch.setitem(sys.modules, "requests", fake_mod)

    out = nd.fact_check_claims(MANIPULATIVE_AR)
    assert out["status"] == "ok"
    assert out["disputed"] >= 2


def test_fact_check_network_failure_fails_safe(monkeypatch):
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", True)
    monkeypatch.setattr(nd.settings, "GOOGLE_FACT_CHECK_API_KEY", "test-key")

    import sys, types
    fake_mod = types.ModuleType("requests")
    def boom(*a, **k):
        raise ConnectionError("offline")
    fake_mod.get = boom
    monkeypatch.setitem(sys.modules, "requests", fake_mod)

    out = nd.fact_check_claims(MANIPULATIVE_AR)
    assert out["status"] == "unavailable"  # fails safe, no condemnation


# ---------------------------------------------------------------------------
# Arbiter fusion + anchors
# ---------------------------------------------------------------------------

def test_arbiter_disputed_anchors_high():
    fc = {"status": "ok", "disputed": 2, "verified": 0, "results": []}
    p, audit = nd._news_arbiter(0.4, 0.2, fc, ocr_ok=True)
    assert p >= nd.NEWS_FAKE_ANCHOR
    assert any("anchor" in a for a in audit)


def test_arbiter_verified_anchors_low():
    fc = {"status": "ok", "disputed": 0, "verified": 2, "results": []}
    p, audit = nd._news_arbiter(0.5, 0.5, fc, ocr_ok=True)
    assert p <= nd.NEWS_TRUE_FLOOR


def test_arbiter_without_ocr_excludes_text():
    p_with, _ = nd._news_arbiter(0.9, 0.1, {"status": "disabled"}, ocr_ok=True)
    p_without, audit = nd._news_arbiter(0.9, 0.1, {"status": "disabled"}, ocr_ok=False)
    assert p_without < p_with
    # forensic 0.1 with no text voter must read as LOW, not alarm
    assert p_without < 0.4
    assert any("OCR unavailable" in a for a in audit)


def test_verdict_bands():
    assert nd.classify_news_verdict(0.8) == "misleading"
    assert nd.classify_news_verdict(0.5) == "suspicious"
    assert nd.classify_news_verdict(0.2) == "likely_fine"


# ---------------------------------------------------------------------------
# Deep signal: source provenance
# ---------------------------------------------------------------------------

def test_source_shortener_scores_high():
    text = "اقرأ التفاصيل كاملة عبر الرابط التالي bit.ly/xyz123 وشارك الموضوع مع الجميع الآن فوراً"
    out = nd.analyze_source_provenance(text)
    assert out is not None
    s, d = out
    assert s >= 0.5
    assert d["shorteners"]


def test_source_named_agency_scores_low():
    text = "قالت وزارة الصحة في بيان رسمي عبر موقع reuters.com أن الفحوصات الروتينية لم تُظهر أي مخاطر صحية على المواطنين"
    out = nd.analyze_source_provenance(text)
    s, d = out
    assert s <= 0.3
    assert d["named_sources"]


def test_source_anonymous_only_scores_mid():
    text = "مصادر مؤكدة تكشف أن الأمر يتعلق بقرار كبير سيغير كل شيء في الأيام المقبلة القريبة جداً"
    out = nd.analyze_source_provenance(text)
    s, d = out
    assert d["anonymous_only"] is True
    assert s >= 0.4


# ---------------------------------------------------------------------------
# Deep signal: dates
# ---------------------------------------------------------------------------

def test_date_future_flagged():
    future = (date.today() + timedelta(days=30)).isoformat()
    text = f"في تقرير بتاريخ {future} أعلنت الجهات المختصة عن نتائج مهمة"
    out = nd.analyze_dates(text)
    s, d = out
    assert d["future_dates"]
    assert s >= 0.5


def test_date_stale_sold_as_breaking():
    stale = (date.today() - timedelta(days=90)).isoformat()
    text = f"عاجل: بتاريخ {stale} وقعت الحادثة الكبرى التي هزت المدينة بالكامل أخيراً"
    out = nd.analyze_dates(text)
    s, d = out
    assert d["stale_with_urgency"] is True
    assert s >= 0.3


def test_date_missing_timestamps():
    text = "مصادر مؤكدة تكشف سراً مرعباً هز الجميع بلا تاريخ ولا وقت ولا أي مرجع زمني محدد"
    out = nd.analyze_dates(text)
    s, d = out
    assert d["missing_date"] is True
    assert s >= 0.1


def test_date_arabic_month_parsed():
    text = "15 سبتمبر 2026 أعلنت البورصة عن نتائج الربع الثالث خلال مؤتمر صحفي"
    out = nd.analyze_dates(text)
    s, d = out
    assert "2026-09-15" in d["dates_found"]


# ---------------------------------------------------------------------------
# Deep signal: logic + agenda
# ---------------------------------------------------------------------------

def test_logic_absolutes_and_unfalsifiable():
    text = "الجميع يعلم دائماً أن كل الناس يعرفون الحقيقة المطلقة التي لا أحد يجرؤ على قولها للناس"
    out = nd.analyze_logic(text)
    s, d = out
    assert d["families"] >= 2
    assert s >= 0.3


def test_logic_balanced_text_scores_low():
    text = "ذكرت وزارة الصحة في بيانها رقم 45 بتاريخ 2026-09-30 أن الفحوصات أظهرت نتائج إيجابية"
    out = nd.analyze_logic(text)
    s, d = out
    assert s <= 0.15


def test_agenda_conspiracy_us_them():
    text = "مؤامرة كبرى يدبرها الأعداء وخونة بيعوا وطنهم، والإعلام الكاذب لا يريدك أن تعرف الحقيقة"
    out = nd.analyze_agenda(text)
    s, d = out
    assert d["conspiracy"]
    assert d["us_vs_them"]
    assert s >= 0.5


def test_agenda_financial_bait():
    text = "اربح الآن من منصة جديدة مضاعفة أموالك في أيام قليلة فقط بالضغط على الرابط المرفق"
    out = nd.analyze_agenda(text)
    s, d = out
    assert d["financial_bait"]
    assert s >= 0.2


def test_agenda_neutral_news_scores_zero():
    text = "قالت وزارة الخارجية في بيان رسمي أن المباحثات مستمرة وفريق العمل يعمل على المتابعة اليومية"
    out = nd.analyze_agenda(text)
    s, d = out
    assert s == 0.0


# ---------------------------------------------------------------------------
# Full pipeline with mocked OCR
# ---------------------------------------------------------------------------

def test_pipeline_end_to_end(monkeypatch):
    monkeypatch.setattr(nd, "extract_text", lambda img: MANIPULATIVE_AR)
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", False)

    from PIL import Image
    img = Image.new("RGB", (64, 48), (90, 90, 90))
    out = nd.analyze_news_screenshot(img, raw_bytes=b"")

    assert out["status"] == "success"
    assert out["ocr_available"] is True
    assert out["extracted_text"] == MANIPULATIVE_AR
    assert 0.0 <= out["misinformation_prob"] <= 1.0
    assert out["verdict"] in ("misleading", "suspicious", "likely_fine")
    assert any("text-manipulation" in a for a in out["arbiter_audit"])
    assert "weights" in out["thresholds"]


def test_pipeline_without_ocr_stays_neutral(monkeypatch):
    monkeypatch.setattr(nd, "extract_text", lambda img: "")
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", False)

    from PIL import Image
    img = Image.new("RGB", (64, 48), (90, 90, 90))
    out = nd.analyze_news_screenshot(img, raw_bytes=b"")

    assert out["ocr_available"] is False
    # no text + neutral forensics (conftest nukes detectors) -> low confidence
    assert out["misinformation_prob"] <= 0.65


def test_pipeline_includes_deep_analysis(monkeypatch):
    monkeypatch.setattr(nd, "extract_text", lambda img: MANIPULATIVE_AR)
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", False)

    from PIL import Image
    img = Image.new("RGB", (64, 48), (90, 90, 90))
    out = nd.analyze_news_screenshot(img, raw_bytes=b"")

    deep = out["deep_analysis"]
    assert set(deep.keys()) == {"source", "date", "logic", "agenda"}
    for k, v in deep.items():
        assert 0.0 <= v["score"] <= 1.0
        assert isinstance(v["detail"], dict)
    # audit lines must mention every deep voter
    audit = "\n".join(out["arbiter_audit"])
    for k in ("source-provenance", "date-analysis", "logic-coherence", "agenda-framing"):
        assert k in audit


def test_pipeline_short_text_skips_deep(monkeypatch):
    monkeypatch.setattr(nd, "extract_text", lambda img: "قصير")
    monkeypatch.setattr(nd.settings, "NEWS_FACT_CHECK_ENABLED", False)

    from PIL import Image
    img = Image.new("RGB", (64, 48), (90, 90, 90))
    out = nd.analyze_news_screenshot(img, raw_bytes=b"")
    assert out["deep_analysis"] == {}
