#!/usr/bin/env python3
"""Guards the on-page SEO invariants this site depends on for indexing.

Run: python3 scripts/seo-check.py
"""
import glob
import html
import json
import re
import sys
import xml.etree.ElementTree as ET

ORIGIN = "https://shop.autobrainservice.app"
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


# --- sitemap: canonical URLs only (sitemaps.org forbids fragment identifiers) ---
tree = ET.parse("sitemap.xml")
locs = [e.text for e in tree.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
check(bool(locs), "sitemap.xml has no <loc> entries")
for loc in locs:
    check("#" not in loc, f"sitemap.xml has fragment URL (not indexable): {loc}")
    check(loc.startswith(ORIGIN), f"sitemap.xml loc is off-origin: {loc}")

# --- every local page must be discoverable from the sitemap ---
for page in sorted(glob.glob("*.html")):
    url = f"{ORIGIN}/" if page == "index.html" else f"{ORIGIN}/{page}"
    check(url in locs, f"{page} is not listed in sitemap.xml (expected {url})")

for page in sorted(glob.glob("*.html")):
    src = open(page, encoding="utf-8").read()

    def meta(attr, value):
        m = re.search(rf'<meta\s+{attr}="{value}"\s+content="(.*?)"', src, re.I | re.S)
        return html.unescape(m.group(1)) if m else None

    title = re.search(r"<title[^>]*>(.*?)</title>", src, re.I | re.S)
    title = html.unescape(title.group(1)).strip() if title else ""
    desc = meta("name", "description")

    check(title, f"{page}: missing <title>")
    check(len(title) <= 60, f"{page}: <title> is {len(title)} chars, Google truncates past ~60")
    check(desc, f"{page}: missing meta description")
    if desc is not None:
        check(
            70 <= len(desc) <= 160,
            f"{page}: meta description is {len(desc)} chars, must be 70-160 to fill the SERP snippet",
        )
    check(
        re.search(r'<link\s+rel="canonical"', src, re.I),
        f"{page}: missing rel=canonical",
    )
    check(
        '<meta property="og:title"' in src and '<meta property="og:description"' in src,
        f"{page}: missing Open Graph title/description",
    )
    check(
        len(re.findall(r"<h1[^>]*>", src, re.I)) == 1,
        f"{page}: needs exactly one <h1>",
    )

    hreflangs = re.findall(r'<link\s+rel="alternate"\s+hreflang="([^"]+)"', src, re.I)
    dupes = {v for v in hreflangs if hreflangs.count(v) > 1}
    check(not dupes, f"{page}: duplicate hreflang values {sorted(dupes)}")
    check(
        all(src.find('<link rel="alternate"') > src.index("</head>") for _ in [0])
        or src.rindex('<link rel="alternate"') < src.index("</head>"),
        f"{page}: hreflang link outside <head>",
    )

    for block in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', src, re.I | re.S
    ):
        try:
            json.loads(block)
        except json.JSONDecodeError as exc:
            errors.append(f"{page}: invalid JSON-LD ({exc})")

if errors:
    print("SEO check FAILED:")
    print("\n".join(f"  - {e}" for e in errors))
    sys.exit(1)
print(f"SEO check passed ({len(glob.glob('*.html'))} pages, {len(locs)} sitemap URLs).")