<template>
  <div class="mindmap-wrapper">
    <div class="mindmap-toolbar">
      <button class="btn-download" @click="downloadSVG">
        <span>⬇️</span> 下载思维导图
      </button>
    </div>
    <div ref="svgContainer" class="mindmap-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Transformer } from 'markmap-lib'
import * as markmap from 'markmap-view'

const props = defineProps({
  data: {
    type: Object,
    required: true
  }
})

const svgContainer = ref(null)
let currentMM = null

// 把 AI 返回的 JSON 脑图结构转成 markmap 认识的 markdown
function toMarkdown(node, level = 0) {
  const depth = Math.min(level + 1, 6)
  const prefix = '#'.repeat(depth)
  let md = `${prefix} ${node.content}\n`
  if (node.children && node.children.length) {
    for (const child of node.children) {
      md += toMarkdown(child, level + 1)
    }
  }
  return md
}

function render() {
  if (!svgContainer.value || !props.data) return

  // 清掉上次渲染的
  svgContainer.value.innerHTML = ''

  try {
    const markdown = toMarkdown(props.data)
    const transformer = new Transformer()
    const { root, features } = transformer.transform(markdown)

    // 设置 Markmap 的全局选项
    currentMM = markmap.Markmap.create(
      svgContainer.value,
      {
        autoFit: true,
        colorFreezeLevel: 2,
        duration: 400,
        maxWidth: 280,
        paddingX: 20,
        spacingHorizontal: 80,
        spacingVertical: 10,
        initialExpandLevel: 2,
      },
      root
    )
  } catch (err) {
    console.error('MindMap render error:', err)
  }
}

// 下载 SVG
function downloadSVG() {
  const svg = svgContainer.value?.querySelector('svg')
  if (!svg) return

  // 克隆一份来加白底（否则透明背景下载后不好看）
  const clone = svg.cloneNode(true)
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  rect.setAttribute('width', '100%')
  rect.setAttribute('height', '100%')
  rect.setAttribute('fill', '#ffffff')
  clone.insertBefore(rect, clone.firstChild)

  const svgText = new XMLSerializer().serializeToString(clone)
  const blob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = `思维导图_${Date.now()}.svg`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  nextTick(render)
})

watch(() => props.data, () => {
  nextTick(render)
}, { deep: true })

onBeforeUnmount(() => {
  if (currentMM) {
    currentMM = null
  }
  if (svgContainer.value) {
    svgContainer.value.innerHTML = ''
  }
})
</script>

<style scoped>
.mindmap-wrapper {
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: #fff;
}

.mindmap-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: #fafbfc;
}

.btn-download {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-download:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
  background: #f9fafb;
}

.mindmap-container {
  width: 100%;
  height: 500px;
}

/* 让 markmap 内部的 SVG 填满容器 */
:deep(svg) {
  width: 100% !important;
  height: 100% !important;
}
</style>
