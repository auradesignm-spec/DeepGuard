"""m1 — verdict rules config tests (the invariants, not the values)."""

import copy
import json

import pytest

from app.verdict_config import (
    CONFIG_PATH,
    PROPOSED_PATH,
    VerdictConfigError,
    load_rules,
    reload_rules,
    validate_rules,
)


@pytest.fixture()
def rules():
    return copy.deepcopy(reload_rules())


def test_config_file_exists_and_parses():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict)


def test_load_rules_validates_clean_file():
    rules = load_rules()
    assert rules["escalation"]["min_agreeing_signals"] == 2


def test_min_k_is_fixed_floor_of_two(rules):
    rules["escalation"]["min_agreeing_signals"] = 1
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_min_k_rejects_non_integer(rules):
    rules["escalation"]["min_agreeing_signals"] = 2.5
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_min_working_models_floor(rules):
    rules["escalation"]["min_working_generation_models"] = 1
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_single_model_can_never_decide(rules):
    rules["escalation"]["single_model_decides"] = True
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_algorithmic_checks_capped_at_investigate(rules):
    rules["escalation"]["algorithmic_checks_max_verdict"] = "AI Detected"
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_possible_edits_requires_registered_editing_model(rules):
    rules["escalation"]["possible_edits_requires_editing_model"] = False
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_authenticity_is_one_way(rules):
    rules["one_way_signals"]["authenticity_blocks_escalation"] = False
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_hash_settle_requires_both_hashes(rules):
    rules["direct_settle"]["known_forgery_hash"]["requires_all"] = ["phash"]
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_hash_settle_hamming_must_be_configurable_nonneg_int(rules):
    rules["direct_settle"]["known_forgery_hash"]["max_hamming"] = -1
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)
    rules["direct_settle"]["known_forgery_hash"]["max_hamming"] = 6
    validate_rules(rules)  # configurable upward is fine


def test_calibration_never_auto_applies(rules):
    rules["calibration"]["auto_apply"] = True
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_calibration_writes_to_proposed_only(rules):
    assert rules["calibration"]["proposed_output"] == "verdict_config.proposed.json"
    assert PROPOSED_PATH.endswith("verdict_config.proposed.json")


def test_feedback_never_auto_tunes(rules):
    rules["feedback"]["auto_tune_thresholds"] = True
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_missing_key_rejected(rules):
    del rules["escalation"]
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)


def test_verdict_labels_are_the_fixed_four(rules):
    assert rules["verdict_labels"] == [
        "AI Detected",
        "Possible Edits",
        "Investigate",
        "No AI Detected",
    ]
    rules["verdict_labels"] = ["Fake", "Real"]
    with pytest.raises(VerdictConfigError):
        validate_rules(rules)
