import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  AppOverview,
  BootstrapProgress,
  RuntimeManifest,
} from "./types";

export async function getAppOverview(): Promise<AppOverview> {
  return invoke<AppOverview>("get_app_overview");
}

export async function bootstrapInstall(
  manifestUrl: string,
): Promise<RuntimeManifest> {
  return invoke<RuntimeManifest>("bootstrap_install", { manifestUrl });
}

export async function ensureRuntimeAndWorker(
  manifestUrl: string,
): Promise<AppOverview> {
  return invoke<AppOverview>("ensure_runtime_and_worker", { manifestUrl });
}

export async function startWorker(): Promise<number> {
  return invoke<number>("start_worker");
}

export async function stopWorker(): Promise<void> {
  return invoke<void>("stop_worker");
}

export async function repairInstallation(): Promise<void> {
  return invoke<void>("repair_installation");
}

export async function pickFiles(): Promise<string[]> {
  return invoke<string[]>("pick_files");
}

export async function pickFolder(): Promise<string | null> {
  return invoke<string | null>("pick_folder");
}

export async function openLogsDir(): Promise<void> {
  return invoke<void>("open_logs_dir");
}

export async function listenBootstrapProgress(
  onMessage: (progress: BootstrapProgress) => void,
): Promise<UnlistenFn> {
  return listen<BootstrapProgress>("bootstrap://progress", (event) => {
    onMessage(event.payload);
  });
}
