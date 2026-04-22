from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import settings
from app.models.schemas import OcrOptions

Image.MAX_IMAGE_PIXELS = 120_000_000
SUPPORTED_FILE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"}


@dataclass(slots=True)
class PreparedPdfPage:
    page_number: int
    image: Image.Image
    width: int
    height: int


def is_supported(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_FILE_TYPES


def scan_supported_files(folder_path: str) -> list[Path]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"folder not found: {folder_path}")

    return sorted(path for path in folder.rglob("*") if is_supported(path))


def apply_option_defaults(options: OcrOptions) -> OcrOptions:
    if options.pdfDpi <= 0:
        options.pdfDpi = settings.default_pdf_dpi
    if options.imageMaxSide <= 0:
        options.imageMaxSide = settings.default_image_max_side
    if options.pdfMaxPages <= 0 and settings.max_pdf_pages > 0:
        options.pdfMaxPages = settings.max_pdf_pages
    return options


def preprocess_image(image: Image.Image, options: OcrOptions) -> Image.Image:
    options = apply_option_defaults(options)
    normalized = ImageOps.exif_transpose(image).convert("RGB")
    normalized = ImageOps.autocontrast(normalized, cutoff=1)

    if options.binarize:
        grayscale = normalized.convert("L")
        grayscale = ImageOps.autocontrast(grayscale, cutoff=1)
        normalized = grayscale.point(lambda pixel: 255 if pixel > 168 else 0).convert("RGB")

    largest_side = max(normalized.size)
    if largest_side > options.imageMaxSide:
        ratio = options.imageMaxSide / float(largest_side)
        normalized = normalized.resize(
            (
                max(1, int(normalized.width * ratio)),
                max(1, int(normalized.height * ratio)),
            ),
            Image.Resampling.LANCZOS,
        )

    return normalized


def prepare_image_file(source_path: Path, options: OcrOptions, output_path: Path) -> tuple[Path, tuple[int, int]]:
    with Image.open(source_path) as image:
        processed = preprocess_image(image, options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        processed.save(output_path, format="PNG")
        return output_path, processed.size


def pdf_to_images(file_path: Path, options: OcrOptions) -> list[PreparedPdfPage]:
    try:
        import fitz  # type: ignore
    except Exception as error:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("PyMuPDF 未安装，当前 runtime 无法处理 PDF") from error

    options = apply_option_defaults(options)
    document = fitz.open(file_path)
    scale = options.pdfDpi / 72.0
    max_pages = options.pdfMaxPages if options.pdfMaxPages > 0 else None
    pages: list[PreparedPdfPage] = []

    try:
        for index, page in enumerate(document, start=1):
            if max_pages is not None and index > max_pages:
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            image = preprocess_image(image, options)
            pages.append(
                PreparedPdfPage(
                    page_number=index,
                    image=image,
                    width=image.width,
                    height=image.height,
                )
            )
    finally:
        document.close()

    return pages
