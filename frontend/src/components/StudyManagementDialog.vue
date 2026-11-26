<template>
  <dialog ref="dialog" class="card study-dialog" :aria-labelledby="titleId" @cancel.prevent="dismiss">
    <div class="dialog-layout">
      <header class="dialog-heading">
        <h2 :id="titleId">{{ title }}</h2>
        <button class="study-quiet dialog-close" type="button" aria-label="关闭" :disabled="busy" @click="dismiss">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
            <path d="m6 6 12 12M18 6 6 18"/>
          </svg>
        </button>
      </header>
      <slot />
    </div>
  </dialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'

const props = defineProps({ title: { type: String, required: true }, busy: Boolean })
const emit = defineEmits(['close'])
const dialog = ref(null)
const titleId = useId()

function dismiss() {
  if (!props.busy) emit('close')
}

onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => dialog.value.close())
</script>

<style scoped>
.study-dialog {
  width: min(520px, calc(100% - 28px));
  max-height: calc(100dvh - 32px);
  margin: auto;
  padding: clamp(16px, 4vw, 26px);
  color: var(--text-primary);
  box-shadow: var(--shadow-lg);
  overflow: auto;
}
.study-dialog::backdrop { background: rgb(0 0 0 / 0.42); }
.dialog-layout { display: grid; gap: 16px; }
.dialog-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dialog-heading h2 { min-width: 0; font-size: 1.12rem; line-height: 1.4; overflow-wrap: anywhere; }
.dialog-close { width: 38px; flex: none; justify-content: center; color: var(--text-secondary); }
</style>
