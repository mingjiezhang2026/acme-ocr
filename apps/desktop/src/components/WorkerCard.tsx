import type { WorkerHealth } from "../lib/types";
import { StatusPill } from "./StatusPill";

interface WorkerCardProps {
  health: WorkerHealth | null;
  workerRunning: boolean;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  onOpenLogs: () => void;
}

export function WorkerCard({
  health,
  workerRunning,
  busy,
  onStart,
  onStop,
  onOpenLogs,
}: WorkerCardProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">本地 OCR Worker</p>
          <h2>服务状态</h2>
        </div>
        <StatusPill
          tone={health?.status === "ok" ? "ready" : workerRunning ? "warn" : "neutral"}
          label={health?.status === "ok" ? "运行中" : workerRunning ? "启动中" : "未启动"}
        />
      </div>

      <div className="kv-grid">
        <div>
          <span>Runtime Version</span>
          <strong>{health?.runtimeVersion ?? "未知"}</strong>
        </div>
        <div>
          <span>Model Status</span>
          <strong>{health?.modelStatus ?? "unknown"}</strong>
        </div>
      </div>

      <div className="actions">
        <button className="button button--primary" onClick={onStart} disabled={busy}>
          启动 Worker
        </button>
        <button className="button button--ghost" onClick={onStop} disabled={busy}>
          停止 Worker
        </button>
        <button className="button button--ghost" onClick={onOpenLogs}>
          打开日志目录
        </button>
      </div>
    </section>
  );
}

