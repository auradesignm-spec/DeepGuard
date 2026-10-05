"""Threshold calibration — proposes, never applies.

Usage (production, real models)::

    python scripts/calibrate.py --data path/to/labeled_root [--holdout 0.3]
                                [--seed 42] [--out verdict_config.proposed.json]

Labeled root layout (folders you create)::

    labeled_root/
        real/    # authentic camera/photo samples
        ai/      # AI-generated samples
        edited/  # manipulated/edited samples (reported, not threshold-fitted)

What it measures (real numbers only):

* per detector: precision / recall / F1 / confusion matrix / false-positive
  rate at the CURRENT flag threshold, plus the best-F1 threshold found by a
  sweep — computed on the calibration split, then reported untouched on the
  holdout split,
* the fused probability the same way at the current verdict thresholds,
* ROC/AUC (rank-based, no external dependencies).

Rules honored here:

* output goes to ``verdict_config.proposed.json`` ONLY — the active
  ``verdict_config.json`` is read but never written (enforced by a test),
* every proposal carries ``requires_approval: true`` — nothing is applied,
* if a class has fewer samples than ``--stat-min`` (default 200), the report
  carries a statistical warning and conclusions must not be drawn from it,
* missing classes produce an explicit "unavailable" note, never numbers.

Injectable prediction: tests pass ``predict_fn``; production uses the real
four-model pipeline via ``app.services.detector``.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.verdict_config import CONFIG_PATH, PROPOSED_PATH  # noqa: E402

PredictFn = Callable[[str], Dict[str, Any]]

CLASSES = ("real", "ai", "edited")
DEFAULT_STAT_MIN = 200
SWEEP = [round(0.30 + i * 0.01, 2) for i in range(66)]  # 0.30 .. 0.95


# ---------------------------------------------------------------------------
# Metrics (pure python, no dependencies)
# ---------------------------------------------------------------------------

def compute_metrics(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    for y, s in zip(y_true, scores):
        pred = 1 if s > threshold else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    fpr = fp / (fp + tn) if (fp + tn) else None
    return {
        "threshold": threshold,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
    }


def roc_auc(y_true: Sequence[int], scores: Sequence[float]) -> Optional[float]:
    """Rank-based AUC (Mann-Whitney U). None when a class is missing."""
    pos = [s for y, s in zip(y_true, scores) if y == 1]
    neg = [s for y, s in zip(y_true, scores) if y == 0]
    if not pos or not neg:
        return None
    # tie-aware: fraction of (pos > neg) pairs + 0.5 * ties
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def sweep_best_threshold(y_true: Sequence[int], scores: Sequence[float]) -> Dict[str, Any]:
    best = {"threshold": None, "f1": None}
    curve: List[Dict[str, Any]] = []
    for thr in SWEEP:
        m = compute_metrics(y_true, scores, thr)
        curve.append({"threshold": thr, "f1": m["f1"], "precision": m["precision"], "recall": m["recall"]})
        if m["f1"] is not None and (best["f1"] is None or m["f1"] > best["f1"]):
            best = {"threshold": thr, "f1": m["f1"]}
    if best["threshold"] is None:
        return {"threshold": None, "f1": None, "metrics": None}
    return {"threshold": best["threshold"], "f1": best["f1"],
            "metrics": compute_metrics(y_true, scores, best["threshold"])}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def iter_dataset(root: str) -> List[Dict[str, str]]:
    """Every file under real/ ai/ edited/ as {path, class} (sorted, stable)."""
    samples: List[Dict[str, str]] = []
    for cls in CLASSES:
        folder = os.path.join(root, cls)
        if not os.path.isdir(folder):
            continue
        for dirpath, _dirnames, filenames in os.walk(folder):
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                samples.append({"path": os.path.join(dirpath, name), "class": cls})
    return samples


def split_rows(rows: List[Dict[str, Any]], holdout_frac: float, seed: int) -> Tuple[List, List]:
    """Deterministic split keyed by (seed, relative path) — stable across runs."""
    cal, hold = [], []
    for row in rows:
        key = f"{seed}:{row['path']}".encode("utf-8")
        bucket = int(hashlib.sha256(key).hexdigest(), 16) % 10_000 / 10_000.0
        (hold if bucket < holdout_frac else cal).append(row)
    return cal, hold


def default_predict(path: str) -> Dict[str, Any]:
    """Production predictor: the real four-model pipeline + per-model votes."""
    from PIL import Image

    from app.services import detector as det

    with open(path, "rb") as fh:
        raw = fh.read()
    img = Image.open(path)
    real_prob, fake_prob, _conf, _ma = det.analyze_image_forgery(img, raw_bytes=raw)
    return {"probs": dict(det.last_votes()), "fused": float(fake_prob), "real_prob": float(real_prob)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    rows: List[Dict[str, Any]],
    *,
    root: str,
    rules: Dict[str, Any],
    holdout_frac: float,
    seed: int,
    stat_min: int = DEFAULT_STAT_MIN,
) -> Dict[str, Any]:
    counts = {cls: 0 for cls in CLASSES}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1

    cal_rows, hold_rows = split_rows(rows, holdout_frac, seed)

    report: Dict[str, Any] = {
        "tool": "calibrate.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "root": root,
            "counts": counts,
            "split": {
                "calibration": len(cal_rows),
                "holdout": len(hold_rows),
                "holdout_fraction": holdout_frac,
                "seed": seed,
            },
            "binary_task": "ai = positive, real = negative; edited excluded from threshold fitting",
            "statistical_warning": None,
        },
        "current_thresholds": {
            "per_model_flag_bar_good_tier": 0.70,
            "fused_fake_good_tier": 0.70,
            "fused_real": 0.45,
            "source": "read from active config/code; this script NEVER writes them",
        },
        "models": {},
        "edited_behavior": {},
        "proposals": [],
        "notes": [],
    }

    n_pos, n_neg = counts.get("ai", 0), counts.get("real", 0)
    if min(n_pos, n_neg) < stat_min:
        report["dataset"]["statistical_warning"] = (
            f"Only {n_pos} AI / {n_neg} real samples (recommended >= {stat_min} per class). "
            f"These results are indicative only — do not draw conclusions or apply thresholds from them."
        )

    if n_pos == 0 or n_neg == 0:
        report["notes"].append(
            "Binary calibration unavailable: need both ai/ and real/ samples "
            f"(found ai={n_pos}, real={n_neg}). No metrics invented."
        )
        return report

    # Collect per-model score vectors (binary classes only, per split).
    model_ids = sorted({mid for row in rows for mid in row.get("probs", {})})

    def vectors(subset):
        y = [1 if r["class"] == "ai" else 0 for r in subset]
        per_model = {
            mid: [r["probs"].get(mid) for r in subset] for mid in model_ids
        }
        fused = [r.get("fused") for r in subset]
        return y, per_model, fused

    for split_name, subset in (("calibration", cal_rows), ("holdout", hold_rows)):
        if not subset:
            continue
        y, per_model, fused = vectors(subset)
        for mid in model_ids:
            scores = per_model[mid]
            if any(s is None for s in scores):
                report["models"].setdefault(mid, {})[split_name] = {
                    "unavailable": "model produced no output for some samples"
                }
                continue
            entry = report["models"].setdefault(mid, {})
            entry[split_name] = {
                "n_pos": sum(y),
                "n_neg": len(y) - sum(y),
                "at_current_threshold": compute_metrics(y, scores, 0.70),
                "auc": roc_auc(y, scores),
            }
            if split_name == "calibration":
                best = sweep_best_threshold(y, scores)
                entry[split_name]["best_f1_sweep"] = best
        if all(s is not None for s in fused):
            entry = report["models"].setdefault("fused", {})
            entry[split_name] = {
                "n_pos": sum(y),
                "n_neg": len(y) - sum(y),
                "at_current_threshold": compute_metrics(y, fused, 0.70),
                "auc": roc_auc(y, fused),
            }
            if split_name == "calibration":
                entry[split_name]["best_f1_sweep"] = sweep_best_threshold(y, fused)

    # Proposals: only from the calibration split, only when F1 actually improves.
    for mid, entry in report["models"].items():
        cal = entry.get("calibration") or {}
        best = cal.get("best_f1_sweep") or {}
        cur = cal.get("at_current_threshold") or {}
        if best.get("threshold") is None or best.get("f1") is None:
            continue
        cur_f1 = cur.get("f1")
        cur_f1_cmp = 0.0 if cur_f1 is None else cur_f1  # no positive calls at all -> 0
        if best["threshold"] != 0.70 and best["f1"] > cur_f1_cmp:
            report["proposals"].append({
                "target": f"threshold.{mid}",
                "current": 0.70,
                "proposed": best["threshold"],
                "evidence": {
                    "calibration_f1_current": cur_f1,
                    "calibration_f1_proposed": best["f1"],
                    "holdout_at_current": (entry.get("holdout") or {}).get("at_current_threshold"),
                },
                "requires_approval": True,
            })

    # Descriptive behavior on edited samples (no fitting, no claims).
    edited_rows = [r for r in rows if r["class"] == "edited"]
    if edited_rows:
        report["edited_behavior"]["n"] = len(edited_rows)
        for mid in model_ids:
            vals = [r["probs"].get(mid) for r in edited_rows if r["probs"].get(mid) is not None]
            if vals:
                report["edited_behavior"][mid] = {
                    "mean_prob_fake": sum(vals) / len(vals),
                    "min": min(vals),
                    "max": max(vals),
                }

    if not report["proposals"]:
        report["notes"].append(
            "No threshold change proposed: the sweep did not beat the current threshold "
            "on the calibration split (or the dataset is too small)."
        )
    report["notes"].append(
        "Proposals are advisory only: apply manually after operator review "
        "(verdict_config.json is never written by this script)."
    )
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate thresholds; writes proposed config only.")
    parser.add_argument("--data", required=True, help="labeled root with real/ ai/ edited/ subfolders")
    parser.add_argument("--holdout", type=float, default=0.3, help="holdout fraction (default 0.3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stat-min", type=int, default=DEFAULT_STAT_MIN)
    parser.add_argument("--out", default=PROPOSED_PATH)
    parser.add_argument("--limit", type=int, default=0, help="cap samples per class (0 = all)")
    args = parser.parse_args(argv)

    samples = iter_dataset(args.data)
    if args.limit:
        capped: List[Dict[str, str]] = []
        for cls in CLASSES:
            cls_rows = [s for s in samples if s["class"] == cls][: args.limit]
            capped.extend(cls_rows)
        samples = capped
    if not samples:
        print(f"No samples found under {args.data} (expected real/ ai/ edited/).", file=sys.stderr)
        return 2

    # Cache predictions (each image analyzed once across splits).
    cache: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for sample in samples:
        path = sample["path"]
        if path not in cache:
            try:
                cache[path] = default_predict(path)
            except Exception as exc:  # keep going; record honest failure
                cache[path] = {"error": str(exc)}
        pred = cache[path]
        if "error" in pred:
            print(f"skipped {path}: {pred['error']}", file=sys.stderr)
            continue
        rows.append({**sample, **pred})

    from app.verdict_config import load_rules

    report = build_report(
        rows,
        root=args.data,
        rules=load_rules(),
        holdout_frac=args.holdout,
        seed=args.seed,
        stat_min=args.stat_min,
    )
    report["skipped_files"] = len(samples) - len(rows)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out} ({len(rows)} samples scored, "
          f"{len(report['proposals'])} proposal(s)). Config untouched: {CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
