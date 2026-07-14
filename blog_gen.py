#!/usr/bin/env python3
"""
Static bilingual blog generator for peterluo.homes/blog.

Reads posts (same shape as the composer's queue.json entries) and writes plain
HTML into a GitHub Pages repo under /blog/en and /blog/zh. Media stays on R2 —
only text/HTML is written, so the repo stays tiny.

Publish rule (hybrid): a post is rendered into whichever language sections it has
a non-empty caption for. Posts with both are cross-linked with <link hreflang>.

Reusable from post.py:  build_blog(posts, out_root)   # out_root = repo checkout dir
"""
import os, re, html, datetime as dt

SITE = "https://peterluo.homes"
BRAND = "Peter Luo Homes"
UI = {
    "en": {"tagline": "Richmond Hill & York Region real estate",
           "all": "All posts", "home": "Home", "other": "中文", "read": "Read more",
           "empty": "No posts yet."},
    "zh": {"tagline": "列治文山及约克区房地产",
           "all": "全部文章", "home": "首页", "other": "English", "read": "阅读全文",
           "empty": "暂无文章。"},
}

def slugify(s):
    s = (s or "").strip().lower()
    # keep unicode letters/numbers, turn the rest into hyphens
    s = re.sub(r"[^\w一-鿿]+", "-", s, flags=re.UNICODE).strip("-")
    return s or "post"

def cap(post, lang):
    return (post.get("captions", {}) or {}).get(lang, "") or ""

def link_of(post, lang):
    return (post.get("commentLinks", {}) or {}).get(lang, "") or ""

def post_date(post):
    raw = post.get("scheduledFor") or post.get("date")
    try:
        d = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        d = dt.datetime.now(dt.timezone.utc)
    return d

def fmt_date(d, lang):
    if lang == "zh":
        return f"{d.year}年{d.month}月{d.day}日"
    return d.strftime("%B %-d, %Y")

def slug_for(post):
    d = post_date(post)
    return f"{d:%Y-%m-%d}-{slugify(post.get('title',''))}"

def media_html(post):
    out = []
    for m in post.get("media", []) or []:
        u = m.get("url")
        if not u:
            continue
        if m.get("type") == "video":
            out.append(f'<video controls playsinline src="{html.escape(u)}"></video>')
        else:
            out.append(f'<img loading="lazy" src="{html.escape(u)}" alt="">')
    return "\n".join(out)

PAGE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · {brand}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
{hreflang}
<link rel="stylesheet" href="/blog/assets/style.css">
</head>
<body>
<header class="site">
  <a class="brand" href="/blog/{lang}/">{brand}</a>
  <nav><a href="/blog/{lang}/">{all}</a>{lang_toggle}</nav>
</header>
<main class="post">
  <p class="crumbs">{crumbs}</p>
  <h1>{title}</h1>
  <p class="meta">{date}{addr}</p>
  <div class="media">{media}</div>
  <div class="body">{body}</div>
  {cta}
</main>
<footer class="site"><span>© {year} {brand}</span></footer>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand} — {all}</title>
<meta name="description" content="{tagline}">
<link rel="stylesheet" href="/blog/assets/style.css">
</head>
<body>
<header class="site">
  <a class="brand" href="/blog/{lang}/">{brand}</a>
  <nav><a class="on" href="/blog/{lang}/">{all}</a><a href="/blog/{other_lang}/">{other}</a></nav>
</header>
<main class="index">
  <p class="tagline">{tagline}</p>
  <ul class="cards">{cards}</ul>
</main>
<footer class="site"><span>© {year} {brand}</span></footer>
</body>
</html>
"""

def render_page(post, lang, other_url):
    d = post_date(post)
    body = cap(post, lang).strip()
    body_html = "".join(f"<p>{html.escape(line)}</p>" for line in body.split("\n") if line.strip())
    link = link_of(post, lang)
    cta = f'<p class="cta"><a href="{html.escape(link)}">{html.escape(link)}</a></p>' if link else ""
    hreflang = ""
    lang_toggle = ""
    if other_url:
        ol = "zh" if lang == "en" else "en"
        hreflang = (f'<link rel="alternate" hreflang="{ol}" href="{other_url}">\n'
                    f'<link rel="alternate" hreflang="{lang}" href="{SITE}/blog/{lang}/{slug_for(post)}.html">')
        lang_toggle = f' · <a href="{other_url}">{UI[lang]["other"]}</a>'
    addr = f' · {html.escape(post.get("propAddr",""))}' if post.get("propAddr") else ""
    crumbs = html.escape(post.get("metaBreadcrumb","") or UI[lang]["all"])
    title = html.escape(post.get("title","Untitled"))
    return PAGE.format(
        lang=lang, brand=BRAND, all=UI[lang]["all"], title=title,
        desc=html.escape(body[:150]), canonical=f"{SITE}/blog/{lang}/{slug_for(post)}.html",
        hreflang=hreflang, lang_toggle=lang_toggle, crumbs=crumbs,
        date=fmt_date(d, lang), addr=addr, media=media_html(post),
        body=body_html or f"<p>{title}</p>", cta=cta, year=dt.datetime.now().year)

def render_index(posts, lang):
    rows = sorted([p for p in posts if cap(p, lang).strip()], key=post_date, reverse=True)
    if rows:
        cards = ""
        for p in rows:
            d = post_date(p)
            first_img = next((m.get("url") for m in (p.get("media") or []) if m.get("type") != "video" and m.get("url")), "")
            thumb = f'<img loading="lazy" src="{html.escape(first_img)}" alt="">' if first_img else ""
            excerpt = html.escape(cap(p, lang).strip().split("\n")[0][:120])
            cards += (f'<li class="card"><a href="/blog/{lang}/{slug_for(p)}.html">'
                      f'<div class="thumb">{thumb}</div>'
                      f'<div class="c"><span class="d">{fmt_date(d, lang)}</span>'
                      f'<h2>{html.escape(p.get("title","Untitled"))}</h2>'
                      f'<p>{excerpt}</p><span class="more">{UI[lang]["read"]} →</span></div></a></li>')
    else:
        cards = f'<li class="empty">{UI[lang]["empty"]}</li>'
    return INDEX.format(lang=lang, other_lang=("zh" if lang=="en" else "en"),
        brand=BRAND, all=UI[lang]["all"], other=UI[lang]["other"],
        tagline=UI[lang]["tagline"], cards=cards, year=dt.datetime.now().year)

CSS = """:root{--navy:#16243f;--gold:#bb9b46;--cream:#f6f2e8;--ink:#1d2433;--muted:#6b7385;--line:#e3dccb}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,'Noto Sans SC',sans-serif;color:var(--ink);background:#fbf9f3;line-height:1.6}
header.site,footer.site{background:var(--navy);color:var(--cream);padding:16px 22px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
header.site{border-bottom:3px solid var(--gold)}
.brand{font-weight:700;font-size:18px;color:var(--cream);text-decoration:none;letter-spacing:.02em}
header.site nav{margin-left:auto;display:flex;gap:14px}
header.site nav a{color:#cdd5e4;text-decoration:none;font-size:14px}header.site nav a.on,header.site nav a:hover{color:var(--gold)}
main{max-width:820px;margin:0 auto;padding:28px 20px 60px}
.tagline{color:var(--muted);font-size:15px;margin:4px 0 22px}
.cards{list-style:none;padding:0;margin:0;display:grid;gap:18px}
.card a{display:grid;grid-template-columns:150px 1fr;gap:16px;text-decoration:none;color:inherit;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;transition:.15s}
.card a:hover{border-color:var(--gold);box-shadow:0 4px 16px rgba(22,36,63,.08)}
.card .thumb{background:var(--cream)}.card .thumb img{width:100%;height:100%;object-fit:cover;display:block;min-height:110px}
.card .c{padding:14px 16px}.card .d{font-size:12px;color:var(--gold);font-weight:600}
.card h2{font-size:18px;margin:4px 0 6px;color:var(--navy)}.card p{margin:0 0 8px;color:var(--muted);font-size:14px}
.card .more{font-size:13px;color:var(--gold);font-weight:600}
.card .empty,.empty{color:var(--muted);padding:30px 0;list-style:none}
.post .crumbs{font-size:12px;color:var(--gold);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px}
.post h1{font-size:28px;color:var(--navy);margin:0 0 6px;line-height:1.25}
.post .meta{color:var(--muted);font-size:14px;margin:0 0 20px}
.post .media img,.post .media video{width:100%;border-radius:12px;margin:0 0 18px;display:block}
.post .body p{margin:0 0 14px;font-size:17px}
.post .cta{margin-top:20px}.post .cta a{display:inline-block;background:var(--gold);color:var(--navy);font-weight:700;padding:11px 18px;border-radius:9px;text-decoration:none}
@media(max-width:560px){.card a{grid-template-columns:1fr}.card .thumb img{min-height:160px}}
footer.site{border-top:3px solid var(--gold);border-bottom:none;font-size:13px;color:#cdd5e4;justify-content:center}
"""

def build_blog(posts, out_root):
    """Write the whole /blog tree under out_root (a repo checkout)."""
    blog = os.path.join(out_root, "blog")
    os.makedirs(os.path.join(blog, "assets"), exist_ok=True)
    with open(os.path.join(blog, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    # landing redirect -> English index
    with open(os.path.join(blog, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><meta charset="utf-8">'
                '<meta http-equiv="refresh" content="0; url=/blog/en/">'
                '<link rel="canonical" href="/blog/en/">')
    for lang in ("en", "zh"):
        d = os.path.join(blog, lang)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_index(posts, lang))
        for p in posts:
            if not cap(p, lang).strip():
                continue
            other = f"{SITE}/blog/{'zh' if lang=='en' else 'en'}/{slug_for(p)}.html" if cap(p, 'zh' if lang=='en' else 'en').strip() else ""
            with open(os.path.join(d, slug_for(p) + ".html"), "w", encoding="utf-8") as f:
                f.write(render_page(p, lang, other))
    return blog

# ---- demo scaffold when run directly ----
if __name__ == "__main__":
    demo = [
        {"id":"d1","title":"Just Sold — 18 Hayfield Cres","scheduledFor":"2026-07-12T14:00:00Z",
         "propAddr":"18 Hayfield Cres, Richmond Hill","metaBreadcrumb":"Success › Just Sold",
         "captions":{"en":"Sold over asking in 6 days.\nHere's what made the difference: pricing strategy, staging, and a launch that reached the right buyers.",
                     "zh":"六天内高于要价成交。\n关键在于：定价策略、专业布置，以及精准触达买家的上市方案。"},
         "commentLinks":{"en":"https://peterluo.homes/valuation","zh":"https://peterluo.homes/valuation"},
         "media":[{"url":"https://media.peterluo.homes/18-hayfield-cres/sold/front.jpg","type":"image"}]},
        {"id":"d2","title":"July Market Update","scheduledFor":"2026-07-08T13:00:00Z",
         "metaBreadcrumb":"Market › Monthly Update",
         "captions":{"en":"What this month's numbers mean for sellers in York Region.","zh":"本月数据对约克区卖家意味着什么。"},
         "commentLinks":{"en":"","zh":""},
         "media":[{"url":"https://media.peterluo.homes/market/july.jpg","type":"image"}]},
        {"id":"d3","title":"社区亮点：列治文山名校区","scheduledFor":"2026-07-05T15:00:00Z",
         "metaBreadcrumb":"社区 › 学区",
         "captions":{"en":"","zh":"为什么家庭选择这个社区：名校、公园与宁静的街道。"},
         "commentLinks":{"en":"","zh":""},
         "media":[]},
    ]
    root = os.environ.get("BLOG_OUT", ".")
    path = build_blog(demo, root)
    print("wrote blog tree to", path)
