#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filter the WordPress-vs-our-CMS gap list down to what matters for an e-commerce site.

Reads docs/wordpress-cms-gaps-2026-10-01.md and writes
docs/store-relevant-cms-gaps-2026-10-01.md with every item classified:
  P0  customer / revenue / legal / security
  P1  daily admin operations (they block the work)
  P2  SEO / conversion / growth
  --  not relevant to a store (WordPress-CMS-only or out of scope)

Classification is by the line number of each item in the source file, so counts
are measured, never estimated. Any line not classified aborts the run.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = os.path.join("docs", "wordpress-cms-gaps-2026-10-01.md")
DST = os.path.join("docs", "store-relevant-cms-gaps-2026-10-01.md")

# --- not relevant to an e-commerce site -------------------------------------
IRRELEVANT = {
    # block editor / Gutenberg: a store needs a decent rich text, not 115 blocks
    8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24, 26, 27,
    # site editor / theme system: the storefront design is not a WP theme
    30, 31, 32, 33, 34, 35, 36, 37, 38, 40, 41, 42, 44,
    # blog-only WordPress features
    59, 62, 63, 64, 65, 70, 71, 72,
    # taxonomy/meta admin surface a store has no use for
    88, 96, 97, 98, 100, 101,
    # media features aimed at media libraries, not shops
    137, 138, 140, 147, 148, 149, 150, 164,
    # blog-profile and admin cosmetics
    172, 180, 185,
    # comment features a store does not need on product/blog pages
    114, 115, 117, 124, 130,
    # dashboard chrome that is a WordPress admin convention
    201, 204,
    208, 217,
    224, 225, 226, 229, 233, 234, 228, 232,
    # REST/feed plumbing that only matters for WP compatibility
    239, 240, 241, 242, 243, 244, 245, 248, 249, 250, 251, 252, 253, 254,
    # multisite and the WP 7.x platform APIs
    262, 263, 264, 265, 266, 267, 268, 269,
    278, 281, 290,
    294, 296, 297,
    303,
    # leftovers a store has no use for
    39, 43,
}

P0 = {
    52,                        # admin lists capped at 50 rows, no pager
    60,                        # private post body served to anyone with the URL
    111, 113,                  # storefront comment pagination / no comments on CMS pages
    135, 139, 144, 156, 157,   # media: no trash, no srcset, no drag&drop, no bulk delete, no usage warning
    168,                       # no UI to assign a role: a store manager cannot be appointed
    170, 171, 177, 178, 189,   # admin password reset, delete-with-reassign, welcome + password emails, last-admin lockout
    197,                       # custom_html widget renders as plain text
    207, 209, 212, 218,        # front page picker, site name/admin email, search-engine toggle, store identity never read
    227,                       # no maintenance mode: downtime means lost sales
    255, 257,                  # sitemap misses CPT/author/date; no image sitemap
    274, 277, 279, 280,        # GDPR: purge never scheduled, guest comments not erased, IPs kept forever, no privacy notice in forms
    301,                       # every transactional email hardcodes "فروشگاه اینترنتی"
}

P1 = {
    21, 22, 25,                       # editor toolbar, insert media, more shortcodes
    47, 48, 49, 50, 51, 53, 54, 55, 56, 57, 58, 61, 67, 68, 69,
    75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    89, 90, 91, 92, 93, 94, 95,
    104, 105, 106, 107, 108, 109, 110, 116, 118, 119, 120, 121, 122,
    125, 126, 127, 128, 129, 132,
    136, 141, 142, 143, 145, 146, 151, 155, 159, 160, 161, 163, 165,
    169, 173, 174, 175, 176, 179, 181, 182, 183, 184, 186, 187, 188, 190, 191, 192,
    131,
    195, 196, 198, 199, 200,
    213, 214, 215, 219,
    222, 230, 231, 235, 236,
    256, 258,
    272, 273, 275, 276,
    285, 288, 291,
}

P2 = {
    # growth / polish: nothing breaks without these, they only make it faster or nicer
    66,    # auto paragraph + texturize on render
    99,    # post meta only in the edit dialog
    112,   # commenter website field
    123,   # private team note on a post
    152,   # restore the original after an image edit
    153,   # image edit undo/redo
    154,   # edit the image from inside the content editor
    158,   # alt-text warning badge in the media list
    162,   # configurable upload size cap
    202,   # front-end admin bar
    203,   # dismissible admin notices
    210,   # date/time format and timezone settings
    211,   # default category and default post format
    216,   # content locales editor
    223,   # exporter filters
    246,   # admin sees another user's application passwords
    247,   # HTTP Basic for application passwords
    259,   # oEmbed cache and wider provider list
    282,   # client/server sanitizer allowlist sync
    286,   # scheduled site-health runs
    287,   # site-health Info tab detail
    289,   # UI string catalogue admin page
    295,   # wider plugin hook coverage
    300,   # editable email templates
    302,   # email attachments
}

LABELS = [
    ("P0", P0, "P0 — مشتری، درآمد، قانون یا امنیت",
     "کاری که همین الان روی فروش، اعتماد مشتری یا ریسک حقوقی اثر می‌گذارد."),
    ("P1", P1, "P1 — کار روزمره‌ی ادمین را متوقف می‌کند",
     "بدون این‌ها ادمین نمی‌تواند محتوا، کامنت، رسانه یا کاربر را واقعاً مدیریت کند."),
    ("P2", P2, "P2 — رشد، بهینه‌سازی و راحتی",
     "کار را نمی‌ندازد؛ فقط کیفیت، سرعت یا راحتی را بهتر می‌کند."),
]

PRIORITY_OF = {}
for tag, _set, _t, _s in LABELS:
    for n in _set:
        PRIORITY_OF[n] = tag


def main():
    if not os.path.isfile(SRC):
        print("source not found: %s" % SRC)
        return 1
    lines = open(SRC, encoding="utf-8").read().split("\n")

    items = []          # (lineno, domain, text)
    domain = ""
    for i, raw in enumerate(lines, start=1):
        if raw.startswith("## "):
            domain = raw[3:].strip()
        elif raw.startswith("- [نداریم]") or raw.startswith("- [ناقص]"):
            items.append((i, domain, raw))

    p2 = set(P2)
    unclassified = {ln for ln, _, _ in items} - IRRELEVANT - set(PRIORITY_OF) - p2
    if unclassified:
        print('ERROR: unclassified item lines: %s' % sorted(unclassified))
        return 4

    unknown = [n for n in (IRRELEVANT | set(PRIORITY_OF) | p2) if n not in {i for i, _, _ in items}]
    if unknown:
        print("ERROR: classified line numbers that are not items: %s" % sorted(unknown))
        return 2

    counts = {
        "P0": len(P0), "P1": len(P1), "P2": len(p2), "--": len(IRRELEVANT),
    }
    total = sum(counts.values())
    if total != len(items):
        print("ERROR: %d classified vs %d items" % (total, len(items)))
        return 3

    by = {t: [] for t in ("P0", "P1", "P2", "--")}
    for ln, dom, text in items:
        tag = ("--" if ln in IRRELEVANT else "P0" if ln in P0
               else "P1" if ln in P1 else "P2" if ln in P2 else "P2")
        by[tag].append((ln, dom, text))

    out = []
    w = out.append
    w("# کمبودهای CMS که برای یک فروشگاه اینترنتی مهم‌اند")
    w("")
    w("فیلترشده از `docs/wordpress-cms-gaps-2026-10-01.md` (%d آیتم). معیار: آیا این قابلیت روی "
      "فروش، تجربه‌ی مشتری، کار روزمره‌ی ادمین، SEO یا ریسک حقوقی فروشگاه اثر می‌گذارد." % len(items))
    w("")
    w("| اولویت | تعداد | معنی |")
    w("| --- | --- | --- |")
    w("| **P0** | %d | مشتری / درآمد / قانون / امنیت |" % counts["P0"])
    w("| **P1** | %d | کار روزمره‌ی ادمین را متوقف می‌کند |" % counts["P1"])
    w("| **P2** | %d | SEO، تبدیل کاربر، رشد |" % counts["P2"])
    w("| **بی‌ربط** | %d | مخصوص CMS وردپرس یا خارج از دامنه — پیاده‌سازی نشود |" % counts["--"])
    w("")
    w("**جمع: %d آیتم — %d مرتبط، %d بی‌ربط.**" % (len(items), counts["P0"] + counts["P1"] + counts["P2"], counts["--"]))
    w("")
    for tag, _s, title, sub in LABELS:
        w("## %s (%d)" % (title, len(by[tag])))
        w("")
        w(sub)
        w("")
        last = None
        for ln, dom, text in by[tag]:
            if dom != last:
                w("### %s" % dom)
                last = dom
            w(text)
        w("")
    w("---")
    w("")
    w("## بی‌ربط به فروشگاه (%d) — چرا کنار گذاشته شدند" % len(by["--"]))
    w("")
    w("گروه‌های بزرگ این‌ها هستند:")
    w("")
    w("- **ادیتور بلاکی و سایت‌ادیتر** (%d مورد): ساخت گutenberg با ۱۱۵ بلاک، Theme JSON، "
      "قالب‌های بلاکی و child theme. فروشگاه ما یک ادیتور متنی قابل قبول دارد؛ "
      "ساخت سیستم بلاک ماه‌ها کار می‌برد و مشتریِ فروشگاه آن را نمی‌بیند."
      % sum(1 for ln, _, _ in items if ln in IRRELEVANT and ln <= 44))
    w("- **چندسایته و APIهای پلتفرمی وردپرس ۷** (%d مورد): Multisite، Abilities API، AI Client، "
      "Speculation Rules، View Transitions، Interactivity API، HTML API. یک فروشگاه تک‌سایتی به اینها نیاز ندارد."
      % sum(1 for ln, _, _ in items if 262 <= ln <= 269))
    w("- **پلاگین و به‌روزرسانی هسته** (%d مورد): نصب/به‌روزرسانی پلاگین و کور وردپرس، بسته‌ی زبان، "
      "رجیستری افزونه. ما کد خودمان را دیپلوی می‌کنیم، نه وردپرس را."
      % sum(1 for ln, _, _ in items if ln in (224, 225, 226, 294, 296, 297)))
    w("- **سازگاری با ابزارهای وردپرسی** (%d مورد): XML-RPC، RSD، pingback/trackback، "
      "Post by Email، Press This، ایندکس REST، پارامترهای `_fields`/`_embed`، فیدهای RDF/Atom/۰.۹۲."
      % sum(1 for ln, _, _ in items if ln in (70, 71, 72, 239, 240, 241, 242, 243, 244, 248, 249, 250, 251, 252, 253, 254)))
    w("- **قابلیت‌های کتابخانه‌ی رسانه** (%d مورد): صفحه‌ی پیوست، تاکسونومی رسانه، پوشه‌ی سال/ماه، "
      "پلی‌لیست صوتی، متادیتای ID3، Openverse، آپلود zip/docx."
      % sum(1 for ln, _, _ in items if ln in (137, 138, 140, 147, 148, 149, 150)))
    w("")
    w("موارد بی‌ربط دیگر تک‌تک با همان فرمت در انتهای همین سند آمده‌اند؛ این پنج گروه فقط "
      "بزرگ‌ترین خوشه‌ها را نشان می‌دهند، نه همه‌ی %d مورد را." % len(by["--"]))
    w("")
    w("### همه‌ی %d مورد بی‌ربط، به ترتیب سند مبدأ" % len(by["--"]))
    w("")
    for ln, dom, text in by["--"]:
        w(text)
    w("")

    with open(DST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    print("items read      : %d" % len(items))
    print("P0 / P1 / P2 / -: %d / %d / %d / %d" % (counts["P0"], counts["P1"], counts["P2"], counts["--"]))
    print("relevant        : %d" % (counts["P0"] + counts["P1"] + counts["P2"]))
    print("written         : %s" % DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())