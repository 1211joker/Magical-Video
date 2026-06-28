[English](README.md) | [中文](README_CN.md)

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

## 💬 Core Feature: AI Q&A

After the AI analysis, you can ask questions about the video content and get answers grounded in the actual subtitles:

1. **Context**: The Q&A page loads the most recent analysis result, displaying the full content outline (overview, outline, key points, conclusions) in a collapsible sidebar.
2. **Ask Questions**: Type any question about the video — the backend sends the subtitle text and analysis summary to DeepSeek, with a system prompt that requires answers to cite original evidence.
3. **Chat Interface**: A clean chat UI with message bubbles, blockquote-styled citations, and a typing indicator while waiting for the AI response.

The Q&A system prompt instructs the model to base answers strictly on subtitle content, quote original text with「」marks, and honestly state when information is not covered in the video.

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
│   │   ├── download.py           # /api/download
│   │   └── qa.py                 # /api/ask — AI Q&A endpoint
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
    │       ├── QAPage.vue
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
- yt-dlp (installed automatically via pip)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Edit to add your DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

The API server starts at `http://localhost:8000`. FastAPI provides a built-in Swagger UI at `http://localhost:8000/docs` where you can browse and test all API endpoints.

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

### AI Q&A

1. After analysis is complete on the "AI解析" page, click "AI问答" in the navigation bar.
2. Browse the content outline in the left sidebar — click section headers to expand/collapse details.
3. Type your question in the input box at the bottom and press Enter to send.
4. The AI will answer based on the video's subtitle content, citing original text where applicable.

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

---

## ⚠️ Known Issues

**YouTube resolution limited to 360p**. The Android player client bypasses SABR but cannot access HD DASH manifests without a PO Token. Implementing PO Token generation is the next priority.

**Bilibili premium content**. 1080p+ and paid videos require premium membership cookies. Free users are limited to lower resolutions.

**No batch or playlist support**. Only single URLs are accepted. Playlist URLs are not expanded into individual videos.

**No download history**. There is no local or server-side record of previously analyzed or downloaded videos.

**Streaming download stability**. The yt-dlp subprocess to StreamingResponse pipeline can fail on unstable connections, particularly with large files.

**Fixed analysis prompt**. Users cannot customize the AI analysis focus (e.g., requesting only technical details, or only conclusions).

---

## 📝 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `YTDLP_PROXY` | No | HTTP proxy for YouTube access |

Copy `backend/.env.example` to `backend/.env` and fill in the values.

---

## 📄 License

MIT. See [LICENSE](LICENSE).
