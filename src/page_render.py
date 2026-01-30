from pathlib import Path
from typing import BinaryIO, Optional

from pdfixsdk import (
    PdfDevRect,
    PdfImageParams,
    Pdfix,
    PdfPage,
    PdfPageRenderParams,
    PdfPageView,
    PdfRect,
    PsFileStream,
    PsImage,
    kImageDIBFormatArgb,
    kImageFormatJpg,
    kPsTruncate,
    kRotate0,
)
from PIL import Image, ImageFile, ImageOps

from exceptions import PdfixFailedToRenderException

ZOOM: float = 4.0


def render_bbox(pdfix: Pdfix, page: PdfPage, bbox: PdfRect, temporary_file: BinaryIO) -> None:
    """
    Render part of PDF document page to file.

    Args:
        pdfix (Pdfix): Pdfix SDK.
        page (PdfPage): Opened PDF page.
        bbox (PdfRect): The bounding box of the page to render.
        temporary_file (BinaryIO): Temporary file for saving image.
    """
    page_view: Optional[PdfPageView] = page.AcquirePageView(ZOOM, kRotate0)
    if page_view is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to acquire page view")

    try:
        rect: PdfDevRect = page_view.RectToDevice(bbox)

        # Render bbox to image
        render_parameters: PdfPageRenderParams = PdfPageRenderParams()
        render_parameters.matrix = page_view.GetDeviceMatrix()
        render_parameters.clip_box = bbox
        ps_image: Optional[PsImage] = pdfix.CreateImage(
            rect.right - rect.left,
            rect.bottom - rect.top,
            kImageDIBFormatArgb,
        )
        if ps_image is None:
            raise PdfixFailedToRenderException(pdfix, "Unable to create the image")

        render_parameters.image = ps_image

        try:
            if not page.DrawContent(render_parameters):
                raise PdfixFailedToRenderException(pdfix, "Unable to draw the content")

            # Save image to file
            file_stream: Optional[PsFileStream] = pdfix.CreateFileStream(temporary_file.name, kPsTruncate)
            if file_stream is None:
                raise PdfixFailedToRenderException(pdfix, "Unable to create file stream")

            try:
                img_params: PdfImageParams = PdfImageParams()
                img_params.format = kImageFormatJpg
                img_params.quality = 100

                if not ps_image.SaveToStream(file_stream, img_params):
                    raise PdfixFailedToRenderException(pdfix, "Unable to save image to stream")
            except Exception:
                raise
            finally:
                file_stream.Destroy()
        except Exception:
            raise
        finally:
            render_parameters.image.Destroy()
    except Exception:
        raise
    finally:
        page_view.Release()


def render_page(pdfix: Pdfix, page: PdfPage, temporary_file: BinaryIO) -> None:
    """
    Render part of PDF document page to file.

    Args:
        pdfix (Pdfix): Pdfix SDK.
        page (PdfPage): Opened PDF page.
        bbox (PdfRect): The bounding box of the page to render.
        temporary_file (BinaryIO): Temporary file for saving image.
    """
    page_view: Optional[PdfPageView] = page.AcquirePageView(ZOOM, kRotate0)
    if page_view is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to acquire page view")

    try:
        # Get the dimensions of the page view (device width and height)
        page_width = page_view.GetDeviceWidth()
        page_height = page_view.GetDeviceHeight()

        # Render bbox to image
        render_parameters: PdfPageRenderParams = PdfPageRenderParams()
        render_parameters.matrix = page_view.GetDeviceMatrix()
        ps_image: Optional[PsImage] = pdfix.CreateImage(page_width, page_height, kImageDIBFormatArgb)
        if ps_image is None:
            raise PdfixFailedToRenderException(pdfix, "Unable to create the image")

        render_parameters.image = ps_image

        try:
            if not page.DrawContent(render_parameters):
                raise PdfixFailedToRenderException(pdfix, "Unable to draw the content")

            # Save image to file
            file_stream: Optional[PsFileStream] = pdfix.CreateFileStream(temporary_file.name, kPsTruncate)
            if file_stream is None:
                raise PdfixFailedToRenderException(pdfix, "Unable to create file stream")

            try:
                img_params: PdfImageParams = PdfImageParams()
                img_params.format = kImageFormatJpg
                img_params.quality = 100

                if not ps_image.SaveToStream(file_stream, img_params):
                    raise PdfixFailedToRenderException(pdfix, "Unable to save image to stream")
            except Exception:
                raise
            finally:
                file_stream.Destroy()
        except Exception:
            raise
        finally:
            render_parameters.image.Destroy()
    except Exception:
        raise
    finally:
        page_view.Release()


def crop_image(input_image: Path, output_image: Path, pdfix: Pdfix, page: PdfPage, bbox: PdfRect) -> None:
    """
    Crops input image according to bbox and puts it into output image.

    Args:
        input_image (Path): Path to input image file.
        output_image (Path): Path to output image file.
        pdfix (Pdfix): Pdfix SDK.
        page (PdfPage): Opened PDF page.
        bbox (PdfRect): Bounding box inside that page.
    """
    page_view: Optional[PdfPageView] = page.AcquirePageView(ZOOM, kRotate0)
    if page_view is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to acquire page view")

    try:
        rect: PdfDevRect = page_view.RectToDevice(bbox)
        image_file: ImageFile.ImageFile = Image.open(input_image)
        area: tuple[float, float, float, float] = (rect.left, rect.top, rect.right, rect.bottom)
        image: Image.Image = image_file.crop(area)
        image.save(output_image, format="JPEG", quality=100, subsampling=0)

    except Exception:
        raise
    finally:
        page_view.Release()


def make_monochrome(image_path: Path) -> None:
    """
    Transform image into black and while image.

    Args:
        image_path (Path): Path to image file.
    """
    # Open the image
    image: ImageFile.ImageFile = Image.open(image_path)

    # Convert to grayscale (L mode)
    grayscale: Image.Image = image.convert("L")
    threshold: int = 128
    black_white: Image.Image = grayscale.point(lambda x: 255 if x >= threshold else 0)
    black_white = ImageOps.invert(black_white)

    # Save the result
    black_white.save(image_path, format="JPEG", quality=100, subsampling=0)


def upscale(image_path: Path, scale: int) -> None:
    """
    Upscale image by scale factor.

    Args:
        image_path (Path): Path to image file.
        scale (int): Multiplier for image size.
    """
    # Open the image
    image_file: ImageFile.ImageFile = Image.open(image_path)

    # Optional: upscale for better accuracy
    image: Image.Image = image_file.resize(
        (image_file.width * scale, image_file.height * scale), Image.Resampling.NEAREST
    )

    # Save the result
    image.save(image_path, format="JPEG", quality=100, subsampling=0)
