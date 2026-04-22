import type {
  ExportResponse,
  JobSummary,
  OcrJobResponse,
  OcrOptions,
  WorkerHealth,
} from "./types";

const workerPort = Number(import.meta.env.VITE_ACME_OCR_WORKER_PORT ?? 47861);
const baseUrl = `http://127.0.0.1:${workerPort}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Worker request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getWorkerHealth(): Promise<WorkerHealth> {
  return request<WorkerHealth>("/health");
}

export function getBootstrapStatus() {
  return request("/bootstrap/status");
}

export function runOcr(filePath: string, options: OcrOptions) {
  return request<OcrJobResponse>("/ocr/run", {
    method: "POST",
    body: JSON.stringify({ filePath, options }),
  });
}

export function runBatch(folderPath: string, options: OcrOptions) {
  return request<{ jobs: JobSummary[] }>("/ocr/batch", {
    method: "POST",
    body: JSON.stringify({ folderPath, options }),
  });
}

export function getJob(jobId: string) {
  return request<OcrJobResponse>(`/ocr/jobs/${jobId}`);
}

export function cancelJob(jobId: string) {
  return request<{ success: boolean }>(`/ocr/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function exportJob(jobId: string, format: "json" | "csv" | "xlsx") {
  return request<ExportResponse>("/export", {
    method: "POST",
    body: JSON.stringify({ jobId, format }),
  });
}

