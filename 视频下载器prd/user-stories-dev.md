# 开发任务拆解：AI 万能视频下载总结器 (MVP)

> 基于 PRD 的 P0/P1 用户故事拆解为可执行开发任务。按依赖顺序排列。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI (Python async) |
| 下载引擎 | yt-dlp |
| AI | DeepSeek API (REST) |
| 通信 | SSE (Server-Sent Events) |
| 前端 | Vue 3 + Vite |
| 思维导图 | markmap |
| 样式 | 黑白灰 ChatGPT 风格 |

---

## 阶段 1：项目骨架与环境

### 任务 1.1：初始化后端项目

**文件**：
- 创建：`backend/`
- 创建：`backend/requirements.txt`
- 创建：`backend/main.py`
- 创建：`backend/config.py`

**内容**：
```
backend/
├── main.py         # FastAPI 应用入口
├── config.py       # 配置（DeepSeek API key、代理等）
├── requirements.txt
├── routers/        # API 路由
│   ├── __init__.py
│   ├── analyze.py  # 链接分析 + AI 摘要
│   └── download.py # 视频下载
├── services/       # 业务逻辑
│   ├── __init__.py
│   ├── ytdlp_service.py    # yt-dlp 封装
│   ├── deepseek_service.py # DeepSeek API
│   └── subtitle_service.py # 字幕处理
└── models/         # 数据模型
    ├── __init__.py
    └── schemas.py  # Pydantic schemas
```

**配置项**：
```python
# config.py
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")  # 可选代理
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
```

**依赖**：
```txt
fastapi>=0.110.0
uvicorn[standard]
yt-dlp>=2025.10.14
httpx>=0.27.0
pydantic>=2.0
python-dotenv>=1.0
```

---

### 任务 1.2：初始化前端项目

**文件**：
- 创建：`frontend/`
- 运行：`npm create vite@latest frontend -- --template vue`
- 创建：`frontend/src/` 目录结构

```
frontend/
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── api/            # API 请求
│   │   └── index.js
│   ├── components/     # 组件
│   │   ├── LinkInput.vue       # 链接输入框
│   │   ├── VideoInfo.vue       # 视频元数据展示
│   │   ├── AnalysisProgress.vue # SSE 进度条
│   │   ├── AISummary.vue       # AI 摘要
│   │   ├── KeyPoints.vue       # 核心要点
│   │   ├── MindMap.vue         # 思维导图
│   │   └── DownloadPanel.vue   # 下载面板
│   └── styles/
│       └── main.css    # 全局样式（黑白灰）
```

---

## 阶段 2：链接解析与信息展示

### 任务 2.1：平台识别 + 元数据提取

**文件**：
- 修改：`backend/services/ytdlp_service.py`
- 修改：`backend/routers/analyze.py`
- 修改：`backend/models/schemas.py`

**API**：`POST /api/parse`

```python
# schemas.py
class ParseRequest(BaseModel):
    url: str

class ParseResponse(BaseModel):
    platform: str          # "youtube" | "bilibili" | "unsupported"
    title: str
    duration: int          # 秒
    thumbnail: str         # 缩略图 URL
    description: str
    formats: list[FormatInfo]  # 可用清晰度列表

class FormatInfo(BaseModel):
    format_id: str
    resolution: str
    filesize: int | None
    ext: str
```

**实现要点**：
- `yt-dlp --dump-json URL` 提取元数据
- 平台识别：URL 匹配 youtube.com / youtu.be / bilibili.com
- 错误处理：不支持的链接 → 返回 `{"platform": "unsupported"}`
- 需要代理时通过 config.py 配置

**依赖**：任务 1.1 ✅

---

### 任务 2.2：前端链接输入 + 信息展示

**文件**：
- 创建：`frontend/src/components/LinkInput.vue`
- 创建：`frontend/src/components/VideoInfo.vue`
- 修改：`frontend/src/App.vue`
- 修改：`frontend/src/api/index.js`

**组件**：

`LinkInput.vue`：
- 输入框（居中，类似 ChatGPT 风格）
- 粘贴自动检测合法性（是否含视频链接）
- 提交按钮
- 状态：idle / loading / error

`VideoInfo.vue`：
- 展示缩略图、标题、时长、平台标志
- 平台标志 YTB/B站 图标
- 时长格式化（mm:ss 或 hh:mm:ss）

**API 封装**：
```js
// api/index.js
const API_BASE = '/api'

export async function parseVideo(url) {
  const res = await fetch(`${API_BASE}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function createAnalysisSSE(url) {
  // 返回 EventSource 用于 SSE
  return new EventSource(`${API_BASE}/analyze?url=${encodeURIComponent(url)}`)
}
```

**依赖**：任务 1.2 ✅, 2.1 ✅

---

## 阶段 3：字幕 + AI 摘要

### 任务 3.1：字幕提取

**文件**：
- 创建：`backend/services/subtitle_service.py`

```python
# subtitle_service.py
async def extract_subtitles(url: str, platform: str) -> dict:
    """
    提取视频字幕。
    返回: {"success": True, "subtitles": "SRT 文本", "lang": "zh-Hans"}
           {"success": False, "error": "无字幕可用"}
    """
    # 对于 B站：yt-dlp --write-subs --sub-langs all --skip-download URL
    # 对于 YouTube：yt-dlp --write-subs --sub-langs en,zh-Hans,zh-Hant --skip-download URL
    # 需要处理 PO token 问题（YouTube）
    pass
```

**B站字幕实现**（已验证可行）：
```bash
yt-dlp --cookies-from-browser chrome \
       --write-subs --sub-langs all \
       --skip-download \
       --convert-subs srt \
       -o "%(id)s" \
       "B站URL"
```

**YouTube 字幕实现**（需处理 PO token）：
```bash
yt-dlp --extractor-retries 3 \
       --write-subs --sub-langs "en,zh-Hans,zh-Hant" \
       --skip-download \
       "YTB_URL"
```

> PO token 处理：需要调研如何在无浏览器环境下获取 PO token。备选方案：使用 yt-dlp 社区提供的 `--po-token` 参数或第三方工具。

**错误处理**：
- 平台无字幕 → 返回错误，前端提示"本视频暂无可用字幕"
- 提取失败 → 返回错误，可重试

---

### 任务 3.2：DeepSeek AI 摘要

**文件**：
- 创建：`backend/services/deepseek_service.py`

```python
# deepseek_service.py
import httpx
import json

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"

SYSTEM_PROMPT = """你是视频内容分析助手。你需要根据视频字幕，输出：
1. 核心摘要（2-3句话概括视频核心内容）
2. 关键要点（列表形式，每个要点一条）
3. 知识结构（JSON格式用于生成思维导图，控制在3层以内）

输出格式为 JSON：
{
  "summary": "...",
  "key_points": ["要点1", "要点2", ...],
  "mindmap": {
    "name": "视频主题",
    "children": [
      {"name": "章节1", "children": [{"name": "子点1"}, {"name": "子点2"}]}
    ]
  }
}
"""

async def analyze_subtitles(subtitle_text: str, api_key: str) -> dict:
    """调用 DeepSeek 分析字幕，返回摘要 JSON"""
    
    # 字幕截断（DeepSeek 上下文长度有限）
    max_chars = 30000  # 约 7500 tokens
    truncated = subtitle_text[:max_chars]
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(DEEPSEEK_API, json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下视频字幕：\n\n{truncated}"}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }, headers={"Authorization": f"Bearer {api_key}"})
        
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
```

**成本估算**：
- 每字幕平均 5000 tokens
- DeepSeek 价格 ¥0.001/1K tokens（输入）
- 每次调用约 **¥0.01**

---

### 任务 3.3：SSE 实时推送 + 分析流程编排

**文件**：
- 修改：`backend/routers/analyze.py`

**API**：`GET /api/analyze?url=xxx`

```python
# analyze.py
@router.get("/analyze")
async def analyze_video(url: str, request: Request):
    async def event_generator():
        # Step 1: 解析链接
        yield {"event": "step", "data": json.dumps({"step": "parsing", "status": "processing", "message": "正在解析视频链接..."})}
        info = await parse_video_info(url)
        yield {"event": "step", "data": json.dumps({"step": "parsing", "status": "done"})}
        
        # Step 2: 提取字幕
        yield {"event": "step", "data": json.dumps({"step": "subtitles", "status": "processing", "message": "正在提取字幕..."})}
        subs = await extract_subtitles(url, info["platform"])
        if not subs["success"]:
            yield {"event": "step", "data": json.dumps({"step": "subtitles", "status": "failed", "message": "无可用字幕，AI 分析跳过"})}
            yield {"event": "done", "data": json.dumps({"error": "no_subtitles"})}
            return
        yield {"event": "step", "data": json.dumps({"step": "subtitles", "status": "done", "message": f"字幕提取完成（{len(subs['text'])}字符）"})}
        
        # Step 3: AI 分析
        yield {"event": "step", "data": json.dumps({"step": "analyzing", "status": "processing", "message": "AI 正在分析内容..."})}
        try:
            analysis = await analyze_subtitles(subs["text"], DEEPSEEK_API_KEY)
            yield {"event": "step", "data": json.dumps({"step": "analyzing", "status": "done"})}
        except Exception as e:
            yield {"event": "step", "data": json.dumps({"step": "analyzing", "status": "failed", "message": "AI 分析失败"})}
            yield {"event": "done", "data": json.dumps({"error": str(e)})}
            return
        
        # Step 4: 完成，返回结果
        yield {"event": "result", "data": json.dumps(analysis)}
        yield {"event": "done", "data": json.dumps({"status": "ok"})}
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 任务 3.4：前端 SSE 接收 + 实时进度展示

**文件**：
- 创建：`frontend/src/components/AnalysisProgress.vue`
- 修改：`frontend/src/App.vue`

**AnalysisProgress.vue**：
```
进度步骤：
□ 解析链接         → ✅ 已完成
□ 提取字幕         → ⏳ 处理中...
□ AI 内容分析      → ⏳ 等待中...
□ 生成结果         → ⏳ 等待中...
```

**实现**：
```js
// App.vue
const sse = createAnalysisSSE(url.value)
sse.addEventListener('step', (e) => {
  const data = JSON.parse(e.data)
  // 更新进度状态
  progressSteps.value[data.step] = data
})
sse.addEventListener('result', (e) => {
  const data = JSON.parse(e.data)
  analysisResult.value = data
  sse.close()
})
sse.addEventListener('done', (e) => {
  sse.close()
})
```

**错误处理**：
- SSE 连接断开 → 显示"连接中断，请重试"
- 分析失败 → 显示错误信息和重试按钮

**依赖**：任务 3.3 ✅

---

## 阶段 4：结果展示

### 任务 4.1：AI 摘要 + 核心要点展示

**文件**：
- 创建：`frontend/src/components/AISummary.vue`
- 创建：`frontend/src/components/KeyPoints.vue`
- 修改：`frontend/src/App.vue`

**AISummary.vue**：
- 显示 AI 生成的 2-3 句摘要
- 打字机效果（可选）
- 复制按钮

**KeyPoints.vue**：
- 显示核心要点列表
- 每点前带 ✅ 或 ▢ 图标
- 简洁的卡片样式

---

### 任务 4.2：思维导图

**文件**：
- 创建：`frontend/src/components/MindMap.vue`

**实现**：
```vue
<template>
  <div class="mindmap-container" ref="container">
    <svg ref="svg"></svg>
    <button @click="exportPNG" class="export-btn">导出图片</button>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as markmap from 'markmap-view'
import { Transformer } from 'markmap-lib'

const props = defineProps({ data: Object })
const container = ref(null)
const svg = ref(null)

let mm = null

onMounted(() => {
  if (props.data) renderMindmap()
})

watch(() => props.data, () => {
  if (props.data) renderMindmap()
})

function renderMindmap() {
  const transformer = new Transformer()
  const { root } = transformer.transform(props.data)
  if (mm) mm.destroy()
  mm = new markmap.Markmap(svg.value, {
    colorFreezeLevel: 2,
    zoom: true,
    pan: true,
  })
  mm.setData(root)
  mm.fit()
}

function exportPNG() {
  // 使用 html2canvas 或 SVG 转 PNG
  // 参考 markmap 文档的导出方法
}
</script>
```

**依赖**：markmap-lib + markmap-view 依赖包

---

## 阶段 5：视频下载

### 任务 5.1：服务器端下载代理

**文件**：
- 创建：`backend/routers/download.py`
- 修改：`backend/main.py`

**API**：`GET /api/download?url=xxx&format_id=xxx`

```python
@router.get("/download")
async def download_video(url: str, format_id: str = "best"):
    """
    流式代理下载视频。
    不缓存文件到服务器，直接流式转发给客户端。
    """
    # 使用 yt-dlp 获取下载 URL
    # 然后用 httpx 流式转发
    # 设置 Content-Disposition 头
```

**实现要点**：
- 使用 `yt-dlp -g URL` 获取直链
- 使用 `httpx` 或 `aiohttp` 流式转发
- 设置 `Content-Disposition` 头让浏览器触发下载
- 支持 `Range` 头（断点续传）
- 不支持超大文件（>2GB）留到付费版本

---

### 任务 5.2：前端下载面板

**文件**：
- 创建：`frontend/src/components/DownloadPanel.vue`

**组件**：
- 清晰度下拉选择（从 parse 阶段获取的 formats 列表）
- 文件大小展示
- 下载按钮
- 下载进度条（基于 fetch 的 Content-Length）
- 状态：idle / downloading / done / error

```vue
<template>
  <div class="download-panel" v-if="formats.length">
    <select v-model="selectedFormat">
      <option v-for="f in formats" :key="f.format_id" :value="f">
        {{ f.resolution }} ({{ formatSize(f.filesize) }})
      </option>
    </select>
    <button @click="download" :disabled="downloading">
      {{ downloading ? '下载中...' : '下载视频' }}
    </button>
    <div v-if="progress" class="progress-bar">
      <div class="progress-fill" :style="{ width: progress + '%' }"></div>
    </div>
  </div>
</template>
```

**依赖**：任务 2.1 ✅（需要 formats 数据）

---

## 阶段 6：样式打磨

### 任务 6.1：全局样式 + ChatGPT 风格

**文件**：
- 修改：`frontend/src/styles/main.css`

**设计规范**：
- 背景：白色 #FFFFFF / 浅灰 #F5F5F5
- 文字：黑色 #1A1A1A / 次级 #666666
- 主色：深灰 #333333 / 强调使用蓝色 #2563EB
- 圆角：12px 卡片
- 字体系统：系统默认 sans-serif
- 最大宽度：800px 居中布局
- 阴影：微妙阴影 `0 2px 8px rgba(0,0,0,0.08)`

---

## 阶段 7：集成测试与验证

### 任务 7.1：端到端测试

**测试场景**：

1. **YouTube 正常流程**：
   - 粘贴 YouTube 链接 → 展示元数据 → AI 分析 → 展示摘要 → 下载

2. **B站 正常流程**：
   - 粘贴 B站 链接 → 需要先配置 cookies 提示（首次）→ 展示元数据 → AI 分析 → 下载

3. **无字幕视频**：
   - 粘贴无字幕视频 → 展示元数据 → AI 分析失败 → 提示"无字幕可用" → 可下载

4. **不支持的链接**：
   - 粘贴抖音链接 → 提示"暂不支持此平台"

5. **错误恢复**：
   - 断网重连 → 显示提示 → 可重试

---

## 任务依赖总图

```
1.1 后端骨架 ──────────────────────────────┐
                                           ▼
1.2 前端骨架 ────┐                 2.1 元数据 API
                  │                      │
                  ▼                      ▼
            2.2 输入 + 展示 ◄──── 完成 ──┘
                                           │
                                   3.1 字幕提取
                                           │
                                   3.2 DeepSeek
                                           │
                                   3.3 SSE 推送
                                           │
                  ┌────────────────────────┘
                  ▼
            3.4 前端进度展示
                  │
            4.1 摘要 + 要点
                  │
            4.2 思维导图
                  │
            5.1 下载 API ────────── 5.2 下载面板
                  │                      │
                  └────── 6.1 样式 ──────┘
                              │
                        7.1 集成测试
```

## MVP 开发顺序建议

> 按依赖链分批，每批产出可测试的功能点

| 批次 | 任务 | 可测试点 |
|------|------|---------|
| **批 1** | 1.1 + 2.1 | `curl POST /api/parse` 返回视频信息 |
| **批 2** | 1.2 + 2.2 | 前端输入链接 → 看到视频封面 |
| **批 3** | 3.1 + 3.2 + 3.3 | `curl GET /api/analyze` SSE 推送分析进度 |
| **批 4** | 3.4 + 4.1 + 4.2 | 前端看到完整分析结果和导图 |
| **批 5** | 5.1 + 5.2 + 6.1 | 完整流程闭合：粘贴→分析→下载 |
| **批 6** | 7.1 | 全场景测试 |
