# 模块 2：链接解析与视频信息展示 — 设计规格

> 日期：2026-06-27 | 状态：已完成（补写）

## 1. 概述

用户粘贴视频链接 → 后端调用 yt-dlp 抓取元数据 → 前端以卡片形式展示封面、标题、时长、简介等信息。

## 2. 数据流

```
用户粘贴链接 → 点"开始解析"
     ↓
POST /api/parse  {url, cookies?}
     ↓
ytdlp_service.parse_video_info()
     ├─ 平台识别: 正则匹配 URL → youtube / bilibili / unsupported
     ├─ 不支持检测: TikTok/抖音等给出明确中文提示
     ├─ cookies处理: B站如需登录，cookies写入临时文件传给yt-dlp，用完即删
     ├─ 命令执行: python3 -m yt_dlp --dump-json --no-playlist <url>
     └─ JSON解析: 提取 title/duration/thumbnail/description/formats
     ↓
ParseResponse → 前端 VideoInfo.vue 卡片渲染
```

## 3. 后端接口

### POST /api/parse

请求：
```json
{"url": "https://...", "cookies": "Netscape格式cookies文本（可选）"}
```

响应（成功）：
```json
{
  "platform": "youtube",
  "title": "视频标题",
  "duration": 706,
  "thumbnail": "https://...",
  "description": "简介前500字",
  "webpage_url": "https://...",
  "formats": [
    {"format_id": "137+140", "resolution": "1080p", "filesize": 450000000, "ext": "mp4"},
    {"format_id": "136+140", "resolution": "720p", "filesize": 220000000, "ext": "mp4"}
  ]
}
```

### 平台识别规则

| URL 关键词 | 平台 | 备注 |
|-----------|------|------|
| `youtube.com` / `youtu.be` | youtube | 无需 cookies |
| `bilibili.com` / `b23.tv` | bilibili | 部分视频需 cookies |
| `tiktok.com` | unsupported | 明确提示"暂不支持 TikTok" |
| `douyin.com` | unsupported | 明确提示"暂不支持抖音" |
| 其他 | unsupported | 提示"暂不支持此平台" |

## 4. 格式过滤逻辑

yt-dlp 返回的原始格式列表很杂乱（纯视频流、纯音频流、合并流混在一起）。过滤规则：

1. 只要同时有视频编码 + 音频编码的格式（合并流）
2. 同一分辨率只保留一个（取体积最小的）
3. 按分辨率从高到低排序
4. 最多展示 6 个选项

## 5. 前端组件

### VideoInfo.vue

**显示内容**：
- 封面图（带平台标签：红色 YouTube、蓝色 B站，毛玻璃效果）
- 标题
- 时长（自动格式化为 分:秒 或 时:分:秒）
- 简介（最多 500 字，超出省略）

**边界处理**：
- 封面加载失败 → 占位图（灰色背景 + 图标）
- 无简介 → 不显示简介区
- duration 为 0 → 显示"时长未知"
- duration 为小数 → 自动取整（Pydantic v2 不会自动转）

### 封面图代理

B站 封面图有防盗链（检查 Referer 头），浏览器直接加载会 403。

解决：新增 `GET /api/thumbnail?url=...`，后端伪造 `Referer: bilibili.com` 去取图，流式返回给前端。加 1 天缓存减少重复请求。

## 6. 错误处理

| 场景 | 后端处理 | 前端表现 |
|------|---------|---------|
| B站 无 cookies | 检测 412/403 → RuntimeError | 错误横幅 + 自动展开 cookies 设置面板 |
| B站 cookies 过期 | 带了 cookies 仍 412/403 | "cookies 已过期或无效，请重新获取" |
| 视频私密/已删除 | 检测 "Private video" | "视频不可用（可能已删除或设为私密）" |
| 请求过于频繁 | HTTP 429 | "请求过于频繁，请稍等片刻再试" |
| yt-dlp 超时 | asyncio.TimeoutError | "解析超时" |
| 不支持平台 | identify_platform → unsupported | 红色错误横幅 + 平台名称 |

## 7. Cookies 安全处理

- 前端通过 textarea 接收用户粘贴的 Netscape 格式 cookies
- 后端收到后写入临时文件（`tempfile.NamedTemporaryFile`）→ 传给 yt-dlp `--cookies` 参数
- yt-dlp 调用完成后，无论成功失败，`finally` 块中删除临时文件
- cookies 不存入数据库、不记录日志

## 8. 验证标准

| 场景 | 预期 |
|------|------|
| YouTube 链接 | 正常返回标题、封面、时长、格式 |
| B站 链接（有 cookies） | 正常返回 |
| B站 链接（无 cookies） | 提示需要配置 cookies |
| TikTok 链接 | 提示"暂不支持 TikTok" |
| 无效链接 | 提示"暂不支持此平台" |
| 前端构建 | 编译通过 |
