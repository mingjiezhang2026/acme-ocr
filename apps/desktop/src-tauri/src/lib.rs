mod error;
mod logging;
mod models;
mod state;

use anyhow::Context;
use chrono::Utc;
use error::{AppError, AppResult};
use futures_util::StreamExt;
use logging::append_log;
use models::{
    AppOverview, AppPaths, BootstrapProgress, BootstrapResource, InstalledComponent,
    InstalledComponentWithName, InstalledState, RuntimeManifest,
};
use sha2::{Digest, Sha256};
use state::AppRuntimeState;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager, State};

const WORKER_PORT: u16 = 47861;
const INSTALLED_FILE: &str = "installed.json";

#[tauri::command]
fn get_app_overview(app: AppHandle, state: State<'_, AppRuntimeState>) -> Result<AppOverview, String> {
    get_app_overview_impl(&app, &state)
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn bootstrap_install(
    app: AppHandle,
    _state: State<'_, AppRuntimeState>,
    manifest_url: String,
) -> Result<RuntimeManifest, String> {
    bootstrap_install_impl(&app, &manifest_url)
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn start_worker(app: AppHandle, state: State<'_, AppRuntimeState>) -> Result<u16, String> {
    start_worker_impl(&app, &state)
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn ensure_runtime_and_worker(
    app: AppHandle,
    state: State<'_, AppRuntimeState>,
    manifest_url: String,
) -> Result<AppOverview, String> {
    ensure_runtime_and_worker_impl(&app, &state, &manifest_url)
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn stop_worker(app: AppHandle, state: State<'_, AppRuntimeState>) -> Result<(), String> {
    stop_worker_impl(&app, &state)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn repair_installation(app: AppHandle, state: State<'_, AppRuntimeState>) -> Result<(), String> {
    repair_installation_impl(&app, &state)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn pick_files() -> Result<Vec<String>, String> {
    let files = rfd::FileDialog::new()
        .add_filter("Documents", &["png", "jpg", "jpeg", "bmp", "webp", "pdf"])
        .set_title("选择需要 OCR 的文件")
        .pick_files()
        .unwrap_or_default();

    Ok(files
        .iter()
        .map(|path| path.to_string_lossy().to_string())
        .collect())
}

#[tauri::command]
fn pick_folder() -> Result<Option<String>, String> {
    Ok(rfd::FileDialog::new()
        .set_title("选择批量 OCR 文件夹")
        .pick_folder()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn open_logs_dir(app: AppHandle) -> Result<(), String> {
    let paths = resolve_app_paths(&app).map_err(|error| error.to_string())?;
    opener::open(paths.logs_dir).map_err(|error| error.to_string())?;
    Ok(())
}

fn get_app_overview_impl(app: &AppHandle, state: &State<'_, AppRuntimeState>) -> AppResult<AppOverview> {
    ensure_base_dirs(app)?;
    let paths = resolve_app_paths(app)?;
    let installed = read_installed_state(app)?;
    let platform = current_platform_label()?;
    let app_version = app.package_info().version.to_string();
    let runtime_installed = runtime_layout_exists(&paths);
    let models_installed = models_layout_exists(&paths, installed.as_ref());
    let bootstrap_required = installed.is_none() || !runtime_installed || !models_installed;
    let worker_running = current_worker_running(state)?;

    Ok(AppOverview {
        platform,
        app_version,
        paths,
        installed,
        runtime_installed,
        models_installed,
        bootstrap_required,
        worker_port: WORKER_PORT,
        worker_running,
    })
}

async fn ensure_runtime_and_worker_impl(
    app: &AppHandle,
    state: &State<'_, AppRuntimeState>,
    manifest_url: &str,
) -> AppResult<AppOverview> {
    let overview = get_app_overview_impl(app, state)?;
    if overview.bootstrap_required {
        bootstrap_install_impl(app, manifest_url).await?;
    }

    emit_progress(
        app,
        "STARTING_WORKER",
        "正在启动本地 OCR 服务",
        Some(0.96),
    )?;
    start_worker_impl(app, state).await?;
    emit_progress(app, "READY", "本地 OCR 服务已就绪", Some(1.0))?;
    get_app_overview_impl(app, state)
}

async fn bootstrap_install_impl(app: &AppHandle, manifest_url: &str) -> AppResult<RuntimeManifest> {
    ensure_base_dirs(app)?;
    let paths = resolve_app_paths(app)?;
    let log_path = Path::new(&paths.logs_dir).join("bootstrap.log");

    emit_progress(app, "CHECKING_MANIFEST", "正在拉取 manifest", Some(0.05))?;
    append_log(
        &log_path,
        &format!("[{}] checking manifest {}", Utc::now().to_rfc3339(), manifest_url),
    )?;

    let manifest = fetch_manifest(manifest_url).await?;
    let platform = current_platform_label()?;
    if manifest.platform != platform {
        return Err(AppError(format!(
            "manifest 平台不匹配，当前是 {}，收到 {}",
            platform, manifest.platform
        )));
    }

    let session_dir = Path::new(&paths.cache_dir)
        .join("downloads")
        .join(Utc::now().format("%Y%m%d%H%M%S").to_string());
    fs::create_dir_all(&session_dir)?;

    emit_progress(
        app,
        "DOWNLOADING_RUNTIME",
        "正在下载 runtime bundle",
        Some(0.12),
    )?;
    let runtime_zip = download_with_progress(
        app,
        &manifest.runtime,
        &session_dir.join("runtime.zip"),
        "DOWNLOADING_RUNTIME",
        0.12,
        0.46,
    )
    .await?;

    emit_progress(app, "VERIFYING", "正在校验 runtime bundle", Some(0.5))?;
    verify_sha256(&runtime_zip, &manifest.runtime.sha256)?;

    emit_progress(app, "UNPACKING", "正在解压 runtime bundle", Some(0.6))?;
    replace_directory(&PathBuf::from(&paths.runtime_dir), &runtime_zip)?;

    let model_count = manifest.models.len().max(1) as f32;
    for (index, model) in manifest.models.iter().enumerate() {
        let start = 0.62 + (index as f32 / model_count) * 0.15;
        let end = 0.77 + (index as f32 / model_count) * 0.15;
        emit_progress(
            app,
            "DOWNLOADING_MODELS",
            &format!("正在下载模型 {}", model.name),
            Some(start),
        )?;
        let model_zip = download_with_progress(
            app,
            &BootstrapResource {
                version: model.version.clone(),
                url: model.url.clone(),
                sha256: model.sha256.clone(),
                size: model.size,
            },
            &session_dir.join(format!("{}.zip", model.name)),
            "DOWNLOADING_MODELS",
            start,
            end,
        )
        .await?;
        verify_sha256(&model_zip, &model.sha256)?;
        replace_directory(
            &PathBuf::from(&paths.models_dir).join(&model.name),
            &model_zip,
        )?;
    }

    emit_progress(app, "INSTALLING", "正在写入安装记录", Some(0.92))?;
    let installed = InstalledState {
        platform,
        app_version: app.package_info().version.to_string(),
        runtime: InstalledComponent {
            version: manifest.runtime.version.clone(),
            installed_at: Utc::now().to_rfc3339(),
        },
        models: manifest
            .models
            .iter()
            .map(|model| InstalledComponentWithName {
                name: model.name.clone(),
                version: model.version.clone(),
                installed_at: Utc::now().to_rfc3339(),
            })
            .collect(),
        manifest_url: manifest_url.to_string(),
    };
    write_installed_state(app, &installed)?;

    emit_progress(
        app,
        "READY",
        "资源安装完成，可以启动 OCR Worker",
        Some(1.0),
    )?;
    append_log(
        &log_path,
        &format!(
            "[{}] installed runtime {} with {} models",
            Utc::now().to_rfc3339(),
            installed.runtime.version,
            installed.models.len()
        ),
    )?;

    Ok(manifest)
}

async fn start_worker_impl(app: &AppHandle, state: &State<'_, AppRuntimeState>) -> AppResult<u16> {
    ensure_base_dirs(app)?;

    if current_worker_running(state)? {
        wait_for_worker_health(WORKER_PORT).await?;
        return Ok(WORKER_PORT);
    }

    let paths = resolve_app_paths(app)?;
    let log_dir = PathBuf::from(&paths.logs_dir);
    fs::create_dir_all(&log_dir)?;
    let worker_log = log_dir.join("worker.log");
    append_log(
        &worker_log,
        &format!("[{}] starting worker", Utc::now().to_rfc3339()),
    )?;

    let (python_executable, worker_script) = resolve_worker_launch_targets(&paths)?;
    let stdout = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&worker_log)?;
    let stderr = stdout.try_clone()?;

    let installed = read_installed_state(app)?;
    let mut command = Command::new(&python_executable);
    command
        .arg(&worker_script)
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(WORKER_PORT.to_string())
        .env("ACME_OCR_HOME", &paths.app_home)
        .env(
            "ACME_OCR_RUNTIME_VERSION",
            installed
                .as_ref()
                .map(|state| state.runtime.version.as_str())
                .unwrap_or("dev"),
        )
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .stdin(Stdio::null());

    let child = command.spawn().map_err(|error| {
        AppError(format!(
            "启动 Worker 失败: {}，python={}, script={}",
            error,
            python_executable.display(),
            worker_script.display()
        ))
    })?;

    {
        let mut worker = state.worker.lock().map_err(|_| AppError("worker 状态锁失败".into()))?;
        *worker = Some(child);
    }

    if let Err(error) = wait_for_worker_health(WORKER_PORT).await {
        let _ = stop_worker_impl(app, state);
        return Err(error);
    }
    Ok(WORKER_PORT)
}

fn stop_worker_impl(app: &AppHandle, state: &State<'_, AppRuntimeState>) -> AppResult<()> {
    let paths = resolve_app_paths(app)?;
    let worker_log = PathBuf::from(&paths.logs_dir).join("worker.log");

    let mut worker = state.worker.lock().map_err(|_| AppError("worker 状态锁失败".into()))?;
    if let Some(child) = worker.as_mut() {
        child.kill()?;
        append_log(
            &worker_log,
            &format!("[{}] worker stopped", Utc::now().to_rfc3339()),
        )?;
    }
    *worker = None;
    Ok(())
}

fn repair_installation_impl(app: &AppHandle, state: &State<'_, AppRuntimeState>) -> AppResult<()> {
    stop_worker_impl(app, state)?;
    let paths = resolve_app_paths(app)?;
    let runtime_dir = PathBuf::from(&paths.runtime_dir);
    let models_dir = PathBuf::from(&paths.models_dir);
    let installed_file = PathBuf::from(&paths.config_dir).join(INSTALLED_FILE);

    if runtime_dir.exists() {
        fs::remove_dir_all(runtime_dir)?;
    }
    if models_dir.exists() {
        fs::remove_dir_all(models_dir)?;
    }
    if installed_file.exists() {
        fs::remove_file(installed_file)?;
    }
    Ok(())
}

fn current_worker_running(state: &State<'_, AppRuntimeState>) -> AppResult<bool> {
    let mut worker = state.worker.lock().map_err(|_| AppError("worker 状态锁失败".into()))?;
    match worker.as_mut() {
        Some(child) => {
            if child.try_wait()?.is_some() {
                *worker = None;
                Ok(false)
            } else {
                Ok(true)
            }
        }
        None => Ok(false),
    }
}

fn resolve_app_paths(app: &AppHandle) -> AppResult<AppPaths> {
    let app_home = app
        .path()
        .app_local_data_dir()
        .map_err(|error| AppError(error.to_string()))?;

    Ok(AppPaths {
        app_home: app_home.to_string_lossy().to_string(),
        runtime_dir: app_home.join("runtime").to_string_lossy().to_string(),
        models_dir: app_home.join("models").to_string_lossy().to_string(),
        data_dir: app_home.join("data").to_string_lossy().to_string(),
        cache_dir: app_home.join("cache").to_string_lossy().to_string(),
        logs_dir: app_home.join("logs").to_string_lossy().to_string(),
        config_dir: app_home.join("config").to_string_lossy().to_string(),
    })
}

fn ensure_base_dirs(app: &AppHandle) -> AppResult<()> {
    let paths = resolve_app_paths(app)?;
    for directory in [
        &paths.runtime_dir,
        &paths.models_dir,
        &paths.data_dir,
        &paths.cache_dir,
        &paths.logs_dir,
        &paths.config_dir,
    ] {
        fs::create_dir_all(directory)?;
    }
    Ok(())
}

fn runtime_layout_exists(paths: &AppPaths) -> bool {
    let runtime_dir = PathBuf::from(&paths.runtime_dir);
    let python_candidates = [
        runtime_dir.join("python").join("python.exe"),
        runtime_dir.join("python").join("bin").join("python3"),
        runtime_dir.join("python").join("bin").join("python"),
    ];
    let has_python = python_candidates.iter().any(|candidate| candidate.exists());
    let has_worker = runtime_dir.join("worker").join("main.py").exists();
    has_python && has_worker
}

fn models_layout_exists(paths: &AppPaths, installed: Option<&InstalledState>) -> bool {
    let models_dir = PathBuf::from(&paths.models_dir);
    if !models_dir.exists() {
        return false;
    }

    if let Some(installed_state) = installed {
        if installed_state.models.is_empty() {
            return false;
        }
        return installed_state
            .models
            .iter()
            .all(|model| models_dir.join(&model.name).exists());
    }

    fs::read_dir(models_dir)
        .map(|mut entries| entries.any(|entry| entry.map(|item| item.path().is_dir()).unwrap_or(false)))
        .unwrap_or(false)
}

fn installed_state_path(app: &AppHandle) -> AppResult<PathBuf> {
    let paths = resolve_app_paths(app)?;
    Ok(PathBuf::from(paths.config_dir).join(INSTALLED_FILE))
}

fn read_installed_state(app: &AppHandle) -> AppResult<Option<InstalledState>> {
    let path = installed_state_path(app)?;
    if !path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(path)?;
    let installed = serde_json::from_str::<InstalledState>(&content)?;
    Ok(Some(installed))
}

fn write_installed_state(app: &AppHandle, installed: &InstalledState) -> AppResult<()> {
    let content = serde_json::to_string_pretty(installed)?;
    fs::write(installed_state_path(app)?, content)?;
    Ok(())
}

fn emit_progress(
    app: &AppHandle,
    stage: &str,
    message: &str,
    progress: Option<f32>,
) -> AppResult<()> {
    app.emit(
        "bootstrap://progress",
        BootstrapProgress {
            stage: stage.to_string(),
            message: message.to_string(),
            progress,
        },
    )
    .map_err(|error| AppError(error.to_string()))
}

fn current_platform_label() -> AppResult<String> {
    let label = match (env::consts::OS, env::consts::ARCH) {
        ("windows", "x86_64") => "windows-x64",
        ("macos", "aarch64") => "darwin-aarch64",
        ("macos", "x86_64") => "darwin-x64",
        _ => {
            return Err(AppError(format!(
                "当前平台暂未支持: {}-{}",
                env::consts::OS,
                env::consts::ARCH
            )))
        }
    };

    Ok(label.to_string())
}

async fn fetch_manifest(manifest_url: &str) -> AppResult<RuntimeManifest> {
    let response = reqwest::get(manifest_url).await?.error_for_status()?;
    let manifest = response.json::<RuntimeManifest>().await?;
    Ok(manifest)
}

async fn download_with_progress(
    app: &AppHandle,
    resource: &BootstrapResource,
    target: &Path,
    stage: &str,
    from: f32,
    to: f32,
) -> AppResult<PathBuf> {
    let response = reqwest::get(&resource.url).await?.error_for_status()?;
    let total = response.content_length().or(resource.size).unwrap_or(0);
    let mut stream = response.bytes_stream();
    let file = File::create(target)?;
    let mut writer = BufWriter::new(file);
    let mut downloaded = 0_u64;

    while let Some(chunk) = stream.next().await {
        let chunk = chunk?;
        writer.write_all(&chunk)?;
        downloaded += chunk.len() as u64;

        if total > 0 {
            let ratio = downloaded as f32 / total as f32;
            let progress = from + (to - from) * ratio.min(1.0);
            emit_progress(
                app,
                stage,
                &format!("下载中 {} ({:.1} MB)", resource.version, downloaded as f32 / 1_048_576.0),
                Some(progress),
            )?;
        }
    }

    writer.flush()?;
    Ok(target.to_path_buf())
}

fn verify_sha256(file: &Path, expected: &str) -> AppResult<()> {
    let mut sha = Sha256::new();
    let mut input = File::open(file)?;
    let mut buffer = [0_u8; 64 * 1024];

    loop {
        let read = input.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        sha.update(&buffer[..read]);
    }

    let actual = format!("{:x}", sha.finalize());
    if actual != expected.to_lowercase() {
        return Err(AppError(format!(
            "SHA-256 校验失败: expected={}, actual={}",
            expected, actual
        )));
    }
    Ok(())
}

fn replace_directory(target_dir: &Path, archive_file: &Path) -> AppResult<()> {
    if target_dir.exists() {
        fs::remove_dir_all(target_dir)?;
    }
    fs::create_dir_all(target_dir)?;
    unzip_archive(archive_file, target_dir)?;
    Ok(())
}

fn unzip_archive(archive_file: &Path, target_dir: &Path) -> AppResult<()> {
    let file = File::open(archive_file)?;
    let mut archive = zip::ZipArchive::new(file)?;

    for index in 0..archive.len() {
        let mut zipped = archive.by_index(index)?;
        let Some(safe_name) = zipped.enclosed_name().map(|path| path.to_owned()) else {
            continue;
        };

        let output_path = target_dir.join(safe_name);
        if zipped.is_dir() {
            fs::create_dir_all(&output_path)?;
            continue;
        }

        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut output = File::create(&output_path)?;
        std::io::copy(&mut zipped, &mut output)?;
    }

    Ok(())
}

fn resolve_worker_launch_targets(paths: &AppPaths) -> AppResult<(PathBuf, PathBuf)> {
    let runtime_dir = PathBuf::from(&paths.runtime_dir);
    let installed_script = runtime_dir.join("worker").join("main.py");
    let fallback_script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../../services/ocr-worker/main.py")
        .canonicalize()
        .context("未找到开发模式 Worker 入口")?;

    let worker_script = if installed_script.exists() {
        installed_script
    } else {
        fallback_script
    };

    let candidates = [
        runtime_dir.join("python").join("python.exe"),
        runtime_dir.join("python").join("bin").join("python3"),
        runtime_dir.join("python").join("bin").join("python"),
    ];

    for candidate in candidates {
        if candidate.exists() {
            return Ok((candidate, worker_script));
        }
    }

    let fallback_python = if cfg!(target_os = "windows") {
        PathBuf::from("python")
    } else {
        PathBuf::from("python3")
    };

    Ok((fallback_python, worker_script))
}

async fn wait_for_worker_health(port: u16) -> AppResult<()> {
    let endpoint = format!("http://127.0.0.1:{}/health", port);

    for _ in 0..30 {
        match reqwest::get(&endpoint).await {
            Ok(response) if response.status().is_success() => return Ok(()),
            _ => tokio::time::sleep(Duration::from_millis(500)).await,
        }
    }

    Err(AppError("Worker 启动超时，/health 未就绪".into()))
}

pub fn run() {
    tauri::Builder::default()
        .manage(AppRuntimeState::default())
        .invoke_handler(tauri::generate_handler![
            get_app_overview,
            bootstrap_install,
            ensure_runtime_and_worker,
            start_worker,
            stop_worker,
            repair_installation,
            pick_files,
            pick_folder,
            open_logs_dir
        ])
        .run(tauri::generate_context!())
        .expect("failed to run AcmeOCR");
}
