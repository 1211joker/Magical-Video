# 模块 3：AI 分析 — 字幕提取 + DeepSeek + 进度推送 + 选项卡 UI

> 日期：2026-06-27 | 状态：已完成（补写）

## 1. 概述

把视频字幕提取出来 → 发给 DeepSeek AI 做四维度分析（概述/大纲/要点/总结/思维导图）→ 进度通过 SSE 实时推送 → 结果以选项卡形式展示。

## 2. 数据流

```
用户点"AI 分析"
     ↓
POST /api/analyze-stream  {url, cookies}
     ↓ (SSE 流式推送进度)
     
步骤1: 解析视频 — 同 /api/parse，复用以太已解析的数据
     ↓ SSE: {step:"parse", status:"done"}
     
步骤2: 提取字幕
     ├─ YouTube: youtube-transcript-api 库直接拉取
     ├─ B站: yt-dlp --write-subs 下载字幕文件 → 本地解析
     └─ 返回 SubtitleData(plain_text: str, segments: list[dict])
     ↓ SSE: {step:"subtitles", status:"done"}
     
步骤3: AI 分析
     ├─ 截断字幕到 25,000 字（首20%+中60%+尾20%）
     ├─ 调用 DeepSeek API（deepseek-v4-flash, max_tokens=10000）
     ├─ 解析返回的 JSON（四维度 + 思维导图）
     └─ 返回 AnalysisResult
     ↓ SSE: {step:"analyze", status:"done", result: {...}}
```

## 3. 字幕提取

### 为什么分平台处理

| 平台 | 方法 | 原因 |
|------|------|------|
| YouTube | `youtube-transcript-api` 库 | yt-dlp 受 PO Token 限制无法获取字幕 URL |
| B站 | yt-dlp `--write-subs` 直接下载 | `--dump-json` 不返回字幕 URL，必须下文件 |

### 字幕格式支持

B站 的字幕文件可能有多种格式，按优先级解析：
1. **JSON**（B站原生格式）：`[{"from": 1.0, "to": 3.5, "content": "文本"}]`
2. **VTT**：WebVTT 标准字幕格式
3. **SRT**：SubRip 字幕格式
4. **ASS**：Advanced SubStation Alpha 格式

### 字幕选优策略

按优先级选最佳语言版本：
1. 中文手动字幕（人工上传）
2. 英文手动字幕 → 中文自动字幕
3. 英文自动字幕
4. 都没有 → 返回 None（前端显示"暂无字幕"）

### SubtitleData 结构

```python
@dataclass
class SubtitleData:
    plain_text: str         # 纯文本（给 AI 分析用，片段间用空格连接）
    segments: list[dict]    # 结构化片段（给前端展示时间戳用）
    # 每个 segment: {"start_time": 1.0, "end_time": 3.5, "text": "字幕文本"}
```

关键：同一份字幕数据，AI 看到的是纯文本，前端看到的是带时间戳的片段。不会丢信息。

## 4. AI 分析服务

### 系统提示词设计

五维度输出（按优先级排序）：

1. **思维导图（核心输出）**：5-7 个一级分支，4 层深度，30+ 节点。每节点含具体信息（数字、术语、案例名）
2. **概述**：2-3 句话概括核心内容
3. **大纲**：4-8 个时间段，每段含时间、主题、详情
4. **关键要点**：5-8 个观点，附带原文引述作为证据
5. **总结**：2-4 条可执行结论

### 参数调优历史

| 参数 | 初版 | 最终 | 为什么改 |
|------|------|------|---------|
| 上下文截断 | 8,000 字 | 25,000 字 | 8K 不够 → AI 看不到细节 → 输出空洞 |
| max_tokens | 2,000 | 10,000 | 2K 被概述+大纲+要点占满 → 思维导图被截断 |
| 导图深度 | 无要求 | 4 层 | 无要求 → AI 默认输出 2 层 |
| 节点数 | 无要求 | ≥30 个 | 无要求 → 10 个左右 |
| 提示词示例 | "A""B" 占位符 | 真实知识示范 | 占位符 → AI 照猫画虎输出空洞 |
| 导图优先级 | 等同于其他 | 最高优先级 | 显式标注"思维导图是最重要的输出" |
| 超时 | 30s | 90s | 10K tokens 输出需要更长处理时间 |

### 截断策略

```
字幕全文 → 取首 20% + 中 60% + 尾 20%（覆盖视频全程）
```

而不是简单取前 25,000 字。这样 AI 能看到视频开头、中间和结尾，不会遗漏后半段的内容。

## 5. SSE 进度推送

### 为什么用 fetch + ReadableStream 而不是 EventSource

EventSource 只支持 GET 请求。但我们需要传 cookies（可能很长，超过 URL 长度限制），必须用 POST。所以用手动 fetch + 逐行解析 SSE。

### SSE 事件格式

```
data: {"step":"parse","status":"processing","message":"正在获取视频信息..."}

data: {"step":"parse","status":"done","message":"视频信息获取完成"}

data: {"step":"subtitles","status":"processing","message":"正在提取字幕..."}

data: {"step":"subtitles","status":"done","message":"字幕提取完成（1234 条）"}

data: {"step":"analyze","status":"processing","message":"AI 正在分析（约需 30-60 秒）..."}

data: {"step":"analyze","status":"done","message":"分析完成","result":{...完整AnalysisResult}}

data: {"step":"error","status":"failed","message":"错误描述"}
```

### 前后端超时对齐

- 后端 `AI_ANALYSIS_TIMEOUT = 90s`（DeepSeek 调用超时）
- 前端 fetch 无独立超时（跟随后端响应）
- 前端 AbortController 支持用户取消

## 6. 前端组件

### AnalysisResult.vue — 选项卡布局

六个选项卡通过 `v-show` 切换（不是 `v-if`，避免重新渲染思维导图）：

| 选项卡 | 内容组件 | 展示方式 |
|--------|---------|---------|
| 📝 概述 | 文本 | 概述文字段落 |
| 📋 大纲 | 列表 | 时间轴：时间徽章 + 主题 + 详情 |
| 🔑 要点 | 卡片 | 编号卡片 + 蓝色左边框证据引用（blockquote） |
| 💡 总结 | 卡片 | 绿色卡片 + 编号列表 |
| 🧠 思维导图 | MindMap 子组件 | 交互式 SVG，可缩放/展开/下载 |
| 💬 字幕 | SubtitleViewer 子组件 | 带时间戳的滚动列表 |

选项卡样式：横向排列的药丸按钮，active 态有背景色和阴影，hover 态有反馈。

### MindMap.vue — 思维导图渲染

**关键坑**：markmap 的 `Markmap.create()` 内部调用 `d3.select(container).append("g")`。当容器是 `<div>` 时，d3 创建 HTML `<g>` 元素，浏览器忽略它。容器必须是 `<svg>` 元素。

```html
<!-- 正确 -->
<svg ref="svgContainer" width="100%" height="500"></svg>

<!-- 错误（不渲染） -->
<div ref="svgContainer"></div>
```

**功能**：
- 交互式缩放/平移（markmap 内置）
- 节点展开/折叠（点击圆圈）
- "⬇️ 下载思维导图"按钮：导出带白底的 SVG 文件

### SubtitleViewer.vue — 字幕查看器

- 可滚动容器（max-height: 500px）
- 每条：时间戳徽章（MM:SS 格式，黑底白字）+ 字幕文本
- 奇偶行交替背景色（便于阅读）
- 空状态："📜 暂无字幕数据"

### App.vue — 进度条逻辑

进度条状态根据三步的实际完成情况计算：

| 状态 | 条件 | 标题显示 |
|------|------|---------|
| 分析中 | `analyzing == true` | "AI 分析进行中..." |
| 全部完成 | 三步都 `done` | "✅ AI 分析完成" |
| 有失败 | 任一步 `failed` | "AI 分析未完成" + 重试按钮 |
| 全部完成 | 不显示重试按钮 | 隐 |

失败后进度条不消失（保留 ❌ 状态），用户可以看到哪步出错了。

## 7. 错误处理

| 场景 | 后端 | 前端 |
|------|------|------|
| 无字幕 | 返回 None | "该视频没有可用字幕" |
| AI API Key 无效 | 401 → RuntimeError | 错误提示 + 建议检查 .env |
| AI 余额不足 | 402 → RuntimeError | "DeepSeek 账户余额不足" |
| AI 请求频繁 | 429 → RuntimeError | "请求过于频繁，请稍后重试" |
| AI JSON 解析失败 | 正则提取兜底 | 提取失败时提示"格式异常" |
| 字幕提取异常 | logging 记录 → 返回 None | 不崩溃，降级为"无字幕" |

## 8. 验证标准

| 场景 | 预期 |
|------|------|
| YouTube 视频分析 | 完整的四维度结果 + 思维导图 + 字幕时间戳 |
| B站 视频分析 | 同上 |
| 无字幕视频 | 所有维度正常，字幕选项卡显示"暂无字幕" |
| AI API 异常 | 进度条显示失败步骤 + 错误信息 + 重试按钮 |
| 选项卡切换 | 六个选项卡正常切换，思维导图不重复渲染 |
| 思维导图渲染 | markmap 交互式 SVG 正常显示 |
| 前端构建 | `npm run build` 编译通过 |
