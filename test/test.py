# To run this use "python3 test.py"
# This for testing font fixing app on set of PDFs and verifying results.

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

verbose: bool = len(sys.argv) > 2 and "-v" in sys.argv

logger: logging.Logger = logging.getLogger("Testing Font Fixing")

logger.setLevel(logging.DEBUG)

console_handler: logging.StreamHandler = logging.StreamHandler()
level = logging.INFO if verbose else logging.WARNING
console_handler.setLevel(level)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)


def get_list_of_pdfs(directory: Path) -> list[Path]:
    pdf_files: list[Path] = []
    for path in directory.rglob("*.pdf"):
        if path.is_file():
            pdf_files.append(path)
    return pdf_files


def create_command_list(cli: str, temp_folder: Path, input_name: str, output_name: str) -> list[str]:
    command_list: list[str] = cli.split(" ")

    for index, cmd in enumerate(command_list):
        if "${working_directory}" in cmd:
            command_list[index] = cmd.replace("${working_directory}", str(temp_folder))
        if "${input}" in cmd:
            command_list[index] = cmd.replace("${input}", input_name)
        if "${output}" in cmd:
            command_list[index] = cmd.replace("${output}", output_name)

    return command_list


def run_command(command_list: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    logger.debug("Running command:")
    for arg in command_list:
        logger.debug(f"  Arg: {arg}")
    result: subprocess.CompletedProcess[str] = subprocess.run(
        command_list, cwd=cwd, capture_output=True, check=False, text=True
    )

    return result


def clean_up(paths: list[Path]) -> None:
    for path in paths:
        if path.exists():
            os.remove(path)


def debug_print_directory_contents(directory: Path) -> None:
    logger.debug(f"Contents of {directory}:")
    logger.debug("- NAME - SIZE - RIGHTS")
    for path in directory.iterdir():
        stat_result: os.stat_result = path.stat()
        stat_result.st_size
        logger.debug(f"- {path.name} - {stat_result.st_size} - {oct(stat_result.st_mode)[-3:]}")


def craft_process_message(result: subprocess.CompletedProcess[str], process_name: str, spaces: int = 2) -> str:
    message: str = f"\n{process_name} ({result.returncode}):"
    if result.stdout.strip() != "":
        message += f"\n{process_name} STDOUT:"
        message += f"\n{result.stdout}"
    if result.stderr.strip() != "":
        message += f"\n{process_name} STDERR:"
        message += f"\n{result.stderr}"
    return add_spaces_to_each_line(message, spaces)


def add_spaces_to_each_line(text: str, spaces: int) -> str:
    space_str: str = " " * spaces
    return text.replace("\n", f"\n{space_str}")


def info_verification_message(
    input_verification: subprocess.CompletedProcess[str], output_verification: subprocess.CompletedProcess[str]
) -> None:
    message: str = "  VERIFICATIONS:"
    message += craft_process_message(input_verification, "VERIFICATION INPUT")
    message += craft_process_message(output_verification, "VERIFICATION OUTPUT")
    logger.info(message)


def get_accepted_return_codes(this_project_path: Path) -> list[int]:
    config_json_path: Path = this_project_path.joinpath("config.json").resolve()
    with open(config_json_path, "r", encoding="utf-8") as file:
        config_data: dict[str, Any] = json.load(file)
        actions_data: list[dict[str, Any]] = config_data["actions"]
        accepted_codes: list[int] = actions_data[0]["returnCodes"]
        return accepted_codes


def copy_file(file_path: Path, folder_path: Path) -> None:
    destination_path: Path = folder_path.joinpath(file_path.name).resolve()
    with (
        open(file_path, "r", encoding="utf-8") as source_file,
        open(destination_path, "w", encoding="utf-8") as destination_file,
    ):
        logger.debug(f"{file_path}:")
        content: str = source_file.read()
        logger.debug(content)
        destination_file.write(content)

    destination_path.chmod(0o666)

    with open(destination_path, "r", encoding="utf-8") as destination_file:
        logger.debug(f"{destination_path}:")
        logger.debug(destination_file.read())


def extract_rules(html_page: list[str]) -> dict[str, tuple[str, int]]:
    rules: dict[str, tuple[str, int]] = {}
    parse_rules: bool = False
    failed_message: str = ""
    occurences: int = -1
    for line in html_page:
        if not parse_rules and 'id="table3"' in line:
            parse_rules = True
            continue

        if parse_rules:
            if "<b>Failed</b>" in line:
                # line example:
                #                     <td width="800">Xref streams shall not be used</td>
                # <td width="50"><b><font color="red"><b>Failed</b></font></b></td>
                failed_message = line.split(">")[1].split("<")[0]
            if "occurrences" in line:
                # line example:
                #                     <td width="800">1 occurrences
                occurences = int(line.split(">")[1].split(" ")[0])

            if occurences > 0 and failed_message != "":
                hash: str = hashlib.md5(failed_message.encode("utf-8")).hexdigest()
                rules[hash] = (failed_message, occurences)
                failed_message = ""
                occurences = -1

            if "</table>" in line:
                parse_rules = False

    return rules


def craft_summary_of_verification(output_html: Path) -> str:
    message: str = "Verification errors:"

    try:
        with open(output_html, "r") as output_file:
            output_rules: dict[str, tuple[str, int]] = extract_rules(output_file.readlines())
    except Exception:
        return message

    for value in output_rules.values():
        message += f'\n  - RULE [{value[1]}time(s)]: "{value[0]}"'

    return message


# Get config
image_name: str = "font-fix-pdfix:test"
build_cli: str = "docker build -t font-fix-pdfix:test ."
cli: str = "docker run --rm -v ${working_directory}:/data -w /data font-fix-pdfix:test"
cli += " fix-missing-unicode -i /data/${input} -o /data/${output}"
verification_cli: str = "docker run -v ${working_directory}:/data --rm pdfix/validate-pdf-verapdf:v0.4.10"
verification_cli += " validate --format html --profile /data/font_profiles.xml"
verification_cli += " --input /data/${input} --output /data/${output}"

# Check .env
test_folder: Path = Path(__file__).parent
this_project_path: Path = test_folder.parent
example_path: Path = this_project_path.joinpath("examples")
projects_path: Path = this_project_path.parent
error_output_folder: Path = test_folder.joinpath("output")
error_output_folder.mkdir(exist_ok=True)
accepted_return_codes: list[int] = [0]

# Build docker image for testing
build_result: subprocess.CompletedProcess[str] = run_command(build_cli.split(" "), this_project_path)

if build_result.returncode != 0:
    logger.error("Failed to build docker image.")
    logger.debug(craft_process_message(build_result, "BUILD DOCKER IMAGE"))
    sys.exit(1)

# Go through files
count: int = 0
passed: int = 0
failed: list[str] = []

# Create temp directory
with tempfile.TemporaryDirectory() as temp_dir:
    temp_folder: Path = Path(temp_dir).resolve()

    # Copy profile
    profile_path: Path = test_folder.joinpath("font_profiles.xml").resolve()
    if profile_path.exists():
        copy_file(profile_path, temp_folder)

    # For each file:
    for pdf_path in get_list_of_pdfs(example_path):
        logger.debug(f"Processing {pdf_path}:")
        count += 1

        # if count > 50:
        #     break

        # Copy input + make output name
        temp_input: Path = temp_folder.joinpath(pdf_path.name).resolve()
        shutil.copy(pdf_path, temp_input)

        # Fill commands
        output_pdf_name: str = f"{pdf_path.stem}_fixed.pdf"
        output_pdf_path: Path = temp_folder.joinpath(output_pdf_name).resolve()
        command_list: list[str] = create_command_list(cli, temp_folder, pdf_path.name, output_pdf_name)

        output_html_name: str = f"{pdf_path.stem}_fixed_verified.html"
        output_html_path: Path = temp_folder.joinpath(output_html_name).resolve()
        verification_output_list: list[str] = create_command_list(
            verification_cli, temp_folder, output_pdf_name, output_html_name
        )

        files_to_remove: list[Path] = [output_html_path, output_pdf_path, temp_input]

        # Run Fix
        cli_result: subprocess.CompletedProcess[str] = run_command(command_list, temp_folder)

        if cli_result.returncode == 0:
            logger.debug(f"{pdf_path.name}: Command ran successfully ({cli_result.returncode}).")
        else:
            message: str = f"Check: {pdf_path.as_posix()}{craft_process_message(cli_result, 'COMMAND')}"
            logger.warning(f"❌ {pdf_path.name}: Failed command ({cli_result.returncode}). No verification run.")
            logger.info(message)
            failed.append(pdf_path.name)
            clean_up(files_to_remove)
            continue

        # Run verifications
        verification_output_result: subprocess.CompletedProcess[str] = run_command(
            verification_output_list, temp_folder
        )
        logger.debug(f"{pdf_path.name}: Verification on output ran {verification_output_result.returncode}.")

        # Print results
        is_passed = verification_output_result.returncode == 0

        if is_passed:
            logger.warning(f"✅ {pdf_path.name}: Passed ({cli_result.returncode}).")
        else:
            summary: str = craft_summary_of_verification(output_html_path)
            logger.warning(f"❌ {pdf_path.name}: Command ({cli_result.returncode}). Failed verification. {summary}")
            failed.append(pdf_path.name)
            clean_up(files_to_remove)
            continue

        passed += 1

        # Clean-up
        clean_up(files_to_remove)

    logger.error(f"Statistics {passed}/{count} (passed/total)")
    logger.error(f"Failed files:\n{'\n'.join(failed)}")
