export type BootstrapStage =
  | "NOT_INITIALIZED"
  | "CHECKING_MANIFEST"
  | "DOWNLOADING_RUNTIME"
  | "DOWNLOADING_MODELS"
  | "VERIFYING"
  | "UNPACKING"
  | "INSTALLING"
  | "STARTING_WORKER"
  | "READY"
  | "FAILED";

export interface InstalledComponent {
  version: string;
  installedAt: string;
}

export interface InstalledState {
  platform: string;
  appVersion: string;
  runtime: InstalledComponent;
  models: InstalledComponent[];
  manifestUrl: string;
}

