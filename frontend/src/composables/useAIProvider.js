import { ref, watch } from 'vue'

const preferenceKey = 'aiProviderPreference'
const provider = ref('')
try { provider.value = localStorage.getItem(preferenceKey) ?? '' } catch { /* 本地存储不可用 */ }

watch(provider, value => {
  try { localStorage.setItem(preferenceKey, value) } catch { /* 本地存储不可用 */ }
})

export function useAIProvider() {
  return provider
}
