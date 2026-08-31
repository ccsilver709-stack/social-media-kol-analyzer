#!/usr/bin/env python3
"""
多平台 KOL 内容采集主入口
自动识别平台（YouTube/TikTok/Instagram/Facebook），按优先级调用对应抓取通道，
输出统一结构化 JSON，并计算互动率。

用法:
    python fetch_kol_data.py "<URL>" --json
    python fetch_kol_data.py "<URL>" --json --verbose
"""

import argparse
import json
import re
import subprocess
import sys
import os
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def detect_platform(url):
    """根据 URL 自动识别平台"""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    elif "tiktok.com" in host:
        return "tiktok"
    elif "instagram.com" in host:
        return "instagram"
    elif "facebook.com" in host or "fb.com" in host or "fb.watch" in host:
        return "facebook"
    else:
        return "unknown"


def normalize_instagram_url(url):
    """Instagram /reels/ 复数 URL 转换为 /reel/ 单数，oEmbed 才支持"""
    return re.sub(r'instagram\.com/reels/', 'instagram.com/reel/', url)


def fetch_youtube(url, max_comments=0, verbose=False):
    """调用 yt-dlp 抓取 YouTube 视频数据"""
    try:
        import yt_dlp
    except ImportError:
        if verbose:
            print("[INFO] 正在安装 yt-dlp...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"])
        import yt_dlp

    ydl_opts = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "extract_flat": False,
        "getcomments": max_comments > 0,
        "max_comments": max_comments if max_comments > 0 else None,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # 提取频道粉丝数（yt-dlp 不直接提供，需要单独请求频道页）
    subscriber_count = info.get("channel_follower_count") or info.get("subscriber_count")

    return {
        "platform": "youtube",
        "url": url,
        "fetch_channel": "yt-dlp",
        "video": {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "uploader": info.get("uploader") or info.get("channel", ""),
            "uploader_id": info.get("channel_id") or info.get("uploader_id", ""),
            "channel_url": info.get("channel_url") or info.get("uploader_url", ""),
            "subscriber_count": subscriber_count,
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "comment_count": info.get("comment_count"),
            "upload_date": info.get("upload_date", ""),
            "duration": info.get("duration"),
            "thumbnail_url": info.get("thumbnail", ""),
            "tags": info.get("tags", []),
        },
        "error": None,
    }


def fetch_oembed(url, platform, verbose=False):
    """调用 oEmbed API 抓取 TikTok/Instagram 数据"""
    import urllib.request
    import urllib.error

    if platform == "tiktok":
        api_url = f"https://www.tiktok.com/oembed?url={url}"
    elif platform == "instagram":
        normalized_url = normalize_instagram_url(url)
        api_url = f"https://www.instagram.com/api/v1/oembed/?url={normalized_url}"
    else:
        return None

    if verbose:
        print(f"[INFO] 调用 oEmbed API: {api_url}", file=sys.stderr)

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"[WARN] oEmbed HTTP 错误: {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        if verbose:
            print(f"[WARN] oEmbed 请求失败: {e}", file=sys.stderr)
        return None

    # oEmbed 不提供观看量/粉丝量/点赞/评论，这些需要从其他来源获取
    # 但标题字段通常包含完整描述文本
    title = data.get("title", "")
    author_name = data.get("author_name", "")
    author_url = data.get("author_url", "")
    thumbnail_url = data.get("thumbnail_url", "")

    # 从 author_url 提取用户名
    uploader_id = ""
    if author_url:
        match = re.search(r'/(?:@)?([^/]+)/?$', author_url)
        if match:
            uploader_id = match.group(1)

    return {
        "platform": platform,
        "url": url,
        "fetch_channel": "oembed",
        "video": {
            "title": title,
            "description": title,  # oEmbed 的 title 字段实际是完整描述
            "uploader": author_name,
            "uploader_id": uploader_id,
            "channel_url": author_url,
            "subscriber_count": None,  # oEmbed 不提供
            "view_count": None,  # oEmbed 不提供
            "like_count": None,  # oEmbed 不提供
            "comment_count": None,  # oEmbed 不提供
            "upload_date": "",
            "duration": None,
            "thumbnail_url": thumbnail_url,
            "tags": [],
        },
        "error": None,
    }


def parse_fans_count(value):
    """解析带单位的粉丝量字符串，返回纯数字。支持 k/K=千, w/W=万, M=百万"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip().lower().replace(",", "")
    if not s or s in ("/", "-", "n/a", "unknown"):
        return None

    match = re.match(r'^([\d.]+)\s*([kmw]?)$', s)
    if not match:
        try:
            return int(float(s))
        except ValueError:
            return None

    num = float(match.group(1))
    unit = match.group(2)

    multipliers = {"k": 1000, "m": 1_000_000, "w": 10_000, "": 1}
    return int(num * multipliers.get(unit, 1))


def calculate_engagement(result):
    """计算互动率并附加到结果中"""
    video = result.get("video", {})
    likes = video.get("like_count") or 0
    comments = video.get("comment_count") or 0
    views = video.get("view_count")
    fans = video.get("subscriber_count")

    engagement = {
        "view_engagement_rate": None,
        "fan_engagement_rate": None,
    }

    # 观看互动率 = (点赞+评论)/观看量
    if views and views > 0:
        engagement["view_engagement_rate"] = round((likes + comments) / views, 6)

    # 粉丝互动率 = (点赞+评论)/粉丝量
    if fans and fans > 0:
        engagement["fan_engagement_rate"] = round((likes + comments) / fans, 6)

    result["engagement"] = engagement
    return result


def fetch_kol_data(url, max_comments=0, verbose=False):
    """主入口：识别平台 → 调用对应通道 → 统一输出"""
    platform = detect_platform(url)

    if verbose:
        print(f"[INFO] 识别平台: {platform}", file=sys.stderr)

    result = None

    if platform == "youtube":
        try:
            result = fetch_youtube(url, max_comments=max_comments, verbose=verbose)
        except Exception as e:
            result = {
                "platform": "youtube",
                "url": url,
                "fetch_channel": "failed",
                "video": {},
                "error": f"yt-dlp 抓取失败: {str(e)}",
            }

    elif platform in ("tiktok", "instagram"):
        result = fetch_oembed(url, platform, verbose=verbose)
        if result is None:
            result = {
                "platform": platform,
                "url": url,
                "fetch_channel": "failed",
                "video": {},
                "error": "oEmbed API 获取失败，建议使用浏览器兜底",
            }

    elif platform == "facebook":
        # Facebook oEmbed 需 access token，直接标记需浏览器兜底
        result = {
            "platform": "facebook",
            "url": url,
            "fetch_channel": "browser_required",
            "video": {},
            "error": "Facebook 需浏览器手动抓取（oEmbed 需 access token）",
        }

    else:
        result = {
            "platform": "unknown",
            "url": url,
            "fetch_channel": "failed",
            "video": {},
            "error": f"无法识别的平台: {url}",
        }

    # 计算互动率
    if result and result.get("video"):
        result = calculate_engagement(result)

    return result


def main():
    parser = argparse.ArgumentParser(description="多平台 KOL 内容采集工具")
    parser.add_argument("url", help="社媒视频链接")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--max-comments", type=int, default=0, help="YouTube 评论抓取上限（默认0不抓）")
    parser.add_argument("--verbose", action="store_true", help="输出详细过程")
    args = parser.parse_args()

    result = fetch_kol_data(args.url, max_comments=args.max_comments, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 人类可读格式
        v = result.get("video", {})
        print(f"平台: {result.get('platform')}")
        print(f"抓取通道: {result.get('fetch_channel')}")
        if result.get("error"):
            print(f"错误: {result['error']}")
        print(f"标题: {v.get('title', 'N/A')[:80]}")
        print(f"博主: {v.get('uploader', 'N/A')}")
        print(f"粉丝量: {v.get('subscriber_count', 'N/A')}")
        print(f"观看量: {v.get('view_count', 'N/A')}")
        print(f"点赞: {v.get('like_count', 'N/A')}")
        print(f"评论: {v.get('comment_count', 'N/A')}")
        eng = result.get("engagement", {})
        if eng.get("view_engagement_rate"):
            print(f"观看互动率: {eng['view_engagement_rate']*100:.2f}%")
        if eng.get("fan_engagement_rate"):
            print(f"粉丝互动率: {eng['fan_engagement_rate']*100:.2f}%")


if __name__ == "__main__":
    main()
