# AcmeOCR

基于技术方案实现的本地 OCR 桌面软件代码骨架，目标是支持 Windows 和 macOS：

- 桌面壳：Tauri 2 + React + TypeScript
- 本地 Worker：Python 3.11 + FastAPI
- OCR 引擎：PaddleOCR CPU 版优先
- 首次启动：联网下载 runtime bundle / model bundle
- 后续运行：本地离线 OCR

当前代码已经覆盖以下主链路：

- Tauri 桌面应用骨架
- Windows/macOS 本地目录管理
- manifest 拉取、资源下载、SHA-256 校验、ZIP 解压、`installed.json` 写入
- 本地 Python Worker 启动/停止
- `/health`、`/bootstrap/status`、`/ocr/run`、`/ocr/batch`、`/ocr/jobs/{id}`、`/export`
- SQLite 任务记录
- JSON / CSV / XLSX 导出
- 图片 OCR、PDF 转图 OCR 的 Worker 适配层
- 当运行时未安装 PaddleOCR 时，自动回退到 mock OCR，方便本地联调
- `scripts/build-runtime-bundle/` 可直接构建 Windows/macOS runtime bundle
- `scripts/build-model-bundle/` 可直接从 Paddle 官方模型地址构建 model bundle
- `scripts/generate-manifests/` 可根据已构建产物生成带真实 `sha256/size` 的 release manifest
- 桌面端支持首次启动自动准备运行环境，无需用户手动安装 Python 依赖
- 已提供 GitHub Actions 工作流，可在 macOS Runner 上自动构建 `.dmg`

## 目录结构

```text
acme-ocr/
  apps/
    desktop/
      src/
      src-tauri/
  services/
    ocr-worker/
      app/
      main.py
      requirements.lock
  packages/
    shared-types/
  infra/
    manifests/
  docs/
```

## 平台目录

桌面端通过 Tauri 的 `app_local_data_dir` 统一管理运行时目录：

- Windows: `%LOCALAPPDATA%/com.acme.ocr/`
- macOS: `~/Library/Application Support/com.acme.ocr/`

目录内会创建：

- `runtime/`
- `models/`
- `data/`
- `cache/`
- `logs/`
- `config/`

Worker 侧也支持通过 `ACME_OCR_HOME` 环境变量覆盖目录，确保桌面壳与 Worker 使用同一套路径。

关于为什么推荐“首次启动自动下载 runtime bundle”，而不是让用户自己装 Python 依赖，可以看：

- [运行时交付策略](/Users/zhangmingjie/data/www/ocr/docs/runtime-install-strategy.md)
- [GitHub 自动打包 DMG](/Users/zhangmingjie/data/www/ocr/docs/github-dmg-build.md)

## 开发模式

### 1. 安装前端依赖

```bash
pnpm install
```

### 2. 启动桌面端

```bash
pnpm dev:desktop
```

### 3. 单独启动 Python Worker

如果你还没有制作 runtime bundle，可以直接用系统 Python 启动开发版 Worker：

macOS:

```bash
cd services/ocr-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python main.py --host 127.0.0.1 --port 47861
```

Windows PowerShell:

```powershell
cd services/ocr-worker
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock
python main.py --host 127.0.0.1 --port 47861
```

在这种模式下，Tauri 启动 Worker 时会优先寻找已安装的 runtime；如果没有安装，会回退到仓库里的 `services/ocr-worker/main.py`。

## 自动初始化策略

生产模式建议开启：

```env
VITE_ACME_OCR_AUTO_BOOTSTRAP=true
```

开启后，应用启动时会自动：

1. 检查本地 runtime 和 model 是否完整
2. 如缺失则自动下载并安装
3. 自动启动本地 OCR Worker
4. 成功后直接进入可用状态

这意味着用户不需要单独安装任何 Python 或 OCR 依赖。

## 首次安装资源流

1. 前端调用 Tauri `bootstrap_install`
2. Rust 层读取 manifest
3. 下载 runtime bundle 与 model bundle
4. 执行 SHA-256 校验
5. 解压到本地 `runtime/` 与 `models/`
6. 写入 `config/installed.json`
7. 前端允许用户启动 Worker

## Runtime Bundle 构建

构建脚本位于：

- [build_runtime_bundle.py](/Users/zhangmingjie/data/www/ocr/scripts/build-runtime-bundle/build_runtime_bundle.py)
- [build.sh](/Users/zhangmingjie/data/www/ocr/scripts/build-runtime-bundle/build.sh)
- [build.ps1](/Users/zhangmingjie/data/www/ocr/scripts/build-runtime-bundle/build.ps1)
- [Runtime Bundle Builder](/Users/zhangmingjie/data/www/ocr/scripts/build-runtime-bundle/README.md)
- [build_model_bundle.py](/Users/zhangmingjie/data/www/ocr/scripts/build-model-bundle/build_model_bundle.py)
- [Model Bundle Builder](/Users/zhangmingjie/data/www/ocr/scripts/build-model-bundle/README.md)
- [generate_manifests.py](/Users/zhangmingjie/data/www/ocr/scripts/generate-manifests/generate_manifests.py)
- [Release Manifest Generator](/Users/zhangmingjie/data/www/ocr/scripts/generate-manifests/README.md)

典型命令：

macOS:

```bash
python3 scripts/build-runtime-bundle/build_runtime_bundle.py \
  --version 0.1.0 \
  --python-version 3.11.11 \
  --platform darwin-aarch64
```

Windows:

```powershell
py -3 scripts/build-runtime-bundle/build_runtime_bundle.py `
  --version 0.1.0 `
  --python-version 3.11.11 `
  --platform windows-x64
```

脚本会：

1. 从官方上游获取 Python 运行时
2. 安装 Worker 锁定依赖
3. 复制 `services/ocr-worker` 到 `worker/`
4. 生成 `metadata/runtime-manifest.json`
5. 打包到 `dist/runtime-bundles/*.zip`
6. 输出同名 `.sha256`

模型打包命令：

```bash
python3 scripts/build-model-bundle/build_model_bundle.py \
  --version 0.1.0 \
  --model-key ppocr-zh
```

该脚本会从 Paddle 官方模型地址下载模型，并整理成 `det/rec/cls` 目录后打包。

manifest 生成命令：

```bash
python3 scripts/generate-manifests/generate_manifests.py \
  --owner mingjiezhang2026 \
  --repo acme-ocr \
  --tag v0.1.0 \
  --app-version 0.1.0 \
  --runtime darwin-aarch64=dist/runtime-bundles/runtime-bundle-darwin-aarch64-0.1.0.zip \
  --model ppocr-zh=dist/model-bundles/model-bundle-ppocr-zh-0.1.0.zip
```

manifest 示例放在：

- [windows-x64.json](/Users/zhangmingjie/data/www/ocr/infra/manifests/windows-x64.json)
- [darwin-x64.json](/Users/zhangmingjie/data/www/ocr/infra/manifests/darwin-x64.json)
- [darwin-aarch64.json](/Users/zhangmingjie/data/www/ocr/infra/manifests/darwin-aarch64.json)

## 生产打包建议

### Windows

- 产出 Tauri MSI 安装包
- 运行时包内放置：
  - `python/python.exe`
  - `worker/main.py`
  - PaddleOCR CPU 依赖
- manifest 使用 `windows-x64.json`

### macOS

- 产出 Tauri DMG / `.app`
- 运行时包内放置：
  - `python/bin/python3`
  - `worker/main.py`
  - PaddleOCR CPU 依赖
- manifest 根据芯片选择 `darwin-x64.json` 或 `darwin-aarch64.json`

## 关键实现文件

- 前端入口：[App.tsx](/Users/zhangmingjie/data/www/ocr/apps/desktop/src/App.tsx)
- Tauri 系统层：[lib.rs](/Users/zhangmingjie/data/www/ocr/apps/desktop/src-tauri/src/lib.rs)
- Worker 入口：[main.py](/Users/zhangmingjie/data/www/ocr/services/ocr-worker/main.py)
- OCR 任务管理：[job_service.py](/Users/zhangmingjie/data/www/ocr/services/ocr-worker/app/services/job_service.py)
- Paddle 适配层：[paddle_adapter.py](/Users/zhangmingjie/data/www/ocr/services/ocr-worker/app/engine/paddle_adapter.py)
- 文件预处理与 PDF 渲染：[file_processor.py](/Users/zhangmingjie/data/www/ocr/services/ocr-worker/app/services/file_processor.py)
- 导出服务：[export_service.py](/Users/zhangmingjie/data/www/ocr/services/ocr-worker/app/services/export_service.py)
- Runtime 构建脚本：[build_runtime_bundle.py](/Users/zhangmingjie/data/www/ocr/scripts/build-runtime-bundle/build_runtime_bundle.py)
- Model 构建脚本：[build_model_bundle.py](/Users/zhangmingjie/data/www/ocr/scripts/build-model-bundle/build_model_bundle.py)
- Manifest 生成脚本：[generate_manifests.py](/Users/zhangmingjie/data/www/ocr/scripts/generate-manifests/generate_manifests.py)

## 当前约束

- 还没有接入 Tauri updater
- 还没有做断点续传
- 还没有做日志一键打包
- 表格增强和版面分析仍是预留开关
- `runtime bundle` 目前基于 `venv` 结构，生产版建议替换成可重定位 Python

## 下一步建议

1. 用真实 CDN 地址与 SHA-256 更新 `infra/manifests/*.json`
2. 在 Worker 里补任务历史列表与更细的批量进度
3. 对 PDF 转图链路做大文件与多页性能优化
4. 为 runtime bundle 构建流程补 CI job 和 wheelhouse 缓存
