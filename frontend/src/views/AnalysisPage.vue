<template>
  <div class="analysis-page">
    <header class="page-header">
      <h1 class="page-title">AI 视频解析</h1>
      <p class="page-desc">粘贴视频链接，AI 自动分析字幕内容，生成结构化摘要</p>
    </header>

    <!-- B站 Cookies 设置（可折叠） -->
    <CookieGuide ref="cookieGuideRef" @update:cookies="onCookiesUpdate" />

    <!-- 链接输入区 -->
    <div class="input-section card">
      <label for="url-input" class="input-label">视频链接</label>
      <div class="input-row">
        <input
          id="url-input"
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

    <!-- 视频加载骨架屏 -->
    <div v-if="parsing" class="skeleton-card card">
      <div class="skeleton skeleton-thumb"></div>
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-text"></div>
      <div class="skeleton skeleton-text"></div>
    </div>

    <!-- 解析错误 -->
    <Transition name="fade">
      <div v-if="errorMsg" class="error-banner" role="alert">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="error-text">{{ errorMsg }}</span>
        <button class="error-close" aria-label="关闭错误提示" @click="errorMsg = ''">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </Transition>

    <!-- 视频信息 + 分析 + 下载 -->
    <Transition name="slide-fade">
      <div v-if="videoInfo && videoInfo.platform !== 'unsupported'" class="result-area">
        <VideoInfo :info="videoInfo" />

        <!-- AI 分析按钮 -->
        <div class="analyze-area" v-if="!analysisResult && !analyzing && progressSteps.length === 0">
          <button class="btn-analyze" @click="handleAnalyze">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/>
            </svg>
            AI 分析视频内容
          </button>
        </div>

        <!-- 分析错误 -->
        <Transition name="fade">
          <div v-if="analysisError" class="error-banner" role="alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="error-text">{{ analysisError }}</span>
            <button class="error-close" aria-label="关闭错误提示" @click="analysisError = ''">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </Transition>

        <!-- 分析进度 -->
        <Transition name="slide-fade">
          <div v-if="progressSteps.length > 0" class="progress-area card">
            <div class="progress-header">
              <span>{{ progressStatusText }}</span>
              <button v-if="showRetryButton" class="btn-retry" @click="handleAnalyze">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                重新分析
              </button>
              <button v-if="!analyzing" class="btn-close-progress" aria-label="关闭进度面板" @click="dismissProgress">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div class="progress-steps">
              <div
                v-for="s in progressSteps"
                :key="s.step"
                class="progress-step"
                :class="'step-' + s.status"
              >
                <span class="step-dot" :aria-label="s.status">
                  <template v-if="s.status === 'processing'">
                    <svg class="spinner-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/></svg>
                  </template>
                  <template v-else-if="s.status === 'done'">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  </template>
                  <template v-else-if="s.status === 'failed'">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  </template>
                  <template v-else>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>
                  </template>
                </span>
                <span class="step-label">{{ progressLabels[s.step] || s.step }}</span>
                <span class="step-message" v-if="s.message">— {{ s.message }}</span>
              </div>
            </div>
          </div>
        </Transition>

        <!-- 分析结果 -->
        <Transition name="slide-fade">
          <AnalysisResult v-if="analysisResult" :result="analysisResult" />
        </Transition>

        <!-- 视频下载 -->
        <Transition name="slide-fade">
          <DownloadSection
            v-if="videoInfo && videoInfo.formats && videoInfo.formats.length > 0"
            :formats="videoInfo.formats"
            :url="urlInput"
            :cookies="cookies"
          />
        </Transition>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { parseVideo, startAnalysis } from '../api/index.js'
import VideoInfo from '../components/VideoInfo.vue'
import CookieGuide from '../components/CookieGuide.vue'
import AnalysisResult from '../components/AnalysisResult.vue'
import DownloadSection from '../components/DownloadSection.vue'

const urlInput = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const errorMsg = ref('')
const cookies = ref(null)
const cookieGuideRef = ref(null)

// AI 分析状态
const analyzing = ref(false)
const analysisResult = ref(null)
const analysisError = ref('')
const progressSteps = reactive([])
let abortAnalysis = null

// 状态持久化 — 页面切换后恢复已解析的视频和 AI 分析结果
const STATE_KEY = 'analysisPageState'

// 页面挂载时恢复之前的分析状态
onMounted(() => {
  try {
    const saved = localStorage.getItem(STATE_KEY)
    if (saved) {
      const state = JSON.parse(saved)
      if (state.urlInput) urlInput.value = state.urlInput
      if (state.videoInfo) videoInfo.value = state.videoInfo
      if (state.analysisResult) analysisResult.value = state.analysisResult
      if (state.cookies) cookies.value = state.cookies
    }
  } catch (e) { /* 数据损坏，忽略 */ }
})

// 自动保存状态变化
watch(
  [urlInput, videoInfo, analysisResult, () => cookies.value],
  () => {
    try {
      localStorage.setItem(STATE_KEY, JSON.stringify({
        urlInput: urlInput.value,
        videoInfo: videoInfo.value,
        analysisResult: analysisResult.value,
        cookies: cookies.value,
      }))
    } catch (e) { /* localStorage 可能满了 */ }
  },
  { deep: true }
)

function clearSavedState() {
  try { localStorage.removeItem(STATE_KEY) } catch (e) { /* ignore */ }
}

const progressLabels = {
  parse: '获取视频信息',
  subtitles: '提取字幕',
  analyze: 'AI 分析',
  error: '出错',
}

const progressStatusText = computed(() => {
  if (analyzing.value) return 'AI 分析进行中...'
  const hasFailed = progressSteps.some(s => s.status === 'failed')
  const allDone = progressSteps.length > 0 && progressSteps.every(s => s.status === 'done')
  if (allDone) return 'AI 分析完成'
  if (hasFailed) return 'AI 分析未完成'
  return 'AI 分析未完成'
})

const showRetryButton = computed(() => {
  if (analyzing.value) return false
  const allDone = progressSteps.length > 0 && progressSteps.every(s => s.status === 'done')
  return !allDone
})

function onCookiesUpdate(cookiesText) {
  cookies.value = cookiesText
}

async function handleParse() {
  if (!urlInput.value.trim()) return

  parsing.value = true
  errorMsg.value = ''
  videoInfo.value = null
  analysisResult.value = null
  analysisError.value = ''
  progressSteps.length = 0

  try {
    const result = await parseVideo(urlInput.value, cookies.value)
    if (result.platform === 'unsupported') {
      errorMsg.value = result.description || '暂不支持此平台'
      videoInfo.value = null
    } else {
      videoInfo.value = result
    }
  } catch (err) {
    errorMsg.value = err.message || '解析失败，请检查链接'
    if (errorMsg.value.includes('cookies') || errorMsg.value.includes('B站')) {
      cookieGuideRef.value?.open()
    }
  } finally {
    parsing.value = false
  }
}

function handleAnalyze() {
  if (!videoInfo.value) return

  analyzing.value = true
  analysisError.value = ''
  analysisResult.value = null
  progressSteps.length = 0

  progressSteps.push(
    { step: 'parse', status: 'waiting' },
    { step: 'subtitles', status: 'waiting' },
    { step: 'analyze', status: 'waiting' }
  )

  abortAnalysis = startAnalysis(
    urlInput.value,
    cookies.value,
    (event) => {
      const idx = progressSteps.findIndex(s => s.step === event.step)
      if (idx >= 0) {
        progressSteps[idx].status = event.status
        progressSteps[idx].message = event.message
      } else if (event.step === 'error') {
        analysisError.value = event.message
        analyzing.value = false
        return
      }

      if (event.status === 'failed') {
        analyzing.value = false
        analysisError.value = event.message
        if (event.message.includes('cookies') || event.message.includes('B站')) {
          cookieGuideRef.value?.open()
        }
        return
      }

      if (event.status === 'done' && event.result) {
        analyzing.value = false
        analysisResult.value = event.result
        // 存入 localStorage 供 AI 问答页面使用
        try {
          localStorage.setItem('lastAnalysisResult', JSON.stringify({
            ...event.result,
            savedAt: Date.now(),
          }))
        } catch (e) {
          // localStorage 可能满了，忽略
        }
      }
    },
    (err) => {
      analyzing.value = false
      analysisError.value = err.message || '分析请求失败'
      const active = progressSteps.find(s => s.status === 'processing')
      if (active) {
        active.status = 'failed'
        active.message = analysisError.value
      }
    }
  )
}

function dismissProgress() {
  progressSteps.length = 0
  analysisError.value = ''
}

onBeforeUnmount(() => {
  if (abortAnalysis) {
    abortAnalysis.abort()
  }
})
</script>

<style scoped>
.analysis-page {
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

/* 骨架屏卡片 */
.skeleton-card {
  margin-top: 20px;
  padding: 20px 24px;
}

.skeleton-card .skeleton-thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.skeleton-card .skeleton-title {
  height: 22px;
  width: 70%;
  margin-bottom: 14px;
  border-radius: 6px;
}

.skeleton-card .skeleton-text {
  height: 13px;
  margin-bottom: 8px;
  border-radius: 4px;
}

.skeleton-card .skeleton-text:last-child {
  width: 50%;
}

/* 错误提示 */
.error-banner {
  margin-top: 16px;
  padding: 14px 18px;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.9rem;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.error-text {
  flex: 1;
  white-space: pre-line;
  line-height: 1.7;
}

.error-close {
  flex-shrink: 0;
  background: none;
  color: var(--text-secondary);
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  min-height: 32px;
}

.error-close:hover {
  background: var(--bg-hover);
}

.result-area {
  margin-top: 24px;
}

/* AI 分析按钮 */
.analyze-area {
  margin-top: 20px;
  text-align: center;
}

.btn-analyze {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 40px;
  font-size: 1.05rem;
  font-weight: 700;
  border: 2px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  min-height: 52px;
}

.btn-analyze:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.btn-analyze:active {
  transform: scale(0.98);
}

/* 分析进度 */
.progress-area {
  margin-top: 16px;
  padding: 20px 24px;
}

.progress-header {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text-primary);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 6px 16px;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 36px;
}

.btn-retry:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.btn-close-progress {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  min-width: 32px;
  min-height: 32px;
}

.btn-close-progress:hover {
  color: var(--text-primary);
  border-color: var(--border-strong);
}

.progress-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast);
}

.step-waiting {
  color: var(--text-muted);
}

.step-processing {
  color: var(--text-primary);
  background: var(--bg-hover);
  border: 1px solid var(--border);
}

.step-done {
  color: var(--text-primary);
  font-weight: 600;
}

.step-failed {
  color: var(--text-primary);
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
}

.step-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.step-label {
  font-weight: 600;
  min-width: 80px;
}

.step-message {
  color: var(--text-muted);
  font-size: 0.82rem;
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .analysis-page {
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
  .btn-analyze {
    width: 100%;
    padding: 14px 20px;
    font-size: 0.95rem;
  }
  .progress-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .btn-retry {
    margin-left: 0;
  }
}

@media (max-width: 374px) {
  .card { padding: 14px; }
  .progress-area { padding: 14px 16px; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
