<template>
  <div class="analysis-page">
    <header class="page-header">
      <h1 class="page-title">AI 视频解析</h1>
      <p class="page-desc">粘贴视频链接，AI 自动分析字幕内容，生成结构化摘要</p>
    </header>

    <YouTubeNetworkDialog
      v-if="networkIssue"
      :message="networkIssue.message"
      @dismiss="networkIssue = null"
      @retry="retryYouTubeNetwork"
    />

    <!-- 链接输入区 -->
    <div class="input-section card">
      <label for="url-input" class="input-label">视频链接</label>
      <div class="input-row">
        <input
          id="url-input"
          v-model="urlInput"
          type="text"
          placeholder="粘贴 YouTube、B站或理大 Panopto 录像链接"
          class="url-input"
          @keyup.enter="handleParse()"
        />
        <button
          class="btn-primary parse-btn"
          :disabled="!urlInput.trim() || parsing || (analyzing && !abortAnalysis)"
          @click="handleParse()"
        >
          <svg v-if="parsing" class="spinner-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
            <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/>
          </svg>
          <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4 4"/>
          </svg>
          {{ parsing ? '解析中…' : '解析视频' }}
        </button>
      </div>
      <div v-if="studyAvailable || (inputSite && !sessionGuide)" class="input-tools">
        <details v-if="studyAvailable" ref="recentPanel" class="recent-analysis" @toggle="toggleRecent">
          <summary class="utility-action">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 2"/>
            </svg>
            最近解析
            <svg class="disclosure-icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="m6 9 6 6 6-6"/>
            </svg>
          </summary>
          <p v-if="recentError" class="platform-note" role="alert">{{ recentError }}</p>
          <template v-if="recent.length">
            <div class="recent-analysis-tools">
              <button class="study-quiet" type="button" :aria-pressed="manageRecent" @click="manageRecent = !manageRecent">
                {{ manageRecent ? '完成' : '管理' }}
              </button>
            </div>
            <ul class="recent-analysis-list">
              <li v-for="item in recent" :key="item.id">
                <RouterLink :to="analysisTaskLink(item.id)" :aria-current="taskId === item.id ? 'true' : undefined">
                  <span>{{ item.label }}</span>
                  <small>{{ taskStates[item.state] }}</small>
                </RouterLink>
                <button v-if="manageRecent" class="study-quiet" type="button" :disabled="taskBusy"
                        :aria-label="'删除解析记录 · ' + item.label" @click="chooseRecent(item)">删除</button>
              </li>
            </ul>
          </template>
          <p v-else-if="loadingRecent" class="platform-note" role="status">正在读取解析记录…</p>
          <p v-else-if="!recentError" class="platform-note">解析过的视频会出现在这里。</p>
        </details>
        <div v-if="inputSite && !sessionGuide" class="input-session">
          <details v-if="inputSite.platform === 'bilibili' && getSession(inputSite)" class="session-details">
            <summary class="utility-action">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v2"/>
              </svg>
              B站会话 · 已填写
            </summary>
            <div class="session-options">
              <button class="session-action" type="button" :disabled="parsing" @click="openInputSession">更换会话</button>
              <button class="session-action" type="button" @click="clearSession(inputSite)">清除会话</button>
            </div>
          </details>
          <template v-else-if="getSession(inputSite)">
            <span>{{ inputSite.label }} 会话已填写</span>
            <button class="session-action" type="button" @click="clearSession(inputSite)">清除会话</button>
          </template>
          <button v-else class="utility-action" type="button" :disabled="parsing" @click="openInputSession">
            连接 {{ inputSite.label }} 会话
          </button>
        </div>
      </div>
    </div>

    <StudyManagementDialog v-if="deletingRecent" title="删除解析记录" :busy="removingRecent" @close="deletingRecent = null">
      <div class="study-editor">
        <p>删除「{{ deletingRecent.label }}」的解析记录？</p>
        <p v-if="isTaskActive(deletingRecent)" class="study-muted">仍在执行的分析会停止。</p>
        <p v-if="deletingRecent.persistent && deletingRecent.state === 'done'" class="study-muted">
          已保存的视频和解析结果仍可在资料库查看。
        </p>
        <p v-else-if="!deletingRecent.persistent && deletingRecent.state === 'done'" class="study-muted">
          这次的临时解析结果和问答入口会失效。
        </p>
        <p v-if="removeRecentError" class="study-notice" role="alert">{{ removeRecentError }}</p>
        <div class="study-actions">
          <button class="btn-secondary btn-compact" type="button" :disabled="removingRecent" @click="deletingRecent = null">取消</button>
          <button class="btn-primary btn-compact" type="button" :disabled="removingRecent" @click="confirmRecentRemoval">确认删除记录</button>
        </div>
      </div>
    </StudyManagementDialog>

    <VideoSessionGuide
      v-if="sessionGuide"
      :key="sessionGuide.url"
      :site="sessionGuide.site"
      :message="sessionGuide.message"
      :submit-label="sessionGuide.submitLabel"
      @connect="connectSession"
      @dismiss="sessionGuide = null"
    />

    <!-- 视频加载骨架屏 -->
    <div v-if="parsing" class="skeleton-card card" aria-hidden="true">
      <div class="skeleton skeleton-thumb"></div>
      <div>
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text"></div>
      </div>
    </div>

    <!-- 解析错误 -->
    <Transition name="fade">
      <div v-if="errorMsg && !sessionGuide" class="error-banner" role="alert">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="error-text">{{ errorMsg }}</span>
        <button class="error-close" aria-label="关闭错误提示" @click="errorMsg = ''">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </Transition>

    <!-- 视频信息 + 分析 + 下载 -->
    <Transition name="slide-fade">
      <div v-if="previewVideo || taskId || videoId" class="result-area">
        <section v-if="previewVideo" class="video-preview card" aria-label="当前视频">
          <VideoInfo :key="previewVideo.source_url" :info="previewVideo" />
          <div v-if="canStartAnalysis || canDownload" class="video-actions">
            <div v-if="canStartAnalysis" class="video-primary-actions">
              <button class="btn-primary btn-compact" type="button" :disabled="analyzing" @click="handleAnalyze">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15v5m-2.5-2.5h5"/>
                </svg>
                {{ analyzing ? '提交分析中…' : '开始分析' }}
              </button>
              <AIProviderSelect v-model="provider" :disabled="analyzing" />
              <label v-if="canArchive" class="study-check save-option">
                <input v-model="saveToLibrary" type="checkbox" :disabled="analyzing">
                保存到资料库
              </label>
            </div>
            <DownloadSection
              v-if="canDownload"
              :key="parsedVideoUrl"
              :formats="previewVideo.formats"
              :url="parsedVideoUrl"
              :credentials="credentialsFor(parsedVideoUrl)"
              @error="handleDownloadError"
            />
          </div>
          <p v-if="canStartAnalysis && studyAvailable && !canArchive" class="platform-note">
            此链接支持即时分析，结果在当前问答中使用。
          </p>
          <p v-if="canStartAnalysis && privateSource" class="platform-note">
            开始分析时，视频字幕会发送给 AI。<template v-if="canArchive && saveToLibrary">保存后可加入课程，整理 Wiki 和问答时会向 AI 发送用到的字幕片段。</template>
          </p>
          <p v-if="previewVideo.has_captions === false" class="platform-note">该录像没有可用字幕，暂时无法生成摘要和问答。</p>
          <p v-if="previewVideo.youtube_connection" class="platform-note" role="status">
            {{ previewVideo.youtube_connection === 'proxy' ? 'YouTube 已通过代理连通' : 'YouTube 网络已连通' }}
          </p>
          <p v-if="previewVideo.platform === 'panopto' && !previewVideo.formats?.length" class="platform-note">此录像未提供官方下载。</p>
        </section>
        <p v-if="loading" class="card" role="status">正在读取视频解析…</p>
        <div v-if="loadError" class="error-banner" role="alert">
          <span class="error-text">{{ loadError }}</span>
          <button class="btn-retry" type="button" @click="readSelection">重新读取</button>
        </div>

        <!-- 分析错误 -->
        <Transition name="fade">
          <div v-if="analysisError" class="error-banner" role="alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="error-text">{{ analysisError }}</span>
            <button class="error-close" aria-label="关闭错误提示" @click="analysisError = ''">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </Transition>

        <!-- 后台分析留在当前视频下方，刷新后从同一地址恢复 -->
        <section v-if="task && !visibleResult" class="progress-area card" aria-labelledby="queued-analysis-title">
          <div class="analysis-record-header">
            <div>
              <h2 id="queued-analysis-title">{{ task.label }}</h2>
              <p class="platform-note" role="status">
                {{ taskStates[task.state] }}<span v-if="task.state === 'running' && taskPhases[task.phase]"> · {{ taskPhases[task.phase] }}</span>
              </p>
            </div>
            <div class="analysis-actions">
              <button v-if="canRetryTask(task)" class="btn-secondary btn-compact" :disabled="taskBusy"
                      @click="retryAnalysisTask()">{{ retryAnalysisLabel }}</button>
              <button v-if="isTaskActive(task) || ['needs_input', 'needs_retry'].includes(task.state)"
                      class="btn-secondary btn-compact" :disabled="taskBusy" @click="cancelAnalysisTask">取消分析</button>
            </div>
          </div>
          <p v-if="task.detail" class="platform-note" :role="canRetryTask(task) ? 'alert' : undefined">{{ task.detail }}</p>
          <p v-else-if="isTaskActive(task)" class="platform-note">离开页面后，分析会继续。可以在「最近解析」找回进度。</p>
          <label v-if="needsRetryConsent" class="study-check retry-consent">
            <input v-model="retryConsent" type="checkbox">保存此登录视频，并允许整理和问答时处理相关字幕
          </label>
        </section>

        <!-- 兼容即时分析的流式进度 -->
        <Transition name="slide-fade">
          <div v-if="!taskId && !videoId && progressSteps.length > 0 && !visibleResult" class="progress-area card">
            <div class="progress-header">
              <span>{{ progressStatusText }}</span>
              <button v-if="showRetryButton" class="btn-retry" @click="handleImmediateAnalyze">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                重新分析
              </button>
              <button v-if="!analyzing" class="btn-close-progress" aria-label="关闭进度面板" @click="dismissProgress">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div class="progress-steps">
              <div
                v-for="s in progressSteps"
                :key="s.step"
                class="progress-step"
                :class="'step-' + s.status"
              >
                <span class="step-dot" :aria-label="s.status">
                  <template v-if="s.status === 'processing'">
                    <svg class="spinner-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/></svg>
                  </template>
                  <template v-else-if="s.status === 'done'">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  </template>
                  <template v-else-if="s.status === 'failed'">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  </template>
                  <template v-else>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>
                  </template>
                </span>
                <span class="step-label">{{ progressLabels[s.step] || s.step }}</span>
                <span class="step-message" v-if="s.message">— {{ s.message }}</span>
              </div>
            </div>
          </div>
        </Transition>

        <!-- 分析结果 -->
        <section v-if="visibleResult" class="analysis-output" aria-labelledby="analysis-output-title">
          <div class="analysis-record-header card">
            <div>
              <h2 id="analysis-output-title">{{ previewVideo ? '分析结果' : visibleResult.title }}</h2>
              <p class="platform-note">
                {{ resultRecord?.id ? '已保存到资料库' : taskId ? '临时结果 · 完成后保留 1 小时' : '分析完成' }}
                <template v-if="resultRecord"> · {{ platforms[resultRecord.platform] }} · {{ timecode(resultRecord.duration) }}</template>
              </p>
            </div>
            <div class="analysis-actions">
              <a v-if="resultRecord?.id" :href="resultRecord.url" target="_blank" rel="noopener noreferrer"
                 class="btn-secondary btn-compact">打开原视频 ↗</a>
              <RouterLink :to="questionLink" class="btn-primary btn-compact">去问答
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M5 12h14m-7-7 7 7-7 7"/>
                </svg>
              </RouterLink>
            </div>
          </div>
          <AnalysisResult :key="taskId || videoId || parsedVideoUrl" :result="visibleResult" />
        </section>

      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { parseVideo, startAnalysis } from '../api/index.js'
import { studyApi, studyRequestId } from '../api/study.js'
import { useAIProvider } from '../composables/useAIProvider.js'
import { useAnalysisRecords } from '../composables/useAnalysisRecords.js'
import {
  analysisContent, analysisTaskLink, canRetryTask, confirmTaskRetry, isTaskActive,
  platforms, restoreImmediateResult, setImmediateResult, studyChatLink, taskPhases, taskStates, timecode, videoAnalysisLink,
} from '../studyUi.js'
import { sessionSiteFor, useVideoSessions } from '../videoSessions.js'
import VideoInfo from '../components/VideoInfo.vue'
import AIProviderSelect from '../components/AIProviderSelect.vue'
import AnalysisResult from '../components/AnalysisResult.vue'
import DownloadSection from '../components/DownloadSection.vue'
import StudyManagementDialog from '../components/StudyManagementDialog.vue'
import YouTubeNetworkDialog from '../components/YouTubeNetworkDialog.vue'
import VideoSessionGuide from '../components/VideoSessionGuide.vue'

const urlInput = ref('')
const route = useRoute()
const router = useRouter()
const provider = useAIProvider()
const {
  taskId, videoId, task, video, loading, loadError, readSelection,
  recent, loadingRecent, recentError, loadRecent, removeRecent,
} = useAnalysisRecords()
const recentPanel = ref(null)
const manageRecent = ref(false)
const deletingRecent = ref(null)
const removingRecent = ref(false)
const removeRecentError = ref('')
const parsing = ref(false)
const videoInfo = ref(null)
const parsedInput = ref('')
const parsedVideoUrl = computed(() => parsedInput.value === urlInput.value.trim()
  ? videoInfo.value?.source_url || videoInfo.value?.webpage_url
  : undefined)
const errorMsg = ref('')
const networkIssue = ref(null)
const sessionGuide = ref(null)
const { getSession, connectSession: rememberSession, clearSession, restoreLegacyBilibiliSession } = useVideoSessions()
const inputSite = computed(() => sessionSiteFor(urlInput.value))
const studyAvailable = ref(false)
const saveToLibrary = ref(true)
const canArchive = computed(() => studyAvailable.value && videoInfo.value?.archive_supported !== false)
const privateParsed = ref(false)
const privateSource = computed(() =>
  privateParsed.value || inputSite.value?.platform === 'panopto' || Boolean(credentialsFor(parsedVideoUrl.value)))

// AI 分析状态
const analyzing = ref(false)
const analysisResult = ref(null)
const immediateId = ref('')
const analysisError = ref('')
const progressSteps = reactive([])
const submittedTaskId = ref('')
const taskBusy = ref(false)
const retryConsent = ref(false)
let abortAnalysis = null
let studyAttempt = null
let bilibiliAttempt = null
const resultRecord = computed(() => task.value?.result ?? video.value)
const visibleResult = computed(() => taskId.value || videoId.value ? analysisContent(resultRecord.value) : analysisResult.value)
const previewVideo = computed(() => {
  if (videoId.value) return null
  if (taskId.value) return submittedTaskId.value === taskId.value ? videoInfo.value : null
  return parsedVideoUrl.value ? videoInfo.value : null
})
const canStartAnalysis = computed(() =>
  previewVideo.value && !taskId.value && !videoId.value &&
  previewVideo.value.has_captions !== false && !analysisResult.value && !progressSteps.length)
const canDownload = computed(() => Boolean(parsedVideoUrl.value && previewVideo.value?.formats?.length))
const questionLink = computed(() => {
  if (resultRecord.value?.id) return studyChatLink('video', resultRecord.value.id)
  return { name: 'qa', query: taskId.value ? { task: taskId.value } : { temporary: immediateId.value } }
})
const needsRetryConsent = computed(() =>
  task.value?.state === 'needs_input' && task.value.persistent && !task.value.target.private)
const retryAnalysisLabel = computed(() => {
  if (task.value?.state !== 'needs_input' || !task.value.target.requires_session) return '重新分析'
  return credentialsFor(task.value.target.url) ? '用当前会话重试' : '填写会话'
})

function toggleRecent(event) {
  if (event.target.open) loadRecent()
  else manageRecent.value = false
}

function chooseRecent(item) {
  deletingRecent.value = item.id === taskId.value && task.value ? task.value : item
  removeRecentError.value = ''
}

async function confirmRecentRemoval() {
  if (!deletingRecent.value || removingRecent.value) return
  const id = deletingRecent.value.id
  removingRecent.value = true
  removeRecentError.value = ''
  try {
    await removeRecent(id)
    if (taskId.value === id) {
      const archivedId = task.value?.result?.id
      await router.replace(archivedId ? videoAnalysisLink(archivedId) : { name: 'analyze' })
    }
    deletingRecent.value = null
  } catch (error) {
    removeRecentError.value = error.message
  } finally {
    removingRecent.value = false
  }
}

// 状态持久化 — 页面切换后恢复已解析的视频和 AI 分析结果
const STATE_KEY = 'analysisPageState'

// 页面挂载时恢复之前的分析状态
onMounted(() => {
  try {
    const saved = localStorage.getItem(STATE_KEY)
    if (saved) {
      const { cookies, ...state } = JSON.parse(saved)
      if (state.urlInput) urlInput.value = state.urlInput
      if (state.videoInfo) videoInfo.value = state.videoInfo
      parsedInput.value = state.parsedInput || state.videoInfo?.source_url || state.videoInfo?.webpage_url || ''
      if (state.analysisResult && parsedVideoUrl.value) {
        analysisResult.value = state.analysisResult
        immediateId.value = cookies || privateSource.value
          ? setImmediateResult(state.analysisResult)
          : restoreImmediateResult(state.analysisResult, state.immediateId)
      }
      if (typeof cookies === 'string' && cookies) {
        restoreLegacyBilibiliSession(cookies)
        // 迁移时直接清除已存在的凭证副本，避免被私密资料的保存检查跳过。
        localStorage.setItem(STATE_KEY, JSON.stringify(state))
      }
    }
  } catch (e) { /* 数据损坏，忽略 */ }
  studyApi.status().then(() => { studyAvailable.value = true }).catch(() => {})
})

// 自动保存状态变化
watch([urlInput, videoInfo, analysisResult, immediateId], saveAnalysisState, { deep: true })
watch(() => urlInput.value.trim(), () => { sessionGuide.value = null })

function saveAnalysisState() {
  if (privateSource.value || credentialsFor(urlInput.value)) return
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({
      urlInput: urlInput.value,
      parsedInput: parsedInput.value,
      videoInfo: videoInfo.value,
      analysisResult: analysisResult.value,
      immediateId: immediateId.value,
    }))
  } catch (e) { /* localStorage 可能满了 */ }
}

watch([parsedVideoUrl, privateSource], ([url, privateVideo]) => {
  saveToLibrary.value = Boolean(url) && !privateVideo
})

watch([taskId, videoId], () => {
  retryConsent.value = false
  analysisError.value = ''
  sessionGuide.value = null
  networkIssue.value = null
  if (taskId.value || videoId.value) {
    if (abortAnalysis) {
      abortAnalysis.abort()
      abortAnalysis = null
      analyzing.value = false
    }
    progressSteps.length = 0
  }
})

const progressLabels = {
  parse: '获取视频信息',
  subtitles: '提取字幕',
  analyze: 'AI 分析',
  error: '出错',
}

const progressStatusText = computed(() => {
  if (analyzing.value) return 'AI 分析进行中...'
  return progressSteps.every(s => s.status === 'done') ? 'AI 分析完成' : 'AI 分析未完成'
})

const showRetryButton = computed(() => {
  if (analyzing.value) return false
  const allDone = progressSteps.length > 0 && progressSteps.every(s => s.status === 'done')
  return !allDone
})

function credentialsFor(url) {
  return getSession(sessionSiteFor(url))
}

function openInputSession() {
  const url = urlInput.value.trim()
  const site = inputSite.value
  sessionGuide.value = getSession(site)
    ? { site, url, submitLabel: '更新会话' }
    : { site, url, submitLabel: '连接会话并解析', retry: () => handleParse(url) }
}

function requireBilibiliSession(url, submitLabel, retry) {
  const site = sessionSiteFor(url)
  if (site?.platform !== 'bilibili' || getSession(site)) return false
  sessionGuide.value = {
    site, url, submitLabel, retry,
    message: '请先填写 B 站的 SESSDATA 会话值。',
  }
  return true
}

function handleVideoError({ code, message }, url, retry, credentials) {
  if (code === 'youtube_network_unavailable' || code === 'youtube_proxy_unavailable') {
    networkIssue.value = { message, retry }
    return
  }
  const site = sessionSiteFor(url)
  if (!site || (code !== site.platform + '_login_required' && code !== site.platform + '_session_rejected')) return
  // 旧请求拒绝的会话可能已经被用户替换。
  if (credentials !== getSession(site)) return

  clearSession(site)
  sessionGuide.value = { site, url, message, retry, submitLabel: retry ? '连接会话并重试' : undefined }
}

function handleDownloadError(error, url, credentials, retry) {
  handleVideoError(error, url, error.code?.startsWith('youtube_') ? retry : null, credentials)
}

async function connectSession(value) {
  const { site, retry } = sessionGuide.value
  rememberSession(site, value)
  sessionGuide.value = null
  if (retry) {
    // 先让登录视频的保存选项更新，再提交后台分析。
    await nextTick()
    retry()
  }
}

function retryYouTubeNetwork() {
  const retry = networkIssue.value?.retry
  networkIssue.value = null
  retry?.()
}

async function handleParse(url = urlInput.value.trim()) {
  if (!url || url !== urlInput.value.trim() || parsing.value || (analyzing.value && !abortAnalysis)) return
  if (requireBilibiliSession(url, '连接会话并解析', () => handleParse(url))) return

  abortAnalysis?.abort()
  abortAnalysis = null
  submittedTaskId.value = ''
  analyzing.value = false
  parsing.value = true
  errorMsg.value = ''
  networkIssue.value = null
  sessionGuide.value = null
  videoInfo.value = null
  parsedInput.value = ''
  privateParsed.value = false
  analysisResult.value = null
  analysisError.value = ''
  progressSteps.length = 0

  const credentials = credentialsFor(url)
  if (taskId.value || videoId.value) await router.replace({ name: 'analyze' })
  const selection = route.fullPath
  try {
    const result = await parseVideo(url, credentials)
    if (selection !== route.fullPath || urlInput.value.trim() !== url) return
    if (result.platform === 'unsupported') {
      errorMsg.value = result.description || '暂不支持此平台'
      videoInfo.value = null
    } else {
      privateParsed.value = result.platform === 'panopto' || Boolean(credentials)
      parsedInput.value = url
      videoInfo.value = { ...result, source_url: result.platform === 'panopto' ? result.webpage_url : url }
    }
  } catch (err) {
    if (selection !== route.fullPath || urlInput.value.trim() !== url) return
    errorMsg.value = err.message || '解析失败，请检查链接'
    handleVideoError({ code: err.code, message: errorMsg.value }, url, () => handleParse(url), credentials)
  } finally {
    parsing.value = false
  }
}

async function handleAnalyze() {
  if (!canArchive.value) return handleImmediateAnalyze()
  const url = parsedVideoUrl.value
  if (!url || analyzing.value) return
  if (requireBilibiliSession(url, '连接会话并分析', handleAnalyze)) return
  sessionGuide.value = null
  const credentials = credentialsFor(url)
  const save = saveToLibrary.value
  const selectedProvider = provider.value
  const key = JSON.stringify([url, save, privateSource.value, selectedProvider])
  if (studyAttempt?.key !== key) studyAttempt = { key, id: studyRequestId() }
  const selection = route.fullPath
  analyzing.value = true
  analysisError.value = ''
  let useImmediate = false
  try {
    const queued = await studyApi.analyze(url, credentials, {
      id: studyAttempt.id, save, consent: privateSource.value && save,
      title: videoInfo.value.title.slice(0, 240), provider: selectedProvider,
    })
    studyAttempt = null
    if (selection !== route.fullPath || parsedVideoUrl.value !== url) return
    trackBilibiliAttempt(queued.id, credentials)
    submittedTaskId.value = queued.id
    await router.replace(analysisTaskLink(queued.id))
    if (recentPanel.value?.open) loadRecent()
  } catch (error) {
    if (selection !== route.fullPath || parsedVideoUrl.value !== url) return
    if (error.code === 'video_link') {
      // 旧的预览缓存没有归档能力标记。沿用后端校验结果。
      videoInfo.value = { ...videoInfo.value, archive_supported: false }
      studyAttempt = null
      useImmediate = !save
      if (save) analysisError.value = '该链接支持临时分析。再次点击「开始分析」可继续。'
    } else {
      analysisError.value = error.message
    }
  } finally {
    analyzing.value = false
  }
  if (useImmediate) handleImmediateAnalyze()
}

function trackBilibiliAttempt(id, credentials) {
  bilibiliAttempt = credentials?.bilibiliSession || credentials?.cookies ? { id, credentials } : null
}

watch(task, current => {
  if (!current || current.id !== bilibiliAttempt?.id || isTaskActive(current)) return
  const { credentials } = bilibiliAttempt
  bilibiliAttempt = null
  if (current.code === 'bilibili_session_rejected') {
    handleVideoError({ code: current.code, message: current.detail }, current.target.url, retryAnalysisTask, credentials)
  }
})

async function retryAnalysisTask() {
  const current = task.value
  if (!current || taskBusy.value || !confirmTaskRetry(current)) return
  const { url } = current.target
  const site = sessionSiteFor(url)
  const credentials = credentialsFor(url)
  if (needsRetryConsent.value && !retryConsent.value) {
    analysisError.value = '请先确认保存此登录视频。'
    return
  }
  if (current.target.requires_session && current.state === 'needs_input' && site && !credentials) {
    sessionGuide.value = { site, url, message: current.detail, retry: retryAnalysisTask, submitLabel: '连接会话并重试' }
    return
  }
  taskBusy.value = true
  analysisError.value = ''
  try {
    await studyApi.retryTask(current.id, credentials, retryConsent.value)
    if (taskId.value === current.id) {
      trackBilibiliAttempt(current.id, credentials)
      await readSelection()
    }
  } catch (error) {
    if (taskId.value !== current.id) return
    analysisError.value = error.message
    handleVideoError(error, url, retryAnalysisTask, credentials)
  } finally {
    taskBusy.value = false
  }
}

async function cancelAnalysisTask() {
  const current = task.value
  if (!current || taskBusy.value) return
  taskBusy.value = true
  analysisError.value = ''
  try {
    await studyApi.cancelTask(current.id)
    if (taskId.value === current.id) await readSelection()
  } catch (error) {
    if (taskId.value === current.id) analysisError.value = error.message
  } finally {
    taskBusy.value = false
  }
}

function handleImmediateAnalyze() {
  const url = parsedVideoUrl.value
  if (!url || analyzing.value) return
  if (requireBilibiliSession(url, '连接会话并分析', handleImmediateAnalyze)) return

  analyzing.value = true
  sessionGuide.value = null
  analysisError.value = ''
  analysisResult.value = null
  progressSteps.length = 0

  progressSteps.push(
    { step: 'parse', status: 'waiting' },
    { step: 'subtitles', status: 'waiting' },
    { step: 'analyze', status: 'waiting' }
  )

  const credentials = credentialsFor(url)
  const controller = startAnalysis(
    url,
    credentials,
    (event) => {
      if (abortAnalysis !== controller) return
      if (event.status === 'failed') {
        handleVideoError(event, url, handleImmediateAnalyze, credentials)
      }
      const idx = progressSteps.findIndex(s => s.step === event.step)
      if (idx >= 0) {
        progressSteps[idx].status = event.status
        progressSteps[idx].message = event.message
      } else if (event.step === 'error') {
        analysisError.value = event.message
        analyzing.value = false
        abortAnalysis = null
        return
      }

      if (event.status === 'failed') {
        analyzing.value = false
        analysisError.value = event.message
        abortAnalysis = null
        return
      }

      if (event.status === 'done' && event.result) {
        analyzing.value = false
        analysisResult.value = event.result
        immediateId.value = setImmediateResult(event.result, { persist: !privateSource.value })
        abortAnalysis = null
      }
    },
    (err) => {
      if (abortAnalysis !== controller) return
      abortAnalysis = null
      analyzing.value = false
      analysisError.value = err.message || '分析请求失败'
      handleVideoError({ code: err.code, message: analysisError.value }, url, handleImmediateAnalyze, credentials)
      const active = progressSteps.find(s => s.status === 'processing')
      if (active) {
        active.status = 'failed'
        active.message = analysisError.value
      }
    },
    provider.value,
  )
  abortAnalysis = controller
}

function dismissProgress() {
  progressSteps.length = 0
  analysisError.value = ''
}

onBeforeUnmount(() => {
  abortAnalysis?.abort()
  abortAnalysis = null
})
</script>

<style scoped>
.analysis-page {
  --video-cover-width: clamp(148px, 24vw, 218px);
  padding-top: 32px;
}

.input-tools {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px 12px;
  border-top: 1px solid var(--border);
  padding-top: 6px;
}
.utility-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  list-style: none;
}
.utility-action svg { flex: none; }
.utility-action::-webkit-details-marker { display: none; }
.utility-action:hover, details[open] > .utility-action { color: var(--text-primary); background: var(--bg-hover); }
details[open] > .utility-action .disclosure-icon { transform: rotate(180deg); }
.recent-analysis { flex: 1 1 auto; min-width: 0; }
.recent-analysis-tools { display: flex; justify-content: flex-end; margin-top: 4px; }
.recent-analysis-list { list-style: none; max-height: 15rem; overflow: auto; }
.recent-analysis-list li { display: flex; align-items: center; gap: 4px; }
.recent-analysis-list a {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px 16px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  text-decoration: none;
  overflow-wrap: anywhere;
}
.recent-analysis-list a:hover, .recent-analysis-list a[aria-current] { background: var(--bg-hover); }
.recent-analysis-list button { flex: none; }
.recent-analysis-list small { color: var(--text-secondary); flex-shrink: 0; }
.analysis-output { display: grid; gap: 14px; margin-top: 18px; }
.analysis-record-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px 20px;
}
.analysis-record-header h2 { font-size: 1.14rem; line-height: 1.45; overflow-wrap: anywhere; }
.analysis-record-header .platform-note { margin-top: 4px; }
.analysis-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.retry-consent { margin-top: 12px; }

.platform-note {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.input-session {
  display: flex;
  align-items: baseline;
  gap: 4px 8px;
  flex-wrap: wrap;
  margin-inline-start: auto;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.session-action {
  padding: 4px 6px;
  min-height: 32px;
  background: transparent;
  color: var(--accent);
  font-size: 0.82rem;
  text-underline-offset: 3px;
}
.session-action:hover { text-decoration: underline; }

.session-details > summary {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.session-options {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 8px;
}

.page-header {
  text-align: center;
  margin-bottom: 24px;
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

/* 输入区 */
.input-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-label {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-secondary);
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.url-input {
  flex: 1;
  min-width: 0;
  font-size: 1.05rem;
  padding: 14px 18px;
  min-height: 48px;
}

.parse-btn {
  white-space: nowrap;
  padding: 12px 22px;
  min-height: 48px;
}

.spinner-svg {
  animation: spin 0.6s linear infinite;
}

/* 骨架屏卡片 */
.skeleton-card {
  margin-top: 20px;
  display: grid;
  grid-template-columns: var(--video-cover-width) minmax(0, 1fr);
  gap: clamp(12px, 3vw, 22px);
  align-items: center;
}

.skeleton-card .skeleton-thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-sm);
}

.skeleton-card .skeleton-title {
  height: 22px;
  width: 70%;
  margin-bottom: 14px;
  border-radius: 6px;
}

.skeleton-card .skeleton-text {
  height: 13px;
  margin-bottom: 8px;
  border-radius: 4px;
}

.skeleton-card .skeleton-text:last-child {
  width: 50%;
}

/* 错误提示 */
.error-banner {
  margin-top: 16px;
  padding: 14px 18px;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 10px;
}
.error-banner > svg { flex: none; }

.error-text {
  flex: 1;
  white-space: pre-line;
  line-height: 1.7;
}

.error-close, .btn-close-progress {
  flex-shrink: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 6px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 38px;
  min-height: 38px;
}

.error-close:hover, .btn-close-progress:hover {
  color: var(--text-primary);
  border-color: var(--border-strong);
  background: var(--bg-hover);
}

.result-area {
  margin-top: 24px;
}

.video-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.video-primary-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; }
.video-primary-actions svg { flex: none; }
.save-option { min-height: 40px; color: var(--text-secondary); font-size: 0.84rem; }
.video-actions > .download-section { margin-inline-start: auto; }
.video-preview .platform-note { margin-top: 8px; font-size: 0.82rem; }

/* 分析进度 */
.progress-area {
  margin-top: 16px;
  padding: 20px 24px;
}

.progress-header {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text-primary);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 6px 16px;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 36px;
}

.btn-retry:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.progress-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast);
}

.step-waiting {
  color: var(--text-muted);
}

.step-processing {
  color: var(--text-primary);
  background: var(--bg-hover);
  border: 1px solid var(--border);
}

.step-done {
  color: var(--text-primary);
  font-weight: 600;
}

.step-failed {
  color: var(--text-primary);
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
}

.step-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.step-label {
  font-weight: 600;
  min-width: 80px;
}

.step-message {
  color: var(--text-muted);
  font-size: 0.82rem;
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .analysis-page {
    --video-cover-width: min(30vw, 120px);
    padding-top: 24px;
  }
  .page-title {
    font-size: 1.4rem;
  }
  .page-desc {
    font-size: 0.88rem;
  }
  .page-header {
    margin-bottom: 24px;
  }
  .input-row {
    flex-direction: column;
    gap: 10px;
  }
  .parse-btn {
    width: 100%;
    padding: 14px 24px;
  }
  .url-input {
    font-size: 1rem;
    padding: 12px 14px;
  }
  .video-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .video-actions > .download-section { justify-self: start; margin-inline-start: 0; }
  .progress-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .btn-retry {
    margin-left: 0;
  }
}

@media (max-width: 374px) {
  .card { padding: 14px; }
  .progress-area { padding: 14px 16px; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
