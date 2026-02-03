import os
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional, cast

from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    PdfFont,
    Pdfix,
    PdfPage,
    PdfRect,
    PdfTextState,
    PdsContent,
    PdsPageObject,
    PdsText,
    kPdsPageText,
    kSaveFull,
)

from constants import EASY_OCR, RAPID_OCR, TESSERACT_OCR
from exceptions import PdfixFailedToOpenException, PdfixFailedToSaveException, PdfixInitializeException
from ocr import OCR
from page_render import crop_image, render_page
from utils_sdk import authorize_sdk, get_latest_sdk_error


class CharLocation:
    """
    Class containing information where character in document is located.
    """

    def __init__(self, page_index: int, bbox: PdfRect) -> None:
        """
        Constructor for character location in PDF document. Calculate height of BBox of character.

        Args:
            page_index (int): Page index that character is on.
            bbox (PdfRect): Bounding Box inside Page where it is located.
        """
        self.page_index: int = page_index
        self.bbox: PdfRect = bbox
        self.height: float = self._get_height()

    def _get_height(self) -> float:
        """
        Calculates heigh of BBox of character.
        """
        return abs(self.bbox.top - self.bbox.bottom)

    def str(self) -> str:
        bbox_area: tuple[int, int, int, int] = (self.bbox.left, self.bbox.top, self.bbox.right, self.bbox.bottom)
        return f"Location: Page: {self.page_index + 1}, BBox: {bbox_area}, Height: {self.height}"


class MissingGlyph:
    """
    Class containing all info about embedded font glyph that has missing unicode.
    """

    def __init__(self, font: PdfFont, char_code: int) -> None:
        """
        Constructor for missing glyph information. Creates unique key.

        Args:
            font (PdfFont): Embedded font that has missing glyph.
            char_code (int): Code of missing glyph.
        """
        self.font: PdfFont = font
        self.char_code: int = char_code
        self.locations: list[CharLocation] = []
        self.key: str = f"{font.GetFontName()}{char_code}"

    def add_location(self, location: CharLocation) -> None:
        """
        Add location where font glyph is used in dokument.

        Args:
            location (CharLocation): All info about location.
        """
        self.locations.append(location)

    def str(self) -> str:
        output: str = f"Missing Glyph: Font: {self.font.GetFontName()}, Char Code: {self.char_code}\n  "
        output += "\n  ".join(location.str() for location in self.locations)
        return output


class FixFontGlyphsUnicodesPdfix:
    """
    Class that process PDF document and assigns unicode to missing embedded font glyphs.
    """

    EASY_OCR: str = EASY_OCR
    RAPID_OCR: str = RAPID_OCR
    TESSERACT_OCR: str = TESSERACT_OCR

    def __init__(
        self,
        license_name: Optional[str],
        license_key: Optional[str],
        input_path: str,
        output_path: str,
        engine: str,
        default_character: str,
    ) -> None:
        """
        Initialize class for fixing fonts.

        Args:
            license_name (Optional[str]): Pdfix SDK license name (e-mail).
            license_key (Optional[str]): Pdfix SDK license key.
            input_path (str): Path to PDF document.
            output_path (str): Path where fixed PDF should be saved.
            engine (str): Name of OCR enginge.
            default_character (str): Which character to use when OCR fails.
        """
        self.license_name: Optional[str] = license_name
        self.license_key: Optional[str] = license_key
        self.input_file_str_path: str = input_path
        self.output_file_str_path: str = output_path
        self.engine: str = engine
        self.default_character: str = default_character
        self.cached_renders: dict[int, Path] = {}
        # self.font_info: dict[str, tuple[PdfFont, set[int]]] = {}

    def fix_missing_unicode(self) -> None:
        """
        Goes through whole PDF document and searches for all used Embedded fonts glyphs if they have unicode value.
        If they don't it cuts part of PDF page and uses OCR to find out what is that character and saves it into
        embedded font information.
        """
        pdfix: Optional[Pdfix] = GetPdfix()
        if pdfix is None:
            raise PdfixInitializeException()

        try:
            # Try to authorize PDFix SDK
            authorize_sdk(pdfix, self.license_name, self.license_key)

            # Open the document
            doc: Optional[PdfDoc] = pdfix.OpenDoc(self.input_file_str_path, "")
            if doc is None:
                raise PdfixFailedToOpenException(pdfix, self.input_file_str_path)

            try:
                # Fix missing unicodes in the embedded fonts from the document
                missing_glyphs: dict[str, MissingGlyph] = self._gather_all_missing_occurences(pdfix, doc)
                # self._debug_all_fonts_info(missing_glyphs)
                self._process_all_missing_occurences(pdfix, doc, missing_glyphs)
                self._clean_up_rendered_pages()

                # Save the processed document
                if not doc.Save(self.output_file_str_path, kSaveFull):
                    raise PdfixFailedToSaveException(pdfix, self.output_file_str_path)
            finally:
                doc.Close()
        finally:
            pdfix.Destroy()

    def _gather_all_missing_occurences(self, pdfix: Pdfix, doc: PdfDoc) -> dict[str, MissingGlyph]:
        """
        Goes though text on all PDF pages of PDF document and gather all occurences where emebedded font is missing
        glyph unicode and at which places.

        Args:
            pdfix (Pdfix): SDK to be able to call API.
            doc (PdfDoc): Opened PDF document.

        Returns:
            Dictionary containing all missing glyphs.
        """
        missing_glyphs: dict[str, MissingGlyph] = {}
        page_count: int = doc.GetNumPages()

        for page_index in range(page_count):
            page: Optional[PdfPage] = doc.AcquirePage(page_index)

            if page is None:
                sdk_error: str = get_latest_sdk_error(pdfix)
                print(f"Failed to open page {page_index + 1}: {sdk_error}")
                continue

            try:
                # Get Page Content
                content: Optional[PdsContent] = page.GetContent()

                if content is None:
                    sdk_error = get_latest_sdk_error(pdfix)
                    print(f"Failed to get content from PDF page: {sdk_error}")
                    continue

                # Walk Objects in Content
                num_objects: int = content.GetNumObjects()

                for obj_index in range(num_objects):
                    obj: Optional[PdsPageObject] = content.GetObject(obj_index)

                    if obj is None:
                        sdk_error = get_latest_sdk_error(pdfix)
                        print(f"Failed to obtain {obj_index + 1}. object: {sdk_error}")
                        continue

                    # We are interested only in Text Objects
                    if obj.GetObjectType() == kPdsPageText:
                        text: PdsText = PdsText(obj.obj)
                        state: PdfTextState = text.GetTextState()
                        font: Optional[PdfFont] = state.font
                        if font is None or not font.GetEmbedded():
                            # We are not interested in not embedded fonts
                            continue

                        # Walk characters of text object
                        num_chars: int = text.GetNumChars()

                        for char_index in range(num_chars):
                            char_code: int = text.GetCharCode(char_index)
                            char_text: str = text.GetCharText(char_index)
                            # self._add_info(font, char_code)
                            if not self._should_char_be_ocr(char_text):
                                # Glyph has unicode assigned, go to next character
                                continue

                            bbox: PdfRect = text.GetCharBBox(char_index)
                            glyph_info: MissingGlyph = MissingGlyph(font, char_code)
                            location: CharLocation = CharLocation(page_index, bbox)
                            dictionary_key: str = glyph_info.key
                            if dictionary_key not in missing_glyphs:
                                missing_glyphs[dictionary_key] = glyph_info

                            missing_glyphs[dictionary_key].add_location(location)
            finally:
                page.Release()

        return missing_glyphs

    def _should_char_be_ocr(self, character: str) -> bool:
        """
        Decide if character should go to OCR engine.

        Args:
            character (str): Character in question.

        Returns:
            True if character should be OCR, False otherwise.
        """
        # number: int = ord(character) if character != "" else -1
        # unicode_str: str = f"U+{ord(character):04X}" if number >= 0 else "-1"

        # print(f"Found character: '{character}' number: {number} with unicode: {unicode_str}")

        if character == "":
            return True

        number: int = ord(character)

        # U+FFFE is 65534, U+FEFF is 65279
        if number in {65534, 65279}:
            return True

        return False

    def _process_all_missing_occurences(
        self, pdfix: Pdfix, doc: PdfDoc, missing_glyphs: dict[str, MissingGlyph]
    ) -> None:
        """
        Go through all missing glyphs and for each makes couple of images and tries to OCR them. Also assigns all
        successfull OCRs.

        Args:
            pdfix (Pdfix): Pdfix SDK.
            doc (PdfDoc): Opened PDF document.
            missing_glyphs (dict[str, MissingGlyph]): Dictionary containing all missing glyphs for processing.
        """
        ocr: OCR = OCR(self.default_character)

        for value in missing_glyphs.values():
            locations: list[CharLocation] = value.locations
            locations.sort(key=lambda x: x.height, reverse=True)
            # print(value.str())
            new_char: str = self._ocr_missing_glyph(pdfix, doc, locations, ocr, value)
            if not value.font.SetUnicodeForCharcode(value.char_code, new_char):
                sdk_error = get_latest_sdk_error(pdfix)
                print(f"Failed to set {new_char} to charcode {value.char_code}: {sdk_error}")

    def _ocr_missing_glyph(
        self, pdfix: Pdfix, doc: PdfDoc, locations: list[CharLocation], ocr: OCR, missing_glyph: MissingGlyph
    ) -> str:
        """
        Goes through top 5 (biggest height) locations of glyph in document and renders them, sends them to OCR, takes
        most probable character value and returns it.

        Args:
            pdfix (Pdfix): Pdfix SDK.
            doc (PdfDoc): Opened PDF document.
            locations (list[CharLocation]): List of locations of character.
            ocr (OCR): OCR engines.
            missing_glyph (MissingGlyph): Information about font and which character is being OCR.
        """
        max_count: int = 5
        results: list[str] = []
        count: int = 0
        for location in locations:
            count += 1
            if count > max_count:
                break

            page: Optional[PdfPage] = doc.AcquirePage(location.page_index)

            if page is None:
                sdk_error: str = get_latest_sdk_error(pdfix)
                print(f"Failed to open page {location.page_index + 1}: {sdk_error}")
                continue

            try:
                # Get page image
                page_image: Path = self._get_pdf_page_render(pdfix, location.page_index, page)

                with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
                    tmp_path: Path = Path(tmp.name)
                    bbox: PdfRect = self._increase_bbox(location.bbox, 2)

                    # Crop it
                    crop_image(page_image, tmp_path, pdfix, page, bbox)

                    # # For debugging purposes copy temporary image file to outside to study how the cut outs look like
                    # local_file: Path = Path(f"/data/temp_image{tmp_path.stem}.jpg")
                    # print(f"Copy {tmp_path} -> {local_file}")
                    # shutil.copy(tmp_path, local_file)  # for debugging

                    result: str = self._ocr_character(tmp_path, ocr)

                    if result:
                        results.append(result)
            finally:
                page.Release()

        if len(results) == 0:
            return self.default_character

        char_result: str = max(results, key=results.count)
        font_name: str = missing_glyph.font.GetFontName()
        char_code: int = missing_glyph.char_code
        # print(f"OCR Results: {results} -> {char_result} (Chosen character)")
        # print(f"Setting '{char_result}' to {font_name} char_code: {char_code}")
        print(
            f"From OCR results: {char_result} character: '{results}' was chosen"
            + f" for font: '{font_name}' at place {char_code} (char_code)."
        )
        return char_result

    def _get_pdf_page_render(self, pdfix: Pdfix, page_index: int, page: PdfPage) -> Path:
        """
        Return path to rendered PDF Page. Either from cache or create it and add it to cache.

        Args:
            pdfix (Pdfix): Pdfix SDK.
            page_index (int): Which page to render.
            page (PdfPage): Opened PDF Page that will be rendered.

        Returns:
            Path to rendered image.
        """
        if page_index in self.cached_renders:
            return self.cached_renders[page_index]

        with tempfile.NamedTemporaryFile(suffix=".jpg", prefix=f"Page{page_index + 1}", delete=False) as tmp:
            render_page(pdfix, page, cast(BinaryIO, tmp))
            temp_path: Path = Path(tmp.name)
            self.cached_renders[page_index] = temp_path
            return temp_path

    def _increase_bbox(self, bbox: PdfRect, increase_by: int) -> PdfRect:
        """
        Takes bbox from PDF page and increases it by x points in each direction.

        Args:
            bbox (PdfRect): Original bounding box.
            increase_by (int): How many points/pixel to add at each side.

        Returns:
            Already increased bounding box.
        """
        if bbox.bottom < bbox.top:
            bbox.left -= increase_by
            bbox.right += increase_by
            bbox.top += increase_by
            bbox.bottom -= increase_by
        else:
            bbox.left -= increase_by
            bbox.right += increase_by
            bbox.top -= increase_by
            bbox.bottom += increase_by
        return bbox

    def _ocr_character(self, image_path: Path, ocr: OCR) -> str:
        """
        Render cut of PDF page into temporary image file. Sends this file to OCR engine.

        Args:
            image_path (Path): Path to image file with character.
            ocr (OCR): Initialized OCR engine.

        Returns:
            Character that OCR engine recognised.
        """
        result: str = ""
        match self.engine:
            case self.EASY_OCR:
                result = ocr.easy_ocr(image_path)
            case self.RAPID_OCR:
                result = ocr.rapid_ocr(image_path)
            case self.TESSERACT_OCR:
                result = ocr.tesseract_ocr(image_path)

        # Fallback does not bring more functionality so it will stay disabled
        # if result == "":
        #     print("FALLBACK")
        #     # Fallback
        #     tesseract_result: str = ocr.tesseract_ocr(image_path) if self.engine == self.TESSERACT_OCR else ""
        #     easy_result: str = ocr.easy_ocr(image_path) if self.engine == self.EASY_OCR else ""
        #     rapid_result: str = ocr.rapid_ocr(image_path) if self.engine == self.RAPID_OCR else ""
        #     print(f"OCR: tesseract: '{tesseract_result}' easy: '{easy_result}' rapid: '{rapid_result}'")

        #     if tesseract_result != "" and tesseract_result != " ":
        #         print(f"Fallbacked from {self.engine} to Tesseract. New result: '{tesseract_result}'")
        #         result = tesseract_result
        #     elif easy_result != "" and easy_result != " ":
        #         print(f"Fallbacked from {self.engine} to Easy. New result: '{easy_result}'")
        #         result = easy_result
        #     elif rapid_result != "" and rapid_result != " ":
        #         print(f"Fallbacked from {self.engine} to Rapid. New result: '{rapid_result}'")
        #         result = rapid_result

        return result

    def _clean_up_rendered_pages(self) -> None:
        """
        Removes all cached rendered PDF Pages.
        """
        for value in self.cached_renders.values():
            os.remove(value)

    # def _add_info(self, font: PdfFont, char_code: int) -> None:
    #     name: str = font.GetFontName()

    #     if name in self.font_info:
    #         self.font_info[name][1].add(char_code)
    #     else:
    #         self.font_info[name] = (font, {char_code})

    # def _debug_all_fonts_info(self, missing_glyphs: dict[str, MissingGlyph]) -> None:
    #     for font_name, data in self.font_info.items():
    #         font: PdfFont = data[0]
    #         char_codes: set[int] = data[1]
    #         for char_code in char_codes:
    #             key: str = f"{font_name}{char_code}"
    #             character: str = font.GetUnicodeFromCharcode(char_code)
    #             is_missing: bool = key in missing_glyphs
    #             print(f"{font_name} - {char_code} - '{character}' - Missing: {is_missing}")
