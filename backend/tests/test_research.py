"""m5 research sections: states, honesty rules and link allow-listing."""

from urllib.parse import urlparse

from app.analysis_schema import new_analysis, validate_analysis
from app.services.research import (
    ALLOWED_HOSTS,
    apply_research,
    dated_query,
    fact_check_links,
    location_links,
    reverse_search_engines,
    searchable_query,
    web_search_links,
)

M5_SECTIONS = (
    "reverse_search",
    "links_on_web",
    "fact_check_monitor",
    "location",
    "what_to_do_next",
    "further_investigation",
)
EXTERNAL_CARDS = ("web_presence", "fact_check", "links", "location")


def _record(name: str = "ronaldo-fan-photo.jpg") -> dict:
    return new_analysis(name=name)


def _apply(record: dict, **kwargs) -> dict:
    kwargs.setdefault("exif_data", {})
    apply_research(record, **kwargs)
    return record


def _links_of(section: dict) -> list:
    data = section.get("data") or {}
    return list(data.get("links") or data.get("engines") or [])


# ---------------------------------------------------------------------------


def test_every_m5_section_resolves_to_a_final_state():
    record = _apply(_record())
    for sid in M5_SECTIONS:
        state = record["sections"][sid]["state"]
        assert state in ("ok", "skipped"), f"{sid} stuck in {state}"
        if state == "skipped":
            assert record["sections"][sid].get("reason"), f"{sid} skipped w/o reason"
    assert record["external"]["state"] in ("ok", "skipped")
    for sub in EXTERNAL_CARDS:
        assert record["external"][sub]["state"] in ("ok", "skipped", "error")


def test_record_still_validates_after_research():
    record = _apply(_record())
    assert validate_analysis(record) == []


def test_no_card_left_in_loading_state():
    record = _apply(_record())
    assert record["sections"]["reverse_search"]["state"] != "loading"
    for sub in EXTERNAL_CARDS:
        assert record["external"][sub]["state"] != "loading"


# ---------------------------------------------------------------------------


def test_generic_camera_name_yields_skipped_not_a_noise_query():
    record = _apply(_record("IMG_1234.jpg"))
    section = record["sections"]["links_on_web"]
    assert section["state"] == "skipped"
    assert section.get("reason")
    data = section.get("data") or {}
    assert "links" not in data and "query" not in data
    assert data["reason_en"] and data["reason_ar"]


def test_every_skipped_m5_section_explains_itself_in_both_languages():
    record = _apply(_record("IMG_1234.jpg"))
    for sid in M5_SECTIONS:
        section = record["sections"][sid]
        if section["state"] != "skipped":
            continue
        data = section.get("data") or {}
        assert data.get("reason_en"), sid
        assert data.get("reason_ar"), sid


def test_screenshot_name_yields_skipped():
    record = _apply(_record("Screenshot_20240101_120000.png"))
    assert record["sections"]["links_on_web"]["state"] == "skipped"


def test_meaningful_name_produces_a_query_and_links():
    record = _apply(_record())
    section = record["sections"]["links_on_web"]
    assert section["state"] == "ok"
    assert section["data"]["query"] == "ronaldo fan"
    assert len(section["data"]["links"]) >= 4


def test_fact_check_section_is_a_search_not_a_verdict():
    record = _apply(_record())
    section = record["sections"]["fact_check_monitor"]
    assert section["state"] == "ok"
    note = section["data"]["note_en"].lower()
    assert "no fact-check api" in note
    for link in section["data"]["links"]:
        assert set(link) >= {"id", "label", "url"}


# ---------------------------------------------------------------------------


def test_reverse_search_always_offers_engines_without_uploading():
    record = _apply(_record("IMG_1234.jpg"))
    section = record["sections"]["reverse_search"]
    assert section["state"] == "ok"
    engines = section["data"]["engines"]
    assert {e["id"] for e in engines} >= {"google_lens", "tineye"}
    assert "not uploaded" in section["data"]["note_en"].lower()


def test_location_requires_real_gps():
    record = _apply(_record("IMG_1234.jpg"))
    section = record["sections"]["location"]
    assert section["state"] == "skipped"
    assert "GPS" in section["reason"] or "EXIF" in section["reason"]


def test_location_links_built_from_decoded_coordinates():
    record = _record("IMG_1234.jpg")
    apply_research(
        record,
        exif_data={
            "exif_present": True,
            "exif": {},
            "gps": {"lat": 24.7136, "lon": 46.6753},
            "generator_signatures": [],
        },
    )
    section = record["sections"]["location"]
    assert section["state"] == "ok"
    assert section["data"]["lat"] == 24.7136
    urls = [l["url"] for l in section["data"]["links"]]
    assert any("24.7136" in u and "46.6753" in u for u in urls)


# ---------------------------------------------------------------------------


def test_guidance_is_bilingual_and_rule_tracked():
    record = _apply(_record())
    todo = record["sections"]["what_to_do_next"]["data"]
    assert todo["steps"], "what_to_do_next produced nothing"
    assert todo["rule"]
    for step in todo["steps"]:
        assert step["en"].strip() and step["ar"].strip(), step["id"]
    further = record["sections"]["further_investigation"]["data"]
    assert len(further["steps"]) >= 3
    for step in further["steps"]:
        assert step["en"].strip() and step["ar"].strip()


def test_record_signals_add_specific_guidance():
    record = _record("IMG_1234.jpg")
    apply_research(
        record,
        exif_data={
            "exif_present": True,
            "exif": {"make": "Canon", "model": "EOS R5"},
            "gps": None,
            "generator_signatures": ["Midjourney"],
        },
    )
    ids = [s["id"] for s in record["sections"]["what_to_do_next"]["data"]["steps"]]
    assert "generator_signature" in ids
    assert "camera_exif" in ids


def test_missing_exif_is_reported_as_a_fact():
    record = _record("IMG_1234.jpg")
    apply_research(record, exif_data={"exif_present": False, "exif": {}})
    ids = [s["id"] for s in record["sections"]["what_to_do_next"]["data"]["steps"]]
    assert "no_exif" in ids


# ---------------------------------------------------------------------------


def test_all_emitted_links_use_verified_hosts_and_https():
    record = _apply(_record())
    emitted = []
    for sid in ("links_on_web", "fact_check_monitor", "location",
                "reverse_search", "further_investigation"):
        emitted.extend(_links_of(record["sections"][sid]))
    assert emitted, "no links emitted at all"
    for link in emitted:
        parsed = urlparse(link["url"])
        assert parsed.scheme == "https", link
        assert parsed.netloc in ALLOWED_HOSTS, link


def test_fact_check_and_web_links_carry_the_query():
    q = "ronaldo fan"
    for link in fact_check_links(q):
        assert "ronaldo+fan" in link["url"] or "ronaldo%20fan" in link["url"]
    for link in web_search_links(q):
        assert "ronaldo+fan" in link["url"] or "ronaldo%20fan" in link["url"]
    for engine in reverse_search_engines():
        assert urlparse(engine["url"]).netloc in ALLOWED_HOSTS


def test_location_links_hosts_are_allowlisted():
    for link in location_links(24.7136, 46.6753):
        assert urlparse(link["url"]).netloc in ALLOWED_HOSTS


# ---------------------------------------------------------------------------


def test_dated_query_absent_without_a_real_capture_date():
    assert dated_query("ronaldo fan", None) is None
    assert dated_query("ronaldo fan", "not-a-date") is None


def test_dated_query_uses_the_exif_date_window():
    out = dated_query("ronaldo fan", "2024:03:10 12:00:00")
    assert out is not None
    assert "since:2024-03-03" in out["url"] or "since%3A2024-03-03" in out["url"]
    assert urlparse(out["url"]).netloc in ALLOWED_HOSTS


def test_external_rollup_reports_skip_when_nothing_searchable():
    record = _apply(_record("IMG_1234.jpg"))
    # reverse search still works, so the roll-up stays honest about it
    assert record["external"]["state"] == "ok"
    assert record["external"]["web_presence"]["state"] == "skipped"
    assert record["external"]["web_presence"].get("reason")
