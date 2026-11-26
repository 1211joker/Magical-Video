import { shallowRef } from 'vue'

const BILIBILI = {
  platform: 'bilibili',
  label: 'B站',
  host: 'www.bilibili.com',
  cookieName: 'SESSDATA',
  requestField: 'bilibiliSession',
  signInUrl: 'https://www.bilibili.com/',
}

const PANOPTO = {
  platform: 'panopto',
  label: '理大 Panopto',
  host: 'polyu.ap.panopto.com',
  cookieName: '.ASPXAUTH',
  requestField: 'panoptoSession',
}

// B站会话随当前标签页使用，切换路由时可继续用于获取视频和字幕。
const bilibiliSession = shallowRef()

export function useVideoSessions() {
  const panoptoSession = shallowRef()
  const sessionRef = site => site.platform === BILIBILI.platform ? bilibiliSession : panoptoSession

  function getSession(site) {
    return site ? sessionRef(site).value : undefined
  }

  function connectSession(site, value) {
    sessionRef(site).value = { [site.requestField]: value }
  }

  function clearSession(site) {
    sessionRef(site).value = undefined
  }

  function restoreLegacyBilibiliSession(cookies) {
    if (typeof cookies === 'string' && cookies && !bilibiliSession.value) {
      bilibiliSession.value = { cookies }
    }
  }

  return { getSession, connectSession, clearSession, restoreLegacyBilibiliSession }
}

export function sessionSiteFor(input) {
  const value = input?.trim()
  if (!value) return null

  try {
    const url = new URL(value.includes('://') ? value : 'https://' + value.replace(/^\/\//, ''))
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return null
    if (url.origin === 'https://' + PANOPTO.host) return { ...PANOPTO, signInUrl: url.href }

    const host = url.hostname
    if (host === 'bilibili.com' || host.endsWith('.bilibili.com') || host === 'b23.tv' || host.endsWith('.b23.tv')) {
      return BILIBILI
    }
  } catch { /* 等后端校验链接 */ }

  return null
}
