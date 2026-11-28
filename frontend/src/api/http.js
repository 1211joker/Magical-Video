const base = '/api'
let accountId
let accountRequests = new AbortController()
let expireSession

export function onSessionExpired(handler) {
  expireSession = handler
}

export function useRequestAccount(id) {
  accountRequests.abort()
  accountRequests = new AbortController()
  accountId = id
}

export async function apiFetch(path, options = {}, { authenticated = true } = {}) {
  const headers = new Headers(options.headers)
  let signal = options.signal
  if (authenticated) {
    // Cookie 可因另一标签页登录而变化。声明页面正在使用的身份，服务端独立核对。
    if (!accountId) throw new DOMException('账号会话已结束', 'AbortError')
    headers.set('X-Account-Id', accountId)
    signal = signal ? AbortSignal.any([signal, accountRequests.signal]) : accountRequests.signal
  }
  const response = await fetch(base + path, {
    credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options, headers, signal,
  })
  if (authenticated && response.status === 401) {
    const error = await response.clone().json().catch(() => null)
    if (error?.code === 'auth_required' && !signal.aborted) expireSession?.()
  }
  signal?.throwIfAborted()
  return response
}

export async function readApiError(response, fallback) {
  const detail = await response.json().catch(() => ({}))
  return Object.assign(new Error(detail.detail || detail.error || fallback), { code: detail.code })
}

export async function apiRequest(path, method = 'GET', data, settings) {
  const response = await apiFetch(path, {
    method,
    ...(data === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  }, settings)
  if (!response.ok) throw await readApiError(response, '请求失败，请重试')
  return response.status === 204 ? undefined : response.json()
}
