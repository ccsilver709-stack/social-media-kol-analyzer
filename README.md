# social-media-kol-analyzer

多平台 KOL 内容采集与数据分析工具。输入 YouTube / TikTok / Instagram / Facebook 链接，自动识别平台并按优先级抓取，输出统一结构化数据，并自动计算粉丝互动率。

## 特性

- **多平台自动识别**：YouTube、TikTok、Instagram、Facebook
- **智能抓取优先级**：
  - YouTube → yt-dlp（含自动重试 + 客户端切换容错）
  - TikTok / Instagram → oEmbed 公开 API（无需登录）
  - Facebook → 浏览器兜底（oEmbed 需 access token）
- **统一输出格式**：标题、描述、博主、粉丝量、观看量、点赞、评论、发布日期
- **自动互动率计算**：观看互动率 + 粉丝互动率（粉丝量带 k/w 单位自动换算）
- **批量飞书回填**：支持读取飞书表格链接列，批量抓取并回填到指定列
- **Instagram URL 自动修复**：`/reels/` 复数 URL 自动转 `/reel/` 单数

## 安装

```bash
# 克隆仓库
git clone https://github.com/ccsilver709-stack/social-media-kol-analyzer.git
cd social-media-kol-analyzer

# 安装依赖
pip install yt-dlp
```

## 快速开始

### 单链接抓取

```bash
python scripts/fetch_kol_data.py "https://www.youtube.com/watch?v=VIDEO_ID" --json
python scripts/fetch_kol_data.py "https://www.tiktok.com/@user/video/VIDEO_ID" --json
python scripts/fetch_kol_data.py "https://www.instagram.com/reel/REEL_ID/" --json
```

输出统一 JSON：

```json
{
  "platform": "youtube",
  "fetch_channel": "yt-dlp",
  "video": {
    "title": "视频标题",
    "description": "视频描述",
    "uploader": "博主名称",
    "subscriber_count": 12345,
    "view_count": 12345,
    "like_count": 123,
    "comment_count": 12
  },
  "engagement": {
    "view_engagement_rate": 0.0123,
    "fan_engagement_rate": 0.0456
  }
}
```

### 批量抓取 + 飞书表格回填

```bash
python scripts/batch_fetch_and_write.py \
  --url "https://mammotion.feishu.cn/wiki/xxx" \
  --sheet-name "KOL" \
  --url-col F --start-row 56 --end-row 80 \
  --view-col G --fans-col H --like-col I --comment-col J \
  --engagement-col N --summary-col O --type-col P
```

### oEmbed 独立模块

```bash
python scripts/fetch_oembed.py "https://www.tiktok.com/@user/video/VIDEO_ID" --json
python scripts/fetch_oembed.py "https://www.instagram.com/reel/REEL_ID/" --json
```

## 项目结构

```
social-media-kol-analyzer/
├── SKILL.md                          # 技能主文档（触发条件、工作流、分类参考）
├── README.md                         # 项目说明（本文件）
├── scripts/
│   ├── fetch_kol_data.py             # 主入口：自动平台识别 + 多通道调度 + 统一输出
│   ├── fetch_oembed.py               # 独立模块：TikTok/Instagram oEmbed 抓取
│   └── batch_fetch_and_write.py      # 批量抓取 + 飞书表格回填
└── references/
    └── platform-endpoints.md         # 各平台 API 端点、字段映射、互动率口径详解
```

## 平台支持详情

| 平台 | 抓取通道 | 可获取字段 | 限制 |
|---|---|---|---|
| YouTube | yt-dlp | 全字段（标题、描述、博主、粉丝、观看、点赞、评论、日期、时长） | 国内需代理；偶发 502 自动重试 |
| TikTok | oEmbed API | 完整描述、博主名、博主ID、封面图 | 无观看量/点赞/评论/粉丝数 |
| Instagram | oEmbed API | 完整描述、博主名、博主ID、封面图 | 无观看量/点赞/评论/粉丝数 |
| Facebook | 浏览器兜底 | 博主名、可见描述、点赞/评论/分享数 | oEmbed 需 Graph API access token |

## 互动率口径

- **观看互动率** = (点赞数 + 评论数) / 观看量（仅 YouTube）
- **粉丝互动率** = (点赞数 + 评论数) / 粉丝量（全平台通用）

行业参考：<1% 偏低，1-3% 正常，3-6% 较高，>6% 很高。

## 作为豆包 Skill 使用

本项目同时是一个豆包工作伙伴（AI Work Partner）自定义 Skill。将项目目录放入 `.user_skills/` 下，豆包工作伙伴会自动识别并加载。

Skill 触发关键词：KOL数据采集、社媒数据分析、红人监控、YouTube/TikTok/Instagram链接抓取。

## License

MIT
