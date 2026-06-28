<template>
  <div class="video-card card fade-enter" v-if="info">
    <!-- 平台标签 + 封面图 -->
    <div class="video-hero">
      <img
        v-if="info.thumbnail && !thumbFailed"
        :src="thumbnailSrc"
        :alt="info.title"
        class="video-thumbnail"
        referrerpolicy="no-referrer"
        @error="onThumbError"
      />
      <div v-else class="video-thumbnail placeholder">
        <span class="placeholder-icon">🎬</span>
      </div>

      <!-- 平台小标签 -->
      <span class="platform-badge" :class="'badge-' + info.platform">
        {{ platformName }}
      </span>

      <!-- 时长标签 -->
      <span v-if="info.duration" class="duration-badge">
        {{ formatDuration(info.duration) }}
      </span>
    </div>

    <!-- 文字信息 -->
    <div class="video-body">
      <h2 class="video-title">{{ info.title }}</h2>

      <p v-if="info.description" class="video-desc">
        {{ info.description }}
      </p>
    </div>

    <!-- 底部操作栏 -->
    <div class="video-footer" v-if="info.formats && info.formats.length">
      <span class="format-count">
        {{ info.formats.length }} 种清晰度可选
      </span>
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
  return `/api/thumbnail?url=${encodeURIComponent(props.info.thumbnail)}`
})

const platformName = computed(() => {
  const map = {
    youtube: 'YouTube',
    bilibili: 'B站'
  }
  return map[props.info.platform] || props.info.platform
})

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

function onThumbError() {
  thumbFailed.value = true
}
</script>

<style scoped>
.video-card {
  overflow: hidden;
  padding: 0;
}

/* 封面区域 */
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
  background: linear-gradient(135deg, var(--bg-skeleton) 0%, var(--bg-hover) 100%);
}
.placeholder-icon {
  font-size: 3rem;
  opacity: 0.4;
}

/* 平台小标签 */
.platform-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  backdrop-filter: blur(8px);
}
.badge-youtube {
  background: rgba(255, 0, 0, 0.15);
  color: #cc0000;
  border: 1px solid rgba(255, 0, 0, 0.25);
}
.badge-bilibili {
  background: rgba(0, 161, 214, 0.15);
  color: #0099cc;
  border: 1px solid rgba(0, 161, 214, 0.25);
}

/* 时长标签 */
.duration-badge {
  position: absolute;
  bottom: 12px;
  right: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* 文字区域 */
.video-body {
  padding: 20px 24px;
}
.video-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.video-desc {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 底部操作栏 */
.video-footer {
  padding: 14px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.format-count {
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
