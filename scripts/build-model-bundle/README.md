# Model Bundle Builder

这个目录用于从 Paddle 官方模型地址下载推理模型并打包成 AcmeOCR 可直接消费的 `model bundle`。

产物结构如下：

```text
model-bundle-<model-key>-<version>.zip
  det/
  rec/
  cls/
  metadata/
    model-manifest.json
```

默认模型目录映射来自：

- [paddle_model_catalog.json](/Users/zhangmingjie/data/www/ocr/scripts/build-model-bundle/paddle_model_catalog.json)

## macOS / Linux

```bash
python3 scripts/build-model-bundle/build_model_bundle.py \
  --version 0.1.0 \
  --model-key ppocr-zh
```

## Windows

```powershell
py -3 scripts/build-model-bundle/build_model_bundle.py `
  --version 0.1.0 `
  --model-key ppocr-zh
```

脚本会：

1. 从 Paddle 官方 URL 下载模型归档
2. 解压并整理成 `det/`、`rec/`、`cls/` 目录
3. 生成 `metadata/model-manifest.json`
4. 打包成 zip
5. 输出同名 `.sha256`
