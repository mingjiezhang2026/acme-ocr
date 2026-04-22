from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _default_home() -> Path:
    env_home = os.getenv("ACME_OCR_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "AcmeOCR"

    return Path.home() / "Library" / "Application Support" / "AcmeOCR"


@dataclass(slots=True)
class Settings:
    app_home: Path
    runtime_dir: Path
    models_dir: Path
    data_dir: Path
    cache_dir: Path
    logs_dir: Path
    config_dir: Path
    database_path: Path
    jobs_dir: Path
    exports_dir: Path
    worker_log_file: Path
    settings_file: Path
    runtime_version: str
    allow_model_auto_download: bool
    default_pdf_dpi: int
    max_pdf_pages: int
    default_image_max_side: int

    def ensure_directories(self) -> None:
        for directory in (
            self.runtime_dir,
            self.models_dir,
            self.data_dir,
            self.cache_dir,
            self.logs_dir,
            self.config_dir,
            self.jobs_dir,
            self.exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        if not self.settings_file.exists():
            self.settings_file.write_text(
                json.dumps(
                    {
                        "language": "zh",
                        "defaultExportDir": str(self.exports_dir),
                        "ocrMode": "accurate",
                        "autoCheckUpdates": True,
                        "cacheLimitMb": 2048,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def read_settings(self) -> dict[str, Any]:
        self.ensure_directories()
        return json.loads(self.settings_file.read_text(encoding="utf-8"))


def load_settings() -> Settings:
    app_home = _default_home()
    return Settings(
        app_home=app_home,
        runtime_dir=app_home / "runtime",
        models_dir=app_home / "models",
        data_dir=app_home / "data",
        cache_dir=app_home / "cache",
        logs_dir=app_home / "logs",
        config_dir=app_home / "config",
        database_path=app_home / "data" / "app.db",
        jobs_dir=app_home / "data" / "jobs",
        exports_dir=app_home / "data" / "exports",
        worker_log_file=app_home / "logs" / "worker.log",
        settings_file=app_home / "config" / "settings.json",
        runtime_version=os.getenv("ACME_OCR_RUNTIME_VERSION", "dev"),
        allow_model_auto_download=os.getenv("ACME_OCR_ALLOW_MODEL_AUTO_DOWNLOAD", "0") == "1",
        default_pdf_dpi=int(os.getenv("ACME_OCR_DEFAULT_PDF_DPI", "216")),
        max_pdf_pages=int(os.getenv("ACME_OCR_MAX_PDF_PAGES", "0")),
        default_image_max_side=int(os.getenv("ACME_OCR_DEFAULT_IMAGE_MAX_SIDE", "2400")),
    )


settings = load_settings()
