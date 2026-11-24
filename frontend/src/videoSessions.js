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
