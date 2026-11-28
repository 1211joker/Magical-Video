<template>
  <section class="auth-page" aria-labelledby="auth-title">
    <div class="card auth-card">
      <h1 id="auth-title">{{ registering ? '注册账号' : '登录' }}</h1>
      <p v-if="!registering && accountExpired" class="auth-message" role="status">登录已过期，请重新登录。</p>
      <form class="auth-form" @submit.prevent="submit">
        <label for="account-username">用户名
          <input id="account-username" v-model.trim="username" type="text" autocomplete="username"
                 autocapitalize="none" spellcheck="false" required
                 :maxlength="registering ? 32 : 254" :minlength="registering ? 3 : undefined"
                 :pattern="registering ? usernamePattern : undefined"
                 :aria-describedby="registering ? 'username-help' : undefined">
        </label>
        <p v-if="registering" id="username-help" class="auth-help">3 至 32 位，以字母或数字开头，可用英文字母、数字、下划线和短横线。</p>
        <label for="account-password">密码
          <input id="account-password" v-model="password" type="password" required maxlength="128"
                 :minlength="registering ? 15 : undefined"
                 :autocomplete="registering ? 'new-password' : 'current-password'"
                 :aria-describedby="registering ? 'password-help' : undefined">
        </label>
        <template v-if="registering">
          <p id="password-help" class="auth-help">请输入 15 至 128 个字符。</p>
          <label for="confirm-password">再次输入密码
            <input id="confirm-password" v-model="confirmation" type="password" autocomplete="new-password" maxlength="128" required>
          </label>
        </template>
        <p v-if="error" class="auth-message" role="alert">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="busy">
          {{ busy ? '提交中…' : registering ? '注册并登录' : '登录' }}
        </button>
      </form>
      <div class="auth-links">
        <RouterLink :to="{ name: registering ? 'login' : 'register', query: { redirect: route.query.redirect } }">
          {{ registering ? '已有账号？登录' : '注册账号' }}
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { accountExpired, currentAccount, signIn, signUp } from '../composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const registering = computed(() => route.name === 'register')
const usernamePattern = '[A-Za-z0-9][A-Za-z0-9_\\-]*'
const username = ref('')
const password = ref('')
const confirmation = ref('')
const busy = ref(false)
const error = ref('')

function destination() {
  const next = route.query.redirect
  if (typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')) {
    const target = router.resolve(next)
    if (target.matched.length && !target.meta.public) return target.fullPath
  }
  return { name: 'study-library' }
}

watch(() => route.fullPath, () => {
  password.value = ''
  confirmation.value = ''
  error.value = ''
})

watch([currentAccount, () => route.name], ([user, page]) => {
  if (user && (page === 'login' || page === 'register') && !busy.value) void router.replace(destination())
}, { immediate: true })

async function submit() {
  if (busy.value) return
  const page = route.fullPath
  error.value = ''
  if (registering.value && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致。'
    return
  }
  const next = destination()
  busy.value = true
  try {
    const establishSession = registering.value ? signUp : signIn
    await establishSession(username.value, password.value)
    if (route.fullPath === page) await router.replace(next)
  } catch (reason) {
    if (route.fullPath === page) error.value = reason.message || '提交失败，请稍后再试。'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.auth-page { width: min(100%, 460px); margin: clamp(36px, 8vh, 90px) auto; }
.auth-card { display: grid; gap: 18px; padding: clamp(18px, 5vw, 32px); }
.auth-card h1 { font-size: clamp(1.45rem, 4vw, 1.85rem); line-height: 1.35; }
.auth-form { display: grid; gap: 16px; }
.auth-form label { display: grid; gap: 7px; font-weight: 600; }
.auth-form input {
  width: 100%;
  min-height: 44px;
  padding: 9px 12px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.auth-form input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.auth-form .btn-primary { justify-content: center; min-height: 44px; }
.auth-links { display: flex; gap: 10px 20px; flex-wrap: wrap; font-size: 0.9rem; }
.auth-links a { color: var(--text-primary); text-underline-offset: 3px; }
.auth-help { color: var(--text-secondary); font-size: 0.86rem; }
.auth-message { padding: 10px; border-radius: var(--radius-sm); background: var(--bg-hover); }
</style>
