# 本地 OCR 桌面软件技术方案（可直接交给 Codex 实现）

## 1. 目标

构建一个**本地运行、首次启动联网下载运行时/模型/依赖、后续可离线使用**的 OCR 桌面软件，满足以下约束：

1. **安装包尽量小**：安装器只包含桌面壳、启动器、基础 UI，不内置完整 OCR 运行时与模型。
2. **首次使用联网**：首次启动时自动下载运行时包、依赖包、模型包。
3. **后续离线运行**：下载完成后，本地 OCR 不依赖公网。
4. **面向 MAC/Windows 优先**：第一期仅支持需要支持windows 和 MAC系统。
5. **以 CPU 版为主**：先做 CPU 版，降低部署和兼容性复杂度；GPU 作为企业增强版。
6. **可直接交给 Codex 开发**：文档包含目录结构、接口、模块边界、关键流程和 Codex 提示词。

---

## 2. 方案总览

### 2.1 推荐技术栈

- **桌面端壳**：Tauri 2 + React + TypeScript
- **本地 OCR 服务**：Python 3.11 + FastAPI
- **OCR 引擎**：PaddleOCR（CPU 版优先）
- **本地数据库**：SQLite
- **任务执行**：Python asyncio + 轻量任务队列
- **配置与日志**：JSON/YAML + 本地滚动日志
- **更新机制**：
  - 应用壳更新：Tauri updater
  - OCR 运行时/模型更新：自定义 manifest + 版本化资源包
- **资源下载**：对象存储/CDN（阿里云 OSS、腾讯云 COS、七牛、S3 均可）
- **完整性校验**：SHA-256 + 可选签名校验

### 2.2 架构原则

采用**双进程架构**：

1. **桌面主应用（Tauri）**
   - 负责 UI、文件选择、设置、任务发起、结果展示、升级。
2. **本地 OCR Worker（Python）**
   - 负责模型加载、OCR 推理、PDF/图片处理、结构化输出。

这样做的原因：

- OCR 生态更适合 Python；
- 桌面壳用 Tauri 更轻；
- UI 与 OCR 运行时解耦，升级和替换成本低；
- 后期可把 OCR Worker 独立成局域网服务版。

---

## 3. 为什么选这个架构

## 3.1 不建议直接做成单体 Python 桌面程序

不推荐第一版直接使用 PyInstaller + Tkinter / PySide 把全部内容打成一个安装包，原因：

- 安装包大；
- Paddle 相关依赖体积大；
- 首次安装慢，失败率高；
- 增量更新体验差；
- 后续多语言前端和企业功能扩展不灵活。

## 3.2 不建议要求终端用户安装 Docker

虽然 Docker 很适合开发和 CI，但桌面用户通常不会预装 Docker，也不适合作为通用本地软件前提条件。

因此本方案中的“镜像”**不使用 Docker 镜像作为终端运行依赖**，而采用：

- **运行时资源包（runtime bundle）**
- **模型资源包（model bundle）**
- **依赖镜像源/自建 wheelhouse**

也就是说，用户感知上是“首次启动联网下载镜像和依赖”，但工程实现上是**下载预构建运行时包**，而不是要求用户装 Docker。

---

## 4. 交付形态

## 4.1 终端用户安装包

安装包内仅包含：

- Tauri 桌面程序
- Bootstrap 启动器
- 基础前端资源
- 基础配置模板
- 下载管理器
- 本地空数据库模板

### 目标

安装包控制在较小体积，便于分发和更新。

## 4.2 首次启动下载的资源

首次启动时下载以下资源：

1. **Python Runtime Bundle**
   - 预构建 Python 运行环境
   - 已锁版本的核心依赖
   - PaddlePaddle CPU 版本
   - PaddleOCR 版本
   - 基础三方库（numpy、opencv、fastapi、uvicorn 等）

2. **OCR Model Bundle**
   - 文本检测模型
   - 文本识别模型
   - 方向分类模型
   - 可选表格模型/版面模型

3. **Optional Feature Bundle**
   - PDF 预处理工具
   - 表格解析增强模块
   - 文档结构化增强模块

4. **Manifest 文件**
   - 版本号
   - 下载地址
   - sha256
   - 平台信息
   - 兼容关系
   - 更新策略

---

## 5. 整体架构

```text
┌──────────────────────────────────────────────────────┐
│                  Tauri Desktop App                  │
│  React UI                                           │
│  - 文件导入                                         │
│  - 首次安装向导                                     │
│  - OCR 任务发起                                     │
│  - 结果预览/校对/导出                               │
│  - 设置/升级/日志                                   │
└───────────────┬──────────────────────────────────────┘
                │ localhost HTTP / IPC
                ▼
┌──────────────────────────────────────────────────────┐
│               Local OCR Worker (Python)             │
│  FastAPI                                             │
│  - /health                                           │
│  - /bootstrap/status                                 │
│  - /ocr/run                                          │
│  - /ocr/batch                                        │
│  - /export                                           │
│  - /models/status                                    │
│  - /settings                                         │
└───────────────┬──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│                Local Data & Runtime Layer           │
│  %LOCALAPPDATA%/AcmeOCR/                             │
│  - runtime/                                          │
│  - models/                                           │
│  - data/                                             │
│  - cache/                                            │
│  - logs/                                             │
│  - config/                                           │
└──────────────────────────────────────────────────────┘

首次联网下载：
CDN / 对象存储
- manifest.json
- runtime-bundle-win-x64-v1.0.0.zip
- model-bundle-ppocr-cn-v1.0.0.zip
- feature-bundle-table-v1.0.0.zip
```

---

## 6. 首次安装与启动流程

## 6.1 启动状态机

定义以下状态：

- `NOT_INITIALIZED`
- `CHECKING_MANIFEST`
- `DOWNLOADING_RUNTIME`
- `DOWNLOADING_MODELS`
- `VERIFYING`
- `UNPACKING`
- `INSTALLING`
- `STARTING_WORKER`
- `READY`
- `FAILED`

## 6.2 首次启动流程

1. 用户安装并打开桌面软件。
2. Tauri 应用检测本地 `runtime/` 是否存在可用版本。
3. 若不存在，进入首次安装向导。
4. 请求远端 `manifest.json`。
5. 根据平台匹配资源包：
   - `win-x64`
   - `runtimeVersion`
   - `modelVersion`
6. 下载资源到临时目录。
7. 校验 sha256。
8. 解压到 `%LOCALAPPDATA%/AcmeOCR/`。
9. 生成本地 `installed.json`。
10. 启动 Python OCR Worker。
11. 通过 `/health` 轮询健康状态。
12. 进入主界面。

## 6.3 断点续传与失败恢复

必须支持：

- 下载中断后重试
- 校验失败自动删除坏包并重下
- 解压失败回滚
- 运行时版本不兼容时提示修复安装
- 手动“重新安装运行时”按钮

---

## 7. 资源发布设计

## 7.1 远端目录建议

```text
/releases/
  app/
    windows/
      latest.json
      app-1.0.0-x64.msi
  runtime/
    windows/
      x64/
        runtime-bundle-1.0.0.zip
        runtime-bundle-1.0.0.zip.sha256
  models/
    ppocr/
      zh/
        model-bundle-1.0.0.zip
        model-bundle-1.0.0.zip.sha256
      en/
        model-bundle-1.0.0.zip
  features/
    table/
      table-bundle-1.0.0.zip
  manifest/
    windows-x64.json
```

## 7.2 Manifest 示例

```json
{
  "platform": "windows-x64",
  "appVersion": "1.0.0",
  "runtime": {
    "version": "1.0.0",
    "url": "https://cdn.example.com/runtime/windows/x64/runtime-bundle-1.0.0.zip",
    "sha256": "REPLACE_ME",
    "size": 0
  },
  "models": [
    {
      "name": "ppocr-zh",
      "version": "1.0.0",
      "url": "https://cdn.example.com/models/ppocr/zh/model-bundle-1.0.0.zip",
      "sha256": "REPLACE_ME",
      "size": 0
    }
  ],
  "features": [],
  "minAppVersion": "1.0.0"
}
```

---

## 8. 本地目录设计

Windows 下使用：

```text
%LOCALAPPDATA%/AcmeOCR/
  app/
  runtime/
    python/
    site-packages/
    worker/
  models/
    ppocr-zh/
  data/
    app.db
    jobs/
    exports/
  cache/
    downloads/
    previews/
    thumbnails/
  logs/
    app.log
    worker.log
    bootstrap.log
  config/
    settings.json
    installed.json
```

说明：

- `runtime/`：运行时包和 Python worker
- `models/`：OCR 模型
- `data/`：业务数据、导出结果
- `cache/`：临时文件与预览
- `logs/`：分模块日志
- `config/`：设置和安装记录

---

## 9. 模块设计

## 9.1 桌面端模块

### A. Bootstrap 模块
职责：

- 拉取 manifest
- 下载资源
- 校验 sha256
- 解压与安装
- 版本检查
- 修复安装

### B. OCR 任务模块
职责：

- 文件选择
- 批量导入
- 调用本地 OCR Worker
- 显示任务进度
- 展示结果

### C. 导出模块
职责：

- 导出 TXT / JSON / CSV / XLSX
- 导出原图高亮结果
- 批量导出

### D. 设置模块
职责：

- 语言
- 默认导出目录
- OCR 模式（快速/准确）
- 是否自动检查更新
- 本地缓存上限

### E. 升级模块
职责：

- 应用壳升级
- 运行时包升级
- 模型升级

## 9.2 Python OCR Worker 模块

### A. API 层
FastAPI 提供本地 HTTP 接口。

### B. Bootstrap Service
检查本地模型与依赖。

### C. OCR Engine Adapter
封装 PaddleOCR 调用，屏蔽版本差异。

### D. File Processor
支持：
- jpg / png / jpeg / bmp / webp
- 单页 PDF
- 多页 PDF

### E. Result Normalizer
统一输出格式：
- 文本块
- 坐标
- 置信度
- 页码
- 方向信息

### F. Export Service
输出 JSON/CSV/TXT/XLSX。

### G. Job Manager
管理批量任务、取消、重试、历史记录。

---

## 10. 关键流程设计

## 10.1 OCR 单文件流程

```text
选择文件
→ 计算文件指纹
→ 保存任务记录
→ 调用 /ocr/run
→ 预处理文件
→ OCR 推理
→ 结构化结果归一化
→ 保存结果到 SQLite / JSON
→ 返回前端展示
→ 用户校对
→ 导出
```

## 10.2 批量处理流程

```text
选择文件夹
→ 递归扫描支持文件
→ 生成任务队列
→ 控制并发数
→ 逐个推理
→ 失败项记录
→ 支持重试失败任务
→ 批量导出汇总结果
```

---

## 11. 本地 API 设计

## 11.1 健康检查

### GET /health

响应：

```json
{
  "status": "ok",
  "runtimeVersion": "1.0.0",
  "modelStatus": "ready"
}
```

## 11.2 安装状态

### GET /bootstrap/status

```json
{
  "initialized": true,
  "runtimeInstalled": true,
  "modelsInstalled": true,
  "versions": {
    "runtime": "1.0.0",
    "ppocrZh": "1.0.0"
  }
}
```

## 11.3 单文件 OCR

### POST /ocr/run

请求：

```json
{
  "filePath": "C:\\Users\\me\\Desktop\\sample.pdf",
  "options": {
    "language": "zh",
    "detectOrientation": true,
    "enableTable": false,
    "outputFormat": "json"
  }
}
```

响应：

```json
{
  "jobId": "job_001",
  "status": "completed",
  "result": {
    "pages": [
      {
        "page": 1,
        "blocks": [
          {
            "text": "示例文本",
            "score": 0.98,
            "box": [[0,0],[100,0],[100,20],[0,20]]
          }
        ]
      }
    ]
  }
}
```

## 11.4 批量 OCR

### POST /ocr/batch

### GET /ocr/jobs/{jobId}

### POST /ocr/jobs/{jobId}/cancel

## 11.5 导出

### POST /export

请求：

```json
{
  "jobId": "job_001",
  "format": "xlsx",
  "targetPath": "C:\\Users\\me\\Documents\\export.xlsx"
}
```

---

## 12. 数据库设计（SQLite）

建议最小表结构：

### jobs

- id
- status
- file_path
- file_hash
- created_at
- updated_at
- error_message

### job_results

- id
- job_id
- page_no
- result_json

### exports

- id
- job_id
- format
- target_path
- created_at

### app_settings

- key
- value

---

## 13. 运行时包策略（核心）

这是本方案最关键的部分。

## 13.1 不建议首次启动时直接在线 pip 安装公网依赖

不要在终端用户机器上执行类似：

```bash
pip install paddleocr paddlepaddle fastapi uvicorn opencv-python
```

原因：

- 下载慢；
- 容易失败；
- 依赖版本不可控；
- 某些包在用户网络环境中可能安装异常；
- 终端机器缺少编译工具时会报错。

## 13.2 推荐方案：预构建 Runtime Bundle

在 CI 中预构建一个稳定运行时包：

```text
runtime-bundle-1.0.0.zip
  /python/
  /Lib/site-packages/
  /worker/
  /scripts/
```

其中包含：

- 固定版本 Python
- 固定版本 paddlepaddle
- 固定版本 paddleocr
- 固定版本 fastapi/uvicorn
- 所需动态库与脚本

终端用户首次启动时只做：

1. 下载 zip
2. 校验
3. 解压
4. 启动 `python worker/main.py`

### 好处

- 首次安装成功率高
- 问题定位容易
- 版本统一
- 不依赖用户本机 Python 环境

## 13.3 依赖镜像策略

CI 或构建机从官方源拉依赖后，生成：

- 自有 wheelhouse
- 自有 runtime bundle
- 自有 model bundle

生产环境只从**自有 CDN**下载，不从公网 pip 临时装包。

这能显著提升成功率与可控性。

---

## 14. 模型包策略

## 14.1 默认模型组合

第一版建议只支持：

- 中文通用 OCR
- 图片 OCR
- PDF OCR（通过页转图）

不建议第一版就加入：

- 多语言大而全模型
- 复杂表格恢复
- 版面分析全家桶
- 大模型理解能力

## 14.2 模型下载策略

模型单独打包，版本独立于应用壳。

优点：

- 可以热更新模型
- 不必重新发安装包
- 支持增量增加语种

---

## 15. PDF 支持策略

第一版建议：

- 支持图片型 PDF
- 支持单页与多页 PDF
- 通过本地页渲染转图片再进入 OCR

不建议第一版承诺：

- 完整可编辑 PDF 语义还原
- 复杂扫描件自动纠偏到极致
- 高精度表格结构恢复

---

## 16. 日志、监控与诊断

本地软件必须内建诊断能力。

建议至少包含：

- `bootstrap.log`：安装下载日志
- `worker.log`：OCR 服务日志
- `app.log`：前端行为与错误日志

必须支持：

- 一键导出日志包
- 错误码体系
- 下载失败错误提示
- 模型缺失检测
- 运行时损坏修复

---

## 17. 更新策略

## 17.1 应用壳更新

使用 Tauri updater，负责：

- 桌面壳二进制更新
- UI 资源更新
- 更新提醒

## 17.2 运行时更新

自定义检查机制：

1. 比较本地 `installed.json` 与远端 manifest。
2. 若 runtime 版本落后，则提示下载新版。
3. 下载新 runtime 到临时目录。
4. 停止 Worker。
5. 原子替换目录。
6. 重启 Worker。

## 17.3 模型更新

模型单独更新，可在设置页中触发“检查新模型”。

---

## 18. 安全要求

1. 下载资源必须做 sha256 校验。
2. 可选增加签名校验。
3. 本地 HTTP 服务仅监听 `127.0.0.1`。
4. 所有文件路径做白名单检查。
5. 限制可访问目录，防止任意文件读取。
6. 导出目录权限校验。
7. 日志避免写入敏感全文内容。
8. Manifest 下载建议走 HTTPS。

---

## 19. MVP 范围（建议）

### 第一版必须做

- Windows 桌面端
- 首次联网下载运行时和模型
- 本地图像/PDF OCR
- 单文件与批量处理
- 结果预览
- JSON/CSV/XLSX 导出
- 更新与修复安装
- 日志导出

### 第一版不要做

- 账户系统
- 云同步
- GPU 自动适配
- 多语言复杂模型自动切换
- 大模型总结/问答
- 插件系统
- 多人协作

---

## 20. 里程碑

## M1：可运行骨架（1 周）
- Tauri 主壳
- React 页面骨架
- FastAPI Worker 骨架
- localhost 通信跑通

## M2：Bootstrap（1 周）
- manifest 拉取
- 下载、校验、解压
- 首次安装流程跑通

## M3：OCR 核心（1~2 周）
- PaddleOCR 接入
- 图片 OCR
- PDF OCR
- 单文件结果展示

## M4：批量与导出（1 周）
- 批量队列
- 导出 JSON/CSV/XLSX
- 任务历史

## M5：更新与修复（1 周）
- 运行时更新
- 模型更新
- 修复安装
- 日志打包

---

## 21. 建议仓库结构

```text
acme-ocr/
  apps/
    desktop/
      src/
      src-tauri/
      package.json
  services/
    ocr-worker/
      app/
        api/
        core/
        engine/
        models/
        services/
        utils/
      main.py
      requirements.lock
  packages/
    shared-types/
  scripts/
    build-runtime-bundle/
    build-model-bundle/
    publish-release/
  infra/
    manifests/
    release-notes/
  docs/
    technical-solution.md
```

---

## 22. 构建与发布策略

## 22.1 CI 任务拆分

### Job A：构建桌面壳
输出：
- `AcmeOCR-Setup-1.0.0-x64.msi`

### Job B：构建 Runtime Bundle
输出：
- `runtime-bundle-1.0.0.zip`

### Job C：构建 Model Bundle
输出：
- `model-bundle-1.0.0.zip`

### Job D：生成 Manifest
输出：
- `windows-x64.json`

### Job E：发布到 CDN
上传：
- 安装包
- runtime
- models
- manifest

---

## 23. 开发阶段的关键决策

### 决策 1：优先 CPU，不做 GPU
原因：降低首次部署复杂度。

### 决策 2：优先本地单机，不做账号系统
原因：先验证安装与 OCR 主链路。

### 决策 3：先做 OCR，不做文档理解
原因：避免范围失控。

### 决策 4：运行时与模型独立版本化
原因：方便后续更新和问题隔离。

---

## 24. 风险与规避

### 风险 1：Paddle 依赖体积仍然较大
规避：
- 只发 CPU 包
- 只发中文基础模型
- 运行时与模型拆包

### 风险 2：首次下载失败
规避：
- 断点续传
- 多 CDN 源
- 重试机制
- 手动导入离线包

### 风险 3：Windows 环境差异
规避：
- 使用预构建 runtime bundle
- 不依赖用户本机 Python
- 做启动前自检

### 风险 4：升级破坏已有运行时
规避：
- 双目录安装
- 切换成功后再清理旧版本
- 保留回滚入口

---

## 25. 给 Codex 的主提示词（可直接使用）

将下面整段直接发给 Codex：

```text
你现在是资深桌面端与本地 AI 工程师，请按以下要求生成可运行项目代码，不要只给示例，要给完整项目骨架、关键实现代码、README、运行脚本和必要注释。

项目名称：AcmeOCR

目标：
开发一个 Windows 本地 OCR 桌面软件，使用 Tauri 2 + React + TypeScript 作为桌面前端壳，使用 Python 3.11 + FastAPI + PaddleOCR 作为本地 OCR Worker。软件安装包应尽量小，首次启动时联网下载 runtime bundle 和 model bundle，下载完成后可离线运行 OCR。

功能要求：
1. 首次启动检测本地 runtime 和 models 是否存在；
2. 若不存在，则进入安装向导；
3. 从远端 manifest 地址拉取 windows-x64.json；
4. 下载 runtime-bundle.zip 和 model-bundle.zip；
5. 校验 sha256；
6. 解压到 %LOCALAPPDATA%/AcmeOCR/ 对应目录；
7. 启动本地 Python OCR Worker；
8. 前端通过 localhost HTTP 调用 Worker；
9. 支持图片和 PDF OCR；
10. 支持单文件与批量处理；
11. 支持结果预览；
12. 支持 JSON/CSV/XLSX 导出；
13. 支持日志输出；
14. 支持检查更新和修复安装。

技术约束：
- 前端：React + TypeScript
- 桌面壳：Tauri 2
- OCR Worker：Python 3.11 + FastAPI
- OCR 引擎：PaddleOCR CPU
- 数据库存储：SQLite
- 配置：JSON
- 只监听 127.0.0.1
- 使用模块化目录结构
- 为关键代码补充注释
- 提供 .env.example 和 manifest 示例
- 提供开发模式与生产模式说明

请输出：
1. 仓库目录树
2. 每个核心文件的代码
3. 前端页面代码
4. Python Worker 代码
5. Bootstrap 下载与校验逻辑
6. 本地数据库初始化代码
7. 导出模块代码
8. README
9. 打包与运行说明
10. 后续待办列表

如果内容过长，请按阶段持续输出，不要省略关键文件。
```

---

## 26. 给 Codex 的分阶段提示词

## 阶段 1：先搭项目骨架

```text
请先生成 AcmeOCR 的完整仓库骨架，包含：
- Tauri 2 + React + TypeScript 桌面端
- Python FastAPI OCR Worker
- SQLite 初始化
- localhost 通信
- 一个最小可运行页面：选择文件并调用 /health
先不要加入真实 PaddleOCR 推理，只要把骨架和调用链路跑通。
```

## 阶段 2：补 Bootstrap

```text
请在现有项目基础上实现首次启动安装流程：
- 读取远端 manifest
- 下载 runtime bundle 与 model bundle
- 校验 sha256
- 解压到 %LOCALAPPDATA%/AcmeOCR/
- 写入 installed.json
- 提供安装进度 UI
请给出完整代码与目录变更。
```

## 阶段 3：补 PaddleOCR

```text
请在 Python Worker 中接入 PaddleOCR CPU 版，实现：
- 图片 OCR
- PDF 每页转图 OCR
- 输出统一 JSON 结构
- 结果保存到 SQLite
- 返回前端可展示的结构
请给出完整代码和依赖说明。
```

## 阶段 4：补批量与导出

```text
请继续补充：
- 批量 OCR 队列
- 取消任务
- 失败重试
- JSON/CSV/XLSX 导出
- 任务历史记录页面
请保持现有目录结构不变，直接生成新增和修改代码。
```

---

## 27. 结论

本方案最核心的价值在于：

- **安装包小**
- **首次启动联网拉取运行时/模型**
- **后续本地离线 OCR**
- **架构清晰，适合用 Codex 直接落地**

如果后续要商业化，建议按这个路径演进：

1. 单机版 OCR 工具  
2. 局域网部署版  
3. 企业私有化版（支持多模型、多语种、权限与审计）

