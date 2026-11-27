CONFIG_FILE: str = "config.json"
DOCKER_NAMESPACE: str = "pdfix"
DOCKER_REPOSITORY: str = "font-fix-pdfix"
DOCKER_IMAGE: str = f"{DOCKER_NAMESPACE}/{DOCKER_REPOSITORY}"
EASY_OCR: str = "Easy"
RAPID_OCR: str = "Rapid"
TESSERACT_OCR: str = "Tesseract"
SDK_ERROR_INVALID_PASSWORD: int = 34  # PDFix SDK error type of OpenDoc with a missing or wrong password
