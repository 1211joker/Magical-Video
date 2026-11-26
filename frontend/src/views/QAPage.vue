<template>
  <div class="qa-page">
    <header class="qa-toolbar card">
      <div class="qa-heading">
        <h1 class="page-title">AI 问答</h1>
        <div v-if="context" class="qa-scope-title">
          <p>{{ scopeLabel }}</p>
          <h2 :title="context.title">{{ context.title }}</h2>
        </div>
      </div>
      <div v-if="context || index.videos.length || index.courses.length" class="qa-toolbar-actions">
        <label v-if="index.videos.length || index.courses.length" class="qa-scope-select">
          <span class="sr-only">切换问答范围</span>
          <select :value="scopeSelection" :disabled="sending || loading" @change="changeScope($event.target.value)">
            <option v-if="!context" value="" disabled>选择视频或课程</option>
            <option v-if="context?.kind === 'temporary'" value="temporary">{{ context.title }}</option>
            <option v-if="conversation?.archived" :value="scopeSelection" disabled>{{ context.title }}（已删除）</option>
            <optgroup v-if="index.videos.length" label="单个视频">
              <option v-for="video in index.videos" :key="video.id" :value="'video:' + video.id">{{ video.title }}</option>
            </optgroup>
            <optgroup v-if="index.courses.length" label="整门课程">
              <option v-for="item in index.courses" :key="item.id" :value="'course:' + item.id">{{ item.title }}</option>
            </optgroup>
            <option value="library">全部资料</option>
          </select>
        </label>
        <template v-if="context && context.kind !== 'temporary'">
          <details ref="historyPanel" class="qa-history">
            <summary class="btn-secondary btn-compact">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 2"/>
              </svg>
              历史对话
            </summary>
            <div class="qa-history-panel card">
              <label class="study-check">
                <input v-model="includeAll" type="checkbox" :disabled="conversation?.archived">显示所有范围的对话
              </label>
              <ul v-if="history.length">
                <li v-for="item in history" :key="item.id">
                  <RouterLink :to="conversationLink(item.id)" :aria-current="conversation?.id === item.id ? 'true' : undefined">
                    {{ item.title }}
                    <small v-if="includeAll || conversation?.archived">{{ item.scope_label }}</small>
                  </RouterLink>
                </li>
              </ul>
              <p v-else>当前范围暂无历史对话。</p>
              <button v-if="conversation" class="quiet-action" :disabled="sending" @click="deleteConversation">删除当前对话</button>
            </div>
          </details>
          <button v-if="canAsk" class="btn-secondary btn-compact" type="button"
                  :disabled="sending || loading" @click="startNewConversation">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" aria-hidden="true">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            新对话
          </button>
        </template>
      </div>
    </header>

    <p v-if="loading" class="empty-state card" role="status">正在读取问答资料…</p>
    <div v-else-if="!context" class="empty-state card">
      <div>
        <h2 class="empty-title">{{ error ? '暂时无法打开问答' : '还没有分析数据' }}</h2>
        <p class="empty-desc">{{ error || '分析一个视频后，就可以结合字幕和分析结果提问。' }}</p>
      </div>
      <RouterLink to="/analyze" class="btn-primary btn-compact">前往 AI解析</RouterLink>
    </div>

    <div v-else class="qa-layout">
      <button class="analysis-toggle btn-secondary btn-compact" type="button" aria-controls="qa-context-panel"
              :aria-expanded="showAnalysis" @click="showAnalysis = !showAnalysis">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2"/><path d="M9 5v14"/>
        </svg>
        {{ showAnalysis ? '收起资料' : context.kind === 'course' ? '查看本讲分析' : context.kind === 'library' ? '查看资料范围' : '查看视频分析' }}
      </button>
      <aside id="qa-context-panel" class="outline-sidebar card" :class="{ expanded: showAnalysis }" aria-labelledby="qa-context-title">
        <header class="outline-header">
          <h2 id="qa-context-title">{{ context.kind === 'library' ? '资料范围' : '视频分析' }}</h2>
          <div v-if="analysisLink || course" class="outline-links">
            <RouterLink v-if="analysisLink" :to="analysisLink" class="qa-context-link">查看完整解析 <span aria-hidden="true">↗</span></RouterLink>
            <RouterLink v-if="course" :to="{ name: 'study-course', params: { courseId: course.id }, query: { tab: 'wiki' } }"
                        class="qa-context-link">课程 Wiki</RouterLink>
          </div>
        </header>
        <div class="outline-scroll" tabindex="0" aria-label="分析内容">
          <div v-if="course?.videos.length" class="lecture-picker">
            <label for="qa-lecture">查看单讲分析</label>
            <select id="qa-lecture" :value="lectureId" @change="loadLecture($event.target.value)">
              <option v-for="(item, position) in course.videos" :key="item.id" :value="item.id">
                第 {{ position + 1 }} 讲 · {{ item.title }}
              </option>
            </select>
          </div>
          <h3 v-if="analysisData" class="outline-video-title">{{ analysisData.title || context.title }}</h3>
          <p v-if="lectureLoading" class="outline-note" role="status">正在读取本讲分析…</p>
          <p v-else-if="lectureError" class="outline-note" role="alert">{{ lectureError }}</p>
          <AnalysisOutline v-else-if="analysisData" :key="lectureId || analysisData.title" :analysis-data="analysisData" />
          <p v-else-if="context.kind === 'library'" class="outline-note">可查阅 {{ index.videos.length }} 条已保存视频和 {{ index.courses.length }} 门课程。</p>
          <p v-else-if="conversation?.archived" class="outline-note">原始资料已删除。可查看历史对话。</p>
          <p v-else class="outline-note">加入课程视频后，可在这里查看每一讲的分析。</p>
        </div>
      </aside>

      <section class="chat-area card" aria-label="对话">
        <div ref="chatMessagesRef" class="chat-messages" role="log" aria-label="问答消息" tabindex="0">
          <div v-if="!entries.length" class="chat-message assistant">
            <div class="message-avatar" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/></svg>
            </div>
            <div class="message-bubble">
              <p v-if="conversation?.archived">该对话已归档。</p>
              <p v-else-if="!canAsk">当前范围还没有已分析的视频。</p>
              <p v-else-if="context.kind === 'course'">你可以结合这门课的字幕提问，或比较不同讲次。</p>
              <p v-else-if="context.kind === 'library'">提问时可以加上视频名、讲次或想了解的概念。</p>
              <p v-else>可以从分析要点问起，也可以直接输入你的问题。</p>
              <div v-if="suggestions.length && canAsk" class="question-suggestions" aria-label="建议问题">
                <button v-for="suggestion in suggestions" :key="suggestion.question" type="button"
                        class="btn-secondary btn-compact" @click="fillQuestion(suggestion.question)">{{ suggestion.label }}</button>
              </div>
            </div>
          </div>

          <template v-for="entry in entries" :key="entry.id">
            <div :id="'study-turn-' + entry.id" class="chat-message user">
              <div class="message-avatar" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"/><path d="M4 21v-3a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v3"/></svg>
            </div>
              <p class="message-bubble">{{ entry.question }}</p>
            </div>
            <div class="chat-message assistant" :data-answer-id="entry.id">
              <div class="message-avatar" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/></svg>
            </div>
              <div v-if="entry.answer" class="message-bubble">
                <template v-for="(block, position) in parseMessageBlocks(entry.answer)" :key="position">
                  <blockquote v-if="block.type === 'quote'" class="msg-quote">{{ block.text }}</blockquote>
                  <p v-else class="msg-paragraph">
                    <template v-for="(part, partIndex) in answerTextParts(block.text)" :key="partIndex">
                      <strong v-if="part.bold">{{ part.text }}</strong><template v-else>{{ part.text }}</template>
                    </template>
                  </p>
                </template>
                <p v-if="entry.invalidated" class="answer-note">来源已删除，此轮已退出回忆。</p>
                <details v-if="entry.citations?.length" class="answer-sources">
                  <summary>字幕出处 · {{ entry.citations.length }} 条</summary>
                  <StudySources :sources="entry.citations" title="" />
                </details>
                <div v-if="entry.recalled?.length" class="recalled-answers">
                  <h3>参考的旧问答</h3>
                  <ul>
                    <li v-for="memory in entry.recalled" :key="memory.id">
                      <RouterLink :to="conversationLink(memory.conversation_id, memory.id)">{{ memory.question }}</RouterLink>
                    </li>
                  </ul>
                </div>
              </div>
              <div v-else-if="entry.pending || isTaskActive(entry.task)" class="message-bubble typing-bubble" role="status">
                <span>{{ entry.task?.state === 'queued' ? '等待回答' : '正在回答' }}</span>
                <span class="typing-dot" aria-hidden="true"></span><span class="typing-dot" aria-hidden="true"></span><span class="typing-dot" aria-hidden="true"></span>
                <button v-if="entry.task" class="quiet-action" :disabled="sending" @click="updateTask(entry.task, 'cancel')">取消</button>
              </div>
              <div v-else class="message-bubble">
                <p>{{ entry.task?.detail || entry.error || taskStates[entry.task?.state] }}</p>
                <p v-if="taskError?.id === entry.id" class="answer-note" role="alert">{{ taskError.message }}</p>
                <button v-if="canRetryTask(entry.task)" class="quiet-action" :disabled="busy || conversation?.archived"
                        @click="updateTask(entry.task, 'retry')">重试回答</button>
                <button v-else-if="entry.error" class="quiet-action" :disabled="busy" @click="answerTemporary(entry.question, entry.id)">重试回答</button>
              </div>
            </div>
          </template>
        </div>

        <p v-if="sendError || error || taskError && active" class="qa-error" role="alert">{{ sendError || error || taskError.message }}</p>
        <form v-if="canAsk" class="chat-form" @submit.prevent="handleSend">
          <textarea ref="questionField" v-model="questionInput" class="chat-input" aria-label="输入问题"
                    placeholder="输入你的问题…" rows="2" maxlength="2000" :disabled="busy" @keydown="handleKeydown" />
          <div class="composer-actions">
            <label v-if="context.kind !== 'temporary'" class="study-check recall-option">
              <input v-model="recall" type="checkbox">参考旧问答
            </label>
            <button class="btn-primary btn-compact" type="submit" :disabled="!questionInput.trim() || busy" aria-label="发送问题">
              <svg v-if="!busy" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
              <svg v-else class="spinner-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/>
              </svg>
              {{ busy ? '处理中…' : '发送' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { askQuestion } from '../api/index.js'
import AnalysisOutline from '../components/AnalysisOutline.vue'
import StudySources from '../components/StudySources.vue'
import { useStudyQuestions } from '../composables/useStudyQuestions.js'
import {
  analysisTaskLink, canRetryTask, conversationLink, isTaskActive, studyChatLink, taskStates, videoAnalysisLink,
} from '../studyUi.js'

const route = useRoute()
const router = useRouter()
const {
  index, context, conversation, history, includeAll, course, lectureId, analysis: analysisData,
  lectureLoading, lectureError, loading, error, active, loadLecture, send, changeTask, removeConversation,
} = useStudyQuestions()

const showAnalysis = ref(false)
const localTurns = ref([])
const questionInput = ref('')
const questionField = ref(null)
const chatMessagesRef = ref(null)
const historyPanel = ref(null)
const recall = ref(true)
const sending = ref(false)
const sendError = ref('')
const taskError = ref(null)
let localTurnId = 0

const scopeLabel = computed(() => ({
  video: '视频问答', temporary: '视频问答 · 临时分析', course: '课程问答', library: '全库问答',
})[context.value?.kind])
const scopeSelection = computed(() => {
  const scope = context.value
  return scope?.id ? scope.kind + ':' + scope.id : scope?.kind ?? ''
})
const analysisLink = computed(() => {
  const id = lectureId.value || (context.value?.kind === 'video' ? context.value.id : null)
  if (id && !conversation.value?.archived) return videoAnalysisLink(id)
  if (context.value?.kind === 'temporary' && route.query.task) return analysisTaskLink(route.query.task)
  return null
})
const canAsk = computed(() => {
  if (!context.value || conversation.value?.archived) return false
  if (context.value.kind === 'course') return Boolean(course.value?.videos.length)
  if (context.value.kind === 'library') return Boolean(index.value.videos.length)
  return Boolean(analysisData.value)
})
const busy = computed(() => sending.value || active.value)
const entries = computed(() => {
  if (context.value?.kind === 'temporary') return localTurns.value
  return [
    ...(conversation.value?.turns ?? []),
    ...(conversation.value?.tasks ?? []).map(task => ({
      id: task.id, question: task.question ?? task.label, created_at: task.created_at, task,
    })),
  ].sort((a, b) => a.created_at - b.created_at)
})
const suggestions = computed(() => {
  if (context.value?.kind === 'course' && course.value?.videos.length > 1) {
    const question = '第 1 讲和第 2 讲的主要内容有什么联系？'
    return [{ label: question, question }]
  }
  return (analysisData.value?.key_points ?? []).slice(0, 3).map(item => ({
    label: item.point,
    question: '能结合视频解释「' + item.point.slice(0, 160) + '」吗？',
  }))
})

watch(context, () => {
  localTurns.value = []
  questionInput.value = ''
  sendError.value = ''
  taskError.value = null
  sending.value = false
  showAnalysis.value = false
  if (historyPanel.value) historyPanel.value.open = false
}, { flush: 'sync' })

const latestEntry = computed(() => entries.value.at(-1))
watch(
  [loading, () => latestEntry.value?.id, () => latestEntry.value?.task?.state, () => latestEntry.value?.answer],
  async () => {
    if (loading.value || route.query.turn) return
    await nextTick()
    const log = chatMessagesRef.value
    if (!log) return
    const answer = latestEntry.value?.answer && log.querySelector('[data-answer-id="' + latestEntry.value.id + '"]')
    if (answer) {
      log.scrollTop += answer.getBoundingClientRect().top - log.getBoundingClientRect().top - 12
    } else {
      log.scrollTop = log.scrollHeight
    }
  },
)

function changeScope(value) {
  if (!value || value === 'temporary' || value === scopeSelection.value) return
  const [scope, id] = value.split(':')
  router.push(studyChatLink(scope, id))
}

function startNewConversation() {
  const { kind, id } = context.value
  const destination = studyChatLink(kind, id)
  router.push({ ...destination, query: { ...destination.query, fresh: '1' } })
}

function fillQuestion(question) {
  questionInput.value = question
  questionField.value?.focus()
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    handleSend()
  }
}

async function handleSend() {
  const question = questionInput.value.trim()
  if (!question || busy.value || !canAsk.value) return
  if (context.value.kind === 'temporary') {
    questionInput.value = ''
    await answerTemporary(question)
    return
  }

  const selected = context.value
  sending.value = true
  sendError.value = ''
  try {
    if (route.query.turn) await router.replace(conversationLink(conversation.value.id))
    await send(question, recall.value)
    if (context.value === selected) questionInput.value = ''
  } catch (err) {
    if (context.value === selected) sendError.value = err.message
  } finally {
    if (context.value === selected) sending.value = false
  }
}

async function answerTemporary(question, retryId) {
  if (busy.value || context.value?.kind !== 'temporary') return
  const selected = context.value
  const data = analysisData.value
  const previous = localTurns.value.filter(turn => turn.answer).slice(-5).flatMap(turn => [
    { role: 'user', content: turn.question }, { role: 'assistant', content: turn.answer },
  ])
  const id = retryId ?? 'temporary-' + ++localTurnId
  if (!retryId) localTurns.value.push({ id, question, pending: true })
  const entry = localTurns.value.find(turn => turn.id === id)
  entry.pending = true
  entry.error = ''
  sending.value = true
  try {
    const subtitles = data.subtitle_text ?? data.subtitle_segments.map(segment => segment.text).join(' ')
    const result = await askQuestion(question, subtitles, analysisSummary(data), previous)
    entry.answer = result.answer
  } catch (err) {
    entry.error = err.message || '问答请求失败，请重试'
  } finally {
    entry.pending = false
    if (context.value === selected) sending.value = false
  }
}

async function updateTask(task, action) {
  const selected = context.value
  sending.value = true
  taskError.value = null
  try {
    await changeTask(task, action)
  } catch (err) {
    if (context.value === selected) taskError.value = { id: task.id, message: err.message }
  } finally {
    if (context.value === selected) sending.value = false
  }
}

async function deleteConversation() {
  const selected = context.value
  sending.value = true
  sendError.value = ''
  try {
    await removeConversation()
  } catch (err) {
    if (context.value === selected) sendError.value = err.message
  } finally {
    if (context.value === selected) sending.value = false
  }
}

function analysisSummary(d) {
  const parts = []

  if (d.overview) {
    parts.push(`【概述】${d.overview}`)
  }

  if (d.outline?.length) {
    const outlineText = d.outline
      .map(o => `• ${o.time ? '[' + o.time + '] ' : ''}${o.topic}${o.detail ? '：' + o.detail : ''}`)
      .join('\n')
    parts.push(`【内容大纲】\n${outlineText}`)
  }

  if (d.key_points?.length) {
    const kpText = d.key_points
      .map((k, i) => `${i + 1}. ${k.point}${k.evidence ? '（原文：' + k.evidence + '）' : ''}`)
      .join('\n')
    parts.push(`【关键要点】\n${kpText}`)
  }

  if (d.conclusions?.length) {
    const conclusions = d.conclusions
      .map((c, i) => `${i + 1}. ${typeof c === 'string' ? c : c.text}`)
      .filter(Boolean)
      .join('\n')
    if (conclusions) parts.push(`【总结】\n${conclusions}`)
  }
  return parts.join('\n\n')
}

function answerTextParts(text) {
  return text.split(/(\*\*[^*\n]+\*\*)/).map((part, index) =>
    index % 2 ? { bold: true, text: part.slice(2, -2) } : { bold: false, text: part })
}

/**
 * 将 AI 回答解析为文本块：
 * - 以 ">" 开头的行 → blockquote
 * - 其他 → 普通段落
 */
function parseMessageBlocks(content) {
  if (!content) return [{ type: 'text', text: '' }]

  const lines = content.split('\n')
  const blocks = []
  let currentBlock = null

  for (const line of lines) {
    const trimmed = line.trim()
    // 检测引用行（以 > 开头，或包含「」标记的原文引用）
    const isQuote = trimmed.startsWith('>')

    if (isQuote) {
      const quoteText = trimmed.replace(/^>\s*/, '')
      if (quoteText) {
        if (currentBlock && currentBlock.type === 'quote') {
          currentBlock.text += '\n' + quoteText
        } else {
          if (currentBlock) blocks.push(currentBlock)
          currentBlock = { type: 'quote', text: quoteText }
        }
      }
    } else if (trimmed) {
      if (currentBlock && currentBlock.type === 'text') {
        currentBlock.text += '\n' + trimmed
      } else {
        if (currentBlock) blocks.push(currentBlock)
        currentBlock = { type: 'text', text: trimmed }
      }
    } else {
      // 空行：结束当前块
      if (currentBlock) {
        blocks.push(currentBlock)
        currentBlock = null
      }
    }
  }
  if (currentBlock) blocks.push(currentBlock)

  return blocks.length > 0 ? blocks : [{ type: 'text', text: content }]
}
</script>

<style scoped>
.qa-page {
  --qa-gap: clamp(10px, 1.2vw, 16px);
  --qa-padding: clamp(12px, 1.5vw, 20px);
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--qa-gap);
  min-width: 0;
  min-height: 0;
  padding-top: var(--qa-gap);
}

.qa-toolbar {
  position: relative;
  z-index: 2;
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 10px 18px;
  padding: 10px var(--qa-padding);
}

.qa-heading {
  display: flex;
  align-items: center;
  gap: clamp(10px, 1.6vw, 22px);
  min-width: 0;
}

.page-title {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 2vw, 1.55rem);
  line-height: 1.3;
  white-space: nowrap;
}

.qa-scope-title {
  min-width: 0;
  padding-inline-start: clamp(10px, 1.6vw, 20px);
  border-inline-start: 1px solid var(--border);
}

.qa-scope-title p,
.lecture-picker label {
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 700;
}

.qa-scope-title h2 {
  overflow: hidden;
  font-size: 0.94rem;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-toolbar-actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.qa-toolbar-actions .btn-compact { white-space: nowrap; }
.qa-toolbar-actions svg, .analysis-toggle svg { flex: none; }
.qa-scope-select { width: clamp(9rem, 20vw, 18rem); min-width: 0; }
.qa-scope-select select, .lecture-picker select {
  display: block;
  min-height: 40px;
  padding: 7px 10px;
  font-size: 0.86rem;
  text-overflow: ellipsis;
}

.qa-history { position: relative; flex: none; }
.qa-history > summary { cursor: pointer; list-style: none; }
.qa-history > summary::-webkit-details-marker { display: none; }

.qa-history-panel {
  position: absolute;
  inset-block-start: calc(100% + 7px);
  inset-inline-end: 0;
  display: grid;
  gap: 8px;
  width: min(22rem, calc(100vw - 2 * var(--app-gutter) - 24px));
  padding: 12px;
  background: var(--bg-primary);
  box-shadow: var(--shadow-md);
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.qa-history-panel ul {
  max-height: min(18rem, 40dvh);
  overflow-y: auto;
  list-style: none;
}

.qa-history-panel a {
  display: block;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  text-decoration: none;
  overflow-wrap: anywhere;
}

.qa-history-panel a:hover, .qa-history-panel a[aria-current] { background: var(--bg-hover); }
.qa-history-panel small { display: block; color: var(--text-secondary); }
.qa-history-panel > .quiet-action { justify-self: start; }

.empty-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: var(--qa-padding);
  color: var(--text-secondary);
}
.empty-title { color: var(--text-primary); font-size: 1.08rem; }
.empty-desc { margin-top: 5px; font-size: 0.88rem; }

.qa-layout {
  display: grid;
  flex: 1;
  grid-template-columns: clamp(236px, 30%, 480px) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: var(--qa-gap);
  min-height: 0;
}

.outline-sidebar, .chat-area {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.outline-header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px 10px;
  min-height: 44px;
  padding: 8px var(--qa-padding);
  border-bottom: 1px solid var(--border);
}
.outline-header h2 { font-size: 0.93rem; }
.outline-links { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; }
.qa-context-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  color: var(--text-secondary);
  font-size: 0.81rem;
  font-weight: 600;
  text-underline-offset: 3px;
}
.qa-context-link:hover { color: var(--text-primary); }

.outline-scroll, .chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.outline-scroll:focus-visible, .chat-messages:focus-visible { outline-offset: -2px; }
.outline-scroll { padding: 12px var(--qa-padding); overflow-wrap: anywhere; }

.lecture-picker { display: grid; gap: 4px; margin-bottom: 12px; }
.outline-video-title {
  margin-bottom: 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 1.02rem;
  line-height: 1.45;
}
.outline-note { color: var(--text-secondary); font-size: 0.86rem; }
.analysis-toggle { display: none; }

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: var(--qa-padding);
}

.chat-message {
  display: flex;
  flex: none;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}
.chat-message.user { align-self: flex-end; flex-direction: row-reverse; max-width: min(78%, 65rem); }
.chat-message.assistant { align-self: stretch; }

.message-avatar {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--bg-card);
  color: var(--text-secondary);
}
.chat-message.user .message-avatar { background: var(--accent); border-color: var(--accent); color: var(--bg-primary); }

.message-bubble {
  min-width: 0;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 0.92rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.chat-message.assistant .message-bubble {
  flex: 1;
  border-top-left-radius: 4px;
  background: var(--bg-hover);
  color: var(--text-primary);
}
.chat-message.user .message-bubble {
  border-top-right-radius: 4px;
  background: var(--accent);
  color: var(--bg-primary);
}
.msg-paragraph + .msg-paragraph { margin-top: 8px; }

.msg-quote {
  margin: 6px 0;
  padding: 3px 10px;
  border-inline-start: 2px solid var(--border-strong);
  color: var(--text-secondary);
  font-size: 0.86rem;
}

.question-suggestions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.question-suggestions button { min-width: 0; max-width: 100%; text-align: left; overflow-wrap: anywhere; }
.answer-note { padding-top: 6px; color: var(--text-secondary); font-size: 0.82rem; }
.answer-sources, .recalled-answers { margin-top: 8px; }
.answer-sources > summary { cursor: pointer; color: var(--text-secondary); font-weight: 700; font-size: 0.84rem; }
.answer-sources[open] > summary { margin-bottom: 6px; }
.answer-sources :deep(.study-evidence) {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr));
}
.recalled-answers h3 { margin-bottom: 3px; font-size: 0.84rem; }
.recalled-answers ul { padding-inline-start: 1.2em; }
.recalled-answers a, .quiet-action { color: var(--text-primary); }
.quiet-action { background: transparent; font-size: 0.85rem; text-decoration: underline; text-underline-offset: 3px; }

.chat-message.assistant .typing-bubble {
  display: flex;
  flex: 0 1 auto;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
}
.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.typing-dot:nth-of-type(3) { animation-delay: 0.15s; }
.typing-dot:nth-of-type(4) { animation-delay: 0.3s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.qa-error {
  flex: none;
  margin: 6px var(--qa-padding);
  padding: 8px 12px;
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
  background: var(--danger-light);
  color: var(--text-primary);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.chat-form {
  display: flex;
  flex: none;
  gap: 10px;
  padding: 10px var(--qa-padding);
  border-top: 1px solid var(--border);
}

.chat-input {
  flex: 1;
  min-width: 0;
  min-height: 50px;
  padding: 8px 12px;
  font-size: 0.95rem;
  line-height: 1.5;
  resize: none;
}

.composer-actions {
  display: flex;
  flex: none;
  flex-direction: column;
  justify-content: flex-end;
  gap: 5px;
  min-width: 98px;
}
.composer-actions .btn-compact { white-space: nowrap; }
.recall-option { justify-content: center; color: var(--text-secondary); font-size: 0.75rem; white-space: nowrap; }

.spinner-svg { animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 767px) {
  .qa-toolbar { flex-direction: column; align-items: stretch; }
  .qa-toolbar-actions { flex-wrap: wrap; }
  .qa-toolbar-actions .btn-compact { padding-inline: 10px; }
  .qa-scope-select { flex: 1 1 7rem; width: auto; }
  .qa-history { position: static; }
  .qa-history-panel { margin-inline-end: 10px; }

  .qa-layout { display: flex; flex-direction: column; }
  .analysis-toggle { display: inline-flex; align-self: flex-start; flex: none; }
  .outline-sidebar { display: none; }
  .outline-sidebar.expanded { display: flex; max-height: min(31dvh, 17rem); }
  .chat-area { flex: 1; }
  .chat-message.user { max-width: 94%; }
  .chat-input { font-size: 1rem; }
}

@media (max-width: 374px) {
  .qa-toolbar-actions { gap: 6px; }
  .qa-toolbar-actions .btn-compact { padding-inline: 8px; }
  .message-bubble { padding: 9px 10px; }
  .chat-form { gap: 8px; }
  .composer-actions { min-width: 82px; }
}
</style>
