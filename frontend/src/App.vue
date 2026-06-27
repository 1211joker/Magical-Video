<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">📹 视频预览下载器</h1>
      <p class="app-subtitle">粘贴链接 → AI 摘要 → 判断是否值得下载</p>
    </header>

    <main class="app-main">
      <!-- B站 Cookies 设置（可折叠） -->
      <CookieGuide @update:cookies="onCookiesUpdate" />

      <!-- 链接输入区 -->
      <div class="input-section card">
        <input
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
          {{ parsing ? '解析中...' : '开始解析' }}
        </button>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-banner fade-enter">
        <span class="error-text">{{ errorMsg }}</span>
        <button class="error-close" @click="errorMsg = ''">✕</button>
      </div>

      <!-- 视频信息展示 -->
      <div v-if="videoInfo && videoInfo.platform !== 'unsupported'" class="result-area fade-enter">
        <VideoInfo :info="videoInfo" />

        <!-- AI 分析按钮 / 进度 / 结果 -->
        <div class="analyze-area" v-if="!analysisResult && !analyzing">
          <button
            class="btn-analyze"
            @click="handleAnalyze"
          >
            🤖 AI 分析视频内容
          </button>
        </div>

        <!-- 分析进度 -->
        <div v-if="analyzing" class="progress-area card fade-enter">
          <div class="progress-header">AI 分析进行中...</div>
          <div class="progress-steps">
            <div
              v-for="s in progressSteps"
              :key="s.step"
              class="progress-step"
              :class="'step-' + s.status"
            >
              <span class="step-dot">
                <template v-if="s.status === 'processing'">⏳</template>
                <template v-else-if="s.status === 'done'">✅</template>
                <template v-else-if="s.status === 'failed'">❌</template>
                <template v-else>○</template>
              </span>
              <span class="step-label">{{ progressLabels[s.step] || s.step }}</span>
              <span class="step-message" v-if="s.message">— {{ s.message }}</span>
            </div>
          </div>
        </div>

        <!-- 分析结果 -->
        <AnalysisResult v-if="analysisResult" :result="analysisResult" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { parseVideo, startAnalysis } from './api/index.js'
import VideoInfo from './components/VideoInfo.vue'
import CookieGuide from './components/CookieGuide.vue'
import AnalysisResult from './components/AnalysisResult.vue'

const urlInput = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const errorMsg = ref('')
const cookies = ref(null)

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

// 取消分析（组件卸载时）
import { onBeforeUnmount } from 'vue'
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
}
.app-subtitle {
  color: var(--text-secondary);
  font-size: 1.05rem;
}

.input-section {
  display: flex;
  gap: 12px;
  align-items: center;
}
.url-input {
  flex: 1;
  font-size: 1.05rem;
  padding: 14px 18px;
}
.parse-btn {
  white-space: nowrap;
  padding: 14px 32px;
}

/* 错误提示 */
.error-banner {
  margin-top: 16px;
  padding: 14px 18px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  color: #dc2626;
  font-size: 0.9rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.error-text {
  white-space: pre-line;
  line-height: 1.7;
}
.error-close {
  background: none;
  color: #dc2626;
  font-size: 1.1rem;
  padding: 4px 8px;
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
  padding: 14px 36px;
  font-size: 1rem;
  font-weight: 700;
  border: 2px dashed var(--text-muted);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-analyze:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
  background: #f9fafb;
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
  transition: background 0.2s;
}

.step-waiting {
  color: var(--text-muted);
}

.step-processing {
  color: var(--text-primary);
  background: #f0f7ff;
  border: 1px solid #bfdbfe;
  animation: pulse-bg 2s ease-in-out infinite;
}

.step-done {
  color: #16a34a;
}

.step-failed {
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.step-dot {
  font-size: 0.9rem;
  width: 22px;
  text-align: center;
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
  0%, 100% { background: #f0f7ff; }
  50% { background: #e0efff; }
}
</style>
