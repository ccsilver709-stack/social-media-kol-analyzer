# 各平台 API 端点与返回字段详解

## YouTube（yt-dlp）

### 调用方式
通过 Python `yt_dlp` 库直接提取视频元数据，无需 API Key。

```python
import yt_dlp
ydl_opts = {"quiet": True, "no_warnings": True}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
```

### 支持的 URL 格式
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`

### 关键字段映射
| 输出字段 | yt-dlp 字段 | 说明 |
|---|---|---|
| title | title | 视频标题 |
| description | description | 视频描述（可能很长） |
| uploader | uploader / channel | 博主显示名 |
| uploader_id | channel_id / uploader_id | 频道ID |
| channel_url | channel_url / uploader_url | 频道主页链接 |
| subscriber_count | channel_follower_count | 粉丝数（部分频道可能为null） |
| view_count | view_count | 观看量 |
| like_count | like_count | 点赞数 |
| comment_count | comment_count | 评论数 |
| upload_date | upload_date | 发布日期（YYYYMMDD格式） |
| duration | duration | 时长（秒） |
| thumbnail_url | thumbnail | 封面图 |
| tags | tags | 标签列表 |

### 注意事项
- 粉丝数通过频道页获取，极少数频道可能返回 null
- Shorts 视频评论数可能为 0
- 首次运行需 `pip install yt-dlp`

---

## TikTok（oEmbed API）

### API 端点
```
GET https://www.tiktok.com/oembed?url=<TikTok视频URL>
```

### 支持的 URL 格式
- `https://www.tiktok.com/@username/video/VIDEO_ID`
- `https://www.tiktok.com/t/SHORT_CODE/`（短链会重定向）

### 返回字段
| 字段 | 类型 | 说明 |
|---|---|---|
| version | string | oEmbed 版本（固定 "1.0"） |
| type | string | 类型（固定 "video"） |
| title | string | **视频标题+完整描述文本**（关键字段） |
| author_name | string | 博主显示名 |
| author_url | string | 博主主页链接 |
| provider_name | string | 固定 "TikTok" |
| thumbnail_url | string | 封面图 URL |
| thumbnail_width | int | 封面宽度 |
| thumbnail_height | int | 封面高度 |
| html | string | 嵌入代码 |
| width | int | 嵌入宽度 |
| height | int/null | 嵌入高度 |

### 不提供的字段（需其他来源）
- 观看量、点赞数、评论数、分享数、粉丝量
- 发布日期、视频时长

### 注意事项
- 无需 API Key，公开接口
- 无严格限流，但批量请求建议间隔 ≥0.5 秒
- title 字段实际包含完整的视频描述文本，是内容概要的主要来源

---

## Instagram（oEmbed API）

### API 端点
```
GET https://www.instagram.com/api/v1/oembed/?url=<Instagram帖子URL>
```

### 支持的 URL 格式
- `https://www.instagram.com/reel/REEL_ID/`（Reels 视频，**单数**）
- `https://www.instagram.com/p/POST_ID/`（图片帖子）
- `https://www.instagram.com/tv/TV_ID/`（IGTV）

### ⚠️ 关键：URL 格式问题
`/reels/`（复数）URL 调用 oEmbed 会返回 404 错误，**必须转换为 `/reel/`（单数）**：

```python
import re
url = re.sub(r'instagram\.com/reels/', 'instagram.com/reel/', url)
```

### 返回字段
| 字段 | 类型 | 说明 |
|---|---|---|
| version | string | oEmbed 版本 |
| type | string | 类型（"rich" 或 "video"） |
| title | string | **帖子标题+完整描述文本**（关键字段） |
| author_name | string | 博主显示名 |
| author_url | string | 博主主页链接 |
| author_id | int | 博主数字 ID |
| media_id | string | 媒体 ID |
| provider_name | string | 固定 "Instagram" |
| thumbnail_url | string | 封面图 URL |
| thumbnail_width | int | 封面宽度 |
| thumbnail_height | int | 封面高度 |
| html | string | 嵌入代码 |
| width | int | 嵌入宽度 |
| height | int/null | 嵌入高度 |

### 不提供的字段
- 观看量、点赞数、评论数、粉丝量
- 发布日期（需从其他来源获取）

### 注意事项
- 无需 API Key，公开接口
- `/reels/` 复数 URL 必须转 `/reel/` 单数
- 部分私密账号帖子可能返回错误

---

## Facebook（浏览器兜底）

### oEmbed API（需 Access Token）
Facebook 的 oEmbed API 已迁移到 Graph API，需要有效的 access token：

```
GET https://graph.facebook.com/v18.0/oembed_video?url=<URL>&access_token=<TOKEN>
GET https://graph.facebook.com/v18.0/oembed_post?url=<URL>&access_token=<TOKEN>
```

无 token 时只返回嵌入代码（html 字段），不含 title/author_name 等元数据。

### 支持的 URL 格式
- `https://www.facebook.com/reel/REEL_ID`（Reels 视频）
- `https://www.facebook.com/photo.php?fbid=PHOTO_ID`（图片帖子）
- `https://www.facebook.com/watch/?v=VIDEO_ID`（Watch 视频）
- `https://www.facebook.com/username/posts/POST_ID`（普通帖子）

### 浏览器抓取步骤
1. 用浏览器打开 Facebook 链接
2. 页面加载后会弹出登录框，点击右上角 X 或按 ESC 关闭
3. 从页面可见区域提取：
   - 博主名称（页面顶部头像旁）
   - 视频/帖子描述（视频下方，可能需点击"展开"查看完整内容）
   - 点赞数（点赞图标旁）
   - 评论数（评论图标旁）
   - 分享数（分享图标旁）
4. 手动整理内容概要和博主类型
5. 用 lark-cli 写入对应单元格

### 注意事项
- 登录弹窗关闭后仍可看到公开内容
- 部分描述被截断，需点击"展开"/"See more"查看完整内容
- Reels 视频的描述在视频下方，可能需要滚动才能看到
- 图片帖子的描述在右侧边栏

---

## 互动率计算口径

### 观看互动率（仅 YouTube）
```
观看互动率 = (点赞数 + 评论数) / 观看量 × 100%
```
- 适用于有观看量数据的平台（YouTube）
- 反映视频内容对观众的吸引力

### 粉丝互动率（全平台通用）
```
粉丝互动率 = (点赞数 + 评论数) / 粉丝量 × 100%
```
- 适用于所有平台（只要有粉丝量、点赞、评论数据）
- 反映博主粉丝群体的活跃度和粘性
- 非 YouTube 平台的粉丝量常带 k/w 单位，需先换算：
  - `k` = 千（×1000）
  - `w` / `W` = 万（×10000）
  - `M` = 百万（×1000000）

### 行业参考值
| 粉丝互动率 | 评价 |
|---|---|
| < 1% | 偏低 |
| 1% - 3% | 正常 |
| 3% - 6% | 较高 |
| > 6% | 很高（通常是小账号或爆款内容） |

> 注意：粉丝量越小的账号互动率通常越高，跨账号比较时需考虑粉丝量基数。

===== 全文完 =====
