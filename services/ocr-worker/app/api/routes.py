from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import (
    BatchOcrRequest,
    BatchOcrResponse,
    BootstrapStatusResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    JobDetailResponse,
    OcrRequest,
    OcrResponse,
    SettingsResponse,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    bootstrap = request.app.state.bootstrap_service
    status = bootstrap.status()
    return HealthResponse(
        status="ok",
        runtimeVersion=status.versions.get("runtime", "dev"),
        modelStatus="ready" if status.modelsInstalled else "missing",
    )


@router.get("/bootstrap/status", response_model=BootstrapStatusResponse)
async def bootstrap_status(request: Request) -> BootstrapStatusResponse:
    return request.app.state.bootstrap_service.status()


@router.post("/ocr/run", response_model=OcrResponse)
async def run_ocr(payload: OcrRequest, request: Request) -> OcrResponse:
    job_service = request.app.state.job_service
    job = await job_service.run_single(payload.filePath, payload.options)
    return OcrResponse(jobId=job["job_id"], status=job["status"], result=job["result"])


@router.post("/ocr/batch", response_model=BatchOcrResponse)
async def run_batch(payload: BatchOcrRequest, request: Request) -> BatchOcrResponse:
    job_service = request.app.state.job_service
    jobs = await job_service.run_batch(payload.folderPath, payload.options)
    return BatchOcrResponse(jobs=jobs)


@router.get("/ocr/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str, request: Request) -> JobDetailResponse:
    job_service = request.app.state.job_service
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobDetailResponse.model_validate(job)


@router.post("/ocr/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> dict[str, bool]:
    job_service = request.app.state.job_service
    success = await job_service.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="job not found")
    return {"success": True}


@router.post("/export", response_model=ExportResponse)
async def export_job(payload: ExportRequest, request: Request) -> ExportResponse:
    export_service = request.app.state.export_service
    result = export_service.export_job(payload.jobId, payload.format, payload.targetPath)
    return ExportResponse(**result)


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(request: Request) -> SettingsResponse:
    return SettingsResponse(**request.app.state.bootstrap_service.read_settings())
