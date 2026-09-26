import os
import uuid
import shutil
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any

from app.config import settings
from app.services.detector import analyze_image_forgery
from app.services.gpt_analyzer import generate_forensic_analysis
from app.services.pdf_generator import generate_pdf_report

router = APIRouter()

ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "image/jpg", "image/gif"]


class DetectionResponse(BaseModel):
    status: str
    real_prob: float
    fake_prob: float
    confidence: float
    multi_aspect_scores: Dict[str, float]
    forensic_analysis: str
    report_id: str


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DeepGuard Forensic Backend",
        "version": settings.VERSION
    }


@router.post("/detect", response_model=DetectionResponse)
async def detect_deepfake(file: UploadFile = File(...)):
    """
    Accepts an uploaded image file, performs deep learning forensic scan,
    calculates multi-aspect distortion indicators, synthesizes GPT-4 forensic report,
    and generates an exportable ReportLab PDF.
    """
    # 1. Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file.content_type}'. Please upload a valid JPG, PNG, WEBP, or GIF image."
        )

    # 2. Save temporary upload
    file_ext = os.path.splitext(file.filename or "")[1]
    if not file_ext:
        file_ext = ".jpg"
    unique_filename = f"specimen_{uuid.uuid4().hex[:12]}{file_ext}"
    specimen_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    try:
        with open(specimen_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Model & Feature Inference
        real_prob, fake_prob, confidence, multi_aspect = analyze_image_forgery(specimen_path)

        # 4. GPT-4 Forensic Analysis
        forensic_analysis = generate_forensic_analysis(
            real_prob=real_prob,
            fake_prob=fake_prob,
            confidence=confidence,
            multi_aspect_scores=multi_aspect
        )

        # 5. Generate PDF Report
        report_id = generate_pdf_report(
            real_prob=real_prob,
            fake_prob=fake_prob,
            confidence=confidence,
            multi_aspect_scores=multi_aspect,
            forensic_analysis=forensic_analysis,
            image_path=specimen_path,
            reports_dir=settings.REPORTS_DIR
        )

        return DetectionResponse(
            status="success",
            real_prob=real_prob,
            fake_prob=fake_prob,
            confidence=confidence,
            multi_aspect_scores=multi_aspect,
            forensic_analysis=forensic_analysis,
            report_id=report_id
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forensic detection failed: {str(exc)}"
        )
    finally:
        # Cleanup uploaded specimen if needed, or keep for audit
        if os.path.exists(specimen_path):
            try:
                os.remove(specimen_path)
            except Exception:
                pass


@router.get("/download-report/{report_id}")
async def download_report(report_id: str):
    """
    Serves the generated PDF file as an attachment.
    """
    # Prevent directory traversal attacks
    safe_filename = os.path.basename(report_id)
    report_path = os.path.join(settings.REPORTS_DIR, safe_filename)

    if not os.path.exists(report_path) or not safe_filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_filename}' not found or has expired."
        )

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=safe_filename,
        headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
    )
