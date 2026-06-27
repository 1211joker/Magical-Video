# 🎬 Magical Video — 开发日志

> 基于 yt-dlp + DeepSeek AI 的 Web 应用，AI 驱动的智能视频分析下载工具。粘贴链接 → AI 解析 → 结构化摘要 → 选择性下载。

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
    │   ├── App.vue          ← 布局壳（主题切换 + NavBar + router-view）
    │   ├── main.js          ← 入口（注册 vue-router）
    │   ├── api/index.js     ← API 请求封装
    │   ├── router/index.js  ← 四页面路由配置（hash mode）
    │   ├── components/      ← 组件目录
    │   │   ├── NavBar.vue          ← 顶部导航栏
    │   │   ├── VideoInfo.vue       ← 视频信息卡片
    │   │   ├── CookieGuide.vue     ← B站 Cookies 引导
    │   │   ├── AnalysisResult.vue  ← AI 分析结果（选项卡布局）
    │   │   ├── DownloadSection.vue ← 清晰度选择 + 下载按钮
    │   │   ├── MindMap.vue         ← markmap 思维导图
    │   │   ├── SubtitleViewer.vue  ← 带时间戳的字幕展示
    │   │   └── StickFigures.vue    ← 简笔画动画（火柴人 + 小恐龙）
    │   ├── views/           ← 页面视图
    │   │   ├── HomePage.vue        ← 首页（品牌 + 动画）
    │   │   ├── AnalysisPage.vue    ← AI解析（完整工作流）
    │   │   ├── DownloadPage.vue    ← 视频下载（快速下载）
    │   │   └── IssuesPage.vue      ← 问题及优化（开发记录）
    │   └── styles/main.css  ← 全局样式（纯黑白灰配色）
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
  - YouTube：`youtube-transcript-api` 专用库提取
  - B站：yt-dlp `--write-subs` 下载 VTT/JSON 文件 → 本地解析
  - 按优先级选最佳字幕：中文手动 → 英文手动 → 中文自动 → 英文自动
  - 支持多种字幕格式：VTT、SRT、ASS、B站原生 JSON
- 后端新建了 `deepseek_service.py`（AI 分析服务）：
  - 调用 DeepSeek chat API（`deepseek-v4-flash`），传入字幕文本
  - 思维导图优先的四维度分析：概述 + 大纲 + 要点 + 总结 + 思维导图
  - 要点附带原文证据引用（`evidence` 字段），可溯源验证
  - 智能截断：25,000 字上下文，首 20% + 中 60% + 尾 20%（覆盖视频全程）
  - 输出限制 10,000 tokens，思维导图独占约 5,000 tokens 空间
  - 思维导图要求：5-7 个一级分支、4 层深度、30+ 节点、每节点含具体信息
  - 处理各种异常：Key 无效、余额不足、API 限流、JSON 解析失败
- 后端新增 `POST /api/analyze-stream` SSE 端点：
  - 实时推送分析进度（parse → subtitles → analyze）
  - 每步有 processing/done/failed 状态 + 中文描述
  - 使用 fetch + ReadableStream 方式（非 EventSource），支持 POST 传递 cookies
  - 最终事件携带完整四维度结果 + 字幕时间戳片段
- 前端新建了 `AnalysisResult.vue` 组件（选项卡布局）：
  - 📝 概述 — 2-3 句概括视频核心内容
  - 📋 大纲 — 时间线 + 段落主题 + 详细内容
  - 🔑 要点 — 编号卡片 + 原文证据引用（blockquote 样式）
  - 💡 总结 — 可执行结论（绿色卡片）
  - 🧠 思维导图 — markmap 交互式 SVG，可缩放展开，支持 SVG 下载
  - 💬 字幕 — 原始字幕列表，每条显示 MM:SS 时间戳
- 前端新建了 `SubtitleViewer.vue` 组件：
  - 带时间戳徽章的可滚动字幕列表
  - 交替行背景色，便于阅读
  - 空状态友好提示
- 前端新建了 `MindMap.vue` 组件：
  - markmap 真实渲染（交互式 SVG）
  - SVG `<svg>` 容器确保正确的 SVG 命名空间
  - 「⬇️ 下载思维导图」按钮，导出带白底的 SVG 文件
- 前端 App.vue 新增分析流程：
  - 解析成功后显示「🤖 AI 分析视频内容」虚线按钮
  - 分析中展示三步进度条（⏳/✅/❌ 状态 + 实时消息）
  - 完成时标题显示「✅ AI 分析完成」，失败时显示「AI 分析未完成」+ 重试按钮
  - 支持取消分析（组件卸载时自动 abort）

**新增文件**：
- `backend/services/subtitle_service.py` — 字幕提取与解析（含时间戳保留）
- `backend/services/deepseek_service.py` — DeepSeek API 封装
- `frontend/src/components/AnalysisResult.vue` — 选项卡式分析结果展示
- `frontend/src/components/MindMap.vue` — markmap 思维导图渲染
- `frontend/src/components/SubtitleViewer.vue` — 带时间戳的字幕查看器

**修改文件**：
- `backend/models/schemas.py` — 新增 SubtitleSegment / OutlineItem / KeyPoint / ConclusionItem 模型，重构 AnalysisResult
- `backend/routers/analyze.py` — 新增 `POST /api/analyze-stream` SSE 端点
- `backend/config.py` — AI_ANALYSIS_TIMEOUT 30s → 90s
- `frontend/src/api/index.js` — 新增 `startAnalysis()`（fetch + ReadableStream SSE）
- `frontend/src/App.vue` — 新增分析按钮 + 进度展示 + 结果展示逻辑

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 后端 Python 导入检查 | ✅ 全部模型和服务正常导入 |
| 前端构建 | ✅ 746 模块编译通过，305ms |
| 前后端服务心跳 | ✅ 后端 8000 / 前端 5173 均正常响应 |
| 完整 AI 分析链路 | ✅ 解析 → 字幕提取 → deepseek-v4-flash 四维度分析 → 结构化结果 |
| 思维导图渲染 | ✅ markmap 交互式 SVG（官方 `<svg>` 容器），支持下载 |
| 选项卡切换 | ✅ 六选项卡（概述/大纲/要点/总结/思维导图/字幕）正常切换 |
| 字幕时间戳 | ✅ MM:SS 格式徽章，VTT/JSON 时间戳完整保留 |
| B站字幕提取 | ✅ --write-subs 直接下载 + 多格式解析（VTT/SRT/ASS/JSON） |

### ✅ 模块 4：视频下载（已完成 — 2026-06-28）

**做了什么**：
- 后端实现了 `POST /api/download` 缓存下载端点：
  - yt-dlp 下载视频到临时目录 → 完整下载后 `FileResponse` 发给浏览器 → 自动清理
  - 流式代理（yt-dlp→stdout→StreamingResponse）因 B站 风控/SSL/ffmpeg 等多种问题被废弃
  - 缓存模式：yt-dlp 自己搞定一切（cookies/ffmpeg/风控），后端只做封装，成功才返回
- **核心改进 — yt-dlp 原生格式选择器**：
  - 不再使用原始 `format_id`（如 "100022"），改用 `bestvideo[height<=1080]+bestaudio/best[height<=1080]`
  - yt-dlp 自己决定用哪个流、如何合并，后端只传分辨率字符串（如 "720p"）
  - 添加 `--format-sort vcodec:avc` 优先 H.264 编码（兼容性好），避免 AV1 在某些播放器中"有声音无画面"
  - 下载超时设为 600 秒（10 分钟），适应大文件
- 前端 `DownloadSection.vue` 组件：
  - 清晰度选择器：radio 按钮列表，显示分辨率 / 预估文件大小 / 扩展名
  - 默认选中最高画质，`formats` 变化时自动重置
  - 下载按钮：正常态 / 下载中（spinner + 禁用）/ 成功绿色 / 失败红色
  - 下载完成 3 秒后自动恢复按钮状态
- 前端 `downloadVideo()` API 函数：POST + fetch + Blob + `<a download>` 触发保存

**架构演进（三轮迭代）**：
| 版本 | 模式 | 问题 |
|------|------|------|
| v1 流式代理 | yt-dlp→stdout→Python逐块读→StreamingResponse | 中途错误 → 连接断裂 → 500；stderr 缓冲区死锁 |
| v2 缓存 + raw format_id | 临时文件 + FileResponse | B站 format_id 不准确 → "只有声音没视频" |
| v3 缓存 + 原生选择器 | 临时文件 + `bestvideo[height<=X]+bestaudio` | ✅ 稳定可靠 |

**新增/修改文件**：
- `backend/services/ytdlp_service.py` — `download_video()` 重写为缓存模式；`_extract_formats()` 简化为分辨率收集 + 文件大小预估
- `backend/routers/download.py` — `StreamingResponse` → `FileResponse` + `BackgroundTasks` 清理
- `backend/config.py` — 新增 `DOWNLOAD_TIMEOUT=600`；移除废弃的 `DOWNLOAD_CHUNK_SIZE`、`MAX_FILE_SIZE`
- `frontend/src/components/DownloadSection.vue` — 移除 `has_audio` 逻辑（原生选择器始终含音频）
- `frontend/src/api/index.js` — 简化 `downloadVideo()` 参数

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 后端导入链 | ✅ 全部正常导入 |
| 前端构建 | ✅ 编译通过 |
| B站 下载（360p） | ✅ 200 OK，8.1MB，4s，H.264+AAC 双轨 |
| B站 下载（720p） | ✅ 200 OK，视频+音频完整 |
| 格式选择器 | ✅ `bestvideo[height<=720]+bestaudio/best[height<=720]` 正确合并 |
| 中文文件名 | ✅ FileResponse 自动 UTF-8 编码，不再 latin-1 报错 |
| 错误处理 | ✅ 下载失败返回 400 JSON（非 500） |
| Cookies 未留存 | ✅ 临时文件用完即删 |

### ✅ 模块 5：样式打磨（已完成 — 2026-06-28）

**做了什么**：基于 ui-ux-pro-max skill 的设计系统审查，对前端进行全面 UI/UX 打磨。

**六大优先级**：

- **P1 响应式设计**：
  - 系统化断点：375px（极小屏）→ 640px（手机）→ 768px（平板）→ 1024px（桌面）
  - 移动端：输入区 flex 列布局、按钮全宽、卡片内边距自适应
  - 触控友好：所有按钮/标签 `min-height: 48px`，符合 Apple HIG 44pt 最低要求
- **P2 暗色模式**：
  - `[data-theme="dark"]` 完整 CSS 变量覆盖（取自 Developer Tool 调色板）
  - 跟随系统 `prefers-color-scheme: dark` 自动切换
  - 手动切换按钮（🌙/☀️），localStorage 持久化偏好
  - 支持 `[data-theme="light"]` 强制浅色模式
- **P3 过渡动画**：
  - Vue `<Transition name="fade/slide-fade">` 包裹错误横幅、视频信息、分析结果
  - 选项卡切换：`<Transition mode="out-in" name="tab">` 带方向性动画
  - 骨架屏加载态：解析中显示 `skeleton` 卡片（shimmer 动画）
  - `@media (prefers-reduced-motion: reduce)` 全局禁用动画
- **P4 视觉细节**：
  - 斑马纹对比度修复：字幕偶数列改用 `var(--bg-input)` 替代 `#f0f1f3`
  - AI 分析按钮：虚线边框 → 实线边框 + hover 提亮，降低"未完成"感
  - 思维导图：500px 固定高度 → `getBBox()` 动态计算实际高度
  - emoji→SVG：全部功能图标（选项卡、按钮、进度步骤）替换为 Feather 风格 SVG
  - 状态颜色语义化：success/danger/warning/info 使用 CSS 变量 token
- **P5 代码清理**：
  - 删除孤立 `frontend/src/style.css`（Vite 脚手架残留，含未使用的暗色代码）
  - `index.html`：`lang="en"`→`"zh-CN"`、标题→"AI 视频下载总结器"、新增 description meta
  - 新增 `theme-color` meta 标签（浅色 #f8f9fa / 暗色 #0F172A）
- **P6 无障碍**：
  - `:focus-visible` 全局样式：2px accent 色轮廓 + 2px offset
  - 跳过链接 `.skip-link`：Tab 键后出现，直达 `#main-content`
  - ARIA 属性：`role="tab/tablist/tabpanel/alert/list/listitem"`、`aria-label`、`aria-selected`
  - 键盘导航：Tab 顺序与视觉顺序一致

**修改文件**：
- `frontend/index.html` — 标题/语言/meta/viewport
- `frontend/src/styles/main.css` — 全面重写（~280 行 → ~370 行）
- `frontend/src/App.vue` — 主题切换/跳过链接/SVG 图标/Transition/骨架屏
- `frontend/src/components/AnalysisResult.vue` — emoji→SVG/Tab Transition/暗色适配
- `frontend/src/components/SubtitleViewer.vue` — 对比度修复/暗色适配
- `frontend/src/components/MindMap.vue` — 动态高度/暗色适配
- `frontend/src/components/VideoInfo.vue` — 硬编码颜色→CSS 变量
- `frontend/src/components/CookieGuide.vue` — 硬编码颜色→CSS 变量
- `frontend/src/style.css` — **已删除**（孤立文件）

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 前端构建 | ✅ 748 模块，26KB CSS + 771KB JS，311ms |
| 暗色模式切换 | ✅ 手动切换 + 系统自动 + 持久化均正常 |
| 响应式布局 | ✅ 4 个断点，组件在 375px 窄屏正常重排 |
| SVG 图标渲染 | ✅ 全部 Feather 风格内联 SVG 正常显示 |
| Vue Transition 动画 | ✅ fade/slide-fade/tab 三类过渡正常 |
| 骨架屏 | ✅ 解析中 shimmer 动画卡片正常 |
| 无障碍 | ✅ Tab 焦点可见、skip link 可用、aria 完整 |
| 减动偏好 | ✅ `prefers-reduced-motion` 禁用所有动画 |
| 向后兼容 | ✅ 后端 0 改动，所有 API 接口无变化 |

---

### ✅ 模块 6：前端重构 — Magical Video（已完成 — 2026-06-28）

**做了什么**：全面重构前端为多页面导航架构，纯黑白灰配色，增加简笔画风格趣味动画。

**架构升级**：
- 引入 `vue-router`（hash mode），从单页面巨石组件变为四页面导航结构
- `App.vue` 从 400+ 行精简为 90 行布局壳（NavBar + `<router-view>` + 页面 Transition）
- 四页面懒加载（`() => import(...)`），首屏体积优化

**四页面布局**：

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 品牌展示 + 标语 + CTA 按钮 + 简笔画动画 |
| `/analyze` | AI解析 | 完整工作流：URL输入 → 视频信息 → AI分析 → 结构化结果 → 下载 |
| `/download` | 视频下载 | 快速下载：URL输入 → 清晰度卡片选择 → 一键下载 |
| `/issues` | 问题及优化 | 8 个已解决问题 + 7 个项目不足，卡片布局 |

**配色系统**：
- 纯黑白灰 CSS 变量（`--accent: #000`），移除 indigo 主题
- 完整暗色模式支持（黑底白字），手动切换 + 系统自动检测
- Google Fonts：Fredoka（标题，圆润趣味）+ Nunito（正文，清晰易读）

**简笔画动画**（StickFigures.vue）：
- 跳舞火柴人：SVG 关节动画（头部浮动 + 四肢 CSS keyframes 摆动）
- 走路小恐龙：左右平移 + 尾巴摇摆 + 交替迈腿
- `prefers-reduced-motion` 自动降级为静态

**新增/修改文件**：
- `frontend/package.json` — 新增 `vue-router` 依赖
- `frontend/index.html` — 标题改为 Magical Video，引入 Google Fonts
- `frontend/src/main.js` — 注册 vue-router
- `frontend/src/App.vue` — **重写**为布局壳（NavBar + router-view + 主题切换）
- `frontend/src/router/index.js` — **新建**四页面路由配置
- `frontend/src/styles/main.css` — **重写**纯黑白灰 CSS 变量系统
- `frontend/src/components/NavBar.vue` — **新建**顶部导航栏（sticky + 路由高亮）
- `frontend/src/components/StickFigures.vue` — **新建**简笔画动画组件
- `frontend/src/views/HomePage.vue` — **新建**首页
- `frontend/src/views/AnalysisPage.vue` — **新建**AI解析页（从 App.vue 提取）
- `frontend/src/views/DownloadPage.vue` — **新建**视频下载页
- `frontend/src/views/IssuesPage.vue` — **新建**问题及优化页

**验证结果**：

| 测试场景 | 结果 |
|----------|------|
| 前端构建 | ✅ 771 模块，0 错误，306ms |
| 四页面导航 | ✅ vue-router hash mode，页面切换动画流畅 |
| 首页动画 | ✅ 火柴人 + 小恐龙 CSS 动画正常 |
| AI解析流程 | ✅ 完整工作流（解析→分析→结果→下载）正常 |
| 视频下载页 | ✅ 快速下载流程正常 |
| 暗色模式 | ✅ 手动/自动切换均正常 |
| 响应式 | ✅ 375px / 639px / 768px / 1024px 断点正常 |
| 无障碍 | ✅ focus-visible / skip-link / aria 完整 |
| 减动偏好 | ✅ `prefers-reduced-motion` 动画降级正常 |
| 向后兼容 | ✅ 后端 0 改动，所有 API 接口无变化 |

---

## ⚙️ AI 分析参数调优历史

思维导图经历了三轮优化，从"泛泛而谈"到"知识树"：

| 轮次 | 上下文 | max_tokens | 导图深度 | 节点要求 | 效果 |
|------|--------|-----------|---------|---------|------|
| 初版 | 8,000 | 2,000 | 无要求 | 无要求 | 只有 2 层，"大类A""具体点1"这种占位符 |
| 第一轮 | 15,000 | 4,000→6,000 | 3 层 | ≥20 节点 | 深度增加但内容仍然泛泛 |
| 第二轮 | **25,000** | **10,000** | **4 层** | **≥30 节点** | 每节点要求具体信息（数字/术语/案例名） |

核心发现：
- 上下文不足 → AI 看不到细节 → 无法输出细节。从 8K 提到 25K 是关键
- token 不够 → 概述+大纲+要点把 token 占完 → 导图被截断。提到 10K 后导图有独立空间
- 提示词示例不能是"A""B""1""2"占位符 → AI 照猫画虎。改用真实知识点示范（"过拟合定义→训练99%测试85%"）
- 思维导图必须标注为 **"最重要的输出"**，并加上"宁可少写大纲也要保证导图完整"

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

### 坑 5：yt-dlp 无法提取 YouTube 字幕（PO Token 限制）

**现象**：`yt-dlp --dump-json` 返回的 `subtitles` 和 `automatic_captions` 都是空字典，即使 `--list-subs` 显示有字幕。

**原因**：YouTube 近期加强了反爬措施，要求 web_safari 客户端提供 PO Token。yt-dlp 默认的 web 客户端受到 SABR streaming 限制，字幕 URL 无法获取。详见 yt-dlp issue #12482。

**解决**：YouTube 字幕改用 `youtube-transcript-api` 这个专门的 Python 库，它直接请求 YouTube 的 timedtext API，不受 yt-dlp 的 PO Token 限制。B站 字幕继续使用 yt-dlp（B站 没有 PO Token 问题）。

---

### 坑 6：B站 AI 分析在字幕步骤崩溃

**现象**：B站 视频解析成功，点击「AI 分析」后，进度走到"提取字幕"时所有内容突然消失，控制台报 `POST /api/parse 400`。

**原因**：
1. B站 字幕提取失败 → `analyzing = false` → 进度条瞬间消失，看起来像"崩溃了"
2. 用户本能按 Enter 重试 → 触发 `/api/parse` → 若 cookies 刚好过期 → 400 报错
3. B站 字幕提取底层 yt-dlp 异常未捕获，直接崩到 SSE 外层

**解决**：
1. 进度条改为根据 `progressSteps.length` 显隐（失败后保留，显示 ❌ 状态 + 错误信息）
2. 失败后展示「🔄 重新分析」和「✕ 关闭」按钮，无需重新解析视频
3. `_extract_bilibili_subs` 加 `except Exception` 兜底，异常时返回 None（当作无字幕）

---

### 坑 7：B站 字幕提取不到（--dump-json 不返回字幕 URL）

**现象**：B站 视频明明有中文字幕，但 AI 分析始终提示"该视频没有可用字幕"。

**原因**：和坑 5 类似，`--dump-json` 虽然能拿到视频元数据，但 `subtitles` / `automatic_captions` 字段为空，字幕 URL 无法通过 JSON 方式获取。

**解决**：放弃 `--dump-json → 取 URL → httpx 下载` 的间接路线，改用 yt-dlp 直接下载字幕文件：
- `--write-subs --write-auto-subs --sub-langs "..." --skip-download`
- 字幕文件下载到临时目录 → 按中文优先排序选最佳 → 读取解析 → 清理临时目录
- 支持多格式：VTT、SRT、ASS、B站原生 JSON

---

### 坑 8：思维导图不渲染 — SVG 命名空间问题

**现象**：思维导图组件不显示任何内容，无报错。

**原因**：markmap 的 `Markmap.create()` 内部调用 `d3.select(container).append("g")`。当容器是 `<div>` 时，d3 在 HTML 命名空间创建 `<g>` 元素，浏览器将其当作未知 HTML 元素而忽略，SVG 内容全部不渲染。markmap 官方文档明确要求容器必须是 `<svg>` 元素。

**解决**：
1. 容器从 `<div ref="svgContainer">` 改为 `<svg ref="svgContainer" width="100%" height="500">`
2. 导入从 `import * as markmap` 改为 `import { Markmap }`（命名导入）
3. `downloadSVG()` 函数适配：容器本身即为 SVG 元素

---

### 坑 9：进度条标题与实际状态不一致

**现象**：AI 分析顺利完成，所有步骤显示 ✅，但标题显示"AI 分析未完成"。

**原因**：标题逻辑仅根据 `analyzing` 布尔值判断 — 成功完成后 `analyzing = false`，触发"未完成"文本。

**解决**：改为根据步骤实际状态计算：
- 进行中 → "AI 分析进行中..."
- 全部 ✅ → "✅ AI 分析完成"
- 有 ❌ → "AI 分析未完成" + 重试按钮

---

### 坑 10：思维导图内容太"泛" — AI 输出细节不足

**现象**：思维导图只有 2 层结构，节点内容空洞（"介绍""总结""分析"），缺少视频中提到的具体知识点。

**原因**（三个叠加）：
1. **上下文太少**：字幕截断 8,000 字，AI 看不到足够多的视频内容，自然提炼不出细节
2. **token 空间不够**：概述+大纲+要点+总结把 4,000 tokens 基本占满，轮到思维导图时空间所剩无几
3. **提示词太弱**：示例用"A""B""1""2"占位符，AI 照猫画虎；没有明确的节点数量和深度要求

**解决**（三轮迭代）：
- 上下文：8,000 → 15,000 → **25,000** 字
- max_tokens：2,000 → 4,000 → 6,000 → **10,000**
- 提示词改为思维导图优先：要求 5-7 个一级分支、4 层深度、30+ 节点
- 示例改为真实知识点（"过拟合定义→训练准确率99%测试85%"），不用占位符
- 明确标注"思维导图是最重要的输出"，末尾追加"宁可少写大纲也要保证导图完整"
- 超时同步上调：30s → 60s → **90s**

---

### 坑 11：yt-dlp stdout 流式下载时 stderr 缓冲区死锁（已废弃）

**现象**：长时间下载（>15 分钟）时，下载卡死并在 60 秒后超时报错。

**原因**：`stream()` 异步生成器只读取 `process.stdout`，完全不消费 `process.stderr`。yt-dlp 在 `-o -` 模式下每秒输出一条进度信息到 stderr（约 70 字节/次），asyncio `StreamReader` 默认缓冲区仅 64KB。约 15 分钟后 stderr 缓冲区填满 → yt-dlp 阻塞在 stderr write → stdout 不再产出数据 → `process.stdout.read()` 挂起 → 超时。

**解决**：模块 4 整体架构改为缓存模式（临时文件 + FileResponse），流式代理已废弃，此坑不再适用。

---

### 坑 12：B站 下载只有声音没有画面 — AV1 编码兼容性

**现象**：B站 下载的 MP4 文件在某些播放器（QuickTime、Windows Media Player）中只有声音，画面黑屏。

**原因**：B站 部分分辨率（尤其是 360p）使用 AV1 视频编码。AV1 是新一代编码，兼容性不如 H.264。macOS QuickTime 不支持 AV1，直接静音播放。

**解决**：添加 `--format-sort vcodec:avc` 参数，告诉 yt-dlp 优先选 H.264（AVC）编码。如果该分辨率没有 H.264 版本，yt-dlp 自动降级到 AV1。

---

### 坑 13：中文文件名导致 500 — HTTP 头 latin-1 编码限制

**现象**：B站 视频下载成功，但返回 500 错误，文件无法传到浏览器。后端日志报 `UnicodeEncodeError: 'latin-1' codec can't encode characters`。

**原因**：手动构建的 `Content-Disposition` 头包含中文原始文件名，Starlette 的 `init_headers()` 将所有 HTTP 头值编码为 latin-1，中文超出 latin-1 字符集范围 → 编码失败 → 500。

**解决**：废弃手动构建的 `Content-Disposition` 头，改用 `FileResponse` 的 `filename` 参数。Starlette 内部自动处理 UTF-8 编码（`filename*=UTF-8''%E4%B8%AD%E6%96%87`），不会触发 latin-1 限制。

---

### 坑 14：B站 cookies 文件格式 — 空格 vs Tab 分隔

**现象**：用户粘贴 Netscape 格式 cookies 后，yt-dlp 报 `skipping cookie file entry due to invalid length 1`，cookies 全部无效。

**原因**：Netscape cookies 格式要求 Tab（`\t`）作为字段分隔符。用户从浏览器导出或粘贴时，Tab 常被转换成空格，导致 yt-dlp 按 Tab 切分只能得到 1 个字段。

**解决**：后端不依赖用户粘贴的格式，在写入临时文件时按空格切分前 6 个字段，剩余部分作为 value（value 本身可能含空格）。公式：`domain\tflag\tpath\tsecure\texpiration\tname\tvalue`。

---

### 坑 15：yt-dlp 原始 format_id 不可靠 — DASH 流选择问题

**现象**：使用 yt-dlp 返回的原始 `format_id`（如 B站 的 "100022"）下载，结果只有声音没有视频，或者文件格式错误。

**原因**：yt-dlp 的 `format_id` 是内部标识符，不同平台含义不同。B站 的 DASH 流（音视频分离）中，按 `format_id` 直接下载可能只拿到音频流或视频流中的一个。用 `format_id+bestaudio` 合并依赖 ffmpeg 且兼容性差。

**解决**：完全放弃原始 `format_id`。`_extract_formats()` 只收集可用分辨率，`download_video()` 使用时转化为 yt-dlp 原生选择器 `bestvideo[height<=X]+bestaudio/best[height<=X]`。yt-dlp 自己处理流选择、音视频合并、编码优先级，后端只做封装。

---

### 坑 16：YouTube 下载 HTTP 403 Forbidden — SABR 流式拦截

**现象**：YouTube 视频解析成功，但下载时报 `WARNING: [youtube] Some web client https formats have been skipped as they are missing a url. YouTube is forcing SABR streaming for this client.` + `ERROR: unable to download video data: HTTP Error 403: Forbidden`。

**原因**：YouTube 近期加强了反爬措施，对 web 客户端强制 SABR（Server And Browser Rendering）流式传输。yt-dlp 默认的 web 客户端无法获取高清 DASH 格式的 URL，降级到 format 18 后仍被 CDN 返回 403。详见 yt-dlp issue #12482。

**解决**：在 `parse_video_info()`、`_get_download_filename()`、`download_video()` 三处添加平台检测，YouTube 时自动注入 `--extractor-args "youtube:player_client=android"`，切换到 Android 客户端绕过 SABR 限制。

**当前限制**：Android 客户端没有 GVS PO Token 时只能获取 format 18（360p mp4 合并流）。高清 DASH 格式需要 PO Token（类似 B站 cookies 的机制，后续可添加支持）。

---

### 坑 17：emoji 图标跨平台不一致

**现象**：界面使用 emoji（📹📝📋🔑💡🧠💬🤖⬇️🔄❌✅⏳📜🍪📖🎬🔐⚠️💡）作为功能图标，在不同操作系统渲染效果不一致（macOS/iOS 原生 → Windows 黑白线条 → Android 彩色 blob），且无法通过 CSS color 控制颜色。

**原因**：emoji 是 font-dependent 的字符，渲染效果完全取决于操作系统自带的 emoji 字体，开发者无法控制样式。ui-ux-pro-max skill 明确规则："No emojis as structural icons — use SVG icons instead"。

**解决**：模块 5 中将全部功能图标（选项卡、按钮、进度步骤、下载按钮、关闭按钮等）替换为 Feather 风格内联 SVG（`viewBox="0 0 24 24"`），通过 `stroke="currentColor"` 继承文字颜色，在浅色/暗色模式下自动适配。标题中的装饰性 emoji 保留但不影响交互。

---


*最后更新：2026-06-28 完成模块 6 前端重构（Magical Video 四页面导航 + 纯黑白灰配色 + 简笔画动画）；模块 1-5 全部完成*
