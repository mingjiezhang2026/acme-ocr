from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.db.database import Database


class ExportService:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database

    def export_job(self, job_id: str, fmt: str, target_path: str | None = None) -> dict[str, str]:
        rows = self.database.fetchall(
            """
            SELECT jobs.id, jobs.file_path, job_results.page_no, job_results.result_json
            FROM jobs
            LEFT JOIN job_results ON jobs.id = job_results.job_id
            WHERE jobs.id = ?
            ORDER BY job_results.page_no ASC
            """,
            (job_id,),
        )
        if not rows or rows[0]["result_json"] is None:
            raise ValueError("job result not found")

        payload = {
            "pages": [json.loads(row["result_json"]) for row in rows if row["result_json"] is not None],
            "metadata": None,
        }
        output_path = Path(target_path) if target_path else self.settings.exports_dir / f"{job_id}.{fmt}"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "csv":
            self._write_csv(output_path, payload)
        elif fmt == "xlsx":
            self._write_xlsx(output_path, payload)
        else:
            raise ValueError(f"unsupported format: {fmt}")

        self.database.execute(
            "INSERT INTO exports(job_id, format, target_path, created_at) VALUES (?, ?, ?, ?)",
            (job_id, fmt, str(output_path), datetime.now(timezone.utc).isoformat()),
        )
        return {"outputPath": str(output_path), "format": fmt}

    def _flatten_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in payload.get("pages", []):
            for block in page.get("blocks", []):
                rows.append(
                    {
                        "page": page.get("page"),
                        "text": block.get("text", ""),
                        "score": block.get("score", 0),
                        "box": json.dumps(block.get("box", []), ensure_ascii=False),
                    }
                )
        return rows

    def _write_csv(self, target: Path, payload: dict[str, Any]) -> None:
        rows = self._flatten_rows(payload)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["page", "text", "score", "box"])
            writer.writeheader()
            writer.writerows(rows)

    def _write_xlsx(self, target: Path, payload: dict[str, Any]) -> None:
        try:
            from openpyxl import Workbook
        except Exception as error:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("openpyxl 未安装，当前 runtime 无法导出 XLSX") from error

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "OCR"
        sheet.append(["page", "text", "score", "box"])
        for row in self._flatten_rows(payload):
            sheet.append([row["page"], row["text"], row["score"], row["box"]])
        workbook.save(target)
