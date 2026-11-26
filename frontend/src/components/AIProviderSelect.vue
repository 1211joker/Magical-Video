<template>
  <div class="provider-picker">
    <label v-if="providers.length" class="provider-label">
      <span>AI 模型</span>
      <select v-model="provider" :disabled="disabled">
        <option value="" disabled>暂无已配置的模型</option>
        <option
          v-for="item in providers"
          :key="item.id"
          :value="item.id"
          :disabled="!item.configured"
        >
          {{ item.label }} · {{ item.model }}{{ item.configured ? '' : '（未配置）' }}
        </option>
      </select>
    </label>
    <span v-else role="status">{{ status }}</span>
    <p v-if="providers.length && !provider" class="provider-hint">
      在 backend/.env 填写 API Key 后重启后端。
    </p>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getAIProviders } from '../api/index.js'

defineProps({ disabled: Boolean })
const provider = defineModel({ type: String, default: '' })
const providers = ref([])
const status = ref('正在读取 AI 模型…')
const controller = new AbortController()

onMounted(async () => {
  try {
    const data = await getAIProviders(controller.signal)
    providers.value = data.providers
    if (!data.providers.some(item => item.configured && item.id === provider.value)) {
      provider.value = data.default_provider || ''
    }
  } catch (error) {
    if (error.name !== 'AbortError') status.value = 'AI 模型列表加载失败'
  }
})

onBeforeUnmount(() => controller.abort())
</script>

<style scoped>
.provider-picker {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.provider-label {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.provider-label span {
  flex: 0 0 auto;
}

.provider-label select {
  min-width: 0;
  max-width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  background: var(--bg-card);
  font: inherit;
}

.provider-hint {
  margin-top: 6px;
  color: var(--text-muted);
}
</style>
