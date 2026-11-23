# Use the official Debian slim image as a base
FROM debian:stable-slim

# Update system and Install python3
RUN apt-get update && \
    apt-get install -y \
    libgl1 \
    # Only English is used for OCR of single characters
    tesseract-ocr \
    tesseract-ocr-eng \
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/font-fix/

# Create a virtual environment and install dependencies
ENV VIRTUAL_ENV=venv
RUN python3 -m venv venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt /usr/font-fix/
RUN pip install --no-cache-dir -r requirements.txt

# COPY easy OCR model files
COPY easyocr_models/ /usr/font-fix/easyocr_models

# Copy config and source codes
COPY config.json /usr/font-fix/
COPY src/ /usr/font-fix/src/

# Debug use "-u" for unbuffered console output (if segmentation fault happens)
# ENTRYPOINT ["/usr/font-fix/venv/bin/python3", "-u", "/usr/font-fix/src/main.py"]

# License
COPY THIRD_PARTY_LICENSES.md /THIRD_PARTY_LICENSES.md
LABEL license="https://pdfix.net/terms (PDFix SDK) and Apache-2.0 (Tesseract / EasyOCR / RapidOCR)"

ENTRYPOINT ["/usr/font-fix/venv/bin/python3", "/usr/font-fix/src/main.py"]
