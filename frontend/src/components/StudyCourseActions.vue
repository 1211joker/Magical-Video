<template>
  <StudyManagementDialog title="管理课程" :busy="busy" @close="emit('close')">
    <form v-if="!deleting" class="study-editor" @submit.prevent="rename">
      <label class="study-field">课程名称
        <input v-model="title" maxlength="120" required autofocus :disabled="busy">
      </label>
      <div class="study-editor-actions">
        <button class="study-quiet" type="button" :disabled="busy" @click="deleting = true; error = ''">删除课程</button>
        <button class="btn-primary btn-compact" :disabled="busy || !title.trim() || title.trim() === course.title">
          保存名称
        </button>
      </div>
    </form>
    <div v-else class="study-editor">
      <p>删除「{{ course.title }}」及其 Wiki 概念页？课程中的视频仍可在资料库查看。</p>
      <div class="study-actions">
        <button class="btn-secondary btn-compact" type="button" :disabled="busy" @click="deleting = false; error = ''">返回</button>
        <button class="btn-primary btn-compact" type="button" :disabled="busy" @click="destroy">确认删除课程</button>
      </div>
    </div>
    <p v-if="error" class="study-notice" role="alert">{{ error }}</p>
  </StudyManagementDialog>
</template>

<script setup>
import { ref } from 'vue'
import { studyApi } from '../api/study.js'
import StudyManagementDialog from './StudyManagementDialog.vue'

const props = defineProps({ course: { type: Object, required: true } })
const emit = defineEmits(['close', 'changed'])
const title = ref(props.course.title)
const deleting = ref(false)
const busy = ref(false)
const error = ref('')

async function update(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    emit('changed')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function rename() {
  const name = title.value.trim()
  if (name && name !== props.course.title) return update(() => studyApi.renameCourse(props.course.id, name))
}

function destroy() {
  return update(() => studyApi.deleteCourse(props.course.id))
}
</script>
