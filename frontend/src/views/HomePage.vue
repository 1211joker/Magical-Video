<template>
  <div class="home-page">
    <div class="hero">
      <!-- 主标题 -->
      <h1 class="hero-title">Magical Video</h1>

      <!-- 标语 -->
      <p class="hero-tagline">
        AI 驱动的智能视频分析下载工具
      </p>
      <p class="hero-desc">
        粘贴链接 → AI 解析字幕 → 结构化摘要 → 选择性下载
      </p>

      <!-- CTA 按钮 -->
      <router-link to="/analyze" class="hero-cta">
        开始使用
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="5" y1="12" x2="19" y2="12"/>
          <polyline points="12 5 19 12 12 19"/>
        </svg>
      </router-link>
    </div>

    <!-- 简笔画动画区域 -->
    <StickFigures />

    <!-- 底部功能亮点 -->
    <div class="features">
      <div class="feature-item">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polygon points="23 7 16 12 23 17 23 7"/>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
        </svg>
        <span>YouTube &amp; B站</span>
      </div>
      <div class="feature-item">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 2a10 10 0 1 0 10 10H12V2z"/>
          <circle cx="8" cy="8" r="2"/>
          <path d="M4 16l4-4 3 3 4-4 5 5"/>
        </svg>
        <span>AI 智能分析</span>
      </div>
      <div class="feature-item">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        <span>多清晰度下载</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import StickFigures from '../components/StickFigures.vue'
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: calc(100dvh - 56px - 80px);
  padding-top: 80px;
}

/* ===== 主标题区域 ===== */
.hero {
  text-align: center;
  max-width: 520px;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 3.5rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-bottom: 16px;
  animation: fadeInUp 0.6s var(--ease-out) both;
}

.hero-tagline {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  animation: fadeInUp 0.6s var(--ease-out) 0.1s both;
}

.hero-desc {
  font-size: 0.95rem;
  color: var(--text-muted);
  margin-bottom: 36px;
  animation: fadeInUp 0.6s var(--ease-out) 0.2s both;
}

/* CTA 按钮 */
.hero-cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 16px 40px;
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  background: var(--accent);
  color: var(--bg-primary);
  border-radius: var(--radius-sm);
  text-decoration: none;
  transition: all var(--duration-normal) var(--ease-out);
  box-shadow: 0 2px 12px var(--accent-glow);
  animation: fadeInUp 0.6s var(--ease-out) 0.35s both;
}

.hero-cta:hover {
  background: var(--accent-hover);
  box-shadow: 0 4px 20px var(--accent-glow);
  transform: translateY(-2px);
}

.hero-cta:active {
  transform: translateY(0) scale(0.98);
  transition-duration: 50ms;
}

/* ===== 功能亮点 ===== */
.features {
  display: flex;
  gap: 32px;
  margin-top: 40px;
  padding-top: 40px;
  border-top: 1px solid var(--border);
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 600;
}

.feature-item svg {
  opacity: 0.5;
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .home-page {
    padding-top: 50px;
  }
  .hero-title {
    font-size: 2.2rem;
  }
  .hero-tagline {
    font-size: 1rem;
  }
  .hero-desc {
    font-size: 0.88rem;
    margin-bottom: 28px;
  }
  .hero-cta {
    padding: 14px 32px;
    font-size: 1rem;
  }
  .features {
    gap: 20px;
    flex-wrap: wrap;
    justify-content: center;
    margin-top: 30px;
    padding-top: 30px;
  }
}

@media (max-width: 374px) {
  .home-page {
    padding-top: 30px;
  }
  .hero-title {
    font-size: 1.8rem;
  }
  .features {
    gap: 14px;
  }
  .feature-item {
    font-size: 0.8rem;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
