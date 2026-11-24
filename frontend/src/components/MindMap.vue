<template>
  <div class="mindmap-wrapper">
    <div class="mindmap-toolbar">
      <button class="btn-download" @click="downloadSVG" aria-label="下载思维导图 SVG 文件">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        下载思维导图
      </button>
    </div>
    <div ref="container" class="mindmap-inner">
      <svg class="mindmap-svg" width="100%" :style="{ height: svgHeight + 'px' }"></svg>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { deriveOptions, Markmap } from 'markmap-view'

const props = defineProps({
  data: {
    type: Object,
    required: true
  }
})

const container = ref(null)
const svgHeight = ref(500)
let currentMM = null

// 获取实际的 SVG 元素（markmap 在 svgEl 内创建内容）
function getSvgEl() {
  return container.value?.querySelector('svg') || null
}

function nodeLabel(node) {
  return typeof node?.content === 'string' ? node.content.replace(/\s+/g, ' ').trim() : ''
}

function toMarkmapNode(node, depth = 0) {
  const label = nodeLabel(node) || '视频分析'
  const children = []

  // 旧分析结果也使用同样的三层结构，只保留各主题下最先列出的不同要点。
  if (depth < 2 && Array.isArray(node.children)) {
    const labels = new Set()
    const limit = depth === 0 ? 5 : 3
    for (const child of node.children) {
      const childLabel = nodeLabel(child)
      if (!childLabel || labels.has(childLabel)) continue
      labels.add(childLabel)
      children.push(toMarkmapNode(child, depth + 1))
      if (children.length === limit) break
    }
  }

  // markmap 用 HTML 渲染节点，字幕中的标记按纯文本显示。
  const content = label.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  return { content, children }
}

async function render() {
  const svg = getSvgEl()
  if (!svg || !props.data) return

  currentMM?.destroy()
  try {
    const map = Markmap.create(svg, {
      ...deriveOptions({ colorFreezeLevel: 2 }),
      autoFit: true,
      duration: 400,
      maxWidth: 240,
      paddingX: 12,
      spacingHorizontal: 48,
      spacingVertical: 10,
      initialExpandLevel: -1,
    })
    currentMM = map
    await map.setData(toMarkmapNode(props.data))
    if (currentMM !== map) return

    const { y1, y2 } = map.state.rect
    svgHeight.value = Math.max(400, Math.ceil(y2 - y1 + 40))
    await nextTick()
    if (currentMM === map) await map.fit()
  } catch (err) {
    console.error('MindMap render error:', err)
  }
}

// 下载 SVG
function downloadSVG() {
  const svgEl = getSvgEl()
  if (!svgEl) return

  // 克隆一份来加白底（否则透明背景下载后不好看）
  const clone = svgEl.cloneNode(true)
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

onMounted(render)

watch(() => props.data, render, { deep: true, flush: 'post' })

onBeforeUnmount(() => {
  currentMM?.destroy()
  currentMM = null
})
</script>

<style scoped>
.mindmap-wrapper {
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--border);
}

.mindmap-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-hover);
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
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 36px;
}

.btn-download:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}

.mindmap-inner {
  width: 100%;
  min-height: 400px;
}

.mindmap-svg {
  width: 100%;
  display: block;
  min-height: 400px;
}

/* 响应式 */
@media (max-width: 639px) {
  .mindmap-toolbar {
    padding: 8px 12px;
  }
  .btn-download {
    padding: 6px 12px;
    font-size: 0.8rem;
  }
}
</style>
