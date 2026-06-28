<template>
  <div class="qa-page">
    <header class="page-header">
      <h1 class="page-title">AI 问答</h1>
      <p class="page-desc">基于已分析的视频内容，向 AI 提问深度理解</p>
    </header>

    <!-- 思考火柴人动画 -->
    <div v-if="analysisData" class="thinking-figure" aria-hidden="true">
      <svg width="60" height="72" viewBox="0 0 60 72" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <!-- 身体 -->
        <circle cx="30" cy="16" r="8" class="fig-head"/>
        <line x1="30" y1="24" x2="30" y2="44" class="fig-body"/>
        <!-- 手臂（思考姿态：一手托腮） -->
        <line x1="30" y1="30" x2="14" y2="24" class="fig-arm-l"/>
        <line x1="30" y1="30" x2="42" y2="18" class="fig-arm-r-thinking"/>
        <!-- 腿 -->
        <line x1="30" y1="44" x2="20" y2="66" class="fig-leg-l"/>
        <line x1="30" y1="44" x2="40" y2="66" class="fig-leg-r"/>
        <!-- 问号气泡 -->
        <g class="question-bubble">
          <circle cx="50" cy="10" r="8" fill="none"/>
          <text x="50" y="14" text-anchor="middle" font-size="12" font-weight="700" fill="currentColor" stroke="none">?</text>
        </g>
      </svg>
    </div>

    <!-- 空状态：无分析数据 -->
    <div v-if="!analysisData" class="empty-state card">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" opacity="0.25">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <p class="empty-title">还没有分析数据</p>
      <p class="empty-desc">请先在 AI解析 页面分析一个视频，然后再来提问。</p>
      <router-link to="/analyze" class="btn-primary empty-cta">
        前往 AI解析
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
        </svg>
      </router-link>
    </div>

    <!-- 主布局：左侧大纲 + 右侧对话 -->
    <div v-else class="qa-layout">
      <!-- 左侧：内容大纲 -->
      <aside class="outline-sidebar card">
        <div class="outline-header">
          <h2 class="outline-video-title">{{ analysisData.title || '视频分析' }}</h2>
        </div>

        <div class="outline-sections">
          <!-- 概述 -->
          <div class="outline-section" :class="{ open: openSections.overview }">
            <button class="outline-toggle" @click="openSections.overview = !openSections.overview">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.overview }">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span>概述</span>
            </button>
            <Transition name="collapse">
              <p v-if="openSections.overview" class="outline-content">{{ analysisData.overview }}</p>
            </Transition>
          </div>

          <!-- 大纲 -->
          <div class="outline-section" :class="{ open: openSections.outline }">
            <button class="outline-toggle" @click="openSections.outline = !openSections.outline">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.outline }">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span>大纲</span>
              <span class="outline-count">{{ analysisData.outline?.length || 0 }} 段</span>
            </button>
            <Transition name="collapse">
              <ul v-if="openSections.outline" class="outline-list">
                <li v-for="(item, i) in analysisData.outline" :key="i" class="outline-item">
                  <span v-if="item.time" class="outline-time">{{ item.time }}</span>
                  <span class="outline-topic">{{ item.topic }}</span>
                  <p v-if="item.detail" class="outline-detail">{{ item.detail }}</p>
                </li>
              </ul>
            </Transition>
          </div>

          <!-- 关键要点 -->
          <div class="outline-section" :class="{ open: openSections.keyPoints }">
            <button class="outline-toggle" @click="openSections.keyPoints = !openSections.keyPoints">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.keyPoints }">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span>关键要点</span>
              <span class="outline-count">{{ analysisData.key_points?.length || 0 }} 条</span>
            </button>
            <Transition name="collapse">
              <ul v-if="openSections.keyPoints" class="keypoints-list">
                <li v-for="(item, i) in analysisData.key_points" :key="i" class="keypoint-item">
                  <p class="keypoint-text">{{ item.point }}</p>
                  <blockquote v-if="item.evidence" class="keypoint-evidence">{{ item.evidence }}</blockquote>
                </li>
              </ul>
            </Transition>
          </div>

          <!-- 总结 -->
          <div class="outline-section" :class="{ open: openSections.conclusions }">
            <button class="outline-toggle" @click="openSections.conclusions = !openSections.conclusions">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="toggle-arrow" :class="{ rotated: openSections.conclusions }">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span>总结</span>
              <span class="outline-count">{{ analysisData.conclusions?.length || 0 }} 条</span>
            </button>
            <Transition name="collapse">
              <ol v-if="openSections.conclusions" class="conclusions-list">
                <li v-for="(item, i) in analysisData.conclusions" :key="i" class="conclusion-item">
                  {{ typeof item === 'string' ? item : item.text }}
                </li>
              </ol>
            </Transition>
          </div>
        </div>
      </aside>

      <!-- 右侧：对话区 -->
      <div class="chat-area card">
        <!-- 消息列表 -->
        <div class="chat-messages" ref="chatMessagesRef">
          <!-- 初始提示 -->
          <div class="chat-message assistant">
            <div class="message-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/>
              </svg>
            </div>
            <div class="message-bubble">
              <p>你好！我已阅读了视频的字幕内容和分析结果，有什么想问的吗？可以基于左侧的大纲找到你感兴趣的部分进行提问。</p>
            </div>
          </div>

          <!-- 对话消息 -->
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="chat-message"
            :class="msg.role"
          >
            <div class="message-avatar">
              <template v-if="msg.role === 'user'">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
              </template>
              <template v-else>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/>
                </svg>
              </template>
            </div>
            <div class="message-bubble">
              <!-- 渲染回答中的 markdown 片段（blockquote + 段落） -->
              <template v-for="(block, bi) in parseMessageBlocks(msg.content)" :key="bi">
                <blockquote v-if="block.type === 'quote'" class="msg-quote">{{ block.text }}</blockquote>
                <p v-else class="msg-paragraph">{{ block.text }}</p>
              </template>
            </div>
          </div>

          <!-- 打字动画 -->
          <div v-if="loading" class="chat-message assistant">
            <div class="message-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a10 10 0 1 0 10 10H12V2z"/><circle cx="8" cy="8" r="2"/><path d="M4 16l4-4 3 3 4-4 5 5"/>
              </svg>
            </div>
            <div class="message-bubble typing-bubble">
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            </div>
          </div>
        </div>

        <!-- 错误提示 -->
        <Transition name="fade">
          <div v-if="errorMsg" class="qa-error" role="alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ errorMsg }}</span>
            <button class="error-dismiss" aria-label="关闭错误" @click="errorMsg = ''">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </Transition>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <textarea
            v-model="questionInput"
            class="chat-input"
            placeholder="输入你的问题..."
            rows="2"
            :disabled="loading"
            @keydown="handleKeydown"
          ></textarea>
          <button
            class="btn-send"
            :disabled="!questionInput.trim() || loading"
            @click="handleSend"
            aria-label="发送问题"
          >
            <svg v-if="!loading" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
            <svg v-else class="spinner-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { askQuestion } from '../api/index.js'

// 分析数据
const analysisData = ref(null)

// 大纲折叠状态
const openSections = reactive({
  overview: true,
  outline: true,
  keyPoints: false,
  conclusions: false,
})

// 对话状态
const messages = ref([])
const questionInput = ref('')
const loading = ref(false)
const errorMsg = ref('')
const chatMessagesRef = ref(null)

// 从 localStorage 加载分析数据
onMounted(() => {
  try {
    const stored = localStorage.getItem('lastAnalysisResult')
    if (stored) {
      const data = JSON.parse(stored)
      // 检查数据是否有效且不超过 24 小时
      if (data.subtitle_text && data.title) {
        analysisData.value = data
      }
    }
  } catch (e) {
    // 数据损坏，忽略
  }
})

// Enter 发送，Shift+Enter 换行
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// 发送问题
async function handleSend() {
  const question = questionInput.value.trim()
  if (!question || loading.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: question })
  questionInput.value = ''
  errorMsg.value = ''
  loading.value = true

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 构建分析摘要 — 传递完整的四维度分析结果，给 AI 更丰富的上下文
  let summary = ''
  if (analysisData.value) {
    const d = analysisData.value
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

    summary = parts.join('\n\n')
  }

  try {
    const result = await askQuestion(
      question,
      analysisData.value.subtitle_text,
      summary
    )
    messages.value.push({ role: 'assistant', content: result.answer })
  } catch (err) {
    errorMsg.value = err.message || '问答请求失败，请重试'
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  const el = chatMessagesRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
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
  padding-top: 32px;
}

.page-header {
  text-align: center;
  margin-bottom: 20px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.page-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
}

/* ===== 思考火柴人 ===== */
.thinking-figure {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
  color: var(--text-muted);
  opacity: 0.4;
}

.fig-head {
  animation: headBob 2s ease-in-out infinite;
}

.fig-arm-r-thinking {
  animation: armThink 2.5s ease-in-out infinite;
  transform-origin: 30px 30px;
}

.question-bubble {
  animation: bubbleFloat 2s ease-in-out infinite;
  transform-origin: 50px 10px;
}

@keyframes headBob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

@keyframes armThink {
  0%, 100% { transform: rotate(0deg); }
  30% { transform: rotate(-8deg); }
  60% { transform: rotate(3deg); }
}

@keyframes bubbleFloat {
  0%, 100% { transform: translateY(0); opacity: 0.6; }
  50% { transform: translateY(-4px); opacity: 1; }
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 24px;
  text-align: center;
  max-width: 420px;
  margin: 20px auto 0;
}

.empty-title {
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.empty-desc {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 12px;
}

.empty-cta {
  text-decoration: none;
  padding: 12px 28px;
}

/* ===== 双栏布局 ===== */
.qa-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  align-items: start;
  margin-top: 4px;
}

/* ===== 左侧大纲 ===== */
.outline-sidebar {
  max-height: calc(100dvh - 200px);
  overflow-y: auto;
  padding: 18px;
  position: sticky;
  top: 72px;
}

.outline-header {
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.outline-video-title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.outline-sections {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.outline-section {
  border-radius: var(--radius-sm);
}

.outline-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 0.85rem;
  text-align: left;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast);
}

.outline-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.outline-section.open .outline-toggle {
  color: var(--text-primary);
}

.toggle-arrow {
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-out);
  color: var(--text-muted);
}

.toggle-arrow.rotated {
  transform: rotate(90deg);
}

.outline-count {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
}

.outline-content {
  padding: 4px 10px 10px 28px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.outline-list {
  list-style: none;
  padding: 2px 6px 8px 28px;
}

.outline-item {
  padding: 6px 4px;
  border-left: 2px solid var(--border);
  margin-bottom: 2px;
}

.outline-item:last-child {
  border-left-color: transparent;
}

.outline-time {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: 3px;
  margin-bottom: 2px;
}

.outline-topic {
  display: block;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 2px;
}

.outline-detail {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 2px;
  line-height: 1.5;
}

.keypoints-list {
  list-style: none;
  padding: 2px 6px 8px 28px;
}

.keypoint-item {
  padding: 6px 4px;
  border-bottom: 1px solid var(--border);
}

.keypoint-item:last-child {
  border-bottom: none;
}

.keypoint-text {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.5;
}

.keypoint-evidence {
  font-size: 0.76rem;
  color: var(--text-muted);
  border-left: 2px solid var(--border-strong);
  padding: 2px 8px;
  margin-top: 4px;
  line-height: 1.5;
  font-style: italic;
}

.conclusions-list {
  padding: 4px 8px 10px 36px;
}

.conclusion-item {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 2px 0;
}

/* collapse transition */
.collapse-enter-active,
.collapse-leave-active {
  transition: all var(--duration-normal) var(--ease-out);
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 600px;
}

/* ===== 右侧对话区 ===== */
.chat-area {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 200px);
  min-height: 400px;
  padding: 0;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 20px 8px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-message {
  display: flex;
  gap: 10px;
  max-width: 90%;
}

.chat-message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-message.assistant {
  align-self: flex-start;
}

.message-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.chat-message.user .message-avatar {
  background: var(--accent);
  color: var(--bg-primary);
  border-color: var(--accent);
}

.message-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  line-height: 1.6;
  font-size: 0.88rem;
}

.chat-message.assistant .message-bubble {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-top-left-radius: 4px;
}

.chat-message.user .message-bubble {
  background: var(--accent);
  color: var(--bg-primary);
  border-top-right-radius: 4px;
}

.msg-paragraph {
  margin: 0;
  line-height: 1.7;
}

.msg-paragraph + .msg-paragraph {
  margin-top: 8px;
}

.msg-quote {
  margin: 6px 0;
  padding: 4px 10px;
  border-left: 2px solid var(--border-strong);
  color: var(--text-secondary);
  font-style: italic;
  font-size: 0.84rem;
  line-height: 1.6;
}

.chat-message.user .msg-quote {
  border-left-color: rgba(255,255,255,0.3);
  color: rgba(255,255,255,0.8);
}

/* 打字动画 */
.typing-bubble {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
  min-width: 48px;
}

.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typingBounce 1.2s ease-in-out infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* 错误 */
.qa-error {
  margin: 8px 20px;
  padding: 10px 14px;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
}

.error-dismiss {
  margin-left: auto;
  background: none;
  color: var(--text-muted);
  padding: 2px;
  border-radius: 4px;
  display: flex;
}

.error-dismiss:hover {
  color: var(--text-primary);
}

/* 输入区 */
.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-card);
}

.chat-input {
  flex: 1;
  font-size: 0.9rem;
  padding: 10px 14px;
  min-height: 44px;
  max-height: 120px;
  resize: none;
  border-radius: var(--radius-sm);
  line-height: 1.5;
}

.btn-send {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--bg-primary);
  flex-shrink: 0;
  box-shadow: 0 2px 8px var(--accent-glow);
  transition: all var(--duration-fast) var(--ease-out);
}

.btn-send:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 4px 14px var(--accent-glow);
  transform: translateY(-1px);
}

.btn-send:active:not(:disabled) {
  transform: translateY(0) scale(0.96);
}

.btn-send:disabled {
  opacity: 0.3;
  box-shadow: none;
}

.spinner-svg {
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 响应式 ===== */
@media (max-width: 767px) {
  .qa-page {
    padding-top: 24px;
  }

  .page-title {
    font-size: 1.4rem;
  }

  .page-desc {
    font-size: 0.88rem;
  }

  .qa-layout {
    grid-template-columns: 1fr;
  }

  .outline-sidebar {
    position: static;
    max-height: none;
  }

  .chat-area {
    height: calc(100dvh - 360px);
    min-height: 320px;
  }

  .chat-message {
    max-width: 95%;
  }
}

@media (max-width: 374px) {
  .chat-messages {
    padding: 14px 12px 6px;
    gap: 10px;
  }

  .chat-input-area {
    padding: 10px 12px;
    gap: 8px;
  }

  .message-bubble {
    padding: 10px 12px;
    font-size: 0.82rem;
  }
}
</style>
