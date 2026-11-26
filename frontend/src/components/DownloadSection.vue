<template>
  <details v-if="formats.length" class="download-section">
    <summary class="download-toggle">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 3v12m-4-4 4 4 4-4M5 16v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"/>
      </svg>
      <span>下载视频</span>
      <span v-if="downloading || status === 'error'" class="download-summary-state">
        {{ downloading ? '准备中…' : '失败' }}
      </span>
      <svg class="disclosure-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="m6 9 6 6 6-6"/>
      </svg>
    </summary>
    <form class="download-options" @submit.prevent="handleDownload">
      <label class="download-format">
        视频清晰度
        <select v-model="selectedFormat" :disabled="downloading">
          <option v-for="fmt in formats" :key="fmt.format_id" :value="fmt.format_id">
            {{ fmt.resolution }}{{ fmt.ext ? ' · ' + fmt.ext.toUpperCase() : '' }}{{ fmt.filesize ? ' · 约 ' + formatSize(fmt.filesize) : '' }}
          </option>
        </select>
      </label>
      <button class="btn-secondary btn-compact" :disabled="downloading" type="submit">
        <span v-if="downloading" class="spinner" aria-hidden="true"></span>
        {{ downloading ? '准备中…' : '开始下载' }}
      </button>
      <p v-if="statusMessage" class="download-status" :data-status="status" role="status">{{ statusMessage }}</p>
    </form>
  </details>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { prepareDownload } from '../api/index.js'

const props = defineProps({
  formats: { type: Array, required: true },
  url: { type: String, required: true },
  credentials: { type: Object, default: undefined }
})
const emit = defineEmits(['error'])

// 默认选中第一个（最高画质，因为 formats 已按分辨率降序排列）
const selectedFormat = ref(props.formats[0]?.format_id || 'best')

// 状态管理
const status = ref('idle')
const downloading = computed(() => status.value === 'preparing')
const statusMessage = ref('')
let downloadController = null
let active = true

function formatSize(bytes) {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

async function handleDownload() {
  if (!active || downloading.value) return

  status.value = 'preparing'
  statusMessage.value = '正在准备文件，请保持页面打开。'
  downloadController = new AbortController()
  const signal = downloadController.signal
  const credentials = props.credentials

  try {
    const url = await prepareDownload(props.url, selectedFormat.value, credentials, signal)
    signal.throwIfAborted()

    const link = document.createElement('a')
    link.href = url
    link.download = ''
    link.referrerPolicy = 'no-referrer'
    document.body.append(link)
    link.click()
    link.remove()

    status.value = 'handedOff'
    statusMessage.value = '已交给浏览器下载，请在浏览器的下载列表查看进度。'
  } catch (err) {
    if (signal.aborted) {
      status.value = 'idle'
      statusMessage.value = ''
    } else {
      status.value = 'error'
      statusMessage.value = err.message || '下载失败，请重试'
      emit('error', err, props.url, credentials, handleDownload)
    }
  } finally {
    downloadController = null
  }
}

onBeforeUnmount(() => {
  active = false
  downloadController?.abort()
})

// 当 formats 变化时（重新解析），重置为第一个
watch(() => props.formats, (newFormats) => {
  if (newFormats && newFormats.length > 0) {
    selectedFormat.value = newFormats[0].format_id
  }
})
</script>

<style scoped>
.download-section {
  max-width: min(100%, 23rem);
  min-width: 0;
}

.download-toggle {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  width: fit-content;
  margin-inline-start: auto;
  padding: 7px 10px;
  min-height: 40px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-secondary);
  cursor: pointer;
  list-style: none;
}

.download-toggle::-webkit-details-marker { display: none; }

.download-toggle:hover, .download-section[open] > .download-toggle {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.download-toggle svg { flex: none; }
.download-section[open] .disclosure-icon { transform: rotate(180deg); }
.download-summary-state { font-size: 0.75rem; font-weight: 600; }
.download-section[open] .download-summary-state { display: none; }

.download-options {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 8px 10px;
  min-width: 0;
  margin-top: 7px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
}

.download-format {
  display: grid;
  gap: 4px;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 700;
}

.download-format select {
  min-width: 0;
  padding: 7px 9px;
  min-height: 40px;
  font-size: 0.86rem;
}

.download-status {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.download-status[data-status="error"] { color: var(--text-primary); }

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-strong);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 639px) {
  .download-toggle { margin-inline-start: 0; }
}
</style>
