import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DeepGuard Forensic API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment & Keys
    OPENAI_API_KEY: str = ""
    HF_REPO_ID: str = "auradesignm/deepfake-detection-keras"
    MODEL_PATH: str = "final_deepfake_model.keras"

    # Hugging Face detectors used by app.services.detector
    # Ensemble (geometric mean): v2 = face-deepfake specialist, sdxl = diffusion/general
    # specialist with low false-positive rate on real photos.
    DETECTOR_MODEL_ID: str = "prithivMLmods/Deep-Fake-Detector-v2-Model"
    DETECTOR_ENSEMBLE_ENABLED: bool = True
    DETECTOR_MODEL_ID_SECONDARY: str = "Organika/sdxl-detector"
    # Fourth voter (arbiter tiebreaker): compact independent deepfake ViT
    DETECTOR_QUATERNARY_ENABLED: bool = True
    DETECTOR_MODEL_ID_QUATERNARY: str = "dima806/deepfake_vs_real_image_detection"

    # News misinformation pipeline (screenshot forensics + fact-check)
    NEWS_FACT_CHECK_ENABLED: bool = True
    GOOGLE_FACT_CHECK_API_KEY: str = ""

    # Arabic OCR for the news pipeline. The bundled rapidocr models are
    # zh/en-only; the Arabic recognizer lives in backend/models/ocr (see
    # backend/models/ocr/README.md). Empty paths disable the Arabic pass.
    OCR_ARABIC_ENABLED: bool = True
    OCR_ARABIC_REC_MODEL: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "models", "ocr", "ar_PP-OCRv3_rec.onnx")
    )
    OCR_ARABIC_KEYS: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "models", "ocr", "ar_dict.txt")
    )

    # Sieve scrape API (server-side only).
    # Key is created with scripts/sieve_device_login.py and stored in .env;
    # it grants full account access. Never send it to a browser or a log.
    SIEVE_API_KEY: str = ""
    SIEVE_BASE_URL: str = "https://scrape.usesieve.com"
    # "regular" unless the operator explicitly opts into "conservative"/"yolo".
    SIEVE_COMPLIANCE_MODE: str = "regular"

    # CommFor weight-key remap (m0): the safetensors file stores keys with a
    # single "vit." prefix while the wrapper expects "vit.vit.*". When True
    # (default) keys are remapped at load time; False restores the legacy
    # broken-loading behavior (152 missing keys) for before/after comparison.
    COMMFOR_REMAP_ENABLED: bool = True

    # m3 forensics (all free/local; every optional integration degrades to an
    # honest skipped/error state when unavailable).
    # Optional path to a C2PA trust-anchor file (PEM/list). Empty = trust
    # verification is skipped with an explicit reason on the C2PA card.
    C2PA_TRUST_ANCHORS_PATH: str = ""
    # Local known-forgery hash database (admin-populated; JSON).
    FORGERY_DB_PATH: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "forgery_db.json")
    )
    # Directory of watermark templates (empty -> watermark check = skipped).
    WATERMARK_TEMPLATES_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "watermarks")
    )
    # Decompression-bomb guard: max decoded pixels for any analysis.
    MAX_IMAGE_PIXELS: int = 50_000_000
    
    # Server & Host
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # File Directories
    UPLOAD_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    REPORTS_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    # Durable sieve session records (crash-safe resume; gitignored).
    SIEVE_STATE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "state", "sieve"))
    MAX_UPLOAD_SIZE_MB: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs(settings.SIEVE_STATE_DIR, exist_ok=True)
