<template>
  <div v-if="sources.length" class="study-evidence">
    <h3 v-if="title">{{ title }}</h3>
    <details v-for="source in sources" :key="source.id">
      <summary>{{ source.video_title }} · {{ timecode(source.start_time) }}–{{ timecode(source.end_time) }}</summary>
      <blockquote>{{ source.quote || source.text }}</blockquote>
      <a :href="sourceUrl(source)" target="_blank" rel="noopener noreferrer">打开原视频 ↗</a>
    </details>
  </div>
</template>

<script setup>
import { timecode } from '../studyUi.js'

defineProps({
  sources: { type: Array, required: true },
  title: { type: String, default: '字幕出处' },
})

function sourceUrl(source) {
  const url = new URL(source.url)
  const time = Math.floor(source.start_time)
  if (source.platform === 'youtube') url.searchParams.set('t', String(time))
  if (source.platform === 'bilibili') url.searchParams.set('t', String(time))
  return url.href
}
</script>
