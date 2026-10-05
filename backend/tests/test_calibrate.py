"""m2 — calibrate.py tests: metric math + the promise that it only proposes."""

import hashlib
import json
import os

import pytest

from scripts.calibrate import (
    build_report,
    compute_metrics,
    iter_dataset,
    main,
    roc_auc,
    split_rows,
    sweep_best_threshold,
)
from app.verdict_config import CONFIG_PATH, load_rules, reload_rules


# ---------------------------------------------------------------------------
# Metric math (hand-computed)
# ---------------------------------------------------------------------------

def test_compute_metrics_hand_computed():
    y = [1, 1, 0, 0]
    s = [0.9, 0.4, 0.6, 0.2]  # 1 TP, 1 FN, 1 FP, 1 TN at thr=0.5
    m = compute_metrics(y, s, 0.5)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (1, 1, 1, 1)
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5)
    assert m["fpr"] == pytest.approx(0.5)


def test_compute_metrics_no_false_positives():
    m = compute_metrics([1, 0], [0.9, 0.1], 0.5)
    assert m["precision"] == 1.0 and m["fpr"] == 0.0


def test_roc_auc_perfect_and_inverted():
    assert roc_auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0
    assert roc_auc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0
    assert roc_auc([1, 1, 0, 0], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_roc_auc_needs_both_classes():
    assert roc_auc([1, 1], [0.9, 0.8]) is None


def test_sweep_picks_separating_threshold():
    y = [1, 1, 1, 0, 0, 0]
    s = [0.9, 0.85, 0.8, 0.3, 0.2, 0.1]
    best = sweep_best_threshold(y, s)
    assert best["f1"] == 1.0
    assert 0.30 <= best["threshold"] <= 0.80


# ---------------------------------------------------------------------------
# Dataset plumbing
# ---------------------------------------------------------------------------

def _make_dataset(tmp_path, real=3, ai=3, edited=1):
    for cls, n in (("real", real), ("ai", ai), ("edited", edited)):
        folder = tmp_path / cls
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (folder / f"{cls}_{i}.png").write_bytes(b"fake-image-bytes")
    return str(tmp_path)


def test_iter_dataset_counts(tmp_path):
    root = _make_dataset(tmp_path, real=2, ai=4, edited=0)
    rows = iter_dataset(root)
    assert len(rows) == 6
    assert {r["class"] for r in rows} == {"real", "ai"}


def test_split_is_deterministic_and_covering():
    rows = [{"path": f"/x/{i}.png", "class": "ai" if i % 2 else "real"} for i in range(50)]
    cal1, hold1 = split_rows(rows, 0.3, 42)
    cal2, hold2 = split_rows(rows, 0.3, 42)
    assert [r["path"] for r in cal1] == [r["path"] for r in cal2]
    assert len(cal1) + len(hold1) == 50
    assert len(hold1) > 0


# ---------------------------------------------------------------------------
# Report building (synthetic predictions — no models needed)
# ---------------------------------------------------------------------------

def _synthetic_rows(n_real=30, n_ai=30, n_edited=10, perfect=True):
    rows = []
    for i in range(n_real):
        p = 0.05 if perfect else (0.4 + 0.4 * ((i % 5) / 5))
        rows.append({"path": f"real/{i}.png", "class": "real",
                     "probs": {"sdxl": p, "commfor": p}, "fused": p})
    for i in range(n_ai):
        p = 0.95 if perfect else (0.3 + 0.6 * ((i % 5) / 5))
        rows.append({"path": f"ai/{i}.png", "class": "ai",
                     "probs": {"sdxl": p, "commfor": p}, "fused": p})
    for i in range(n_edited):
        rows.append({"path": f"edited/{i}.png", "class": "edited",
                     "probs": {"sdxl": 0.5, "commfor": 0.5}, "fused": 0.5})
    return rows


def test_build_report_full_dataset():
    rows = _synthetic_rows()
    report = build_report(rows, root="/d", rules=reload_rules(), holdout_frac=0.3, seed=42)
    assert report["dataset"]["counts"] == {"real": 30, "ai": 30, "edited": 10}
    assert report["dataset"]["split"]["calibration"] + report["dataset"]["split"]["holdout"] == 70
    assert report["dataset"]["statistical_warning"]  # 30 < 200 per class
    assert "sdxl" in report["models"] and "fused" in report["models"]
    cal = report["models"]["sdxl"]["calibration"]
    assert cal["at_current_threshold"]["fpr"] == 0.0
    assert cal["auc"] == 1.0
    # edited excluded from binary fitting but described
    assert report["edited_behavior"]["n"] == 10
    assert "mean_prob_fake" in report["edited_behavior"]["sdxl"]


def test_build_report_missing_class_is_honest():
    rows = _synthetic_rows(n_ai=0)
    report = build_report(rows, root="/d", rules=reload_rules(), holdout_frac=0.3, seed=42)
    assert report["models"] == {}
    assert any("Binary calibration unavailable" in n for n in report["notes"])
    assert report["proposals"] == []


def test_no_proposal_when_perfect_already():
    rows = _synthetic_rows(perfect=True)
    report = build_report(rows, root="/d", rules=reload_rules(), holdout_frac=0.3, seed=42)
    # perfect separation at 0.70 -> sweep finds no better threshold
    assert report["proposals"] == []


def test_proposal_carries_approval_flag():
    # construct data where current 0.70 threshold is clearly suboptimal
    rows = []
    for i in range(40):
        rows.append({"path": f"real/{i}.png", "class": "real", "probs": {"x": 0.02}, "fused": 0.02})
    for i in range(40):
        # positives sit at 0.60-0.65: 0.70 misses them all (f1 undefined -> 0 recall)
        rows.append({"path": f"ai/{i}.png", "class": "ai",
                     "probs": {"x": 0.60 + (i % 6) * 0.01}, "fused": 0.60})
    report = build_report(rows, root="/d", rules=reload_rules(), holdout_frac=0.3, seed=42)
    proposals = [p for p in report["proposals"] if p["target"] == "threshold.x"]
    assert proposals, "sweep should propose a lower bar for these scores"
    assert proposals[0]["requires_approval"] is True
    assert proposals[0]["current"] == 0.70
    cur_f1 = proposals[0]["evidence"]["calibration_f1_current"]
    assert proposals[0]["evidence"]["calibration_f1_proposed"] > (cur_f1 or 0.0)


# ---------------------------------------------------------------------------
# CLI: proposed-only guarantee
# ---------------------------------------------------------------------------

def test_main_writes_proposed_and_never_touches_active_config(tmp_path, monkeypatch):
    root = _make_dataset(tmp_path / "data", real=5, ai=5, edited=2)
    before = open(CONFIG_PATH, "rb").read()
    before_hash = hashlib.sha256(before).hexdigest()

    # inject a fake predictor so no real models run
    import scripts.calibrate as cal_mod

    calls = {"n": 0}

    def fake_predict(path):
        calls["n"] += 1
        is_ai = os.sep + "ai" + os.sep in path
        p = 0.92 if is_ai else 0.04
        return {"probs": {"sdxl": p}, "fused": p}

    monkeypatch.setattr(cal_mod, "default_predict", fake_predict)

    out = str(tmp_path / "verdict_config.proposed.json")
    rc = main(["--data", root, "--out", out, "--holdout", "0.3", "--seed", "7"])
    assert rc == 0

    # proposed file written and well-formed
    with open(out, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    assert report["tool"] == "calibrate.py"
    assert report["dataset"]["counts"]["real"] == 5
    assert calls["n"] == 12  # every file analyzed exactly once

    # active config untouched
    after = open(CONFIG_PATH, "rb").read()
    assert hashlib.sha256(after).hexdigest() == before_hash
    reload_rules()  # still valid


def test_main_reports_empty_dataset(tmp_path, capsys):
    rc = main(["--data", str(tmp_path / "nothing"), "--out", str(tmp_path / "p.json")])
    assert rc == 2
    assert not (tmp_path / "p.json").exists()


def test_rules_config_still_valid_after_calibrate():
    rules = load_rules()
    assert rules["calibration"]["auto_apply"] is False
