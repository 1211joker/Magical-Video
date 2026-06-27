<template>
  <div class="app">
    <!-- 无障碍跳过链接 -->
    <a href="#main-content" class="skip-link">跳到主要内容</a>

    <!-- 主题切换按钮 -->
    <button
      class="theme-toggle"
      :title="isDark ? '切换到浅色模式' : '切换到暗色模式'"
      :aria-label="isDark ? '切换到浅色模式' : '切换到暗色模式'"
      @click="toggleTheme"
    >
      <svg v-if="isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
      <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>

    <header class="app-header">
      <h1 class="app-title">
        <svg class="title-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polygon points="23 7 16 12 23 17 23 7"/>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
        </svg>
        视频预览下载器
      </h1>
      <p class="app-subtitle">粘贴链接 → AI 摘要 → 判断是否值得下载</p>
    </header>

    <main id="main-content" class="app-main" tabindex="-1">
      <!-- B站 Cookies 设置（可折叠） -->
      <CookieGuide ref="cookieGuideRef" @update:cookies="onCookiesUpdate" />

      <!-- 链接输入区 -->
      <div class="input-section card">
        <label for="url-input" class="sr-only">视频链接</label>
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
          {{ parsing ? '解析中...' : '开始解析' }}
        </button>
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
          <svg class="error-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span class="error-text">{{ errorMsg }}</span>
          <button class="error-close" aria-label="关闭错误提示" @click="errorMsg = ''">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </Transition>

      <!-- 分析错误 -->
      <Transition name="fade">
        <div v-if="analysisError" class="error-banner" role="alert">
          <svg class="error-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span class="error-text">{{ analysisError }}</span>
          <button class="error-close" aria-label="关闭错误提示" @click="analysisError = ''">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </Transition>

      <!-- 视频信息展示 -->
      <Transition name="slide-fade">
        <div v-if="videoInfo && videoInfo.platform !== 'unsupported'" class="result-area">
          <VideoInfo :info="videoInfo" />

          <!-- AI 分析按钮 -->
          <div class="analyze-area" v-if="!analysisResult && !analyzing && progressSteps.length === 0">
            <button
              class="btn-analyze"
              @click="handleAnalyze"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/>
              </svg>
              AI 分析视频内容
            </button>
          </div>

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
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { parseVideo, startAnalysis } from './api/index.js'
import VideoInfo from './components/VideoInfo.vue'
import CookieGuide from './components/CookieGuide.vue'
import AnalysisResult from './components/AnalysisResult.vue'
import DownloadSection from './components/DownloadSection.vue'

const urlInput = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const errorMsg = ref('')
const cookies = ref(null)
const cookieGuideRef = ref(null)

// === 主题切换 ===
const THEME_KEY = 'app-theme-preference'
const isDark = ref(false)

function getPreferredTheme() {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function applyTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
    isDark.value = true
  } else {
    document.documentElement.setAttribute('data-theme', 'light')
    isDark.value = false
  }
}

function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  localStorage.setItem(THEME_KEY, next)
  applyTheme(next)
}

// 初始化主题
applyTheme(getPreferredTheme())

// 监听系统主题变化（仅在没有手动设置时生效）
const mqDark = window.matchMedia('(prefers-color-scheme: dark)')
function onSystemThemeChange() {
  if (!localStorage.getItem(THEME_KEY)) {
    applyTheme(mqDark.matches ? 'dark' : 'light')
  }
}
mqDark.addEventListener('change', onSystemThemeChange)

// AI 分析状态
const analyzing = ref(false)
const analysisResult = ref(null)
const analysisError = ref('')
const progressSteps = reactive([])
let abortAnalysis = null

const progressLabels = {
  parse: '获取视频信息',
  subtitles: '提取字幕',
  analyze: 'AI 分析',
  error: '出错',
}

// 根据进度步骤状态计算头部标题
const progressStatusText = computed(() => {
  if (analyzing.value) return 'AI 分析进行中...'
  const hasFailed = progressSteps.some(s => s.status === 'failed')
  const allDone = progressSteps.length > 0 && progressSteps.every(s => s.status === 'done')
  if (allDone) return '✅ AI 分析完成'
  if (hasFailed) return 'AI 分析未完成'
  return 'AI 分析未完成'
})

// 只在分析失败时显示重试按钮（全部完成时不需要）
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
  // 重置分析状态
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
    // B站 cookies 相关错误 → 自动展开设置面板
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

  // 初始化进度步骤
  progressSteps.push(
    { step: 'parse', status: 'waiting' },
    { step: 'subtitles', status: 'waiting' },
    { step: 'analyze', status: 'waiting' }
  )

  abortAnalysis = startAnalysis(
    urlInput.value,
    cookies.value,
    (event) => {
      // 收到 SSE 事件时更新进度
      const idx = progressSteps.findIndex(s => s.step === event.step)
      if (idx >= 0) {
        progressSteps[idx].status = event.status
        progressSteps[idx].message = event.message
      } else if (event.step === 'error') {
        // 全局错误
        analysisError.value = event.message
        analyzing.value = false
        return
      }

      // 某个步骤失败 → 停止
      if (event.status === 'failed') {
        analyzing.value = false
        analysisError.value = event.message
        // B站 cookies 相关错误 → 自动展开设置面板
        if (event.message.includes('cookies') || event.message.includes('B站')) {
          cookieGuideRef.value?.open()
        }
        return
      }

      // AI 分析完成 → 展示结果
      if (event.status === 'done' && event.result) {
        analyzing.value = false
        analysisResult.value = event.result
      }
    },
    (err) => {
      // 网络错误
      analyzing.value = false
      analysisError.value = err.message || '分析请求失败'
      // 标记当前进行中的步骤为失败
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

// 取消分析（组件卸载时）
onBeforeUnmount(() => {
  if (abortAnalysis) {
    abortAnalysis.abort()
  }
})
</script>

<style scoped>
.app-header {
  text-align: center;
  margin-bottom: 40px;
}
.app-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.title-icon {
  color: var(--accent);
  flex-shrink: 0;
}
.app-subtitle {
  color: var(--text-secondary);
  font-size: 1.05rem;
}

/* 无障碍隐藏文本 */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* 输入区 */
.input-section {
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
  color: var(--danger);
  font-size: 0.9rem;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.error-icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.error-text {
  flex: 1;
  white-space: pre-line;
  line-height: 1.7;
}
.error-close {
  flex-shrink: 0;
  background: none;
  color: var(--danger);
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  min-height: 32px;
}
.error-close:hover {
  background: var(--danger-border);
}

.result-area {
  margin-top: 24px;
}

/* AI 分析按钮 */
.analyze-area {
  margin-top: 16px;
  text-align: center;
}

.btn-analyze {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 36px;
  font-size: 1rem;
  font-weight: 600;
  border: 2px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  min-height: 48px;
}

.btn-analyze:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
  box-shadow: 0 2px 8px var(--accent-glow);
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
  color: var(--accent);
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
  color: var(--danger);
  border-color: var(--danger-border);
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
  background: var(--accent-light);
  border: 1px solid var(--accent);
  animation: pulse-bg 2s ease-in-out infinite;
}

.step-done {
  color: var(--success);
}

.step-failed {
  color: var(--danger);
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

@keyframes pulse-bg {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* ======== 响应式 ======== */

@media (max-width: 639px) {
  .app-header {
    margin-bottom: 28px;
  }
  .app-title {
    font-size: 1.4rem;
  }
  .app-subtitle {
    font-size: 0.9rem;
  }
  .input-section {
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
  .app-title { font-size: 1.2rem; }
  .title-icon { width: 22px; height: 22px; }
  .card { padding: 14px; }
  .progress-area { padding: 14px 16px; }
}
</style>
