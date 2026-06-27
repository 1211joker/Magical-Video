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
 * 启动 AI 分析 — 通过 fetch + ReadableStream 接收 SSE 事件。
 *
 * 为什么不用 EventSource？EventSource 只支持 GET 请求，无法传 cookies 文本（可能很长）。
 * 我们用 fetch POST 发请求，手动读取 body 流，逐行解析 SSE 事件。
 *
 * 参数：
 *   url       - 视频链接
 *   cookies   - B站 cookies（可选）
 *   onEvent   - 收到事件时的回调，参数 { step, status, message, result? }
 *   onError   - 发生错误时的回调
 *
 * 返回：
 *   { abort: () => void } — 用于取消分析
 */
export function startAnalysis(url, cookies, onEvent, onError) {
  const controller = new AbortController()

  fetch(`${API_BASE}/analyze-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, cookies }),
    signal: controller.signal
  }).then(async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }))
      onError(new Error(err.detail || '分析请求失败'))
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE 事件以 \n\n 分隔
        const parts = buffer.split('\n\n')
        // 保留最后一段不完整的数据
        buffer = parts.pop()

        for (const part of parts) {
          // 找 data: 开头的行
          const lines = part.split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                onEvent(data)
              } catch (e) {
                // 跳过解析失败的行
              }
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        onError(err)
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err)
    }
  })

  return controller
}

/**
 * 触发视频下载
 */
export function downloadVideo(url, formatId = 'best') {
  const downloadUrl = `${API_BASE}/download?url=${encodeURIComponent(url)}&format_id=${formatId}`
  window.open(downloadUrl, '_blank')
}
