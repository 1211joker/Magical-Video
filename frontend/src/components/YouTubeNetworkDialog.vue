<template>
  <dialog
    ref="dialog"
    class="network-dialog"
    aria-labelledby="youtube-network-title"
    aria-describedby="youtube-network-message"
    @cancel.prevent="emit('dismiss')"
  >
    <h2 id="youtube-network-title">无法连接 YouTube</h2>
    <p id="youtube-network-message">{{ message }}</p>
    <p>如果你在中国大陆，请在运行本项目后端的设备上开启代理，并打开代理客户端的系统代理模式，再重新检测。</p>
    <p>如果你使用的是在线部署，请联系管理员检查服务器网络和代理配置。</p>
    <div class="dialog-actions">
      <button class="btn-secondary" type="button" @click="emit('dismiss')">关闭</button>
      <button class="btn-primary" type="button" autofocus @click="emit('retry')">重新检测</button>
    </div>
  </dialog>
</template>

<script setup>
import { onMounted, ref } from 'vue'

defineProps({ message: { type: String, required: true } })
const emit = defineEmits(['dismiss', 'retry'])
const dialog = ref(null)

onMounted(() => dialog.value.showModal())
</script>

<style scoped>
.network-dialog {
  width: min(30rem, calc(100% - 2rem));
  margin: auto;
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-primary);
}

.network-dialog::backdrop {
  background: rgb(0 0 0 / 0.52);
}

.network-dialog h2 {
  font-size: 1.2rem;
  margin-bottom: 12px;
}

.network-dialog p {
  margin-bottom: 10px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
