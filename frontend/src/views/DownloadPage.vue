<template>
  <div class="download-page">
    <header class="page-header">
      <h1 class="page-title">视频下载</h1>
      <p class="page-desc">快速解析并下载视频，选择你需要的清晰度</p>
    </header>

    <!-- 输入区 -->
    <div class="input-section card">
      <label for="dl-url-input" class="input-label">视频链接</label>
      <div class="input-row">
        <input
          id="dl-url-input"
          v-model="urlInput"
          type="text"
          placeholder="粘贴 YouTube 或 B站 视频链接..."
          class="url-input"
          @keyup.enter="handleParse"
        />
        <button
          class="btn-primary parse-btn"
          :disabled="!urlInput.trim() || parsing"
          @click="handleParse"
        >
          <svg v-if="parsing" class="spinner-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
            <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/>
          </svg>
          {{ parsing ? '解析中...' : '解析视频' }}
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="parsing" class="loading-card card">
      <div class="skeleton skeleton-thumb"></div>
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-text"></div>
    </div>

    <!-- 错误 -->
    <Transition name="fade">
      <div v-if="errorMsg" class="error-banner" role="alert">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>
    </Transition>

    <!-- 视频信息 & 下载 -->
    <Transition name="slide-fade">
      <div v-if="videoInfo && videoInfo.platform !== 'unsupported'" class="result-area">
        <!-- 视频卡片（精简版） -->
        <div class="video-card card">
          <div class="video-hero">
            <img
              v-if="videoInfo.thumbnail"
              :src="'/api/thumbnail?url=' + encodeURIComponent(videoInfo.thumbnail)"
              :alt="videoInfo.title"
              class="video-thumbnail"
              referrerpolicy="no-referrer"
            />
            <div v-else class="video-thumbnail placeholder">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3">
                <polygon points="23 7 16 12 23 17 23 7"/>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
              </svg>
            </div>
          </div>
          <div class="video-body">
            <h2 class="video-title">{{ videoInfo.title }}</h2>
            <span v-if="videoInfo.duration" class="video-duration">
              {{ formatDuration(videoInfo.duration) }}
            </span>
          </div>
        </div>

        <!-- 交互式清晰度选择器 -->
        <div class="format-section card">
          <h3 class="section-title">选择清晰度</h3>
          <p class="section-hint">点击选择，高亮项为当前选中</p>

          <div class="format-grid">
            <button
              v-for="fmt in videoInfo.formats"
              :key="fmt.format_id"
              class="format-card"
              :class="{ selected: selectedFormat === fmt.format_id }"
              @click="selectedFormat = fmt.format_id"
              :aria-pressed="selectedFormat === fmt.format_id"
            >
              <span class="format-res">{{ fmt.resolution }}</span>
              <span class="format-meta">
                {{ fmt.ext?.toUpperCase() || '' }}
                <template v-if="fmt.filesize"> · {{ formatSize(fmt.filesize) }}</template>
              </span>
              <span v-if="selectedFormat === fmt.format_id" class="format-check" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </span>
            </button>
          </div>

          <!-- 下载按钮 -->
          <button
            class="btn-download"
            :class="{ downloading }"
            :disabled="downloading || !selectedFormat"
            @click="handleDownload"
          >
            <template v-if="downloading">
              <svg class="spinner-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/></svg>
              正在下载...
            </template>
            <template v-else-if="statusType === 'success'">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              下载完成
            </template>
            <template v-else>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              下载视频
            </template>
          </button>

          <!-- 状态消息 -->
          <Transition name="fade">
            <p v-if="statusMessage" class="status-msg" :class="statusType ? 'msg-' + statusType : ''">
              {{ statusMessage }}
            </p>
          </Transition>
        </div>
      </div>
    </Transition>

    <!-- 空状态：未输入时展示小贴士 -->
    <div v-if="!videoInfo && !parsing && !errorMsg" class="empty-hint-card">
      <svg class="empty-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" opacity="0.2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <p>在输入框中粘贴视频链接，点击"解析视频"开始</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { parseVideo, downloadVideo } from '../api/index.js'

const urlInput = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const errorMsg = ref('')

// 下载状态
const selectedFormat = ref('')
const downloading = ref(false)
const statusMessage = ref('')
const statusType = ref('')

async function handleParse() {
  if (!urlInput.value.trim()) return

  parsing.value = true
  errorMsg.value = ''
  videoInfo.value = null
  statusMessage.value = ''
  statusType.value = ''

  try {
    const result = await parseVideo(urlInput.value, null)
    if (result.platform === 'unsupported') {
      errorMsg.value = result.description || '暂不支持此平台'
    } else {
      videoInfo.value = result
      selectedFormat.value = result.formats?.[0]?.format_id || ''
    }
  } catch (err) {
    errorMsg.value = err.message || '解析失败，请检查链接'
  } finally {
    parsing.value = false
  }
}

async function handleDownload() {
  if (downloading.value || !selectedFormat.value) return

  downloading.value = true
  statusType.value = ''
  statusMessage.value = '正在下载，浏览器将弹出保存对话框...'

  try {
    await downloadVideo(urlInput.value, selectedFormat.value, null)
    statusType.value = 'success'
    statusMessage.value = '下载完成！文件已保存。'
    setTimeout(() => {
      statusType.value = ''
      statusMessage.value = ''
    }, 4000)
  } catch (err) {
    statusType.value = 'error'
    statusMessage.value = err.message || '下载失败，请重试'
  } finally {
    downloading.value = false
  }
}

function formatSize(bytes) {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.download-page {
  padding-top: 32px;
}

.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.page-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
}

/* 输入区 */
.input-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-label {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-secondary);
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.url-input {
  flex: 1;
  font-size: 1.05rem;
  padding: 14px 18px;
  min-height: 48px;
}

.parse-btn {
  white-space: nowrap;
  padding: 14px 32px;
  min-height: 48px;
}

.spinner-svg {
  animation: spin 0.6s linear infinite;
}

/* 加载 */
.loading-card {
  margin-top: 20px;
  padding: 20px 24px;
}

.loading-card .skeleton-thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.loading-card .skeleton-title {
  height: 22px;
  width: 70%;
  margin-bottom: 14px;
  border-radius: 6px;
}

.loading-card .skeleton-text {
  height: 13px;
  width: 50%;
  border-radius: 4px;
}

/* 错误 */
.error-banner {
  margin-top: 16px;
  padding: 14px 18px;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.result-area {
  margin-top: 24px;
}

/* 视频卡片（精简） */
.video-card {
  overflow: hidden;
  padding: 0;
}

.video-hero {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--bg-skeleton);
  overflow: hidden;
}

.video-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.video-thumbnail.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
}

.video-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  gap: 12px;
}

.video-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.video-duration {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  padding: 3px 10px;
  background: var(--bg-hover);
  border-radius: 4px;
}

/* 清晰度选择 */
.format-section {
  margin-top: 16px;
}

.section-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.section-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 14px;
}

.format-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 20px;
}

.format-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 12px;
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-family: inherit;
}

.format-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.format-card.selected {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.format-res {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.format-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.format-check {
  position: absolute;
  top: 6px;
  right: 6px;
  color: var(--accent);
}

/* 下载按钮 */
.btn-download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 16px 32px;
  font-size: 1.05rem;
  font-weight: 700;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--bg-primary);
  box-shadow: 0 2px 12px var(--accent-glow);
  transition: all var(--duration-normal) var(--ease-out);
  min-height: 52px;
}

.btn-download:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 4px 20px var(--accent-glow);
  transform: translateY(-2px);
}

.btn-download:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
  transition-duration: 50ms;
}

.btn-download.downloading {
  background: var(--bg-hover);
  color: var(--text-muted);
  box-shadow: none;
}

/* 状态消息 */
.status-msg {
  margin-top: 14px;
  text-align: center;
  font-size: 0.9rem;
  font-weight: 600;
}

.msg-success { color: var(--text-primary); }
.msg-error { color: var(--text-primary); }

/* 空状态 */
.empty-hint-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.95rem;
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .download-page {
    padding-top: 24px;
  }
  .page-title {
    font-size: 1.4rem;
  }
  .page-desc {
    font-size: 0.88rem;
  }
  .page-header {
    margin-bottom: 24px;
  }
  .input-row {
    flex-direction: column;
    gap: 10px;
  }
  .parse-btn {
    width: 100%;
    padding: 14px 24px;
  }
  .url-input {
    font-size: 1rem;
    padding: 12px 14px;
  }
  .format-grid {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
