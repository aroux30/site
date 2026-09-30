"""Extract WordPress core's feature inventory from a real source checkout.

Source: github.com/WordPress/WordPress (default branch, wordpress-develop layout
as shipped in the tarball) — read-only, never imported or executed.
"""

import json
import os
import re
import sys

WP = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\ADMINI~1\AppData\Local\Temp\wp-core"
OUT = os.path.join(os.path.dirname(__file__), "wp_inventory.json")


def read(rel):
    p = os.path.join(WP, rel)
    if not os.path.exists(p):
        return ""
    return open(p, encoding="utf-8", errors="ignore").read()


def function_body(rel, name, span=60000):
    s = read(rel)
    i = s.find("function " + name)
    if i < 0:
        return ""
    return s[i : i + span]


def post_types():
    seg = function_body("wp-includes/post.php", "create_initial_post_types", 60000)
    return sorted(set(re.findall(r"register_post_type\(\s*'([a-z_]+)'", seg)))


def taxonomies():
    seg = function_body("wp-includes/taxonomy.php", "create_initial_taxonomies", 60000)
    return sorted(set(re.findall(r"register_taxonomy\(\s*'([a-z_]+)'\s*,", seg)))


def post_statuses():
    """Initial statuses are registered inline in create_initial_post_types()."""
    s = read("wp-includes/post.php")
    return sorted(set(re.findall(r"register_post_status\(\s*'([a-z_-]+)'", s)))


def post_formats():
    s = read("wp-includes/post-formats.php")
    i = s.find("function get_post_format_strings")
    seg = s[i : i + 2000]
    return sorted(set(re.findall(r"'([a-z-]+)'\s*=>\s*_x\(", seg)))


def capabilities():
    s = read("wp-includes/capabilities.php")
    i = s.find("function map_meta_cap")
    seg = s[i : i + 90000]
    return sorted(set(re.findall(r"^\s+case '([a-z_]+)':", seg, re.M)))


def roles():
    """Initial roles are seeded by populate_roles() in wp-admin/includes/schema.php."""
    s = read("wp-admin/includes/schema.php")
    i = s.find("function populate_roles")
    seg = s[i : i + 60000] if i > 0 else s
    return sorted(set(re.findall(r"add_role\(\s*\n?\s*'([a-z_]+)'", seg)))


def role_cap_counts():
    s = read("wp-admin/includes/schema.php")
    i = s.find("function populate_roles")
    seg = s[i : i + 80000] if i > 0 else s
    out = {}
    # each role block: add_role( 'x', 'X', array( ...caps... ) );
    for m in re.finditer(r"add_role\(\s*'([a-z_]+)'[^\n]*\n?[^;]*?array\((.*?)\n\t\);", seg, re.S):
        caps = re.findall(r"^\s*'([a-z_]+)'", m.group(2), re.M)
        out[m.group(1)] = len(set(caps))
    return out


def meta_boxes():
    return sorted(set(re.findall(r"add_meta_box\(\s*\n?\s*'([^']+)'", read("wp-admin/includes/meta-boxes.php"))))


def rest_controllers():
    d = os.path.join(WP, "wp-includes/rest-api/endpoints")
    out = []
    for f in sorted(os.listdir(d)):
        if not f.startswith("class-wp-rest-"):
            continue
        name = f[len("class-wp-rest-") : -len(".php")]
        out.append(re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name))
    return out


def widgets():
    d = os.path.join(WP, "wp-includes/widgets")
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.startswith("class-wp-widget-") and f.endswith(".php"):
            name = f[len("class-wp-widget-") : -len(".php")]
            out.append(re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name))
    return out


def shortcodes():
    """Core-registered shortcodes live in default-filters.php / default-widgets.php."""
    blob = read("wp-includes/default-filters.php") + read("wp-includes/widgets/block.php") + read(
        "wp-includes/embed.php"
    )
    found = set(re.findall(r"add_shortcode\(\s*'([^']+)'", blob))
    found |= set(re.findall(r"add_shortcode\(\s*'([^']+)'\s*,", blob))
    return sorted(found)


def blocks():
    d = os.path.join(WP, "wp-includes/blocks")
    return sorted(f for f in os.listdir(d) if os.path.isdir(os.path.join(d, f)))


def block_supports():
    d = os.path.join(WP, "wp-includes/block-supports")
    if not os.path.isdir(d):
        return []
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".php"))


def shortcodes():
    s = read("wp-includes/shortcodes.php")
    # core shortcodes are added in default-filters.php
    df = read("wp-includes/default-filters.php")
    found = set(re.findall(r"add_shortcode\(\s*\n?\s*'([^']+)'", s + df))
    return sorted(found)


def rewrite_tags():
    s = read("wp-includes/rewrite.php")
    i = s.find("$wp_rewrite->extra_permastructs")
    seg = s[: i + 4000] if i > 0 else s
    i2 = s.find("function WP_Rewrite::extra_permastructs")
    seg2 = s[i2 : i2 + 4000] if i2 > 0 else ""
    return sorted(set(re.findall(r"^\s+'([a-z_%]+)'\s*=>", seg2, re.M)))


def feeds():
    return sorted(
        f for f in os.listdir(os.path.join(WP, "wp-includes"))
        if f.startswith("feed-") or f in {"feed.php", "rss.php"}
    )


def admin_screens():
    d = os.path.join(WP, "wp-admin")
    return sorted(f for f in os.listdir(d) if f.endswith(".php"))


def hooks_count():
    n = 0
    for rel in ("wp-includes/default-filters.php",):
        s = read(rel)
        n += len(re.findall(r"^add_(action|filter)\(", s, re.M))
    return n


def cron_events():
    s = read("wp-includes/cron.php")
    i = s.find("function _get_cron_array")
    return len(set(re.findall(r"'([a-z0-9_]+)'\s*=>\s*array\(", s)))


def meta_keys():
    s = read("wp-includes/meta.php")
    i = s.find("function register_meta")
    return len(re.findall(r"register_meta\(", s))


def main():
    inv = {
        "source": WP,
        "version": re.search(r"\$wp_version\s*=\s*'([^']+)'", read("wp-includes/version.php")).group(1),
        "post_types": post_types(),
        "taxonomies": taxonomies(),
        "post_statuses": post_statuses(),
        "post_formats": post_formats(),
        "capabilities": capabilities(),
        "roles": roles(),
        "role_cap_counts": role_cap_counts(),
        "meta_boxes": meta_boxes(),
        "rest_controllers": rest_controllers(),
        "widgets": widgets(),
        "blocks": blocks(),
        "block_supports": block_supports(),
        "shortcodes": shortcodes(),
        "feeds": feeds(),
        "admin_screens": admin_screens(),
        "wp_includes_files": sorted(f for f in os.listdir(os.path.join(WP, "wp-includes")) if f.endswith(".php")),
        "wp_includes_subdirs": sorted(
            d for d in os.listdir(os.path.join(WP, "wp-includes")) if os.path.isdir(os.path.join(WP, "wp-includes", d))
        ),
        "wp_admin_files": sorted(f for f in os.listdir(os.path.join(WP, "wp-admin")) if f.endswith(".php")),
        "wp_admin_subdirs": sorted(
            d for d in os.listdir(os.path.join(WP, "wp-admin")) if os.path.isdir(os.path.join(WP, "wp-admin", d))
        ),
        "default_filter_hooks": hooks_count(),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(inv, fh, indent=1, ensure_ascii=False)
    for k, v in inv.items():
        if isinstance(v, list):
            print(f"{len(v):5d}  {k}")
        else:
            print(f"       {k}: {v}")
    print("written:", OUT)


if __name__ == "__main__":
    main()
