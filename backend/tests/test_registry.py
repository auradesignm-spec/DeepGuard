"""m1 — detector registry tests.

The critical test here is ``test_weights_pinned_to_arbiter``: it recomputes
the weighted geometric fusion from the registry's *display* weights and
compares it against the real ``_arbiter_fuse`` output. If detector.py's
weights ever drift from the registry, the UI could print a number the engine
does not use — this test makes that impossible.
"""

import math

import pytest

import app.services.detector as det
from app.detectors.registry import (
    ARBITER_CONDITIONAL_WEIGHTS,
    DETECTORS,
    KINDS,
    all_detectors,
    editing_detectors,
    generation_detectors,
    spec_by_id,
    working_generation_count,
)


def test_exactly_four_generation_detectors_registered():
    gens = generation_detectors()
    assert [d.id for d in gens] == ["face_v2", "sdxl", "commfor", "dima806"]
    assert all(d.kind == "generation" for d in gens)


def test_editing_slot_reserved_and_empty():
    """Possible Edits stays reserved: no editing model is registered."""
    assert editing_detectors() == []
    assert all(d.kind in KINDS for d in DETECTORS)


def test_specs_are_well_formed():
    for spec in all_detectors():
        assert spec.id and spec.label_en and spec.label_ar
        assert spec.kind in KINDS
        assert spec.role in ("primary", "supporting")
        assert spec.weight > 0
        assert spec.source and spec.framework and spec.input_spec and spec.output_spec


def test_spec_by_id_lookup():
    assert spec_by_id("commfor").weight == 1.25
    assert spec_by_id("does_not_exist") is None


def test_availability_is_boolean_and_false_under_test_isolation():
    for spec in DETECTORS:
        assert isinstance(spec.is_available(), bool)
        # conftest blocks model loading at source -> nothing is loaded.
        assert spec.is_available() is False
    assert working_generation_count() == 0


def _fuse_expected(votes, weights):
    total_w = sum(weights[k] for k in votes)
    return math.exp(
        sum(weights[k] * math.log(max(v, det.FAKE_PROB_FLOOR)) for k, v in votes.items())
        / total_w
    )


def test_weights_pinned_to_arbiter():
    """Registry display weights must equal the weights _arbiter_fuse uses."""
    votes = {"commfor": 0.9, "face_v2": 0.2, "sdxl": 0.1, "dima806": 0.4}
    base = {d.id: d.weight for d in DETECTORS}

    # good quality + face present -> pure base weights, untouched.
    fused, _ = det._arbiter_fuse(dict(votes), "good", True)
    assert fused == pytest.approx(_fuse_expected(votes, base), abs=1e-12)


def test_conditional_weights_pinned_to_arbiter():
    votes = {"commfor": 0.9, "face_v2": 0.2, "sdxl": 0.1, "dima806": 0.4}
    base = {d.id: d.weight for d in DETECTORS}

    # face absent -> face_v2 weight drops to the conditional value.
    w = dict(base)
    w["face_v2"] = ARBITER_CONDITIONAL_WEIGHTS["face_v2_face_absent"]
    fused, _ = det._arbiter_fuse(dict(votes), "good", False)
    assert fused == pytest.approx(_fuse_expected(votes, w), abs=1e-12)

    # poor quality -> face vote capped.
    w = dict(base)
    w["face_v2"] = ARBITER_CONDITIONAL_WEIGHTS["face_v2_quality_poor_cap"]
    fused, _ = det._arbiter_fuse(dict(votes), "poor", True)
    assert fused == pytest.approx(_fuse_expected(votes, w), abs=1e-12)

    # degraded quality -> face vote scaled.
    w = dict(base)
    w["face_v2"] = base["face_v2"] * ARBITER_CONDITIONAL_WEIGHTS["face_v2_quality_degraded_factor"]
    fused, _ = det._arbiter_fuse(dict(votes), "degraded", True)
    assert fused == pytest.approx(_fuse_expected(votes, w), abs=1e-12)
