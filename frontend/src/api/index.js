const API_BASE = '/api'

/**
 * 解析视频链接 — 获取元数据（标题、封面、时长等）
 */
export async function parseVideo(url, cookies = null) {
  const body = { url }
  if (cookies) {
    body.cookies = cookies
  }
  const res = await fetch(`${API_BASE}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '解析失败')
  }
  return res.json()
}

/**
 * 创建 SSE 连接 — 实时接收 AI 分析进度和结果
 */
export function createAnalysisSSE(url) {
  return new EventSource(`${API_BASE}/analyze?url=${encodeURIComponent(url)}`)
}

/**
 * 触发视频下载
 */
export function downloadVideo(url, formatId = 'best') {
  const downloadUrl = `${API_BASE}/download?url=${encodeURIComponent(url)}&format_id=${formatId}`
  window.open(downloadUrl, '_blank')
}
