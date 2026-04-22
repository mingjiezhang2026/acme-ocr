# Runtime Bundle Builder

这个目录用于构建 AcmeOCR 的 `runtime bundle`。

升级后，脚本支持从官方上游自动获取 Python 运行时：

- Windows：默认使用 Python 官方 embeddable package
- macOS：默认使用 `python-build-standalone` 官方 release 资产

产物结构如下：

```text
runtime-bundle-<platform>-<version>.zip
  python/
  worker/
  metadata/
    runtime-manifest.json
```

脚本完成的工作：

1. 获取官方上游 Python 运行时
2. 安装 `services/ocr-worker/requirements.lock`
3. 复制 `services/ocr-worker` 到 `worker/`
4. 生成 `metadata/runtime-manifest.json`
5. 打 zip 包
6. 输出 `.sha256`

## macOS

```bash
python3 scripts/build-runtime-bundle/build_runtime_bundle.py \
  --version 0.1.0 \
  --python-version 3.11 \
  --platform darwin-aarch64
```

## Windows

```powershell
py -3 scripts/build-runtime-bundle/build_runtime_bundle.py `
  --version 0.1.0 `
  --python-version 3.11 `
  --platform windows-x64
```

## 可选 provider

```bash
python3 scripts/build-runtime-bundle/build_runtime_bundle.py \
  --version 0.1.0 \
  --platform darwin-aarch64 \
  --python-provider python-build-standalone
```

```powershell
py -3 scripts/build-runtime-bundle/build_runtime_bundle.py `
  --version 0.1.0 `
  --platform windows-x64 `
  --python-provider python-org-embed
```

## 离线 wheelhouse

```bash
python3 scripts/build-runtime-bundle/build_runtime_bundle.py \
  --version 0.1.0 \
  --platform darwin-aarch64 \
  --wheelhouse ./wheelhouse
```

## 说明

- `auto` 模式下，Windows 默认选 `python-org-embed`，macOS 默认选 `python-build-standalone`
- 如果你只想本地调试，也可以继续使用 `--python-provider local-venv`
- 正式发布时，更推荐继续使用可分发上游运行时，而不是依赖构建机本地 Python
