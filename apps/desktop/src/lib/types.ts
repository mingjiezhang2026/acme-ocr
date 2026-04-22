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

export interface BootstrapProgress {
  stage: BootstrapStage;
  message: string;
  progress?: number;
}

export interface InstalledComponent {
  version: string;
  installedAt: string;
}

export interface InstalledModel extends InstalledComponent {
  name: string;
}

export interface InstalledState {
  platform: string;
  appVersion: string;
  runtime: InstalledComponent;
  models: InstalledModel[];
  manifestUrl: string;
}

export interface AppPaths {
  appHome: string;
  runtimeDir: string;
  modelsDir: string;
  dataDir: string;
  cacheDir: string;
  logsDir: string;
  configDir: string;
}

export interface AppOverview {
  platform: string;
  appVersion: string;
  paths: AppPaths;
  installed: InstalledState | null;
  runtimeInstalled: boolean;
  modelsInstalled: boolean;
  bootstrapRequired: boolean;
  workerPort: number;
  workerRunning: boolean;
}

export interface BootstrapResource {
  version: string;
  url: string;
  sha256: string;
  size?: number | null;
}

export interface ManifestModel extends BootstrapResource {
  name: string;
}

export interface RuntimeManifest {
  platform: string;
  appVersion: string;
  runtime: BootstrapResource;
  models: ManifestModel[];
  features: ManifestModel[];
  minAppVersion: string;
}

export interface WorkerHealth {
  status: string;
  runtimeVersion: string;
  modelStatus: string;
}

export interface OcrBlock {
  text: string;
  score: number;
  box: number[][];
}

export interface OcrPage {
  page: number;
  blocks: OcrBlock[];
}

export interface OcrResultPayload {
  pages: OcrPage[];
  metadata?: Record<string, string | number | boolean | null>;
}

export interface JobSummary {
  id: string;
  status: string;
  filePath: string;
  createdAt: string;
  updatedAt: string;
  errorMessage?: string | null;
}

export interface OcrJobResponse {
  jobId: string;
  status: string;
  result: OcrResultPayload;
}

export interface OcrOptions {
  language: string;
  detectOrientation: boolean;
  enableTable: boolean;
  outputFormat: "json" | "text";
  pdfDpi?: number;
  pdfMaxPages?: number;
  imageMaxSide?: number;
  binarize?: boolean;
}

export interface ExportResponse {
  outputPath: string;
  format: string;
}
