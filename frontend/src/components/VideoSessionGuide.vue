<template>
  <section class="video-session-guide card" aria-labelledby="video-session-title">
    <h2 id="video-session-title">连接 {{ site.label }} 会话</h2>
    <p v-if="message" role="status">{{ message }}</p>
    <a :href="site.signInUrl" target="_blank" rel="noopener noreferrer">
      打开 {{ site.label }} 登录 <span aria-hidden="true">↗</span>
    </a>
    <template v-if="secureContext">
      <ol class="session-steps">
        <li>在已登录的官方页面打开 Chrome 或 Edge 开发者工具。Mac 按 <kbd>⌥⌘I</kbd>，Windows 按 <kbd>Ctrl+Shift+I</kbd>。</li>
        <li>在开发者工具顶部选「应用（Application）」。如果标签没显示，点标签栏右侧的 <strong>»</strong> 展开。</li>
        <li>在左侧「存储（Storage）」下展开「Cookies」，选 <strong>{{ site.host }}</strong>，复制 <code>{{ site.cookieName }}</code> 这一行的「值（Value）」。</li>
      </ol>
      <form class="session-form" @submit.prevent="connect">
        <label for="video-session-value">{{ site.cookieName }} 会话值</label>
        <input
          id="video-session-value"
          ref="sessionField"
          v-model="sessionValue"
          type="password"
          autocomplete="off"
          spellcheck="false"
          maxlength="8192"
        />
        <p class="session-note">
          {{ site.platform === 'bilibili' ? '当前标签页打开期间，其他 B 站视频可继续使用此会话。' : '会话保留在当前解析页。' }}
          请在自己信任的项目页面填写。
        </p>
        <div class="session-actions">
          <button class="btn-primary" :disabled="!sessionValue.trim()" type="submit">
            {{ submitLabel }}
          </button>
          <button class="btn-secondary" type="button" @click="$emit('dismiss')">取消</button>
        </div>
      </form>
    </template>
    <template v-else>
      <p>请通过本机地址或 HTTPS 打开本项目，再连接会话。</p>
      <button class="btn-secondary" type="button" @click="$emit('dismiss')">关闭</button>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'

defineProps({
  site: { type: Object, required: true },
  message: { type: String, default: '' },
  submitLabel: { type: String, default: '连接会话' },
})

const emit = defineEmits(['connect', 'dismiss'])
const secureContext = window.isSecureContext
const sessionValue = ref('')
const sessionField = ref(null)

onMounted(() => sessionField.value?.focus())

function connect() {
  const value = sessionValue.value.trim()
  if (!secureContext || !value) return
  sessionValue.value = ''
  emit('connect', value)
}
</script>

<style scoped>
.video-session-guide {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  padding: 20px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.video-session-guide h2 {
  color: var(--text-primary);
  font-size: 1.08rem;
}

.video-session-guide a {
  justify-self: start;
  font-weight: 600;
}

.session-steps {
  display: grid;
  gap: 6px;
  padding-inline-start: 1.25rem;
}

.session-form {
  display: grid;
  gap: 8px;
}

.session-form input {
  width: min(100%, 32rem);
}

.session-note {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.session-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
