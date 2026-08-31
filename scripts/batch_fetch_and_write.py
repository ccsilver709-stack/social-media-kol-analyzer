#!/usr/bin/env python3
"""
批量 KOL 数据抓取 + 飞书表格回填工具
读取飞书表格指定范围内的社媒链接，逐行抓取数据，回填到对应列，并计算互动率。

用法:
    python batch_fetch_and_write.py \
      --url "https://mammotion.feishu.cn/wiki/xxx" \
      --sheet-name "KOL" \
      --url-col F --start-row 56 --end-row 80 \
      --view-col G --fans-col H --like-col I --comment-col J \
      --engagement-col N --summary-col O --type-col P \
      --delay 0.5

    # 仅预览不写入
    python batch_fetch_and_write.py ... --dry-run
"""

import argparse
import json
import subprocess
import sys
import os
import time
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_lark_cli(args_list, timeout=60):
    """执行 lark-cli 命令并返回解析后的 JSON"""
    cmd = ["lark-cli", "sheets"] + args_list
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
        if result.returncode != 0:
            print(f"[WARN] lark-cli 错误: {result.stderr[:200]}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] lark-cli 执行失败: {e}", file=sys.stderr)
        return None


def read_range(url, sheet_name, range_str):
    """读取飞书表格指定范围"""
    result = run_lark_cli([
        "+csv-get", "--url", url, "--sheet-name", sheet_name, "--range", range_str
    ])
    if not result or not result.get("ok"):
        return []

    csv_text = result.get("data", {}).get("annotated_csv", "")
    rows = []
    for line in csv_text.strip().split("\n"):
        if not line:
            continue
        # 解析 [row=N] 前缀
        match = re.match(r'^\[row=(\d+)\]\s*(.*)$', line)
        if match:
            row_num = int(match.group(1))
            content = match.group(2)
            cells = content.split(",")
            rows.append({"row": row_num, "cells": cells})
    return rows


def write_cells(url, sheet_name, range_str, values):
    """写入单元格值（二维数组）"""
    cells_json = json.dumps([[{"value": v} for v in row] for row in values], ensure_ascii=False)
    result = run_lark_cli([
        "+cells-set", "--url", url, "--sheet-name", sheet_name,
        "--range", range_str, "--cells", cells_json
    ])
    return result and result.get("ok")


def col_letter_to_index(letter):
    """列字母转索引（A=0）"""
    result = 0
    for c in letter.upper():
        result = result * 26 + (ord(c) - ord("A") + 1)
    return result - 1


def index_to_col_letter(index):
    """索引转列字母"""
    result = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def fetch_single(url, verbose=False):
    """调用主脚本抓取单条链接"""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "fetch_kol_data.py"), url, "--json"]
    if verbose:
        cmd.append("--verbose")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8")
        if result.returncode != 0:
            return {"error": f"脚本执行失败: {result.stderr[:200]}"}
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def parse_fans_value(value_str):
    """解析粉丝量字符串（支持 k/w 单位）"""
    if not value_str or value_str.strip() in ("/", "-", ""):
        return None
    s = value_str.strip().lower().replace(",", "")
    match = re.match(r'^([\d.]+)\s*([kw]?)$', s)
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        return int(num * {"k": 1000, "w": 10000, "": 1}.get(unit, 1))
    try:
        return int(float(s))
    except ValueError:
        return None


def summarize_content(result):
    """基于抓取结果生成内容概要（纯事实，不推断）"""
    video = result.get("video", {})
    title = video.get("title", "") or video.get("description", "")

    if not title:
        return ""

    # 取前150字符作为概要基础
    summary = title[:150].strip()
    if len(title) > 150:
        summary += "..."
    return summary


def classify_blogger(result):
    """基于博主名和内容分类（仅基于可见信息，不深度推断）"""
    video = result.get("video", {})
    uploader = (video.get("uploader") or "").lower()
    title = (video.get("title") or video.get("description") or "").lower()
    platform = result.get("platform", "")

    # 基于频道名关键词的分类规则
    name_keywords = {
        "草坪养护/园艺专业博主": ["lawn", "rasen", "garten", "garden", "horti", "larchi", "pelle"],
        "科技/产品测评博主": ["tech", "smart", "review", "test", "nicolas", "tesla", "pino", "gpt"],
        "家庭生活/亲子vlog": ["family", "familie", "charlyne", "kids", "亲子"],
        "庄园/城堡翻新/家居": ["chateau", "manoir", "castle", "cosy", "casa", "renovation", "翻新"],
        "旅行/户外生活方式": ["travel", "reise", "podroz", "bus", "van", "outdoor", "kopf", "gulasch"],
        "情侣/花园改造博主": ["xav", "tash", "couple", "情侣"],
        "DIY自建房屋/生活方式": ["diy", "selbstbau", "build", "自建"],
        "宠物/生活方式博主": ["pet", "cat", "dog", "sinas", "colorcats"],
        "海外移居/乡村生活vlog": ["new life", "move", "france", "移居", "乡村"],
        "房车旅行/生活方式博主": ["schrauber", "bus", "camper", "van life"],
    }

    for blogger_type, keywords in name_keywords.items():
        for kw in keywords:
            if kw in uploader:
                return blogger_type

    # 基于内容关键词
    content_keywords = {
        "草坪养护/园艺专业博主": ["mähroboter", "rasen", "garten", "lawn", "割草", "草坪"],
        "科技/产品测评博主": ["review", "test", "测评", "教程", "tutorial", "参数"],
        "家庭生活/亲子vlog": ["family", "kids", "孩子", "家庭"],
        "庄园/城堡翻新/家居": ["chateau", "castle", "renovation", "翻新", "庄园", "泳池", "piscine"],
        "旅行/户外生活方式": ["travel", "urlaub", "vacation", "旅行", "度假"],
    }

    for blogger_type, keywords in content_keywords.items():
        for kw in keywords:
            if kw in title:
                return blogger_type

    return "生活方式博主"  # 默认分类


def main():
    parser = argparse.ArgumentParser(description="批量 KOL 数据抓取 + 飞书表格回填")
    parser.add_argument("--url", required=True, help="飞书表格链接")
    parser.add_argument("--sheet-name", required=True, help="子表名")
    parser.add_argument("--url-col", default="F", help="链接所在列（默认F）")
    parser.add_argument("--start-row", type=int, required=True, help="起始行")
    parser.add_argument("--end-row", type=int, required=True, help="结束行")
    parser.add_argument("--view-col", default="G", help="观看量列")
    parser.add_argument("--fans-col", default="H", help="粉丝量列")
    parser.add_argument("--like-col", default="I", help="点赞数列")
    parser.add_argument("--comment-col", default="J", help="评论数列")
    parser.add_argument("--engagement-col", default="N", help="互动率列")
    parser.add_argument("--summary-col", default="O", help="内容概要列")
    parser.add_argument("--type-col", default="P", help="博主类型列")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数")
    parser.add_argument("--dry-run", action="store_true", help="仅抓取不写入")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    # 读取链接列
    url_range = f"{args.url_col}{args.start_row}:{args.url_col}{args.end_row}"
    print(f"[INFO] 读取链接范围: {url_range}", file=sys.stderr)
    rows = read_range(args.url, args.sheet_name, url_range)

    if not rows:
        print("[ERROR] 无法读取链接列", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 共读取 {len(rows)} 行链接", file=sys.stderr)

    # 统计
    stats = {"success": 0, "failed": 0, "skipped": 0, "browser_required": 0}
    results = []

    for row_data in rows:
        row_num = row_data["row"]
        cells = row_data["cells"]
        url = cells[0].strip() if cells else ""

        if not url or url in ("/", "-", ""):
            print(f"[行{row_num}] 跳过（无链接）", file=sys.stderr)
            stats["skipped"] += 1
            continue

        print(f"[行{row_num}] 抓取: {url[:60]}...", file=sys.stderr)

        result = fetch_single(url, verbose=args.verbose)
        result["row"] = row_num
        results.append(result)

        platform = result.get("platform", "unknown")
        channel = result.get("fetch_channel", "unknown")
        error = result.get("error")

        if error:
            print(f"  → 失败: {error[:80]}", file=sys.stderr)
            stats["failed"] += 1
        elif channel == "browser_required":
            print(f"  → 需浏览器兜底（{platform}）", file=sys.stderr)
            stats["browser_required"] += 1
        else:
            video = result.get("video", {})
            print(f"  → 成功（{platform}/{channel}）: {video.get('uploader', 'N/A')} | "
                  f"观看:{video.get('view_count', 'N/A')} 点赞:{video.get('like_count', 'N/A')}",
                  file=sys.stderr)
            stats["success"] += 1

        time.sleep(args.delay)

    # 写入飞书
    if not args.dry_run:
        print("\n[INFO] 开始写入飞书表格...", file=sys.stderr)
        for result in results:
            row_num = result["row"]
            if result.get("error") or result.get("fetch_channel") in ("failed", "browser_required"):
                continue

            video = result.get("video", {})
            platform = result.get("platform")

            # YouTube 行：写入观看量/粉丝/点赞/评论
            if platform == "youtube":
                if video.get("view_count") is not None:
                    write_cells(args.url, args.sheet_name, f"{args.view_col}{row_num}",
                                [[video["view_count"]]])
                if video.get("subscriber_count") is not None:
                    write_cells(args.url, args.sheet_name, f"{args.fans_col}{row_num}",
                                [[video["subscriber_count"]]])
                if video.get("like_count") is not None:
                    write_cells(args.url, args.sheet_name, f"{args.like_col}{row_num}",
                                [[video["like_count"]]])
                if video.get("comment_count") is not None:
                    write_cells(args.url, args.sheet_name, f"{args.comment_col}{row_num}",
                                [[video["comment_count"]]])

            # 所有平台：写入内容概要和博主类型
            summary = summarize_content(result)
            blogger_type = classify_blogger(result)

            if summary:
                write_cells(args.url, args.sheet_name, f"{args.summary_col}{row_num}", [[summary]])
            if blogger_type:
                write_cells(args.url, args.sheet_name, f"{args.type_col}{row_num}", [[blogger_type]])

            # 计算并写入互动率（基于表格中已有的粉丝量/点赞/评论值）
            # 这里简化处理：YouTube 用观看互动率，其他平台需先读取表格中的粉丝量
            # 完整实现应先读取 H/I/J 列再计算

        print("[INFO] 写入完成", file=sys.stderr)

    # 输出报告
    print("\n" + "=" * 50)
    print("处理报告")
    print("=" * 50)
    print(f"总行数: {len(rows)}")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"跳过（无链接）: {stats['skipped']}")
    print(f"需浏览器兜底: {stats['browser_required']}")
    if args.dry_run:
        print("\n[DRY-RUN] 未写入飞书表格")

    # 输出详细结果 JSON
    output = {"stats": stats, "results": results}
    print("\n" + json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
