"""C2PA / Content Credentials check (m3), via c2pa-python (free, open source).

Honest states:

* ``ok``            — manifest found; card shows signer, generator, actions,
                      and the cryptographic validation results,
* ``not_applicable``— no Content Credentials in the file (absence proves
                      nothing — stated in the card text),
* ``skipped``       — the c2pa-python wheel is unavailable for this Python
                      (reason says so; never fakes a result),
* ``error``         — the library failed while reading this specific file.

Trust handling (project decision): signature *validity* (crypto) and signer
*trust* (against a configured trust-anchor list) are reported separately, so
a self-signed/untrusted signer is never shown as "trusted". The official
trust-anchor file is optional (``C2PA_TRUST_ANCHORS_PATH``); when it is not
configured the card says verification against the trust list was skipped and
why. Nothing here requires network access.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

_AI_SOURCE_TYPE_MARKERS = ("trainedAlgorithmicMedia", "algorithmicmedia", "compositewithTrainedAlgorithmicMedia")
_TRUST_FAILURE_CODES = ("signingCredential.untrusted", "signingCredential.chain")
_CRYPTO_OK_CODES = ("claimSignature.validated", "claimSignature.insideValidity")


def _import_c2pa():
    try:
        import c2pa  # type: ignore
        return c2pa, None
    except Exception as exc:  # ImportError / OSError (missing wheel)
        return None, str(exc)


def _reader_context(c2pa, trust_path: str):
    """Build a per-reader Context with trust anchors when configured.

    Returns (context, trust_note). Falls back to (None, reason) on any
    configuration problem — reading then proceeds without trust anchors and
    the card reports that honestly.
    """
    if not trust_path:
        return None, "Trust-anchor list not configured (optional); signer trust not verified."
    if not os.path.isfile(trust_path):
        return None, f"Trust-anchor file not found: {trust_path}"
    try:
        settings_obj = c2pa.Settings.from_dict({"trust": {"trust_anchors": trust_path}})
        ctx = c2pa.ContextBuilder().with_settings(settings_obj).build()
        return ctx, None
    except Exception as exc:
        logger.warning("c2pa trust settings failed: %s", exc)
        return None, f"Trust-anchor configuration failed: {exc}"


def read_c2pa(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Read the manifest store.

    Returns (payload, trust_note, error). payload=None + error=None means
    "no Content Credentials".
    """
    c2pa, import_error = _import_c2pa()
    if import_error:
        return None, None, f"c2pa-python unavailable for this Python build: {import_error}"

    ctx, trust_note = _reader_context(c2pa, settings.C2PA_TRUST_ANCHORS_PATH)
    try:
        if ctx is not None:
            reader = c2pa.Reader.try_create(path, context=ctx)
        else:
            reader = c2pa.Reader.try_create(path)
    except Exception as exc:
        return None, trust_note, f"Failed to read C2PA data: {exc}"

    if reader is None:
        return None, trust_note, None

    try:
        import json as _json
        manifest_json = _json.loads(reader.json())
        results = reader.get_validation_results() or {}
        active = results.get("activeManifest", {}) if isinstance(results, dict) else {}
        successes = [s.get("code", "") for s in active.get("success", [])]
        failures = active.get("failure", []) if isinstance(active, dict) else []
        informational = active.get("informational", []) if isinstance(active, dict) else []

        mid = manifest_json.get("active_manifest")
        manifest = (manifest_json.get("manifests") or {}).get(mid, {}) if mid else {}

        generator = None
        gen_info = manifest.get("claim_generator_info")
        if isinstance(gen_info, list) and gen_info:
            generator = gen_info[0].get("name")
        elif isinstance(gen_info, dict):
            generator = gen_info.get("name")

        actions: List[Dict[str, Any]] = []
        declares_generation = False
        for assertion in manifest.get("assertions", []):
            if not str(assertion.get("label", "")).startswith("c2pa.actions"):
                continue
            for action in (assertion.get("data") or {}).get("actions", []):
                source_type = str(action.get("digitalSourceType", ""))
                agent = action.get("softwareAgent")
                agent_name = agent.get("name") if isinstance(agent, dict) else agent
                entry = {
                    "action": action.get("action"),
                    "software_agent": agent_name,
                    "when": action.get("when"),
                    "digital_source_type": source_type or None,
                }
                actions.append(entry)
                if any(marker in source_type for marker in _AI_SOURCE_TYPE_MARKERS):
                    declares_generation = True

        signature = manifest.get("signature_info") or {}
        trust_failures = [f for f in failures if f.get("code") in _TRUST_FAILURE_CODES]
        crypto_ok = any(code in successes for code in _CRYPTO_OK_CODES)
        trusted = bool(crypto_ok) and not trust_failures

        payload = {
            "found": True,
            "generator": generator,
            "title": manifest.get("title"),
            "signature": {
                "alg": signature.get("alg"),
                "issuer": signature.get("issuer"),
                "common_name": signature.get("common_name"),
                "time": signature.get("time"),
            },
            "actions": actions,
            "declares_generation": declares_generation,
            "crypto_valid": crypto_ok,
            "trusted": trusted,
            "validation_state": None,
            "failures": [{"code": f.get("code"), "explanation": f.get("explanation")} for f in failures],
            "informational": [{"code": i.get("code"), "explanation": i.get("explanation")} for i in informational],
            "trust_note": trust_note,
        }
        try:
            payload["validation_state"] = reader.get_validation_state()
        except Exception:
            pass
        return payload, trust_note, None
    except Exception as exc:
        return None, trust_note, f"Failed to parse C2PA manifest: {exc}"


def check_c2pa(raw: Optional[bytes] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """The C2PA section card (id ``c2pa``) + settle input for the engine."""
    why_en = (
        "Content Credentials (C2PA) are signed declarations embedded by the "
        "creating tool. A trusted manifest that declares generation is decisive "
        "evidence; absence of Credentials proves nothing either way."
    )
    why_ar = (
        "بيانات المصداقية (C2PA) إقرارات موقّعة يضمّنها الأداة المنشئة. البيان "
        "الموثوق الذي يعلن التوليد دليل قاطع؛ وغياب البيانات لا يثبت شيئًا."
    )

    if path is None:
        return _card_c2pa(
            status="skipped",
            why_en=why_en, why_ar=why_ar,
            reason="C2PA check needs a file path; raw-bytes-only analysis skips it.",
        )

    payload, trust_note, error = read_c2pa(path)

    if error and payload is None and "unavailable" in error:
        return _card_c2pa(status="skipped", why_en=why_en, why_ar=why_ar, reason=error)
    if error and payload is None:
        # Distinguish "library broke on this file" from "no manifest".
        if "Failed" in error:
            return _card_c2pa(status="error", why_en=why_en, why_ar=why_ar, error=error)
    if payload is None:
        return _card_c2pa(
            status="not_applicable",
            why_en=why_en, why_ar=why_ar,
            reason="No Content Credentials found — absence does not prove anything.",
        )

    settle = {
        "hit": True,
        "declares_generation": payload["declares_generation"],
        "crypto_valid": payload["crypto_valid"],
        "trusted": payload["trusted"],
        "detail": (
            f"generator={payload.get('generator') or 'unknown'}; "
            f"signer={payload['signature'].get('common_name') or payload['signature'].get('issuer') or 'unknown'}"
        ),
    }
    card = _card_c2pa(
        status="ok", why_en=why_en, why_ar=why_ar,
        data=payload, settle=settle,
    )
    if error:
        card["warning"] = error
    return card


def _card_c2pa(
    status: str,
    why_en: str,
    why_ar: str,
    data: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    error: Optional[str] = None,
    settle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    card: Dict[str, Any] = {
        "id": "c2pa",
        "name_en": "C2PA / Content Credentials",
        "name_ar": "بيانات المصداقية C2PA",
        "status": status,
        "flag": None,
        "vote_capable": False,  # decisive path goes through engine direct-settle
        "axes": ["source_check"],
        "why_en": why_en,
        "why_ar": why_ar,
    }
    if data is not None:
        card["data"] = data
    if reason is not None:
        card["reason"] = reason
    if error is not None:
        card["error"] = error
    if settle is not None:
        card["settle"] = settle
    return card


__all__ = ["check_c2pa", "read_c2pa"]
