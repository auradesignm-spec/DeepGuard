import os
import uuid
from typing import Dict
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as PDFImage,
    Table,
    TableStyle,
    HRFlowable
)


def generate_pdf_report(
    real_prob: float,
    fake_prob: float,
    confidence: float,
    multi_aspect_scores: Dict[str, float],
    forensic_analysis: str,
    image_path: str,
    reports_dir: str
) -> str:
    """
    Generates a professional forensic PDF report using ReportLab.
    Returns the generated report filename (e.g., deepfake_report_uuid.pdf).
    """
    os.makedirs(reports_dir, exist_ok=True)
    report_filename = f"deepfake_report_{uuid.uuid4().hex[:8]}.pdf"
    report_path = os.path.join(reports_dir, report_filename)

    doc = SimpleDocTemplate(
        report_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0f172a"),
        alignment=0
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b")
    )

    heading2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155")
    )

    # 1. Header Banner
    elements.append(Paragraph("DEEPGUARD FORENSIC INTELLIGENCE", subtitle_style))
    elements.append(Paragraph("Deepfake Detection & Media Integrity Report", title_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=14))

    # 2. Executive Summary Box
    verdict = "DEEPFAKE / SYNTHETIC MEDIA" if fake_prob > 0.50 else "AUTHENTIC MEDIA"
    verdict_color = "#dc2626" if fake_prob > 0.50 else "#16a34a"

    summary_data = [
        [
            Paragraph(f"<b>VERDICT:</b> <font color='{verdict_color}'><b>{verdict}</b></font>", body_style),
            Paragraph(f"<b>CONFIDENCE:</b> {confidence * 100:.1f}%", body_style),
        ],
        [
            Paragraph(f"<b>Fake Probability:</b> {fake_prob * 100:.1f}%", body_style),
            Paragraph(f"<b>Real Probability:</b> {real_prob * 100:.1f}%", body_style),
        ]
    ]

    summary_table = Table(summary_data, colWidths=[260, 260])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # 3. Image preview (if exists)
    if os.path.exists(image_path):
        try:
            elements.append(Paragraph("Examined Media Specimen:", heading2_style))
            img = PDFImage(image_path, width=240, height=180)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 12))
        except Exception:
            pass

    # 4. Multi-Aspect Metric Table
    elements.append(Paragraph("Multi-Aspect Forensic Indicators:", heading2_style))
    aspect_rows = [["Forensic Dimension", "Risk / Anomaly Index", "Status Assessment"]]
    for key, val in multi_aspect_scores.items():
        formatted_name = key.replace("_", " ").title()
        status = "High Risk" if val > 85 else ("Elevated" if val > 75 else "Nominal")
        aspect_rows.append([formatted_name, f"{val:.1f}%", status])

    aspect_table = Table(aspect_rows, colWidths=[220, 150, 150])
    aspect_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    elements.append(aspect_table)
    elements.append(Spacer(1, 14))

    # 5. GPT-4 Detailed Forensic Findings
    elements.append(Paragraph("Expert AI Forensic Findings & Fingerprints:", heading2_style))
    for line in forensic_analysis.split("\n"):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4))
            continue
        if line.startswith("###") or line.startswith("##"):
            clean_title = line.replace("#", "").strip()
            elements.append(Paragraph(f"<b>{clean_title}</b>", ParagraphStyle('Sub', parent=body_style, fontName='Helvetica-Bold', fontSize=11, spaceBefore=6)))
        elif line.startswith("-") or line.startswith("*"):
            clean_item = line.lstrip("-* ").replace("**", "<b>", 1).replace("**", "</b>", 1)
            elements.append(Paragraph(f"• {clean_item}", body_style))
        else:
            clean_line = line.replace("**", "<b>").replace("**", "</b>")
            elements.append(Paragraph(clean_line, body_style))

    elements.append(Spacer(1, 16))

    # 6. Legal & Chain-of-Custody Notice
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    disclaimer = (
        "<b>Legal & Evidentiary Notice:</b> This automated forensic report is generated for media integrity "
        "verification and triage. False positive/negative margins exist. For judicial or criminal prosecution, "
        "cryptographic key verification and expert certified examiner attestation is advised."
    )
    elements.append(Paragraph(disclaimer, ParagraphStyle("Disc", parent=subtitle_style, fontSize=8, leading=10)))

    doc.build(elements)
    return report_filename
