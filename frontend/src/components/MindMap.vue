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
    <svg ref="svgContainer" class="mindmap-container" width="100%" :style="{ height: svgHeight + 'px' }"></svg>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const props = defineProps({
  data: {
    type: Object,
    required: true
  }
})

const svgContainer = ref(null)
const svgHeight = ref(500)
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
  if (!svgContainer.value || !props.data) {
    console.warn('[MindMap] render skipped', { hasContainer: !!svgContainer.value, hasData: !!props.data })
    return
  }

  // 清掉上次渲染的
  svgContainer.value.innerHTML = ''

  try {
    const markdown = toMarkdown(props.data)
    const transformer = new Transformer()
    const { root } = transformer.transform(markdown)

    currentMM = Markmap.create(
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

    // 动态计算 SVG 高度：等渲染完成后读取内容边界
    nextTick(() => {
      requestAnimationFrame(() => {
        const svg = svgContainer.value
        if (!svg) return
        // 查找 markmap 的 <g> 元素获取实际高度
        const g = svg.querySelector('g')
        if (g) {
          const bbox = g.getBBox()
          if (bbox.height > 0) {
            svgHeight.value = Math.max(400, Math.ceil(bbox.height + 40))
          }
        }
      })
    })
  } catch (err) {
    console.error('MindMap render error:', err)
  }
}

// 下载 SVG
function downloadSVG() {
  // 容器本身就是 SVG 元素
  const svgEl = svgContainer.value
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

.mindmap-container {
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
