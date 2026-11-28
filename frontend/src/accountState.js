let accountId
const prefix = 'magical-video-account:'

export function changeAccountState(id) {
  try {
    if (accountId) {
      const previous = prefix + accountId + ':'
      for (let index = sessionStorage.length - 1; index >= 0; index--) {
        const key = sessionStorage.key(index)
        if (key?.startsWith(previous)) sessionStorage.removeItem(key)
      }
    }
  } catch { /* 浏览器可能限制标签页存储。 */ }
  accountId = id
}

export function readAccountState(key) {
  if (!accountId) return null
  try { return JSON.parse(sessionStorage.getItem(prefix + accountId + ':' + key)) } catch { return null }
}

export function saveAccountState(key, value) {
  if (!accountId) return
  try { sessionStorage.setItem(prefix + accountId + ':' + key, JSON.stringify(value)) } catch { /* 存储不可用 */ }
}
