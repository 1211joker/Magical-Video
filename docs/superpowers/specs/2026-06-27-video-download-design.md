# 模块 4：视频下载 — 设计规格

> 日期：2026-06-27 | 状态：待审查

## 1. 概述

在 AI 分析完成后，用户可以选择清晰度并下载视频。采用后端代理流式转发方案：yt-dlp 输出到 stdout → 后端逐块读取 → StreamingResponse 转发 → 前端拼 Blob 触发浏览器保存。

**不改动现有功能**：解析、AI 分析、字幕提取、思维导图等模块不受影响。

## 2. 数据流

```
用户选择清晰度 → 点击下载
     ↓
POST /api/download  {url, format_id, cookies}
     ↓
ytdlp_service.download_video()
     ├─ 步骤1: yt-dlp --print filename → 获得输出文件名
     └─ 步骤2: yt-dlp -f <id> -o - <url> → stdout 流式输出
              ↓ 逐块读取 (1MB/chunk)
StreamingResponse
  - Content-Type: application/octet-stream
  - Content-Disposition: attachment; filename*=UTF-8''<安全文件名>
     ↓
前端 fetch → ReadableStream → 拼 Blob
     ↓
URL.createObjectURL(blob) → <a download> 点击 → 浏览器保存对话框
```

## 3. 后端改动

### 3.1 schemas.py — 新增 DownloadRequest

```python
class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"  # yt-dlp 格式选择器
    cookies: Optional[str] = None
```

### 3.2 ytdlp_service.py — 新增 download_video()

```
download_video(url, format_id, cookies) → AsyncGenerator[bytes]

逻辑:
1. 先跑 yt-dlp --print filename -f <format_id> --no-playlist <url>
   → 拿到文件名（如 "视频标题.f137.mp4"）
2. 再跑 yt-dlp -f <format_id> -o - --no-playlist <url>
   → stdout 输出视频数据
3. asyncio subprocess, 每次读 DOWNLOAD_CHUNK_SIZE (1MB)
   → yield 给 StreamingResponse
4. stderr 异常时抛 RuntimeError
5. finally 清理 cookies 临时文件
```

**关键细节**：
- `-o -` 表示输出到 stdout（不存磁盘）
- 文件名获取失败时，fallback 到 `"video.mp4"`
- 文件名安全处理：`re.sub(r'[<>:"/\\|?*]', '_', filename)`
- cookies 临时文件在 finally 中删除

### 3.3 routers/download.py — 新增 POST /api/download

```
POST /api/download
Body: {url, format_id, cookies}

流程:
1. 校验 format_id 非空
2. 调用 download_video() 获取流
3. 构建 Content-Disposition 头（含文件名）
4. 返回 StreamingResponse(stream, media_type="application/octet-stream")

错误处理:
- yt-dlp 进程异常 → 返回 {"error": "..."} 
- 超时（config.YTDLP_TIMEOUT） → asyncio.TimeoutError
```

### 3.4 config.py — 无需改动

已有 `MAX_FILE_SIZE`（2GB）、`DOWNLOAD_CHUNK_SIZE`（1MB）、`YTDLP_TIMEOUT`（60s）。

注意：下载不需要 `AI_ANALYSIS_TIMEOUT`，下载用 `YTDLP_TIMEOUT`（60s）。但实际上视频下载可能超过 60s，需要考虑：长视频下载时 yt-dlp 持续输出数据，每 60s 内有数据产出就不算超时。如果 60s 内完全没有数据产出（卡住），才算超时。

## 4. 前端改动

### 4.1 DownloadSection.vue — 新建组件

**位置**：在 AnalysisResult 组件下方展示。

**三个区域**：

1. **清晰度选择器**
   - 从 `videoInfo.formats` 拿数据
   - 每行：圆点选择 + 清晰度标签 + 文件大小（未知时显示"大小未知"）
   - 默认选中最高画质
   - 样式：与现有卡片风格一致（黑白灰基调）

2. **下载按钮**
   - 未下载时：实心按钮 "⬇️ 下载视频"
   - 下载中：灰色禁用 + spinner "⏳ 正在下载..."
   - 下载完成：绿色 "✅ 下载完成"（3 秒后恢复）
   - 下载失败：红色 "❌ 下载失败" + "🔄 重试"按钮

3. **状态消息**
   - 下载中显示 "正在下载，请稍候，浏览器将弹出保存对话框..."

**Props**：
- `formats: Array` — 清晰度列表
- `url: String` — 视频链接
- `cookies: String | null` — B站 cookies

### 4.2 api/index.js — 重写 downloadVideo()

```
downloadVideo(url, formatId, cookies, onProgress) → Promise<{success, message}>

逻辑:
1. fetch POST /api/download, body: {url, format_id, cookies}
2. 检查 response.ok
   - 非 200 → 解析 error JSON, throw Error
3. 从 Content-Disposition 头提取文件名
4. 读取 response.body (ReadableStream) → 拼成 Blob
5. URL.createObjectURL(blob) → 创建隐藏 <a> → 点击 → URL.revokeObjectURL()
6. 返回 {success: true}
```

**为什么不用 `window.open`**：需要传 cookies（可能很长）和 format_id，POST body 更合适。

### 4.3 App.vue — 集成 DownloadSection

在 `AnalysisResult` 组件下方插入：

```html
<DownloadSection
  v-if="videoInfo && videoInfo.formats.length > 0"
  :formats="videoInfo.formats"
  :url="urlInput"
  :cookies="cookies"
/>
```

**显隐条件**：视频解析成功且有可选格式时显示。不依赖 AI 分析结果。

## 5. 错误处理

| 场景 | 后端处理 | 前端表现 |
|------|---------|---------|
| yt-dlp 下载中途断开 | catch 异常，StreamingResponse 提前结束 | Blob 不完整，前端捕获后提示"下载中断" |
| 所选格式不可用 | yt-dlp 返回非 0 → RuntimeError | "所选清晰度不可用，请尝试其他选项" |
| cookies 过期（B站） | 同解析流程，412/403 检测 | "cookies 可能已过期，请重新获取" |
| 网络超时 | asyncio.TimeoutError | "下载超时，请检查网络后重试" |
| 文件过大（>2GB） | 流式转发无限制，但需注意内存 | 前端 Blob 在内存中，超大文件可能卡浏览器。暂不做限制，后续模块 5 优化 |

## 6. 边界情况

- **无可用格式**：`formats` 为空时，DownloadSection 不显示
- **文件大小未知**：显示"大小未知"而非空白
- **文件名含特殊字符**：`/` `\` `:` `*` `?` `"` `<` `>` `|` 替换为 `_`
- **中文文件名**：Content-Disposition 使用 `filename*=UTF-8''` 编码
- **重复下载**：下载中按钮禁用，防止重复点击
- **取消下载**：前端 AbortController，用户刷新页面即取消

## 7. 验证方案

1. YouTube 视频：选择不同清晰度各下载一次，确认文件可播放
2. B站 视频：带 cookies 下载，确认文件可播放
3. 异常场景：无效 format_id、过期 cookies、断网
4. 前端构建：`npm run build` 无报错
5. 文件名：中文标题下载后文件名正确显示
