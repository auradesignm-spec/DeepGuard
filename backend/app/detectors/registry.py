"""Detector registry — single enumeration point for detection models.

Project constant #1: the four production models, their weights and their
thresholds live in ``app.services.detector`` and are NEVER moved, modified or
replaced. This registry *references* them (lazily, via module globals) so the
verdict engine, the scores UI and the pipeline all enumerate detectors from
one place while model behavior stays byte-for-byte identical.

Kinds
-----
``generation``   — answers "is this image AI-generated?" (the four current
                   models; the only kind with members today).
``editing``      — returns a manipulation heatmap. RESERVED: no editing model
                   is registered, therefore the "Possible Edits" verdict can
                   never be issued (project constant #5 — the algorithmic
                   checks max out at "Investigate").
``authenticity`` — camera/source authenticity signals (future slot).

Weights
-------
``DetectorSpec.weight`` and ``ARBITER_CONDITIONAL_WEIGHTS`` are *display
mirrors* of the values used inside ``_arbiter_fuse``. A behavioral test
(``tests/test_registry.py::test_weights_pinned_to_arbiter``) recomputes the
fusion from these numbers and fails loudly if detector.py ever drifts, so the
UI can never print a weight the engine does not actually use.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

KIND_GENERATION = "generation"
KIND_EDITING = "editing"
KIND_AUTHENTICITY = "authenticity"
KINDS = (KIND_GENERATION, KIND_EDITING, KIND_AUTHENTICITY)

ROLES = ("primary", "supporting")


@dataclass(frozen=True)
class DetectorSpec:
    """Static description of one registered detector."""

    id: str                 # stable machine id used in votes/results
    label_en: str           # display name (EN)
    label_ar: str           # display name (AR)
    kind: str               # generation | editing | authenticity
    source: str             # HF repo id or local weights path
    framework: str          # runtime + architecture
    input_spec: str         # input size / preprocessing
    output_spec: str        # shape/meaning of the raw output
    weight: float           # arbiter base weight (display mirror)
    role: str               # primary | supporting
    global_name: str        # module-global holding the loaded model

    def is_available(self) -> bool:
        """True when the backing model object is loaded (never raises)."""
        try:
            import app.services.detector as det
        except Exception:  # pragma: no cover - import should never fail here
            return False
        return getattr(det, self.global_name, None) is not None


# Conditional arbiter weights (display mirror of _arbiter_fuse branches).
ARBITER_CONDITIONAL_WEIGHTS: Dict[str, float] = {
    "face_v2_face_absent": 0.55,        # face specialist without a face crop
    "face_v2_quality_poor_cap": 0.5,    # poor tier caps the face vote
    "face_v2_quality_degraded_factor": 0.8,  # degraded tier scales it down
}


DETECTORS: Tuple[DetectorSpec, ...] = (
    DetectorSpec(
        id="face_v2",
        label_en="Face specialist",
        label_ar="متخصص الوجوه",
        kind=KIND_GENERATION,
        source="prithivMLmods/Deep-Fake-Detector-v2-Model",
        framework="PyTorch / transformers (ViT-base)",
        input_spec="224x224 BlazeFace face crop (min side 224px); falls back to full image when no face",
        output_spec="2-label probabilities (Deepfake/Realism) -> fake_prob",
        weight=1.0,
        role="primary",
        global_name="GLOBAL_DETECTOR",
    ),
    DetectorSpec(
        id="sdxl",
        label_en="Whole-image diffusion detector",
        label_ar="كاشف التوليد للصورة كاملة",
        kind=KIND_GENERATION,
        source="Organika/sdxl-detector",
        framework="PyTorch / transformers (Swin)",
        input_spec="224x224 full image",
        output_spec="artificial/human labels -> fake_prob",
        weight=1.0,
        role="primary",
        global_name="GLOBAL_SECONDARY_DETECTOR",
    ),
    DetectorSpec(
        id="commfor",
        label_en="CommFor generator specialist",
        label_ar="متخصص مولّدات CommFor",
        kind=KIND_GENERATION,
        source="backend/commfor_384.safetensors (CommFor, CVPR 2025)",
        framework="PyTorch / timm (ViT-small/384)",
        input_spec="Resize(440) + CenterCrop(384) + ImageNet normalization",
        output_spec="single logit -> sigmoid fake_prob",
        weight=1.25,
        role="primary",
        global_name="GLOBAL_COMMFOR_DETECTOR",
    ),
    DetectorSpec(
        id="dima806",
        label_en="Independent deepfake ViT",
        label_ar="كاشف التزييف المستقل",
        kind=KIND_GENERATION,
        source="dima806/deepfake_vs_real_image_detection",
        framework="PyTorch / transformers (ViT)",
        input_spec="224x224 full image",
        output_spec="Real/Fake labels -> fake_prob",
        weight=0.7,
        role="supporting",
        global_name="GLOBAL_QUATERNARY_DETECTOR",
    ),
)


def spec_by_id(detector_id: str) -> Optional[DetectorSpec]:
    """Look up a registered spec by id (None when unknown)."""
    for spec in DETECTORS:
        if spec.id == detector_id:
            return spec
    return None


def all_detectors() -> List[DetectorSpec]:
    """Every registered detector, in registration order."""
    return list(DETECTORS)


def generation_detectors(available_only: bool = False) -> List[DetectorSpec]:
    """AI-generation detectors (the four). ``available_only`` filters to the
    ones actually loaded in this process."""
    specs = [d for d in DETECTORS if d.kind == KIND_GENERATION]
    if available_only:
        specs = [d for d in specs if d.is_available()]
    return specs


def editing_detectors() -> List[DetectorSpec]:
    """Editing/heatmap detectors. Reserved slot — empty until a real editing
    model is registered (Possible Edits stays unreachable until then)."""
    return [d for d in DETECTORS if d.kind == KIND_EDITING]


def working_generation_count() -> int:
    """How many generation detectors are actually loaded right now."""
    return len(generation_detectors(available_only=True))
