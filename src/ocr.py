import warnings
from pathlib import Path
from typing import Any

import easyocr
import pytesseract
from rapidocr_onnxruntime import RapidOCR

# To filter out:
# /usr/font-fix/venv/lib/python3.13/site-packages/torch/utils/data/dataloader.py:775:
# UserWarning: 'pin_memory' argument is set as true but no accelerator is found, then device pinned memory won't be
# used.
#   super().__init__(loader)
warnings.filterwarnings("ignore", message=".*pin_memory.*")


class OCR:
    """
    Class that hold all OCR engines.
    """

    def __init__(self, default_character: str) -> None:
        """
        Initialize OCR engines

        Args:
            default_character (str): Which character to use when OCR fails.
        """
        self.default_character: str = default_character
        self.rapidocr: RapidOCR = RapidOCR()
        easy_ocr_models_folder: Path = Path(__file__).parent.parent.joinpath("easyocr_models").resolve()
        # As we are doing OCR over 1 character any advantage of using language words won't help us
        # so we ignore other languages https://github.com/JaidedAI/EasyOCR/tree/master/easyocr/character
        self.easyocr: easyocr.Reader = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=False,
            download_enabled=False,
            model_storage_directory=easy_ocr_models_folder.as_posix(),
        )

    def tesseract_ocr(self, path_to_image: Path) -> str:
        """
        Use Tesseract OCR engine to find out what character is in image.

        Args:
            path_to_image (Path): Path to image with character.

        Returns:
            What character OCR found out.
        """
        try:
            # Using default language as we are doing OCR over 1 character
            result: str = pytesseract.image_to_string(path_to_image.as_posix(), lang="eng", config="--psm 10")
            # Remove new lines
            stripped_result: str = result.strip("\n")
            # Return first character
            return stripped_result[0] if stripped_result != "" else ""
        except Exception:
            print("During Tesseract OCR run, exception happened. Returning default result.")
            return self.default_character

    def rapid_ocr(self, path_to_image: Path) -> str:
        """
        Use Rapid OCR engine to find out what character is in image.

        Args:
            path_to_image (Path): Path to image with character.

        Returns:
            What character OCR found out.
        """
        try:
            # Run OCR
            # self.rapidocr.print_verbose = True # Debug info
            self.rapidocr.text_score = 0.1  # 0.0 debug Include everything, 0.1 filter out total nonsence
            self.rapidocr.use_text_det = False  # Do not cut boxes with text as it is already cut of image
            self.rapidocr.use_angle_cls = False  # Do not try to angle it
            result: Any = self.rapidocr(path_to_image.as_posix())

            # Extract character from result
            output: list[tuple[str, float]] = self._parse_rapid_ocr(result)
            if len(output) > 0:
                return max(output, key=lambda x: x[1])[0]

            return self.default_character
        except Exception:
            print("During Rapid OCR run, exception happened. Returning default result.")
            return self.default_character

    def _parse_rapid_ocr(self, result: Any) -> list[tuple[str, float]]:
        """
        Parse results from Rapid OCR and return them as list of tuples.

        Args:
            result (Any): Can be anything from Rapid OCR.

        Returns:
            List of tuples with character and score. Can be empty list.
        """
        output: list[tuple[str, float]] = []
        if isinstance(result, tuple):
            # First are results, Second are times
            first: Any = result[0]
            if isinstance(first, list):
                # Multiple results
                for member in first:
                    # Result is list containing 1 list (bbox) 2 str (recognised text) 3 float (score)
                    if isinstance(member, list):
                        recognised_text: str = str(member[1]) if len(member) > 1 else ""
                        score: float = float(member[2]) if len(member) > 2 else 0.0
                        output.append((recognised_text, score))
        return output

    def easy_ocr(self, path_to_image: Path) -> str:
        """
        Use Easy OCR engine to find out what character is in image.

        Args:
            path_to_image (Path): Path to image with character.

        Returns:
            What character OCR found out.
        """
        try:
            result: list[str] = self.easyocr.readtext(path_to_image.as_posix(), detail=0)
            if len(result) > 0:
                return result[0]
            return self.default_character
        except Exception:
            print("During Easy OCR run, exception happened. Returning default result.")
            return self.default_character
