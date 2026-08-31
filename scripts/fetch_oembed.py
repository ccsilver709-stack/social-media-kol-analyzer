#!/usr/bin/env python3
"""
TikTok / Instagram oEmbed API 独立抓取工具
无需登录，通过公开 oEmbed 接口获取视频标题（含完整描述）、博主名称、博主ID、封面图。

用法:
    python fetch_oembed.py "<TikTok或Instagram链接>" --json
    python fetch_oembed.py "<链接>" --platform tiktok
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse


def detect_platform(url):
    host = urlparse(url).netloc.lower()
    if "tiktok.com" in host:
        return "tiktok"
    elif "instagram.com" in host:
        return "instagram"
    return "unknown"


def normalize_instagram_url(url):
    """Instagram /reels/ 复数 → /reel/ 单数，oEmbed 才支持"""
    return re.sub(r'instagram\.com/reels/', 'instagram.com/reel/', url)


def fetch_oembed(url, platform=None, timeout=15):
    if platform is None:
        platform = detect_platform(url)

    if platform == "tiktok":
        api_url = f"https://www.tiktok.com/oembed?url={url}"
    elif platform == "instagram":
        normalized = normalize_instagram_url(url)
        api_url = f"https://www.instagram.com/api/v1/oembed/?url={normalized}"
    else:
        return {"error": f"不支持的平台: {platform}"}

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "platform": platform, "url": url}
    except Exception as e:
        return {"error": str(e), "platform": platform, "url": url}

    # 从 author_url 提取用户名
    uploader_id = ""
    author_url = data.get("author_url", "")
    if author_url:
        m = re.search(r'/(?:@)?([^/]+)/?$', author_url)
        if m:
            uploader_id = m.group(1)

    return {
        "platform": platform,
        "url": url,
        "title": data.get("title", ""),
        "description": data.get("title", ""),
        "author_name": data.get("author_name", ""),
        "author_id": uploader_id,
        "author_url": author_url,
        "thumbnail_url": data.get("thumbnail_url", ""),
        "provider": data.get("provider_name", ""),
        "raw": data,
    }


def main():
    parser = argparse.ArgumentParser(description="TikTok/Instagram oEmbed 抓取工具")
    parser.add_argument("url", help="视频链接")
    parser.add_argument("--platform", choices=["tiktok", "instagram"], help="指定平台（默认自动识别）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--no-raw", action="store_true", help="不输出原始 oEmbed 数据")
    args = parser.parse_args()

    result = fetch_oembed(args.url, platform=args.platform)

    if args.no_raw and "raw" in result:
        del result["raw"]

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"平台: {result.get('platform')}")
        print(f"博主: {result.get('author_name')} (@{result.get('author_id')})")
        print(f"标题/描述: {result.get('title', '')[:200]}")
        if result.get("error"):
            print(f"错误: {result['error']}")


if __name__ == "__main__":
    main()
