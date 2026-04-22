import { useEffect, useState } from "react";
import { BootstrapCard } from "./components/BootstrapCard";
import { OcrPanel } from "./components/OcrPanel";
import { WorkerCard } from "./components/WorkerCard";
import { useBootstrapProgress } from "./hooks/useBootstrapProgress";
import {
  bootstrapInstall,
  ensureRuntimeAndWorker,
  getAppOverview,
  openLogsDir,
  pickFiles,
  pickFolder,
  repairInstallation,
  startWorker,
  stopWorker,
} from "./lib/tauri";
import type { AppOverview, WorkerHealth } from "./lib/types";
import { exportJob, getWorkerHealth, runBatch, runOcr } from "./lib/worker";

export default function App() {
  const { progress, setProgress } = useBootstrapProgress();
  const [overview, setOverview] = useState<AppOverview | null>(null);
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [autoEnsureAttempted, setAutoEnsureAttempted] = useState(false);
  const manifestUrl =
    import.meta.env.VITE_ACME_OCR_MANIFEST_URL ??
    `https://raw.githubusercontent.com/mingjiezhang2026/acme-ocr/main/infra/manifests/${overview?.platform ?? "windows-x64"}.json`;
  const autoBootstrapEnabled =
    (import.meta.env.VITE_ACME_OCR_AUTO_BOOTSTRAP ??
      (import.meta.env.PROD ? "true" : "false")) === "true";

  async function refreshOverview() {
    const next = await getAppOverview();
    setOverview(next);
  }

  async function refreshHealth() {
    try {
      const nextHealth = await getWorkerHealth();
      setHealth(nextHealth);
    } catch {
      setHealth(null);
    }
  }

  useEffect(() => {
    void refreshOverview().catch((reason) => {
      setError(reason instanceof Error ? reason.message : "读取应用状态失败");
    });
    void refreshHealth();
  }, []);

  useEffect(() => {
    if (!autoBootstrapEnabled || autoEnsureAttempted || busy || !overview) {
      return;
    }

    if (overview.bootstrapRequired || !overview.workerRunning) {
      setAutoEnsureAttempted(true);
      void handleEnsureReady();
    }
  }, [autoBootstrapEnabled, autoEnsureAttempted, busy, overview]);

  async function handleEnsureReady() {
    setBusy(true);
    setError("");
    setProgress({
      stage: overview?.bootstrapRequired ? "CHECKING_MANIFEST" : "STARTING_WORKER",
      message: overview?.bootstrapRequired
        ? "首次启动正在准备 OCR 运行环境"
        : "正在启动本地 OCR 服务",
      progress: overview?.bootstrapRequired ? 0.02 : 0.9,
    });

    try {
      const nextOverview = await ensureRuntimeAndWorker(manifestUrl);
      setOverview(nextOverview);
      await refreshHealth();
      setProgress({
        stage: "READY",
        message: nextOverview.bootstrapRequired
          ? "运行环境检查未完成"
          : "OCR 环境已就绪，可直接使用",
        progress: 1,
      });
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "初始化 OCR 环境失败";
      setError(message);
      setProgress({
        stage: "FAILED",
        message,
        progress: progress.progress,
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleInstall() {
    setBusy(true);
    setError("");
    try {
      const manifest = await bootstrapInstall(manifestUrl);
      setProgress({
        stage: "READY",
        message: `资源安装完成，runtime ${manifest.runtime.version}`,
        progress: 1,
      });
      await refreshOverview();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "安装失败";
      setError(message);
      setProgress({
        stage: "FAILED",
        message,
        progress: progress.progress,
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleRepair() {
    setBusy(true);
    setError("");
    try {
      await repairInstallation();
      setProgress({
        stage: "NOT_INITIALIZED",
        message: "已清理 runtime 和 model 目录，请重新安装。",
        progress: 0,
      });
      await refreshOverview();
      setHealth(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "修复失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleStartWorker() {
    setBusy(true);
    setError("");
    try {
      await startWorker();
      await refreshOverview();
      await refreshHealth();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "启动 Worker 失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleStopWorker() {
    setBusy(true);
    setError("");
    try {
      await stopWorker();
      await refreshOverview();
      setHealth(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "停止 Worker 失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">AcmeOCR</p>
          <h1>本地 OCR 桌面软件</h1>
          <p className="hero__copy">
            Tauri 2 + React + TypeScript 桌面壳，配合 Python FastAPI Worker，
            支持 Windows 与 macOS 的首次联网安装、后续离线 OCR。
          </p>
        </div>

        <div className="hero__meta">
          <div>
            <span>平台</span>
            <strong>{overview?.platform ?? "loading..."}</strong>
          </div>
          <div>
            <span>App Version</span>
            <strong>{overview?.appVersion ?? "0.1.0"}</strong>
          </div>
          <div>
            <span>Worker Port</span>
            <strong>{overview?.workerPort ?? 47861}</strong>
          </div>
        </div>
      </header>

      {error ? <section className="banner">{error}</section> : null}

      <section className="layout-grid">
        <BootstrapCard
          manifestUrl={manifestUrl}
          installed={overview?.installed ?? null}
          progress={progress}
          busy={busy}
          autoBootstrapEnabled={autoBootstrapEnabled}
          bootstrapRequired={overview?.bootstrapRequired ?? true}
          onInstall={() => void handleInstall()}
          onEnsureReady={() => void handleEnsureReady()}
          onRepair={() => void handleRepair()}
        />

        <WorkerCard
          health={health}
          workerRunning={overview?.workerRunning ?? false}
          busy={busy}
          onStart={() => void handleStartWorker()}
          onStop={() => void handleStopWorker()}
          onOpenLogs={() => void openLogsDir()}
        />
      </section>

      <OcrPanel
        onPickFile={pickFiles}
        onPickFolder={pickFolder}
        onRunSingle={runOcr}
        onRunBatch={runBatch}
        onExport={exportJob}
      />

      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">本地目录</p>
            <h2>Windows / macOS 兼容路径</h2>
          </div>
        </div>

        <div className="path-list">
          <div>
            <span>App Home</span>
            <strong>{overview?.paths.appHome ?? "-"}</strong>
          </div>
          <div>
            <span>Runtime</span>
            <strong>{overview?.paths.runtimeDir ?? "-"}</strong>
          </div>
          <div>
            <span>Models</span>
            <strong>{overview?.paths.modelsDir ?? "-"}</strong>
          </div>
          <div>
            <span>Logs</span>
            <strong>{overview?.paths.logsDir ?? "-"}</strong>
          </div>
        </div>
      </section>
    </main>
  );
}
