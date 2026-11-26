<template>
  <nav class="navbar" role="navigation" aria-label="主导航">
    <div class="navbar-inner">
      <!-- Logo -->
      <router-link to="/" class="navbar-brand" aria-label="Magical Video 首页">
        <svg class="brand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polygon points="23 7 16 12 23 17 23 7"/>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
        </svg>
        <span class="brand-text">Magical Video</span>
      </router-link>

      <!-- 导航链接 -->
      <div class="navbar-links">
        <router-link
          v-for="item in visibleItems"
          :key="item.path"
          :to="item.path === '/qa' && route.name === 'qa' ? route.fullPath : item.path"
          class="nav-link"
          :aria-label="item.label"
          :class="{ active: isActive(item.path) }"
          :aria-current="isActive(item.path) ? 'page' : undefined"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { studyApi } from '../api/study.js'

const route = useRoute()
const studyAvailable = ref(false)
onMounted(async () => {
  try { await studyApi.status(); studyAvailable.value = true } catch { /* 资料库入口限于本地 */ }
})

const navItems = [
  {
    path: '/',
    label: '首页',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
  },
  {
    path: '/analyze',
    label: 'AI解析',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/></svg>',
  },
  {
    path: '/qa',
    label: 'AI问答',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  },
  {
    path: '/study',
    label: '资料库',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0 0 4h13"/><path d="M8 7h7m-7 4h5"/></svg>',
  },
]
const visibleItems = computed(() => navItems.filter(item => item.path !== '/study' || studyAvailable.value))
const isActive = path => route.path === path || (path === '/study' && route.path.startsWith('/study/'))
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  width: 100%;
  max-width: var(--app-width, 900px);
  margin: 0 auto;
  padding: 0 var(--app-gutter, 0px);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.navbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  max-width: 900px;
  margin: 0 auto;
  padding: 0 4px;
}

/* Brand */
.navbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.15rem;
  transition: opacity var(--duration-fast);
  flex-shrink: 0;
}

.navbar-brand:hover {
  opacity: 0.7;
}

.brand-icon {
  color: var(--text-primary);
}

/* Nav links */
.navbar-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: 0.85rem;
  font-weight: 600;
  transition: color var(--duration-fast), background-color var(--duration-fast);
  white-space: nowrap;
}

.nav-link:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-link.active {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-link.active::after {
  content: '';
  position: absolute;
  bottom: -13px;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 3px;
  border-radius: 2px;
  background: var(--accent);
}

.nav-link {
  position: relative;
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.nav-label {
  display: inline;
}

/* ===== 响应式 ===== */
@media (max-width: 1000px) {
  .navbar-inner { padding-right: 54px; }
}

@media (max-width: 639px) {
  .navbar-inner {
    height: 50px;
    padding-right: 42px;
  }
  .brand-text {
    display: none;
  }
  .nav-link {
    padding: 8px 10px;
    font-size: 0.8rem;
  }
  .nav-icon {
    display: none;
  }
}

@media (max-width: 374px) {
  .nav-link {
    padding: 8px 7px;
  }
}
</style>
