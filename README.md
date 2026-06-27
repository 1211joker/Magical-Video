# 📹 AI 视频预览下载器 — 开发日志

> 基于 yt-dlp + DeepSeek AI 的 Web 应用，粘贴链接 → AI 摘要 → 判断是否值得下载。

---

## 技术栈速览

| 层 | 用到的技术 | 一句话解释 |
|----|-----------|-----------|
| 后端 | FastAPI (Python) | 负责接收请求、调用 yt-dlp 和 AI |
| 下载引擎 | yt-dlp | GitHub 十几万 star 的开源视频下载工具 |
| AI | DeepSeek API | 性价比最高的 AI 模型，用来分析字幕生成摘要 |
| 前端 | Vue 3 + Vite | 用户看到的界面 |
| 思维导图 | markmap | 把 AI 分析结果变成可视化知识树 |
| 通信 | SSE | 让后端能实时推送进度给前端（不用刷新页面） |

---

## 开发进度

### ✅ 模块 1：项目骨架（已完成 — 2026-06-27）

**做了什么**：
- 创建了后端项目结构（FastAPI），包含配置、路由、数据模型
- 创建了前端项目结构（Vue 3 + Vite），包含输入框和请求封装
- 安装了 yt-dlp（nightly 版本）
- 配置了前端到后端的代理，开发时两个服务能互通
- 设计了全局 UI 样式：黑白灰基调 + 细腻卡片层次感（微拟物风格）

**验证**：后端 `uvicorn` 正常启动，`/api/health` 返回成功；前端 `vite build` 编译通过。

**项目结构**：
```
万能视频下载器项目/
├── backend/                  ← 后端（大脑）
│   ├── main.py              ← 服务入口
│   ├── config.py            ← 配置中心（API Key、超时等）
│   ├── requirements.txt     ← 依赖清单
│   ├── .env.example         ← 密钥填写模板
│   ├── routers/             ← 接口层
│   │   ├── analyze.py       ← 分析相关接口
│   │   └── download.py      ← 下载相关接口
│   ├── services/            ← 业务逻辑层
│   └── models/schemas.py    ← 数据格式定义
│
└── frontend/                 ← 前端（脸面）
    ├── src/
    │   ├── App.vue          ← 主页面（链接输入框 + 结果区）
    │   ├── api/index.js     ← API 请求封装
    │   ├── components/      ← 组件目录
    │   │   ├── VideoInfo.vue    ← 视频信息卡片
    │   │   └── CookieGuide.vue  ← B站 Cookies 引导
    │   └── styles/main.css  ← 全局样式
    └── vite.config.js       ← Vite 配置（含代理）
```

---

### ✅ 模块 2：链接解析与视频信息展示（已完成 — 2026-06-27）

**做了什么**：
- 后端实现了 `POST /api/parse` 接口，收到视频链接后调用 yt-dlp 抓取元数据
- 自动识别 YouTube 和 B站 链接，遇到不支持的平台（抖音/TikTok）会给出中文提示
- 前端创建了 `VideoInfo.vue` 卡片组件，展示封面图、平台标签、标题、时长、简介
- 封面图自动适配，加载失败会显示占位图
- 平台标签带半透明毛玻璃效果（红色=YouTube，蓝色=B站）
- 时长自动格式化为 `分:秒` 或 `时:分:秒`

**新增/修改的文件**：
- `backend/services/ytdlp_service.py` — yt-dlp 封装，用 `subprocess` 调用 CLI
- `backend/routers/analyze.py` — 新增 `POST /api/parse` 接口
- `frontend/src/components/VideoInfo.vue` — 视频信息卡片组件
- `frontend/src/App.vue` — 接入 VideoInfo 组件

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| YouTube 链接解析 | ✅ 正常返回标题、封面、时长、格式 |
| TikTok（不支持） | ✅ 正确识别并提示"暂不支持TikTok" |
| 无效链接 | ✅ 提示"暂不支持此平台" |
| 前端构建 | ✅ 16 个模块编译通过，无报错 |

### ✅ 模块 2.5：B站 Cookies 支持（已完成 — 2026-06-27）

**做了什么**：
- 前端添加了可折叠的「B站 Cookies 设置」面板，包含 4 步图文引导
- 用户粘贴 cookies 后自动检测格式是否有效，显示条数确认
- 后端接收 cookies 文本，写入临时文件传给 yt-dlp，用完立刻删除
- B站 无 cookies 时给出清晰的错误提示，引导用户配置
- 错误提示支持多行显示（长文案友好）

**新增/修改的文件**：
- `backend/models/schemas.py` — ParseRequest 新增 `cookies` 字段
- `backend/services/ytdlp_service.py` — 支持 cookies 参数，临时文件写入 + 清理
- `backend/routers/analyze.py` — 传递 cookies 到服务层
- `frontend/src/components/CookieGuide.vue` — 新建，cookies 获取引导 + 输入组件
- `frontend/src/api/index.js` — parseVideo 支持 cookies 参数
- `frontend/src/App.vue` — 集成 CookieGuide 组件

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 前端构建 | ✅ 18 个模块编译通过，无报错 |
| B站 无 cookies 解析 | ✅ 提示「需要登录，请配置 cookies」 |
| cookies 格式检测 | ✅ 少于 3 条提示「格式不对」，>= 3 条显示「已检测到 N 条」 |

### ✅ 模块 3：AI 分析 — 字幕提取 + DeepSeek + 进度推送（已完成 — 2026-06-27）

**做了什么**：
- 后端新建了 `subtitle_service.py`（字幕提取服务）：
  - 从 yt-dlp dump-json 中获取字幕 URL
  - 按优先级选最佳字幕：中文手动 → 英文手动 → 中文自动 → 英文自动
  - 下载 VTT/SRT 字幕文件 → 解析为纯文本（去掉时间戳、HTML标签、序号）
- 后端新建了 `deepseek_service.py`（AI 分析服务）：
  - 调用 DeepSeek chat API，传入字幕文本
  - 自定义系统提示词，要求 AI 返回结构化 JSON（摘要 + 关键要点 + 思维导图）
  - 处理各种异常：Key 无效、余额不足、API 限流、JSON 解析失败
  - 字幕过长时智能截断（取前 60% + 后 20%）
- 后端新增 `POST /api/analyze-stream` SSE 端点：
  - 实时推送分析进度（parse → subtitles → analyze）
  - 每步有 processing/done/failed 状态 + 中文描述
  - 使用 fetch + ReadableStream 方式（非 EventSource），支持 POST 传递 cookies
- 前端新建了 `AnalysisResult.vue` 组件：
  - 📝 核心摘要卡片 — 2-3 句话总结
  - 🔑 关键要点列表 — 编号圆点 + 卡片样式 + 交错淡入动画
  - 🧠 思维导图占位预览 — 分支节点 + 标签云（模块 4 升级为交互式 markmap）
- 前端 App.vue 新增分析流程：
  - 解析成功后显示「🤖 AI 分析视频内容」虚线按钮
  - 分析中展示三步进度条（⏳/✅/❌ 状态 + 实时消息）
  - 分析完成自动展示 AnalysisResult 组件
  - 支持取消分析（组件卸载时自动 abort）

**新增文件**：
- `backend/services/subtitle_service.py` — 字幕提取与解析
- `backend/services/deepseek_service.py` — DeepSeek API 封装
- `frontend/src/components/AnalysisResult.vue` — 分析结果展示组件

**修改文件**：
- `backend/routers/analyze.py` — 新增 `POST /api/analyze-stream` SSE 端点
- `frontend/src/api/index.js` — 新增 `startAnalysis()`（fetch + ReadableStream SSE）
- `frontend/src/App.vue` — 新增分析按钮 + 进度展示 + 结果展示逻辑

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 后端 Python 导入检查 | ✅ 3 个新模块全部正常导入 |
| 前端构建 | ✅ 20 个模块编译通过，171ms |
| 前后端服务心跳 | ✅ 后端 8000 / 前端 5173 均正常响应 |

**⚠️ 使用前提**：需要先在 `backend/.env` 中配置 `DEEPSEEK_API_KEY`，否则 AI 分析会提示 Key 未配置。

### 🔲 模块 4：结果展示（摘要 + 要点 + 思维导图）

### 🔲 模块 5：视频下载 + 样式打磨

---

## 启动方式

```bash
# 终端 1：启动后端（端口 8000）
cd backend
cp .env.example .env   # 第一次需要，然后编辑 .env 填入 DeepSeek API Key
python3 -m uvicorn main:app --reload

# 终端 2：启动前端（端口 5173）
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`

---

---

## 🐛 踩坑记录

开发过程中遇到的问题和解决方案，方便后续回顾。

### 坑 1：`yt-dlp` 命令找不到

**现象**：后端调用 yt-dlp 时报 `No such file or directory`

**原因**：`yt-dlp` 通过 pip 安装到了用户目录（`~/Library/Python/3.9/bin/`），不在系统 PATH 中。直接用 `yt-dlp` 命令找不到。

**解决**：用 `python3 -m yt_dlp` 代替 `yt-dlp`。在 `ytdlp_service.py` 中使用 `sys.executable` 获取当前 Python 路径：
```python
cmd = [sys.executable, "-m", "yt_dlp", ...]
```

---

### 坑 2：B站 需要 cookies 才能获取数据

**现象**：粘贴 B站 链接后返回 400 错误，提示需要登录

**原因**：B站 的部分接口需要登录态验证，没有 cookies 会返回 412/403

**解决**：
1. 前端加了折叠面板，引导用户用 Chrome 插件导出 cookies
2. 后端收到 cookies 文本后写入临时文件 → 传给 yt-dlp `--cookies` 参数 → 用完立刻删除

---

### 坑 3：Pydantic 校验失败 — 时长字段类型不匹配

**现象**：请求返回 500，报错 `Input should be a valid integer, got a number with a fractional part`

**原因**：yt-dlp 返回的视频时长是**小数**（如 `706.645` 秒），但 Pydantic schema 定义的是 `int` 类型。Pydantic v2 默认严格校验，不会自动把 float 转成 int。

**解决**：在赋值前强制转整数 `int(data.get("duration", 0) or 0)`。对用户来说少 0.6 秒无感知。

---

### 坑 4：B站 封面图不显示（防盗链）

**现象**：视频信息解析成功，但封面图裂了，控制台有图片加载失败的错误

**原因**：B站 CDN 做了**防盗链**，检查 HTTP 请求的 `Referer` 头。浏览器直接从我们的页面加载 B站 图片时，Referer 是我们的域名而不是 `bilibili.com`，被 CDN 拒绝。

**解决**：加了后端封面图代理接口 `GET /api/thumbnail?url=...`：
1. 前端不直接加载 B站 图片链接，改为请求后端代理
2. 后端用 `httpx` 去取图，伪装 `Referer: https://www.bilibili.com`
3. 取到图片后流式返回给前端，顺便加了 1 天缓存

---

*最后更新：2026-06-27 完成模块 1 + 2 + 2.5 + 3*
