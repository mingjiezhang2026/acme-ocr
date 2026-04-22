# Release Manifest Generator

这个脚本会根据你已经构建好的 runtime/model zip 资产，自动生成带有：

- GitHub Release 下载 URL
- `sha256`
- `size`

的 manifest 文件。

## 用法

```bash
python3 scripts/generate-manifests/generate_manifests.py \
  --owner mingjiezhang2026 \
  --repo acme-ocr \
  --tag v0.1.0 \
  --app-version 0.1.0 \
  --runtime darwin-aarch64=dist/runtime-bundles/runtime-bundle-darwin-aarch64-0.1.0.zip \
  --model ppocr-zh=dist/model-bundles/model-bundle-ppocr-zh-0.1.0.zip
```

输出目录默认是：

```text
dist/release-manifests/
```
