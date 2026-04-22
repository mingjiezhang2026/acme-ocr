import { useState } from "react";
import type { ExportResponse, OcrJobResponse, OcrOptions } from "../lib/types";

interface OcrPanelProps {
  onPickFile: () => Promise<string[]>;
  onPickFolder: () => Promise<string | null>;
  onRunSingle: (filePath: string, options: OcrOptions) => Promise<OcrJobResponse>;
  onRunBatch: (
    folderPath: string,
    options: OcrOptions,
  ) => Promise<{ jobs: { id: string; status: string; filePath: string }[] }>;
  onExport: (jobId: string, format: "json" | "csv" | "xlsx") => Promise<ExportResponse>;
}

const defaultOptions: OcrOptions = {
  language: "zh",
  detectOrientation: true,
  enableTable: false,
  outputFormat: "json",
  pdfDpi: 216,
  pdfMaxPages: 0,
  imageMaxSide: 2400,
  binarize: false,
};

export function OcrPanel({
  onPickFile,
  onPickFolder,
  onRunSingle,
  onRunBatch,
  onExport,
}: OcrPanelProps) {
  const [options, setOptions] = useState<OcrOptions>(defaultOptions);
  const [selectedFile, setSelectedFile] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [result, setResult] = useState<OcrJobResponse | null>(null);
  const [batchInfo, setBatchInfo] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("选择文件或文件夹开始识别。");

  async function handlePickFile() {
    const files = await onPickFile();
    if (files.length > 0) {
      setSelectedFile(files[0]);
    }
  }

  async function handlePickFolder() {
    const folder = await onPickFolder();
    if (folder) {
      setSelectedFolder(folder);
    }
  }

  async function handleRunSingle() {
    if (!selectedFile) {
      setMessage("请先选择图片或 PDF 文件。");
      return;
    }

    setBusy(true);
    setMessage("正在调用本地 OCR Worker...");
    try {
      const next = await onRunSingle(selectedFile, options);
      setResult(next);
      setBatchInfo("");
      setMessage(`识别完成，任务 ${next.jobId}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "识别失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRunBatch() {
    if (!selectedFolder) {
      setMessage("请先选择批量处理文件夹。");
      return;
    }

    setBusy(true);
    setMessage("正在创建批量 OCR 任务...");
    try {
      const response = await onRunBatch(selectedFolder, options);
      setBatchInfo(`已提交 ${response.jobs.length} 个任务`);
      setMessage("批量任务已提交，可在后续版本中扩展历史页。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport(format: "json" | "csv" | "xlsx") {
    if (!result) {
      setMessage("当前没有可导出的 OCR 结果。");
      return;
    }

    setBusy(true);
    try {
      const exportResult = await onExport(result.jobId, format);
      setMessage(`导出完成：${exportResult.outputPath}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">图片 / PDF / 批量目录</p>
          <h2>OCR 任务</h2>
        </div>
      </div>

      <div className="field-grid">
        <label className="field">
          <span>单文件路径</span>
          <div className="field__inline">
            <input value={selectedFile} onChange={(event) => setSelectedFile(event.target.value)} />
            <button className="button button--ghost" onClick={handlePickFile}>
              选择文件
            </button>
          </div>
        </label>

        <label className="field">
          <span>批量目录</span>
          <div className="field__inline">
            <input
              value={selectedFolder}
              onChange={(event) => setSelectedFolder(event.target.value)}
            />
            <button className="button button--ghost" onClick={handlePickFolder}>
              选择文件夹
            </button>
          </div>
        </label>
      </div>

      <div className="field-grid field-grid--compact">
        <label className="field">
          <span>语言</span>
          <select
            value={options.language}
            onChange={(event) =>
              setOptions((current) => ({ ...current, language: event.target.value }))
            }
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </label>

        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={options.detectOrientation}
            onChange={(event) =>
              setOptions((current) => ({
                ...current,
                detectOrientation: event.target.checked,
              }))
            }
          />
          <span>方向检测</span>
        </label>

        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={options.enableTable}
            onChange={(event) =>
              setOptions((current) => ({
                ...current,
                enableTable: event.target.checked,
              }))
            }
          />
          <span>表格增强</span>
        </label>
      </div>

      <div className="actions">
        <button className="button button--primary" onClick={handleRunSingle} disabled={busy}>
          识别当前文件
        </button>
        <button className="button button--ghost" onClick={handleRunBatch} disabled={busy}>
          批量处理
        </button>
        <button className="button button--ghost" onClick={() => void handleExport("json")}>
          导出 JSON
        </button>
        <button className="button button--ghost" onClick={() => void handleExport("csv")}>
          导出 CSV
        </button>
        <button className="button button--ghost" onClick={() => void handleExport("xlsx")}>
          导出 XLSX
        </button>
      </div>

      <div className="result-card">
        <p>{message}</p>
        {batchInfo ? <p className="muted">{batchInfo}</p> : null}
        {result ? (
          <pre>{JSON.stringify(result.result, null, 2)}</pre>
        ) : (
          <p className="muted">结果会在这里预览，当前展示统一 JSON 结构。</p>
        )}
      </div>
    </section>
  );
}
