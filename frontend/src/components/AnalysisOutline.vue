<template>
  <div class="outline-sections">
    <!-- 概述 -->
    <div class="outline-section" :class="{ open: openSections.overview }">
      <button class="outline-toggle" :aria-expanded="openSections.overview" @click="openSections.overview = !openSections.overview">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.overview }">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <span>概述</span>
      </button>
      <Transition name="collapse">
        <p v-if="openSections.overview" class="outline-content">{{ analysisData.overview }}</p>
      </Transition>
    </div>

    <!-- 大纲 -->
    <div class="outline-section" :class="{ open: openSections.outline }">
      <button class="outline-toggle" :aria-expanded="openSections.outline" @click="openSections.outline = !openSections.outline">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.outline }">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <span>大纲</span>
        <span class="outline-count">{{ analysisData.outline?.length || 0 }} 段</span>
      </button>
      <Transition name="collapse">
        <ul v-if="openSections.outline" class="outline-list">
          <li v-for="(item, i) in analysisData.outline" :key="i" class="outline-item">
            <span v-if="item.time" class="outline-time">{{ item.time }}</span>
            <span class="outline-topic">{{ item.topic }}</span>
            <p v-if="item.detail" class="outline-detail">{{ item.detail }}</p>
          </li>
        </ul>
      </Transition>
    </div>

    <!-- 关键要点 -->
    <div class="outline-section" :class="{ open: openSections.keyPoints }">
      <button class="outline-toggle" :aria-expanded="openSections.keyPoints" @click="openSections.keyPoints = !openSections.keyPoints">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.keyPoints }">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <span>关键要点</span>
        <span class="outline-count">{{ analysisData.key_points?.length || 0 }} 条</span>
      </button>
      <Transition name="collapse">
        <ul v-if="openSections.keyPoints" class="keypoints-list">
          <li v-for="(item, i) in analysisData.key_points" :key="i" class="keypoint-item">
            <p class="keypoint-text">{{ item.point }}</p>
            <blockquote v-if="item.evidence" class="keypoint-evidence">{{ item.evidence }}</blockquote>
          </li>
        </ul>
      </Transition>
    </div>

    <!-- 总结 -->
    <div class="outline-section" :class="{ open: openSections.conclusions }">
      <button class="outline-toggle" :aria-expanded="openSections.conclusions" @click="openSections.conclusions = !openSections.conclusions">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.conclusions }">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <span>总结</span>
        <span class="outline-count">{{ analysisData.conclusions?.length || 0 }} 条</span>
      </button>
      <Transition name="collapse">
        <ol v-if="openSections.conclusions" class="conclusions-list">
          <li v-for="(item, i) in analysisData.conclusions" :key="i" class="conclusion-item">
            {{ typeof item === 'string' ? item : item.text }}
          </li>
        </ol>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

defineProps({ analysisData: { type: Object, required: true } })
const openSections = reactive({ overview: true, outline: false, keyPoints: true, conclusions: false })
</script>

<style scoped>
.outline-sections {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.outline-section {
  border-radius: var(--radius-sm);
}

.outline-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 34px;
  padding: 8px 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 0.85rem;
  text-align: left;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast);
}

.outline-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.outline-section.open .outline-toggle {
  color: var(--text-primary);
}

.toggle-arrow {
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-out);
  color: var(--text-muted);
}

.toggle-arrow.rotated {
  transform: rotate(90deg);
}

.outline-count {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.outline-content {
  padding: 4px 8px 8px 24px;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.outline-list {
  list-style: none;
  padding: 2px 6px 8px 24px;
}

.outline-item {
  padding: 6px 4px;
  border-left: 2px solid var(--border);
  margin-bottom: 2px;
}

.outline-item:last-child {
  border-left-color: transparent;
}

.outline-time {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: 3px;
  margin-bottom: 2px;
}

.outline-topic {
  display: block;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 2px;
}

.outline-detail {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 2px;
  line-height: 1.5;
}

.keypoints-list {
  list-style: none;
  padding: 2px 6px 8px 24px;
}

.keypoint-item {
  padding: 6px 4px;
  border-bottom: 1px solid var(--border);
}

.keypoint-item:last-child {
  border-bottom: none;
}

.keypoint-text {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.5;
}

.keypoint-evidence {
  font-size: 0.76rem;
  color: var(--text-secondary);
  border-left: 2px solid var(--border-strong);
  padding: 2px 8px;
  margin-top: 4px;
  line-height: 1.5;
  font-style: italic;
}

.conclusions-list {
  padding: 4px 8px 10px 36px;
}

.conclusion-item {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 2px 0;
}

/* collapse transition */
.collapse-enter-active,
.collapse-leave-active {
  transition: all var(--duration-normal) var(--ease-out);
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 600px;
}
</style>
