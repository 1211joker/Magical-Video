<template>
  <StudyManagementDialog title="管理分组" :busy="busy" @close="emit('close')">
    <form class="study-form" @submit.prevent="create">
      <label class="study-field">新分组名称
        <input v-model="newTitle" maxlength="120" placeholder="例如 待复习" required autofocus :disabled="disabled">
      </label>
      <button class="btn-primary btn-compact" :disabled="disabled || !newTitle.trim()">新建分组</button>
    </form>
    <p v-if="error" class="study-notice" role="alert">{{ error }}</p>
    <ul v-if="groups.length" class="study-list">
      <li v-for="group in groups" :key="group.id" class="study-editor">
        <div class="study-row">
          <div>
            <h3>{{ group.title }}</h3>
            <p class="study-muted study-small">{{ group.video_count }} 个视频</p>
          </div>
          <div class="study-actions group-actions">
            <button class="study-quiet" type="button" :disabled="disabled"
                    :aria-label="'重命名分组 · ' + group.title" @click="choose(group, 'rename')">重命名</button>
            <button class="study-quiet" type="button" :disabled="disabled"
                    :aria-label="'删除分组 · ' + group.title" @click="choose(group, 'delete')">删除</button>
          </div>
        </div>
        <form v-if="editing?.id === group.id && editing.action === 'rename'" class="study-form" @submit.prevent="rename(group)">
          <label class="study-field">分组名称
            <input v-model="groupTitle" maxlength="120" required :disabled="disabled">
          </label>
          <button class="btn-secondary btn-compact" type="button" :disabled="disabled" @click="reset">取消</button>
          <button class="btn-primary btn-compact" :disabled="disabled || !groupTitle.trim() || groupTitle.trim() === group.title">
            保存名称
          </button>
        </form>
        <div v-else-if="editing?.id === group.id" class="study-editor">
          <p>删除「{{ group.title }}」？<template v-if="group.video_count">组内视频会移到「未分组」。</template></p>
          <div class="study-actions">
            <button class="btn-secondary btn-compact" type="button" :disabled="disabled" @click="reset">取消</button>
            <button class="btn-primary btn-compact" type="button" :disabled="disabled" @click="destroy(group)">确认删除分组</button>
          </div>
        </div>
      </li>
    </ul>
    <p v-else class="study-muted study-small">还没有分组</p>
  </StudyManagementDialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { studyApi } from '../api/study.js'
import StudyManagementDialog from './StudyManagementDialog.vue'

const props = defineProps({ groups: { type: Array, required: true }, refreshing: Boolean })
const emit = defineEmits(['close', 'changed'])
const newTitle = ref('')
const groupTitle = ref('')
const editing = ref(null)
const busy = ref(false)
const error = ref('')
const disabled = computed(() => busy.value || props.refreshing)

function choose(group, action) {
  editing.value = { id: group.id, action }
  groupTitle.value = group.title
  error.value = ''
}

function reset() {
  editing.value = null
  error.value = ''
}

async function update(action) {
  if (disabled.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    reset()
    emit('changed')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function create() {
  const title = newTitle.value.trim()
  if (title) return update(async () => {
    await studyApi.createGroup(title)
    newTitle.value = ''
  })
}

function rename(group) {
  const title = groupTitle.value.trim()
  if (title && title !== group.title) return update(() => studyApi.renameGroup(group.id, title))
}

function destroy(group) {
  return update(() => studyApi.deleteGroup(group.id))
}
</script>

<style scoped>
.group-actions { gap: 4px; }
</style>
