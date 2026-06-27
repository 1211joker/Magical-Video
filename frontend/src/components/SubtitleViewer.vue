<template>
  <div class="subtitle-viewer">
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
defineProps({
  segments: {
    type: Array,
    default: () => []
  }
})

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
.subtitle-viewer {
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
  padding-top: 1px;
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
