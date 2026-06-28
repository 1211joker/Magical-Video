[English](#english) | [中文](#中文)

<a id="english"></a>

# 🎬 Magical Video

Magical Video is a web application that uses AI to analyze video content. Given a YouTube or Bilibili URL, it extracts the video's subtitles, sends them to DeepSeek for structured analysis, and presents the results as a multi-dimensional summary with an interactive mind map. It also supports downloading videos in available resolutions.

The core value is the AI analysis pipeline: instead of watching a 30-minute video, you can skim a structured breakdown (overview, outline, key points, conclusions, and a knowledge-tree mind map) in under a minute.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4fc08d.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-8.1-646cff.svg)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<img src="screenshot.png" alt="Magical Video Screenshot" width="100%">

---

## 🧠 Core Feature: AI Video Analysis

The primary workflow takes a video URL and produces a structured analysis in four dimensions, plus an interactive mind map:

1. **Parse**: yt-dlp retrieves video metadata (title, duration, thumbnail).
2. **Extract Subtitles**: YouTube subtitles are fetched via `youtube-transcript-api`; Bilibili subtitles are downloaded via yt-dlp and parsed from VTT/JSON.
3. **AI Analysis**: The subtitle text is sent to DeepSeek (`deepseek-v4-flash`) with a system prompt that enforces detailed, evidence-backed output. Progress is streamed to the frontend via SSE.
4. **Result Display**: The analysis is rendered in a tabbed interface (Overview, Outline, Key Points, Conclusions) with an interactive mind map powered by markmap.

The system prompt instructs the model to preserve technical terms, numbers, case studies, and direct quotes from the source material. The mind map is required to have at least 30 nodes across 4 levels of depth.

---

## 📥 Secondary: Video Download

The application can also download videos directly. Given a URL, it queries available formats and resolutions, then uses yt-dlp to download the selected format. The file is streamed to the browser as a download.

**Current limitation**: YouTube downloads are capped at 360p due to the Android player client workaround for SABR blocking (see Known Issues).

---

## 🛠 Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend framework | FastAPI (Python) |
| Download engine | yt-dlp |
| AI provider | DeepSeek API (v4-flash) |
| YouTube subtitles | youtube-transcript-api |
| Frontend framework | Vue 3 (Composition API, SFCs) |
| Build tool | Vite |
| Routing | vue-router (hash mode) |
| Mind map | markmap (d3-based) |
| Real-time updates | Server-Sent Events (SSE) |

---

## 📁 Project Structure

```
Magical-Video/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Environment-based configuration
│   ├── requirements.txt
│   ├── .env.example              # Template for required env vars
│   ├── models/schemas.py         # Pydantic models (request/response)
│   ├── routers/
│   │   ├── analyze.py            # /api/parse, /api/analyze-stream, /api/thumbnail
│   │   └── download.py           # /api/download
│   └── services/
│       ├── ytdlp_service.py      # yt-dlp subprocess wrapper
│       ├── subtitle_service.py   # Subtitle extraction and parsing
│       └── deepseek_service.py   # DeepSeek API client
│
└── frontend/
    ├── src/
    │   ├── App.vue               # Layout shell (theme toggle, NavBar, router-view)
    │   ├── main.js               # Vue app bootstrap
    │   ├── api/index.js          # HTTP client (fetch wrapper)
    │   ├── router/index.js       # Hash-mode route definitions
    │   ├── styles/main.css       # Global styles (grayscale theme, CSS variables)
    │   ├── components/           # Shared components
    │   │   ├── NavBar.vue
    │   │   ├── VideoInfo.vue
    │   │   ├── CookieGuide.vue
    │   │   ├── AnalysisResult.vue
    │   │   ├── DownloadSection.vue
    │   │   ├── MindMap.vue
    │   │   ├── SubtitleViewer.vue
    │   │   └── StickFigures.vue
    │   └── views/                # Page-level components
    │       ├── HomePage.vue
    │       ├── AnalysisPage.vue
    │       ├── DownloadPage.vue
    │       └── IssuesPage.vue
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## 🚀 Setup

### Prerequisites

- Python 3.10 or later
- Node.js 18 or later
- ffmpeg (recommended; yt-dlp uses it for merging video and audio streams)
- A DeepSeek API key ([platform.deepseek.com](https://platform.deepseek.com/))

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Edit to add your DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

The API server starts at `http://localhost:8000`. Interactive API docs are at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev                       # Dev server at http://localhost:5173
```

The Vite dev server proxies `/api` requests to `localhost:8000` automatically.

### Production

```bash
cd frontend && npm run build      # Output: frontend/dist/
```

Serve `frontend/dist/` with any static file server and proxy `/api/*` to the FastAPI backend.

---

## 📖 Usage

### AI Analysis

1. Open `http://localhost:5173` in your browser.
2. Click "AI解析" in the navigation bar.
3. Paste a YouTube or Bilibili video URL into the input field.
4. For Bilibili links, expand the "B站 Cookies" panel, paste your browser cookies, and click "保存 Cookies". (YouTube links skip this step.)
5. Click "解析视频". The video metadata (title, duration, thumbnail) will appear.
6. Click "AI 分析". The backend extracts subtitles and sends them to DeepSeek. Progress is shown in real time.
7. When complete, browse the results across four tabs: Overview, Outline, Key Points, and Conclusions. An interactive mind map is available under the "思维导图" tab.

### Quick Download

1. Click "视频下载" in the navigation bar.
2. Paste a video URL and click "解析视频".
3. Select your preferred resolution from the grid.
4. Click "下载视频". The browser will prompt you to save the file.

### Bilibili Cookies

Bilibili requires login cookies to access video information. To obtain them:

1. Log in to [bilibili.com](https://www.bilibili.com) in your browser.
2. Install a browser extension like "Get cookies.txt LOCALLY" (Chrome/Edge) or "cookies.txt" (Firefox).
3. Navigate to any Bilibili video page, click the extension icon, and export cookies in Netscape format.
4. Paste the exported text into the "B站 Cookies" panel in the app.

The cookies are validated to ensure they contain `DedeUserID`, `SESSDATA`, and `bili_jct`. They are written to a temporary file, passed to yt-dlp, and deleted immediately after the request.

---

## 🔧 Technical Challenges

**Bilibili 412/403 Anti-Scraping**. Bilibili rejects requests without valid login cookies. Fixed by implementing Netscape-format cookie parsing with mandatory field validation (`DedeUserID`, `SESSDATA`, `bili_jct`). Cookies are written to a temporary file, passed to yt-dlp, and deleted immediately after use.

**YouTube SABR Streaming Block**. YouTube's Server-And-Browser-Rendering blocks the default web client. Worked around by switching to the Android player client (`youtube:player_client=android`). The trade-off is that HD formats (720p+) require a PO Token which is not yet implemented.

**Bilibili Subtitle Extraction**. `yt-dlp --write-subs` returned no files for Bilibili, and `dump-json` did not include subtitle URLs. Fixed by downloading subtitles directly as VTT files via yt-dlp and parsing them in Python. The subtitle service returns both plain text (for the AI prompt) and timestamped segments (for the frontend viewer).

**AI Analysis Quality**. Early system prompts produced vague, overly generic summaries. Rewrote the prompt to enforce four-dimension structured output with mandatory evidence citations, preservation of technical vocabulary, and a minimum 30-node mind map requirement.

**AI Timeout on Long Videos**. Subtitle text from videos over 30 minutes could exceed 8,000 characters, causing 30-second timeouts. Increased the character limit to 25,000, max tokens to 10,000, and implemented a three-segment truncation strategy (first 20%, middle 60%, last 20%) to maintain coverage across the entire video.

**Bilibili Cookie Validation**. Early validation only checked line count, allowing incomplete cookies to pass. Added mandatory field detection with specific error messages for missing `DedeUserID`, `SESSDATA`, or `bili_jct`.

**Cross-Platform Emoji Rendering**. Emoji appearance varied significantly across operating systems. Replaced all emoji with inline SVG icons (Feather-style, `stroke="currentColor"`) for consistent rendering.

**Frontend Monolith Refactoring**. The initial implementation had all logic in a single 400-line `App.vue`. Introduced vue-router with hash mode, split into four page components, and reduced `App.vue` to a layout shell (theme toggle, navigation bar, router view).

## ⚠️ Known Issues

**YouTube resolution limited to 360p**. The Android player client bypasses SABR but cannot access HD DASH manifests without a PO Token. Implementing PO Token generation is the next priority.

**Bilibili premium content**. 1080p+ and paid videos require premium membership cookies. Free users are limited to lower resolutions.

**No batch or playlist support**. Only single URLs are accepted. Playlist URLs are not expanded into individual videos.

**No download history**. There is no local or server-side record of previously analyzed or downloaded videos.

**Streaming download stability**. The yt-dlp subprocess to StreamingResponse pipeline can fail on unstable connections, particularly with large files.

**Fixed analysis prompt**. Users cannot customize the AI analysis focus (e.g., requesting only technical details, or only conclusions).

## 📝 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `YTDLP_PROXY` | No | HTTP proxy for YouTube access |

Copy `backend/.env.example` to `backend/.env` and fill in the values.

---

## 📄 License

MIT. See [LICENSE](LICENSE).

---

<a id="中文"></a>

# 🎬 Magical Video

Magical Video 是一个基于 AI 的视频内容分析工具。输入 YouTube 或 Bilibili 视频链接，程序自动提取字幕，交由 DeepSeek 进行结构化分析，最终输出包含概述、大纲、要点、总结和交互式思维导图的多维度摘要。同时支持视频下载。

核心价值在于 AI 分析流程：一段 30 分钟的视频，可以在不到一分钟内浏览其结构化拆解结果（概述、大纲、关键要点、结论及知识树思维导图），快速判断视频是否值得完整观看。

---

## 🧠 核心功能：AI 视频分析

主流程接收视频链接，输出四维度分析结果及交互式思维导图：

1. **解析**：yt-dlp 获取视频元数据（标题、时长、封面）。
2. **提取字幕**：YouTube 通过 `youtube-transcript-api` 获取字幕；Bilibili 通过 yt-dlp 下载字幕文件后解析 VTT 或 JSON 格式。
3. **AI 分析**：字幕文本发送至 DeepSeek（`deepseek-v4-flash` 模型），系统提示词要求输出详实、有原文依据的结构化结果。分析进度通过 SSE 实时推送到前端。
4. **结果展示**：选项卡式界面呈现概述、大纲、要点、结论四个维度，并包含基于 markmap 的交互式思维导图。

系统提示词要求模型保留原文中的术语、数字、案例名称和直接引用，避免过度概括。思维导图要求至少 30 个节点，覆盖 4 层深度。

---

## 📥 辅助功能：视频下载

输入链接后可直接下载视频，支持选择可用的分辨率和格式。后端通过 yt-dlp 下载完成后将文件流式传输至浏览器。

**当前限制**：YouTube 下载因使用 Android 客户端绕过 SABR 风控，最高仅支持 360p（详见已知问题）。

---

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 下载引擎 | yt-dlp |
| AI 服务 | DeepSeek API (v4-flash) |
| YouTube 字幕 | youtube-transcript-api |
| 前端框架 | Vue 3 (Composition API, SFC) |
| 构建工具 | Vite |
| 路由 | vue-router (hash 模式) |
| 思维导图 | markmap (基于 d3) |
| 实时通信 | Server-Sent Events (SSE) |

---

## 📁 项目结构

```
Magical-Video/
├── backend/
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 环境变量配置
│   ├── requirements.txt
│   ├── .env.example              # 环境变量模板
│   ├── models/schemas.py         # Pydantic 数据模型
│   ├── routers/
│   │   ├── analyze.py            # /api/parse, /api/analyze-stream, /api/thumbnail
│   │   └── download.py           # /api/download
│   └── services/
│       ├── ytdlp_service.py      # yt-dlp 子进程封装
│       ├── subtitle_service.py   # 字幕提取与解析
│       └── deepseek_service.py   # DeepSeek API 客户端
│
└── frontend/
    ├── src/
    │   ├── App.vue               # 布局壳（主题切换、导航栏、路由视图）
    │   ├── main.js               # Vue 启动入口
    │   ├── api/index.js          # HTTP 请求封装
    │   ├── router/index.js       # 路由配置（hash 模式）
    │   ├── styles/main.css       # 全局样式（灰度主题、CSS 变量）
    │   ├── components/           # 公共组件
    │   │   ├── NavBar.vue
    │   │   ├── VideoInfo.vue
    │   │   ├── CookieGuide.vue
    │   │   ├── AnalysisResult.vue
    │   │   ├── DownloadSection.vue
    │   │   ├── MindMap.vue
    │   │   ├── SubtitleViewer.vue
    │   │   └── StickFigures.vue
    │   └── views/                # 页面级组件
    │       ├── HomePage.vue
    │       ├── AnalysisPage.vue
    │       ├── DownloadPage.vue
    │       └── IssuesPage.vue
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## 🚀 环境搭建

### 前置条件

- Python 3.10 及以上
- Node.js 18 及以上
- ffmpeg（推荐安装；yt-dlp 合并视频和音频时需要）
- DeepSeek API 密钥（[platform.deepseek.com](https://platform.deepseek.com/)）

### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # 编辑填入 DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

API 服务启动在 `http://localhost:8000`，接口文档在 `/docs`。

### 前端

```bash
cd frontend
npm install
npm run dev                       # 开发服务器 http://localhost:5173
```

Vite 开发服务器自动将 `/api` 请求代理到后端 `localhost:8000`。

### 生产构建

```bash
cd frontend && npm run build      # 输出到 frontend/dist/
```

将 `frontend/dist/` 部署到任意静态文件服务器，并将 `/api/*` 请求代理到 FastAPI 后端。

---

## 📖 使用指南

### AI 分析

1. 浏览器打开 `http://localhost:5173`。
2. 点击导航栏中的"AI解析"。
3. 在输入框中粘贴 YouTube 或 Bilibili 视频链接。
4. Bilibili 链接需要先展开"B站 Cookies"面板，粘贴浏览器 Cookie 并点击"保存 Cookies"。（YouTube 链接跳过此步骤。）
5. 点击"解析视频"，等待视频信息（标题、时长、封面）加载。
6. 点击"AI 分析"，后端会自动提取字幕并发送给 DeepSeek 进行分析，进度实时显示。
7. 分析完成后，在四个选项卡中浏览结果：概述、大纲、要点、总结。"思维导图"选项卡提供交互式知识树。

### 快速下载

1. 点击导航栏中的"视频下载"。
2. 粘贴视频链接，点击"解析视频"。
3. 在清晰度网格中选择需要的分辨率。
4. 点击"下载视频"，浏览器将弹出保存对话框。

### 获取 Bilibili Cookies

Bilibili 需要登录 Cookie 才能获取视频信息，获取方法：

1. 在浏览器中登录 [bilibili.com](https://www.bilibili.com)。
2. 安装浏览器扩展，如"Get cookies.txt LOCALLY"（Chrome/Edge）或"cookies.txt"（Firefox）。
3. 打开任意 Bilibili 视频页面，点击扩展图标，导出 Netscape 格式的 Cookie。
4. 将导出的文本粘贴到应用中的"B站 Cookies"面板。

Cookie 会经过校验，确保包含 `DedeUserID`、`SESSDATA`、`bili_jct` 三个必填字段。Cookie 写入临时文件传递给 yt-dlp，请求完成后立即删除。

---

## 🔧 技术挑战与解决方案

**Bilibili 412/403 反爬拦截**。Bilibili 对无有效登录凭证的请求返回 412 或 403。通过实现 Netscape 格式 Cookie 解析解决：用户粘贴浏览器 Cookie，后端校验必填字段（`DedeUserID`、`SESSDATA`、`bili_jct`），写入临时文件传给 yt-dlp，用完即删。

**YouTube SABR 流式拦截**。YouTube 的服务端与浏览器协同渲染机制拦截默认 Web 客户端的流媒体请求。通过切换到 Android 客户端（`youtube:player_client=android`）绕过。代价是无 PO Token 时仅能获取 360p 格式。

**Bilibili 字幕提取失败**。`yt-dlp --write-subs` 对 Bilibili 不产生字幕文件，`dump-json` 也不包含字幕 URL，导致 AI 分析管线中断。改为通过 yt-dlp 直接下载 VTT 文件再用 Python 解析，同时返回纯文本（供 AI 使用）和带时间戳的片段（供前端展示）。

**AI 分析质量问题**。早期提示词导致 AI 输出过于概括，丢失关键信息。重写系统提示词，强制要求四维度结构化输出，必须引用原文证据，保留术语和数字，思维导图至少 30 个节点。

**长视频 AI 超时**。超过 30 分钟的视频字幕可能超过 8000 字符，导致 30 秒超时。将字符上限提升到 25000，max tokens 提升到 10000，截断策略改为首 20% 加中 60% 加尾 20%，保证覆盖视频全程。

**Cookie 校验不准确**。早期校验仅检查行数，不完整 Cookie 也能通过。增加必填字段检测（`DedeUserID`、`SESSDATA`、`bili_jct`），缺失时给出明确错误提示。

**Emoji 跨平台渲染不一致**。Windows、macOS、Linux 对 Emoji 渲染差异大。全部替换为 Feather 风格 SVG 内联图标，使用 `currentColor` 跟随文字颜色，消除跨平台差异。

**前端巨石架构重构**。初始版本所有功能集中在单个 400 行的 `App.vue` 中。引入 vue-router（hash 模式），拆分为四个页面组件，`App.vue` 缩减为布局壳。

## ⚠️ 已知问题

**YouTube 分辨率限制在 360p**。Android 客户端虽然能绕过 SABR，但缺少 PO Token 无法获取 720p 及以上格式。

**Bilibili 付费内容**。1080p+ 和付费视频需要大会员 Cookie，免费用户只能下载较低画质。

**不支持批量和播放列表**。仅接受单个视频链接，播放列表链接不会被展开为单个视频。

**无下载历史记录**。没有本地或服务端的历史记录，重复分析会浪费 AI 配额。

**流式下载稳定性**。yt-dlp 子进程到 StreamingResponse 的管道在网络不稳定时可能中断，大文件尤其容易出问题。

**分析选项固定**。用户无法自定义 AI 分析侧重点（例如只提取技术细节或只输出结论）。

## 📝 环境变量

| 变量 | 是否必填 | 说明 |
|------|----------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥 |
| `YTDLP_PROXY` | 否 | 访问 YouTube 的 HTTP 代理地址 |

复制 `backend/.env.example` 为 `backend/.env` 并填入对应值。

---

## 📄 许可证

MIT 协议。详见 [LICENSE](LICENSE)。
