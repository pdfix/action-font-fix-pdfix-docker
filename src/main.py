import argparse
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from constants import CONFIG_FILE, EASY_OCR, RAPID_OCR, TESSERACT_OCR
from exceptions import (
    EC_ARG_GENERAL,
    MESSAGE_ARG_GENERAL,
    ArgumentInputNotPdfException,
    ArgumentOutputExtensionException,
    ArgumentOutputFolderNotExistsException,
    ExpectedException,
)
from fixmissingunicode import FixFontGlyphsUnicodesPdfix
from image_update import DockerImageContainerUpdateChecker
from logger import get_logger

logger: logging.Logger = get_logger("app_logger")


def set_arguments(
    parser: argparse.ArgumentParser, names: list, required_output: bool = True, output_help: str = ""
) -> None:
    """
    Set arguments for the parser based on the provided names and options.

    Args:
        parser (argparse.ArgumentParser): The argument parser to set arguments for.
        names (list): List of argument names to set.
        required_output (bool): Whether the output argument is required. Defaults to True.
        output_help (str): Help for output argument. Defaults to "".
    """
    for name in names:
        match name:
            case "default_char":
                parser.add_argument(
                    "--default_char",
                    type=str,
                    default=" ",
                    help="Which default character should be used when OCR fails.",
                )
            case "engine":
                parser.add_argument(
                    "--engine",
                    type=str,
                    choices=[TESSERACT_OCR, EASY_OCR, RAPID_OCR],
                    default=TESSERACT_OCR,
                    help="Choose which OCR engine will be used.",
                )
            case "key":
                parser.add_argument("--key", type=str, default="", nargs="?", help="PDFix license key")
            case "input":
                parser.add_argument("--input", "-i", type=str, required=True, help="The input PDF file.")
            case "name":
                parser.add_argument("--name", type=str, default="", nargs="?", help="PDFix license name")
            case "output":
                parser.add_argument("--output", "-o", type=str, required=required_output, help=output_help)


def check_output_file(output_path: str) -> None:
    """
    Check the output file extension and that its folder exists before any processing.

    Args:
        output_path (str): Path to the output PDF document.
    """
    if Path(output_path).suffix.lower() != ".pdf":
        raise ArgumentOutputExtensionException()

    output_folder: Path = Path(output_path).resolve().parent
    if not output_folder.is_dir():
        raise ArgumentOutputFolderNotExistsException(output_folder.as_posix())


def check_input_file(input_path: str) -> None:
    """
    Check that the input is an existing PDF file before any processing.

    Args:
        input_path (str): Path to the input PDF document.
    """
    path: Path = Path(input_path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise ArgumentInputNotPdfException(input_path)


def run_config_subcommand(args) -> None:
    get_pdfix_config(args.output)


def get_pdfix_config(path: str) -> None:
    """
    If Path is not provided, output content of config.
    If Path is provided, copy config to destination path.

    Args:
        path (string): Destination path for config.json file
    """
    config_path: Path = Path(__file__).parent.parent.joinpath(CONFIG_FILE).resolve()

    with open(config_path, "r", encoding="utf-8") as file:
        if path is None:
            print(file.read())
        else:
            with open(path, "w") as out:
                out.write(file.read())


# @KA:action pdfix_generate_missing_unicode
# @KA:desc Gives a Unicode value to characters of embedded fonts that have none, so the text can be read by screen
# readers, searched and copied (PDF/UA, clause 7.21.7). Every such character is cut out of the rendered page and
# recognised by OCR, and the recognised character is written into the font, so every use of that character in the
# document gets it. The input file is not changed; the fixed PDF is saved as the output file.
# @KA:context Run on the **whole document** when a PDF/UA validation reports a missing Unicode mapping (7.21.7), or when
# text copied from the PDF is empty or garbled. Check the text afterwards, because OCR of single characters can confuse
# similar characters. Runs locally in Docker and nothing leaves your computer; the first run downloads the image and
# takes longer.
# @KA:param input_pdf
# @KA:desc PDF document to fix. It is only read, never changed.
# @KA:problem "Input file must be an existing PDF document." (error 13)
# @KA:solution The file shown in the message was not found or does not have the `.pdf` extension. Select an existing PDF
# file.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 30" (error 24)
# @KA:solution The file is not a valid PDF. Open and save it again in a PDF editor and run the action again.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 34" (error 24)
# @KA:solution The PDF is password-protected. Remove the password and run the action again.
# @KA:param output_pdf
# @KA:desc Where the fixed PDF is saved, a file with the `.pdf` extension. The folder must already exist; an existing
# file with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be PDF document." (error 11)
# @KA:solution Select an output file with the `.pdf` extension.
# @KA:problem "Output folder does not exist." (error 12)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:problem "Failed to save PDF document." (error 25)
# @KA:solution The fixed PDF could not be written. Check that the output folder is writable and that the file is not
# open in another application.
# @KA:param engine
# @KA:desc OCR engine that recognises the single characters: **Tesseract** (default, fastest start), **Easy** (EasyOCR,
# slower start) or **Rapid** (RapidOCR). All of them recognise English (Latin) characters only. Their results differ;
# for example in tests Tesseract read `e` as `a`, while Easy and Rapid read `l` as `1` and `o` as `0`.
# @KA:problem Recognised characters are wrong, for example `1` instead of `l` or `0` instead of `o`.
# @KA:solution A single character has no surrounding word, so similar characters are confused. Run the action with
# another OCR engine and compare the text, or correct the characters in a PDF editor.
# @KA:param default
# @KA:desc Character written to a character when OCR recognises nothing in any of its places (default: space).
# Characters that draw nothing, like spaces, always get a space without OCR.
# @KA:problem Some characters got the default character.
# @KA:solution OCR could not read them, for example decorative, very small or non-Latin characters. Try another OCR
# engine, or set the characters manually in a PDF editor.
# @KA:logic Which characters are fixed
# @KA:desc Only text in embedded fonts is checked, and only characters with no Unicode value (empty, U+FFFE or U+FEFF).
# Characters that already have a Unicode value are kept, even when the value is wrong. Text in fonts that are not
# embedded, text inside form XObjects (content reused on more pages) and text in annotations is not changed. Fonts with
# the same name in different parts of the document are fixed separately.
# @KA:problem Validation still reports a missing Unicode mapping (7.21.7) after the fix.
# @KA:solution The remaining text uses a font that is not embedded, or it is inside a form XObject or an annotation,
# which the action does not change. Embed the fonts when you create the PDF, or fix these characters in a PDF editor.
# @KA:logic How characters are recognised
# @KA:desc For every character without Unicode, up to 5 of its largest places are cut out of the page rendered at high
# resolution and sent to the OCR engine. The most frequent result is used for all uses of the character. A character
# that draws nothing gets a space without OCR. The log shows every character with its OCR results and the chosen
# character.
# @KA:problem "Failed to render PDF Page into image." (error 23)
# @KA:solution A page cannot be drawn by PDFix SDK. Open and save the PDF again in a PDF editor and run the action
# again.
# @KA:logic What is not done
# @KA:desc The action only adds missing Unicode values. Fonts that are not embedded, `.notdef` glyphs and other font
# problems are not fixed; run **Fix Fonts (Callas)** for them, and validate the document again afterwards.
# @KA:logic PDFix license
# @KA:desc PDFix Desktop passes your PDFix license to the action automatically. Without a license the action runs in
# trial mode, which adds watermarks and may redact random content in the output PDF.
# @KA:problem The output PDF has watermarks or randomly redacted content.
# @KA:solution Trial mode is active. Activate your PDFix license in PDFix Desktop and run the action again.
# @KA:problem "Failed to authorize PDFix SDK account." and the next log line shows "PDFix SDK error 420" (error 22)
# @KA:solution The license name or key is not valid. Check the license in PDFix Desktop settings.
# @KA:problem "Failed to activate PDFix SDK account." and the next log line shows "PDFix SDK error 1205" (error 21)
# @KA:solution The license key is not valid. Check the license in PDFix Desktop settings.
def run_fontfixing_subcommand(args) -> None:
    check_output_file(args.output)
    check_input_file(args.input)
    font_fixing(args.input, args.output, args.name, args.key, args.engine, args.default_char)


def font_fixing(
    input_path: str,
    output_path: str,
    license_name: Optional[str],
    license_key: Optional[str],
    engine: str,
    default_char: str,
) -> None:
    """
    Autotagging PDF document with provided arguments

    Args:
        input_path (str): Path to PDF document.
        output_path (str): Path to PDF document.
        license_name (str): PDFix license name.
        license_key (str): PDFix license key.
        engine (str): Name of OCR enginge.
        default_char (str): Which character to use when OCR fails.
    """
    fixer: FixFontGlyphsUnicodesPdfix = FixFontGlyphsUnicodesPdfix(
        license_name, license_key, input_path, output_path, engine, default_char
    )
    fixer.fix_missing_unicode()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fixing fonts of PDF document",
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    # Config subparser
    config_subparser = subparsers.add_parser(
        "config",
        help="Extract config file for integration",
    )
    set_arguments(
        config_subparser,
        ["output"],
        False,
        "Output to save the config JSON file. Application output is used if not provided.",
    )
    config_subparser.set_defaults(func=run_config_subcommand)

    # Glyph missing unicode fixing subparser
    fontfixing_subparser = subparsers.add_parser(
        "fix-missing-unicode",
        help="Run font fixing (adding unicode to embedded fonts missing glyphs)",
    )
    set_arguments(
        fontfixing_subparser,
        ["name", "key", "input", "output", "engine", "default_char"],
        True,
        "The output PDF file.",
    )
    fontfixing_subparser.set_defaults(func=run_fontfixing_subcommand)

    # Parse arguments
    try:
        args = parser.parse_args()
    except ExpectedException as e:
        logger.error(e.message)
        sys.exit(e.error_code)
    except SystemExit as e:
        if e.code != 0:
            logger.error(MESSAGE_ARG_GENERAL)
            sys.exit(EC_ARG_GENERAL)
        # This happens when --help is used, exit gracefully
        sys.exit(0)
    except Exception as e:
        logger.error("Failed to run the program:")
        logger.exception(e)
        sys.exit(1)

    if hasattr(args, "func"):
        # Check for updates only when help is not checked
        update_checker = DockerImageContainerUpdateChecker()
        # Check it in separate thread not to be delayed when there is slow or no internet connection
        update_thread = threading.Thread(target=update_checker.check_for_image_updates)
        update_thread.start()

        # Measure the time it takes to process the input
        start_time: float = time.time()
        current_time: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.info(f"Processing started at: {current_time}")

        # Run subcommand
        try:
            args.func(args)
        except ExpectedException as e:
            logger.error(e.message)
            if e.sdk_error:
                logger.error(e.sdk_error)
            sys.exit(e.error_code)
        except Exception as e:
            # not expected exception -> print stack trace and what exception happened
            logger.error("Failed to run the program:")
            logger.exception(e)
            sys.exit(1)
        finally:
            elapsed_time: float = time.time() - start_time
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logger.info(f"Processing finished at: {current_time}. Elapsed time: {elapsed_time:.2f} seconds")

            # Make sure to let update thread finish before exiting
            update_thread.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
