# 模块 2.5：B站 Cookies 支持 — 设计规格

> 日期：2026-06-27 | 状态：已完成（补写）

## 1. 概述

B站部分接口需要登录态。用户在浏览器中登录 B站 后，把 cookies 导出并粘贴到应用中，后端用这些 cookies 模拟已登录状态去抓取视频信息。

## 2. 为什么需要 cookies

B站对未登录用户限制较多：
- 部分番剧/影视需要大会员 → 登录后才能获取元数据
- 部分接口直接返回 412/403 无权限 → 登录后正常
- yt-dlp 本身支持 `--cookies` 参数加载 Netscape 格式的 cookies 文件

YouTube 不需要此步骤（用 `youtube-transcript-api` 绕过限制）。

## 3. 前端：CookieGuide.vue

### 交互流程

1. **可折叠面板**：默认收起，B站用户需要时点击展开
2. **4 步图文引导**：
   - 步骤 1：用 Chrome 打开 bilibili.com 并登录
   - 步骤 2：安装 "EditThisCookie" 或类似扩展
   - 步骤 3：导出 cookies（Netscape 格式）
   - 步骤 4：粘贴到下方输入框
3. **输入区**：
   - textarea 接收 cookies 文本
   - 自动检测格式有效性：按行 `\t` 分割，检查是否为 Netscape 格式
   - 格式无效时：红色提示"格式不对"
   - 格式有效时：绿色提示"已检测到 N 条 cookies"
4. **状态持久化**：cookies 文本通过 `emit` 事件传给 App.vue，在分析时一并发送

### Cookies 格式检测

Netscape 格式每行 7 个字段（Tab 分隔）：
```
domain	flag	path	secure	expiration	name	value
.bilibili.com	TRUE	/	TRUE	1234567890	DedeUserID	123456
```

简易检测：按 `\t` `\n` 分割，检查是否 >= 3 行有效记录。

## 4. 后端：cookies 处理

### 流转

```
前端 textarea → ParseRequest.cookies (str)
     ↓
ytdlp_service.parse_video_info(cookies=cookies_text)
     ↓
tempfile.NamedTemporaryFile(suffix=".txt") → 写入 cookies 文本
     ↓
cmd = ["python3", "-m", "yt_dlp", "--cookies", tmp_file_path, ...]
     ↓
finally: os.unlink(tmp_file_path)  ← 用完即删，不留存
```

同样逻辑也用于：
- 字幕提取（`subtitle_service.py`）
- 未来视频下载

## 5. 错误提示优化

与早期仅显示 "B站需要登录" 不同，现在根据情况分级提示：

| 情况 | 提示 | 自动行为 |
|------|------|---------|
| B站 无 cookies → 解析失败 | "B站需要登录才能获取视频信息。请在下方展开「B站 Cookies」面板..." | 自动展开 CookieGuide |
| B站 cookies 过期 → 解析失败 | "cookies 已过期或无效，请重新获取并粘贴" | 自动展开 CookieGuide |
| B站 有 cookies → 字幕提取失败 | 不再崩溃，降级为"该视频没有可用字幕" | 无 |
| AI 分析中 B站 失败 | 同上，进度条保留显示 ❌ | 显示重试按钮 |

## 6. 安全考量

- 临时文件创建在系统临时目录（`tempfile` 默认 `/tmp`），进程退出后系统自动清理
- 文件名随机生成，无规律
- 即使 `finally` 块未执行（进程被 kill），文件也在临时目录中，系统会定期清理
- cookies 不记日志、不入库、不缓存在内存中超过请求周期

## 7. 验证标准

| 场景 | 预期 |
|------|------|
| B站 无 cookies 解析 | 提示需要 cookies + 自动展开面板 |
| 粘贴无效 cookies（少于 3 行有效记录） | 提示"格式不对" |
| 粘贴有效 cookies（>=3 行有效记录） | 提示"已检测到 N 条" |
| B站 有有效 cookies 解析 | 正常获取视频信息 |
| 前端构建 | 编译通过 |
