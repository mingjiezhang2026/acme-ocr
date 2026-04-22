use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppPaths {
    pub app_home: String,
    pub runtime_dir: String,
    pub models_dir: String,
    pub data_dir: String,
    pub cache_dir: String,
    pub logs_dir: String,
    pub config_dir: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InstalledComponent {
    pub version: String,
    pub installed_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InstalledState {
    pub platform: String,
    pub app_version: String,
    pub runtime: InstalledComponent,
    pub models: Vec<InstalledComponentWithName>,
    pub manifest_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InstalledComponentWithName {
    pub name: String,
    pub version: String,
    pub installed_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BootstrapResource {
    pub version: String,
    pub url: String,
    pub sha256: String,
    pub size: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ManifestModel {
    pub name: String,
    pub version: String,
    pub url: String,
    pub sha256: String,
    pub size: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeManifest {
    pub platform: String,
    pub app_version: String,
    pub runtime: BootstrapResource,
    pub models: Vec<ManifestModel>,
    pub features: Vec<ManifestModel>,
    pub min_app_version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BootstrapProgress {
    pub stage: String,
    pub message: String,
    pub progress: Option<f32>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppOverview {
    pub platform: String,
    pub app_version: String,
    pub paths: AppPaths,
    pub installed: Option<InstalledState>,
    pub runtime_installed: bool,
    pub models_installed: bool,
    pub bootstrap_required: bool,
    pub worker_port: u16,
    pub worker_running: bool,
}
