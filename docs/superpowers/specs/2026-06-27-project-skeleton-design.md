# 模块 1：项目骨架 — 设计规格

> 日期：2026-06-27 | 状态：已完成（补写）

## 1. 概述

搭建前后端项目骨架。后端用 FastAPI（Python）提供 REST API 和 SSE 流式接口，前端用 Vue 3 + Vite 构建用户界面。两个服务通过 Vite 代理互通。

## 2. 技术选型

| 层 | 技术 | 选型理由 |
|---|------|---------|
| 后端框架 | FastAPI | Python 生态中最成熟的异步 Web 框架，自带 API 文档、SSE 支持好 |
| 下载引擎 | yt-dlp | GitHub 十几万 star，支持 1000+ 网站，命令行调用稳定可靠 |
| AI | DeepSeek API | 中文能力强、性价比高、兼容 OpenAI 格式 |
| 前端框架 | Vue 3 + Vite | 响应式数据绑定适合实时进度展示，Vite 开发体验好 |
| 思维导图 | markmap | 纯前端渲染，交互式 SVG，支持缩放/展开/导出 |

## 3. 项目结构

```
万能视频下载器项目/
├── backend/
│   ├── main.py              ← FastAPI 应用入口，注册路由、CORS
│   ├── config.py            ← 所有配置项（环境变量读取，有默认值）
│   ├── requirements.txt     ← Python 依赖清单
│   ├── .env.example         ← 密钥填写模板（DeepSeek API Key）
│   ├── routers/             ← API 接口层（薄层，只做参数校验和调用 service）
│   │   ├── analyze.py       ← 解析 + AI 分析接口
│   │   └── download.py      ← 下载接口（占位）
│   ├── services/            ← 业务逻辑层（厚层，具体实现）
│   └── models/schemas.py    ← Pydantic 数据模型，前后端数据契约
│
└── frontend/
    ├── src/
    │   ├── App.vue          ← 主页面，管理全局状态（输入、解析、分析、下载）
    │   ├── api/index.js     ← 所有后端 API 请求的统一封装
    │   ├── components/      ← UI 组件目录（每个组件独立 .vue 文件）
    │   └── styles/main.css  ← 全局样式变量和基础样式
    └── vite.config.js       ← Vite 构建配置 + 开发代理
```

**设计原则**：
- 后端 router → service 分层：router 只做参数校验和 HTTP 相关，service 做实际业务逻辑
- 前端组件单向数据流：App.vue 管理状态，通过 props 传给子组件，子组件通过事件通知父组件
- 所有 API 请求走 `api/index.js` 统一出口，不散落在组件中

## 4. 关键配置项

```python
# config.py — 所有配置集中管理，通过环境变量覆盖
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")        # 访问 YouTube 用的代理（可选）
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024             # 2GB 下载上限
DOWNLOAD_CHUNK_SIZE = 1024 * 1024                   # 流式转发每块 1MB
AI_RATE_LIMIT_PER_MIN = 10                          # 每 IP 每分钟最多 10 次 AI 分析
MAX_CONCURRENT_TASKS = 2                            # 同一用户同时最多 2 个任务
AI_ANALYSIS_TIMEOUT = 90                            # AI 分析超时秒数
YTDLP_TIMEOUT = 60                                  # yt-dlp 单次调用最长等待
```

## 5. 全局 UI 风格

黑白灰基调 + 细腻卡片层次感（微拟物风格）：

- `--bg-page: #f5f5f7`（页面背景）
- `--bg-card: #ffffff`（卡片背景）
- `--text-primary: #1d1d1f`（主文字）
- `--text-secondary: #6e6e73`（次要文字）
- `--text-muted: #aeaeb2`（弱化文字）
- `--border: #e5e5ea`（卡片边框）
- `--accent: #3b82f6`（强调色，蓝色）

卡片带细微阴影、圆角、hover 时阴影加深。

## 6. 验证标准

- 后端 `uvicorn main:app --reload` 正常启动，`/api/health` 返回 200
- 前端 `npm run dev` 正常启动，浏览器打开 `localhost:5173` 可见输入框
- 前端 `npm run build` 编译通过（用于验证组件引用、导入路径正确）
