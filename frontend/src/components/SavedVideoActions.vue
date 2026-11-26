<template>
  <StudyManagementDialog title="管理视频" :busy="busy" @close="emit('close')">
    <form v-if="!impact" class="study-editor" @submit.prevent="save">
      <label class="study-field">视频名称
        <input v-model="title" maxlength="240" required autofocus :disabled="busy">
      </label>
      <label class="study-field">视频分组
        <select v-model="groupId" :disabled="busy">
          <option :value="null">未分组</option>
          <option v-for="group in groups" :key="group.id" :value="group.id">{{ group.title }}</option>
        </select>
      </label>
      <div class="study-editor-actions">
        <button class="study-quiet" type="button" :disabled="busy" @click="prepareDelete">删除视频</button>
        <button class="btn-primary btn-compact" :disabled="busy || !dirty || !title.trim()">保存更改</button>
      </div>
    </form>
    <div v-else class="study-editor">
      <h3>删除《{{ video.title }}》</h3>
      <p>影响 {{ impact.courses.length }} 门课程、{{ impact.pages.length }} 个概念页和 {{ impact.turn_count }} 轮问答。</p>
      <p v-if="impact.pages.length" class="study-muted">{{ impact.pages.map(page => page.title).join('、') }}</p>
      <label v-if="impact.turn_count" class="study-check">
        <input v-model="clearTurns" type="checkbox">同时清除受影响的旧问答
      </label>
      <p v-if="impact.turn_count && !clearTurns" class="study-muted">旧问答保留供查看，相应轮次会退出回忆。</p>
      <div class="study-actions">
        <button class="btn-secondary btn-compact" type="button" :disabled="busy" @click="impact = null; error = ''">返回</button>
        <button class="btn-primary btn-compact" type="button" :disabled="busy" @click="destroy">确认删除视频</button>
      </div>
    </div>
    <p v-if="error" class="study-notice" role="alert">{{ error }}</p>
  </StudyManagementDialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { studyApi } from '../api/study.js'
import StudyManagementDialog from './StudyManagementDialog.vue'

const props = defineProps({
  video: { type: Object, required: true },
  groups: { type: Array, required: true },
})
const emit = defineEmits(['close', 'changed'])
const title = ref(props.video.title)
const groupId = ref(props.video.group_id ?? null)
const impact = ref(null)
const clearTurns = ref(false)
const busy = ref(false)
const error = ref('')
const dirty = computed(() => title.value.trim() !== props.video.title || groupId.value !== (props.video.group_id ?? null))

async function update(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function save() {
  const name = title.value.trim()
  if (!dirty.value || !name) return
  return update(async () => {
    await studyApi.updateVideo(props.video.id, groupId.value, name === props.video.title ? undefined : name)
    emit('changed')
  })
}

function prepareDelete() {
  return update(async () => {
    impact.value = await studyApi.impact(props.video.id)
    clearTurns.value = false
  })
}

function destroy() {
  return update(async () => {
    await studyApi.deleteVideo(props.video.id, clearTurns.value)
    emit('changed')
  })
}
</script>
