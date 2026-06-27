# Discovery Plan: AI 万能视频下载总结器

**日期**: 2026-06-27
**产品阶段**: 新产品（纯粹想法阶段）
**Discovery 问题**: 这个基于 yt-dlp + AI 摘要的视频下载工具是否值得做？

---

## Ideas Explored

从 PM/Designer/Engineer 三视角生成 15 个创意，筛选出 4 个核心创意：

| # | 创意 | 来源 | 简述 |
|---|------|------|------|
| 1 | 链接智能粘贴 + AI 摘要预览 | PM | 粘贴链接后自动识别平台、展示元数据、生成摘要 |
| 2 | 字幕提取 + DeepSeek AI 分析 | PM | 提取平台字幕 → DeepSeek 生成摘要+要点 |
| 3 | 多平台一键下载 (yt-dlp) | PM | YouTube/B站/抖音 一个入口搞定 |
| 7 | 思维导图可视化 | Designer | 知识树可视化，可保存为图片 |

---

## 实验 1 结果：技术可行性验证（实测）

### 测试环境
- 设备: macOS arm64
- yt-dlp: 2025.10.14.232845.dev0 (nightly)
- 代理: http://127.0.0.1:7892 (Shadowsocks)
- 依赖: curl_cffi 已安装（支持 impersonate）

### 逐平台结果

| 平台 | 元数据提取 | AI 可用字幕 | 下载可行性 | 备注 |
|------|-----------|------------|-----------|------|
| **YouTube** | ✅ 成功 | ⚠️ 需 PO Token | ✅ 可行 | 最成熟的平台，字幕目前需要 yt-dlp 未完全解决的 PO token 问题 |
| **B站** | ✅ 成功（需 cookies） | ✅ 成功提取 `.srt` | ✅ 可行 | 从 Chrome 导出 cookies 即可；字幕下载完美支持 |
| **TikTok** | ❌ 失败 | ❌ | ❌ | 即使有 impersonate + curl_cffi，"Unable to extract webpage video data" |
| **Douyin** | ❌ 失败 | ❌ | ❌ | 已知 Bug，yt-dlp #9667。需 cookies 但即使提供也失败 |

### 关键发现

1. **B站是最佳切入点**：cookies 认证后元数据+字幕完美支持
2. **YouTube 可靠但字幕需要修复**：PO token 问题在 yt-dlp 社区已知，有解决方案
3. **抖音/TikTok 短期不可用**：需等待 yt-dlp 社区修复或引入 Playwright 等替代方案
4. **MPC 建议**：MVP 先做 YouTube + B站，抖音/TikTok 列为"实验性支持"或后续版本

---

## Critical Assumptions

| # | 假设 | 类别 | 影响 | 不确定性 | 优先级 |
|---|------|------|------|---------|--------|
| 1 | 抖音/TikTok 反爬可以绕过 | 可行性 | 高 | 高 | 🔴 已验证失败 |
| 2 | B站通过 cookies 可长期稳定使用 | 可行性 | 高 | 中 | 🟡 已验证可行，需维护 |
| 3 | 用户接受 20-60 秒等待 AI 分析 | 价值 | 中 | 低 | 🟢 不担心 |
| 4 | 无字幕视频可以用 Whisper 兜底 | 价值 | 中 | 中 | 🟡 后续 Feature |
| 5 | 纯 Web 下载体验可接受 | 价值 | 中 | 中 | 🟡 需实际测试 |
| 6 | 带宽成本可承受（非商用规模） | 可行性 | 低 | 低 | 🟢 不担心 |
| 7 | 思维导图有用户价值 | 价值 | 低 | 低 | 🟢 锦上添花 |

---

## Validation Experiments

| # | 验证假设 | 方法 | 结果 | 结论 |
|---|---------|------|------|------|
| 1 | 抖音/TikTok 技术支持度 | 技术 Spike（20+ 真实 URL 测试） | ✅ 已完成 | **抖音/TikTok 不可用**，MVP 排除 |
| 2 | B站 技术支持度 | 技术 Spike | ✅ 已完成 | **B站可用**（需 cookies），进入 MVP |
| 3 | YouTube 字幕支持度 | 技术 Spike | ✅ 已完成 | **YouTube 元数据OK**，字幕需解决 PO token |
| 4 | 整体市场验证 | Concierge MVP（手动服务 3-5 人） | ⏳ 可选 | 上线后可做 |

---

## 技术架构建议（基于实验结论）

```
用户浏览器
  │
  ├── YouTube → yt-dlp (需处理 PO token)
  ├── B站     → yt-dlp + --cookies-from-browser
  └── (抖音/TikTok → 暂不支持，后续评估)
         │
         ▼
    DeepSeek AI 分析（字幕 → 摘要 + 要点 + 导图）
         │
         ▼
    视频流式下载（服务器中转）
```

---

## Decision Framework

- 抖音/TikTok 在 MVP 阶段 **排除**
- YouTube + B站 作为 MVP **核心平台**
- 后续抖音/TikTok 支持取决于：yt-dlp 社区修复进度 or Playwright 方案成熟度
- 建议 MVP 上线后再补做 **Concierge 验证**（找 3-5 人用用看）
