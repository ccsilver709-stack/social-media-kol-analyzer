---
name: social-media-kol-analyzer
version: 1.0.0
description: "多平台 KOL 内容采集与数据分析工具。输入 YouTube / TikTok / Instagram / Facebook 链接，自动识别平台并按优先级抓取：YouTube 走 yt-dlp，TikTok/Instagram 走 oEmbed 公开 API，Facebook 走浏览器兜底。输出统一格式的视频标题、内容描述、博主名称、粉丝量、观看量、点赞数、评论数，并自动计算粉丝互动率。适用于 KOL 合作效果追踪、社媒内容汇总、竞品红人分析等场景。"
metadata:
  requires:
    bins: ["python3", "yt-dlp"]
  platforms: ["YouTube", "TikTok", "Instagram", "Facebook"]
---

# 多平台 KOL 内容采集分析工具

一套跨平台的 KOL 数据采集方法论，按平台自动选择最优抓取通道，输出统一结构化数据。

## 触发条件

命中以下任一情况即进入本 Skill：

1. 用户给出 YouTube / TikTok / Instagram / Facebook 链接，要求抓取视频数据（观看量、点赞、评论、粉丝量、内容概要）
2. 用户要求批量处理 KOL 表格中的社媒链接并回填数据
3. 用户要求计算 KOL 互动率 / 粉丝互动率
4. 用户提到"KOL 数据采集""社媒数据分析""红人监控"等关键词

## 平台识别与抓取优先级

| 平台 | URL 特征 | 第一通道 | 兜底通道 | 可获取字段 |
|---|---|---|---|---|
| YouTube | youtube.com/watch, youtu.be, youtube.com/shorts | yt-dlp（脚本自动安装） | — | 标题、描述、博主、粉丝量、观看量、点赞、评论、发布日期、时长、标签 |
| TikTok | tiktok.com/@user/video/ID | oEmbed API | 浏览器 | 标题（含完整描述）、博主名称、博主ID、封面图 |
| Instagram | instagram.com/reel/, /p/, /reels/ | oEmbed API（注意 /reels/ 复数需转 /reel/ 单数） | 浏览器 | 标题（含完整描述）、博主名称、博主ID、封面图 |
| Facebook | facebook.com/reel/, /photo.php, /watch/ | 浏览器（oEmbed 需 access token） | — | 博主名称、可见描述、点赞/评论/分享数 |

> ⚠️ **关键经验**：Instagram 的 `/reels/`（复数）URL 调用 oEmbed 会失败，必须自动转换为 `/reel/`（单数）后再调用。

## 工作流

### Step 1：单链接抓取

使用主脚本 `scripts/fetch_kol_data.py`：

```bash
python scripts/fetch_kol_data.py "<URL>" --json
```

参数说明：
- `url`：社媒视频链接（支持所有平台）
- `--json`：输出 JSON 格式（推荐，便于解析）
- `--max-comments N`：YouTube 评论抓取上限（默认 0，不抓评论）
- `--verbose`：输出详细抓取过程

输出统一 JSON 结构：

```json
{
  "platform": "youtube|tiktok|instagram|facebook|unknown",
  "url": "原始链接",
  "fetch_channel": "yt-dlp|oembed|browser|failed",
  "video": {
    "title": "视频标题",
    "description": "视频描述/正文",
    "uploader": "博主名称",
    "uploader_id": "博主ID/用户名",
    "channel_url": "博主主页链接",
    "subscriber_count": 12345,
    "view_count": 12345,
    "like_count": 123,
    "comment_count": 12,
    "upload_date": "20260815",
    "duration": 120,
    "thumbnail_url": "封面图链接"
  },
  "engagement": {
    "view_engagement_rate": 0.0123,
    "fan_engagement_rate": 0.0456
  },
  "error": null
}
```

互动率计算口径：
- **观看互动率** = (点赞数 + 评论数) / 观看量（仅 YouTube 有观看量时计算）
- **粉丝互动率** = (点赞数 + 评论数) / 粉丝量（所有平台通用，粉丝量带 k/w 单位时自动换算）

### Step 2：批量抓取 + 飞书表格回填

使用批量脚本 `scripts/batch_fetch_and_write.py`：

```bash
python scripts/batch_fetch_and_write.py \
  --url "https://mammotion.feishu.cn/wiki/xxx" \
  --sheet-name "KOL" \
  --url-col "F" \
  --start-row 56 \
  --end-row 80 \
  --view-col "G" \
  --fans-col "H" \
  --like-col "I" \
  --comment-col "J" \
  --summary-col "O" \
  --type-col "P"
```

参数说明：
- `--url`：飞书表格链接
- `--sheet-name`：子表名
- `--url-col`：链接所在列（如 F）
- `--start-row / --end-row`：处理行范围
- `--view-col / --fans-col / --like-col / --comment-col`：数据回填列
- `--summary-col`：内容概要回填列
- `--type-col`：博主类型回填列
- `--dry-run`：仅抓取不写入，预览结果
- `--delay 1`：请求间隔秒数（默认 0.5，避免限流）

脚本会自动：
1. 读取指定范围内的链接
2. 逐行识别平台并抓取
3. YouTube 行回填观看量/粉丝/点赞/评论 + 内容概要 + 博主类型
4. 非 YouTube 行回填粉丝/点赞/评论（如有）+ 内容概要 + 博主类型，观看量列留空
5. 自动计算并回填互动率到指定列
6. 输出处理报告（成功/失败/跳过统计）

### Step 3：Facebook 浏览器兜底

当 oEmbed 通道失败时（主要是 Facebook），使用浏览器工具手动打开链接：

1. 用 `open_url_in_browser` 打开 Facebook 链接
2. 等待页面加载，关闭登录弹窗（点击 X 或按 ESC）
3. 从页面可见区域提取：博主名称、视频描述、点赞/评论/分享数
4. 手动整理内容概要和博主类型
5. 用 `lark-cli sheets +cells-set` 写入对应单元格

> Facebook 的 oEmbed API 需 Graph API access token，无 token 时只返回嵌入代码不含元数据，因此浏览器是唯一可靠通道。

## 博主类型分类参考

基于抓取到的频道名和内容，按以下维度分类：

| 类型 | 典型特征 | 示例频道名 |
|---|---|---|
| 科技/产品测评博主 | 内容以深度测评、参数对比、功能教程为主 | SmartHome yourself, Nicolas Tesla |
| 家庭生活/亲子vlog | 内容围绕家庭日常、孩子、花园改造 | charlyne_family, familie_am_feldrand |
| 庄园/城堡翻新/家居 | 内容围绕庄园/城堡/老房翻新、家居好物 | Chateau Love, lepetitmanoir37, Cosy Casa |
| 草坪养护/园艺专业 | 内容专注草坪护理、园艺技术、割草机评测 | lawnly_rasengesundheit, larchipelle |
| 旅行/户外生活方式 | 内容以旅行、房车、户外生活为主 | Reiseschrauber, Podróże Busem, kopf.gulasch |
| 情侣/花园改造博主 | 内容围绕情侣日常、花园/城堡改造 | xavandtash |
| 海外移居/乡村生活vlog | 内容围绕跨国移居、乡村新生活 | A New Life in France |
| DIY自建房屋/生活方式 | 内容围绕自建房屋、DIY项目、生活日常 | selbstbautdiefrau |
| 宠物/生活方式博主 | 内容围绕宠物日常、生活好物 | sinascolorcats |
| 科技/智能生活博主 | 内容以智能产品、科技好物推荐为主 | pino.gpt |

## 注意事项

1. **yt-dlp 自动安装**：首次运行 YouTube 抓取时脚本会自动 `pip install yt-dlp`，属正常现象
2. **oEmbed 限流**：TikTok/Instagram oEmbed 无严格限流，但批量抓取时建议间隔 ≥0.5 秒
3. **粉丝量单位换算**：非 YouTube 平台粉丝量常带 k（千）/ w（万）单位，脚本自动换算为纯数字
4. **评论数为 0**：YouTube Shorts 和部分视频评论数可能返回 0，这是真实数据非缺失
5. **Facebook 登录墙**：浏览器打开 Facebook 时会弹出登录框，关闭后仍可看到公开内容的作者和描述
6. **数据时效**：所有数据为抓取时刻的实时值，观看量/点赞数会随时间变化，建议标注抓取日期

## 脚本清单

| 脚本 | 用途 |
|---|---|
| `scripts/fetch_kol_data.py` | 单链接多平台统一抓取主入口 |
| `scripts/fetch_youtube.py` | YouTube yt-dlp 抓取模块（独立可用） |
| `scripts/fetch_oembed.py` | TikTok/Instagram oEmbed API 抓取模块（独立可用） |
| `scripts/batch_fetch_and_write.py` | 批量抓取 + 飞书表格回填 |

## 参考文档

- `references/platform-endpoints.md`：各平台 API 端点、参数、返回字段详解
- `references/error-handling.md`：常见错误码与处理方案

===== 全文完 =====
