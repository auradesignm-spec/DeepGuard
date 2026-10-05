"""m3 — C2PA check: signer/generator/actions data + honest trust states."""

import os

from app.services import c2pa_check as C

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_WITH_C2PA = os.path.join(_HERE, "assets", "chatgpt_edited_c2pa.png")
ASSET_WITHOUT_C2PA = os.path.abspath(os.path.join(_HERE, "..", "..", "news_test.png"))


def test_manifest_found_with_generator_and_actions():
    payload, trust_note, error = C.read_c2pa(ASSET_WITH_C2PA)
    assert error is None
    assert payload is not None
    assert payload["found"] is True
    assert payload["generator"] == "OpenAI Media Service API"
    assert payload["signature"]["common_name"] == "OpenAI Media Service"
    assert payload["signature"]["alg"] == "Es256"
    assert payload["actions"], "actions list must expose the edits"
    assert payload["crypto_valid"] is True          # claim signature validated
    assert payload["declares_generation"] is True   # trainedAlgorithmicMedia
    assert payload["trust_note"] is not None        # trust-list status is stated


def test_trust_is_reported_separately_from_crypto_validity():
    payload, _note, _err = C.read_c2pa(ASSET_WITH_C2PA)
    # No trust anchors configured in tests -> crypto can be valid while the
    # signer is explicitly NOT trusted (never shown as trusted).
    assert payload["crypto_valid"] is True
    assert payload["trusted"] is False
    assert any(f.get("code") == "signingCredential.untrusted" for f in payload["failures"])


def test_check_card_ok_with_settle_input():
    card = C.check_c2pa(b"\x89PNG", path=ASSET_WITH_C2PA)
    assert card["status"] == "ok"
    assert card["id"] == "c2pa"
    assert card["vote_capable"] is False  # decisive path = engine direct-settle
    settle = card["settle"]
    assert settle["hit"] is True
    assert settle["declares_generation"] is True
    assert settle["crypto_valid"] is True
    assert settle["trusted"] is False       # trust list not configured here
    assert "OpenAI" in settle["detail"]
    assert card["why_en"] and card["why_ar"]


def test_absence_is_not_applicable_with_honest_reason():
    card = C.check_c2pa(b"...", path=ASSET_WITHOUT_C2PA)
    assert card["status"] == "not_applicable"
    assert "absence does not prove" in card["reason"]


def test_raw_only_analysis_skips_with_reason():
    card = C.check_c2pa(b"\x89PNG...", path=None)
    assert card["status"] == "skipped"
    assert "path" in card["reason"]


def test_missing_wheel_is_skipped_not_faked(monkeypatch):
    monkeypatch.setattr(
        C, "_import_c2pa", lambda: (None, "No module named 'c2pa' (no cp314 wheel)")
    )
    card = C.check_c2pa(b"x", path=ASSET_WITH_C2PA)
    assert card["status"] == "skipped"
    assert "unavailable" in card["reason"]
    assert "cp314" in card["reason"]


def test_bogus_trust_path_degrades_honestly(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "C2PA_TRUST_ANCHORS_PATH", "C:/does/not/exist/anchors.pem")
    payload, trust_note, error = C.read_c2pa(ASSET_WITH_C2PA)
    assert error is None
    assert payload is not None
    assert "not found" in trust_note
    assert payload["trusted"] is False
