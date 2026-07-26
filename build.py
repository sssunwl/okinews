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
SECTIONS = {
    "guide": {
        "title": "沖繩旅遊攻略",
        "eyebrow": "Travel Guide",
        "lead": "依主題、旅行方式、月份與地區整理。先挑一個最接近你這趟的方式，再往下看細節。",
        "axes": [
            ("主題", ["食", "玩", "住", "買", "拍"]),
            ("旅行方式", ["一天遊", "自駕", "不自駕", "親子", "情侶", "一人", "三代同行", "長住"]),
            ("地區", ["那霸", "南部", "中部", "北部", "離島"]),
            ("月份", ["1月", "2月", "3月", "4月", "5月", "6月",
                     "7月", "8月", "9月", "10月", "11月", "12月"]),
        ],
    },
    "okinawa": {
        "title": "認識沖繩",
        "eyebrow": "Know Okinawa",
        "lead": "琉球王國、傳統祭典、信仰與禮儀。知道背景之後，同樣的風景會看得比較久。",
        "axes": [("主題", ["歷史", "傳統", "信仰", "language", "禮儀"])],
    },
    "goods": {
        "title": "沖繩特色好物",
        "eyebrow": "Okinawa Goods",
        "lead": "工藝、超市便利店、100・300 円店與藥妝伴手禮。買得到、帶得回去、回家還會用的那些。",
        "axes": [("類型", ["工藝", "超市", "便利店", "100円", "藥妝", "食品"])],
    },
    "ocean": {
        "title": "玩水・潛水",
        "eyebrow": "Ocean Time",
        "lead": "浮潛點、潛水店、季節與安全提醒。下水前先看一次，比到現場再問快。",
        "axes": [
            ("方式", ["浮潛", "潛水", "海灘", "SUP", "獨木舟"]),
            ("地區", ["那霸", "南部", "中部", "北部", "離島"]),
        ],
    },
}

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


def build_home(posts, events, weather, news):
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
            '  <section class="know-banner">\n'
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
            '  <section class="know-banner">\n'
            '    <div class="shell know-card">\n'
            '      <div><div class="eyebrow">Know Okinawa</div>'
            '<h2>認識沖繩</h2><p>琉球王國、傳統祭典與信仰。內容整理中。</p>'
            '<a class="know-link" href="okinawa/">看這一區 →</a></div>\n'
            '    </div>\n'
            '  </section>\n'
        )

    main = fill(template("home.html"), {
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


def build_section(key, posts):
    meta = SECTIONS[key]
    used_tags = set()
    for post in posts:
        for tag in (post.get("tags") or []):
            used_tags.add(str(tag))

    rows = []
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
        filters = ('      <div class="filter-block" id="postFilters">\n'
                   '        <div class="filter-row"><span class="filter-label">全部</span>'
                   '<div class="filter-chips"><button class="tag-chip active" type="button" data-tag="">看全部</button></div></div>\n'
                   + "\n".join(rows) + "\n      </div>")

    cards = "\n".join("        " + post_card(post, "../") for post in posts) or \
        '        <div class="empty-state"><strong>內容整理中</strong>這一區的文章正在寫，很快會放上來。</div>'

    main = fill(template("section.html"), {
        "SECTION_TITLE": html.escape(meta["title"]),
        "SECTION_EYEBROW": meta["eyebrow"],
        "SECTION_LEAD": html.escape(meta["lead"]),
        "FILTERS": filters,
        "CARDS": cards,
    })
    render_page(
        key, main,
        "{}｜OKIPLAYGROUND".format(meta["title"]),
        meta["lead"],
        active=key,
        page_script='<script src="../assets/section.js"></script>' if filters else "",
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
    )


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
            entries = "".join(
                '<article class="news-item">'
                '<div class="news-meta"><span class="news-cat">{cat}</span><span>{source}</span></div>'
                '<h3>{title}</h3><p>{summary}</p>'
                '<a href="{url}" target="_blank" rel="noopener">看原文 ↗</a>'
                '</article>'.format(
                    cat=html.escape(str(item.get("category", "沖繩"))),
                    source=html.escape(str(item.get("source", ""))),
                    title=html.escape(str(item.get("title", ""))),
                    summary=html.escape(str(item.get("summary", ""))),
                    url=html.escape(str(item.get("url", "")), quote=True),
                )
                for item in groups[date]
            )
            blocks.append('      <section class="news-day"><h2>{}</h2><div class="news-list">{}</div></section>'
                          .format(html.escape(date), entries))
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


def build_toolkit():
    main = template("toolkit.html")
    render_page("toolkit", main, "旅行小抄｜OKIPLAYGROUND",
                "沖繩旅行實用資訊：緊急電話、機場與自駕重點、匯率換算與旅遊日語。",
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

    posts = load_content()
    copy_assets()

    urls = [SITE_URL]
    event_urls = build_event_pages(events)  # 要先跑，才能讓 home/events 拿到 _detail_slug
    build_home(posts, events, weather, news)
    build_events(events, len(events))
    build_news(news)
    build_toolkit()
    urls += [SITE_URL + "events/", SITE_URL + "news/", SITE_URL + "toolkit/"] + event_urls

    for key in SECTIONS:
        build_section(key, posts.get(key) or [])
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
