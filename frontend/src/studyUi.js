import { onBeforeUnmount, onMounted } from 'vue'
import { readAccountState, saveAccountState } from './accountState.js'

export const taskStates = {
  queued: '排队中', running: '处理中', done: '完成', failed: '失败', cancelled: '已取消',
  needs_input: '需要平台会话', needs_retry: '等待确认重试',
}
export const taskPhases = {
  fetching: '获取视频与字幕', subtitles_ready: '已取得字幕', ai: '等待 AI',
  draft_ready: '已整理部分条目', retrieving: '检索 Wiki 和字幕',
}
export const platforms = { youtube: 'YouTube', bilibili: 'B站', panopto: 'Panopto' }

let immediateResult
const IMMEDIATE_CACHE = 'lastAnalysisResult'

function readImmediateCache() {
  const saved = readAccountState(IMMEDIATE_CACHE)
  return saved?.savedAt + 3600_000 > Date.now() ? saved : null
}

export function setImmediateResult(result, { persist = false, id = crypto.randomUUID(), sourceUrl } = {}) {
  const savedAt = Date.now()
  immediateResult = { id, result, sourceUrl, expiresAt: savedAt + 3600_000 }
  if (persist) saveAccountState(IMMEDIATE_CACHE, { ...result, temporaryId: id, sourceUrl, savedAt })
  return id
}

export function clearImmediateResult() {
  immediateResult = undefined
}

export function getImmediateResult(id, sourceUrl) {
  if (immediateResult && immediateResult.expiresAt <= Date.now()) immediateResult = undefined
  if (immediateResult && (!id || immediateResult.id === id) && (!sourceUrl || immediateResult.sourceUrl === sourceUrl)) {
    return immediateResult.result
  }
  const cached = readImmediateCache()
  return cached && (!id || cached.temporaryId === id) && (!sourceUrl || cached.sourceUrl === sourceUrl) ? cached : null
}

export function timecode(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const parts = [Math.floor(total / 60), total % 60]
  if (total >= 3600) parts.splice(0, 1, Math.floor(total / 3600), Math.floor(total / 60) % 60)
  return parts.map(number => String(number).padStart(2, '0')).join(':')
}

export function studyChatLink(scope, scopeId) {
  return { name: 'qa', query: { scope, ...(scopeId ? { scope_id: scopeId } : {}) } }
}

export function conversationLink(id, turn) {
  return { name: 'qa', query: { conversation: id, ...(turn ? { turn } : {}) } }
}

export function videoAnalysisLink(videoId) {
  return { name: 'analyze', query: { video: videoId } }
}

export function analysisTaskLink(taskId) {
  return { name: 'analyze', query: { task: taskId } }
}

export function analysisContent(video) {
  if (!video?.analysis) return null
  return { ...video.analysis, title: video.title, subtitle_segments: video.subtitle_segments }
}

export function isTaskActive(task) {
  return task?.state === 'queued' || task?.state === 'running'
}

export function canRetryTask(task) {
  return ['needs_input', 'needs_retry', 'failed', 'cancelled'].includes(task?.state)
}

export function confirmTaskRetry(task) {
  return task.state !== 'needs_retry' || window.confirm('上一次 AI 请求可能已发出。要重新发送吗？')
}

export function useStudyPolling(refresh, delay = 1600) {
  let timer
  let stopped = false
  let pending = false

  async function tick() {
    if (stopped || pending) return
    clearTimeout(timer)
    pending = true
    try {
      if (!document.hidden) await refresh()
    } finally {
      pending = false
      if (!stopped) timer = setTimeout(tick, delay)
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', tick)
    tick()
  })
  onBeforeUnmount(() => {
    stopped = true
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', tick)
  })
}
