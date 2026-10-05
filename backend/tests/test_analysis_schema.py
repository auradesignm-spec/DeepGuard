"""m1 — unified analysis schema tests (state discipline + contract)."""

import copy

import pytest

from app.analysis_schema import (
    AXIS_IDS,
    SCHEMA_VERSION,
    SECTION_IDS,
    SECTION_STATES,
    VERDICT_LABELS,
    is_valid,
    new_analysis,
    new_section,
    set_section,
    validate_analysis,
)


@pytest.fixture()
def record():
    return new_analysis(name="specimen.png", sha256="ab" * 32, size_bytes=1234)


def test_fresh_record_is_valid_and_fully_loading(record):
    assert validate_analysis(record) == []
    assert record["schema_version"] == SCHEMA_VERSION
    assert record["verdict"]["state"] == "loading"
    assert [a["id"] for a in record["verdict"]["axes"]] == list(AXIS_IDS)
    assert all(s["state"] == "loading" for s in record["sections"].values())
    assert set(record["sections"]) == set(SECTION_IDS)


def test_new_section_rejects_unknown_state():
    with pytest.raises(ValueError):
        new_section("probably_fine")


def test_set_section_unknown_key_raises(record):
    with pytest.raises(KeyError):
        set_section(record, "not_a_section", "ok")


def test_skipped_requires_reason(record):
    set_section(record, "location", "skipped")
    errors = validate_analysis(record)
    assert any("location" in e and "reason" in e for e in errors)

    set_section(record, "location", "skipped", reason="Image is AI-generated — no real-world location.")
    assert validate_analysis(record) == []


def test_error_requires_message(record):
    set_section(record, "c2pa", "error")
    errors = validate_analysis(record)
    assert any("c2pa" in e for e in errors)

    set_section(record, "c2pa", "error", error="c2pa-python wheel unavailable for Python 3.14")
    assert validate_analysis(record) == []


def test_not_applicable_is_allowed_without_reason(record):
    set_section(record, "location", "not_applicable")
    assert validate_analysis(record) == []


def test_verdict_ok_requires_label_and_generated_texts(record):
    record["verdict"]["state"] = "ok"
    errors = validate_analysis(record)
    assert any("label" in e for e in errors)
    assert any("why_rule" in e for e in errors)

    record["verdict"]["label"] = "No AI Detected"
    errors = validate_analysis(record)
    assert any("why_rule" in e for e in errors)

    record["verdict"]["why_rule"] = "rule: k-of-N satisfied"
    record["verdict"]["reasoning"] = "generated reasoning"
    assert validate_analysis(record) == []


def test_verdict_label_must_be_from_fixed_set(record):
    record["verdict"].update(
        state="ok", label="Definitely Fake", why_rule="r", reasoning="x"
    )
    errors = validate_analysis(record)
    assert any("verdict.label" in e for e in errors)
    assert "Definitely Fake" not in VERDICT_LABELS


def test_model_entries_contract(record):
    record["models"] = [{"id": "sdxl", "kind": "generation", "status": "ok"}]
    errors = validate_analysis(record)
    assert any("prob_fake" in e for e in errors)

    record["models"] = [
        {"id": "sdxl", "kind": "generation", "status": "ok", "prob_fake": 0.12},
        {"id": "commfor", "kind": "generation", "status": "error", "error": "OOM"},
        {"id": "face_v2", "kind": "generation", "status": "skipped", "reason": "no face"},
    ]
    assert validate_analysis(record) == []


def test_model_prob_out_of_range_rejected(record):
    record["models"] = [
        {"id": "sdxl", "kind": "generation", "status": "ok", "prob_fake": 1.7}
    ]
    errors = validate_analysis(record)
    assert any("prob_fake" in e for e in errors)


def test_missing_and_unknown_sections_detected(record):
    removed = copy.deepcopy(record)
    del removed["sections"]["c2pa"]
    assert any("missing section: c2pa" in e for e in validate_analysis(removed))

    extra = copy.deepcopy(record)
    extra["sections"]["mystery"] = {"state": "ok"}
    assert any("unknown section: mystery" in e for e in validate_analysis(extra))


def test_forensics_checks_use_status_key(record):
    record["forensics"] = {
        "state": "ok",
        "checks": [
            {"id": "exif", "status": "ok"},
            {"id": "watermark", "status": "skipped", "reason": "no templates"},
        ],
    }
    assert validate_analysis(record) == []

    record["forensics"]["checks"][1] = {"id": "watermark", "status": "skipped"}
    errors = validate_analysis(record)
    assert any("watermark" in e and "reason" in e for e in errors)

    record["forensics"]["checks"][1] = {"id": "qr", "status": "error"}
    errors = validate_analysis(record)
    assert any("qr" in e and "error message" in e for e in errors)


def test_wrong_schema_version_rejected(record):
    record["schema_version"] = "0.9"
    errors = validate_analysis(record)
    assert any("schema_version" in e for e in errors)


def test_axes_order_is_enforced(record):
    record["verdict"]["axes"] = list(reversed(record["verdict"]["axes"]))
    errors = validate_analysis(record)
    assert any("axes" in e for e in errors)


def test_is_valid_helper(record):
    assert is_valid(record) is True
    record["schema_version"] = "nope"
    assert is_valid(record) is False


def test_all_five_states_renderable(record):
    for i, state in enumerate(SECTION_STATES):
        sid = SECTION_IDS[i]
        if state == "skipped":
            set_section(record, sid, state, reason="why")
        elif state == "error":
            set_section(record, sid, state, error="what happened")
        else:
            set_section(record, sid, state)
    assert validate_analysis(record) == []
