#!/usr/bin/env python3
"""
结构化内容概要生成器
从 KOL 视频标题/描述中自动提取关键信息维度，生成详细的结构化内容概要。
支持中文、英语、德语、法语多语言关键词识别，纯事实提取不推断。

维度：
1. 产品/型号（LUBA 3 AWD、SPINO E1 等）
2. 核心卖点/功能（无边界线、LiDAR、AI避障、AWD 等）
3. 促销信息（价格、折扣、周年庆等）
4. 使用场景（度假、花园、泳池、家庭等）
5. 个人背景/故事（雷击损坏、保险理赔、移居等）
6. 互动点（提问、投票、命名挑战等）
"""

import re
from typing import Dict, List, Optional


# ============================================================
# 多语言关键词词典
# ============================================================

# 产品型号正则（匹配 Mammotion 产品线）
PRODUCT_PATTERNS = [
    r'\bLUBA\s*(?:\d+)?\s*(?:AWD|Mini|Pro)?\s*(?:\d+)?\b',
    r'\bSPINO\s*(?:E\d+)?\b',
    r'\bYUKA\b',
    r'\bMammotion\b',
    r'\bMähroboter\b',
    r'\brobot\s*tondeuse\b',
    r'\blawn\s*mower\b',
    r'\brobot\s*mower\b',
    r'\bpool\s*cleaner\b',
    r'\brobot\s*de\s*piscine\b',
    r'\bPoolroboter\b',
]

# 核心功能/卖点关键词（多语言）
FEATURE_KEYWORDS = {
    "无边界线/无需埋线": [
        r'no\s*boundary', r'boundary\s*free', r'without\s*boundary',
        r'kein\s*Begrenzungskabel', r'ohne\s*Kabel', r'kein\s*Kabel',
        r'sans\s*fil', r'sans\s*câble', r'pas\s*de\s*câble',
        r'无边界', r'无埋线', r'不用埋线', r'无需边界线',
    ],
    "LiDAR激光导航": [
        r'\bLiDAR\b', r'\bLidar\b', r'360°?\s*LiDAR', r'360\s*Grad\s*LiDAR',
        r'激光导航', r'激光雷达',
    ],
    "AI视觉/AI避障": [
        r'\bAI\s*Vision\b', r'\bAI\b.*vision', r'vision\s*AI',
        r'\bKI\b', r'künstliche\s*Intelligenz',
        r'\bAI\b.*避障', r'AI\s*避障', r'智能避障',
        r'obstacle\s*avoidance', r'Hinderniserkennung',
        r'détection\s*d\'obstacles',
    ],
    "全轮驱动AWD": [
        r'\bAWD\b', r'all[\s-]?wheel\s*drive', r'Allradantrieb',
        r'全轮驱动', r'四驱',
    ],
    "爬坡能力": [
        r'\d+\s*%\s*(?:slope|inclination|gradient|steep)',
        r'\d+\s*%\s*Steigung', r'bis zu\s*\d+\s*%',
        r'爬\s*\d+\s*%', r'坡度', r'爬坡',
        r'pente\s*(?:de\s*)?\d+\s*%',
    ],
    "App远程控制": [
        r'App[\s-]?Steuerung', r'per\s*App', r'App\s*steuern',
        r'App\s*control', r'via\s*app', r'app\s*remote',
        r'contrôle\s*(?:via\s*)?app', r'application',
        r'App控制', r'远程控制', r'手机控制',
    ],
    "自动建图/导航": [
        r'automatic\s*mapping', r'auto\s*mapping', r'RTK',
        r'automatische\s*Kartierung', r'Kartierung',
        r'cartographie\s*automatique',
        r'自动建图', r'智能建图', r'导航',
        r'Tri[\s-]?Fusion', r'tri\s*fusion', r'三融合',
    ],
    "续航/面积": [
        r'\d+\s*m[²2]', r'\d+\s*qm', r'\d+\s*sq\s*ft',
        r'bis zu\s*\d+\s*m', r'Fläche\s*von',
        r'jusqu\'à\s*\d+\s*m',
        r'\d+\s*平方米', r'覆盖面积', r'续航',
        r'battery\s*life', r'Akkulaufzeit', r'autonomie',
    ],
    "割草高度可调": [
        r'mowing\s*height', r'cutting\s*height',
        r'Mähhöhe', r'Schnitthöhe',
        r'hauteur\s*de\s*coupe',
        r'割草高度', r'割高',
    ],
    "静音/低噪音": [
        r'quiet', r'silent', r'low\s*noise', r'\d+\s*dB',
        r'leise', r'Geräusch', r'\d+\s*dB',
        r'silencieux', r'bruits',
        r'静音', r'低噪', r'噪音',
    ],
    "防水": [
        r'waterproof', r'water\s*resistant', r'IPX\d',
        r'wasserdicht', r'Wasserschutz',
        r'étanche',
        r'防水', r'IPX\d',
    ],
    "GPS防盗": [
        r'GPS\s*tracking', r'GPS\s*anti[\s-]?theft',
        r'GPS\s*Diebstahlschutz',
        r'GPS防盗', r'定位防盗',
    ],
    "割边/边缘切割": [
        r'edge\s*cutting', r'edge\s*cut',
        r'Kantenschnitt', r'Kantenschneidscheibe',
        r'bords\s*nets',
        r'割边', r'边缘切割', r'割边盘',
    ],
    "野生动物/宠物安全": [
        r'wildlife', r'animal\s*safe', r'pet\s*safe',
        r'Wildtiererkennung', r'Tierschutz', r'Igel',
        r'animaux', r'sécurité\s*des\s*animaux',
        r'动物安全', r'宠物安全', r'野生动物',
    ],
    "雨天保护": [
        r'rain\s*mode', r'rain\s*protection', r'weather',
        r'Regenschutz', r'Regenmodus',
        r'protection\s*pluie',
        r'雨天', r'防雨',
    ],
}

# 促销信息关键词
PROMOTION_KEYWORDS = {
    "折扣/降价": [
        r'\d+\s*%\s*(?:off|discount|rabatt|réduction|sale)',
        r'save\s*[\$€£]?\d+', r'save\s*up\s*to',
        r'Rabatt', r'Nachlass', r'preiswert',
        r'réduction', r'promo', r'soldes',
        r'折扣', r'降价', r'优惠', r'立减',
    ],
    "具体价格": [
        r'[\$€£]\s*\d+(?:[.,]\d+)?',
        r'\d+(?:[.,]\d+)?\s*[\$€£]',
        r'\d+\s*Euro', r'\d+\s*€',
        r'au lieu de\s*\d+', r'pour\s*\d+',
        r'\d+\s*元', r'\d+\s*块',
    ],
    "原价对比": [
        r'instead\s*of\s*[\$€£]?\d+', r'was\s*[\$€£]?\d+',
        r'statt\s*\d+', r'früher\s*\d+', r'ursprünglich',
        r'au lieu de', r'ancien\s*prix',
        r'原价', r'现价', r'原价\s*\d+',
    ],
    "周年庆/活动": [
        r'anniversary', r'10\s*years?', r'birthday',
        r'Geburtstag', r'Jubiläum', r'10\s*Jahre',
        r'anniversaire', r'10\s*ans',
        r'周年', r'周年庆', r'店庆', r'促销',
    ],
    "限时/倒计时": [
        r'limited\s*time', r'limited\s*offer', r'ends\s*soon',
        r'zeitlich\s*begrenzt', r'nur\s*für\s*kurze',
        r'offre\s*limitée', r'pendant\s*une\s*durée\s*limitée',
        r'限时', r'倒计时', r'最后',
    ],
    "购买链接/引导": [
        r'link\s*in\s*bio', r'click\s*the\s*link', r'shop\s*now',
        r'Link\s*in\s*Bio', r'zum\s*Shop', r'bestellen',
        r'lien\s*dans\s*la\s*bio', r'acheter',
        r'链接', r'购买', r'下单', r'点击链接',
    ],
}

# 使用场景关键词
SCENARIO_KEYWORDS = {
    "度假/旅行中": [
        r'vacation', r'holiday', r'travel', r'trip', r'away',
        r'Urlaub', r'reisen', r'unterwegs', r'Ferien',
        r'vacances', r'voyage', r'parti',
        r'度假', r'旅行', r'出差', r'不在家',
    ],
    "花园/庭院维护": [
        r'garden', r'yard', r'lawn', r'backyard',
        r'Garten', r'Rasen', r'Hof',
        r'jardin', r'pelouse', r'cour',
        r'花园', r'庭院', r'草坪', r'院子',
    ],
    "泳池清洁": [
        r'pool', r'swimming\s*pool', r'pool\s*cleaning',
        r'Pool', r'Schwimmbad', r'Poolpflege',
        r'piscine', r'nettoyage\s*de\s*piscine',
        r'泳池', r'游泳池', r'泳池清洁',
    ],
    "家庭日常": [
        r'family', r'home', r'daily', r'routine',
        r'Familie', r'zuHause', r'Alltag',
        r'famille', r'maison', r'quotidien',
        r'家庭', r'家里', r'日常',
    ],
    "庄园/城堡/大房产": [
        r'estate', r'manor', r'chateau', r'castle', r'property',
        r'Schloss', r'Anwesen', r'Gut',
        r'manoir', r'château', r'propriété',
        r'庄园', r'城堡', r'大花园', r'大院子',
    ],
    "DIY/自建": [
        r'DIY', r'do\s*it\s*yourself', r'build', r'renovation',
        r'selbstgebaut', r'Selbstbau', r'Ausbau',
        r'bricolage', r'construction', r'rénovation',
        r'自己建', r'自建', r'改造', r'装修',
    ],
    "省时/效率": [
        r'save\s*time', r'time\s*saver', r'efficient', r'hassle\s*free',
        r'Zeit\s*sparen', r'zeitsparend', r'entspannter',
        r'gagner\s*du\s*temps', r'pratique',
        r'省时', r'省心', r'方便', r'解放双手',
    ],
}

# 个人背景/故事关键词
STORY_KEYWORDS = {
    "设备损坏/更换": [
        r'broke', r'broken', r'damaged', r'replace', r'old\s*one',
        r'kaputt', r'Beschädigung', r'ersetzt', r'altes\s*Gerät',
        r'cassé', r'endommagé', r'remplacé', r'ancien',
        r'坏了', r'损坏', r'换了', r'旧的', r'之前的',
    ],
    "保险理赔": [
        r'insurance', r'claim', r'covered\s*by\s*insurance',
        r'Versicherung', r'Schadensübernahme', r'versichert',
        r'assurance', r'indemnisation', r'pris\s*en\s*charge',
        r'保险', r'理赔', r'报销',
    ],
    "自然灾害/意外": [
        r'storm', r'lightning', r'flood', r'fire', r'accident',
        r'Blitz', r'Blitzeinschlag', r'Unwetter', r'Sturm',
        r'orage', r'éclair', r'inondation', r'accident',
        r'雷击', r'暴风雨', r'洪水', r'火灾', r'意外',
    ],
    "移居/新生活": [
        r'moved\s*to', r'new\s*life', r'relocated', r'starting\s*anew',
        r'umgezogen', r'neues\s*Leben', r'Neuanfang',
        r'déménagé', r'nouvelle\s*vie', r'installé',
        r'移居', r'搬家', r'新生活', r'来到',
    ],
    "初次使用/体验": [
        r'first\s*time', r'new\s*to', r'trying\s*out', r'first\s*impression',
        r'erstmalig', r'zum\s*ersten\s*Mal', r'neugierig',
        r'première\s*fois', r'découverte',
        r'第一次', r'初次', r'体验', r'试试',
    ],
}

# 互动点关键词
INTERACTION_KEYWORDS = {
    "提问/问答": [
        r'\?', r'what\s*do\s*you\s*think', r'would\s*you', r'comment',
        r'was\s*meint\s*ihr', r'habt\s*ihr\s*schon', r'frage',
        r'qu\'en\s*pensez', r'vous\s*préférez', r'question',
        r'你们觉得', r'怎么选', r'你们会', r'问一下',
    ],
    "投票/选择": [
        r'poll', r'vote', r'choose\s*between', r'A\s*or\s*B',
        r'Abstimmung', r'wählen', r'oder\s*oder',
        r'sondage', r'choisir', r'ou\s*bien',
        r'投票', r'选哪个', r'二选一', r'哪个好',
    ],
    "命名挑战": [
        r'name\s*it', r'what\s*should\s*we\s*name', r'naming',
        r'taufen', r'Name\s*geben', r'wie\s*soll\s*er\s*heißen',
        r'prénommer', r'comment\s*l\'appeler',
        r'起名', r'取名字', r'叫什么', r'命名',
    ],
    " giveaway/抽奖": [
        r'giveaway', r'win', r'free\s*giveaway', r'contest',
        r'Verlosung', r'gewinnen',
        r'concours', r'gagner',
        r'抽奖', r'福利', r'送', r'免费拿',
    ],
    "经验分享/求助": [
        r'share\s*your', r'let\s*me\s*know', r'tips', r'experience',
        r'erzählt\s*mir', r'Erfahrungen', r'Tipps',
        r'partagez', r'expérience', r'conseils',
        r'分享', r'交流', r'经验', r'建议',
    ],
}


# ============================================================
# 提取函数
# ============================================================

def extract_products(text: str) -> List[str]:
    """提取文本中提到的产品/型号"""
    products = []
    for pattern in PRODUCT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            m = m.strip()
            if m and m not in products:
                products.append(m)
    return products


def extract_by_keyword_dict(text: str, keyword_dict: Dict[str, List[str]]) -> List[str]:
    """通用：按关键词词典提取匹配的维度标签"""
    text_lower = text.lower()
    matched = []
    for label, patterns in keyword_dict.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                if label not in matched:
                    matched.append(label)
                break
    return matched


def extract_specific_prices(text: str) -> List[str]:
    """提取具体价格信息"""
    prices = []
    # 匹配 € $ £ 价格
    for match in re.finditer(r'([\$€£])\s*(\d+(?:[.,]\d+)?)', text):
        price = f"{match.group(1)}{match.group(2)}"
        if price not in prices:
            prices.append(price)
    # 匹配 数字 Euro / 数字 €
    for match in re.finditer(r'(\d+(?:[.,]\d+)?)\s*(?:Euro|€)', text, re.IGNORECASE):
        price = f"{match.group(1)}€"
        if price not in prices:
            prices.append(price)
    # 匹配 au lieu de X pour Y（法语原价对比）
    for match in re.finditer(r'au lieu de\s*(\d+(?:[.,]\d+)?)\s*€?\s*(?:pour|à)?\s*(\d+(?:[.,]\d+)?)?', text, re.IGNORECASE):
        if match.group(2):
            price = f"{match.group(2)}€（原价{match.group(1)}€）"
        else:
            price = f"原价{match.group(1)}€"
        if price not in prices:
            prices.append(price)
    # 匹配 statt X（德语原价对比）
    for match in re.finditer(r'(?:statt|ursprünglich|früher)\s*(\d+(?:[.,]\d+)?)\s*€?', text, re.IGNORECASE):
        price = f"原价{match.group(1)}€"
        if price not in prices:
            prices.append(price)
    return prices[:3]  # 最多保留3个价格


def extract_core_sentence(text: str, max_len: int = 120) -> str:
    """提取第一句核心内容（去掉emoji和多余空格）"""
    # 按换行和句号分割，取第一句
    sentences = re.split(r'[\n.!?。！？]', text)
    for s in sentences:
        s = s.strip()
        # 去掉emoji
        s = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b00-\u2bff\u3030\u303d\ufe0f]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        if len(s) > 10:  # 至少10个字符才算有效句子
            return s[:max_len]
    return ""


def generate_detailed_summary(title: str, description: str = "", max_length: int = 500) -> str:
    """
    生成详细的结构化内容概要
    
    Args:
        title: 视频标题（TikTok/Instagram 的 title 字段就是完整描述）
        description: 视频描述（YouTube 的 description 字段）
        max_length: 概要最大长度
    
    Returns:
        结构化内容概要字符串
    """
    # 合并文本
    full_text = title or ""
    if description and description.strip() and description.strip() != title.strip():
        full_text = title + "\n" + description
    
    if not full_text.strip():
        return ""
    
    # 提取各维度
    products = extract_products(full_text)
    features = extract_by_keyword_dict(full_text, FEATURE_KEYWORDS)
    promotions = extract_by_keyword_dict(full_text, PROMOTION_KEYWORDS)
    prices = extract_specific_prices(full_text)
    scenarios = extract_by_keyword_dict(full_text, SCENARIO_KEYWORDS)
    stories = extract_by_keyword_dict(full_text, STORY_KEYWORDS)
    interactions = extract_by_keyword_dict(full_text, INTERACTION_KEYWORDS)
    
    # 组装结构化概要
    parts = []
    
    # 1. 核心句（第一句概括）
    core = extract_core_sentence(full_text)
    if core:
        parts.append(core)
    
    # 2. 产品/型号
    if products:
        product_str = "、".join(products[:3])
        parts.append(f"【产品】{product_str}")
    
    # 3. 核心卖点/功能
    if features:
        feature_str = "、".join(features[:6])
        parts.append(f"【卖点】{feature_str}")
    
    # 4. 促销信息
    promo_parts = []
    if prices:
        promo_parts.append("价格" + "/".join(prices))
    if promotions:
        promo_parts.append("、".join(promotions[:3]))
    if promo_parts:
        parts.append(f"【促销】{'；'.join(promo_parts)}")
    
    # 5. 使用场景
    if scenarios:
        scenario_str = "、".join(scenarios[:3])
        parts.append(f"【场景】{scenario_str}")
    
    # 6. 个人背景/故事
    if stories:
        story_str = "、".join(stories[:2])
        parts.append(f"【背景】{story_str}")
    
    # 7. 互动点
    if interactions:
        interaction_str = "、".join(interactions[:2])
        parts.append(f"【互动】{interaction_str}")
    
    summary = " | ".join(parts)
    
    # 控制最大长度
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."
    
    return summary


def summarize_content_simple(title: str, description: str = "", max_length: int = 200) -> str:
    """
    简化版概要：仅提取核心句 + 产品 + 促销（适合空间有限的场景）
    """
    full_text = title or ""
    if description and description.strip() and description.strip() != title.strip():
        full_text = title + "\n" + description
    
    if not full_text.strip():
        return ""
    
    parts = []
    
    core = extract_core_sentence(full_text, max_len=100)
    if core:
        parts.append(core)
    
    products = extract_products(full_text)
    if products:
        parts.append("产品：" + "、".join(products[:2]))
    
    prices = extract_specific_prices(full_text)
    if prices:
        parts.append("价格：" + "/".join(prices))
    
    summary = "；".join(parts)
    
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."
    
    return summary


# ============================================================
# 命令行测试入口
# ============================================================

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("用法: python content_summarizer.py <文本文件路径或直接文本>")
        print("示例: python content_summarizer.py \"LUBA 3 AWD im Test...\"")
        sys.exit(1)
    
    input_text = sys.argv[1]
    
    # 如果是文件路径，读取文件
    import os
    if os.path.isfile(input_text):
        with open(input_text, "r", encoding="utf-8") as f:
            input_text = f.read()
    
    print("=" * 60)
    print("详细版概要：")
    print("=" * 60)
    print(generate_detailed_summary(input_text))
    print()
    print("=" * 60)
    print("简化版概要：")
    print("=" * 60)
    print(summarize_content_simple(input_text))
    print()
    
    # 输出提取的维度详情
    print("=" * 60)
    print("提取维度详情：")
    print("=" * 60)
    print(f"产品: {extract_products(input_text)}")
    print(f"卖点: {extract_by_keyword_dict(input_text, FEATURE_KEYWORDS)}")
    print(f"促销: {extract_by_keyword_dict(input_text, PROMOTION_KEYWORDS)}")
    print(f"价格: {extract_specific_prices(input_text)}")
    print(f"场景: {extract_by_keyword_dict(input_text, SCENARIO_KEYWORDS)}")
    print(f"背景: {extract_by_keyword_dict(input_text, STORY_KEYWORDS)}")
    print(f"互动: {extract_by_keyword_dict(input_text, INTERACTION_KEYWORDS)}")
