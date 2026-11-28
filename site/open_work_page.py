#!/usr/bin/env python3
"""Render docs/open-work.md to <out>/open-work/index.html (stdlib only; used by site/build.sh).

Handles what that file uses: #-headings, paragraphs, '-' lists, '>' quotes, `code`, **bold**, [links](url).
Relative links are pointed at the file on GitHub. Reuses the landing page's head assets and theme toggle.
"""
import html, re, sys
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[2])
md = (root / "docs/open-work.md").read_text()
landing = (root / "site/static/index.html").read_text()
GH = "https://github.com/dogluk/air-apocalypse/blob/main/"

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    def link(m):
        u = m.group(2)
        if not re.match(r"^(https?:|#|/)", u):
            u = GH + re.sub(r"^(\.\./)+", "", u)
        return f'<a href="{u}">{m.group(1)}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)

def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")

body, para, items, quote = [], [], [], []
def flush():
    global para, items, quote
    if para: body.append("<p>" + inline(" ".join(para)) + "</p>")
    if items: body.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
    if quote: body.append("<blockquote><p>" + inline(" ".join(quote)) + "</p></blockquote>")
    para, items, quote = [], [], []
title = "Open work"
for line in md.splitlines():
    m = re.match(r"^(#{1,4}) (.*)", line)
    if m:
        flush()
        n, t = len(m.group(1)), m.group(2)
        if n == 1: title = t; continue
        tag = f"h{n}"
        body.append(f'<{tag} id="{slug(t.split(":")[0]) if t.startswith("OW-") else slug(t)}">{inline(t)}</{tag}>')
    elif line.startswith("- "):
        if para or quote: flush()
        items.append(line[2:])
    elif line.startswith("> "):
        if para or items: flush()
        quote.append(line[2:])
    elif not line.strip():
        flush()
    else:
        if items: items[-1] += " " + line.strip()
        else: para.append(line.strip())
flush()

head = re.search(r"<head>.*?</head>", landing, re.S).group(0)
head = re.sub(r"<title>.*?</title>", "", head)
head = re.sub(r'<link rel="canonical"[^>]*>|<meta property="og:(url|title|description)"[^>]*>|<meta name="description"[^>]*>|<meta property="(twitter:)?title"[^>]*>|<script type="application/ld\+json">.*?</script>', "", head, flags=re.S)
head = head.replace("<head>", f'<head>\n<title>Open work | airhealth</title>\n<link rel="canonical" href="https://airhealth.dev/open-work/" />\n'
    '<meta name="description" content="Open questions in the air-apocalypse model, each with what to read, where it lands and the check that proves it." />\n'
    '<meta property="og:url" content="https://airhealth.dev/open-work/" /><meta property="og:title" content="Open work | airhealth" />\n'
    '<style>.post h3{margin-top:2.2rem}.post ul{padding-left:1.2rem}.post li{margin:.25rem 0;overflow-wrap:anywhere}.post code{overflow-wrap:anywhere;white-space:normal}</style>', 1)
header = re.search(r'<header class="site-header".*?</header>', landing, re.S).group(0)
footer = re.search(r'<footer class="site-footer".*?</footer>', landing, re.S).group(0)
page = (f'<!DOCTYPE html>\n<html lang="en">{head}<body>{header}\n<main class="page-content" aria-label="Content"><div class="wrapper">'
        f'<article class="post"><header class="post-header"><h1 class="post-title">{html.escape(title)}</h1></header>'
        f'<div class="post-content">{"".join(body)}</div></article></div></main>{footer}</body></html>\n')
d = out / "open-work"; d.mkdir(parents=True, exist_ok=True)
(d / "index.html").write_text(page)
