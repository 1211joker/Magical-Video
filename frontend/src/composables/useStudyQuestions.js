import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { studyApi, studyRequestId } from '../api/study.js'
import { readAccountState, saveAccountState } from '../accountState.js'
import {
  analysisContent, confirmTaskRetry, conversationLink, getImmediateResult, isTaskActive, studyChatLink,
  useStudyPolling,
} from '../studyUi.js'

const RECENT_QUESTION_KEY = 'recentQuestionLocation'
const emptyIndex = () => ({ videos: [], courses: [] })

function immediateAnalysis(temporaryId) {
  const id = temporaryId === '1' ? undefined : temporaryId
  const data = getImmediateResult(id)
  return data?.subtitle_text && data?.title ? data : null
}

function rememberLocation(query) {
  // 仅保存入口所需的 ID。分析内容和平台会话仍由各自的数据生命周期管理。
  saveAccountState(RECENT_QUESTION_KEY, query)
}

export function useStudyQuestions() {
  const route = useRoute()
  const router = useRouter()
  const index = ref(emptyIndex())
  const context = ref(null)
  const conversation = ref(null)
  const history = ref([])
  const includeAll = ref(false)
  const course = ref(null)
  const lectureId = ref('')
  const analysis = ref(null)
  const lectureLoading = ref(false)
  const lectureError = ref('')
  const loading = ref(true)
  const error = ref('')
  const active = computed(() => conversation.value?.tasks.some(isTaskActive) ?? false)
  let visit = 0
  let conversationRead = 0
  let requestAttempt

  const isCurrent = generation => generation === visit && route.name === 'qa'

  async function loadIndex() {
    try { return await studyApi.library() } catch { return emptyIndex() }
  }

  async function loadHistory() {
    const generation = visit
    const scope = context.value
    if (!scope || scope.kind === 'temporary') return
    const all = includeAll.value
    try {
      const items = all || conversation.value?.archived
        ? await studyApi.conversations()
        : await studyApi.conversations(scope.kind, scope.id)
      if (isCurrent(generation) && all === includeAll.value) history.value = items
    } catch (err) {
      if (isCurrent(generation)) error.value = err.message
    }
  }

  async function loadLecture(id) {
    const generation = visit
    lectureId.value = id
    analysis.value = null
    lectureError.value = ''
    lectureLoading.value = Boolean(id)
    if (!id) return
    try {
      const video = await studyApi.video(id)
      if (isCurrent(generation) && lectureId.value === id) analysis.value = analysisContent(video)
    } catch (err) {
      if (isCurrent(generation) && lectureId.value === id) lectureError.value = err.message
    } finally {
      if (isCurrent(generation) && lectureId.value === id) lectureLoading.value = false
    }
  }

  async function loadTemporary(query, generation) {
    const data = query.task ? await studyApi.task(query.task) : null
    if (!isCurrent(generation)) return
    if (data?.result?.id && data.kind === 'analysis') {
      await router.replace(studyChatLink('video', data.result.id))
      return
    }
    const result = data
      ? (data.kind === 'analysis' && data.state === 'done' ? analysisContent(data.result) : null)
      : immediateAnalysis(query.temporary)
    if (!result) throw new Error(data ? '这条视频还没有可用于问答的分析结果。' : '临时分析已过期，请重新分析视频。')
    analysis.value = result
    context.value = { kind: 'temporary', title: result.title }
    rememberLocation(query)
  }

  async function showRequestedTurn(turn) {
    if (!turn) return
    await nextTick()
    if (route.query.turn === turn) document.getElementById('study-turn-' + turn)?.scrollIntoView({ block: 'nearest' })
  }

  async function load() {
    if (route.name !== 'qa') {
      visit++
      return
    }
    const query = { ...route.query }
    if (query.conversation && conversation.value?.id === query.conversation) {
      if (!loading.value) rememberLocation({ conversation: query.conversation })
      await showRequestedTurn(query.turn)
      return
    }
    const generation = ++visit
    loading.value = true
    error.value = ''
    context.value = null
    conversation.value = null
    course.value = null
    analysis.value = null
    lectureId.value = ''
    lectureError.value = ''
    lectureLoading.value = false
    history.value = []
    requestAttempt = null

    try {
      const choices = await loadIndex()
      if (!isCurrent(generation)) return
      index.value = choices
      const explicit = query.conversation ? await studyApi.conversation(query.conversation) : null
      if (!isCurrent(generation)) return
      if (!query.conversation && !query.scope && !query.task && !query.temporary) {
        const remembered = readAccountState(RECENT_QUESTION_KEY)
        if (remembered?.conversation || remembered?.scope || remembered?.task || remembered?.temporary) {
          await router.replace({ name: 'qa', query: remembered })
        } else if (immediateAnalysis()) {
          await router.replace({ name: 'qa', query: { temporary: '1' } })
        } else if (choices.videos[0]) {
          await router.replace(studyChatLink('video', choices.videos[0].id))
        }
        return
      }
      if (query.task || query.temporary) {
        await loadTemporary(query, generation)
        return
      }

      const kind = explicit?.scope ?? query.scope
      const id = explicit?.scope_id ?? query.scope_id
      if (!['video', 'course', 'library'].includes(kind) || (kind !== 'library' && !id)) {
        throw new Error('请选择要提问的视频或课程。')
      }
      const scope = kind === 'library' ? null : id
      const [record, items] = await Promise.all([
        explicit?.archived || kind === 'library' ? null
          : kind === 'video' ? studyApi.video(scope) : studyApi.course(scope, { includeSuggestions: false }),
        includeAll.value || explicit?.archived ? studyApi.conversations() : studyApi.conversations(kind, scope),
      ])
      if (!isCurrent(generation)) return
      const latest = items.find(item => item.scope === kind && item.scope_id === scope)
      const current = explicit ?? (!query.fresh && latest ? await studyApi.conversation(latest.id) : null)
      if (!isCurrent(generation)) return
      context.value = { kind, id: scope, title: record?.title ?? explicit?.scope_title ?? '全部资料' }
      conversation.value = current
      history.value = items
      if (kind === 'video') {
        analysis.value = analysisContent(record)
      } else if (kind === 'course' && record) {
        course.value = record
        await loadLecture(record.videos[0]?.id ?? '')
      }
      if (!isCurrent(generation)) return
      if (current && current.id !== query.conversation) await router.replace(conversationLink(current.id))
      if (!isCurrent(generation)) return
      rememberLocation(current ? { conversation: current.id } : studyChatLink(kind, scope).query)
      await showRequestedTurn(query.turn)
    } catch (err) {
      if (isCurrent(generation)) error.value = err.message
    } finally {
      if (isCurrent(generation)) loading.value = false
    }
  }

  watch(() => route.fullPath, load, { immediate: true })
  watch(includeAll, loadHistory)
  onBeforeUnmount(() => { visit++ })

  async function refreshConversation() {
    const generation = visit
    const id = conversation.value?.id
    if (!id) return
    const revision = ++conversationRead
    const updated = await studyApi.conversation(id)
    if (!isCurrent(generation) || revision !== conversationRead || conversation.value?.id !== id) return
    const changed = updated.updated_at !== conversation.value.updated_at
    conversation.value = updated
    error.value = ''
    if (changed) await loadHistory()
  }

  useStudyPolling(async () => {
    if (!active.value || loading.value || route.name !== 'qa') return
    const generation = visit
    try {
      await refreshConversation()
    } catch (err) {
      if (isCurrent(generation)) error.value = err.message
    }
  })

  async function send(question, recall, provider) {
    const generation = visit
    const { kind, id } = context.value
    if (!conversation.value) {
      const created = await studyApi.newConversation(kind, id)
      if (!isCurrent(generation)) return
      conversation.value = { ...created, turns: [], tasks: [] }
      await router.replace(conversationLink(created.id))
      if (!isCurrent(generation)) return
    }
    const conversationId = conversation.value.id
    const key = JSON.stringify([conversationId, question, recall, provider])
    if (requestAttempt?.key !== key) requestAttempt = { key, id: studyRequestId() }
    const job = await studyApi.ask(conversationId, question, requestAttempt.id, recall, provider)
    if (!isCurrent(generation)) return
    if (job.state !== 'done' && !conversation.value.tasks.some(task => task.id === job.id)) {
      conversation.value.tasks.push({ ...job, question })
    }
    requestAttempt = null
    if (!isTaskActive(job)) await refreshConversation()
  }

  async function changeTask(task, action) {
    if (action === 'retry' && !confirmTaskRetry(task)) return
    const generation = visit
    if (action === 'retry') await studyApi.retryTask(task.id)
    else await studyApi.cancelTask(task.id)
    if (isCurrent(generation)) await refreshConversation()
  }

  async function removeConversation() {
    const current = conversation.value
    if (!current || !window.confirm('删除整个对话？相关旧问答会退出回忆。')) return
    const generation = visit
    const { kind, id } = context.value
    await studyApi.deleteConversation(current.id)
    if (isCurrent(generation)) await router.replace(current.archived ? studyChatLink('library') : studyChatLink(kind, id))
  }

  return {
    index, context, conversation, history, includeAll, course, lectureId, analysis, lectureLoading, lectureError,
    loading, error, active, load, loadLecture, send, changeTask, removeConversation,
  }
}
