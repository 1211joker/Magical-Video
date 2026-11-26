<template>
  <div class="study-page">
    <header class="study-header">
      <h1>资料库</h1>
      <p>查看已保存的视频，或把同一教程的各讲整理成课程</p>
    </header>

    <div v-if="loadError" class="study-notice" role="alert">
      {{ loadError }}
      <button class="btn-secondary btn-compact" type="button" @click="load">重新读取</button>
    </div>
    <p v-else-if="!library" class="study-muted" role="status">正在加载资料库…</p>
    <template v-if="library">
      <nav class="study-tabs" aria-label="资料库分类">
        <RouterLink :to="{ name: 'study-library' }" :aria-current="!showCourses ? 'page' : undefined">
          视频 <span>{{ library.videos.length }}</span>
        </RouterLink>
        <RouterLink :to="{ name: 'study-library', query: { tab: 'courses' } }" :aria-current="showCourses ? 'page' : undefined">
          课程 <span>{{ library.courses.length }}</span>
        </RouterLink>
      </nav>

      <template v-if="!showCourses">
        <div class="study-toolbar library-video-toolbar">
          <label class="study-search">
            <span class="sr-only">搜索视频</span>
            <input v-model="query" type="search" placeholder="搜索视频、分组或课程">
          </label>
          <label class="study-search group-filter">
            <span class="sr-only">筛选视频分组</span>
            <select v-model="groupFilter">
              <option value="">全部视频</option>
              <option :value="null">未分组</option>
              <option v-for="group in library.groups" :key="group.id" :value="group.id">{{ group.title }}</option>
            </select>
          </label>
          <button class="btn-secondary btn-compact" type="button" @click="manager = { type: 'groups' }">管理分组</button>
        </div>
        <ul v-if="visibleVideos.length" class="study-cards">
          <li v-for="video in visibleVideos" :key="video.id" class="card study-item">
            <div class="library-item-heading">
              <div class="study-item-meta">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
                  <rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>
                </svg>
                <span>{{ platforms[video.platform] }} · {{ timecode(video.duration) }}<template v-if="video.private"> · 登录资料</template></span>
              </div>
              <button class="study-quiet" type="button" :aria-label="'管理视频 · ' + video.title"
                      @click="manager = { type: 'video', item: video }">管理</button>
            </div>
            <h2>{{ video.title }}</h2>
            <div v-if="video.group_id || video.courses.length" class="library-video-labels">
              <span v-if="groupNames.has(video.group_id)" class="library-group-tag">{{ groupNames.get(video.group_id) }}</span>
              <span v-if="video.courses.length" class="study-muted study-small">{{ video.courses.map(course => course.title).join(' · ') }}</span>
            </div>
            <div class="study-actions">
              <RouterLink :to="videoAnalysisLink(video.id)" class="btn-secondary btn-compact">查看解析</RouterLink>
              <RouterLink :to="studyChatLink('video', video.id)" class="btn-primary btn-compact">去问答</RouterLink>
            </div>
          </li>
        </ul>
        <p v-else-if="query.trim()" class="study-empty card">未找到匹配的视频。</p>
        <p v-else-if="groupFilter !== ''" class="study-empty card">这个分组里还没有视频。</p>
        <div v-else class="study-empty card">
          <h2>还没有已保存的视频</h2>
          <p>开始分析时勾选「保存到资料库」，完成后可以在这里查看。</p>
          <RouterLink :to="{ name: 'analyze' }" class="btn-primary btn-compact">去分析视频</RouterLink>
        </div>
      </template>

      <template v-else>
        <div class="study-toolbar">
          <button class="btn-primary btn-compact" type="button" :aria-expanded="creating"
                  @click="creating = !creating">{{ creating ? '收起新建课程' : '新建课程' }}</button>
        </div>
        <form v-if="creating" class="study-form study-panel card" @submit.prevent="createCourse">
          <label class="study-field">课程名称
            <input v-model="courseTitle" maxlength="120" placeholder="例如 神经网络基础" required>
          </label>
          <button class="btn-primary btn-compact" :disabled="saving || !courseTitle.trim()">创建课程</button>
        </form>
        <p v-if="createError" class="study-notice" role="alert">{{ createError }}</p>
        <ul v-if="library.courses.length" class="study-cards">
          <li v-for="course in library.courses" :key="course.id" class="card study-item">
            <div class="library-item-heading">
              <div class="study-item-meta">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
                  <path d="M4 20V5a2 2 0 0 1 2-2h14v17H6a2 2 0 0 0 0 4m2-17h8m-8 4h8"/>
                </svg>
                <span>{{ course.video_count }} 讲</span>
              </div>
              <button class="study-quiet" type="button" :aria-label="'管理课程 · ' + course.title"
                      @click="manager = { type: 'course', item: course }">管理</button>
            </div>
            <h2>{{ course.title }}</h2>
            <div class="study-actions">
              <RouterLink :to="{ name: 'study-course', params: { courseId: course.id } }" class="btn-secondary btn-compact">打开课程</RouterLink>
            </div>
          </li>
        </ul>
        <div v-else class="study-empty card">
          <h2>还没有课程</h2>
          <p>创建课程后，可以从已保存的视频中选取各讲。</p>
        </div>
      </template>
    </template>
    <SavedVideoActions v-if="manager?.type === 'video'" :video="manager.item" :groups="library.groups"
                       @close="manager = null" @changed="finishManagement" />
    <StudyCourseActions v-else-if="manager?.type === 'course'" :course="manager.item"
                        @close="manager = null" @changed="finishManagement" />
    <StudyGroupActions v-else-if="manager?.type === 'groups'" :groups="library.groups" :refreshing="loading"
                       @close="manager = null" @changed="load" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { studyApi } from '../api/study.js'
import SavedVideoActions from '../components/SavedVideoActions.vue'
import StudyCourseActions from '../components/StudyCourseActions.vue'
import StudyGroupActions from '../components/StudyGroupActions.vue'
import { platforms, studyChatLink, timecode, videoAnalysisLink } from '../studyUi.js'

const route = useRoute()
const router = useRouter()
const library = ref(null)
const loading = ref(true)
const saving = ref(false)
const creating = ref(false)
const loadError = ref('')
const createError = ref('')
const query = ref('')
const courseTitle = ref('')
const groupFilter = ref('')
const manager = ref(null)
const showCourses = computed(() => route.query.tab === 'courses')
const groupNames = computed(() => new Map(library.value.groups.map(group => [group.id, group.title])))
const visibleVideos = computed(() => {
  const text = query.value.trim().toLowerCase()
  return library.value.videos.filter(video => {
    if (groupFilter.value !== '' && groupFilter.value !== (video.group_id ?? null)) return false
    const names = [video.title, groupNames.value.get(video.group_id) ?? '', ...video.courses.map(course => course.title)]
    return names.some(name => name.toLowerCase().includes(text))
  })
})
let readVersion = 0
watch(showCourses, () => { manager.value = null })

async function load() {
  const version = ++readVersion
  loading.value = true
  loadError.value = ''
  try {
    const data = await studyApi.library()
    if (version !== readVersion) return
    library.value = { groups: [], ...data }
    if (groupFilter.value && !groupNames.value.has(groupFilter.value)) groupFilter.value = null
  } catch (err) {
    if (version === readVersion) loadError.value = err.message
  } finally {
    if (version === readVersion) loading.value = false
  }
}

function finishManagement() {
  manager.value = null
  load()
}

async function createCourse() {
  const title = courseTitle.value.trim()
  if (saving.value || !title) return
  saving.value = true
  createError.value = ''
  const location = route.fullPath
  try {
    const course = await studyApi.createCourse(title)
    if (route.name !== 'study-library') return
    if (route.fullPath === location) {
      await router.push({ name: 'study-course', params: { courseId: course.id } })
    } else {
      await load()
    }
    courseTitle.value = ''
    creating.value = false
  } catch (err) {
    createError.value = err.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.library-video-toolbar { justify-content: flex-start; gap: 8px; }
.library-video-toolbar .study-search { flex: 1 1 220px; width: auto; }
.library-video-toolbar .group-filter { flex: 0 1 180px; min-width: 112px; }
.library-item-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.library-item-heading .study-quiet { flex: none; }
.library-video-labels { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; overflow-wrap: anywhere; }
.library-group-tag {
  max-width: 100%;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-input);
  font-size: 0.78rem;
}
@media (max-width: 560px) {
  .library-video-toolbar .study-search { flex-basis: 100%; }
  .library-video-toolbar .group-filter { flex: 1 1 112px; }
}
</style>
