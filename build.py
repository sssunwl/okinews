#!/usr/bin/env python3
"""OKIPLAYGROUND 站台產生器。

把 templates/ + content/ + docs/*.json 合成多頁靜態站到 docs/。
不依賴第三方套件，CI 只要有 Python 3.8+ 就能跑。

用法：
    python3 build.py            # 只重建網頁（不重新爬資料）
"""

import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"

SITE_URL = os.getenv("SITE_URL", "https://sssunwl.github.io/okinews/").rstrip("/") + "/"
SITE_NAME = "OKIPLAYGROUND 沖繩遊樂園"
OG_IMAGE = SITE_URL + "assets/og-image.png"
JST = timezone(timedelta(hours=9))

# 導覽列（順序即權重）
NAV = [
    ("news", "news/", "新聞"),
    ("events", "events/", "活動"),
    ("guide", "guide/", "攻略"),
    ("ocean", "ocean/", "玩水"),
    ("goods", "goods/", "好物"),
    ("okinawa", "okinawa/", "認識沖繩"),
]

# 內容區塊定義：篩選軸決定該區 index 頁出現哪幾排 chip
# 地區標籤共用同一套：先分沖繩本島／沖繩外島，本島再細分南部／中部／北部，
# 最後才是實際地名（那霸等）。文章可以同時掛好幾層（例如 [沖繩本島, 南部, 那霸]），
# 篩選時每一層都能單獨點。
REGION_AXIS = ("地區", ["沖繩本島", "沖繩外島", "南部", "中部", "北部", "那霸"])

SECTIONS = {
    "guide": {
        "title": "沖繩旅遊攻略",
        "eyebrow": "Travel Guide",
        "lead": "依主題、旅行方式、月份與地區整理。先挑一個最接近你這趟的方式，再往下看細節。",
        "axes": [
            ("主題", ["食", "玩", "住", "買", "拍"]),
            ("旅行方式", ["一天遊", "自駕", "不自駕", "親子", "情侶", "一人", "三代同行", "長住"]),
            REGION_AXIS,
            ("月份", ["1月", "2月", "3月", "4月", "5月", "6月",
                     "7月", "8月", "9月", "10月", "11月", "12月"]),
        ],
    },
    "okinawa": {
        "title": "認識沖繩",
        "eyebrow": "Know Okinawa",
        "lead": "琉球王國、傳統祭典、信仰與禮儀。知道背景之後，同樣的風景會看得比較久。",
        "axes": [("主題", ["歷史", "傳統", "信仰", "language", "禮儀"]), REGION_AXIS],
    },
    "goods": {
        "title": "沖繩好物",
        "eyebrow": "Okinawa Goods",
        "lead": "工藝、超市便利店、100・300 円店與藥妝伴手禮。買得到、帶得回去、回家還會用的那些。",
        "axes": [("類型", ["工藝", "超市", "便利店", "100円", "藥妝", "食品"]), REGION_AXIS],
    },
    "ocean": {
        "title": "玩水・潛水",
        "eyebrow": "Ocean Time",
        "lead": "浮潛點、潛水店、季節與安全提醒。下水前先看一次，比到現場再問快。",
        "axes": [
            ("方式", ["浮潛", "潛水", "海灘", "SUP", "獨木舟"]),
            REGION_AXIS,
        ],
    },
}

# 個別好物卡片用的兩軸分類：店舖類型（去哪買）與好物類型（是什麼）。這不是一個
# 會產生獨立頁面的 SECTIONS 條目，只是 /goods/ 頁中間那格「好物卡片」的篩選軸。
GOODS_ITEM_AXES = [
    ("店舖類型", ["超市", "便利店", "藥妝", "100円", "300円"]),
    ("好物類型", ["藥品", "美妝", "護膚", "食品", "手信", "工藝品", "酒類"]),
]

REPORT = {"generated": "", "pages": 0, "skipped": [], "warnings": []}


def warn(message):
    REPORT["warnings"].append(message)
    print("⚠️  " + message)


def skip(what, why):
    REPORT["skipped"].append({"item": what, "reason": why})
    print("⏭️  跳過 {}：{}".format(what, why))


# ── 迷你 Markdown ────────────────────────────────────────────────────

SAFE_LINK = re.compile(r"^(https?://|/|\.{1,2}/|#)")


def _link(match):
    text, url = match.group(1), match.group(2)
    if not SAFE_LINK.match(url):
        return text
    external = url.startswith("http")
    attrs = ' target="_blank" rel="noopener"' if external else ""
    return '<a href="{}"{}>{}{}</a>'.format(url, attrs, text, " ↗" if external else "")


def _image(match):
    alt, src = match.group(1), match.group(2)
    if not SAFE_LINK.match(src):
        return ""
    return '<img src="{}" alt="{}" loading="lazy">'.format(src, alt)


def inline_md(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _image, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def markdown(source):
    """支援標題、清單、引言、表格、分隔線與段落的最小 Markdown 子集。"""
    lines = source.replace("\r\n", "\n").split("\n")
    out, index = [], 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            level = min(max(level, 2), 4)
            out.append("<h{0}>{1}</h{0}>".format(level, inline_md(stripped.lstrip("#").strip())))
            index += 1
            continue

        if re.match(r"^-{3,}$", stripped):
            out.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            block = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                block.append(lines[index].strip().lstrip(">").strip())
                index += 1
            out.append("<blockquote>{}</blockquote>".format(inline_md(" ".join(block))))
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[index + 1].strip()):
            header = [cell.strip() for cell in stripped.strip("|").split("|")]
            index += 2
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            thead = "".join("<th>{}</th>".format(inline_md(cell)) for cell in header)
            tbody = "".join(
                "<tr>{}</tr>".format("".join("<td>{}</td>".format(inline_md(cell)) for cell in row))
                for row in rows
            )
            out.append('<div class="table-wrap"><table><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>'
                       .format(thead, tbody))
            continue

        list_match = re.match(r"^([-*]|\d+\.)\s+", stripped)
        if list_match:
            ordered = not list_match.group(1) in ("-", "*")
            items = []
            while index < len(lines):
                item = lines[index].strip()
                match = re.match(r"^([-*]|\d+\.)\s+(.*)$", item)
                if not match:
                    break
                items.append("<li>{}</li>".format(inline_md(match.group(2))))
                index += 1
            tag = "ol" if ordered else "ul"
            out.append("<{0}>{1}</{0}>".format(tag, "".join(items)))
            continue

        block = []
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#|>|\||[-*]\s|\d+\.\s|-{3,})", lines[index].strip()):
            block.append(lines[index].strip())
            index += 1
        out.append("<p>{}</p>".format(inline_md(" ".join(block))))
    return "\n".join(out)


# ── Front matter（YAML 子集）─────────────────────────────────────────

def parse_scalar(value):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) > 1:
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.match(r"^-?\d+$", value):
        return int(value)
    return value


def parse_front_matter(text):
    """支援純量、行內陣列、`- ` 陣列、一層巢狀 map 與 `|` 區塊字串。"""
    data = {}
    stack = [(-1, data)]
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.strip().startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]

        if stripped.startswith("- "):
            if not isinstance(container, list):
                index += 1
                continue
            container.append(parse_scalar(stripped[2:]))
            index += 1
            continue

        if ":" not in stripped:
            index += 1
            continue

        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()

        if value == "|":
            block, index = [], index + 1
            while index < len(lines) and (not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip(" ")) > indent):
                block.append(lines[index][indent + 2:] if lines[index].strip() else "")
                index += 1
            container[key] = "\n".join(block).strip("\n")
            continue

        if value == "":
            peek = index + 1
            while peek < len(lines) and not lines[peek].strip():
                peek += 1
            child = []
            if peek < len(lines):
                child_indent = len(lines[peek]) - len(lines[peek].lstrip(" "))
                if child_indent > indent and not lines[peek].strip().startswith("- "):
                    child = {}
            container[key] = child
            stack.append((indent, child))
            index += 1
            continue

        container[key] = parse_scalar(value)
        index += 1
    return data


def load_content():
    """讀 content/<section>/*.md，回傳 {section: [post, ...]}。"""
    posts = {key: [] for key in SECTIONS}
    if not CONTENT.exists():
        return posts
    for section in SECTIONS:
        folder = CONTENT / section
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            if not raw.startswith("---"):
                skip(str(path.relative_to(ROOT)), "缺少 front matter")
                continue
            _, _, rest = raw.partition("---")
            front, _, body = rest.partition("\n---")
            meta = parse_front_matter(front)
            meta["section"] = section
            meta.setdefault("slug", path.stem)
            meta["body"] = body.strip()
            problems = validate_post(meta)
            if problems:
                skip(str(path.relative_to(ROOT)), "；".join(problems))
                continue
            posts[section].append(meta)
        posts[section].sort(key=lambda item: str(item.get("updated", "")), reverse=True)
    return posts


def load_goods_items():
    """讀 content/goods-items/*.md：沒有內文的輕量卡片（圖示＋名稱＋簡介＋去哪買＋價位）。"""
    folder = CONTENT / "goods-items"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            skip(str(path.relative_to(ROOT)), "缺少 front matter")
            continue
        _, _, rest = raw.partition("---")
        front, _, _ = rest.partition("\n---")
        meta = parse_front_matter(front)
        problems = validate_goods_item(meta)
        if problems:
            skip(str(path.relative_to(ROOT)), "；".join(problems))
            continue
        items.append(meta)
    return items


def load_months():
    """讀 content/months/*.md：12 篇月份速覽，回傳依月份排序的 list。"""
    folder = CONTENT / "months"
    if not folder.exists():
        return []
    months = []
    for path in sorted(folder.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            skip(str(path.relative_to(ROOT)), "缺少 front matter")
            continue
        _, _, rest = raw.partition("---")
        front, _, body = rest.partition("\n---")
        meta = parse_front_matter(front)
        meta["body"] = body.strip()
        problems = validate_month(meta)
        if problems:
            skip(str(path.relative_to(ROOT)), "；".join(problems))
            continue
        months.append(meta)
    months.sort(key=lambda item: item.get("month", 0))
    return months


def validate_month(meta):
    problems = []
    month = meta.get("month")
    if not isinstance(month, int) or not (1 <= month <= 12):
        problems.append("month 要是 1-12 的整數")
    for field in ("title", "blurb", "weather", "body"):
        if not meta.get(field):
            problems.append("缺 {}".format(field))
    return problems


def validate_goods_item(meta):
    problems = []
    for field in ("name", "blurb", "where", "price"):
        if not meta.get(field):
            problems.append("缺 {}".format(field))
    tags = meta.get("tags") or []
    if not isinstance(tags, list) or not tags:
        problems.append("tags 至少要有一個")
    return problems


def validate_post(meta):
    """全自動發佈的機器關卡：缺必要欄位就不上線，不讓半成品見客。"""
    problems = []
    if not meta.get("title"):
        problems.append("缺 title")
    if not meta.get("summary"):
        problems.append("缺 summary")
    if not meta.get("body"):
        problems.append("內文是空的")
    if not re.match(r"^[a-z0-9-]+$", str(meta.get("slug", ""))):
        problems.append("slug 只能用小寫英數與連字號")
    updated = str(meta.get("updated", ""))
    if updated and not re.match(r"^\d{4}-\d{2}-\d{2}$", updated):
        problems.append("updated 要寫成 YYYY-MM-DD")
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        problems.append("tags 要寫成陣列")
    return problems


# ── 頁面組裝 ─────────────────────────────────────────────────────────

def template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def fill(text, mapping):
    for key, value in mapping.items():
        text = text.replace("<<<{}>>>".format(key), str(value))
    return text


def nav_html(prefix, active, mobile=False):
    items = []
    for key, href, label in NAV:
        cls = ' class="active"' if key == active else ""
        items.append('      <a href="{}{}"{}>{}</a>'.format(prefix, href, cls, label))
    if mobile:
        items.append('      <a href="{}toolkit/">旅行小抄</a>'.format(prefix))
    return "\n".join(items)


def render_page(path, main, title, description, active="", page_data="", page_script="",
                body_class="", og_type="website"):
    """path 是相對 docs/ 的資料夾路徑（'' 代表首頁）。"""
    depth = len([part for part in path.split("/") if part])
    prefix = "../" * depth
    canonical = SITE_URL + (path + "/" if path else "")
    page = fill(template("base.html"), {
        "TITLE": html.escape(title, quote=True),
        "DESC": html.escape(description, quote=True),
        "CANONICAL": canonical,
        "OG_TYPE": og_type,
        "OG_IMAGE": OG_IMAGE,
        "PREFIX": prefix,
        "BODY_CLASS": body_class,
        "NAV": nav_html(prefix, active),
        "NAV_MOBILE": nav_html(prefix, active, mobile=True),
        "MAIN": main,
        "PAGE_DATA": page_data,
        "PAGE_SCRIPT": page_script,
        "UPDATED": REPORT["generated"],
    })
    target = DOCS / path / "index.html" if path else DOCS / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    REPORT["pages"] += 1
    return canonical


def json_block(element_id, payload):
    text = json.dumps(payload, ensure_ascii=False).replace("</script>", "<\\/script>")
    return '<script type="application/json" id="{}">{}</script>'.format(element_id, text)


def post_href(post, prefix=""):
    return "{}{}/{}/".format(prefix, post["section"], post["slug"])


def post_card(post, prefix=""):
    tags = post.get("tags") or []
    cover = post.get("cover")
    style = ' style="background-image:url(\'{}{}\')"'.format(prefix + "assets/covers/", html.escape(cover, quote=True)) if cover else ""
    chips = "".join('<span>{}</span>'.format(html.escape(str(tag))) for tag in tags[:3])
    return (
        '<a class="post-card{cover_cls}" href="{href}" data-tags="{tags}"{style}>'
        '<div class="post-card-body">'
        '<div class="post-tags">{chips}</div>'
        '<h3>{title}</h3><p>{summary}</p>'
        '<span class="post-more">看內容 →</span>'
        '</div></a>'
    ).format(
        cover_cls=" has-cover" if cover else "",
        href=post_href(post, prefix),
        tags=html.escape("|".join(str(tag) for tag in tags), quote=True),
        style=style,
        chips=chips,
        title=html.escape(str(post.get("title", ""))),
        summary=html.escape(str(post.get("summary", ""))),
    )


def row_cards(posts, prefix="", limit=3):
    if not posts:
        return ('      <div class="empty-state"><strong>內容整理中</strong>'
                '這一區的文章正在寫，很快會放上來。</div>')
    return '      <div class="post-grid">{}</div>'.format(
        "".join(post_card(post, prefix) for post in posts[:limit]))


def build_home(posts, events, weather, news, months):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    horizon = (datetime.now(JST) + timedelta(days=90)).strftime("%Y-%m-%d")
    home_events = [
        event for event in events
        if event.get("date_start") and today <= event["date_start"] <= horizon
    ][:60]

    okinawa_posts = posts.get("okinawa") or []
    if okinawa_posts:
        feature = okinawa_posts[0]
        banner = (
            '  <section class="know-banner combo-col">\n'
            '    <div class="shell know-card">\n'
            '      <div><div class="eyebrow">Know Okinawa</div>'
            '<h2>{title}</h2><p>{summary}</p>'
            '<a class="know-link" href="{href}">讀這篇 →</a></div>\n'
            '      <a class="know-all" href="okinawa/">認識沖繩全部主題 →</a>\n'
            '    </div>\n'
            '  </section>\n'
        ).format(
            title=html.escape(str(feature.get("title", ""))),
            summary=html.escape(str(feature.get("summary", ""))),
            href=post_href(feature),
        )
    else:
        banner = (
            '  <section class="know-banner combo-col">\n'
            '    <div class="shell know-card">\n'
            '      <div><div class="eyebrow">Know Okinawa</div>'
            '<h2>認識沖繩</h2><p>琉球王國、傳統祭典與信仰。內容整理中。</p>'
            '<a class="know-link" href="okinawa/">看這一區 →</a></div>\n'
            '    </div>\n'
            '  </section>\n'
        )

    main = fill(template("home.html"), {
        "MONTH_STRIP": month_strip_html(months),
        "GUIDE_PICKS": row_cards(posts.get("guide"), limit=4),
        "OKINAWA_BANNER": banner,
        "OCEAN_ROW": row_cards(posts.get("ocean")),
        "GOODS_ROW": row_cards(posts.get("goods")),
    })
    data = "\n".join([
        json_block("eventData", home_events),
        json_block("weatherData", weather),
        json_block("newsData", news[:3]),
    ])
    render_page(
        "", main,
        "OKIPLAYGROUND 沖繩遊樂園｜今天，在沖繩玩什麼？",
        "沖繩天氣、每日新聞、活動年曆與旅遊攻略。整理成繁體中文，幫你快速決定今天要去哪裡。",
        active="", page_data=data,
        page_script='<script src="assets/home.js"></script>',
    )


def event_slug(event):
    identity = "|".join([
        str(event.get("source", "")),
        str(event.get("date_start", "")),
        str(event.get("url") or event.get("name_zh") or event.get("name") or ""),
    ])
    return "e" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]


def event_source_name(event):
    source = event.get("source")
    if source == "okinawastory":
        return "おきなわ物語"
    if source == "visitokinawa":
        return "Visit Okinawa"
    return source or "原始來源"


def event_display_name(event):
    return event.get("name_zh") or event.get("name") or "未命名活動"


def build_event_pages(events):
    """只給『找得到官方網站』的活動生成獨立介紹頁——這是唯一的外連對象，
    不把 okinawastory / visitokinawa 這類旅遊平台當成活動的主要連結。"""
    urls = []
    for event in events:
        official = str(event.get("official_url") or "")
        if not official.startswith(("http://", "https://")):
            continue  # 抓不到官方網站，先不生成獨立頁，只留在年曆列表

        slug = event_slug(event)
        event["_detail_slug"] = slug
        name = event_display_name(event)
        name_ja = event.get("name") or ""
        subtitle = ""
        if name_ja and name_ja != name:
            subtitle = '      <p class="article-lead">{}</p>'.format(html.escape(name_ja))

        meta_bits = []
        date_text = str(event.get("date_start") or "")
        if date_text:
            if event.get("date_end") and event["date_end"] != event["date_start"]:
                date_text += " ～ " + str(event["date_end"])
            meta_bits.append("<span>{}</span>".format(html.escape(date_text)))
        if event.get("category"):
            meta_bits.append('<span class="tag">{}</span>'.format(html.escape(str(event["category"]))))

        cover = ""
        image = str(event.get("image") or "")
        if image.startswith(("http://", "https://")):
            cover = '      <img class="article-cover" src="{}" alt="" loading="lazy">'.format(
                html.escape(image, quote=True))

        body_parts = []
        description = str(event.get("description") or "")
        if description:
            body_parts.append("<p>{}</p>".format(html.escape(description)))
        rows = []
        if event.get("location"):
            rows.append(("地點", str(event["location"])))
        if event.get("price"):
            rows.append(("費用", str(event["price"])))
        if rows:
            body_parts.append(
                '<table class="event-table"><tbody>{}</tbody></table>'.format(
                    "".join('<tr><th>{}</th><td>{}</td></tr>'.format(html.escape(k), html.escape(v))
                            for k, v in rows)
                )
            )
        if not body_parts:
            body_parts.append("<p>詳細資訊請見官方網站。</p>")

        main = fill(template("event.html"), {
            "BREADCRUMB": '<a href="../../">首頁</a><span>/</span><a href="../../events/">活動年曆</a>',
            "EVENT_TITLE": html.escape(name),
            "EVENT_SUBTITLE": subtitle,
            "EVENT_META": "".join(meta_bits),
            "COVER": cover,
            "BODY": "\n".join(body_parts),
            "OFFICIAL_URL": html.escape(official, quote=True),
            "SOURCE_NAME": html.escape(event_source_name(event)),
        })
        canonical = render_page(
            "events/{}".format(slug), main,
            "{}｜OKIPLAYGROUND".format(name),
            (description or name)[:150],
            active="events",
        )
        urls.append(canonical)
    return urls


def build_events(events, updated_count):
    main = template("events.html")
    render_page(
        "events", main,
        "沖繩活動年曆｜OKIPLAYGROUND",
        "沖繩祭典、花火、季節活動與文化日的年曆。可依日期、關鍵字與地區查詢，共 {} 筆資料。".format(updated_count),
        active="events",
        page_data=json_block("eventData", events),
        page_script='<script src="../assets/events.js"></script>',
    )


def goods_item_card(item):
    tags = item.get("tags") or []
    tag_chips = "".join('<span>{}</span>'.format(html.escape(str(tag))) for tag in tags)
    return (
        '<article class="item-card" data-tags="{tags_attr}">'
        '<div class="item-emoji">{emoji}</div>'
        '<div class="item-body">'
        '<h3>{name}</h3><p>{blurb}</p>'
        '<div class="item-meta"><span>📍 {where}</span><span>💰 {price}</span></div>'
        '<div class="item-tags">{tag_chips}</div>'
        '</div></article>'
    ).format(
        tags_attr=html.escape("|".join(str(tag) for tag in tags), quote=True),
        emoji=html.escape(str(item.get("emoji", "🛍️"))),
        name=html.escape(str(item.get("name", ""))),
        blurb=html.escape(str(item.get("blurb", ""))),
        where=html.escape(str(item.get("where", ""))),
        price=html.escape(str(item.get("price", ""))),
        tag_chips=tag_chips,
    )


REGIONS_MAIN = [
    {
        "slug": "nanbu",
        "title": "南部",
        "subtitle": "那霸・糸滿・南城",
        "blurb": "機場最近、行程頭尾都方便。首里城、國際通、平和祈念公園、玉泉洞鐘乳石洞都在這一段，第一天落地、最後一天要走都排這裡最順。",
    },
    {
        "slug": "chubu",
        "title": "中部",
        "subtitle": "北谷・嘉手納・沖繩市・恩納村・讀谷",
        "blurb": "全島潛水、衝浪、夜生活最密集的一段：美國村、真栄田岬青の洞窟、砂邊、萬座毛、殘波岬都在這裡，很多人整趟只待中部不移動。",
    },
    {
        "slug": "hokubu",
        "title": "北部",
        "subtitle": "名護・本部・今歸仁",
        "blurb": "步調最慢、離島感最重的本島段。美麗海水族館、古宇利島、山原國家公園都在這，適合排在行程後段慢慢晃。",
    },
]

REGIONS_OUTER = [
    {
        "slug": "ishigaki",
        "title": "石垣島",
        "subtitle": "八重山群島門戶",
        "blurb": "有機場可直飛，是八重山群島的轉運中心。川平灣、與那國/竹富島的船班都從這裡出發，潛水看海鰻、鬼蝠魟是強項。",
    },
    {
        "slug": "miyako",
        "title": "宮古島",
        "subtitle": "全日本數一數二的藍",
        "blurb": "島上沒有山，地形平坦，海水清澈度是全日本前段班。來間大橋、伊良部大橋開車就能到，適合喜歡海景勝過市區的人。",
    },
    {
        "slug": "kumejima",
        "title": "久米島",
        "subtitle": "那霸飛 40 分鐘",
        "blurb": "はての浜沙洲、鳥島海龜保護區，遊客比石垣、宮古少很多，適合想避開人潮、單純看海發呆的行程。",
    },
    {
        "slug": "kerama",
        "title": "慶良間諸島",
        "subtitle": "渡嘉敷・座間味",
        "blurb": "那霸出發船程約 1 小時，能見度是全日本數一數二，賞鯨季（冬春）跟浮潛旺季（夏）都值得專程跑一趟。",
    },
    {
        "slug": "iejima",
        "title": "伊江島",
        "subtitle": "本部渡輪 30 分鐘",
        "blurb": "從本部半島搭渡輪半小時就到，適合當天來回。城山（伊江島タッチュー）登頂看海，四月百合花季是最熱門的時候。",
    },
]


def region_row_html(eyebrow, heading, regions):
    cards = "".join(
        '<button type="button" class="okiregion-card" data-okiregion-card aria-expanded="false">'
        '<span class="okiregion-title">{title}<small>{subtitle}</small></span>'
        '<span class="okiregion-blurb">{blurb}</span>'
        '</button>'.format(
            title=html.escape(str(region.get("title", ""))),
            subtitle=html.escape(str(region.get("subtitle", ""))),
            blurb=html.escape(str(region.get("blurb", ""))),
        )
        for region in regions
    )
    return (
        '<div class="okiregion-row-head"><span class="eyebrow">{eyebrow}</span><h3>{heading}</h3></div>'
        '<div class="okiregion-grid">{cards}</div>'
    ).format(eyebrow=html.escape(eyebrow), heading=html.escape(heading), cards=cards)


def region_intro_html():
    return (
        '  <section class="okiregion-intro" id="okiregion-intro">\n'
        '    <div class="shell">\n'
        '      <p class="okiregion-intro-note">滑過或點一下卡片看介紹——沖繩本島先分三段，外島是另一趟行程。</p>\n'
        '      {main_row}\n'
        '      {outer_row}\n'
        '    </div>\n'
        '  </section>\n'
    ).format(
        main_row=region_row_html("Okinawa Main Island", "沖繩本島，先分三段。", REGIONS_MAIN),
        outer_row=region_row_html("Outer Islands", "沖繩外島，還可以走更遠。", REGIONS_OUTER),
    )


def goods_items_html(items):
    if not items:
        return ""

    used_tags = set()
    for item in items:
        for tag in (item.get("tags") or []):
            used_tags.add(str(tag))

    rows = []
    for axis_name, values in GOODS_ITEM_AXES:
        chips = [tag for tag in values if tag in used_tags]
        if not chips:
            continue
        buttons = "".join(
            '<button class="tag-chip" type="button" data-tag="{0}">{0}</button>'.format(html.escape(tag))
            for tag in chips
        )
        rows.append('        <div class="filter-row"><span class="filter-label">{}</span>'
                    '<div class="filter-chips">{}</div></div>'.format(html.escape(axis_name), buttons))

    filters = ""
    if rows:
        filters = (
            '      <div class="filter-block" id="itemFilters" data-target="itemGrid">\n'
            '        <div class="filter-row"><span class="filter-label">全部</span>'
            '<div class="filter-chips"><button class="tag-chip active" type="button" data-tag="">看全部</button></div></div>\n'
            + "\n".join(rows) + "\n      </div>"
        )

    cards = "\n".join("        " + goods_item_card(item) for item in items)

    return (
        '  <section class="goods-items">\n'
        '    <div class="shell">\n'
        '      <div class="section-head">\n'
        '        <div><div class="eyebrow">Pick a Good</div><h2>先看單品，<br>再決定去哪買。</h2></div>\n'
        '        <p>每一件都標好在哪買、大概多少錢，篩一下類型比較快找到你要的。</p>\n'
        '      </div>\n'
        '{filters}\n'
        '      <div class="item-grid" id="itemGrid">\n'
        '{cards}\n'
        '      </div>\n'
        '      <div class="empty-state" id="itemEmpty" hidden><strong>這個組合暫時沒有東西</strong>換個條件再看看。</div>\n'
        '    </div>\n'
        '  </section>\n'
    ).format(filters=filters, cards=cards)


TIDE_ARROWS = {"上漲": "↑", "下降": "↓"}
CN_DIGITS = "零一二三四五六七八九十"


def cn_num(n):
    return CN_DIGITS[n] if 0 <= n < len(CN_DIGITS) else str(n)


def cond_point_payload(wind_dir, wind_speed, wave, tide, verdict, label, reason):
    return json.dumps({
        "wind": "{} {} 節".format(html.escape(str(wind_dir)), html.escape(str(wind_speed))),
        "wave": "{} m".format(html.escape(str(wave))),
        "tide": "{} m".format(html.escape(str(tide))),
        "verdict": html.escape(str(verdict)),
        "label": html.escape(str(label)),
        "reason": html.escape(str(reason)),
    }, ensure_ascii=False).replace("'", "&#39;")


def ocean_timeline_html(spot):
    points = spot.get("timeline") or []
    if not points:
        return ""

    now_payload = cond_point_payload(
        spot.get("wind_dir_label", ""), spot.get("wind_speed_kn", ""),
        spot.get("wave_height_m", ""), spot.get("tide_m", ""),
        spot.get("verdict", "caution"), spot.get("verdict_label", ""),
        spot.get("verdict_reason", ""),
    )
    now_button = (
        '<button type="button" class="cond-hour cond-hour-now active" data-hour="now" '
        'data-point=\'{payload}\'>現在</button>'
    ).format(payload=now_payload)

    buttons = []
    for point in points:
        hour = str(point.get("hour", ""))
        payload = cond_point_payload(
            point.get("wind_dir_label", ""), point.get("wind_speed_kn", ""),
            point.get("wave_height_m", ""), point.get("tide_m", ""),
            point.get("verdict", "caution"), point.get("verdict_label", ""),
            point.get("verdict_reason", ""),
        )
        tomorrow = point.get("is_tomorrow")
        buttons.append(
            '<button type="button" class="cond-hour cond-{level}{tmr_class}" '
            'data-hour="{hour}" data-point=\'{payload}\'{title}>{hour}</button>'.format(
                level=html.escape(str(point.get("verdict", "caution"))),
                tmr_class=" cond-hour-tomorrow" if tomorrow else "",
                hour=html.escape(hour),
                payload=payload,
                title=' title="明天 {}:00"'.format(html.escape(hour)) if tomorrow else "",
            )
        )

    return (
        '<div class="cond-timeline" data-cond-timeline>'
        '<div class="cond-timeline-head"><span>逐時海況</span></div>'
        '<div class="cond-hour-track">'
        '{now_button}'
        '<div class="cond-hour-scroll">'
        '<div class="cond-hour-row">{buttons}</div>'
        '<div class="cond-scrollbar"><div class="cond-scrollbar-thumb"></div></div>'
        '</div>'
        '</div>'
        '</div>'
    ).format(now_button=now_button, buttons="".join(buttons))


def condition_tabs_html(spots):
    if len(spots) < 2:
        return ""
    tabs = "".join(
        '<button type="button" class="cond-tab{active}" data-cond-tab="{index}">{name}</button>'.format(
            active=" active" if index == 0 else "",
            index=index,
            name=html.escape(str(spot.get("name", ""))),
        )
        for index, spot in enumerate(spots)
    )
    return '<div class="cond-tabs" data-cond-tabs>{}</div>'.format(tabs)


def ocean_conditions_html(conditions, note_label="地形要注意", heading="", eyebrow="Live Conditions",
                           section_id="live-conditions", section_class="ocean-conditions"):
    spots = (conditions or {}).get("spots") or []
    if not spots:
        return ""

    cards = []
    for index, spot in enumerate(spots):
        turn = spot.get("tide_turn") or {}
        turn_text = ""
        if turn.get("time"):
            hours = turn.get("hours_away", 0)
            if hours == 0:
                turn_text = "現在接近{}（{}）".format(turn["kind"], turn["time"])
            elif hours > 0:
                turn_text = "約 {} 小時後{}（{}）".format(hours, turn["kind"], turn["time"])
            else:
                turn_text = "約 {} 小時前{}（{}）".format(abs(hours), turn["kind"], turn["time"])

        official = ""
        if spot.get("official_note"):
            official = '<p class="cond-official">📍 {}</p>'.format(html.escape(str(spot["official_note"])))

        official_link = ""
        if spot.get("official_url"):
            official_link = '<a class="cond-link cond-link-official" href="{url}" target="_blank" rel="noopener">{label}</a>'.format(
                url=html.escape(str(spot["official_url"]), quote=True),
                label=html.escape(str(spot.get("official_label") or "官方即時資訊 ↗")),
            )

        cards.append((
            '<article class="cond-card cond-{level}" data-cond-card="{index}">'
            '<div class="cond-head"><h3>{name}</h3><span class="cond-badge" data-cond-badge>{label}</span></div>'
            '<p class="cond-region">{region}・{kind}</p>'
            '<div class="cond-grid" data-cond-grid>'
            '<div><span>風</span><strong data-cond-wind>{wind_dir} {wind_speed} 節</strong><small>陣風 {gust} 節</small></div>'
            '<div><span>浪高</span><strong data-cond-wave>{wave} m</strong><small>湧浪 {swell}m・{period}s</small></div>'
            '<div><span>潮位</span><strong data-cond-tide>{tide} m {arrow}</strong><small>{turn_text}</small></div>'
            '</div>'
            '<p class="cond-reason" data-cond-reason>{reason}</p>'
            '{timeline}'
            '<p class="cond-exposure"><strong>{note_label}：</strong>{exposure}</p>'
            '{official}'
            '<div class="cond-links">'
            '<a class="cond-link" href="{ref_url}" target="_blank" rel="noopener">看完整逐時預報 ↗</a>'
            '{official_link}'
            '</div>'
            '</article>'
        ).format(
            index=index,
            level=html.escape(str(spot.get("verdict", "caution"))),
            name=html.escape(str(spot.get("name", ""))),
            label=html.escape(str(spot.get("verdict_label", ""))),
            region=html.escape(str(spot.get("region", ""))),
            kind=html.escape(str(spot.get("kind", ""))),
            wind_dir=html.escape(str(spot.get("wind_dir_label", ""))),
            wind_speed=html.escape(str(spot.get("wind_speed_kn", ""))),
            gust=html.escape(str(spot.get("wind_gust_kn", ""))),
            wave=html.escape(str(spot.get("wave_height_m", ""))),
            swell=html.escape(str(spot.get("swell_height_m", ""))),
            period=html.escape(str(spot.get("swell_period_s", ""))),
            tide=html.escape(str(spot.get("tide_m", ""))),
            arrow=TIDE_ARROWS.get(spot.get("tide_trend", ""), ""),
            turn_text=html.escape(turn_text),
            reason=html.escape(str(spot.get("verdict_reason", ""))),
            timeline=ocean_timeline_html(spot),
            note_label=html.escape(note_label),
            exposure=html.escape(str(spot.get("exposure", ""))),
            official=official,
            official_link=official_link,
            ref_url=html.escape(str(spot.get("reference_url", "")), quote=True),
        ))

    caution = ""
    if conditions.get("general_caution"):
        caution = '<p class="cond-caution-note">⚠️ {}</p>'.format(
            html.escape(str(conditions["general_caution"]))
        )

    return (
        '  <section class="{section_class}" id="{section_id}">\n'
        '    <div class="shell">\n'
        '      <div class="cond-head-row">\n'
        '        <div><div class="eyebrow">{eyebrow}</div><h2>{heading}</h2></div>\n'
        '        <p class="cond-updated">更新於 {updated} JST・資料來自 Open-Meteo，僅供參考，實際請以現場、教練與官方公告為準</p>\n'
        '      </div>\n'
        '      {caution}\n'
        '      {tabs}\n'
        '      <div class="cond-grid-wrap" data-cond-group>{cards}</div>\n'
        '    </div>\n'
        '  </section>\n'
    ).format(
        section_class=section_class,
        section_id=section_id,
        eyebrow=html.escape(eyebrow),
        heading=html.escape(heading),
        updated=html.escape(str(conditions.get("updated", ""))),
        caution=caution,
        tabs=condition_tabs_html(spots),
        cards="".join(cards),
    )


def build_section(key, posts, extra_block="", show_filters=True, cards_heading=""):
    meta = SECTIONS[key]
    used_tags = set()
    for post in posts:
        for tag in (post.get("tags") or []):
            used_tags.add(str(tag))

    rows = []
    if show_filters:
        for axis_name, values in meta["axes"]:
            chips = [tag for tag in values if tag in used_tags]
            if not chips:
                continue
            buttons = "".join(
                '<button class="tag-chip" type="button" data-tag="{0}">{0}</button>'.format(html.escape(tag))
                for tag in chips
            )
            rows.append('        <div class="filter-row"><span class="filter-label">{}</span>'
                        '<div class="filter-chips">{}</div></div>'.format(html.escape(axis_name), buttons))
    filters = ""
    if rows:
        filters = ('      <div class="filter-block" id="postFilters" data-target="postGrid">\n'
                   '        <div class="filter-row"><span class="filter-label">全部</span>'
                   '<div class="filter-chips"><button class="tag-chip active" type="button" data-tag="">看全部</button></div></div>\n'
                   + "\n".join(rows) + "\n      </div>")

    heading = ""
    if cards_heading:
        heading = '      <h2 class="cards-heading">{}</h2>\n'.format(html.escape(cards_heading))

    cards = "\n".join("        " + post_card(post, "../") for post in posts) or \
        '        <div class="empty-state"><strong>內容整理中</strong>這一區的文章正在寫，很快會放上來。</div>'

    main = fill(template("section.html"), {
        "SECTION_TITLE": html.escape(meta["title"]),
        "SECTION_EYEBROW": meta["eyebrow"],
        "SECTION_LEAD": html.escape(meta["lead"]),
        "EXTRA_BLOCK": extra_block,
        "CARDS_HEADING": heading,
        "FILTERS": filters,
        "CARDS": cards,
    })
    render_page(
        key, main,
        "{}｜OKIPLAYGROUND".format(meta["title"]),
        meta["lead"],
        active=key,
        page_script='<script src="../assets/section.js"></script>' if (filters or extra_block) else "",
    )


def related_posts(post, siblings):
    tags = set(str(tag) for tag in (post.get("tags") or []))
    scored = []
    for other in siblings:
        if other["slug"] == post["slug"]:
            continue
        overlap = len(tags & set(str(tag) for tag in (other.get("tags") or [])))
        scored.append((overlap, other))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [other for score, other in scored[:3] if score > 0] or [other for _, other in scored[:2]]


def build_article(post, siblings):
    meta = SECTIONS[post["section"]]
    prefix = "../../"
    tags = post.get("tags") or []
    meta_bits = []
    if post.get("updated"):
        meta_bits.append('<span>更新 {}</span>'.format(html.escape(str(post["updated"]))))
    meta_bits += ['<span class="tag">{}</span>'.format(html.escape(str(tag))) for tag in tags]

    cover = ""
    if post.get("cover"):
        cover = ('      <img class="article-cover" src="{}assets/covers/{}" alt="" loading="lazy">'
                 .format(prefix, html.escape(str(post["cover"]), quote=True)))

    ig = post.get("ig") or {}
    ig_slot = ""
    if isinstance(ig, dict) and ig.get("slides"):
        slides = ig.get("slides") or []
        cards = "".join(
            '<div class="ig-slide"><span>{}</span><p>{}</p></div>'.format(index + 1, html.escape(str(slide)))
            for index, slide in enumerate(slides)
        )
        ig_slot = (
            '      <section class="ig-slot" data-ig-embed aria-label="這篇的 IG 版本">\n'
            '        <div class="ig-slot-head"><span class="eyebrow">Carousel</span>'
            '<strong>{}</strong></div>\n'
            '        <div class="ig-track">{}</div>\n'
            '      </section>'
        ).format(html.escape(str(ig.get("cover") or post.get("title", ""))), cards)

    related = related_posts(post, siblings)
    related_html = ""
    if related:
        related_html = (
            '  <section class="related">\n'
            '    <div class="shell">\n'
            '      <div class="section-head"><div><div class="eyebrow">Keep Reading</div>'
            '<h2>接著看這幾篇。</h2></div></div>\n'
            '      <div class="post-grid">{}</div>\n'
            '    </div>\n'
            '  </section>\n'
        ).format("".join(post_card(other, prefix) for other in related))

    breadcrumb = '<a href="{0}">首頁</a><span>/</span><a href="{0}{1}/">{2}</a>'.format(
        prefix, post["section"], html.escape(meta["title"]))

    main = fill(template("article.html"), {
        "BREADCRUMB": breadcrumb,
        "ARTICLE_TITLE": html.escape(str(post.get("title", ""))),
        "ARTICLE_SUMMARY": html.escape(str(post.get("summary", ""))),
        "ARTICLE_META": "".join(meta_bits),
        "COVER": cover,
        "BODY": markdown(post["body"]),
        "IG_SLOT": ig_slot,
        "RELATED": related_html,
    })
    return render_page(
        "{}/{}".format(post["section"], post["slug"]), main,
        "{}｜OKIPLAYGROUND".format(post.get("title", "")),
        str(post.get("summary", "")),
        active=post["section"],
        og_type="article",
        page_script='<script src="../../assets/ig-carousel.js"></script>' if ig_slot else "",
    )


NEWS_OKINAWA_SOURCES = ("沖縄タイムス", "氣象庁警報")


def news_entry_html(item):
    return (
        '<article class="news-item">'
        '<div class="news-meta"><span class="news-cat">{cat}</span><span>{source}</span></div>'
        '<h3>{title}</h3><p>{summary}</p>'
        '<a href="{url}" target="_blank" rel="noopener">看原文 ↗</a>'
        '</article>'
    ).format(
        cat=html.escape(str(item.get("category", "沖繩"))),
        source=html.escape(str(item.get("source", ""))),
        title=html.escape(str(item.get("title", ""))),
        summary=html.escape(str(item.get("summary", ""))),
        url=html.escape(str(item.get("url", "")), quote=True),
    )


def news_column_html(title, items):
    body = "".join(news_entry_html(item) for item in items) if items else (
        '<p class="news-col-empty">這天沒有這類消息。</p>')
    return ('<div class="news-col"><h3 class="news-col-title">{}</h3>'
            '<div class="news-list">{}</div></div>').format(html.escape(title), body)


def build_news(news):
    if news:
        alerts = [item for item in news if item.get("alert")]
        alert_html = ""
        if alerts:
            alert_html = ('      <div class="news-alerts"><strong>旅客請注意</strong><ul>{}</ul></div>'.format(
                "".join('<li>{}</li>'.format(html.escape(str(item["title"]))) for item in alerts[:4])))
        groups = {}
        for item in news:
            groups.setdefault(str(item.get("date", "")), []).append(item)
        blocks = []
        for date in sorted(groups, reverse=True):
            oki_items = [item for item in groups[date] if item.get("source") in NEWS_OKINAWA_SOURCES]
            japan_items = [item for item in groups[date] if item.get("source") not in NEWS_OKINAWA_SOURCES]
            columns = (
                news_column_html("🏝️ 沖繩新聞", oki_items) +
                news_column_html("🗾 日本大事", japan_items)
            )
            blocks.append(
                '      <section class="news-day"><h2>{}</h2><div class="news-columns">{}</div></section>'
                .format(html.escape(date), columns))
        body = alert_html + "\n" + "\n".join(blocks)
    else:
        body = ('      <div class="empty-state"><strong>新聞整理中</strong>'
                '每日自動彙整的沖繩新聞與日本大事很快就會出現在這裡。</div>')

    main = (
        '  <section class="page-head">\n'
        '    <div class="shell">\n'
        '      <div class="eyebrow">Okinawa News</div>\n'
        '      <h1>沖繩新聞・日本大事</h1>\n'
        '      <p>每日自動彙整，只做重點摘要與原文連結，不轉載全文。影響旅客的消息會排在最前面。</p>\n'
        '    </div>\n'
        '  </section>\n\n'
        '  <section class="news-section">\n'
        '    <div class="shell">\n'
        '{}\n'
        '    </div>\n'
        '  </section>\n'
    ).format(body)

    render_page("news", main, "沖繩新聞・日本大事｜OKIPLAYGROUND",
                "每日彙整沖繩在地新聞與日本重要消息的繁體中文摘要，並標出會影響旅客的交通、天氣與活動異動。",
                active="news")


MONTH_NAMES = ["", "1月", "2月", "3月", "4月", "5月", "6月", "7月",
               "8月", "9月", "10月", "11月", "12月"]


def _month_minutes(hhmm):
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def month_dashboard_html(month):
    """月份頁最上面的氣候小儀表板：溫度帶、降雨量、颱風接近頻率、日出日落。
    數字來自氣象庁 1991-2020 年平年值（那霸）與台風接近数平年值，寫在各月 frontmatter 裡。
    每個長條預設寬度是 0，捲到看得到時 assets/months.js 用 IntersectionObserver
    加 .in-view class 才展開——跟站上其他 hover 互動的卡片刻意做出不同的手感。"""
    try:
        avg_t = float(month["avg_temp"])
        max_t = float(month["max_temp"])
        min_t = float(month["min_temp"])
        rain = float(month["rain_mm"])
        typhoon = float(month["typhoon_avg"])
    except (KeyError, TypeError, ValueError):
        return ""

    sunrise = str(month.get("sunrise", ""))
    sunset = str(month.get("sunset", ""))
    sr_min = _month_minutes(sunrise)
    ss_min = _month_minutes(sunset)

    scale_lo, scale_hi = 14.0, 33.0
    span = scale_hi - scale_lo

    def pct(value):
        return max(0, min(100, round((value - scale_lo) / span * 100, 1)))

    min_pct, max_pct, avg_pct = pct(min_t), pct(max_t), pct(avg_t)
    hue = max(10, min(215, round(215 - (avg_t - 17.3) / (29.1 - 17.3) * 205)))
    rain_pct = max(4, min(100, round(rain / 300 * 100)))
    dot_count = min(5, round(typhoon / 2.4 * 5))
    typhoon_dots = "".join(
        '<span class="dash-typhoon-dot{on}" style="transition-delay:{delay}ms"></span>'.format(
            on=" is-on" if i < dot_count else "", delay=i * 80,
        )
        for i in range(5)
    )

    day_band = ""
    if sr_min is not None and ss_min is not None:
        day_band = (
            '<div class="dash-day-track">'
            '<div class="dash-day-fill" data-reveal style="left:{l:.2f}%;width:{w:.2f}%"></div>'
            '</div>'
            '<strong>{sunrise} 日出 · {sunset} 日落</strong>'
        ).format(l=sr_min / 1440 * 100, w=(ss_min - sr_min) / 1440 * 100, sunrise=html.escape(sunrise), sunset=html.escape(sunset))

    return (
        '<div class="month-dash" data-month-dash style="--month-hue:{hue}">'
        '  <div class="dash-block dash-temp">'
        '    <span class="dash-label">氣溫（氣象庁平年值）</span>'
        '    <div class="dash-temp-track">'
        '      <div class="dash-temp-fill" data-reveal style="left:{min_pct}%;width:{range_pct}%"></div>'
        '      <div class="dash-temp-avg" style="left:{avg_pct}%">{avg_t:.1f}°C</div>'
        '    </div>'
        '    <div class="dash-temp-labels"><span>最低 {min_t:.1f}°C</span><span>最高 {max_t:.1f}°C</span></div>'
        '  </div>'
        '  <div class="dash-row">'
        '    <div class="dash-block dash-card">'
        '      <span class="dash-label">月降雨量</span>'
        '      <div class="dash-bar"><div class="dash-bar-fill" data-reveal style="width:{rain_pct}%"></div></div>'
        '      <strong>{rain:.0f} mm</strong>'
        '    </div>'
        '    <div class="dash-block dash-card">'
        '      <span class="dash-label">颱風接近平年值</span>'
        '      <div class="dash-typhoon">{typhoon_dots}</div>'
        '      <strong>平均 {typhoon:.1f} 個</strong>'
        '    </div>'
        '    <div class="dash-block dash-card dash-card-wide">'
        '      <span class="dash-label">日出・日落</span>'
        '      {day_band}'
        '    </div>'
        '  </div>'
        '</div>'
    ).format(
        hue=hue, min_pct=min_pct, range_pct=round(max_pct - min_pct, 1), avg_pct=avg_pct,
        avg_t=avg_t, min_t=min_t, max_t=max_t, rain_pct=rain_pct, rain=rain,
        typhoon_dots=typhoon_dots, typhoon=typhoon, day_band=day_band,
    )


def month_nav_html(months, current_n):
    by_n = {m["month"]: m for m in months}
    prev_n = 12 if current_n == 1 else current_n - 1
    next_n = 1 if current_n == 12 else current_n + 1
    prev_m, next_m = by_n.get(prev_n), by_n.get(next_n)
    if not prev_m or not next_m:
        return ""
    return (
        '  <nav class="month-nav">\n'
        '    <a class="month-nav-link prev" href="../month-{prev_n}/"><span>← 上個月</span><strong>{prev_title}</strong></a>\n'
        '    <a class="month-nav-link next" href="../month-{next_n}/"><span>下個月 →</span><strong>{next_title}</strong></a>\n'
        '  </nav>\n'
    ).format(
        prev_n=prev_n, next_n=next_n,
        prev_title=html.escape(str(prev_m.get("title", ""))),
        next_title=html.escape(str(next_m.get("title", ""))),
    )


def build_month_pages(months):
    """月份速覽頁：/guide/month-<n>/。回傳產生的完整網址清單。"""
    urls = []
    for month in months:
        n = month["month"]
        body_src = month["body"]
        if month.get("full_guide_slug"):
            body_src = body_src.replace("{{FULL_GUIDE_URL}}", "../{}/".format(month["full_guide_slug"]))

        meta_bits = ['<span>{}</span>'.format(html.escape(str(month.get("weather", ""))))]
        if month.get("highlight"):
            meta_bits.append('<span class="tag">{}</span>'.format(html.escape(str(month["highlight"]))))

        main = fill(template("article.html"), {
            "BREADCRUMB": '<a href="../../">首頁</a><span>/</span><a href="../../guide/">沖繩旅遊攻略</a>',
            "ARTICLE_TITLE": html.escape(str(month.get("title", ""))),
            "ARTICLE_SUMMARY": html.escape(str(month.get("blurb", ""))),
            "ARTICLE_META": "".join(meta_bits),
            "COVER": month_dashboard_html(month),
            "BODY": markdown(body_src),
            "IG_SLOT": "",
            "RELATED": month_nav_html(months, n),
        })
        canonical = render_page(
            "guide/month-{}".format(n), main,
            "{}｜OKIPLAYGROUND".format(month.get("title", "")),
            str(month.get("blurb", "")),
            active="guide",
            page_script='<script src="../../assets/months.js"></script>',
        )
        urls.append(canonical)
    return urls


def month_strip_html(months):
    if not months:
        return ""
    tiles = []
    for month in months:
        n = month["month"]
        tiles.append((
            '<a class="month-tile" href="guide/month-{n}/" data-blurb="{blurb}">'
            '<strong>{label}</strong><span>{season}</span></a>'
        ).format(
            n=n,
            label=MONTH_NAMES[n],
            season=html.escape(str(month.get("season_name", ""))),
            blurb=html.escape(str(month.get("blurb", "")), quote=True),
        ))
    return (
        '  <section class="month-strip" id="months" aria-label="按月份看沖繩">\n'
        '    <div class="shell-narrow">\n'
        '      <div class="month-head">\n'
        '        <span class="eyebrow">Month by Month</span>\n'
        '        <span class="month-note">滑過或點一下，看那個月的沖繩該怎麼玩</span>\n'
        '      </div>\n'
        '      <div class="month-row" id="monthRow">{tiles}</div>\n'
        '      <p class="month-preview" id="monthPreview">選一個月份看看預覽。</p>\n'
        '    </div>\n'
        '  </section>\n'
    ).format(tiles="".join(tiles))


def build_toolkit():
    main = template("toolkit.html")
    rates = read_json("rates.json", {})
    render_page("toolkit", main, "旅行小抄｜OKIPLAYGROUND",
                "沖繩旅行實用資訊：緊急電話、機場與自駕重點、匯率換算與旅遊日語。",
                page_data=json_block("ratesData", rates),
                page_script='<script src="../assets/toolkit.js"></script>')


def write_ig_queue(posts):
    queue = []
    for section, items in posts.items():
        for post in items:
            ig = post.get("ig") or {}
            if not isinstance(ig, dict) or not ig.get("slides"):
                continue
            queue.append({
                "section": section,
                "slug": post["slug"],
                "title": post.get("title", ""),
                "url": SITE_URL + post_href(post),
                "cover": ig.get("cover") or post.get("title", ""),
                "slides": ig.get("slides") or [],
                "caption": ig.get("caption", ""),
                "hashtags": ig.get("hashtags") or [],
            })
    (DOCS / "ig-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return queue


def write_sitemap(urls):
    entries = "".join("  <url><loc>{}</loc></url>\n".format(html.escape(url, quote=True)) for url in urls)
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{}</urlset>\n'.format(entries),
        encoding="utf-8")
    (DOCS / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: {}sitemap.xml\n".format(SITE_URL), encoding="utf-8")


def copy_assets():
    target = DOCS / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for path in ASSETS.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
    covers = CONTENT / "covers"
    if covers.exists():
        shutil.copytree(covers, target / "covers", dirs_exist_ok=True)


def read_json(name, fallback):
    path = DOCS / name
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        warn("{} 讀不起來（{}），改用上一版行為".format(name, error))
        return fallback


def build_site(events=None, weather=None, updated=None):
    REPORT["generated"] = updated or datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    REPORT["pages"] = 0
    REPORT["skipped"] = []
    REPORT["warnings"] = []

    events = events if events is not None else read_json("events.json", [])
    weather = weather if weather is not None else read_json("weather.json", [])
    news = read_json("news.json", [])
    ocean_conditions = read_json("ocean-conditions.json", {})
    surf_conditions = read_json("surf-conditions.json", {})

    posts = load_content()
    goods_items = load_goods_items()
    months = load_months()
    copy_assets()

    urls = [SITE_URL]
    event_urls = build_event_pages(events)  # 要先跑，才能讓 home/events 拿到 _detail_slug
    month_urls = build_month_pages(months)  # 要先跑，才能讓首頁的月份磚連得到頁面
    build_home(posts, events, weather, news, months)
    build_events(events, len(events))
    build_news(news)
    build_toolkit()
    urls += [SITE_URL + "events/", SITE_URL + "news/", SITE_URL + "toolkit/"] + event_urls + month_urls

    for key in SECTIONS:
        extra_block = ""
        show_filters = True
        cards_heading = ""
        if key == "ocean":
            dive_spots = (ocean_conditions or {}).get("spots") or []
            surf_spots = (surf_conditions or {}).get("spots") or []
            extra_block = ocean_conditions_html(
                ocean_conditions,
                note_label="潛水要注意",
                heading="{}個熱門岸潛點，即時海況。".format(cn_num(len(dive_spots))),
                eyebrow="Live Conditions",
                section_id="live-conditions",
                section_class="ocean-conditions",
            ) + ocean_conditions_html(
                surf_conditions,
                note_label="滑浪要注意",
                heading="{}個滑浪點，即時浪況。".format(cn_num(len(surf_spots))),
                eyebrow="Live Surf Conditions",
                section_id="live-surf-conditions",
                section_class="ocean-conditions surf-conditions",
            )
        if key == "goods":
            extra_block = goods_items_html(goods_items)
            show_filters = False
            cards_heading = "深度好物指南"
        if key == "okinawa":
            extra_block = region_intro_html()
        build_section(key, posts.get(key) or [], extra_block=extra_block,
                       show_filters=show_filters, cards_heading=cards_heading)
        urls.append(SITE_URL + key + "/")
        for post in posts.get(key) or []:
            urls.append(build_article(post, posts.get(key) or []))

    queue = write_ig_queue(posts)
    write_sitemap(urls)
    (DOCS / "build-report.json").write_text(
        json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")

    print("📄 產生 {} 頁・文章 {} 篇・IG 待產 {} 則".format(
        REPORT["pages"], sum(len(items) for items in posts.values()), len(queue)))
    if REPORT["skipped"]:
        print("⏭️  跳過 {} 筆（詳見 docs/build-report.json）".format(len(REPORT["skipped"])))
    return REPORT


if __name__ == "__main__":
    build_site()
