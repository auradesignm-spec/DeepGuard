# Arabic OCR models (news misinformation pipeline)

The bundled `rapidocr-onnxruntime` models are Chinese/English only. These
files add Arabic recognition (PP-OCRv3 arabic rec, Apache-2.0, converted to
ONNX):

- `ar_PP-OCRv3_rec.onnx` (~8.6 MB) - text recognition model
- `ar_dict.txt` - the character dictionary CTC decoding needs

Source: `monkt/paddleocr-onnx` on Hugging Face (`languages/arabic/`).
Detection and angle-classification still use the models bundled with
rapidocr-onnxruntime.

These model files are gitignored (like every other weight in this repo).
Re-download them with:

```bash
python -c "from huggingface_hub import hf_hub_download; import shutil, os; dst=r'backend/models/ocr'; os.makedirs(dst, exist_ok=True); [shutil.copy(hf_hub_download('monkt/paddleocr-onnx', f), os.path.join(dst, os.path.basename(f))) for f in ('languages/arabic/rec.onnx','languages/arabic/dict.txt')]"
```

Settings in `backend/app/config.py`: `OCR_ARABIC_ENABLED` (default true),
`OCR_ARABIC_REC_MODEL`, `OCR_ARABIC_KEYS`. When the files are missing the
pipeline logs one info line and falls back to the zh/en recognizer (the old,
broken-Arabic behavior) instead of failing.
