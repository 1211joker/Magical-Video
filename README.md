# 🎬 Magical Video

> AI-powered video analysis & download tool. Paste a link → AI analyzes subtitles → structured summary with mind map → optional download.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4fc08d.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-8.1-646cff.svg)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ Features

- **Multi-platform support** — YouTube & Bilibili (B站)
- **AI-powered analysis** — DeepSeek AI generates structured summaries with 4 dimensions: overview, outline, key points, and conclusions
- **Interactive mind map** — Visual knowledge tree built from video content (powered by markmap)
- **Subtitle viewer** — Browse timestamped subtitle segments alongside the analysis
- **Smart download** — Choose from available resolutions, download with one click
- **Real-time progress** — SSE streaming keeps you informed during every step
- **B站 cookies auth** — Paste browser cookies to access members-only content
- **Dark mode** — Automatic light/dark theme based on system preference
- **Responsive design** — Works on desktop and mobile

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI (Python) | REST API & SSE streaming |
| Download Engine | yt-dlp | Video metadata extraction & downloading |
| AI | DeepSeek API (v4-flash) | Subtitle analysis & summarization |
| Frontend | Vue 3 + Vite | Reactive SPA with component architecture |
| Routing | vue-router (hash mode) | Multi-page navigation |
| Mind Map | markmap | Interactive knowledge tree visualization |
| YouTube Subs | youtube-transcript-api | Lightweight subtitle extraction |

---

## 📁 Project Structure

```
Magical-Video/
├── backend/                    # Backend (FastAPI)
│   ├── main.py                # App entry point
│   ├── config.py              # Configuration (API keys, timeouts, proxy)
│   ├── requirements.txt       # Python dependencies
│   ├── .env.example           # Environment variables template
│   ├── models/
│   │   └── schemas.py         # Pydantic data models
│   ├── routers/
│   │   ├── analyze.py         # Parse + AI analysis API endpoints
│   │   └── download.py        # Video download endpoint
│   └── services/
│       ├── ytdlp_service.py   # yt-dlp wrapper (parse + download)
│       ├── subtitle_service.py # Subtitle extraction (YouTube + Bilibili)
│       └── deepseek_service.py # DeepSeek AI analysis
│
└── frontend/                   # Frontend (Vue 3 + Vite)
    ├── src/
    │   ├── App.vue            # Layout shell (theme + NavBar + router-view)
    │   ├── main.js            # Entry point (registers vue-router)
    │   ├── api/index.js       # API request layer
    │   ├── router/index.js    # 4-page route config (hash mode)
    │   ├── components/        # Reusable components
    │   │   ├── NavBar.vue           # Top navigation bar
    │   │   ├── VideoInfo.vue        # Video metadata card
    │   │   ├── CookieGuide.vue      # Bilibili cookies guide
    │   │   ├── AnalysisResult.vue   # AI analysis results (tabbed layout)
    │   │   ├── DownloadSection.vue  # Format selector + download
    │   │   ├── MindMap.vue          # markmap mind map
    │   │   ├── SubtitleViewer.vue   # Timestamped subtitle viewer
    │   │   └── StickFigures.vue     # SVG stick-figure animations
    │   ├── views/             # Page views
    │   │   ├── HomePage.vue         # Brand landing + animations
    │   │   ├── AnalysisPage.vue     # Full AI analysis workflow
    │   │   ├── DownloadPage.vue     # Quick video download
    │   │   └── IssuesPage.vue       # Dev issues & optimization log
    │   └── styles/main.css    # Global styles (pure grayscale theme)
    ├── index.html
    ├── package.json
    └── vite.config.js         # Vite config (dev proxy)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **yt-dlp** (installed automatically as a Python dependency)
- **DeepSeek API key** ([get one here](https://platform.deepseek.com/))

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up configuration
cp .env.example .env
# Edit .env — add your DEEPSEEK_API_KEY
# Optional: set YTDLP_PROXY if you need a proxy for YouTube

# Start the server
uvicorn main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`. Visit `/docs` for the interactive Swagger UI.

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open `http://localhost:5173` in your browser. The dev server proxies API requests to the backend automatically.

### Production Build

```bash
cd frontend
npm run build       # Output to frontend/dist/
```

Serve `frontend/dist/` with any static file server (nginx, caddy, etc.), and proxy `/api/*` requests to the FastAPI backend.

---

## 📖 Usage

### AI Analysis Workflow

1. Paste a YouTube or Bilibili video URL
2. (Bilibili only) Paste your browser cookies for authentication
3. Click "解析视频" — the backend extracts video metadata
4. Click "AI 分析" — DeepSeek analyzes the subtitles in real-time via SSE
5. Explore the results: overview, outline, key points, conclusions, and an interactive mind map
6. Optionally download the video in your preferred resolution

### Quick Download

Use the "视频下载" page to skip AI analysis and go straight to downloading.

---

## 🔧 Key Technical Challenges Solved

### 1. Bilibili 412/403 Anti-Scraping
Bilibili blocks requests without valid login cookies. **Solution**: Implemented Netscape-format cookies parsing — users paste browser cookies, the backend validates required fields (`DedeUserID`, `SESSDATA`, `bili_jct`), and injects them into yt-dlp and API requests.

### 2. YouTube SABR Streaming Block (403 Forbidden)
YouTube's Server-And-Browser-Rendering (SABR) blocks the default web client from downloading video streams. **Solution**: Switched to Android player client (`--extractor-args "youtube:player_client=android"`). Trade-off: limited to 360p resolution without a PO Token.

### 3. Bilibili Subtitle Extraction Failure
`yt-dlp --write-subs` did not produce subtitle files for Bilibili, and `dump-json` lacked subtitle URLs, causing the AI analysis pipeline to crash. **Solution**: Rewrote subtitle extraction to download VTT files directly via yt-dlp, then parse them in Python. Returns both plain text (for AI) and structured segments (for frontend display).

### 4. Bilibili Cookies Validation Accuracy
Early validation only checked line count ≥ 3, allowing incomplete cookies to pass through and fail silently. **Solution**: Added mandatory field detection — `DedeUserID`, `SESSDATA`, `bili_jct` must all be present, with clear error messages when missing.

### 5. AI Analysis Timeout
Long videos with 8,000+ characters of subtitles exceeded the 30s AI timeout. **Solution**: Extended `max_chars` to 25,000, `max_tokens` to 10,000, and used a smart truncation strategy (first 20% + middle 60% + last 20%) to cover the entire video. Increased timeout to 90s.

### 6. Vague AI Analysis Results
Early system prompts produced overly generic summaries that lost critical details. **Solution**: Rewrote the system prompt to enforce 4-dimension structured output with mandatory evidence citations from the original text, preservation of technical terms and numbers, and a minimum 30-node mind map.

### 7. Cross-Platform Emoji Rendering
Emoji rendering varied significantly across Windows, macOS, and Linux. **Solution**: Replaced all emoji with inline Feather-style SVG icons using `currentColor`, ensuring consistent appearance across all platforms.

### 8. Monolithic Frontend Architecture
All features (parse, analyze, download) lived in a single 400+ line `App.vue` with no navigation. **Solution**: Introduced vue-router with hash mode, split into 4 pages (Home, AI Analysis, Video Download, Issues & Optimization), and reduced `App.vue` to a layout shell.

---

## ⚠️ Known Issues & Limitations

### Resolution Constraints

| Issue | Status | Impact |
|-------|--------|--------|
| **YouTube HD limited to 360p** | 🔴 Unresolved | Android client bypasses SABR but lacks PO Token for HD DASH formats (720p+). Requires PO Token generation. |
| **Bilibili premium quality** | 🟡 Partial | 1080p+ and paid content requires premium membership cookies. Free users get lower quality only. |

### Feature Gaps

| Issue | Status | Impact |
|-------|--------|--------|
| **No batch download** | 🔴 Unresolved | Only single-link input supported. Cannot process multiple URLs or playlists. |
| **No playlist support** | 🔴 Unresolved | YouTube playlist links parse the list page instead of individual videos. |
| **No download history** | 🔴 Unresolved | No local/server-side record of analyzed/downloaded videos, leading to redundant AI analysis. |
| **No custom analysis options** | 🔴 Unresolved | AI analysis uses a fixed prompt. Users cannot customize focus areas (e.g., "extract all data points" vs "summarize only"). |

### Stability

| Issue | Status | Impact |
|-------|--------|--------|
| **Streaming download fragility** | 🟡 Known | The yt-dlp → stdout → StreamingResponse → Blob pipeline can fail mid-transfer on unstable connections, especially with large files. |

---

## 📝 Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | Your DeepSeek API key |
| `YTDLP_PROXY` | No | HTTP proxy for YouTube access (e.g., `http://127.0.0.1:7890`) |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — The backbone video download engine
- [DeepSeek](https://platform.deepseek.com/) — Affordable, high-quality AI API
- [markmap](https://markmap.js.org/) — Mind map visualization from markdown
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) — Lightweight YouTube subtitle extraction
- [Feather Icons](https://feathericons.com/) — SVG icon inspiration
