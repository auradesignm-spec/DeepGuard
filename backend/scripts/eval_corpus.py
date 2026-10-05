"""Regression corpus runner: re-run the documented live test matrix.

Usage (from backend/):
    python scripts/eval_corpus.py path1.jpg path2.png ...

Each image is analyzed with the same entry point the API uses
(raw bytes passed for provenance scanning) and classified with the
production verdict bands. Exit code 0 always; results are printed as a
table so a human judges correctness against known ground truth.

Documented baseline (CONCERNS.md, 2026-09-27):
    real-user 0.27 real | ChatGPT-edited 0.92 fake+c2pa | trump 0.12 real
    aldrin 0.11 real | macron 0.19 real | flux-portrait 0.87 fake
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.detector import analyze_image_forgery, classify_verdict  # noqa: E402


def main(paths):
    print(f"{'image':<44} {'real':>6} {'fake':>6} {'verdict':>10}  provenance")
    print("-" * 88)
    for p in paths:
        if not os.path.exists(p):
            print(f"{p:<44} {'-':>6} {'-':>6} {'MISSING':>10}")
            continue
        with open(p, "rb") as fh:
            raw = fh.read()
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        real_prob, fake_prob, _, _ = analyze_image_forgery(img, raw_bytes=raw)
        verdict = classify_verdict(fake_prob)
        from app.services.detector import last_provenance_hit
        prov = last_provenance_hit() or "-"
        name = os.path.basename(p)
        print(f"{name:<44} {real_prob:>6.2f} {fake_prob:>6.2f} {verdict:>10}  {prov}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: python scripts/eval_corpus.py <image> [<image> ...]")
        sys.exit(1)
    main(args)
