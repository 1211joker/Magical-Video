<template>
  <div class="analysis-container" v-if="result">
    <!-- 选项卡导航 -->
    <div class="tab-bar" role="tablist" aria-label="分析结果选项卡">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        role="tab"
        :aria-selected="activeTab === tab.key"
        :aria-label="tab.label"
        @click="activeTab = tab.key"
      >
        <!-- SVG icon injected via v-html since they're static inline SVGs -->
        <span class="tab-icon" v-html="tab.icon"></span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </div>

    <!-- 选项卡内容 -->
    <div class="tab-content">
      <Transition name="tab" mode="out-in">
        <!-- 概述 -->
        <div v-if="activeTab === 'overview'" :key="'overview'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            概述
          </h3>
          <p class="overview-text">{{ result.overview }}</p>
        </div>

        <!-- 大纲 -->
        <div v-else-if="activeTab === 'outline'" :key="'outline'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            内容大纲
          </h3>
          <div v-if="!result.outline || result.outline.length === 0" class="empty-hint">
            暂未生成大纲
          </div>
          <div v-else class="outline-list">
            <div v-for="(item, idx) in result.outline" :key="idx" class="outline-item">
              <span class="outline-time">{{ item.time }}</span>
              <div class="outline-body">
                <h4 class="outline-topic">{{ item.topic }}</h4>
                <p class="outline-detail">{{ item.detail }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 要点 -->
        <div v-else-if="activeTab === 'key_points'" :key="'key_points'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            关键要点
          </h3>
          <div v-if="!result.key_points || result.key_points.length === 0" class="empty-hint">
            暂未提取要点
          </div>
          <div v-else class="key-points-list">
            <div v-for="(item, idx) in result.key_points" :key="idx" class="key-point-card"
              :style="{ animationDelay: `${idx * 0.08}s` }">
              <span class="point-marker">{{ idx + 1 }}</span>
              <div class="point-body">
                <p class="point-text">{{ item.point }}</p>
                <blockquote v-if="item.evidence" class="point-evidence">
                  <svg class="evidence-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                  {{ item.evidence }}
                </blockquote>
              </div>
            </div>
          </div>
        </div>

        <!-- 总结 -->
        <div v-else-if="activeTab === 'conclusions'" :key="'conclusions'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            总结
          </h3>
          <div v-if="!result.conclusions || result.conclusions.length === 0" class="empty-hint">
            暂未生成总结
          </div>
          <div v-else class="conclusions-list">
            <div v-for="(item, idx) in result.conclusions" :key="idx" class="conclusion-item">
              <span class="conclusion-marker">{{ idx + 1 }}</span>
              <p class="conclusion-text">{{ item.text }}</p>
            </div>
          </div>
        </div>

        <!-- 思维导图 -->
        <div v-else-if="activeTab === 'mindmap'" :key="'mindmap'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2m-8-10h2m16 0h2m-3.64-7.64l1.42-1.42M4.22 19.78l1.42-1.42m0-12.72l-1.42-1.42m15.56 15.56l-1.42-1.42"/></svg>
            思维导图
          </h3>
          <MindMap v-if="result.mindmap" :data="result.mindmap" />
          <div v-else class="empty-hint">暂未生成思维导图</div>
        </div>

        <!-- 字幕 -->
        <div v-else-if="activeTab === 'subtitles'" :key="'subtitles'" class="card tab-panel">
          <h3 class="section-title">
            <svg class="section-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M7 12h10m-10 4h6"/></svg>
            原始字幕
          </h3>
          <SubtitleViewer :segments="result.subtitle_segments || []" />
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MindMap from './MindMap.vue'
import SubtitleViewer from './SubtitleViewer.vue'

defineProps({
  result: {
    type: Object,
    required: true
  }
})

const activeTab = ref('overview')

const tabs = [
  { key: 'overview', label: '概述', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>' },
  { key: 'outline', label: '大纲', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>' },
  { key: 'key_points', label: '要点', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' },
  { key: 'conclusions', label: '总结', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>' },
  { key: 'mindmap', label: '思维导图', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2m-8-10h2m16 0h2m-3.64-7.64l1.42-1.42M4.22 19.78l1.42-1.42m0-12.72l-1.42-1.42m15.56 15.56l-1.42-1.42"/></svg>' },
  { key: 'subtitles', label: '字幕', icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M7 12h10m-10 4h6"/></svg>' },
]
</script>

<style scoped>
.analysis-container {
  margin-top: 20px;
}

/* ===== 选项卡导航 ===== */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 0;
  overflow-x: auto;
  padding-bottom: 4px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.tab-bar::-webkit-scrollbar { display: none; }

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid transparent;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 40px;
}

.tab-btn:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.tab-btn.active {
  color: var(--accent);
  background: var(--bg-card);
  border-color: var(--border);
  border-bottom-color: var(--bg-card);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
}

.tab-icon {
  display: inline-flex;
  align-items: center;
  color: inherit;
}

.tab-label {
  font-size: 0.82rem;
}

/* ===== 选项卡内容 ===== */
.tab-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-md) var(--radius-md) var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.tab-panel {
  border: none;
  box-shadow: none;
  padding: 24px;
}

.tab-panel:hover {
  box-shadow: none;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-svg {
  color: var(--accent);
  flex-shrink: 0;
}

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 0.88rem;
}

/* ===== 概述 ===== */
.overview-text {
  font-size: 0.95rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

/* ===== 大纲 ===== */
.outline-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.outline-item {
  display: flex;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
}

.outline-item:last-child {
  border-bottom: none;
}

.outline-time {
  flex-shrink: 0;
  min-width: 80px;
  padding: 3px 10px;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: var(--font-mono);
  text-align: center;
  height: fit-content;
}

.outline-body {
  flex: 1;
  min-width: 0;
}

.outline-topic {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.outline-detail {
  font-size: 0.87rem;
  line-height: 1.7;
  color: var(--text-secondary);
  margin: 0;
}

/* ===== 关键要点 ===== */
.key-points-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.key-point-card {
  display: flex;
  gap: 14px;
  padding: 14px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  transition: border-color var(--duration-fast);
  animation: fadeInUp 0.4s var(--ease-out) both;
}

.key-point-card:hover {
  border-color: var(--border-strong);
}

.point-marker {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.point-body {
  flex: 1;
  min-width: 0;
}

.point-text {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
}

.point-evidence {
  margin: 8px 0 0 0;
  padding: 10px 14px;
  background: var(--accent-light);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 0.85rem;
  line-height: 1.7;
  color: var(--text-secondary);
  font-style: normal;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.evidence-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--accent);
}

/* ===== 总结 ===== */
.conclusions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.conclusion-item {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 14px;
  background: var(--success-light);
  border: 1px solid var(--success-border);
  border-radius: var(--radius-sm);
}

.conclusion-marker {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--success);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conclusion-text {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--text-primary);
  margin: 0;
  padding-top: 2px;
}

/* ===== 动画 ===== */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .tab-btn {
    padding: 8px 12px;
    font-size: 0.8rem;
  }
  .tab-label {
    font-size: 0.78rem;
  }
  .tab-panel {
    padding: 16px;
  }
  .outline-item {
    flex-direction: column;
    gap: 8px;
  }
  .outline-time {
    align-self: flex-start;
  }
  .key-point-card {
    flex-direction: column;
    gap: 10px;
  }
}
</style>
