"""m2 — verdict engine tests: one test per rule in verdict_config.json.

The engine must never emit a label outside the fixed four, must generate all
explanation text from the rule that fired, and must obey the project
constants: k=2 floor, algorithmic checks capped at Investigate, authenticity
one-way, Possible Edits reserved.
"""

import copy

import pytest

from app.analysis_schema import AXIS_IDS, VERDICT_LABELS
from app.verdict_config import reload_rules
from app.verdict_engine import (
    CLEAR_BAND,
    FLAG_BAND,
    UNCERTAIN_BAND,
    classify_model_prob,
    evaluate,
)


def m(prob, mid="m1", status="ok"):
    return {"id": mid, "kind": "generation", "status": status, "prob_fake": prob}


def f(fid="ela", flag=True, status="ok", axes=None, vote_capable=True):
    entry = {"id": fid, "status": status, "flag": flag, "vote_capable": vote_capable}
    if axes is not None:
        entry["axes"] = axes
    return entry


ALL_CLEAR = [m(0.05, "a"), m(0.10, "b"), m(0.02, "c"), m(0.30, "d")]
TWO_FLAG = [m(0.95, "a"), m(0.88, "b"), m(0.05, "c"), m(0.10, "d")]
MIXED = [m(0.95, "a"), m(0.05, "b"), m(0.10, "c"), m(0.50, "d")]


# ---------------------------------------------------------------------------
# Bands reuse existing thresholds
# ---------------------------------------------------------------------------

def test_bands_use_existing_thresholds():
    assert classify_model_prob(0.71, "good") == FLAG_BAND
    assert classify_model_prob(0.70, "good") == CLEAR_BAND or classify_model_prob(0.70, "good") == UNCERTAIN_BAND
    assert classify_model_prob(0.44, "good") == CLEAR_BAND
    assert classify_model_prob(0.55, "good") == UNCERTAIN_BAND
    # quality-gated condemnation bar: poor specimens need > 0.80
    assert classify_model_prob(0.75, "poor") == UNCERTAIN_BAND
    assert classify_model_prob(0.85, "poor") == FLAG_BAND


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------

def test_two_model_flags_escalate():
    result = evaluate(TWO_FLAG)
    assert result["label"] == "AI Detected"
    assert result["rule_id"] == "escalation.k_of_n_agreement"
    assert result["counts"]["n_flag"] == 2


def test_model_flag_plus_forensic_flag_escalates():
    result = evaluate([m(0.95, "a"), m(0.05, "b")], forensics=[f()])
    assert result["label"] == "AI Detected"
    assert result["counts"]["signal_total"] == 2


def test_forensic_flags_alone_never_escalate():
    """Algorithmic checks are supporting signals: never above Investigate."""
    result = evaluate(ALL_CLEAR, forensics=[f("ela"), f("jpeg")])
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "default.ambiguous_evidence"


def test_info_only_checks_never_count_as_signals():
    """vote_capable=False (shadows/FFT/...) flags do not enter k-of-N."""
    result = evaluate(
        [m(0.95, "a"), m(0.50, "b")],  # one flag + one uncertain
        forensics=[f("shadows", vote_capable=False), f("fft", vote_capable=False)],
    )
    assert result["counts"]["forensic_flagged"] == 0
    assert result["counts"]["signal_total"] == 1  # not 3
    assert result["label"] == "Investigate"


def test_single_model_flag_insufficient_k():
    result = evaluate([m(0.95, "a"), m(0.50, "b")])
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "default.ambiguous_evidence"


def test_one_flag_two_clear_never_clears_nor_escalates():
    result = evaluate(MIXED)
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "default.ambiguous_evidence"
    assert result["disagreement"], "disagreement must be surfaced"


# ---------------------------------------------------------------------------
# Insufficient evidence
# ---------------------------------------------------------------------------

def test_fewer_than_two_working_models_is_investigate():
    result = evaluate([m(0.95, "a", status="error"), m(0.05, "b")])
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "escalation.insufficient_working_models"
    assert "أدلة غير كافية" in result["why_rule"]["ar"]


def test_all_models_error_is_investigate_even_with_forensics():
    result = evaluate(
        [m(None, "a", status="error"), m(None, "b", status="skipped")],
        forensics=[f("ela"), f("jpeg")],
    )
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "escalation.insufficient_working_models"


def test_skipped_and_error_models_excluded_from_counts():
    result = evaluate([m(0.05, "a"), m(0.95, "b", status="error"), m(0.05, "c", status="skipped")])
    assert result["counts"]["n_working"] == 1
    assert result["label"] == "Investigate"  # only 1 working -> insufficient


# ---------------------------------------------------------------------------
# Clearance rules
# ---------------------------------------------------------------------------

def test_clearance_needs_two_clear_and_zero_flags():
    result = evaluate(ALL_CLEAR)
    assert result["label"] == "No AI Detected"
    assert result["rule_id"] == "clearance.model_consensus"


def test_forensic_flag_blocks_clearance():
    result = evaluate(ALL_CLEAR, forensics=[f("ela")])
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "default.ambiguous_evidence"


def test_one_clear_alone_cannot_clear():
    result = evaluate([m(0.05, "a"), m(0.50, "b"), m(0.55, "c")])
    assert result["label"] == "Investigate"


# ---------------------------------------------------------------------------
# Authenticity is one-way
# ---------------------------------------------------------------------------

def test_authenticity_blocks_escalation():
    auth = {"present": True, "signal_ids": ["exif_camera_consistent"]}
    result = evaluate(TWO_FLAG, authenticity=auth)
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "escalation.blocked_by_authenticity"
    assert result["counts"]["authenticity_blocked"] is True


def test_authenticity_never_causes_escalation():
    auth = {"present": True, "signal_ids": ["exif_camera_consistent"]}
    result = evaluate(ALL_CLEAR, authenticity=auth)
    assert result["label"] == "No AI Detected"
    assert result["counts"]["authenticity_blocked"] is False


# ---------------------------------------------------------------------------
# Direct settle
# ---------------------------------------------------------------------------

def test_hash_settle_both_hashes_agree():
    settle = {
        "known_forgery_hash": {
            "phash_match": True, "dhash_match": True, "hamming": 2,
            "entry_label": "AI Detected", "entry_reference": "DB-42",
        }
    }
    result = evaluate([m(0.05, "a")], settle=settle)  # even one weak model
    assert result["label"] == "AI Detected"
    assert result["rule_id"] == "direct_settle.known_forgery_hash"


def test_hash_settle_requires_phash_and_dhash():
    settle = {
        "known_forgery_hash": {"phash_match": True, "dhash_match": False, "hamming": 2}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["rule_id"] != "direct_settle.known_forgery_hash"
    assert result["label"] == "No AI Detected"


def test_hash_settle_respects_hamming_cap():
    settle = {
        "known_forgery_hash": {"phash_match": True, "dhash_match": True, "hamming": 99}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["rule_id"] != "direct_settle.known_forgery_hash"


def test_hash_settle_unknown_distance_does_not_settle():
    settle = {"known_forgery_hash": {"phash_match": True, "dhash_match": True}}
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["rule_id"] != "direct_settle.known_forgery_hash"


def test_hash_settle_entry_without_class_is_investigate():
    settle = {
        "known_forgery_hash": {
            "phash_match": True, "dhash_match": True, "hamming": 1,
        }
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "direct_settle.known_forgery_hash"


def test_c2pa_valid_signature_generation_settles_even_with_cleared_models():
    settle = {
        "c2pa": {"hit": True, "declares_generation": True,
                 "crypto_valid": True, "trusted": False}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "AI Detected"
    assert result["rule_id"] == "direct_settle.c2pa_generation"
    # honesty: text must not claim trust when trust was not verified
    assert "not verified" in result["why_rule"]["en"]


def test_c2pa_trusted_signer_wording_when_verified():
    settle = {
        "c2pa": {"hit": True, "declares_generation": True,
                 "crypto_valid": True, "trusted": True}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "AI Detected"
    assert "verified against the configured trust list" in result["why_rule"]["en"]


def test_c2pa_invalid_signature_does_not_settle():
    settle = {
        "c2pa": {"hit": True, "declares_generation": True,
                 "crypto_valid": False, "trusted": False}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "No AI Detected"
    assert result["rule_id"] != "direct_settle.c2pa_generation"


def test_c2pa_hit_without_generation_claim_falls_through():
    settle = {
        "c2pa": {"hit": True, "declares_generation": False,
                 "crypto_valid": True, "trusted": True}
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "No AI Detected"


def test_fact_check_match_settles():
    settle = {"fact_check": {"matched": True, "title": "Deepfake photo of X debunked"}}
    result = evaluate([m(0.05, "a"), m(0.50, "b")], settle=settle)
    assert result["label"] == "Investigate"
    assert result["rule_id"] == "direct_settle.fact_check_article_match"


def test_fact_check_match_with_declared_label_uses_it():
    settle = {"fact_check": {"matched": True, "label": "AI Detected"}}
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "AI Detected"


def test_settle_wins_over_insufficient_models():
    settle = {"c2pa": {"hit": True, "declares_generation": True,
                       "crypto_valid": True, "trusted": False}}
    result = evaluate([m(0.05, "a", status="error")], settle=settle)
    assert result["label"] == "AI Detected"
    assert result["rule_id"] == "direct_settle.c2pa_generation"


# ---------------------------------------------------------------------------
# Possible Edits reservation (constant #5)
# ---------------------------------------------------------------------------

def test_possible_edits_never_emitted_without_editing_model():
    settle = {
        "known_forgery_hash": {
            "phash_match": True, "dhash_match": True, "hamming": 0,
            "entry_label": "Possible Edits",
        }
    }
    result = evaluate(ALL_CLEAR, settle=settle)
    assert result["label"] == "Investigate"


def test_possible_edits_not_in_any_generated_label():
    scenarios = [
        evaluate(ALL_CLEAR),
        evaluate(TWO_FLAG),
        evaluate(MIXED),
        evaluate([m(0.05, "a")]),
        evaluate(ALL_CLEAR, authenticity={"present": True, "signal_ids": ["x"]}),
    ]
    for result in scenarios:
        assert result["label"] in VERDICT_LABELS
        assert result["label"] != "Possible Edits"


# ---------------------------------------------------------------------------
# Generated text + axes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "models_kw",
    [
        {"models": ALL_CLEAR},
        {"models": TWO_FLAG},
        {"models": MIXED},
        {"models": [m(0.05, "a")]},
    ],
)
def test_all_explanations_generated_bilingually(models_kw):
    result = evaluate(**models_kw)
    for key in ("why_rule", "reasoning", "human_line"):
        assert result[key]["en"].strip(), f"{key} en empty"
        assert result[key]["ar"].strip(), f"{key} ar empty"
    assert result["rule_id"]


def test_axes_are_the_three_fixed_ids():
    result = evaluate(ALL_CLEAR)
    assert [a["id"] for a in result["axes"]] == list(AXIS_IDS)


def test_ai_generation_axis_skipped_when_no_model_worked():
    result = evaluate([m(None, "a", status="error")])
    axis = next(a for a in result["axes"] if a["id"] == "ai_generation")
    assert axis["state"] == "skipped"
    assert axis["reason"]["en"]


def test_editing_axis_not_applicable_without_editing_checks():
    result = evaluate(ALL_CLEAR)
    axis = next(a for a in result["axes"] if a["id"] == "editing_check")
    assert axis["state"] == "not_applicable"
    assert axis["reason"]["ar"]


def test_editing_axis_ok_when_algorithmic_checks_present():
    result = evaluate(ALL_CLEAR, forensics=[f("ela", axes=["editing_check"])])
    axis = next(a for a in result["axes"] if a["id"] == "editing_check")
    assert axis["state"] == "ok"
    assert "Investigate" in axis["summary"]["en"]  # cap stated honestly


def test_source_axis_not_applicable_when_not_run():
    result = evaluate(ALL_CLEAR)
    axis = next(a for a in result["axes"] if a["id"] == "source_check")
    assert axis["state"] == "not_applicable"


def test_source_axis_reports_real_facts():
    source = {"exif_present": True, "camera": "Canon EOS 5D", "datetime": "2024-01-02", "gps": False}
    result = evaluate(ALL_CLEAR, source=source)
    axis = next(a for a in result["axes"] if a["id"] == "source_check")
    assert axis["state"] == "ok"
    assert "Canon EOS 5D" in axis["summary"]["en"]


def test_engine_outputs_structured_counts_and_bands():
    result = evaluate(MIXED, fused_prob=0.42)
    assert result["fused_prob"] == 0.42
    assert result["counts"]["n_working"] == 4
    assert {b["call"] for b in result["models_banded"]} == {FLAG_BAND, CLEAR_BAND, UNCERTAIN_BAND}


def test_engine_uses_provided_config_override():
    cfg = copy.deepcopy(reload_rules())
    cfg["clearance"]["min_clearing_models"] = 4
    # 3 clear + 1 uncertain: default config would not clear either, make it 4 to prove override
    result = evaluate([m(0.05, "a"), m(0.10, "b"), m(0.02, "c"), m(0.50, "d")], config=cfg)
    assert result["label"] == "Investigate"
    result_default = evaluate([m(0.05, "a"), m(0.10, "b"), m(0.02, "c"), m(0.50, "d")])
    # default config clears with 3 clearing detectors (min is 2)
    assert result_default["label"] == "No AI Detected"
    assert result_default["rule_id"] == "clearance.model_consensus"
