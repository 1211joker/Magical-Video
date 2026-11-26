const API_BASE = '/api'

async function readApiError(response, fallback) {
  const detail = await response.json().catch(() => ({}))
  return Object.assign(new Error(detail.detail || detail.error || fallback), { code: detail.code })
}

function videoRequest(url, { cookies, bilibiliSession, panoptoSession } = {}) {
  const body = { url }
  if (cookies) body.cookies = cookies
  if (bilibiliSession) body.bilibili_session = bilibiliSession
  if (panoptoSession) body.panopto_session = panoptoSession
  return body
}

export async function getAIProviders(signal) {
  const response = await fetch(`${API_BASE}/ai/providers`, { signal, cache: 'no-store' })
  if (!response.ok) throw await readApiError(response, '模型列表加载失败')
  return response.json()
}

/**
 * 解析视频链接 — 获取元数据（标题、封面、时长等）
 */
export async function parseVideo(url, credentials) {
  const res = await fetch(`${API_BASE}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(videoRequest(url, credentials))
  })
  if (!res.ok) {
    throw await readApiError(res, '解析失败')
  }
  return res.json()
}

export async function extractSubtitles(url, credentials, signal) {
  const response = await fetch(`${API_BASE}/subtitles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(videoRequest(url, credentials)),
    signal,
  })
  if (!response.ok) throw await readApiError(response, '字幕提取失败')
  return response.json()
}

/**
 * 启动 AI 分析 — 通过 fetch + ReadableStream 接收 SSE 事件。
 *
 * 为什么不用 EventSource？EventSource 只支持 GET 请求，无法传 cookies 文本（可能很长）。
 * 我们用 fetch POST 发请求，手动读取 body 流，逐行解析 SSE 事件。
 *
 * 参数：
 *   url       - 视频链接
 *   credentials - 视频平台会话（可选）
 *   onEvent   - 收到事件时的回调，参数 { step, status, message, result? }
 *   onError   - 发生错误时的回调
 *   provider  - 所选 AI 服务（可选）
 *
 * 返回：
 *   { abort: () => void } — 用于取消分析
 */
export function startAnalysis(url, credentials, onEvent, onError, provider) {
  const controller = new AbortController()

  fetch(`${API_BASE}/analyze-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...videoRequest(url, credentials), provider: provider || undefined }),
    signal: controller.signal
  }).then(async (response) => {
    if (!response.ok) {
      onError(await readApiError(response, '分析请求失败'))
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
 * AI 问答 — 基于视频字幕内容向 AI 提问。
 *
 * 参数：
 *   question         - 用户问题
 *   subtitleText     - 字幕全文（作为回答依据）
 *   analysisSummary  - AI 分析结果摘要（辅助理解上下文）
 *   chatHistory      - 之前的问答消息，按时间顺序排列
 *   options          - 所选 AI 服务和会话编号（可选）
 *
 * 返回：
 *   { answer: string }
 */
export async function askQuestion(question, subtitleText, analysisSummary, chatHistory = [], { provider, sessionId } = {}) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      subtitle_text: subtitleText,
      analysis_summary: analysisSummary,
      chat_history: chatHistory,
      provider: provider || undefined,
      session_id: sessionId,
    })
  })
  if (!res.ok) {
    throw await readApiError(res, '问答请求失败')
  }
  return res.json()
}

/**
 * 提交下载任务并等待文件准备完毕，返回供浏览器直接访问的下载地址。
 */
export async function prepareDownload(url, formatId, credentials, signal) {
  signal?.throwIfAborted()
  const jobsUrl = `${API_BASE}/download/jobs`
  // 先取得任务编号，页面即使在提交期间离开也能取消已创建的任务。
  const response = await fetch(jobsUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...videoRequest(url, credentials), format_id: formatId }),
  })
  const { job_id: jobId } = await readDownloadResponse(response)
  const jobUrl = `${jobsUrl}/${jobId}`

  try {
    while (true) {
      const statusResponse = await fetch(jobUrl, { cache: 'no-store', signal })
      const status = await readDownloadResponse(statusResponse)
      signal?.throwIfAborted()
      if (status.status === 'ready') return status.download_url
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  } catch (error) {
    // 取消请求失败时，后端仍会按任务有效期清理。
    void fetch(jobUrl, { method: 'DELETE', keepalive: true }).catch(() => {})
    throw error
  }
}

async function readDownloadResponse(response) {
  if (!response.ok) {
    throw await readApiError(response, '下载失败，请重试')
  }
  return response.json()
}
