from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import OcrBlock, OcrOptions, OcrPage, OcrResultPayload
from app.services.file_processor import pdf_to_images, prepare_image_file

logger = get_logger(__name__)


class PaddleAdapter:
    def __init__(self) -> None:
        self._ocr_by_language: dict[str, tuple[Any, str | None]] = {}
        self._paddle_error: Exception | None = None

    def _engine_key(self, language: str, detect_orientation: bool) -> str:
        return f"{language}:{'cls' if detect_orientation else 'nocls'}"

    def _language_name(self, language: str) -> str:
        return "ch" if language == "zh" else language

    def _find_model_subdir(self, model_root: Path, markers: tuple[str, ...]) -> str | None:
        if not model_root.exists():
            return None

        candidates = [model_root]
        candidates.extend(path for path in model_root.rglob("*") if path.is_dir())
        for candidate in candidates:
            name = candidate.name.lower()
            if any(marker in name for marker in markers):
                if (candidate / "inference.pdmodel").exists():
                    return str(candidate)
        return None

    def _resolve_model_bundle(self, language: str) -> tuple[str | None, dict[str, str | None]]:
        requested = language.lower()
        names = [f"ppocr-{requested}", f"paddleocr-{requested}"]
        if requested != "zh":
            names.extend(["ppocr-zh", "paddleocr-zh"])

        bundle_dir: Path | None = None
        for name in names:
            candidate = settings.models_dir / name
            if candidate.exists() and candidate.is_dir():
                bundle_dir = candidate
                break

        if bundle_dir is None and settings.models_dir.exists():
            directories = [path for path in settings.models_dir.iterdir() if path.is_dir()]
            bundle_dir = directories[0] if directories else None

        if bundle_dir is None:
            return None, {"det": None, "rec": None, "cls": None}

        return bundle_dir.name, {
            "det": self._find_model_subdir(bundle_dir, ("det", "detect")),
            "rec": self._find_model_subdir(bundle_dir, ("rec", "recognize")),
            "cls": self._find_model_subdir(bundle_dir, ("cls", "angle")),
        }

    def _ensure_engine(self, language: str, detect_orientation: bool) -> tuple[Any | None, str | None]:
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception as error:  # pragma: no cover - optional runtime dependency
            self._paddle_error = error
            return None, None

        key = self._engine_key(language, detect_orientation)
        if key in self._ocr_by_language:
            return self._ocr_by_language[key]

        bundle_name, bundle_paths = self._resolve_model_bundle(language)
        kwargs: dict[str, Any] = {
            "use_angle_cls": detect_orientation,
            "lang": self._language_name(language),
            "show_log": False,
        }
        if bundle_paths["det"]:
            kwargs["det_model_dir"] = bundle_paths["det"]
        if bundle_paths["rec"]:
            kwargs["rec_model_dir"] = bundle_paths["rec"]
        if detect_orientation and bundle_paths["cls"]:
            kwargs["cls_model_dir"] = bundle_paths["cls"]

        if (not bundle_paths["det"] or not bundle_paths["rec"]) and not settings.allow_model_auto_download:
            raise RuntimeError(f"OCR 模型缺失或目录结构不完整: {settings.models_dir}")

        if not bundle_paths["det"] or not bundle_paths["rec"]:
            logger.warning("model bundle incomplete, PaddleOCR may download defaults online")

        engine = PaddleOCR(**kwargs)
        self._ocr_by_language[key] = (engine, bundle_name)
        return engine, bundle_name

    def _normalize_lines(self, raw_result: Any) -> list[tuple[list[list[int]], str, float]]:
        candidate = raw_result
        if isinstance(raw_result, list) and len(raw_result) == 1 and isinstance(raw_result[0], list):
            candidate = raw_result[0]

        normalized: list[tuple[list[list[int]], str, float]] = []
        if not isinstance(candidate, list):
            return normalized

        for line in candidate:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue

            box, content = line[0], line[1]
            if not isinstance(box, (list, tuple)) or not isinstance(content, (list, tuple)) or len(content) < 2:
                continue

            normalized_box = [
                [int(float(point[0])), int(float(point[1]))]
                for point in box
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            if not normalized_box:
                continue

            normalized.append((normalized_box, str(content[0]), float(content[1])))

        return normalized

    def recognize(self, file_path: str, options: OcrOptions) -> OcrResultPayload:
        path = Path(file_path)
        metadata: dict[str, str | int | float | bool | None] = {
            "runtimeVersion": os.getenv("ACME_OCR_RUNTIME_VERSION", "dev"),
            "language": options.language,
            "fileType": path.suffix.lower().lstrip("."),
            "engine": "paddleocr",
        }

        if path.suffix.lower() == ".pdf":
            pages, extra_metadata = self._recognize_pdf(path, options)
            metadata.update(extra_metadata)
        else:
            page, extra_metadata = self._recognize_image(path, options, page_no=1)
            pages = [page]
            metadata.update(extra_metadata)

        metadata["pageCount"] = len(pages)
        if self._paddle_error is not None:
            metadata["engine"] = "mock"
            metadata["fallbackReason"] = str(self._paddle_error)

        return OcrResultPayload(pages=pages, metadata=metadata)

    def _recognize_pdf(
        self,
        file_path: Path,
        options: OcrOptions,
    ) -> tuple[list[OcrPage], dict[str, str | int | float | bool | None]]:
        rendered_pages = pdf_to_images(file_path, options)
        pages: list[OcrPage] = []
        model_bundle: str | None = None

        with tempfile.TemporaryDirectory(prefix="acmeocr-pdf-") as temp_dir:
            temp_root = Path(temp_dir)
            for rendered in rendered_pages:
                page_file = temp_root / f"page-{rendered.page_number}.png"
                rendered.image.save(page_file, format="PNG")
                page, page_metadata = self._recognize_image(
                    page_file,
                    options,
                    page_no=rendered.page_number,
                    image_size=(rendered.width, rendered.height),
                    source_name=file_path.name,
                )
                model_bundle = page_metadata.get("modelBundle") or model_bundle
                pages.append(page)

        return pages, {
            "pdfDpi": options.pdfDpi,
            "modelBundle": model_bundle,
        }

    def _recognize_image(
        self,
        file_path: Path,
        options: OcrOptions,
        page_no: int,
        image_size: tuple[int, int] | None = None,
        source_name: str | None = None,
    ) -> tuple[OcrPage, dict[str, str | int | float | bool | None]]:
        with tempfile.TemporaryDirectory(prefix="acmeocr-image-") as temp_dir:
            prepared_path, prepared_size = prepare_image_file(
                file_path,
                options,
                Path(temp_dir) / f"{file_path.stem}-prepared.png",
            )
            if image_size is not None:
                prepared_size = image_size

            try:
                engine, bundle_name = self._ensure_engine(options.language, options.detectOrientation)
            except RuntimeError as error:
                logger.warning("model lookup failed: %s", error)
                self._paddle_error = error
                engine, bundle_name = None, None

            metadata = {
                "modelBundle": bundle_name,
                "imageWidth": prepared_size[0],
                "imageHeight": prepared_size[1],
            }

            if engine is None:
                placeholder_name = source_name or file_path.name
                return (
                    OcrPage(
                        page=page_no,
                        blocks=[
                            OcrBlock(
                                text=f"[Mock OCR] PaddleOCR runtime not ready: {placeholder_name}",
                                score=0.0,
                                box=[[0, 0], [480, 0], [480, 40], [0, 40]],
                            )
                        ],
                    ),
                    metadata,
                )

            result = engine.ocr(str(prepared_path), cls=options.detectOrientation)
            blocks = [
                OcrBlock(text=text, score=score, box=box)
                for box, text, score in self._normalize_lines(result)
            ]

            if not blocks:
                blocks.append(
                    OcrBlock(
                        text="",
                        score=0.0,
                        box=[[0, 0], [prepared_size[0], 0], [prepared_size[0], prepared_size[1]], [0, prepared_size[1]]],
                    )
                )

            return OcrPage(page=page_no, blocks=blocks), metadata
