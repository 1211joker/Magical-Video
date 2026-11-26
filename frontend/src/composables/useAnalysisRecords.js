import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { studyApi } from '../api/study.js'
import { isTaskActive, useStudyPolling } from '../studyUi.js'

export function useAnalysisRecords() {
  const route = useRoute()
  const taskId = computed(() => route.name === 'analyze' && typeof route.query.task === 'string' ? route.query.task : '')
  const videoId = computed(() => route.name === 'analyze' && typeof route.query.video === 'string' ? route.query.video : '')
  const task = ref(null)
  const video = ref(null)
  const loading = ref(false)
  const loadError = ref('')
  const recent = ref([])
  const loadingRecent = ref(false)
  const recentError = ref('')
  let selection = 0
  let recentVersion = 0

  async function readSelection() {
    const current = selection
    const id = taskId.value
    try {
      if (id) {
        const updated = await studyApi.task(id)
        if (current !== selection) return
        if (updated.kind !== 'analysis') throw new Error('此记录不是视频解析。')
        if (task.value?.updated_at > updated.updated_at) return
        task.value = updated
        recent.value = recent.value.map(item => item.id === id ? updated : item)
      } else if (videoId.value) {
        const saved = await studyApi.video(videoId.value)
        if (current !== selection) return
        video.value = saved
      }
      if (current === selection) loadError.value = ''
    } catch (error) {
      if (current === selection) loadError.value = error.message
    } finally {
      if (current === selection) loading.value = false
    }
  }

  watch([taskId, videoId], () => {
    selection++
    task.value = null
    video.value = null
    loadError.value = ''
    loading.value = Boolean(taskId.value || videoId.value)
    if (loading.value) readSelection()
  }, { immediate: true, flush: 'sync' })

  useStudyPolling(async () => {
    if (isTaskActive(task.value)) await readSelection()
  })

  async function loadRecent() {
    const version = ++recentVersion
    loadingRecent.value = true
    recentError.value = ''
    try {
      const records = await studyApi.tasks('analysis')
      if (version === recentVersion) recent.value = records
    } catch (error) {
      if (version === recentVersion) recentError.value = error.message
    } finally {
      if (version === recentVersion) loadingRecent.value = false
    }
  }

  async function removeRecent(id) {
    await studyApi.deleteAnalysis(id)
    recent.value = recent.value.filter(item => item.id !== id)
    loadRecent()
  }

  return {
    taskId, videoId, task, video, loading, loadError, readSelection,
    recent, loadingRecent, recentError, loadRecent, removeRecent,
  }
}
