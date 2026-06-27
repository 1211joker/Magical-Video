# 模块 4：视频下载 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现后端代理流式下载：用户选择清晰度 → POST /api/download → yt-dlp stdout 流式转发 → 前端 Blob 保存

**架构：** 后端 yt-dlp `-o -` 输出到 stdout → asyncio subprocess 逐块读取 → StreamingResponse 转发 → 前端 fetch → Blob → `<a download>` 触发浏览器保存对话框

**技术栈：** Python asyncio subprocess + FastAPI StreamingResponse + fetch ReadableStream

---

### 任务 1：新增 DownloadRequest 数据模型

**文件：**
- 修改：`backend/models/schemas.py`（末尾追加）

- [ ] **步骤 1：在 schemas.py 末尾添加 DownloadRequest**

```python
class DownloadRequest(BaseModel):
    """下载视频请求"""
    url: str
    format_id: str = "best"     # yt-dlp 格式选择器，如 "137+140"
    cookies: Optional[str] = None
```

- [ ] **步骤 2：验证导入**

```bash
cd backend && python3 -c "from models.schemas import DownloadRequest; print('OK')"
```

预期输出：`OK`

- [ ] **步骤 3：Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat: add DownloadRequest model for video download"
```

---

### 任务 2：新增 download_video() 流式下载函数

**文件：**
- 修改：`backend/services/ytdlp_service.py`（末尾追加）

- [ ] **步骤 1：在 ytdlp_service.py 顶部 import 区域添加 re 导入**

文件已有 `import re`（第 6 行），确认存在即可。如果没有则添加。

- [ ] **步骤 2：在 ytdlp_service.py 末尾添加两个函数**

在文件末尾追加以下代码（在 `_extract_formats` 函数之后）：

```python
def _sanitize_filename(name: str) -> str:
    """把文件名中的非法字符替换为下划线"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip() or "video"


async def _get_download_filename(
    url: str, format_id: str, cookies_file: Optional[str] = None
) -> str:
    """
    查询 yt-dlp 会输出什么文件名。
    跑一次 --print filename（只查询元数据，不下载），拿到文件名后返回。
    失败时返回 "video.mp4" 兜底。
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--print", "filename",
        "-f", format_id,
        "--no-playlist",
        "--no-check-certificates",
        url
    ]
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    if YTDLP_PROXY:
        cmd.extend(["--proxy", YTDLP_PROXY])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        if process.returncode == 0 and stdout:
            name = stdout.decode("utf-8", errors="replace").strip()
            if name:
                return _sanitize_filename(name)
    except Exception:
        pass

    return "video.mp4"


async def download_video(
    url: str,
    format_id: str = "best",
    cookies: Optional[str] = None
):
    """
    流式下载视频。

    流程：
    1. 先跑 yt-dlp --print filename 拿到输出文件名
    2. 再跑 yt-dlp -f <id> -o - 让视频流输出到 stdout
    3. 返回 (filename, stream_generator) 元组

    stream_generator 是 async generator，逐块 yield bytes。
    每块大小为 DOWNLOAD_CHUNK_SIZE (1MB)。
    """
    from config import DOWNLOAD_CHUNK_SIZE

    # 处理 cookies 临时文件
    cookies_file = None
    if cookies:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(cookies)
        tmp.close()
        cookies_file = tmp.name

    # 步骤 1：获取文件名
    filename = await _get_download_filename(url, format_id, cookies_file)

    # 步骤 2：定义流式下载生成器
    async def stream():
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", format_id,
                "-o", "-",
                "--no-playlist",
                "--no-check-certificates",
                url
            ]
            if cookies_file:
                cmd.extend(["--cookies", cookies_file])
            if YTDLP_PROXY:
                cmd.extend(["--proxy", YTDLP_PROXY])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                while True:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(DOWNLOAD_CHUNK_SIZE),
                        timeout=YTDLP_TIMEOUT
                    )
                    if not chunk:
                        break
                    yield chunk

                await process.wait()
                if process.returncode != 0:
                    stderr_data = await process.stderr.read()
                    error_text = stderr_data.decode("utf-8", errors="replace")[:500]

                    # 识别 B站 cookies 过期
                    if "412" in error_text or "403" in error_text:
                        raise RuntimeError(
                            "cookies 可能已过期，请重新获取 B站 cookies 后重试"
                        )
                    raise RuntimeError(f"下载失败：{error_text}")

            except asyncio.TimeoutError:
                process.kill()
                raise RuntimeError("下载超时，请检查网络后重试")

            finally:
                if process.returncode is None:
                    process.kill()

        finally:
            # 清理 cookies 临时文件
            if cookies_file and os.path.exists(cookies_file):
                os.unlink(cookies_file)

    return filename, stream()
```

- [ ] **步骤 3：验证导入**

```bash
cd backend && python3 -c "from services.ytdlp_service import download_video, _sanitize_filename; print('OK')"
```

预期输出：`OK`

- [ ] **步骤 4：验证文件名安全化函数**

```bash
cd backend && python3 -c "
from services.ytdlp_service import _sanitize_filename
print(repr(_sanitize_filename('视频: 标题<test>?')))
print(repr(_sanitize_filename('a/b\\c:d*e\"f|g')))
"
```

预期：`'视频_ 标题_test_'` 和 `'a_b_c_d_e_f_g'`

- [ ] **步骤 5：Commit**

```bash
git add backend/services/ytdlp_service.py
git commit -m "feat: add download_video() streaming function with yt-dlp stdout pipe"
```

---

### 任务 3：实现 POST /api/download 接口

**文件：**
- 修改：`backend/routers/download.py`（完全重写）

- [ ] **步骤 1：重写 download.py**

```python
"""
下载相关 API 路由 — 流式代理下载
"""
import logging
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.schemas import DownloadRequest
from services.ytdlp_service import download_video

router = APIRouter(prefix="/api", tags=["download"])

logger = logging.getLogger(__name__)


@router.post("/download")
async def download_video_endpoint(request: DownloadRequest):
    """
    流式下载视频。

    接收视频链接和清晰度选择 → 后端通过 yt-dlp stdout 流式获取 →
    StreamingResponse 转发给浏览器。

    浏览器收到后会弹出"另存为"对话框。
    """
    logger.info(
        f"[下载] 开始: url={request.url[:80]}, format={request.format_id}"
    )

    try:
        filename, stream = await download_video(
            url=request.url,
            format_id=request.format_id,
            cookies=request.cookies
        )
    except RuntimeError as e:
        # 下载启动失败（如 yt-dlp 在获取文件名阶段报错）
        from fastapi.responses import JSONResponse
        logger.warning(f"[下载] 启动失败: {e}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(e)}
        )

    # 构建安全的 Content-Disposition 头
    # filename*=UTF-8'' 方式支持中文文件名
    encoded_filename = quote(filename, safe="")
    content_disposition = (
        f"attachment; filename=\"{filename}\"; "
        f"filename*=UTF-8''{encoded_filename}"
    )

    logger.info(f"[下载] 开始流式传输: {filename}")

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition,
            "X-Filename": encoded_filename,
        }
    )
```

- [ ] **步骤 2：验证路由注册正确**

```bash
cd backend && python3 -c "from routers.download import router; print('OK')"
```

预期输出：`OK`

- [ ] **步骤 3：验证整个后端导入链**

```bash
cd backend && python3 -c "from main import app; print('OK')"
```

预期输出：`OK`

- [ ] **步骤 4：Commit**

```bash
git add backend/routers/download.py
git commit -m "feat: implement POST /api/download streaming endpoint"
```

---

### 任务 4：重写前端 downloadVideo() API 函数

**文件：**
- 修改：`frontend/src/api/index.js`（替换 downloadVideo 函数）

- [ ] **步骤 1：替换 downloadVideo 函数**

找到文件末尾的 `downloadVideo` 函数（约第 99-104 行），完整替换为：

```javascript
/**
 * 下载视频 — POST 请求后端代理下载，接收 Blob 流后触发浏览器保存。
 *
 * 参数：
 *   url       - 视频链接
 *   formatId  - 清晰度 format_id（如 "137+140"）
 *   cookies   - B站 cookies（可选）
 *
 * 返回：
 *   { success: true, filename: string }
 *
 * 抛出：
 *   Error — 下载失败时，message 为错误描述
 */
export async function downloadVideo(url, formatId, cookies) {
  const response = await fetch(`${API_BASE}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, format_id: formatId, cookies })
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: '下载失败，请重试' }))
    throw new Error(err.detail || '下载失败，请重试')
  }

  // 从响应头提取文件名
  const disposition = response.headers.get('Content-Disposition') || ''
  const utf8Match = disposition.match(/filename\*=UTF-8''(.+)/)
  const normalMatch = disposition.match(/filename="?(.+?)"?\s*(;|$)/)
  let filename = 'video.mp4'
  if (utf8Match) {
    filename = decodeURIComponent(utf8Match[1])
  } else if (normalMatch) {
    filename = normalMatch[1]
  }

  // 读取整个响应体为 Blob
  const blob = await response.blob()

  // 触发浏览器"另存为"
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(blobUrl)

  return { success: true, filename }
}
```

- [ ] **步骤 2：验证文件语法**

```bash
cd frontend && node -e "require('fs').readFileSync('src/api/index.js','utf8').split('\n').forEach((l,i) => { try { Function(l) } catch(e) { if(!l.trim()||l.startsWith('import')||l.startsWith('export')||l.startsWith('//')||l.startsWith('/*')) return; console.log(i+1, e.message) } })" 2>/dev/null; echo "done"
```

（此命令跳过 import/export 行，检查其余代码是否有明显语法错误）

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/api/index.js
git commit -m "feat: rewrite downloadVideo() to use POST streaming + Blob save"
```

---

### 任务 5：创建 DownloadSection.vue 组件

**文件：**
- 创建：`frontend/src/components/DownloadSection.vue`

- [ ] **步骤 1：创建组件文件**

```vue
<template>
  <div class="download-section card" v-if="formats && formats.length > 0">
    <h3 class="section-title">⬇️ 下载视频</h3>

    <!-- 清晰度选择器 -->
    <div class="format-selector">
      <label
        v-for="fmt in formats"
        :key="fmt.format_id"
        class="format-option"
        :class="{ selected: selectedFormat === fmt.format_id }"
      >
        <input
          type="radio"
          :value="fmt.format_id"
          v-model="selectedFormat"
          class="format-radio"
        />
        <span class="format-resolution">{{ fmt.resolution }}</span>
        <span class="format-size" v-if="fmt.filesize">
          · 约 {{ formatSize(fmt.filesize) }}
        </span>
        <span class="format-size" v-else>· 大小未知</span>
        <span class="format-ext">· {{ fmt.ext }}</span>
      </label>
    </div>

    <!-- 下载按钮 -->
    <button
      class="btn-download"
      :class="btnClass"
      :disabled="downloading"
      @click="handleDownload"
    >
      <span v-if="downloading" class="spinner"></span>
      {{ btnText }}
    </button>

    <!-- 状态消息 -->
    <p v-if="statusMessage" class="status-msg" :class="statusClass">
      {{ statusMessage }}
    </p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { downloadVideo } from '../api/index.js'

const props = defineProps({
  formats: { type: Array, required: true },
  url: { type: String, required: true },
  cookies: { type: String, default: null }
})

// 默认选中第一个（最高画质，因为 formats 已按分辨率降序排列）
const selectedFormat = ref(props.formats[0]?.format_id || 'best')

// 状态管理
const downloading = ref(false)
const statusMessage = ref('')
const statusType = ref('')  // 'success' | 'error'

const btnClass = computed(() => ({
  'is-downloading': downloading.value,
  'is-success': statusType.value === 'success',
  'is-error': statusType.value === 'error'
}))

const btnText = computed(() => {
  if (downloading.value) return '⏳ 正在下载...'
  if (statusType.value === 'success') return '✅ 下载完成'
  return '⬇️ 下载视频'
})

const statusClass = computed(() => ({
  'msg-success': statusType.value === 'success',
  'msg-error': statusType.value === 'error'
}))

function formatSize(bytes) {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

async function handleDownload() {
  if (downloading.value) return

  downloading.value = true
  statusType.value = ''
  statusMessage.value = '正在下载，请稍候，浏览器将弹出保存对话框...'

  try {
    await downloadVideo(props.url, selectedFormat.value, props.cookies)
    statusType.value = 'success'
    statusMessage.value = '下载完成！文件已保存到你的电脑。'
    // 3 秒后恢复按钮状态
    setTimeout(() => {
      statusType.value = ''
      statusMessage.value = ''
    }, 3000)
  } catch (err) {
    statusType.value = 'error'
    statusMessage.value = err.message || '下载失败，请重试'
  } finally {
    downloading.value = false
  }
}

// 当 formats 变化时（重新解析），重置为第一个
import { watch } from 'vue'
watch(() => props.formats, (newFormats) => {
  if (newFormats && newFormats.length > 0) {
    selectedFormat.value = newFormats[0].format_id
    statusType.value = ''
    statusMessage.value = ''
  }
})
</script>

<style scoped>
.download-section {
  margin-top: 20px;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
}

/* 清晰度选择器 */
.format-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 18px;
}

.format-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.9rem;
}

.format-option:hover {
  border-color: var(--text-muted);
  background: #f9fafb;
}

.format-option.selected {
  border-color: var(--accent);
  background: #f0f0ff;
}

.format-radio {
  width: auto;
  accent-color: var(--accent);
  cursor: pointer;
}

.format-resolution {
  font-weight: 700;
  color: var(--text-primary);
  min-width: 50px;
}

.format-size {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.format-ext {
  color: var(--text-muted);
  font-size: 0.82rem;
  text-transform: uppercase;
}

/* 下载按钮 */
.btn-download {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 28px;
  font-size: 0.95rem;
  font-weight: 700;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25);
  transition: all 0.2s;
}

.btn-download:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.35);
  transform: translateY(-1px);
}

.btn-download.is-downloading {
  background: var(--text-muted);
  box-shadow: none;
  cursor: not-allowed;
  transform: none;
}

.btn-download.is-success {
  background: #16a34a;
  box-shadow: 0 2px 8px rgba(22, 163, 74, 0.25);
}

.btn-download.is-error {
  background: #dc2626;
  box-shadow: 0 2px 8px rgba(220, 38, 38, 0.25);
}

/* spinner */
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 状态消息 */
.status-msg {
  margin-top: 12px;
  font-size: 0.88rem;
  color: var(--text-secondary);
}

.msg-success {
  color: #16a34a;
  font-weight: 600;
}

.msg-error {
  color: #dc2626;
  font-weight: 600;
}
</style>
```

- [ ] **步骤 2：验证前端构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

预期：`✓ built in xxxms`，无错误

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/components/DownloadSection.vue
git commit -m "feat: add DownloadSection component with format selector and download button"
```

---

### 任务 6：集成 DownloadSection 到 App.vue

**文件：**
- 修改：`frontend/src/App.vue`

- [ ] **步骤 1：在 App.vue 的 `<script setup>` 中导入 DownloadSection**

在现有 import 区域末尾添加一行：

```javascript
import DownloadSection from './components/DownloadSection.vue'
```

（插入位置：`import AnalysisResult from './components/AnalysisResult.vue'` 之后）

- [ ] **步骤 2：在模板中添加 DownloadSection**

找到 `<!-- 分析结果 -->` 这行（约第 82 行），在 `</AnalysisResult>` 之后添加：

```html
        <!-- 视频下载 -->
        <DownloadSection
          v-if="videoInfo && videoInfo.formats && videoInfo.formats.length > 0"
          :formats="videoInfo.formats"
          :url="urlInput"
          :cookies="cookies"
        />
```

（插入位置：`<AnalysisResult v-if="analysisResult" :result="analysisResult" />` 闭合标签之后）

- [ ] **步骤 3：验证前端构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

预期：`✓ built in xxxms`，无错误

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: integrate DownloadSection into App.vue"
```

---

### 任务 7：端到端验证

- [ ] **步骤 1：重启后端服务**

```bash
lsof -ti :8000 | xargs kill -9 2>/dev/null; sleep 1
cd backend && python3 -m uvicorn main:app --reload &
sleep 2
curl -s http://127.0.0.1:8000/ | python3 -c "import sys,json; print(json.load(sys.stdin)['message'])"
```

预期输出：`AI 视频下载总结器 API`

- [ ] **步骤 2：Python 导入全链路检查**

```bash
cd backend && python3 -c "
from models.schemas import DownloadRequest
from services.ytdlp_service import download_video, _sanitize_filename
from routers.download import router
from main import app
print('All imports OK')
"
```

预期输出：`All imports OK`

- [ ] **步骤 3：前端构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

预期：构建成功，无错误

- [ ] **步骤 4：手动测试清单**

在 `http://localhost:5173` 完成以下测试：

| 测试场景 | 操作 | 预期结果 |
|---------|------|---------|
| 下载区域显示 | 解析 YouTube 视频 | 视频信息下方出现"⬇️ 下载视频"区域 + 清晰度列表 |
| 清晰度选择 | 点击不同清晰度 | 选中态切换，高亮当前选择 |
| YouTube 下载 | 选择清晰度 → 点下载 | 浏览器弹出保存对话框，文件可播放 |
| B站 下载 | 配置 cookies → 解析 → 下载 | 同上 |
| 下载中禁用 | 点下载后 | 按钮变灰显示"⏳ 正在下载..."，不可重复点击 |
| 下载完成 | 下载结束 | 按钮变绿显示"✅ 下载完成"，3 秒后恢复 |
| 无格式不显示 | 解析一个不返回格式的视频 | DownloadSection 不显示 |
