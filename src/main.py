import argparse
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

from constants import CONFIG_FILE, EASY_OCR, RAPID_OCR, TESSERACT_OCR
from exceptions import EC_ARG_GENERAL, MESSAGE_ARG_GENERAL, ArgumentInputPdfOutputPdfException, ExpectedException
from fixmissingunicode import FixFontGlyphsUnicodesPdfix
from image_update import DockerImageContainerUpdateChecker


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


def run_fontfixing_subcommand(args) -> None:
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
    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
        fixer: FixFontGlyphsUnicodesPdfix = FixFontGlyphsUnicodesPdfix(
            license_name, license_key, input_path, output_path, engine, default_char
        )
        fixer.fix_missing_unicode()
    else:
        raise ArgumentInputPdfOutputPdfException()


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
        print(e.message, file=sys.stderr)
        sys.exit(e.error_code)
    except SystemExit as e:
        if e.code != 0:
            print(MESSAGE_ARG_GENERAL, file=sys.stderr)
            sys.exit(EC_ARG_GENERAL)
        # This happens when --help is used, exit gracefully
        sys.exit(0)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        print(f"Failed to run the program:{e}", file=sys.stderr)
        sys.exit(9)

    if hasattr(args, "func"):
        # Check for updates only when help is not checked
        update_checker = DockerImageContainerUpdateChecker()
        # Check it in separate thread not to be delayed when there is slow or no internet connection
        update_thread = threading.Thread(target=update_checker.check_for_image_updates)
        update_thread.start()

        # Run subcommand
        try:
            args.func(args)
        except ExpectedException as e:
            print(e.message, file=sys.stderr)
            sys.exit(e.error_code)
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            print(f"Failed to run the program: {e}", file=sys.stderr)
            sys.exit(9)
        finally:
            # Make sure to let update thread finish before exiting
            update_thread.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
