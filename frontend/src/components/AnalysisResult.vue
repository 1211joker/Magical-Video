<template>
  <div class="analysis-container" v-if="result">
    <!-- 核心摘要 -->
    <div class="card analysis-section">
      <h3 class="section-title">
        <span class="section-icon">📝</span>
        核心摘要
      </h3>
      <p class="summary-text">{{ result.summary }}</p>
    </div>

    <!-- 关键要点 -->
    <div class="card analysis-section" v-if="result.key_points && result.key_points.length">
      <h3 class="section-title">
        <span class="section-icon">🔑</span>
        关键要点
      </h3>
      <ul class="key-points-list">
        <li
          v-for="(point, idx) in result.key_points"
          :key="idx"
          class="key-point-item fade-enter"
          :style="{ animationDelay: `${idx * 0.1}s` }"
        >
          <span class="point-marker">{{ idx + 1 }}</span>
          <span class="point-text">{{ point }}</span>
        </li>
      </ul>
    </div>

    <!-- 思维导图 -->
    <div class="card analysis-section" v-if="result.mindmap">
      <h3 class="section-title">
        <span class="section-icon">🧠</span>
        思维导图
      </h3>
      <MindMap :data="result.mindmap" />
    </div>
  </div>
</template>

<script setup>
import MindMap from './MindMap.vue'

defineProps({
  result: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.analysis-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
}

.analysis-section {
  padding: 24px;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  font-size: 1.1rem;
}

/* 摘要 */
.summary-text {
  font-size: 0.95rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

/* 关键要点 */
.key-points-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.key-point-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: #f9fafb;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  transition: border-color 0.2s;
}

.key-point-item:hover {
  border-color: var(--text-muted);
}

.point-marker {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--text-primary);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.point-text {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--text-secondary);
  padding-top: 1px;
}
</style>
