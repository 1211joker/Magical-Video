<template>
  <div class="issues-page">
    <header class="page-header">
      <h1 class="page-title">问题及优化</h1>
      <p class="page-desc">开发过程中的技术挑战、解决方案与项目不足</p>
    </header>

    <!-- 已解决问题 -->
    <section class="issues-section">
      <h2 class="section-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 11 12 14 22 4"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
        已解决问题
      </h2>

      <div class="issue-list">
        <div v-for="item in solvedIssues" :key="item.id" class="issue-card card">
          <div class="issue-header">
            <span class="issue-badge solved">已解决</span>
            <h3 class="issue-title">{{ item.title }}</h3>
          </div>
          <p class="issue-desc">{{ item.description }}</p>
          <div class="issue-solution">
            <span class="solution-label">解决方案</span>
            <span>{{ item.solution }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 待解决问题 / 项目不足 -->
    <section class="issues-section">
      <h2 class="section-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        待解决与项目限制
      </h2>

      <div class="issue-list">
        <div v-for="item in pendingIssues" :key="item.id" class="issue-card card">
          <div class="issue-header">
            <span class="issue-badge pending">待解决</span>
            <h3 class="issue-title">{{ item.title }}</h3>
          </div>
          <p class="issue-desc">{{ item.description }}</p>
          <p v-if="item.impact" class="issue-impact">{{ item.impact }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
const solvedIssues = [
  {
    id: 17,
    title: '大文件由浏览器直接下载',
    description: '旧版页面把完整视频读成 Blob 后才触发保存，文件越大，页面内存占用越高。',
    solution: '文件准备期间，页面只查询任务状态。准备完成后，浏览器的下载管理器直接接收文件并显示传输进度。',
  },
  {
    id: 15,
    title: 'AI 问答现在可以连续追问',
    description: '旧版问答只发送当前问题，遇到「第二点能再展开讲讲吗」这样的追问时，模型看不到上一轮回答。',
    solution: '同一聊天会发送最近 5 轮已完成的问答。用真实视频打乱三条建议的原顺序后追问，DeepSeek 正确展开了上一轮回答里重新编号的第二点。',
  },
  {
    id: 16,
    title: '思维导图精简并默认全部展开',
    description: '旧版导图把例子和细节拆成许多节点，默认折叠部分分支，浏览时需要逐个打开。',
    solution: '将相近内容归到同一主题，保留最多 5 个主主题，每个主题最多 3 个支撑要点。打开时自动展开并适配画布。真实视频测试中，21 个节点首次打开便全部可见。',
  },
  {
    id: 1,
    title: 'B站 412/403 拦截',
    description: 'B站对无 cookies 请求返回 412 或 403，导致无法获取视频信息和字幕。使用浏览器导出的 Netscape 格式 cookies 进行认证。',
    solution: '实现 cookies 粘贴功能，解析 Netscape 格式，注入 yt-dlp 和 API 请求中；自动检测关键登录字段（DedeUserID、SESSDATA、bili_jct）是否完整。',
  },
  {
    id: 2,
    title: 'YouTube 部分视频解析时出现 403',
    description: '早期使用默认 Web 客户端时，部分视频的可下载格式无法获取。',
    solution: '解析和下载使用 yt-dlp 的 Android 客户端配置。可选清晰度取决于平台返回的格式。',
  },
  {
    id: 3,
    title: 'B站字幕提取失败',
    description: '早期流程依赖视频元数据中的字幕地址，部分视频缺少该字段，分析无法继续。',
    solution: '使用 yt-dlp 将可用字幕下载到临时目录，再解析 VTT、JSON 等格式。字幕服务提供给 AI 的纯文本，也返回供页面显示的带时间戳片段。',
  },
  {
    id: 4,
    title: 'B站 cookies 校验不准确',
    description: '早期 cookies 校验仅检查行数 ≥ 3，但用户粘贴不完整 cookies 时仍会通过校验，导致解析失败但无明确错误提示。',
    solution: '增加关键字段检测：必须包含 DedeUserID、SESSDATA、bili_jct 三个关键登录 cookie；缺少时给出明确提示。',
  },
  {
    id: 5,
    title: '长视频分析超时过早',
    description: '长视频字幕可能超过 8000 字，AI 分析超时（30s）。',
    solution: '字幕超过 25,000 字符时从首、中、尾三段取样。模型输出上限设为 10,000 tokens，分析请求的超时参数设为 120 秒。',
  },
  {
    id: 6,
    title: 'AI 分析结果过于泛泛',
    description: '旧版系统提示词导致 AI 输出高度概括、缺乏具体细节，知识型视频关键信息丢失。',
    solution: '重写系统提示词，要求四维度输出（概述/大纲/要点/总结），强制引用原文证据，避免过度概括，保留术语和数字。',
  },
  {
    id: 7,
    title: 'emoji 跨平台显示不一致',
    description: 'Windows / macOS / Linux 对 emoji 渲染差异大，部分 emoji 在某些平台上显示为方框或风格不一致。',
    solution: '主要操作图标使用 Feather 风格的内联 SVG，颜色跟随主题文字，保持不同平台上的样式一致。',
  },
  {
    id: 8,
    title: '前端单页面巨石架构',
    description: '所有功能（链接解析、AI 分析、视频下载）集中在一个 App.vue 中，代码 400+ 行，缺乏导航结构。',
    solution: '使用 Vue Router 管理首页、AI 解析、AI 问答和问题及优化四个页面。App.vue 负责共用布局。',
  },
  {
    id: 9,
    title: 'AI Q&A 系统提示词缺乏推理深度',
    description: '初版 Q&A 提示词仅要求"严格基于字幕回答 + 引用证据"，回答较为机械，缺乏思考过程和批判性视角，语气偏正式。',
    solution: '重写为思维链（CoT）系统提示词：五步内部推理流程（理解意图→检索证据→评估问题→组织回答→检查准确性）；加入批判性思考——识别错误理解并温和纠正；语气改为朋友聊天式（"嗯""打个比方"）；主动提供延伸建议和实例。',
  },
  {
    id: 10,
    title: 'Q&A 传递给 AI 的上下文信息不完整',
    description: 'Q&A 请求中 analysis_summary 字段只包含概述和总结，缺少内容大纲和关键要点，导致 AI 回答缺乏足够上下文支撑。',
    solution: '问答请求同时发送概述、带时间段的大纲、附原文证据的关键要点和总结，供模型定位相关字幕。',
  },
  {
    id: 11,
    title: '页面切换导致分析状态丢失',
    description: '从 AI解析 页面切换到其他页面（如 AI问答）后再返回，之前解析的视频信息、AI 分析结果、B站 Cookies 全部丢失，需要重新输入和解析。',
    solution: '使用 localStorage + Vue watch 实现状态持久化：onMounted 自动恢复 urlInput / videoInfo / analysisResult / cookies；watch 监听变化自动保存。数据在页面刷新后仍存在，重新解析时自动覆盖旧数据。',
  },
  {
    id: 12,
    title: 'YouTube 视频、封面和字幕的代理配置不一致',
    description: '早期代理配置只用于 yt-dlp，封面与字幕请求可能因为连不上 YouTube 而超时。',
    solution: '后端验证直连或代理是否可用，解析、封面、字幕和下载共用检测成功的线路。连接失败时，页面会弹窗提示并提供重试入口。',
  },
  {
    id: 13,
    title: '思维导图空白 — Vue 3.5 模板 hoisting',
    description: '分析完成后切换到思维导图选项卡显示空白，控制台报 "Missing ref owner context. ref cannot be used on hoisted vnodes"。Vue 3.5 模板编译器将 Transition 内的 MindMap 组件根 SVG 元素静态提升，ref 无法绑定。',
    solution: '改用 div ref + querySelector("svg") 获取 DOM 元素，绕过 Vue 模板 ref 的 hoisting 限制。更稳健的模式 — 不依赖编译器对 ref 的处理行为。',
  },
  {
    id: 14,
    title: '导航栏冗余 — 独立下载页面形同虚设',
    description: 'AI 解析页面已内嵌完整的视频下载功能（DownloadSection 组件），导航栏中独立的"视频下载"栏目造成重复入口，用户困惑。',
    solution: '删除导航栏"视频下载"链接、/download 路由、DownloadPage.vue 整个文件。导航精简为 4 项：首页 / AI解析 / AI问答 / 问题及优化。',
  },
]

const pendingIssues = [
  {
    id: 101,
    title: 'YouTube 高清下载选项可能缺失',
    description: '当前使用 yt-dlp 的 Android 客户端配置，部分视频返回的下载格式较少。',
    impact: '若平台未返回高清格式，页面只能提供已有清晰度。',
  },
  {
    id: 102,
    title: '批量处理和播放列表支持',
    description: '当前按单个视频处理链接，用户需要逐个解析或下载。',
  },
  {
    id: 104,
    title: '大文件需要服务器临时磁盘空间',
    description: '服务端先准备完整视频，再由浏览器接收。准备期间页面会显示等待状态。',
    impact: '大文件需要更多临时磁盘空间，浏览器开始接收前也可能等得更久。',
  },
  {
    id: 105,
    title: '缺少用户自定义分析选项',
    description: 'AI 分析使用固定提示词，无选项让用户自定义分析重点（如"只看技术要点""提取所有数据"等）。',
    impact: '用户无法按需定制分析内容。',
  },
  {
    id: 106,
    title: '缺少分析与下载历史',
    description: '浏览器会保留最近一次分析结果，目前没有历史列表来查找更早的分析或下载。',
    impact: '回看更早的视频分析可能需要再次调用 AI。',
  },
  {
    id: 107,
    title: 'B站部分画质和视频需要账号权限',
    description: '可用画质和视频取决于登录 Cookie 对应账号的权限。',
  },
]
</script>

<style scoped>
.issues-page {
  padding-top: 32px;
}

.page-header {
  text-align: center;
  margin-bottom: 36px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.page-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
}

/* ===== 章节 ===== */
.issues-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ===== 问题卡片 ===== */
.issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-card {
  padding: 20px 24px;
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.issue-badge {
  flex-shrink: 0;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.issue-badge.solved {
  background: var(--bg-hover);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.issue-badge.pending {
  background: var(--bg-card);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.issue-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
}

.issue-desc {
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.issue-solution {
  font-size: 0.85rem;
  line-height: 1.7;
  color: var(--text-secondary);
  padding: 10px 14px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--border-strong);
}

.solution-label {
  margin-right: 0.5em;
  font-weight: 700;
  color: var(--text-primary);
}

.issue-impact {
  font-size: 0.83rem;
  color: var(--text-muted);
  font-style: italic;
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .issues-page {
    padding-top: 24px;
  }
  .page-title {
    font-size: 1.4rem;
  }
  .page-desc {
    font-size: 0.88rem;
  }
  .page-header {
    margin-bottom: 28px;
  }
  .issue-card {
    padding: 16px;
  }
  .issue-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
