[English](README.md) | [中文](README_CN.md)

# 🎬 Magical Video

Magical Video 是一个基于 AI 的视频内容分析工具。输入 YouTube 或 Bilibili 视频链接，程序自动提取字幕，交由 DeepSeek 进行结构化分析，最终输出包含概述、大纲、要点、总结和交互式思维导图的多维度摘要。分析完成后，可以就视频内容与 AI 对话问答，所有回答都基于字幕原文。同时支持视频下载。

核心价值在于 AI 分析流程：一段 30 分钟的视频，可以在不到一分钟内浏览其结构化拆解结果（概述、大纲、关键要点、结论及知识树思维导图），还可通过 AI 问答针对特定话题深入追问。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4fc08d.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-8.1-646cff.svg)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<img src="screenshot.png" alt="Magical Video 截图" width="100%">

---

## 🧠 核心功能：AI 视频分析

主流程接收视频链接，输出四维度分析结果及交互式思维导图：

1. **解析**：yt-dlp 获取视频元数据（标题、时长、封面）。
2. **提取字幕**：YouTube 通过 `youtube-transcript-api` 获取字幕；Bilibili 通过 yt-dlp 下载字幕文件后解析 VTT 或 JSON 格式。
3. **AI 分析**：字幕文本发送至 DeepSeek（`deepseek-v4-flash` 模型），系统提示词要求输出详实、有原文依据的结构化结果。分析进度通过 SSE 实时推送到前端。
4. **结果展示**：选项卡式界面呈现概述、大纲、要点、结论四个维度，并包含基于 markmap 的交互式思维导图。

大纲和要点保留原文中的术语、数字、案例和直接引用。思维导图将相近内容归到同一主题，最多展示 3 层，打开时展开全部节点。

---

## 💬 核心功能：AI 问答

AI 分析完成后，可以就视频内容向 AI 提问，获取基于字幕原文的回答：

1. **上下文加载**：问答页面自动加载最近的分析结果，在可折叠侧边栏中展示完整的内容大纲（概述、大纲、要点、总结）。
2. **自由提问**：输入任何关于视频的问题 — 后端将字幕文本和分析摘要发送给 DeepSeek，系统提示词要求回答必须引用原文证据。
3. **聊天界面**：简洁的对话式 UI，气泡消息、原文引用 blockquote 样式、AI 思考时的打字动画。

问答系统提示词要求 AI 严格基于字幕内容回答，用「」标注原文引用，视频未涉及的内容如实告知。

---

## 📥 辅助功能：视频下载

输入链接后可以选择可用的分辨率和格式。服务端用 yt-dlp 准备文件，随后由浏览器的下载管理器接收文件并显示进度。

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
│   ├── limiter.py                   # 共享 slowapi Limiter 实例
│   ├── routers/
│   │   ├── analyze.py            # /api/parse, /api/analyze-stream, /api/thumbnail
│   │   ├── download.py           # /api/download 和浏览器下载任务
│   │   └── qa.py                 # /api/ask — AI 问答
│   └── services/
│       ├── ytdlp_service.py      # yt-dlp 子进程封装
│       ├── subtitle_service.py   # 字幕提取与解析
│       ├── deepseek_service.py   # DeepSeek 分析服务
│       └── deepseek_client.py    # DeepSeek HTTP 客户端（含重试）
│
├── nginx.conf                     # 生产环境 nginx 配置
├── Dockerfile                     # 后端容器镜像
├── Dockerfile.nginx               # 前端构建 + nginx 镜像
├── docker-compose.yml             # 多服务编排
├── .dockerignore
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
    │       ├── QAPage.vue
    │       └── IssuesPage.vue
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## 🚀 环境搭建

### 前置条件

- Python 3.10 及以上
- Node.js 18 及以上
- ffmpeg（推荐安装；yt-dlp 合并视频和音频时需要）
- DeepSeek API 密钥（[platform.deepseek.com](https://platform.deepseek.com/)）
- yt-dlp（通过 pip 自动安装）
- **YouTube 代理**（国内网络无法直连 YouTube，需配置代理才能使用 YouTube 相关功能；见下方[代理配置](#代理配置)）

### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # 编辑填入 DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

API 服务启动在 `http://localhost:8000`。FastAPI 内置的 Swagger 接口文档可通过浏览器访问 `http://localhost:8000/docs`，在此可以浏览和测试所有 API 接口。

### 前端

```bash
cd frontend
npm install
npm run dev                       # 开发服务器 http://localhost:5173
```

Vite 开发服务器自动将 `/api` 请求代理到后端 `localhost:8000`。

### 🐳 Docker 部署

项目包含完整的 Docker Compose 生产部署配置，两个容器协同工作：

```
浏览器 (80端口)
    │
    ▼
┌──────────────────────────┐
│  nginx (nginx:alpine)    │  ← 静态文件 + 反向代理
│  /              → dist/  │     gzip 压缩、安全头、SPA 回退
│  /api/*         → proxy  │
└──────────┬───────────────┘
           │ 内部网络
           ▼
┌──────────────────────────┐
│  backend (python:3.12)   │  ← FastAPI + uvicorn
│  :8000                   │     yt-dlp、DeepSeek、接口限流
└──────────────────────────┘
```

#### 前置条件

- **Docker** ≥ 20.10 和 **Docker Compose** ≥ 2.0
- DeepSeek API 密钥（[platform.deepseek.com](https://platform.deepseek.com/)）
- （可选）HTTP 代理，如果所在地区无法直连 YouTube

#### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/1211joker/Magical-Video.git
cd Magical-Video

# 2. 创建并编辑环境变量文件
cp backend/.env.example backend/.env
vim backend/.env
```

编辑 `backend/.env`，填入：

```bash
DEEPSEEK_API_KEY=sk-your-key-here       # 必填
YTDLP_PROXY=http://127.0.0.1:7890       # 可选 — 访问 YouTube 需配置
ALLOWED_ORIGINS=https://your-domain.com # 可选 — 生产环境 CORS 白名单
```

```bash
# 3. 启动应用
docker compose up -d

# 4. 验证两个容器均在运行
docker compose ps
# 预期输出：backend (Up) + nginx (Up)

# 5. 打开浏览器访问
# http://你的服务器IP  （本地运行则 http://localhost）
```

#### 日常管理

```bash
# 查看日志
docker compose logs -f              # 所有容器
docker compose logs -f backend      # 仅后端
docker compose logs -f nginx        # 仅 nginx

# 修改 .env 或代码后重新构建
docker compose down
docker compose up -d --build        # 重新构建镜像并启动

# 停止应用
docker compose stop

# 停止并删除容器（.env 文件不受影响）
docker compose down
```

#### 更新到新版本

```bash
git pull                            # 拉取最新代码
docker compose down                 # 停止当前容器
docker compose up -d --build        # 重新构建并启动
```

#### HTTPS 配置

默认配置使用 HTTP（80 端口）。生产环境需要添加 SSL 证书，两种方式：

**方案 A — 前置反向代理（推荐）**

使用宿主机已有的 nginx/Caddy 处理 SSL，转发到 Docker nginx 容器：

```nginx
# 宿主机 nginx 示例
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:80;  # Docker nginx 端口
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**方案 B — Docker 内部 SSL**

将证书挂载到容器内，在 `nginx.conf` 中添加 443 监听，并更新 `docker-compose.yml` 暴露 443 端口。

```yaml
# docker-compose.yml nginx 服务追加
ports:
  - "80:80"
  - "443:443"
volumes:
  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
  - ./ssl/key.pem:/etc/nginx/ssl/key.pem:ro
```

#### 常见问题排查

| 问题 | 检查方法 |
|------|----------|
| `80 端口已被占用` | 有其他 Web 服务在运行。停止它或在 `docker-compose.yml` 中修改 nginx 端口 |
| 后端无法连接 DeepSeek | 检查 `backend/.env` 中的 `DEEPSEEK_API_KEY`，运行 `docker compose logs backend` 查看日志 |
| YouTube 功能不可用 | 在 `backend/.env` 中配置 `YTDLP_PROXY`，然后 `docker compose up -d --build` 重建 |
| 浏览器显示空白页 | DNS 或防火墙问题。确认服务器 IP 和端口可访问 |
| 容器反复重启 | `docker compose logs backend` — 常见原因为缺少 `.env` 或 API Key 无效 |
| 限流 429 错误 | 已触发单 IP 限流，等待 1 分钟计数器自动重置 |

### 手动部署（不使用 Docker）

```bash
cd frontend && npm run build      # 输出到 frontend/dist/
```

将 `frontend/dist/` 部署到 nginx，并将 `/api/*` 代理到 FastAPI 后端。仓库中已包含生产环境 `nginx.conf` 模板供参考。

### 代理配置

解析 YouTube 链接时，后端先检测 YouTube 连通性。若设置了 `YTDLP_PROXY`，优先验证该代理。自动模式先试直连，直连失败后尝试后端能发现的系统代理和 `HTTPS_PROXY` 等环境代理。解析、封面、字幕和下载使用检测成功的线路。

连接失败时页面会弹窗提示，并提供重新检测入口。本机部署可以在运行后端的设备上开启 VPN 或系统代理。在线部署的 YouTube 请求由服务端发出，代理需要在服务端配置。

如果代理客户端未向系统公开地址，可在 `backend/.env` 中指定它的 HTTP 或 SOCKS5 端口，然后重启后端。以下示例使用本机代理端口。

```bash
YTDLP_PROXY=http://127.0.0.1:7890
# 或使用本机的 SOCKS5 端口
# YTDLP_PROXY=socks5h://127.0.0.1:7891
```

在 Docker 中，`127.0.0.1` 指向后端容器。填写后端容器能访问的代理地址。

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

### AI 问答

1. 在"AI解析"页面完成分析后，点击导航栏中的"AI问答"。
2. 在左侧边栏浏览内容大纲，点击标题可展开/折叠详情。
3. 在底部的输入框中输入问题，按 Enter 发送。
4. AI 将基于视频字幕内容回答，尽可能引用原文。

### 快速下载

1. 在"AI解析"页面，粘贴视频链接并点击"解析视频"。
2. 视频信息加载后，向下滚动到下载区域。
3. 在清晰度网格中选择需要的分辨率。
4. 点击「下载视频」并保持页面打开。文件准备完成后，在浏览器的下载列表查看进度。

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

**AI 分析质量问题**。早期提示词导致 AI 输出过于概括，丢失关键信息。大纲和关键要点保留原文证据、术语和数字，思维导图用简短节点呈现核心主题。

**长视频 AI 超时**。超过 30 分钟的视频字幕可能超过 8000 字符，导致 30 秒超时。将字符上限提升到 25000，max tokens 提升到 10000，截断策略改为首 20% 加中 60% 加尾 20%，保证覆盖视频全程。

**Cookie 校验不准确**。早期校验仅检查行数，不完整 Cookie 也能通过。增加必填字段检测（`DedeUserID`、`SESSDATA`、`bili_jct`），缺失时给出明确错误提示。

**Emoji 跨平台渲染不一致**。Windows、macOS、Linux 对 Emoji 渲染差异大。全部替换为 Feather 风格 SVG 内联图标，使用 `currentColor` 跟随文字颜色，消除跨平台差异。

**前端巨石架构重构**。初始版本所有功能集中在单个 400 行的 `App.vue` 中。引入 vue-router（hash 模式），拆分为四个页面组件，`App.vue` 缩减为布局壳。

---

## ⚠️ 已知问题

**YouTube 分辨率限制在 360p**。Android 客户端虽然能绕过 SABR，但缺少 PO Token 无法获取 720p 及以上格式。

**Bilibili 付费内容**。1080p+ 和付费视频需要大会员 Cookie，免费用户只能下载较低画质。

**不支持批量和播放列表**。仅接受单个视频链接，播放列表链接不会被展开为单个视频。

**无下载历史记录**。没有本地或服务端的历史记录，重复分析会浪费 AI 配额。

**大文件准备**。浏览器开始接收前，服务端需要把整个视频准备到临时目录，因此仍需要足够的临时磁盘空间。

**分析选项固定**。用户无法自定义 AI 分析侧重点（例如只提取技术细节或只输出结论）。

---

## 📝 环境变量

| 变量 | 是否必填 | 说明 |
|------|----------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥 |
| `YTDLP_PROXY` | 否 | 访问 YouTube 的 HTTP 或 SOCKS5 代理地址 |
| `ALLOWED_ORIGINS` | 否 | CORS 跨域白名单（逗号分隔）。默认 `*`（开发模式允许所有来源），生产环境设为具体域名 |
| `YTDLP_NO_CHECK_CERTIFICATES` | 否 | 跳过 yt-dlp SSL 证书验证。默认 `false`（安全），仅在国内网络劫持环境下临时设为 `true` |

复制 `backend/.env.example` 为 `backend/.env` 并填入对应值。

---

## 📋 变更日志

### v0.2.0 — 生产就绪（2026-06-30）

本次更新聚焦安全加固、可靠性提升和生产部署。

**🔴 安全（P0）**：
- **CORS 白名单**：`ALLOWED_ORIGINS` 环境变量控制允许的来源。默认 `*`（开发模式），生产环境设为具体域名。
- **接口限流**：接入 `slowapi`，按端点 + IP 分级限流。`/api/analyze-stream` 5次/分、`/api/download` 3次/分、`/api/ask` 10次/分、`/api/parse` 20次/分、`/api/thumbnail` 30次/分。
- **SSL 证书验证**：yt-dlp 默认启用 SSL 证书验证，通过 `YTDLP_NO_CHECK_CERTIFICATES` 环境变量控制（默认 `false` = 安全）。
- **nginx Basic Auth**：服务端密码保护整个站点。
- 新增文件：`backend/limiter.py` — 共享 Limiter 实例，避免循环导入。

**🟠 可靠性（P1）**：
- **API 重试机制**：DeepSeek API 调用遇到临时故障（429 / 5xx / 超时）自动重试，指数退避（2s → 4s → 8s，最多 3 次）。使用 `tenacity`。不可恢复错误（401 / 402）立即失败。
- 新增文件：`backend/services/deepseek_client.py` — 带重试装饰器的共享 DeepSeek HTTP 客户端。

**🟡 架构（P2）**：
- **Docker Compose**：双容器编排 — Python 后端 + nginx 提供静态前端和 `/api` 反向代理。
- **生产 nginx 配置**：包含 gzip 压缩、SPA 路由回退、SSE 长连接支持（`proxy_read_timeout 300s`）、安全头、`client_max_body_size 10m`。
- 新增文件：`Dockerfile`、`Dockerfile.nginx`、`docker-compose.yml`、`nginx.conf`、`.dockerignore`。

**🐛 Bug 修复**：
- 修复 `/api/download` 限流失效问题——slowapi 参数名冲突（`request: DownloadRequest` 改名为 `body: DownloadRequest`）。

### v0.1.0 — 初始版本

- AI 视频分析：四维度结构化输出 + 交互式思维导图
- AI 问答：基于字幕内容的对话问答
- 视频下载：支持分辨率选择
- YouTube + Bilibili 双平台支持 + 代理配置

---

## 📄 许可证

MIT 协议。详见 [LICENSE](LICENSE)。
