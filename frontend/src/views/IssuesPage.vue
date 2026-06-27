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
            <span class="solution-label">解决方案：</span>
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
        待解决 &amp; 项目不足
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
    id: 1,
    title: 'B站 412/403 拦截',
    description: 'B站对无 cookies 请求返回 412 或 403，导致无法获取视频信息和字幕。使用浏览器导出的 Netscape 格式 cookies 进行认证。',
    solution: '实现 cookies 粘贴功能，解析 Netscape 格式，注入 yt-dlp 和 API 请求中；自动检测关键登录字段（DedeUserID、SESSDATA、bili_jct）是否完整。',
  },
  {
    id: 2,
    title: 'YouTube SABR 流式拦截 (403 Forbidden)',
    description: 'YouTube SABR（Server And Browser Rendering）机制对默认 web client 返回 streaming 403，阻止下载。',
    solution: '切换为 Android player client 绕过 SABR：--extractor-args "youtube:player_client=android"。代价是仅能获取 360p 格式。',
  },
  {
    id: 3,
    title: 'B站字幕提取崩溃（--write-subs 无输出）',
    description: 'yt-dlp 的 --write-subs 和 --write-auto-subs 对 B站 不生效，dump-json 中也不包含字幕 URL，导致 AI 分析步骤因缺少字幕而崩溃。',
    solution: '改用 yt-dlp --write-subs 直接下载 VTT 文件到临时目录，再用 Python 读取文件内容。重写 subtitle_service 同时返回纯文本（给 AI）+ 结构化片段（给前端）。',
  },
  {
    id: 4,
    title: 'B站 cookies 校验不准确',
    description: '早期 cookies 校验仅检查行数 ≥ 3，但用户粘贴不完整 cookies 时仍会通过校验，导致解析失败但无明确错误提示。',
    solution: '增加关键字段检测：必须包含 DedeUserID、SESSDATA、bili_jct 三个关键登录 cookie；缺少时给出明确提示。',
  },
  {
    id: 5,
    title: 'AI 分析超时',
    description: '长视频字幕可能超过 8000 字，AI 分析超时（30s）。',
    solution: '扩展 max_chars 到 15000，max_tokens 到 4000，截断策略改为首 20% + 中 60% + 尾 20% 覆盖视频全程；超时从 30s 提高到 60s。',
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
    solution: '全站替换为 Feather 风格 SVG 内联图标，统一 stroke-width="2"，颜色跟随当前文字色（currentColor），无跨平台差异。',
  },
  {
    id: 8,
    title: '前端单页面巨石架构',
    description: '所有功能（链接解析、AI 分析、视频下载）集中在一个 App.vue 中，代码 400+ 行，缺乏导航结构。',
    solution: '引入 vue-router，拆分为四页面（首页/AI解析/视频下载/问题及优化），App.vue 变布局壳。',
  },
]

const pendingIssues = [
  {
    id: 101,
    title: 'YouTube 高清下载受限（仅 360p）',
    description: 'Android player client 虽然能绕过 SABR，但缺少 GVS PO Token 无法获取 HD DASH 格式（720p+）。需要实现 PO Token 生成逻辑。',
    impact: 'YouTube 用户无法下载高清视频，体验打折。',
  },
  {
    id: 102,
    title: '不支持批量下载',
    description: '当前仅支持单链接输入，无法批量处理播放列表或多个链接。',
    impact: '用户需要逐个粘贴链接，使用效率低。',
  },
  {
    id: 103,
    title: '不支持播放列表解析',
    description: 'YouTube 播放列表链接仅解析列表页面而非视频内容。',
    impact: '遇到播放列表链接时用户体验差。',
  },
  {
    id: 104,
    title: '流式下载稳定性不足',
    description: '当前 yt-dlp → stdout → StreamingResponse → 前端 Blob 的流式代理架构，在网络不稳定时容易中途失败，且有内存占用问题。',
    impact: '大文件下载容易失败，需要重试。',
  },
  {
    id: 105,
    title: '缺少用户自定义分析选项',
    description: 'AI 分析使用固定提示词，无选项让用户自定义分析重点（如"只看技术要点""提取所有数据"等）。',
    impact: '用户无法按需定制分析内容。',
  },
  {
    id: 106,
    title: '无下载历史记录',
    description: '没有本地或服务端记录已分析/已下载的视频。',
    impact: '用户无法查看历史操作，重复分析浪费 AI 配额。',
  },
  {
    id: 107,
    title: 'B站 高画质需会员 cookies',
    description: 'B站 1080p+ 和付费视频需要大会员 cookies，免费用户仅能下载较低画质。',
    impact: '非会员用户体验受限。',
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
