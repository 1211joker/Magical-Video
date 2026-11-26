<template>
  <div class="study-page">
    <nav class="study-breadcrumb" aria-label="返回路径">
      <RouterLink :to="{ name: 'study-library', query: { tab: 'courses' } }">‹ 资料库的课程</RouterLink>
    </nav>
    <p v-if="error" class="study-notice" role="alert">{{ error }}</p>
    <p v-if="!course && !error" class="study-muted" role="status">正在读取课程…</p>
    <template v-if="course">
      <header class="study-detail-header card">
        <div>
          <h1>{{ course.title }}</h1>
          <p>{{ course.videos.length }} 讲 · {{ course.wiki_pages.length }} 个概念</p>
        </div>
        <RouterLink v-if="course.videos.length" :to="studyChatLink('course', course.id)" class="btn-primary btn-compact">课程问答</RouterLink>
      </header>

      <nav class="study-tabs" aria-label="课程分类">
        <RouterLink :to="courseLocation()" :aria-current="!showWiki ? 'page' : undefined">课程视频</RouterLink>
        <RouterLink :to="courseLocation('wiki')" :aria-current="showWiki ? 'page' : undefined">课程 Wiki</RouterLink>
      </nav>

      <template v-if="!showWiki">
        <section class="study-panel card" aria-labelledby="course-sequence">
          <header class="study-heading">
            <h2 id="course-sequence">课程序列</h2>
            <button v-if="course.videos.length || available.length" class="btn-secondary btn-compact" type="button"
                    :aria-expanded="managing" @click="managing = !managing">
              {{ managing ? '完成管理' : '管理课程视频' }}
            </button>
          </header>
          <form v-if="(managing || !course.videos.length) && available.length" class="study-form" @submit.prevent="add(selected)">
            <label class="study-field">从资料库选择视频
              <select v-model="selected" :disabled="busy" required>
                <option value="" disabled>选择视频</option>
                <option v-for="video in available" :key="video.id" :value="video.id">{{ video.title }}</option>
              </select>
            </label>
            <button class="btn-primary btn-compact" :disabled="busy || !selected">加入课程</button>
          </form>
          <ol v-if="course.videos.length" class="study-list course-sequence">
            <li v-for="(video, index) in course.videos" :key="video.id" class="study-row">
              <div class="lesson-info">
                <p class="study-item-meta">第 {{ index + 1 }} 讲</p>
                <h3>{{ video.title }}</h3>
                <p v-if="video.wiki_task && video.wiki_task.state !== 'done'" class="study-muted study-small">
                  Wiki {{ taskStates[video.wiki_task.state] }}
                </p>
              </div>
              <div class="study-actions">
                <template v-if="managing">
                  <button class="btn-secondary btn-compact" :disabled="busy || index === 0"
                          :aria-label="'上移 ' + video.title" @click="move(index, -1)">上移</button>
                  <button class="btn-secondary btn-compact" :disabled="busy || index === course.videos.length - 1"
                          :aria-label="'下移 ' + video.title" @click="move(index, 1)">下移</button>
                  <button class="btn-secondary btn-compact" :disabled="busy" @click="remove(video)">移出</button>
                </template>
                <RouterLink v-else :to="videoAnalysisLink(video.id)" class="btn-secondary btn-compact">查看解析</RouterLink>
              </div>
            </li>
          </ol>
          <div v-else class="study-muted">
            <p>加入视频后，系统会按讲次展示，并开始整理课程 Wiki。</p>
            <RouterLink v-if="!available.length" :to="{ name: 'analyze' }" class="btn-secondary btn-compact study-inline-cta">去分析视频</RouterLink>
          </div>
        </section>

        <details v-if="course.suggestions.length" class="study-panel card">
          <summary>可能属于这门课的视频</summary>
          <ul class="study-list">
            <li v-for="video in course.suggestions" :key="video.id" class="study-row">
              <RouterLink :to="videoAnalysisLink(video.id)">{{ video.title }}</RouterLink>
              <button class="btn-secondary btn-compact" :disabled="busy" @click="add(video.id)">加入课程</button>
            </li>
          </ul>
        </details>
      </template>

      <template v-else>
        <section v-if="wikiWork.length" class="study-panel card" aria-label="Wiki 整理进度">
          <h2>Wiki 整理进度</h2>
          <ul class="study-list wiki-progress">
            <li v-for="video in wikiWork" :key="video.id" class="study-row">
              <div>
                <h3>{{ video.title }}</h3>
                <p class="study-small study-muted" role="status">
                  {{ taskStates[video.wiki_task.state] }}<template v-if="video.wiki_task.detail"> · {{ video.wiki_task.detail }}</template>
                </p>
              </div>
              <button v-if="canRetryTask(video.wiki_task)" class="btn-secondary btn-compact" :disabled="busy"
                      @click="retryWiki(video.wiki_task)">重试 Wiki 整理</button>
              <button v-else-if="isTaskActive(video.wiki_task)" class="btn-secondary btn-compact" :disabled="busy"
                      @click="mutate(() => studyApi.cancelTask(video.wiki_task.id))">取消整理</button>
            </li>
          </ul>
        </section>

        <div v-if="course.wiki_pages.length" class="study-toolbar">
          <label class="study-search">
            <span class="sr-only">查找概念</span>
            <input v-model="wikiQuery" type="search" placeholder="搜索概念或别名">
          </label>
        </div>
        <ul v-if="wikiPages.length" class="study-cards">
          <li v-for="page in wikiPages" :key="page.id" class="card study-item wiki-item">
            <RouterLink :to="{ name: 'study-wiki', params: { pageId: page.id } }">
              <h2>{{ page.title }}</h2>
              <span aria-hidden="true">→</span>
              <p v-if="page.aliases.length" class="study-muted study-small">{{ page.aliases.join(' · ') }}</p>
            </RouterLink>
          </li>
        </ul>
        <div v-else class="study-empty card">
          <h2>{{ wikiQuery.trim() ? '未找到匹配的概念' : '暂无概念页' }}</h2>
          <p v-if="!wikiQuery.trim()">{{ course.videos.length ? '整理完成后，概念和字幕出处会出现在这里。' : '加入课程视频后，系统会自动整理概念。' }}</p>
          <RouterLink v-if="!course.videos.length" :to="courseLocation()" class="btn-secondary btn-compact">查看课程视频</RouterLink>
        </div>
      </template>

    </template>
    <button v-else-if="error" class="btn-secondary btn-compact load-course" @click="refresh(route.params.courseId)">重新读取</button>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { studyApi } from '../api/study.js'
import {
  canRetryTask, confirmTaskRetry, isTaskActive, studyChatLink, taskStates, useStudyPolling, videoAnalysisLink,
} from '../studyUi.js'

const route = useRoute()
const course = ref(null)
const allVideos = ref([])
const selected = ref('')
const wikiQuery = ref('')
const error = ref('')
const busy = ref(false)
const managing = ref(false)
const showWiki = computed(() => route.query.tab === 'wiki')
const available = computed(() => {
  const members = new Set(course.value?.videos.map(video => video.id))
  return allVideos.value.filter(video => !members.has(video.id))
})
const wikiPages = computed(() => {
  const query = wikiQuery.value.trim().toLowerCase()
  return (course.value?.wiki_pages ?? []).filter(page =>
    [page.title, ...page.aliases].some(name => name.toLowerCase().includes(query)))
})
const wikiWork = computed(() => course.value?.videos.filter(video => video.wiki_task && video.wiki_task.state !== 'done') ?? [])
let readVersion = 0

function courseLocation(tab) {
  return { name: 'study-course', params: { courseId: route.params.courseId }, query: tab ? { tab } : {} }
}

async function refresh(id, { includeSuggestions = true } = {}) {
  const version = ++readVersion
  try {
    const data = await studyApi.course(id, { includeSuggestions })
    if (id !== route.params.courseId || version !== readVersion) return
    if (!includeSuggestions) data.suggestions = course.value?.suggestions ?? []
    course.value = data
  } catch (err) {
    if (id === route.params.courseId && version === readVersion) error.value = err.message
  }
}

watch(() => route.params.courseId, async id => {
  if (!id) return
  course.value = null
  allVideos.value = []
  selected.value = ''
  wikiQuery.value = ''
  error.value = ''
  managing.value = false
  await Promise.all([refresh(id), studyApi.library().then(data => {
    if (id === route.params.courseId) allVideos.value = data.videos
  }).catch(err => {
    if (id === route.params.courseId) error.value = err.message
  })])
}, { immediate: true })

useStudyPolling(async () => {
  if (!busy.value && wikiWork.value.some(video => isTaskActive(video.wiki_task))) {
    await refresh(route.params.courseId, { includeSuggestions: false })
  }
}, 2800)

async function mutate(action) {
  if (busy.value) return
  const id = course.value.id
  busy.value = true
  error.value = ''
  try {
    await action(id)
    if (id === route.params.courseId) await refresh(id)
  } catch (err) {
    if (id === route.params.courseId) error.value = err.message
  } finally {
    busy.value = false
  }
}

function add(videoId) {
  if (!videoId) return
  return mutate(async id => {
    await studyApi.addVideo(id, videoId)
    if (id === route.params.courseId) selected.value = ''
  })
}

function move(index, direction) {
  const ids = course.value.videos.map(video => video.id)
  const target = index + direction
  if (target < 0 || target >= ids.length) return
  const moved = ids[index]
  ids[index] = ids[target]
  ids[target] = moved
  return mutate(id => studyApi.order(id, ids))
}

function remove(video) {
  if (window.confirm('将「' + video.title + '」移出课程？课程 Wiki 和相关回忆会同步更新。')) {
    return mutate(id => studyApi.removeVideo(id, video.id))
  }
}

function retryWiki(task) {
  if (confirmTaskRetry(task)) return mutate(() => studyApi.retryTask(task.id))
}

</script>

<style scoped>
.course-sequence h3, .wiki-progress h3 { margin: 2px 0; line-height: 1.45; }
.lesson-info { flex: 1 1 250px; }
.load-course { justify-self: start; }
.wiki-item { padding: 0; overflow: hidden; }
.wiki-item > a {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 5px 12px;
  height: 100%;
  padding: 18px;
  text-decoration: none;
}
.wiki-item p { grid-column: 1 / -1; }
</style>
