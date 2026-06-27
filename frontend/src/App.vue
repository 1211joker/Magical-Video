<template>
  <div class="app">
    <!-- 无障碍跳过链接 -->
    <a href="#main-content" class="skip-link">跳到主要内容</a>

    <!-- 主题切换按钮 -->
    <button
      class="theme-toggle"
      :title="isDark ? '切换到浅色模式' : '切换到暗色模式'"
      :aria-label="isDark ? '切换到浅色模式' : '切换到暗色模式'"
      @click="toggleTheme"
    >
      <svg v-if="isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
      <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>

    <!-- 导航栏 -->
    <NavBar />

    <!-- 页面内容 -->
    <main id="main-content" tabindex="-1">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import NavBar from './components/NavBar.vue'

// === 主题切换 ===
const THEME_KEY = 'app-theme-preference'
const isDark = ref(false)

function getPreferredTheme() {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function applyTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
    isDark.value = true
  } else {
    document.documentElement.setAttribute('data-theme', 'light')
    isDark.value = false
  }
}

function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  localStorage.setItem(THEME_KEY, next)
  applyTheme(next)
}

// 初始化主题
applyTheme(getPreferredTheme())

// 监听系统主题变化（仅在没有手动设置时生效）
const mqDark = window.matchMedia('(prefers-color-scheme: dark)')
function onSystemThemeChange() {
  if (!localStorage.getItem(THEME_KEY)) {
    applyTheme(mqDark.matches ? 'dark' : 'light')
  }
}
mqDark.addEventListener('change', onSystemThemeChange)

onBeforeUnmount(() => {
  mqDark.removeEventListener('change', onSystemThemeChange)
})
</script>

<style scoped>
.app {
  /* NavBar 自己处理 sticky，这里不需要额外 margin */
}
</style>
