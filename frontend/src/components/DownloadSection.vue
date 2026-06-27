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
import { ref, computed, watch } from 'vue'
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
    await downloadVideo(props.url, selectedFormat.value, props.cookies, true)
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
