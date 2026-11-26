[English](README.md) | [中文](README_CN.md)

# 🎬 Magical Video

Magical Video analyzes videos from YouTube, Bilibili and PolyU Panopto. It sends available captions to the selected AI model to generate a summary and interactive mind map, then uses the captions to answer follow-up questions. Panopto recordings can be downloaded when the platform offers the viewer an official download.

The core value is the AI analysis pipeline: instead of watching a 30-minute video, you can skim a structured breakdown (overview, outline, key points, conclusions, and a knowledge-tree mind map) in under a minute, then dive deeper into specific topics through AI-powered Q&A.

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
2. **Extract subtitles.** YouTube uses `youtube-transcript-api`, Bilibili uses yt-dlp to fetch VTT or JSON and PolyU Panopto uses the captions available in the video viewer.
3. **AI Analysis**: The selected model uses the captions to generate a structured, evidence-backed analysis. Progress is streamed to the frontend via SSE.
4. **Result Display**: The analysis is rendered in a tabbed interface (Overview, Outline, Key Points, Conclusions) with an interactive mind map powered by markmap.

The outline and key points retain relevant terms, numbers, examples, and quotes. The mind map groups related ideas into up to three levels and opens fully expanded.

---

## 💬 Core Feature: AI Q&A

After the AI analysis, you can ask questions about the video content and get answers grounded in the actual subtitles:

1. **Context**: The Q&A page loads the most recent analysis result, displaying the full content outline (overview, outline, key points, conclusions) in a collapsible sidebar.
2. **Ask Questions**: Type any question about the video — the backend sends the captions, analysis summary and recent conversation to the selected model, with a system prompt that requires answers to cite original evidence.
3. **Chat Interface**: A clean chat UI with message bubbles, blockquote-styled citations, and a typing indicator while waiting for the AI response.

The Q&A system prompt instructs the model to base answers strictly on subtitle content, quote original text with「」marks, and honestly state when information is not covered in the video.

---

## 📥 Secondary: Video Download

The application queries available formats and resolutions, then uses yt-dlp to prepare the selected video in temporary storage. The browser's download manager receives the file and shows transfer progress.

**Current limitation**: YouTube downloads are capped at 360p due to the Android player client workaround for SABR blocking (see Known Issues).

---

## 🛠 Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend framework | FastAPI (Python) |
| Download engine | yt-dlp |
| AI providers | DeepSeek, OpenAI, OpenCode Go |
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
│   ├── limiter.py                   # Shared slowapi Limiter instance
│   ├── routers/
│   │   ├── analyze.py            # /api/parse, /api/analyze-stream, /api/thumbnail
│   │   ├── download.py           # /api/download and browser download jobs
│   │   └── qa.py                 # /api/ask — AI Q&A endpoint
│   └── services/
│       ├── ytdlp_service.py      # yt-dlp subprocess wrapper
│       ├── subtitle_service.py   # Subtitle extraction and parsing
│       ├── analysis_service.py   # Subtitle analysis
│       ├── qa_service.py         # Question-answering context
│       └── ai_client.py         # AI configuration, HTTP requests and retries
│
├── nginx.conf                     # Production nginx configuration
├── Dockerfile                     # Backend container image
├── Dockerfile.nginx               # Frontend build + nginx image
├── docker-compose.yml             # Multi-service orchestration
├── .dockerignore
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
    │   │   ├── VideoSessionGuide.vue
    │   │   ├── AnalysisResult.vue
    │   │   ├── DownloadSection.vue
    │   │   ├── MindMap.vue
    │   │   ├── SubtitleViewer.vue
    │   │   └── StickFigures.vue
    │   └── views/                # Page-level components
    │       ├── HomePage.vue
    │       ├── AnalysisPage.vue
    │       ├── QAPage.vue
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
- An API key for at least one AI provider to use analysis and Q&A
- yt-dlp (installed automatically via pip)
- **A proxy for YouTube access** (required if you're in a region where YouTube is blocked; see [Proxy Configuration](#proxy-configuration) below)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # First-time setup. Add the selected provider's API key.
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

### 🐳 Docker Deployment

The project includes a complete Docker Compose setup for production deployment. Two containers work together:

```
Browser (127.0.0.1:8080 on the host or the configured HTTPS domain)
    │
    ▼
┌──────────────────────────┐
│  nginx (nginx:alpine)    │  ← Static files + reverse proxy
│  /              → dist/  │     gzip, security headers, SPA fallback
│  /api/*         → proxy  │
└──────────┬───────────────┘
           │ internal network
           ▼
┌──────────────────────────┐
│  backend (python:3.12)   │  ← FastAPI + uvicorn
│  :8000                   │     yt-dlp, AI model requests, rate limiting
└──────────────────────────┘
```

#### Prerequisites

- **Docker** ≥ 20.10 and **Docker Compose** ≥ 2.0
- An API key for at least one AI provider to use analysis and Q&A
- (Optional) An HTTP proxy if YouTube is blocked in your region

#### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/1211joker/Magical-Video.git
cd Magical-Video

# 2. Create and configure the environment file
cp backend/.env.example backend/.env
vim backend/.env
```

Edit `backend/.env` and fill in:

```bash
DEEPSEEK_API_KEY=sk-your-key-here       # Example. OPENAI_API_KEY or OPENCODE_GO_API_KEY also works.
# YTDLP_PROXY=http://proxy.example.net:7890 # Optional proxy reachable from the backend container
ALLOWED_ORIGINS=https://your-domain.com # Optional — CORS whitelist in production
```

```bash
# 3. Start the application
docker compose up -d

# 4. Verify both containers are running
docker compose ps
# Expected output: backend (Up) + nginx (Up)

# 5. Check the host entry point
curl -fsS http://127.0.0.1:8080/api/health
```

Open [http://localhost:8080](http://localhost:8080) on the Docker host. For access from another device, use the HTTPS domain configured below.

#### Managing the Application

```bash
# View logs
docker compose logs -f              # All containers
docker compose logs -f backend      # Backend only
docker compose logs -f nginx        # Nginx only

# Restart after .env changes or code updates
docker compose down
docker compose up -d --build        # Rebuild images, restart

# Stop the application
docker compose stop

# Stop and remove containers (data in .env is preserved)
docker compose down
```

#### Updating to a New Version

```bash
git pull                            # Pull latest code
docker compose down                 # Stop current containers
docker compose up -d --build        # Rebuild with latest code
```

#### HTTPS Setup

The default configuration maps HTTP port 80 in the container to `127.0.0.1:8080` on the host. HTTPS can terminate at the host proxy or in the container.

**Option A — Reverse proxy in front (recommended)**

Use this Nginx configuration on the host to terminate HTTPS and forward requests to the container.

```nginx
# Host nginx example
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
```

The container's Nginx accepts the client address from the host proxy through the Compose gateway. Uvicorn trusts the internal address of the Nginx container, so SlowAPI can count requests per client IP. If you change the Compose gateway, update `set_real_ip_from` in `nginx.conf`.

**Option B — SSL inside Docker**

Mount your certificate, add a separate 443 server block to `nginx.conf` and update `docker-compose.yml` to expose port 443. Reuse the API proxy settings for the public 443 listener and keep the host-proxy real-IP settings in the existing HTTP server block.

```yaml
# nginx service settings in docker-compose.yml
ports:
  - "127.0.0.1:8080:80"
  - "443:443"
volumes:
  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
  - ./ssl/key.pem:/etc/nginx/ssl/key.pem:ro
```

#### Troubleshooting

| Problem | Check |
|---------|-------|
| `port 8080 already in use` | Change the published host port in `docker-compose.yml` and update the access URL and host reverse proxy |
| Backend can't connect to an AI provider | Check the API key, model ID and backend network. See `docker compose logs backend` |
| YouTube features don't work | Configure `YTDLP_PROXY` in `backend/.env`, then `docker compose up -d --build` |
| `ERR_EMPTY_RESPONSE` in browser | Check `127.0.0.1:8080` on the Docker host, then check the upstream address of the HTTPS proxy |
| Container keeps restarting | `docker compose logs backend` — often a missing `.env` or invalid API key |
| Rate limit (429) errors | You've hit the per-IP rate limit. Wait 1 minute for the counter to reset |

### Manual Deployment (without Docker)

```bash
cd frontend && npm run build      # Output: frontend/dist/
```

Serve `frontend/dist/` with nginx and proxy `/api/*` to the FastAPI backend. A production `nginx.conf` template is included in the repository for reference.

### Proxy Configuration

The backend checks YouTube connectivity when parsing a link. It checks an explicit `YTDLP_PROXY` first. In automatic mode it tries the direct connection, then proxies exposed by the server's system or environment, such as `HTTPS_PROXY`. Parsing, thumbnails, subtitles, and downloads use the verified route.

If the check fails, the page explains the problem and offers a retry. With a local deployment, enable the VPN or system proxy on the device running the backend. With a hosted deployment, configure the proxy on the server that sends the YouTube requests.

If the proxy client does not expose its address to the system, set its HTTP or SOCKS5 port in `backend/.env` and restart the backend.

```bash
YTDLP_PROXY=http://127.0.0.1:7890
# Or use the local SOCKS5 port
# YTDLP_PROXY=socks5h://127.0.0.1:7891
```

In Docker, `127.0.0.1` refers to the backend container. Use a proxy address reachable from that container.

---

## 📖 Usage

### AI Analysis

1. Open `http://localhost:5173` in your browser.
2. Click "AI解析" in the navigation bar.
3. Paste a YouTube, Bilibili or PolyU Panopto video URL into the input field.
4. When Bilibili or PolyU Panopto requires sign-in, follow the instructions in the session panel.
5. Click "解析视频". The video metadata (title, duration, thumbnail) will appear.
6. Select a model and start AI analysis. The backend extracts captions and sends them to the selected model. Progress is shown in real time.
7. When complete, browse the results across four tabs: Overview, Outline, Key Points, and Conclusions. An interactive mind map is available under the "思维导图" tab.

### AI Q&A

1. After analysis is complete on the "AI解析" page, click "AI问答" in the navigation bar.
2. Browse the content outline in the left sidebar — click section headers to expand/collapse details.
3. Type your question in the input box at the bottom and press Enter to send.
4. The AI will answer based on the video's subtitle content, citing original text where applicable.

### Quick Download

1. On the "AI解析" page, paste a video URL and click "解析视频".
2. After the video info loads, scroll down to the download section.
3. Select your preferred resolution from the grid.
4. Click "下载视频" and keep the page open while the server prepares the file. Once the transfer starts, follow its progress in your browser's downloads list.

### Connect a Bilibili or PolyU Panopto session

1. Paste a video link and open the session panel under the input or from a sign-in prompt.
2. Sign in on the official site linked in the panel. Open Chrome or Edge DevTools with `⌥⌘I` on Mac or `Ctrl+Shift+I` on Windows. Select **Application** at the top. If the tab is hidden, open the `»` menu.
3. Under **Storage → Cookies**, select the site. Copy the value of `SESSDATA` for `www.bilibili.com` or `.ASPXAUTH` for `polyu.ap.panopto.com`.
4. Paste the value into your local app and connect. Reloading or leaving the analysis page clears the session.

### PolyU Panopto

1. Paste a recording link from `polyu.ap.panopto.com` into the analysis page. Public recordings can be parsed immediately.
2. If prompted, sign in on the official recording page, confirm playback and follow the shared session instructions.
3. When captions are available, select a model and start AI analysis to send the captions to that provider. The app makes an MP4 download available when Panopto offers it to the viewer, and hands the download over to the browser.

---

## 🔧 Technical Challenges

**Bilibili sessions**. The app accepts the `SESSDATA` value from browser DevTools. The server validates it, passes it to yt-dlp in a temporary Netscape file scoped to Bilibili and deletes the file after use.

**YouTube SABR Streaming Block**. YouTube's Server-And-Browser-Rendering blocks the default web client. Worked around by switching to the Android player client (`youtube:player_client=android`). The trade-off is that HD formats (720p+) require a PO Token which is not yet implemented.

**Bilibili Subtitle Extraction**. `yt-dlp --write-subs` returned no files for Bilibili, and `dump-json` did not include subtitle URLs. Fixed by downloading subtitles directly as VTT files via yt-dlp and parsing them in Python. The subtitle service returns both plain text (for the AI prompt) and timestamped segments (for the frontend viewer).

**AI Analysis Quality**. Early system prompts produced vague, overly generic summaries. Rewrote the prompt to enforce four-dimension structured output with mandatory evidence citations, preservation of technical vocabulary, and a minimum 30-node mind map requirement.

**AI Timeout on Long Videos**. Subtitle text from videos over 30 minutes could exceed 8,000 characters, causing 30-second timeouts. Increased the character limit to 25,000, max tokens to 10,000, and implemented a three-segment truncation strategy (first 20%, middle 60%, last 20%) to maintain coverage across the entire video.

**Session retries**. Explicit sign-in errors from parsing, captions or downloads open the shared panel so users can refresh the affected site's session.

**Cross-Platform Emoji Rendering**. Emoji appearance varied significantly across operating systems. Replaced all emoji with inline SVG icons (Feather-style, `stroke="currentColor"`) for consistent rendering.

**Frontend Monolith Refactoring**. The initial implementation had all logic in a single 400-line `App.vue`. Introduced vue-router with hash mode, split into four page components, and reduced `App.vue` to a layout shell (theme toggle, navigation bar, router view).

---

## ⚠️ Known Issues

**YouTube resolution limited to 360p**. The Android player client bypasses SABR but cannot access HD DASH manifests without a PO Token. Implementing PO Token generation is the next priority.

**Bilibili premium content**. 1080p+ and paid videos require premium membership cookies. Free users are limited to lower resolutions.

**No batch or playlist support**. Only single URLs are accepted. Playlist URLs are not expanded into individual videos.

**No download history**. There is no local or server-side record of previously analyzed or downloaded videos.

**Large-file preparation**. The server needs enough temporary disk space to prepare the entire video before the browser can receive it.

**Fixed analysis prompt**. Users cannot customize the AI analysis focus (e.g., requesting only technical details, or only conclusions).

---

## 📝 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | At least one provider key | DeepSeek API key |
| `OPENAI_API_KEY` | At least one provider key | OpenAI API platform key |
| `OPENCODE_GO_API_KEY` | At least one provider key | OpenCode API key for a workspace with Go |
| `DEEPSEEK_MODEL` | No | Defaults to `deepseek-v4-flash` |
| `OPENAI_MODEL` | No | Responses API model ID. Defaults to `gpt-5.4-mini` |
| `OPENCODE_GO_MODEL` | No | Go model ID. Defaults to `deepseek-v4.1-flash` |
| `YTDLP_PROXY` | No | HTTP or SOCKS5 proxy for YouTube access |
| `ALLOWED_ORIGINS` | No | CORS allowed origins (comma-separated). Default: `*` (all origins in dev). Set to your domain(s) in production |
| `YTDLP_NO_CHECK_CERTIFICATES` | No | Skip SSL cert verification for yt-dlp. Default: `false`. Only set to `true` in regions with SSL interference |

On first setup, copy `backend/.env.example` to `backend/.env`. Add your API keys and restart the backend. Select a configured model on the analysis or Q&A page. The default is the first configured provider in this order, DeepSeek, OpenAI, then OpenCode Go. Q&A initially uses the provider that generated the summary when available.

OpenCode Go's chat inference is designed for coding agents. Its DeepSeek models require the applicable subscription and region permissions. [DeepSeek platform](https://platform.deepseek.com/), [OpenAI API keys](https://platform.openai.com/api-keys), [OpenCode Go](https://opencode.ai/docs/console/go/)

---

## 📋 Changelog

### v0.2.0 — Production Readiness (2026-06-30)

This release focuses on security hardening, reliability improvements, and production deployment.

**🔴 Security (P0)**:
- **CORS whitelist**: `ALLOWED_ORIGINS` env var controls allowed origins. Default `*` for dev; set specific domain(s) in production.
- **Rate limiting**: Added `slowapi` with per-endpoint IP-based rate limits. `/api/analyze-stream` 5/min, `/api/download` 3/min, `/api/ask` 10/min, `/api/parse` 20/min, `/api/thumbnail` 30/min.
- **SSL certificate verification**: yt-dlp SSL verification now enabled by default. Controlled via `YTDLP_NO_CHECK_CERTIFICATES` env var (default `false`).
- **nginx Basic Auth**: Server-level password protection for the entire site.
- New file: `backend/limiter.py` — shared Limiter instance to avoid circular imports.

**🟠 Reliability (P1)**:
- **API retry logic**: DeepSeek API calls now retry on transient failures (429 / 5xx / timeout) with exponential backoff (2s → 4s → 8s, max 3 attempts). Uses `tenacity`. Non-retryable errors (401 / 402) fail immediately.
- New file: `backend/services/deepseek_client.py` — shared DeepSeek HTTP client with retry decorator.

**🟡 Architecture (P2)**:
- **Docker Compose**: Two-container orchestration — Python backend + nginx serving static frontend with `/api` reverse proxy.
- **Production nginx config**: Includes gzip, SPA fallback, SSE long-connection support (`proxy_read_timeout 300s`), security headers, and `client_max_body_size 10m`.
- New files: `Dockerfile`, `Dockerfile.nginx`, `docker-compose.yml`, `nginx.conf`, `.dockerignore`.

**🐛 Bug Fix**:
- Fixed `/api/download` rate limit not triggering due to slowapi parameter name conflict (`request: DownloadRequest` renamed to `body: DownloadRequest`).

### v0.1.0 — Initial Release

- AI video analysis with four-dimension structured output and interactive mind map
- AI Q&A grounded in subtitle content
- Video download with resolution selection
- YouTube + Bilibili support with proxy configuration

---

## 📄 License

MIT. See [LICENSE](LICENSE).
