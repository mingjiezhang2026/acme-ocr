from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OcrOptions(BaseModel):
    language: str = "zh"
    detectOrientation: bool = True
    enableTable: bool = False
    outputFormat: Literal["json", "text"] = "json"
    pdfDpi: int = 216
    pdfMaxPages: int = 0
    imageMaxSide: int = 2400
    binarize: bool = False


class OcrRequest(BaseModel):
    filePath: str
    options: OcrOptions = Field(default_factory=OcrOptions)


class BatchOcrRequest(BaseModel):
    folderPath: str
    options: OcrOptions = Field(default_factory=OcrOptions)


class OcrBlock(BaseModel):
    text: str
    score: float
    box: list[list[int]]


class OcrPage(BaseModel):
    page: int
    blocks: list[OcrBlock]


class OcrResultPayload(BaseModel):
    pages: list[OcrPage]
    metadata: dict[str, Any] | None = None


class OcrResponse(BaseModel):
    jobId: str
    status: str
    result: OcrResultPayload


class JobSummary(BaseModel):
    id: str
    status: str
    filePath: str
    createdAt: str
    updatedAt: str
    errorMessage: str | None = None


class JobDetailResponse(BaseModel):
    id: str
    status: str
    filePath: str
    createdAt: str
    updatedAt: str
    errorMessage: str | None = None
    result: OcrResultPayload | None = None


class BatchOcrResponse(BaseModel):
    jobs: list[JobSummary]


class ExportRequest(BaseModel):
    jobId: str
    format: Literal["json", "csv", "xlsx"]
    targetPath: str | None = None


class ExportResponse(BaseModel):
    outputPath: str
    format: str


class HealthResponse(BaseModel):
    status: str
    runtimeVersion: str
    modelStatus: str


class BootstrapStatusResponse(BaseModel):
    initialized: bool
    runtimeInstalled: bool
    modelsInstalled: bool
    versions: dict[str, str]


class SettingsResponse(BaseModel):
    language: str
    defaultExportDir: str
    ocrMode: str
    autoCheckUpdates: bool
    cacheLimitMb: int
