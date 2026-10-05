"""Verdict-engine rules loader.

Rules live in ``backend/verdict_config.json`` — never inline in engine code —
so they can be reviewed and versioned without touching logic. The file holds
ENGINE rules only:

* escalation policy (fixed minimum k=2 agreeing signals; fewer than two
  working generation detectors forces "Investigate" / insufficient evidence),
* one-way authenticity signal (blocks escalation toward AI, never causes it),
* direct-settle conditions (known-forgery hash with pHash+dHash agreement,
  trusted C2PA declaring generation, matching fact-check article),
* the rule that algorithmic checks alone can never exceed "Investigate" and
  that "Possible Edits" stays reserved until a real editing model is
  registered.

Model weights and model decision thresholds are NOT part of this file.
Proposals to change them go to ``verdict_config.proposed.json`` (written by
``scripts/calibrate.py``) and are applied only after explicit operator
approval.
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict

CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "verdict_config.json")
)
PROPOSED_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "verdict_config.proposed.json")
)


class VerdictConfigError(ValueError):
    """Raised when the rules file is missing a key or violates an invariant."""


_ALLOWED_VERDICTS = ("AI Detected", "Possible Edits", "Investigate", "No AI Detected")
_SECTION_STATES = ("loading", "ok", "not_applicable", "skipped", "error")


def validate_rules(rules: Dict[str, Any]) -> None:
    """Enforce structure + project invariants. Raises VerdictConfigError."""
    if not isinstance(rules, dict):
        raise VerdictConfigError("verdict config must be a JSON object")

    for key in (
        "schema_version",
        "escalation",
        "clearance",
        "one_way_signals",
        "direct_settle",
        "verdict_labels",
        "axes",
        "calibration",
        "feedback",
    ):
        if key not in rules:
            raise VerdictConfigError(f"missing required key: {key}")

    esc = rules["escalation"]
    if not isinstance(esc, dict):
        raise VerdictConfigError("escalation must be an object")

    min_k = esc.get("min_agreeing_signals")
    if not isinstance(min_k, int) or isinstance(min_k, bool) or min_k < 2:
        # Project constant #5: k=2 is a FIXED floor, whatever the model count.
        raise VerdictConfigError(
            "escalation.min_agreeing_signals must be an integer >= 2 (fixed k floor)"
        )

    min_models = esc.get("min_working_generation_models")
    if not isinstance(min_models, int) or isinstance(min_models, bool) or min_models < 2:
        raise VerdictConfigError(
            "escalation.min_working_generation_models must be an integer >= 2 "
            "(fewer working models -> Investigate, insufficient evidence)"
        )

    if esc.get("single_model_decides") is not False:
        raise VerdictConfigError(
            "escalation.single_model_decides must be false "
            "(no single model may change a verdict alone)"
        )

    if esc.get("algorithmic_checks_max_verdict") != "Investigate":
        raise VerdictConfigError(
            "escalation.algorithmic_checks_max_verdict must be 'Investigate' "
            "(algorithmic checks are supporting signals only)"
        )

    if esc.get("possible_edits_requires_editing_model") is not True:
        raise VerdictConfigError(
            "escalation.possible_edits_requires_editing_model must be true "
            "('Possible Edits' stays reserved until a real editing model is registered)"
        )

    labels = rules["verdict_labels"]
    if list(labels) != list(_ALLOWED_VERDICTS):
        raise VerdictConfigError(
            f"verdict_labels must equal {list(_ALLOWED_VERDICTS)} in order"
        )

    axes = rules["axes"]
    if list(axes) != ["ai_generation", "editing_check", "source_check"]:
        raise VerdictConfigError(
            "axes must be [ai_generation, editing_check, source_check]"
        )

    clearance = rules["clearance"]
    if not isinstance(clearance, dict):
        raise VerdictConfigError("clearance must be an object")
    min_clear = clearance.get("min_clearing_models")
    if not isinstance(min_clear, int) or isinstance(min_clear, bool) or min_clear < 1:
        raise VerdictConfigError(
            "clearance.min_clearing_models must be an integer >= 1"
        )
    for key in ("max_model_flags_allowed", "max_forensic_flags_allowed"):
        value = clearance.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise VerdictConfigError(
                f"clearance.{key} must be a non-negative integer"
            )

    one_way = rules["one_way_signals"]
    if not isinstance(one_way, dict) or one_way.get("authenticity_blocks_escalation") is not True:
        raise VerdictConfigError(
            "one_way_signals.authenticity_blocks_escalation must be true "
            "(authenticity blocks escalation toward AI; it never causes one)"
        )

    settle = rules["direct_settle"]
    if not isinstance(settle, dict):
        raise VerdictConfigError("direct_settle must be an object")
    forgery = settle.get("known_forgery_hash", {})
    requires = forgery.get("requires_all", [])
    if set(requires) != {"phash", "dhash"}:
        raise VerdictConfigError(
            "direct_settle.known_forgery_hash.requires_all must be exactly "
            "['phash', 'dhash'] (hash settle needs BOTH hashes agreeing)"
        )
    max_h = forgery.get("max_hamming")
    if not isinstance(max_h, int) or isinstance(max_h, bool) or max_h < 0:
        raise VerdictConfigError(
            "direct_settle.known_forgery_hash.max_hamming must be a non-negative integer"
        )

    cal = rules["calibration"]
    if not isinstance(cal, dict) or cal.get("auto_apply") is not False:
        raise VerdictConfigError(
            "calibration.auto_apply must be false (proposed thresholds need operator approval)"
        )
    if cal.get("proposed_output") != "verdict_config.proposed.json":
        raise VerdictConfigError(
            "calibration.proposed_output must be 'verdict_config.proposed.json'"
        )

    fb = rules["feedback"]
    if not isinstance(fb, dict) or fb.get("auto_tune_thresholds") is not False:
        raise VerdictConfigError(
            "feedback.auto_tune_thresholds must be false "
            "(user ratings go to a review queue, never auto-applied)"
        )


@lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    """Read + validate the rules file (cached). Raises on any violation so a
    bad config fails loudly at startup instead of silently changing verdicts."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    validate_rules(rules)
    return rules


def reload_rules() -> Dict[str, Any]:
    """Drop the cache and re-read (used by tests and admin tooling)."""
    load_rules.cache_clear()
    return load_rules()


__all__ = [
    "CONFIG_PATH",
    "PROPOSED_PATH",
    "VerdictConfigError",
    "load_rules",
    "reload_rules",
    "validate_rules",
    "_SECTION_STATES",
]
