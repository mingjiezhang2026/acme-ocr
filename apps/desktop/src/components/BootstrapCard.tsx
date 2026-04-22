import type { BootstrapProgress, InstalledState } from "../lib/types";
import { StatusPill } from "./StatusPill";

interface BootstrapCardProps {
  manifestUrl: string;
  installed: InstalledState | null;
  progress: BootstrapProgress;
  busy: boolean;
  autoBootstrapEnabled: boolean;
  bootstrapRequired: boolean;
  onInstall: () => void;
  onEnsureReady: () => void;
  onRepair: () => void;
}

export function BootstrapCard({
  manifestUrl,
  installed,
  progress,
  busy,
  autoBootstrapEnabled,
  bootstrapRequired,
  onInstall,
  onEnsureReady,
  onRepair,
}: BootstrapCardProps) {
  const ready = progress.stage === "READY" || (Boolean(installed) && !bootstrapRequired);

  return (
    <section className="panel panel--hero">
      <div className="panel__header">
        <div>
          <p className="eyebrow">首次安装与运行时管理</p>
          <h2>Bootstrap</h2>
        </div>
        <StatusPill
          tone={ready ? "ready" : progress.stage === "FAILED" ? "danger" : "warn"}
          label={ready ? "可离线运行" : progress.stage}
        />
      </div>

      <p className="muted">
        用户不需要单独安装 Python、PaddleOCR 或其他依赖。应用首次启动会自动从
        manifest 下载预构建的 runtime bundle 和 model bundle，校验后写入本地目录，
        后续即可离线使用。
      </p>

      {autoBootstrapEnabled ? (
        <p className="muted">
          当前已启用自动初始化策略：首次打开会自动安装运行环境，后续启动只做本地自检与服务拉起。
        </p>
      ) : null}

      <div className="kv-grid">
        <div>
          <span>Manifest</span>
          <strong>{manifestUrl}</strong>
        </div>
        <div>
          <span>Runtime</span>
          <strong>{installed?.runtime.version ?? "未安装"}</strong>
        </div>
      </div>

      <div className="progress-card">
        <div className="progress-card__meta">
          <span>{progress.stage}</span>
          <span>{Math.round((progress.progress ?? 0) * 100)}%</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-bar__fill"
            style={{ width: `${Math.round((progress.progress ?? 0) * 100)}%` }}
          />
        </div>
        <p className="muted">{progress.message}</p>
      </div>

      <div className="actions">
        <button className="button button--primary" onClick={onEnsureReady} disabled={busy}>
          {busy
            ? "处理中..."
            : bootstrapRequired
              ? "自动安装并启动"
              : "检查环境并启动"}
        </button>
        <button className="button button--primary" onClick={onInstall} disabled={busy}>
          {busy ? "处理中..." : installed ? "仅检查并更新资源" : "仅执行安装"}
        </button>
        <button className="button button--ghost" onClick={onRepair} disabled={busy}>
          修复安装
        </button>
      </div>
    </section>
  );
}
