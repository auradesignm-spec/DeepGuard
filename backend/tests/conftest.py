"""Conftest for v3 detector tests — no real models loaded.

Why this file looks the way it does
-----------------------------------
``app.services.detector`` runs its loaders at module import time and stashes
the results in module globals (``GLOBAL_DETECTOR`` etc.). Two traps:

1. Patching the *loader functions on the detector module* before
   ``importlib.reload(det)`` does NOT work: reload re-executes the module
   body, the ``def load_*`` statements rebind the names, and
   ``GLOBAL_DETECTOR = load_advanced_detector()`` then calls the REAL
   loaders — silently loading torch/transformers weights for every test
   (that was the bug this file fixes: a missing post-reload re-patch left
   real models voting in unit tests).

2. Therefore we block the heavy machinery at its SOURCE: detector.py does
   ``from transformers import pipeline`` inside the module body, so a patch
   on ``transformers.pipeline`` survives re-imports; CommFor builds through
   ``timm.create_model`` (a raise there is swallowed by its try/except and
   yields ``None``).

The module-level patches run when pytest imports this conftest — before any
test module imports ``app.services.detector`` — so even the first import
never downloads or loads weights. The fixture then reloads the module (to
reset per-test state like provenance/quality globals) and defensively
neutralises the model globals plus the lazy BlazeFace registry so
``_crop_faces`` / ``_compute_forensic_metrics`` never spin up TFLite.
"""

import importlib

import pytest


# ---------------------------------------------------------------------------
# Source-level blocks (session-wide; a test process never needs real weights)
# ---------------------------------------------------------------------------


def _pipeline_returns_none(*args, **kwargs):
    """Stand-in for transformers.pipeline -> _load_detector yields None."""
    return None


def _models_disabled(*args, **kwargs):
    """Any timm construction attempt fails fast (caught by load_commfor_detector)."""
    raise RuntimeError("model loading is disabled in tests (conftest)")


try:
    import transformers

    transformers.pipeline = _pipeline_returns_none
except ImportError:  # pragma: no cover - tests cannot run without it anyway
    pass

try:
    import timm

    timm.create_model = _models_disabled
except ImportError:  # pragma: no cover - optional in stripped environments
    pass


# ---------------------------------------------------------------------------
# Per-test fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_models(monkeypatch):
    import app.services.detector as det

    # Rebuild the module body against the blocked sources: the GLOBAL_*
    # assignments now evaluate to None (neutral votes) and per-test state
    # (_PROVENANCE_RESULT, _LAST_QUALITY, _LAST_AUDIT) starts clean.
    importlib.reload(det)

    # Belt and braces: whatever the reload produced, force neutral model
    # globals (monkeypatch restores them after the test) and mark the lazy
    # BlazeFace registry as failed so _get_face_detector() returns None
    # immediately instead of creating a TFLite delegate.
    def _none_loader(*args, **kwargs):
        return None

    for name in (
        "load_advanced_detector",
        "load_secondary_detector",
        "load_quaternary_detector",
        "load_commfor_detector",
    ):
        monkeypatch.setattr(det, name, _none_loader, raising=False)

    for name in (
        "GLOBAL_DETECTOR",
        "GLOBAL_SECONDARY_DETECTOR",
        "GLOBAL_QUATERNARY_DETECTOR",
        "GLOBAL_COMMFOR_DETECTOR",
    ):
        monkeypatch.setattr(det, name, None, raising=False)

    monkeypatch.setattr(det, "_FACE_DETECTOR", None, raising=False)
    monkeypatch.setattr(det, "_FACE_DETECTOR_FAILED", True, raising=False)
