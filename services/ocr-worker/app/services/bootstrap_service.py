from __future__ import annotations

import json

from app.core.config import Settings
from app.models.schemas import BootstrapStatusResponse


class BootstrapService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def status(self) -> BootstrapStatusResponse:
        self.settings.ensure_directories()
        installed_path = self.settings.config_dir / "installed.json"
        installed = None
        if installed_path.exists():
            installed = json.loads(installed_path.read_text(encoding="utf-8"))

        model_dirs = [item for item in self.settings.models_dir.iterdir()] if self.settings.models_dir.exists() else []
        runtime_installed = (
            (self.settings.runtime_dir / "worker" / "main.py").exists()
            or (self.settings.runtime_dir / "python" / "python.exe").exists()
            or (self.settings.runtime_dir / "python" / "bin" / "python3").exists()
            or (self.settings.runtime_dir / "python" / "bin" / "python").exists()
        )
        versions = {"runtime": self.settings.runtime_version}
        if installed:
            versions["runtime"] = installed.get("runtime", {}).get("version", self.settings.runtime_version)
            for model in installed.get("models", []):
                versions[model.get("name", "model")] = model.get("version", "")

        return BootstrapStatusResponse(
            initialized=installed is not None,
            runtimeInstalled=runtime_installed,
            modelsInstalled=len(model_dirs) > 0,
            versions=versions,
        )

    def read_settings(self) -> dict[str, object]:
        return self.settings.read_settings()
