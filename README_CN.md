[English](README.md) | [中文](README_CN.md)

# 🎬 Magical Video

Magical Video 是一个基于 AI 的视频内容分析工具。输入 YouTube、Bilibili 或理大 Panopto 视频链接后，程序提取可用字幕，通过所选模型生成概述、大纲、要点、总结和交互式思维导图。分析完成后，可以根据字幕向 AI 追问。Panopto 录像在平台为当前账号提供官方下载时也可离线保存。

核心价值在于 AI 分析流程：一段 30 分钟的视频，可以在不到一分钟内浏览其结构化拆解结果（概述、大纲、关键要点、结论及知识树思维导图），还可通过 AI 问答针对特定话题深入追问。

[![Python](https://img.shields.io/badge/Python-3.12%20or%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4fc08d.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-8.1-646cff.svg)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<img src="screenshot.png" alt="Magical Video 截图" width="100%">

---

## 🧠 核心功能：AI 视频分析

主流程接收视频链接，输出四维度分析结果及交互式思维导图：

1. **解析**：yt-dlp 获取视频元数据（标题、时长、封面）。
2. **提取字幕**。YouTube 使用 `youtube-transcript-api`，Bilibili 使用 yt-dlp 获取 VTT、SRT 或 JSON 字幕，理大 Panopto 使用播放器提供的带时间戳字幕。后端统一整理异常断行、跨句片段和滚动重复行。
3. **AI 分析**。字幕发送给所选模型，生成有原文依据的结构化结果。分析进度通过 SSE 实时推送到前端。
4. **结果展示**：选项卡式界面呈现概述、大纲、要点、结论四个维度，并包含基于 markmap 的交互式思维导图。

大纲和要点保留原文中的术语、数字、案例和直接引用。思维导图将相近内容归到同一主题，最多展示 3 层，打开时展开全部节点。

---

## 💬 核心功能：AI 问答

AI 分析完成后，可以就视频内容向 AI 提问，获取基于字幕原文的回答：

1. **上下文加载**：问答页面自动加载最近的分析结果，在可折叠侧边栏中展示完整的内容大纲（概述、大纲、要点、总结）。
2. **自由提问**。后端将字幕、分析摘要和近期对话发送给所选模型，并要求回答引用原文证据。
3. **聊天界面**：简洁的对话式 UI，气泡消息、原文引用 blockquote 样式、AI 思考时的打字动画。

问答系统提示词要求 AI 严格基于字幕内容回答，用「」标注原文引用，视频未涉及的内容如实告知。

用用户名注册登录后，可将解析保存到个人资料库，按分组整理视频、生成课程 Wiki，或跨视频提问并继续历史对话。同一账号可在不同设备读取个人资料。已保存的分析通过后台任务执行，也可从「最近解析」找回进度。[本地资料库说明](docs/长期记忆与课程Wiki-本地开发计划.md)

---

## 📥 辅助功能：视频下载

输入链接后可以选择可用的分辨率和格式。服务端用 yt-dlp 准备文件，随后由浏览器的下载管理器接收文件并显示进度。

**当前限制**：YouTube 下载因使用 Android 客户端绕过 SABR 风控，最高仅支持 360p（详见已知问题）。

---

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 账号与个人资料 | SQLite |
| 下载引擎 | yt-dlp |
| AI 服务 | DeepSeek 官方、OpenAI、OpenCode Go |
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
│   │   ├── analyze.py            # 视频解析、字幕提取、流式分析和封面接口
│   │   ├── download.py           # /api/download 和浏览器下载任务
│   │   └── qa.py                 # /api/ask — AI 问答
│   └── services/
│       ├── ytdlp_service.py      # yt-dlp 子进程封装
│       ├── subtitle_service.py   # 字幕提取与解析
│       ├── subtitle_format.py    # 跨平台字幕整理
│       ├── analysis_service.py   # 字幕分析
│       ├── qa_service.py         # 视频问答上下文
│       └── ai_client.py         # 模型配置、HTTP 请求和重试
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
    │   │   ├── VideoSessionGuide.vue
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

- Python 3.12 或 3.13
- Node.js 22.12 及以上
- ffmpeg（推荐安装；yt-dlp 合并视频和音频时需要）
- 至少一个 [AI 服务](#-环境变量)的 API Key，用于字幕分析和问答
- yt-dlp（通过 pip 自动安装）
- **YouTube 代理**（国内网络无法直连 YouTube，需配置代理才能使用 YouTube 相关功能；见下方[代理配置](#代理配置)）

### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # 初次配置时执行，再填入所选服务的 API Key
uvicorn main:app --reload --port 8000
```

本地 API 服务在 `http://127.0.0.1:8000` 提供服务。业务接口使用登录后的 Cookie。

### 前端

```bash
cd frontend
npm install
npm run dev                       # 开发服务器 http://127.0.0.1:5173
```

Vite 将 `/api` 代理到本机后端。用 `http://127.0.0.1:5173` 打开页面，在「登录 → 注册账号」设置用户名和密码。自定义地址时同步设置 `SITE_ORIGIN`。[本地启动与注册](./docs/长期记忆与课程Wiki-本地开发计划.md#本地运行)

### 🐳 Docker 部署

项目用 Docker Compose 运行两个容器。Nginx 提供 Vue 页面和 `/api` 代理，FastAPI 在内部网络处理账号、字幕、AI 请求和个人资料库。服务器的 Nginx 或宝塔负责 HTTPS。[完整 Docker 部署教程](docs/长期记忆与课程Wiki-服务器部署计划.md)

#### 1. 获取项目和填写配置

服务器需要 Git、Docker Engine、Compose 插件和一个 HTTPS 域名。首次部署时执行以下命令。

```bash
git clone --branch main https://github.com/1211joker/Magical-Video.git
cd Magical-Video
install -m 600 backend/.env.example backend/.env
vi backend/.env
```

在 `backend/.env` 填写浏览器访问的 HTTPS 地址、正整数 AI 日额度及所用模型的 API Key。已有部署继续编辑原文件。

```dotenv
SITE_ORIGIN=https://video.example.com
AUTH_AI_ACCOUNT_DAILY=30
AUTH_AI_SITE_DAILY=300
DEEPSEEK_API_KEY=填写自己的密钥
```

也可按示例文件配置 `OPENAI_API_KEY` 或 `OPENCODE_GO_API_KEY`。[环境变量示例](backend/.env.example)

#### 2. 构建并等待就绪

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

两个服务应显示 `healthy`。宿主机或宝塔把整个 HTTPS 站点反代到 `http://127.0.0.1:8080`。从域名进入「登录 → 注册账号」，就能使用个人资料库。需要管理员角色时，注册目标账号后在服务器运行 `docker compose exec backend python -m maintenance promote-admin --username site_admin`。

#### 3. 备份、升级与排障

账号和资料保存在 `app-data` 卷，语义模型缓存在 `model-cache` 卷。升级前按教程备份账号与个人库，然后运行 `git pull --ff-only origin main` 和上面的构建启动命令。`docker compose stop` 可以暂停服务。`docker compose down -v` 会删除 Compose 管理的数据卷。

出现启动问题时，先运行 `docker compose ps` 和 `docker compose logs --tail=100 backend nginx`。反代配置、端口冲突、403 来源错误、旧库导入和新卷恢复的操作步骤都在部署教程。[HTTPS 与备份恢复](docs/长期记忆与课程Wiki-服务器部署计划.md)

### 手动部署（不使用 Docker）

```bash
cd frontend && npm run build      # 输出到 frontend/dist/
```

将 `frontend/dist/` 部署到 Nginx，并将 `/api/*` 代理到 FastAPI 的实际监听地址。使用 HTTPS 站点时把公开地址填入 `SITE_ORIGIN`。

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
3. 在输入框中粘贴 YouTube、Bilibili 或理大 Panopto 视频链接。
4. B站或理大 Panopto 需要登录时，按「连接会话」面板的指引填写。
5. 点击"解析视频"，等待视频信息（标题、时长、封面）加载。
6. 选择 AI 模型并点击「开始分析」。后端提取字幕并交给所选模型，页面实时显示进度。
7. 分析完成后，可浏览概述、大纲、要点、总结和思维导图，并在「字幕」选项卡对照整理后的原文。

### 提取并下载字幕

1. 在「AI解析」页面解析视频后，点击「提取字幕」。这一步可以独立预览字幕，无需启动 AI 分析。
2. 点击「下载字幕 (.vtt)」，浏览器会保存包含每条字幕起止时间的文件。完成 AI 分析后，也可以从结果的「字幕」选项卡下载。

YouTube 支持省略 `https://` 的短链接，例如 `youtu.be/hwP7WQkmECE`。整理时保留普通字幕的重复台词、重叠时长和韩语词间空格。Panopto 首选轨清理后为空时会继续尝试备选轨。实测与回归记录见[字幕功能验收](docs/上线部署改进清单.md#2026-11-26-字幕功能验收)。

### AI 问答

1. 分析完成后，点击结果旁的「去问答」。
2. 在左侧边栏浏览内容大纲，点击标题可展开/折叠详情。
3. 在底部的输入框中输入问题，按 Enter 发送。
4. AI 将基于视频字幕内容回答，尽可能引用原文。

### 快速下载

1. 在"AI解析"页面，粘贴视频链接并点击"解析视频"。
2. 在视频预览卡片里展开「下载视频」。
3. 选择需要的分辨率。
4. 点击「开始下载」并保持页面打开。文件准备完成后，在浏览器的下载列表查看进度。

### 连接 B站和理大 Panopto 会话

1. 粘贴视频链接，点击链接下方的「连接会话」，或在解析提示登录时打开同一个面板。
2. 在面板提供的官方页面登录。打开 Chrome 或 Edge 开发者工具（Mac 按 `⌥⌘I`，Windows 按 `Ctrl+Shift+I`），在顶部找到「应用（Application）」。标签隐藏时，点右侧 `»`。
3. 在左侧「存储（Storage）→ Cookies」中选择站点。B站在 `www.bilibili.com` 下复制 `SESSDATA` 的值，理大 Panopto 在 `polyu.ap.panopto.com` 下复制 `.ASPXAUTH` 的值。
4. 把值填入本地项目并连接会话。两个平台的会话都只保留在当前解析页，刷新或离开后需要重新连接。

### 理大 Panopto 课程录像

1. 在「AI 解析」中粘贴 `https://polyu.ap.panopto.com/Panopto/Pages/Viewer.aspx?id=…` 并解析。公开视频可直接获取信息。
2. 如页面提示连接会话，在官方课程页登录并确认可以播放，再按上面的共用流程连接。
3. 有字幕时，选择模型并点击「AI 分析视频内容」。字幕会发送给所选服务，结果可用于后续问答。Panopto 为当前账号提供官方下载时，浏览器直接接管 MP4 下载。

---

## 🔧 技术挑战与解决方案

**Bilibili 会话**。用户从浏览器内置开发者工具复制 `SESSDATA`。后端校验该值，生成仅适用于 B站域名的 Netscape 临时文件，供 yt-dlp 解析、取字幕和下载，请求结束后删除。

**YouTube SABR 流式拦截**。YouTube 的服务端与浏览器协同渲染机制拦截默认 Web 客户端的流媒体请求。通过切换到 Android 客户端（`youtube:player_client=android`）绕过。代价是无 PO Token 时仅能获取 360p 格式。

**Bilibili 字幕提取失败**。`yt-dlp --write-subs` 对 Bilibili 不产生字幕文件，`dump-json` 也不包含字幕 URL，导致 AI 分析管线中断。改为通过 yt-dlp 直接下载 VTT 文件再用 Python 解析，同时返回纯文本（供 AI 使用）和带时间戳的片段（供前端展示）。

**AI 分析质量问题**。早期提示词导致 AI 输出过于概括，丢失关键信息。大纲和关键要点保留原文证据、术语和数字，思维导图用简短节点呈现核心主题。

**长视频 AI 超时**。超过 30 分钟的视频字幕可能超过 8000 字符，导致 30 秒超时。将字符上限提升到 25000，max tokens 提升到 10000，截断策略改为首 20% 加中 60% 加尾 20%，保证覆盖视频全程。

**会话重试**。解析、字幕或下载收到明确的登录错误时，页面提示用户更新对应平台的会话。

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
| `DEEPSEEK_API_KEY` | 三家至少配置一家 | DeepSeek 官方 API 密钥 |
| `OPENAI_API_KEY` | 同上 | OpenAI API 平台的密钥 |
| `OPENCODE_GO_API_KEY` | 同上 | 开通 OpenCode Go 的工作区 API Key |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-v4-flash` |
| `OPENAI_MODEL` | 否 | Responses API 的模型 ID，默认 `gpt-5.4-mini` |
| `OPENCODE_GO_MODEL` | 否 | Go 模型 ID，默认 `deepseek-v4.1-flash` |
| `YTDLP_PROXY` | 否 | 访问 YouTube 的 HTTP 或 SOCKS5 代理地址 |
| `SITE_ORIGIN` | 生产必填 | 登录和写入请求使用的站点来源。开发默认 `http://127.0.0.1:5173` |
| `AUTH_AI_ACCOUNT_DAILY`、`AUTH_AI_SITE_DAILY` | 生产必填 | 每账号和全站每天可发出的 AI 请求数 |
| `YTDLP_NO_CHECK_CERTIFICATES` | 否 | 跳过 yt-dlp SSL 证书验证。默认 `false`（安全），仅在国内网络劫持环境下临时设为 `true` |

首次配置时，从 `backend/.env.example` 创建 `backend/.env`。把 API Key 写入对应项并重启后端，即可在分析页和问答页选择已配置的模型。默认按 DeepSeek 官方、OpenAI、OpenCode Go 的顺序选择第一个已配置的服务。分析页和问答页共用当前浏览器的模型选择。课程 Wiki 沿用生成该视频分析的模型。

API Key 可分别从 DeepSeek 平台、OpenAI API 平台或 OpenCode Console 获取。OpenCode Go 的对话接口面向编码代理，DeepSeek 模型还需要相应的订阅和区域权限。[DeepSeek 平台](https://platform.deepseek.com/)、[OpenAI API Keys](https://platform.openai.com/api-keys)、[OpenCode Go](https://opencode.ai/docs/console/go/)

---

## 📋 变更日志

### 2026-11-28 — 账号与 Docker 部署

- 用户名注册登录，账号资料独立，可在不同设备读取。维护者可通过命令设置管理员角色。
- Docker Compose 等待后端与 Nginx 通过健康检查，账号资料和模型缓存使用持久卷。部署教程包含 HTTPS 反代、升级及备份恢复。

### v0.2.0 — 生产就绪（2026-06-30）

本次更新聚焦安全加固、可靠性提升和生产部署。

**🔴 安全（P0）**：
- **站点会话与请求来源**。业务 API 需要登录，修改请求校验 `SITE_ORIGIN`，个人资料与下载按账号隔离。
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
