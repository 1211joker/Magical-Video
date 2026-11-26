<template>
  <div class="video-preview-info" v-if="info">
    <div class="video-cover">
      <img
        v-if="info.thumbnail && !thumbFailed"
        :src="thumbnailSrc"
        alt=""
        class="video-thumbnail"
        referrerpolicy="no-referrer"
        @error="thumbFailed = true"
      />
      <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>
      </svg>
    </div>
    <div class="video-body">
      <p class="video-meta">{{ platformName }}<template v-if="info.duration"> · {{ formatDuration(info.duration) }}</template></p>
      <h2 class="video-title" :title="info.title">{{ info.title }}</h2>
      <p v-if="info.description" class="video-desc">{{ info.description }}</p>
      <a v-if="info.platform === 'panopto'" :href="info.webpage_url" target="_blank" rel="noopener noreferrer" class="video-source">
        在 Panopto 播放
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M13 5h6v6m0-6-8 8m7 0v5H6V6h5"/>
        </svg>
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  info: {
    type: Object,
    required: true
  }
})

const thumbFailed = ref(false)

// 封面图通过后端代理加载（解决 B站 防盗链问题）
const thumbnailSrc = computed(() => {
  if (!props.info?.thumbnail) return ''
  if (props.info.platform === 'panopto') return props.info.thumbnail
  return `/api/thumbnail?url=${encodeURIComponent(props.info.thumbnail)}`
})

const platformName = computed(() => {
  const map = {
    youtube: 'YouTube',
    bilibili: 'B站',
    panopto: '理大 Panopto'
  }
  return map[props.info.platform] || props.info.platform
})

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.video-preview-info {
  display: grid;
  grid-template-columns: var(--video-cover-width, 160px) minmax(0, 1fr);
  gap: clamp(12px, 3vw, 22px);
  align-items: start;
}

.video-cover {
  display: grid;
  place-items: center;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.video-thumbnail {
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: cover;
}

.video-body { min-width: 0; }

.video-meta {
  color: var(--text-secondary);
  font-size: 0.81rem;
  font-weight: 700;
  line-height: 1.4;
}

.video-title {
  margin: 5px 0 0;
  font-size: clamp(1rem, 2.5vw, 1.18rem);
  font-weight: 700;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.video-desc {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.video-source {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 36px;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 0.84rem;
  text-underline-offset: 3px;
}

@media (max-width: 639px) {
  .video-title { -webkit-line-clamp: 3; }
  .video-desc { font-size: 0.81rem; }
}
</style>
