<template>
  <div class="subtitle-viewer">
    <div class="subtitle-header">
      <h3>字幕</h3>
      <button v-if="segments?.length" class="btn-secondary subtitle-download" type="button" @click="downloadVtt">
        下载字幕 (.vtt)
      </button>
    </div>
    <div v-if="!segments || segments.length === 0" class="subtitle-empty">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.4">
        <rect x="2" y="4" width="20" height="16" rx="2"/>
        <path d="M7 12h10m-10 4h6"/>
      </svg>
      <span>暂无字幕数据</span>
    </div>

    <div v-else class="subtitle-list" role="list">
      <div
        v-for="(seg, idx) in segments"
        :key="idx"
        class="subtitle-row"
        :class="{ 'row-even': idx % 2 === 1 }"
        role="listitem"
      >
        <span class="subtitle-time" :aria-label="'时间: ' + formatTime(seg.start_time)">{{ formatTime(seg.start_time) }}</span>
        <span class="subtitle-text">{{ seg.text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  segments: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: '',
  },
})

function vttTime(milliseconds) {
  const hours = Math.floor(milliseconds / 3600000)
  const minutes = Math.floor(milliseconds / 60000) % 60
  const seconds = Math.floor(milliseconds / 1000) % 60
  const time = [hours, minutes, seconds].map(value => String(value).padStart(2, '0')).join(':')
  return time + '.' + String(milliseconds % 1000).padStart(3, '0')
}

function downloadVtt() {
  const cues = []
  for (const segment of props.segments) {
    if (!Number.isFinite(segment?.start_time) || !Number.isFinite(segment.end_time) || typeof segment.text !== 'string') continue
    const text = segment.text.replace(/\s+/g, ' ').trim()
    if (!text) continue
    const start = Math.max(0, Math.round(segment.start_time * 1000))
    const end = Math.max(start + 1, Math.round(segment.end_time * 1000))
    cues.push({ start, end, text: text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;') })
  }
  if (!cues.length) return

  cues.sort((left, right) => left.start - right.start)
  const blocks = cues.map(cue => vttTime(cue.start) + ' --> ' + vttTime(cue.end) + '\n' + cue.text)
  const blob = new Blob(['WEBVTT\n\n' + blocks.join('\n\n') + '\n'], { type: 'text/vtt;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const filename = props.title.replace(/[\\/:*?"<>|\x00-\x1f]/g, '-').slice(0, 120).trim()
  link.href = url
  link.download = (filename || 'transcript') + '.vtt'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function formatTime(seconds) {
  if (seconds == null || isNaN(seconds)) return '--:--'
  const totalSec = Math.floor(seconds)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.subtitle-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.subtitle-header h3 {
  font-size: 1rem;
  color: var(--text-primary);
}

.subtitle-download {
  padding: 7px 11px;
  font-size: 0.8rem;
}

.subtitle-list,
.subtitle-empty {
  max-height: 500px;
  overflow-y: auto;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  border: 1px solid var(--border);
}

.subtitle-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.subtitle-list {
  padding: 4px 0;
}

.subtitle-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 8px 14px;
  font-size: 0.88rem;
  line-height: 1.6;
  transition: background var(--duration-fast);
}

.subtitle-row.row-even {
  background: var(--bg-input);
}

.subtitle-row:hover {
  background: var(--accent-light);
}

.subtitle-time {
  flex-shrink: 0;
  min-width: 52px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: var(--font-mono);
  text-align: center;
}

.subtitle-text {
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  padding-top: 1px;
  overflow-wrap: anywhere;
}

/* 响应式 */
@media (max-width: 639px) {
  .subtitle-row {
    padding: 10px 10px;
    font-size: 0.83rem;
  }
  .subtitle-time {
    min-width: 44px;
    font-size: 0.7rem;
    padding: 2px 6px;
  }
}
</style>
