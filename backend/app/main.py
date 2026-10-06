import hashlib
import io
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.analysis_schema import new_analysis, set_section, validate_analysis
from app.services.research import apply_research
from app.detectors import registry
from app.services.c2pa_check import check_c2pa
from app.services.detector import (
    analyze_image_forgery,
    classify_verdict_calibrated,
    last_provenance_hit,
    last_audit,
    last_quality,
    last_votes,
    last_default_votes,
    last_commfor_logit,
    last_face_count,
    last_crop_count,
)
from app.services.forensics import build_technical_info, run_forensics
from app.services.news_detector import analyze_news_screenshot
from app.services import sieve, sieve_store
from app.services.sieve import SieveError
from app.verdict_engine import evaluate as evaluate_verdict

app = FastAPI(title="DeepGuard Forensic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Sieve scrape API
#
# Thin HTTP wiring over app.services.sieve. The key stays server-side; these
# routes never return it. Nothing here runs when SIEVE_API_KEY is unset -
# every endpoint answers 503 and the rest of the app is untouched.
# ---------------------------------------------------------------------------

class SieveScrapeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    instruction: str
    target_urls: Optional[List[str]] = None
    fields: Optional[List[str]] = None
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    output_schema: Optional[Dict[str, Any]] = None
    table_shape: Optional[str] = None
    compliance_mode: Optional[str] = None


class SieveFollowUpRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    instruction: Optional[str] = None
    target_urls: Optional[List[str]] = None
    fields: Optional[List[str]] = None
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    output_schema: Optional[Dict[str, Any]] = None
    table_shape: Optional[str] = None
    compliance_mode: Optional[str] = None
    previous_turns: Optional[int] = None


def _sieve_guard() -> None:
    if not sieve.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Sieve is not configured. Run 'python scripts/sieve_device_login.py' "
                "to store SIEVE_API_KEY in backend/.env."
            ),
        )


def _sieve_http_error(exc: SieveError) -> HTTPException:
    headers = None
    if exc.retry_after is not None:
        headers = {"Retry-After": str(int(exc.retry_after))}
    return HTTPException(status_code=exc.http_status, detail=exc.as_detail(), headers=headers)


@app.get("/api/v1/sieve/status")
def sieve_status():
    """Whether Sieve is configured. Never reports the key itself."""
    return {"configured": sieve.is_configured(), "base_url": settings.SIEVE_BASE_URL}


@app.get("/api/v1/sieve/scrapes")
def sieve_sessions():
    """Persisted sessions, newest first - how a crash resumes polling."""
    _sieve_guard()
    return {"sessions": sieve_store.list_sessions()}


@app.post("/api/v1/sieve/scrapes", status_code=202)
def sieve_start_scrape(req: SieveScrapeRequest):
    _sieve_guard()
    try:
        return sieve.start_scrape(
            req.instruction,
            target_urls=req.target_urls,
            fields=req.fields,
            schema=req.schema_,
            output_schema=req.output_schema,
            table_shape=req.table_shape,
            compliance_mode=req.compliance_mode,
        )
    except SieveError as exc:
        raise _sieve_http_error(exc)


@app.get("/api/v1/sieve/scrapes/{session_id}")
def sieve_poll_scrape(session_id: str):
    _sieve_guard()
    try:
        run = sieve.poll_run(session_id)
    except SieveError as exc:
        raise _sieve_http_error(exc)
    sieve_store.update_session(
        session_id,
        last_status=run.get("status"),
        turns=run.get("turns"),
        files=run.get("files", []),
    )
    return run


@app.post("/api/v1/sieve/scrapes/{session_id}/messages")
def sieve_follow_up(session_id: str, req: SieveFollowUpRequest):
    _sieve_guard()
    try:
        return sieve.send_followup(
            session_id,
            instruction=req.instruction,
            target_urls=req.target_urls,
            fields=req.fields,
            schema=req.schema_,
            output_schema=req.output_schema,
            table_shape=req.table_shape,
            compliance_mode=req.compliance_mode,
            previous_turns=req.previous_turns,
        )
    except SieveError as exc:
        raise _sieve_http_error(exc)


@app.get("/api/v1/sieve/scrapes/{session_id}/files/{name}")
def sieve_download_file(session_id: str, name: str):
    """Proxy a delivered file, adding the Bearer header server-side."""
    _sieve_guard()
    record = sieve_store.load_session(session_id) or {}
    entry = next(
        (f for f in record.get("files", []) if isinstance(f, dict) and f.get("name") == name),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="No stored file with that name for this session.")
    try:
        content, content_type = sieve.fetch_file(entry)
    except SieveError as exc:
        raise _sieve_http_error(exc)
    filename = os.path.basename(name) or "download"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/v1/detect")
def detect_image(file: UploadFile = File(...)):
    try:
        contents = file.file.read()
        image = Image.open(io.BytesIO(contents))

        # تشغيل الفحص (نمرر البايتات الخام لفحص بصمة C2PA/المولّد)
        real_prob, fake_prob, confidence, multi_aspect_scores = analyze_image_forgery(image, raw_bytes=contents)

        verdict = classify_verdict_calibrated(fake_prob, last_quality().get("tier", "good"))
        verdict_text = {
            "fake": "Fake",
            "real": "Real",
            "uncertain": "Uncertain - manual review recommended",
        }[verdict]
        report_text = f"Analyzed using deep learning model. Result: {verdict_text}"

        provenance = last_provenance_hit()
        if provenance:
            report_text += f" | Provenance evidence: {provenance}"

        quality = last_quality()
        audit = last_audit()
        if quality.get("tier") != "good":
            report_text += f" | Specimen quality: {quality.get('tier')} ({'; '.join(quality.get('notes', []))})"

        return {
            "status": "success",
            "verdict": verdict,
            "provenance": provenance,
            "real_prob": float(real_prob),
            "fake_prob": float(fake_prob),
            "confidence": float(confidence),
            "quality": quality,
            "arbiter_audit": audit,
            "multi_aspect_scores": multi_aspect_scores,
            "forensic_analysis": report_text,
            "report_id": f"deepfake_report_{file.filename}.pdf"
        }

    except Exception as e:
        logging.error(f"Error processing image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Full investigation record (m1-m7 schema; the legacy /api/v1/detect above
# stays byte-identical for old clients).
# ---------------------------------------------------------------------------

_NOT_IMPLEMENTED_YET = "Section not implemented yet."
_NOT_IMPLEMENTED_YET_AR = "هذا القسم لم يُنفَّذ بعد."
# skip reasons are shown to the user, so they ship in both languages (m8-a)
_NOT_IMPLEMENTED_DATA = {
    "reason_en": _NOT_IMPLEMENTED_YET,
    "reason_ar": _NOT_IMPLEMENTED_YET_AR,
}


def _safe_upload_name(name: Optional[str]) -> str:
    base = os.path.basename(name or "upload")
    return "".join(ch for ch in base if ch.isalnum() or ch in " ._-()")[:200] or "upload"


def _model_entries(
    votes: Dict[str, float],
    *,
    default_votes: Optional[set] = None,
    commfor_logit: Optional[float] = None,
    face_count: Optional[int] = None,
    crop_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Model cards. The extras (logit / counts / default flag) are
    display-only and never feed the verdict engine."""
    default_votes = default_votes or set()
    entries: List[Dict[str, Any]] = []
    for spec in registry.all_detectors():
        entry: Dict[str, Any] = {
            "id": spec.id,
            "label_en": spec.label_en,
            "label_ar": spec.label_ar,
            "kind": spec.kind,
            "source": spec.source,
            "weight": spec.weight,
            "role": spec.role,
        }
        if spec.id in votes:
            entry["status"] = "ok"
            entry["prob_fake"] = round(float(votes[spec.id]), 4)
            if spec.id in default_votes:
                entry["default_value"] = True
            if spec.id == "commfor" and commfor_logit is not None:
                entry["logit"] = round(float(commfor_logit), 6)
            if spec.id == "face_v2":
                if face_count is not None:
                    entry["face_count"] = int(face_count)
                if crop_count is not None:
                    entry["crop_count"] = int(crop_count)
        elif not spec.is_available():
            entry["status"] = "error"
            entry["error"] = "Model not loaded in this process."
        else:
            entry["status"] = "error"
            entry["error"] = "Detector produced no vote for this image."
        entries.append(entry)
    return entries


@app.post("/api/v1/analyze")
def analyze_full(file: UploadFile = File(...)):
    """Full investigation record: models + forensic checks + verdict engine."""
    contents = file.file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except Exception:
        raise HTTPException(status_code=400, detail="Not a decodable image file.")
    if image.width * image.height > settings.MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds the allowed pixel count (decompression-bomb guard).",
        )

    record = new_analysis(
        name=_safe_upload_name(file.filename),
        sha256=hashlib.sha256(contents).hexdigest(),
        size_bytes=len(contents),
        width=image.width,
        height=image.height,
        format=image.format,
    )
    pipeline = record["pipeline"]

    def _step(name: str, fn):
        t0 = time.perf_counter()
        try:
            out = fn()
            status, summary = "ok", ""
        except Exception as exc:
            logging.error("pipeline step %s failed: %s", name, exc)
            out, status, summary = None, "error", str(exc)
        pipeline.append({
            "name": name,
            "status": status,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "summary": summary,
        })
        return out

    # 1. four detectors + fused probability (behavior unchanged)
    fusion = _step("detectors_fusion", lambda: analyze_image_forgery(image, raw_bytes=contents))
    model_extras: Dict[str, Any] = {}
    if fusion is None:
        # never read another request's stashed votes/quality/provenance
        votes, quality, fused_fake = {}, {}, None
        provenance_hit, audit = "", []
    else:
        votes = dict(last_votes())
        quality = dict(last_quality())
        fused_fake = float(fusion[1])
        provenance_hit = last_provenance_hit()
        audit = last_audit()
        model_extras = {
            "default_votes": last_default_votes(),
            "commfor_logit": last_commfor_logit(),
            "face_count": last_face_count(),
            "crop_count": last_crop_count(),
        }
    quality_tier = quality.get("tier", "good")

    record["models"] = _model_entries(votes, **model_extras)

    # 2. free algorithmic forensic checks
    forensics_result = _step("forensic_checks", lambda: run_forensics(image, contents))
    if forensics_result is not None:
        record["forensics"] = {
            "state": "ok",
            "checks": forensics_result["checks"],
            "durations_ms": forensics_result["durations_ms"],
            "total_ms": forensics_result["total_ms"],
        }
    else:
        record["forensics"] = {
            "state": "error",
            "checks": [],
            "error": "Forensic checks failed to run.",
        }

    # 3. C2PA / Content Credentials (needs a real path for the SDK)
    c2pa_card: Dict[str, Any]
    tmp_path = None
    try:
        suffix = "." + (image.format or "bin").lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=settings.UPLOAD_DIR) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        c2pa_card = _step("c2pa", lambda: check_c2pa(contents, path=tmp_path)) or {
            "id": "c2pa", "status": "error", "error": "C2PA check crashed.",
            "flag": None, "vote_capable": False, "axes": [],
            "name_en": "C2PA", "name_ar": "C2PA", "why_en": "", "why_ar": "",
        }
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    record["forensics"]["checks"].append(c2pa_card)

    # 4. technical info
    record["technical_info"] = _step("technical_info", lambda: build_technical_info(image, contents)) or {
        "state": "error", "error": "Technical info failed."
    }

    # 5. engine inputs: settle evidence, authenticity (one-way), source facts
    settle: Dict[str, Any] = {}
    for check in record["forensics"]["checks"]:
        if check.get("id") == "hash_db" and (check.get("data") or {}).get("settle"):
            settle["known_forgery_hash"] = check["data"]["settle"]
        if check.get("id") == "c2pa" and check.get("settle"):
            settle["c2pa"] = check["settle"]

    exif_data = next(
        (c.get("data") for c in record["forensics"]["checks"] if c.get("id") == "exif"),
        {},
    ) or {}
    exif_tags = exif_data.get("exif") or {}
    exif_consistent = bool(exif_tags.get("make") and exif_tags.get("model") and exif_tags.get("datetime"))
    authenticity_ids = ["exif_camera_consistent"] if exif_consistent else []
    authenticity = {"present": bool(authenticity_ids), "signal_ids": authenticity_ids}

    c2pa_payload = next(
        (c.get("data") for c in record["forensics"]["checks"] if c.get("id") == "c2pa"),
        None,
    )
    source = {
        "exif_present": bool(exif_data.get("exif_present")),
        "camera": (
            f"{exif_tags.get('make', '')} {exif_tags.get('model', '')}".strip() or None
        ),
        "datetime": exif_tags.get("datetime"),
        "gps": bool(exif_data.get("gps_present")),
        "c2pa": bool(c2pa_payload and c2pa_payload.get("found")),
    }

    # 6. verdict from the rules engine (text generated by rules only)
    verdict = _step("verdict_engine", lambda: evaluate_verdict(
        record["models"],
        forensics=record["forensics"]["checks"],
        authenticity=authenticity,
        settle=settle,
        source=source,
        quality_tier=quality_tier,
        fused_prob=fused_fake,
    ))
    if verdict is None:
        record["verdict"].update(
            state="error", error="Verdict engine failed.",
        )
    else:
        record["verdict"].update(
            state="ok",
            label=verdict["label"],
            confidence=round(max(fused_fake or 0.0, 1.0 - (fused_fake or 0.0)), 4) if fused_fake is not None else None,
            axes=verdict["axes"],
            why_rule=verdict["why_rule"],
            reasoning=verdict["reasoning"],
            human_line=verdict["human_line"],
            disagreement=verdict["disagreement"],
            rule_id=verdict["rule_id"],
            counts=verdict["counts"],
            models_banded=verdict["models_banded"],
            fused_prob=verdict["fused_prob"],
        )
        if fusion is not None:
            record["multi_aspect_scores"] = fusion[3]
        record["quality"] = quality
        record["provenance"] = provenance_hit
        record["arbiter_audit"] = audit

    # 7. section states (implemented ones now; honest skip for the rest)
    set_section(
        record, "model_scores",
        "ok" if any(m.get("status") == "ok" for m in record["models"]) else "error",
        error=None if any(m.get("status") == "ok" for m in record["models"])
        else "No generation detector produced a result.",
    )
    set_section(
        record, "pipeline",
        "error" if any(s["status"] == "error" for s in pipeline) else "ok",
    )
    c2pa_status = c2pa_card.get("status", "error")
    set_section(
        record, "c2pa", c2pa_status,
        reason=c2pa_card.get("reason"), error=c2pa_card.get("error"),
        data=c2pa_card.get("data"),
    )
    # 8. m5 research sections: real search links + rule-driven guidance
    _step("research", lambda: apply_research(
        record,
        exif_data=exif_data,
        quality_tier=quality_tier,
        provenance_hit=provenance_hit,
    ))
    # a crashed research step must never leave a card stuck in "loading"
    for _sid in (
        "reverse_search", "links_on_web", "fact_check_monitor",
        "location", "what_to_do_next", "further_investigation",
    ):
        if record["sections"][_sid].get("state") == "loading":
            set_section(
                record, _sid, "error",
                error="Research step failed before this section was filled.",
            )
    for _sub in ("web_presence", "fact_check", "links", "location"):
        if record["external"][_sub].get("state") == "loading":
            record["external"][_sub] = {
                "state": "error",
                "error": "Research step failed before this card was filled.",
            }
    if record["external"].get("state") == "loading":
        record["external"].update(
            state="error", error="Research step failed before this card was filled.",
        )

    set_section(record, "manipulation_map", "skipped",
                reason=_NOT_IMPLEMENTED_YET, data=_NOT_IMPLEMENTED_DATA)
    for sid in (
        "spot_the_difference", "whats_in_image",
        "how_we_know", "ask_about_image",
        "was_this_result_correct", "ai_visual_findings",
        "what_the_computer_sees",
    ):
        set_section(record, sid, "skipped",
                    reason=_NOT_IMPLEMENTED_YET, data=_NOT_IMPLEMENTED_DATA)

    contract = validate_analysis(record)
    if contract:
        logging.error("analysis record violates schema: %s", contract)
        raise HTTPException(status_code=500, detail={"schema_violations": contract})
    return record


@app.post("/api/v1/analyze-news")
def analyze_news(file: UploadFile = File(...)):
    """News screenshot misinformation scan: OCR + text-manipulation
    analysis + image forensics + external fact-check, fused by a
    weighted arbiter with disputed-claim anchors."""
    try:
        contents = file.file.read()
        image = Image.open(io.BytesIO(contents))
        result = analyze_news_screenshot(image, raw_bytes=contents)
        return result
    except Exception as e:
        logging.error(f"Error analyzing news screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))