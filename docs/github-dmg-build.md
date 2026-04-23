# GitHub 自动打包 DMG

## 结论

可以，不需要你本机手动安装完整打包环境，也不需要 Git CLI 参与构建。

推荐做法是：

- 代码推到 GitHub
- GitHub Actions 使用 macOS Runner
- 自动安装 `pnpm`
- 自动安装 Rust
- 构建 runtime bundle
- 构建 model bundle
- 生成带真实 `sha256/size` 的 manifest
- 执行 Tauri 构建
- 产出 `.dmg`
- 将 `.dmg`、bundle、manifest 一起上传到 GitHub Release

## 当前仓库中的 workflow

已添加：

- [.github/workflows/build-dmg.yml](/Users/zhangmingjie/data/www/ocr/.github/workflows/build-dmg.yml)

它会在以下场景执行：

- 手动触发 `workflow_dispatch`
- 推送 tag，如 `v0.1.0`

## 产物

workflow 会上传并发布：

- `apps/desktop/src-tauri/target/release/bundle/dmg/*.dmg`
- `runtime-bundle-darwin-aarch64-<version>.zip`
- `model-bundle-ppocr-zh-<version>.zip`
- `darwin-aarch64.json`

你可以在 GitHub Actions 的构建结果页直接下载 artifact，也可以在对应 GitHub Release 页面下载这些正式资源。

## 使用方式

### 手动触发

1. 把仓库推到 GitHub：`mingjiezhang2026/acme-ocr`
2. 打开 GitHub 仓库的 `Actions`
3. 选择 `Build macOS DMG`
4. 输入：
   - `release_tag`
   - `app_version`
5. 点击 `Run workflow`
6. 等待构建完成后在：
   - Actions artifact 页面下载
   - 或对应 Release 页面下载

### 通过版本标签触发

如果以后你把仓库变成真正的 Git 仓库，也可以在本地打 tag：

```bash
git tag v0.1.0
git push origin v0.1.0
```

然后 GitHub 会自动构建 `.dmg`。

## 注意事项

- 当前 workflow 以 `darwin-aarch64` 为主，也就是 Apple Silicon 版本
- 生成的 `.dmg` 在构建时会把 manifest URL 指向同一个 GitHub Release 下的 `darwin-aarch64.json`
- 也就是说，安装后的应用首次打开时，会自动从同一条 Release 链路下载 runtime/model 资源
- workflow 里固定传入了 `python-build-standalone` 的官方 asset 直链，避免匿名 GitHub API 查询触发 rate limit
- 如果以后要支持 Intel Mac，可以再补 `darwin-x64` 的构建 job

## 一句话

GitHub 上自动打包 `.dmg` 是完全可行的，而且比在本机手动配环境更稳。
