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

    <!-- 思维导图（模块 4 完善） -->
    <div class="card analysis-section" v-if="result.mindmap">
      <h3 class="section-title">
        <span class="section-icon">🧠</span>
        思维导图
      </h3>
      <div class="mindmap-placeholder">
        <div
          v-for="(child, idx) in result.mindmap.children"
          :key="idx"
          class="mindmap-branch"
        >
          <div class="branch-node">{{ child.content }}</div>
          <div class="branch-leaves" v-if="child.children">
            <span
              v-for="(leaf, li) in child.children.slice(0, 4)"
              :key="li"
              class="leaf-tag"
            >
              {{ leaf.content }}
            </span>
            <span v-if="child.children.length > 4" class="leaf-tag more">
              +{{ child.children.length - 4 }}
            </span>
          </div>
        </div>
      </div>
      <p class="mindmap-hint">💡 模块 4 将展示完整交互式思维导图</p>
    </div>
  </div>
</template>

<script setup>
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

/* 思维导图占位 */
.mindmap-placeholder {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mindmap-branch {
  padding: 12px 16px;
  background: #f9fafb;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--text-primary);
}

.branch-node {
  font-weight: 700;
  font-size: 0.92rem;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.branch-leaves {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.leaf-tag {
  font-size: 0.8rem;
  padding: 3px 10px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text-muted);
}

.leaf-tag.more {
  background: var(--text-primary);
  color: #fff;
  border-color: var(--text-primary);
  font-weight: 600;
}

.mindmap-hint {
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--text-muted);
  text-align: center;
}
</style>
