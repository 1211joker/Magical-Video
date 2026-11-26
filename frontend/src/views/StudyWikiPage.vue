<template>
  <div class="study-page">
    <nav class="study-breadcrumb" aria-label="返回路径">
      <RouterLink :to="{ name: 'study-library', query: { tab: 'courses' } }">资料库的课程</RouterLink>
      <span v-if="page" aria-hidden="true">›</span>
      <RouterLink v-if="page" :to="{ name: 'study-course', params: { courseId: page.course_id }, query: { tab: 'wiki' } }">
        {{ page.course_title }} · 课程 Wiki
      </RouterLink>
    </nav>
    <p v-if="error" role="alert" class="study-notice">{{ error }}</p>
    <p v-if="!page && !error" role="status" class="study-muted">正在读取概念页…</p>
    <template v-if="page">
      <header class="study-detail-header card">
        <div>
          <h1>{{ page.title }}</h1>
          <p v-if="page.aliases.length" class="study-muted">{{ page.aliases.join(' · ') }}</p>
        </div>
        <RouterLink :to="studyChatLink('course', page.course_id)" class="btn-primary btn-compact">课程问答</RouterLink>
      </header>

      <section class="study-panel card">
        <h2>概念说明</h2>
        <ul class="study-list wiki-claims">
          <li v-for="claim in page.claims" :key="claim.id" class="wiki-claim">
            <p>{{ claim.explanation }}</p>
            <StudySources :sources="[{ ...claim.source, quote: claim.quote }]" title="" />
          </li>
        </ul>
      </section>

      <section v-if="page.related.length || page.suggestions.length" class="study-panel card">
        <h2>相关概念</h2>
        <ul v-if="page.related.length" class="study-list">
          <li v-for="item in page.related" :key="item.id" class="study-row">
            <div>
              <RouterLink :to="{ name: 'study-wiki', params: { pageId: item.id } }">{{ item.title }}</RouterLink>
              <p v-if="item.course_id !== page.course_id" class="study-muted study-small">{{ item.course_title }}</p>
            </div>
            <button v-if="item.course_id !== page.course_id" class="btn-secondary btn-compact" :disabled="busy"
                    @click="setLink(item.id, false)">取消链接</button>
          </li>
        </ul>
        <h3 v-if="page.suggestions.length">跨课链接建议</h3>
        <ul v-if="page.suggestions.length" class="study-list">
          <li v-for="item in page.suggestions" :key="item.id" class="study-row">
            <div>
              <RouterLink :to="{ name: 'study-wiki', params: { pageId: item.id } }">{{ item.title }}</RouterLink>
              <p class="study-muted study-small">{{ item.course_title }}</p>
            </div>
            <div class="study-actions">
              <button class="btn-secondary btn-compact" :disabled="busy" @click="setLink(item.id, true)">确认链接</button>
              <button class="btn-secondary btn-compact" :disabled="busy" @click="setLink(item.id, false)">忽略</button>
            </div>
          </li>
        </ul>
      </section>

      <details class="study-panel card">
        <summary>整理概念页</summary>
        <form class="study-form" @submit.prevent="save">
          <label class="study-field">概念名称
            <input v-model="title" maxlength="120" required>
          </label>
          <label class="study-field">别名（用逗号分隔）
            <input v-model="aliases" maxlength="1200">
          </label>
          <button class="btn-primary btn-compact" :disabled="busy || !title.trim()">保存</button>
        </form>
        <form v-if="otherPages.length" class="study-form" @submit.prevent="merge">
          <label class="study-field">将本页合并到
            <select v-model="target" required>
              <option value="" disabled>选择同课程的概念</option>
              <option v-for="item in otherPages" :key="item.id" :value="item.id">{{ item.title }}</option>
            </select>
          </label>
          <button class="btn-secondary btn-compact" :disabled="busy || !target">合并概念</button>
        </form>
      </details>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { studyApi } from '../api/study.js'
import StudySources from '../components/StudySources.vue'
import { studyChatLink } from '../studyUi.js'

const route = useRoute()
const router = useRouter()
const page = ref(null)
const otherPages = ref([])
const title = ref('')
const aliases = ref('')
const target = ref('')
const busy = ref(false)
const error = ref('')

async function load(id) {
  try {
    const data = await studyApi.wiki(id)
    if (id !== route.params.pageId) return
    page.value = data
    title.value = data.title
    aliases.value = data.aliases.join(', ')
    const course = await studyApi.course(data.course_id, { includeSuggestions: false })
    if (id === route.params.pageId) otherPages.value = course.wiki_pages.filter(item => item.id !== id)
  } catch (err) {
    if (id === route.params.pageId) error.value = err.message
  }
}

watch(() => route.params.pageId, id => {
  if (!id) return
  page.value = null
  target.value = ''
  otherPages.value = []
  error.value = ''
  load(id)
}, { immediate: true })

async function mutate(action, refresh = true) {
  busy.value = true
  error.value = ''
  try {
    const id = page.value.id
    await action(id)
    if (refresh && id === route.params.pageId) await load(id)
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function save() {
  const words = aliases.value.split(/[,，、]/).map(word => word.trim()).filter(Boolean)
  return mutate(id => studyApi.editWiki(id, title.value.trim(), words))
}

function setLink(relatedId, accepted) {
  return mutate(id => studyApi.linkWiki(id, relatedId, accepted))
}

function merge() {
  const targetId = target.value
  if (!targetId || !window.confirm('将本页的引文、别名和链接合并到所选概念？')) return
  return mutate(async id => {
    await studyApi.mergeWiki(id, targetId)
    await router.replace({ name: 'study-wiki', params: { pageId: targetId } })
  }, false)
}
</script>

<style scoped>
.wiki-claims li { display: grid; gap: 8px; }
.wiki-claim > p { line-height: 1.75; }
</style>
