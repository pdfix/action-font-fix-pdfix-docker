# Font Fix (PDFix)

Fixes font issues where Unicode is missing for glyphs using OCR and the PDFix SDK. Requires a PDFix Desktop license to run.

## Table of Contents

- [Font Fix (PDFix)](#font-fix-pdfix)
  - [Getting started](#getting-started)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Arguments](#arguments)
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
| `--name` | no | String (PDFix account license name) | PDFix license name |
| `--key` | no | String (PDFix account license key) | PDFix license key |
| `--engine` | no | One of: `Tesseract`, `Easy`, `Rapid` (default: `Tesseract`) | OCR engine |
| `--default_char` | no | Single character string (default: space) | Character when OCR fails |

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

Trial versions of the PDFix SDK may apply watermarks and redact random content in the output PDF.
