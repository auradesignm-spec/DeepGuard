"""Outlier-badge majority rule (display-only, consumed by the scores UI).

Rule under test: the majority call is decided among DECISIVE calls only
(flag/clear). An "uncertain" model neither votes for the majority nor can be
branded an outlier. A tie between decisive camps (or a single decisive camp)
yields no majority, so nobody gets the badge. This never touches the verdict
label, the counts, or any threshold.
"""

from app.verdict_engine import CLEAR_BAND, FLAG_BAND, UNCERTAIN_BAND, evaluate


def _model(pid: str, prob: float):
    return {"id": pid, "kind": "generation", "status": "ok", "prob_fake": prob}


def _evaluate(models):
    return evaluate(
        models,
        forensics=[],
        authenticity={"present": False, "signal_ids": []},
        settle={},
        source={},
        quality_tier="good",
        fused_prob=0.5,
    )


def test_uncertain_model_neither_votes_nor_gets_badge():
    # 2 clear + 1 flag + 1 uncertain -> majority is "clear"; the flag model is
    # the outlier; the uncertain model is neither counted nor badged.
    models = [_model("a", 0.2), _model("b", 0.2), _model("u", 0.5), _model("c", 0.9)]
    banded = {b["id"]: b for b in _evaluate(models)["models_banded"]}

    assert banded["u"]["call"] == UNCERTAIN_BAND
    assert banded["u"]["outlier"] is False
    assert banded["a"]["outlier"] is False
    assert banded["b"]["outlier"] is False
    assert banded["c"]["outlier"] is True


def test_uncertain_majority_does_not_steal_the_vote():
    # Regression for the old frontend logic: 2 uncertain + 1 flag + 1 clear
    # used to make "uncertain" the majority (2 raw votes) and badge BOTH
    # decisive models. With uncertain excluded, the decisive camps tie, so
    # there is no majority and nobody is an outlier.
    models = [_model("u1", 0.5), _model("u2", 0.55), _model("f", 0.9), _model("c", 0.1)]
    banded = {b["id"]: b for b in _evaluate(models)["models_banded"]}

    assert banded["u1"]["outlier"] is False and banded["u2"]["outlier"] is False
    assert banded["f"]["outlier"] is False and banded["c"]["outlier"] is False


def test_single_decisive_camp_has_no_outlier():
    # 3 clear + 1 uncertain: only one decisive camp -> no disagreement ->
    # no majority, nobody badged.
    models = [_model("a", 0.1), _model("b", 0.2), _model("c", 0.3), _model("u", 0.5)]
    banded = {b["id"]: b for b in _evaluate(models)["models_banded"]}

    assert all(b["outlier"] is False for b in banded.values())
