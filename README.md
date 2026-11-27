# Font Fix (PDFix)

Fixes font issues where Unicode is missing for glyphs using OCR and the PDFix SDK. Requires a PDFix Desktop license to run.

## Table of Contents

- [Font Fix (PDFix)](#font-fix-pdfix)
  - [Getting started](#getting-started)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Arguments](#arguments)
  - [How it works](#how-it-works)
  - [Exit codes](#exit-codes)
  - [Examples](#examples)
  - [Help \& support](#help--support)
  - [Licenses](#licenses)

## Getting started

You need Docker installed. The first run downloads the image and may take longer than later runs.

## Usage

Mount a folder into the container and run a subcommand:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/font-fix-pdfix:latest <command> [options]
```

## Commands

- `fix-missing-unicode`: Repair missing Unicode mappings in embedded fonts (PDF → PDF)

## Arguments

### `fix-missing-unicode`

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--input`, `-i` | yes | Path to an existing `.pdf` file | Input PDF |
| `--output`, `-o` | yes | Path for the output `.pdf` file | Output PDF |
| `--password` | no | String (default: empty) | Password to open a password-protected PDF |
| `--name` | no | String (PDFix account license name) | PDFix license name |
| `--key` | no | String (PDFix account license key) | PDFix license key |
| `--engine` | no | One of: `Tesseract`, `Easy`, `Rapid` (default: `Tesseract`) | OCR engine |
| `--default_char` | no | Single character string (default: space) | Character when OCR fails |

## How it works

- Every character of an embedded font without a Unicode value is cut out of the rendered page (up to 5 of its largest places), recognized by OCR (`--engine`) and the most frequent result is written into the font.
- Characters that already have a Unicode value, fonts that are not embedded, form XObjects and annotations are not changed; a character OCR cannot read gets `--default_char`.
- **Checks before processing:** output extension (11) and folder (12), input (13), then the PDFix license and opening the PDF (password 30).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected error (`Failed to run the program:` + traceback) |
| 10 | Failed to parse arguments. Please check the usage and try again |
| 11 | Output file must be PDF document |
| 12 | Output folder does not exist |
| 13 | Input file must be an existing PDF document |
| 20 | Failed to initialize PDFix SDK |
| 21 | Failed to activate PDFix SDK account |
| 22 | Failed to authorize PDFix SDK account |
| 23 | Failed to render PDF page into image |
| 24 | Failed to open PDF document |
| 25 | Failed to save PDF document |
| 30 | PDF document is password-protected. Remove the password with another action first |

## Examples

Fix missing Unicode mappings (license recommended to avoid watermarks):

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/font-fix-pdfix:latest \
  fix-missing-unicode --name "${LICENSE_NAME}" --key "${LICENSE_KEY}" \
  -i /data/input.pdf -o /data/output.pdf
```

Use a different OCR engine and fallback character:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/font-fix-pdfix:latest \
  fix-missing-unicode -i /data/input.pdf -o /data/output.pdf \
  --engine Easy --default_char "?"
```

## Help & support

For PDFix SDK licensing or issues, contact `support@pdfix.net`.

## Licenses

- [PDFix Terms](https://pdfix.net/terms)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [RapidOCR](https://github.com/RapidAI/RapidOCR) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)

Trial versions of the PDFix SDK may apply watermarks and redact random content in the output PDF.

