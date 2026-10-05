# 🛡️ DeepGuard - AI Deepfake Detection & Forensic Intelligence

An enterprise-grade deepfake detection and media forensics platform powered by deep learning neural networks, multi-aspect anomaly breakdown, and GPT-4 automated forensic reporting.

---

## 🏗️ Architecture Overview

```text
DeepGuard/
├── backend/                       # Python FastAPI Microservice
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI entry point & CORS configuration
│   │   ├── config.py              # Environment variables & Settings (pydantic-settings)
│   │   ├── services/
│   │   │   ├── detector.py        # v3.1 engine: C2PA provenance scan + BlazeFace face-crop + ensemble (Deep-Fake-Detector-v2, sdxl-detector, Community Forensics CVPR'25) + real ELA/noise forensic metrics
│   │   │   ├── gpt_analyzer.py    # OpenAI GPT-4 Deepfake Forensic Report generation
│   │   │   └── pdf_generator.py   # ReportLab PDF Generation
│   │   └── api/
│   │       └── routes.py          # API endpoints (/api/v1/detect, /api/v1/download-report)
│   ├── uploads/                   # Temporary upload cache (Ignored in git)
│   ├── reports/                   # Generated forensic PDFs (Ignored in git)
│   ├── .env.example
│   └── requirements.txt
├── frontend/                      # Next.js 14+ App Router + Tailwind CSS Dashboard
│   ├── app/
│   │   ├── layout.tsx             # Root layout with dark cybersecurity theme
│   │   ├── page.tsx               # Main Forensic Dashboard Interface (ScanAnimation, v3.0 PRO badge)
│   │   ├── landing/page.tsx       # Cyber-themed landing page (radar, signal stack, pipeline)
│   │   └── api/                   # Server-side API proxy & offline fallback
│   ├── components/
│   │   ├── UploadZone.tsx         # Drag & Drop File Upload Specimen Component
│   │   ├── ResultCard.tsx         # Real vs Fake Dual Gauge / Confidence Indicators
│   │   ├── MultiAspectChart.tsx   # Visual breakdown (Lighting, Texture, Facial Distortion, etc.)
│   │   └── ForensicReport.tsx     # GPT-4 AI Findings & PDF Download CTA
│   ├── public/                    # Static branding & assets
│   └── package.json
├── .gitignore
├── metadata.json
└── README.md
```

---

## 🚀 Quick Start

### 1. Backend Setup (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY in .env

# Run FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at `http://localhost:8000/docs`.

### 2. Frontend Setup (Next.js 14 + Tailwind CSS)

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to access the DeepGuard Forensic Dashboard.

---

## 📡 API Specification

### `POST /api/v1/detect`
Performs multi-aspect forensic scan on an uploaded specimen image.

**Request:** `multipart/form-data` with `file: Binary`

**Response:**
```json
{
  "status": "success",
  "real_prob": 0.12,
  "fake_prob": 0.88,
  "confidence": 0.94,
  "multi_aspect_scores": {
    "lighting": 82.5,
    "texture": 91.0,
    "color_consistency": 78.4,
    "background_artifacts": 85.0,
    "facial_distortion": 92.1
  },
  "forensic_analysis": "### 1. Executive Summary\nThe forensic pipeline detected significant synthetic artifacts...",
  "report_id": "deepfake_report_a1b2c3d4.pdf"
}
```

### `GET /api/v1/download-report/{report_id}`
Downloads the generated ReportLab PDF forensic document with full evidentiary metrics.

---

## 🔒 Security & Privacy
- Zero persistent storage of biometric data without user authorization.
- Cryptographic hashing and path-traversal mitigation for report retrieval.
- Strict `.gitignore` enforcement avoiding committed weights, secrets, and transient uploads.

---

## Sieve Scrape API (optional, server-side)

Article/source scraping for the news pipeline comes from the Sieve scrape API.
It is optional: with `SIEVE_API_KEY` unset, every `/api/v1/sieve/*` endpoint
answers 503 and nothing else in the app changes.

**1. Create the key with a device login (approve it yourself in a browser):**

```bash
cd backend
python scripts/sieve_device_login.py
```

The script shows a verification link and a short user code, then writes the
returned key into `backend/.env` as `SIEVE_API_KEY`. It never prints the key.
You can instead create one in Sieve -> Settings -> API keys and set
`SIEVE_API_KEY=dc_sk_...` in `backend/.env` yourself.

**2. Run one live scrape (spends credits):**

```bash
cd backend
python scripts/sieve_scrape.py --instruction "Extract the text and author of each quote" --url https://quotes.toscrape.com
```

**3. Endpoints:** `POST /api/v1/sieve/scrapes` (202), `GET /api/v1/sieve/scrapes/{id}`,
`POST /api/v1/sieve/scrapes/{id}/messages`, `GET /api/v1/sieve/scrapes`,
`GET /api/v1/sieve/scrapes/{id}/files/{name}`. Sessions are persisted under
`backend/state/sieve/` so a restart resumes polling from the stored id instead
of starting a duplicate (billable) run.

**Settings:** `SIEVE_API_KEY`, `SIEVE_BASE_URL` (default `https://scrape.usesieve.com`),
`SIEVE_COMPLIANCE_MODE` (default `regular`; `yolo` relaxes the site-access policy).

The key grants full account access, so keep it server-side - never in a browser
bundle, a log, or git.
