import easyocr

# This triggers model download at build time
reader = easyocr.Reader(["en"], download_enabled=True, model_storage_directory="./easyocr_models")
