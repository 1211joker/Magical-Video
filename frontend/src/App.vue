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

      <!-- 错误提示（支持多行） -->
      <div v-if="errorMsg" class="error-banner fade-enter">
        <span class="error-text">{{ errorMsg }}</span>
        <button class="error-close" @click="errorMsg = ''">✕</button>
      </div>

      <!-- 视频信息展示 -->
      <div v-if="videoInfo && videoInfo.platform !== 'unsupported'" class="result-area fade-enter">
        <VideoInfo :info="videoInfo" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { parseVideo } from './api/index.js'
import VideoInfo from './components/VideoInfo.vue'
import CookieGuide from './components/CookieGuide.vue'

const urlInput = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const errorMsg = ref('')
const cookies = ref(null)

function onCookiesUpdate(cookiesText) {
  cookies.value = cookiesText
}

async function handleParse() {
  if (!urlInput.value.trim()) return

  parsing.value = true
  errorMsg.value = ''
  videoInfo.value = null

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
</style>
