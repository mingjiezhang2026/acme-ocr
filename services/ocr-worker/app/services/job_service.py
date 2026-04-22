from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.database import Database
from app.engine.paddle_adapter import PaddleAdapter
from app.models.schemas import JobSummary, OcrOptions, OcrResultPayload
from app.services.file_processor import is_supported, scan_supported_files

logger = get_logger(__name__)


class JobService:
    def __init__(self, settings: Settings, database: Database, bootstrap_service: Any) -> None:
        self.settings = settings
        self.database = database
        self.bootstrap_service = bootstrap_service
        self.adapter = PaddleAdapter()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def run_single(self, file_path: str, options: OcrOptions) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_path}")
        if not is_supported(path):
            raise ValueError(f"unsupported file type: {path.suffix}")

        job_id = self._create_job(file_path)
        result = await asyncio.to_thread(self._process_job, job_id, file_path, options)
        return {"job_id": job_id, "status": "completed", "result": result}

    async def run_batch(self, folder_path: str, options: OcrOptions) -> list[JobSummary]:
        files = scan_supported_files(folder_path)
        jobs: list[JobSummary] = []
        for file_path in files:
            job_id = self._create_job(str(file_path))
            task = asyncio.create_task(self._run_background(job_id, str(file_path), options))
            self._tasks[job_id] = task
            jobs.append(JobSummary(**self._read_job_summary(job_id)))
        return jobs

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            return None

        detail = self._read_job_summary(job_id)
        result_rows = self.database.fetchall(
            "SELECT page_no, result_json FROM job_results WHERE job_id = ? ORDER BY page_no ASC",
            (job_id,),
        )
        if result_rows:
            payload = {
                "pages": [json.loads(row["result_json"]) for row in result_rows],
                "metadata": None,
            }
        else:
            payload = None

        return {**detail, "result": payload}

    async def cancel_job(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task is None:
            return self.database.fetchone("SELECT id FROM jobs WHERE id = ?", (job_id,)) is not None

        task.cancel()
        self.database.execute(
            "UPDATE jobs SET status = ?, updated_at = ?, error_message = ? WHERE id = ?",
            ("cancelled", datetime.now(timezone.utc).isoformat(), "cancelled by user", job_id),
        )
        self._tasks.pop(job_id, None)
        return True

    async def _run_background(self, job_id: str, file_path: str, options: OcrOptions) -> None:
        try:
            await asyncio.to_thread(self._process_job, job_id, file_path, options)
        except asyncio.CancelledError:
            logger.info("job %s cancelled", job_id)
            raise
        except Exception as error:
            logger.exception("job %s failed", job_id)
            self.database.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, error_message = ? WHERE id = ?",
                ("failed", datetime.now(timezone.utc).isoformat(), str(error), job_id),
            )
        finally:
            self._tasks.pop(job_id, None)

    def _process_job(self, job_id: str, file_path: str, options: OcrOptions) -> dict[str, Any]:
        self.database.execute(
            "UPDATE jobs SET status = ?, updated_at = ?, error_message = NULL WHERE id = ?",
            ("running", datetime.now(timezone.utc).isoformat(), job_id),
        )
        result = self.adapter.recognize(file_path, options)
        self._save_result(job_id, result)
        self.database.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("completed", datetime.now(timezone.utc).isoformat(), job_id),
        )
        return result.model_dump()

    def _create_job(self, file_path: str) -> str:
        job_id = f"job_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        file_hash = self._hash_file(file_path)
        self.database.execute(
            """
            INSERT INTO jobs(id, status, file_path, file_hash, created_at, updated_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (job_id, "queued", file_path, file_hash, now, now),
        )
        return job_id

    def _save_result(self, job_id: str, result: OcrResultPayload) -> None:
        payload = result.model_dump()
        self.database.execute("DELETE FROM job_results WHERE job_id = ?", (job_id,))
        for page in payload["pages"]:
            self.database.execute(
                "INSERT INTO job_results(job_id, page_no, result_json) VALUES (?, ?, ?)",
                (job_id, page["page"], json.dumps(page, ensure_ascii=False)),
            )

    def _read_job_summary(self, job_id: str) -> dict[str, Any]:
        row = self.database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            raise KeyError(job_id)
        return {
            "id": row["id"],
            "status": row["status"],
            "filePath": row["file_path"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "errorMessage": row["error_message"],
        }

    def _hash_file(self, file_path: str) -> str:
        path = Path(file_path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
