# Font Fixing Using PDFix SDK

A Docker image that fixes missing glyph unicodes in embedded fonts in PDF document.

## Table of Contents

- [Font Fixing Using PDFix SDK](#font-fixing-using-pdfix-sdk)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Run a Docker Container ](#run-docker-container)
    - [Run Docker Container for Font Fixing](#run-docker-container-for-font-fixing)
      - [Return codes](#return-codes)
    - [Exporting Configuration for Integration](#exporting-configuration-for-integration)
  - [License](#license)
  - [Help \& Support](#help--support)

## Getting Started

To use this Docker application, you'll need to have Docker installed on your system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.

## Run a Docker Container

The first run will pull the docker image, which may take some time. Make your own image for more advanced use.

### Run Docker Container for Font Fixing

To run docker container as CLI you should share the folder with PDF to process using `-v` parameter. In this example it's current folder.

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/font-fix-pdfix:latest fix-missing-unicode -i /data/input.pdf -o /data/output.pdf
```

If you want to use other OCR engine then default Tesseract OCR use parameter `--engine` with one of values `Easy` for Easy OCR or `Rapid` for Rapid OCR.
If you want to fill other then space character when OCR fails to recognize character you can set it using parameter `--default_char` followed by your desired character.

For more detailed information about the available command-line arguments, you can run the following command:

```bash
docker run --rm pdfix/font-fix-pdfix:latest --help
```

### Exporting Configuration for Integration

To export the configuration JSON file, use the following command:

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/font-fix-pdfix:latest config -o config.json
```

## License

- [PDFix SDK](https://pdfix.net/terms)

## Help & Support

To report an issue please contact us at support@pdfix.net.
For more information visit https://pdfix.net
