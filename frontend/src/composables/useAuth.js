import { readonly, shallowRef } from 'vue'
import { changeAccountState } from '../accountState.js'
import { authApi } from '../api/auth.js'
import { onSessionExpired, useRequestAccount } from '../api/http.js'
import { clearImmediateResult } from '../studyUi.js'
import { clearVideoSessions } from '../videoSessions.js'

const account = shallowRef()
const revision = shallowRef(0)
const expired = shallowRef(false)
const changedKey = 'magical-video-session-changed'
let checking

function setAccount(next) {
  if (next === undefined || next?.id !== account.value?.id) {
    revision.value++
    useRequestAccount(next?.id)
    changeAccountState(next?.id)
    clearImmediateResult()
    clearVideoSessions()
  }
  account.value = next
}

export function refreshAccount() {
  if (checking) return checking
  const before = revision.value
  checking = authApi.session().then(result => {
    if (before === revision.value) {
      expired.value = Boolean(account.value && !result)
      setAccount(result)
    }
    return account.value
  }).finally(() => { checking = undefined })
  return checking
}

export async function checkAccount() {
  return account.value === undefined ? refreshAccount() : account.value
}

function notifyOtherTabs() {
  try { localStorage.setItem(changedKey, crypto.randomUUID()) } catch { /* 跨标签页提示不可用 */ }
}

function establishAccount(user) {
  expired.value = false
  setAccount(user)
  notifyOtherTabs()
}

export async function signIn(username, password) {
  establishAccount(await authApi.login(username, password))
}

export async function signUp(username, password) {
  establishAccount(await authApi.register(username, password))
}

export async function signOut() {
  await authApi.logout()
  expired.value = false
  setAccount(null)
  notifyOtherTabs()
}

onSessionExpired(() => {
  expired.value = true
  setAccount(null)
})

export function watchAccountSession() {
  const refresh = () => { if (!document.hidden) refreshAccount().catch(() => {}) }
  const changed = event => {
    if (event.key !== changedKey) return
    setAccount(undefined)
    // 先结束旧请求，再读取其他标签页更新后的 Cookie。
    Promise.resolve(checking).catch(() => {}).then(refresh)
  }
  window.addEventListener('storage', changed)
  document.addEventListener('visibilitychange', refresh)
  const timer = setInterval(refresh, 60_000)
  refresh()
  return () => {
    clearInterval(timer)
    window.removeEventListener('storage', changed)
    document.removeEventListener('visibilitychange', refresh)
  }
}

export const currentAccount = readonly(account)
export const accountRevision = readonly(revision)
export const accountExpired = readonly(expired)
