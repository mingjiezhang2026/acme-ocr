# 运行时交付策略

## 目标

用户安装桌面软件后，不需要单独安装：

- Python
- PaddleOCR
- PaddlePaddle
- PyMuPDF
- openpyxl
- 其他任何命令行依赖

用户只需要：

1. 安装桌面壳
2. 打开应用
3. 等待应用自动准备运行环境
4. 直接使用 OCR

## 方案对比

### 方案 A：首次启动时在线 `pip install`

不推荐。

问题：

- 依赖下载慢
- 终端网络环境不可控
- 原生库安装容易失败
- Windows/macOS 差异大
- 用户机器缺少编译条件时会直接报错
- 版本不可控，问题难排查

### 方案 B：安装包直接内置全部 Python 运行时和模型

可行，但不适合作为默认分发方案。

优点：

- 用户安装后可直接离线使用
- 不依赖首次联网

缺点：

- 安装包非常大
- 更新 runtime 和模型成本高
- 分发压力更大

### 方案 C：小安装包 + 首次启动自动下载预构建 runtime bundle

推荐作为默认方案。

优点：

- 用户不需要手动安装任何依赖
- 安装包小
- 运行时和模型可独立更新
- 成功率比在线 `pip install` 高得多
- 桌面端只负责下载、校验、解压、启动

缺点：

- 首次启动需要联网
- 需要你维护 runtime bundle 和 manifest

## 推荐结论

默认采用：

- 小安装包
- 首次启动自动下载 `runtime bundle`
- 首次启动自动下载 `model bundle`
- 自动校验 SHA-256
- 自动解压到本地应用目录
- 自动启动本地 Worker

企业或内网客户可以额外提供：

- 离线完整安装包

## 用户感知

对用户来说，这个过程不是“安装 Python 依赖”，而是：

- “应用正在初始化 OCR 运行环境”

这也是桌面软件更合理的产品表达。

## 当前仓库中的实现

当前代码已经按这个方案落地：

- Tauri 侧：
  - 下载 manifest
  - 下载 runtime bundle / model bundle
  - 校验 SHA-256
  - 解压到本地目录
  - 启动 Worker
  - `ensure_runtime_and_worker` 负责首次启动自动安装与后续自检

- Worker 侧：
  - 从本地 `runtime/` 与 `models/` 启动
  - 不要求用户机器预装 Python
  - 不要求用户手动安装 PaddleOCR

## 运行时目录建议

```text
<app_local_data_dir>/
  runtime/
    python/
    worker/
  models/
    ppocr-zh/
  data/
  cache/
  logs/
  config/
```

## 构建建议

### 开发/内测阶段

- 用当前的 `venv` 版 runtime bundle 构建脚本
- 快速验证链路

### 正式发布阶段

- 将 `venv` 版 bundle 升级为更稳定的可重定位 Python 运行时
- 保留当前的 manifest、下载、校验、解压、启动逻辑

## 一句话结论

不要让用户自己安装依赖。  
让应用在首次启动时自动下载并安装你预构建好的运行时，这才是最合理的方案。
