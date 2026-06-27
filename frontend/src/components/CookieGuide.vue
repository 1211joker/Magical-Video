<template>
  <div class="cookie-section">
    <!-- 折叠开关 -->
    <button class="cookie-toggle" @click="expanded = !expanded">
      <span class="toggle-icon">{{ expanded ? '▾' : '▸' }}</span>
      <span>🔐 B站 Cookies 设置</span>
      <span class="toggle-hint">{{ expanded ? '点击收起' : 'B站用户需配置' }}</span>
    </button>

    <!-- 展开内容 -->
    <div v-if="expanded" class="cookie-body card fade-enter">
      <!-- 步骤引导 -->
      <div class="guide-steps">
        <h3 class="guide-title">📖 如何获取 B站 Cookies？（30 秒搞定）</h3>

        <div class="step">
          <div class="step-num">1</div>
          <div class="step-content">
            <strong>用 Chrome 浏览器打开 B站 并登录</strong>
            <p>访问 <a href="https://www.bilibili.com" target="_blank">bilibili.com</a>，确保右上角显示你的头像（已登录状态）</p>
          </div>
        </div>

        <div class="step">
          <div class="step-num">2</div>
          <div class="step-content">
            <strong>安装 Chrome 插件：Get cookies.txt LOCALLY</strong>
            <p>打开 <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank">Chrome 商店链接</a>，点击"添加至 Chrome"</p>
          </div>
        </div>

        <div class="step">
          <div class="step-num">3</div>
          <div class="step-content">
            <strong>在 B站 页面点击插件图标 → Export</strong>
            <p>打开任意一个 B站 视频页面，点击浏览器右上角的插件图标 🍪，然后点击 <code>Export</code> 按钮</p>
          </div>
        </div>

        <div class="step">
          <div class="step-num">4</div>
          <div class="step-content">
            <strong>全选复制 → 粘贴到下方输入框</strong>
            <p>插件会弹出一个页面显示 cookies 内容，<code>Ctrl+A</code> 全选 → <code>Ctrl+C</code> 复制 → 粘贴到下面</p>
          </div>
        </div>
      </div>

      <!-- 粘贴区 -->
      <div class="paste-area">
        <label class="paste-label">📋 将 cookies 内容粘贴到这里：</label>
        <textarea
          v-model="cookiesText"
          placeholder="# Netscape HTTP Cookie File&#10;# 粘贴后长这样：&#10;.bilibili.com	TRUE	/	FALSE	1234567890	bili_jct	abc123..."
          class="cookies-input"
          rows="6"
          @input="onCookiesChange"
        ></textarea>
        <div class="paste-status">
          <span v-if="cookiesValid" class="status-ok">✅ 已检测到完整 cookies（{{ cookieCount }} 条，含关键登录凭证）</span>
          <span v-else-if="cookiesText && missingKeys.length > 0" class="status-warn">
            ⚠️ 缺少关键登录字段：{{ missingKeys.join('、') }}，请重新导出完整 cookies
          </span>
          <span v-else-if="cookiesText && cookieCount < 3" class="status-warn">⚠️ cookies 内容太少（至少需要 3 条），请确认复制完整</span>
          <span v-else-if="cookiesText" class="status-warn">⚠️ 格式不太对，请确认复制的是完整 cookies 内容</span>
          <span v-else class="status-empty">等待粘贴...</span>
        </div>
      </div>

      <!-- 底部提示 -->
      <div class="cookie-tips">
        <p>💡 <strong>提示：</strong>cookies 相当于你的"登录凭证"，只会临时用于本次请求，用完即删，不会存储到服务器。</p>
        <p>⏰ cookies 有效期通常 7-30 天，过期后需要重新粘贴。</p>
        <p>📹 YouTube 视频<strong>不需要</strong>此步骤，直接粘贴链接即可。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const expanded = ref(false)
const cookiesText = ref('')

// 事件通知父组件
const emit = defineEmits(['update:cookies'])

// 暴露给父组件：自动展开面板
function open() {
  expanded.value = true
}

defineExpose({ open })

// B站 登录必须的 3 个关键 cookie
const REQUIRED_COOKIES = ['DedeUserID', 'SESSDATA', 'bili_jct']

const cookieLines = computed(() => {
  return cookiesText.value.trim().split('\n').filter(line => {
    return line.trim() && !line.startsWith('#')
  })
})

const cookieCount = computed(() => cookieLines.value.length)

// 检查是否包含 B站 的关键 cookie 名称
const missingKeys = computed(() => {
  const text = cookiesText.value
  if (!text) return REQUIRED_COOKIES
  return REQUIRED_COOKIES.filter(name => !text.includes(name))
})

const cookiesValid = computed(() => {
  // 至少要有足够的行数 且 包含所有关键 cookie
  return cookieCount.value >= 3 && missingKeys.value.length === 0
})

function onCookiesChange() {
  if (cookiesValid.value) {
    emit('update:cookies', cookiesText.value)
  } else {
    emit('update:cookies', null)
  }
}
</script>

<style scoped>
.cookie-section {
  margin-bottom: 16px;
}

.cookie-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}
.cookie-toggle:hover {
  background: var(--bg-primary);
  border-color: var(--border-strong);
}
.toggle-icon {
  font-size: 0.8rem;
  width: 16px;
}
.toggle-hint {
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* 展开内容 */
.cookie-body {
  margin-top: 12px;
  padding: 24px;
}

.guide-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
}

/* 步骤 */
.step {
  display: flex;
  gap: 14px;
  margin-bottom: 16px;
}
.step-num {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-content strong {
  display: block;
  font-size: 0.92rem;
  color: var(--text-primary);
  margin-bottom: 2px;
}
.step-content p {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 0;
}
.step-content a {
  color: var(--accent);
  font-size: 0.85rem;
}
.step-content code {
  background: var(--bg-input);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.82rem;
}

/* 粘贴区 */
.paste-area {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
.paste-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.cookies-input {
  width: 100%;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  resize: vertical;
}
.paste-status {
  margin-top: 6px;
  font-size: 0.82rem;
}
.status-ok { color: var(--success); }
.status-warn { color: var(--warning); }
.status-empty { color: var(--text-muted); }

/* 底部提示 */
.cookie-tips {
  margin-top: 16px;
  padding: 14px;
  background: var(--accent-light);
  border-radius: var(--radius-sm);
  font-size: 0.83rem;
  color: var(--text-secondary);
  line-height: 1.8;
}
.cookie-tips p {
  margin: 0;
}
</style>
