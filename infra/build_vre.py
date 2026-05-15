"""Build vre-construction.com static site from CSV + YAML sources.

Usage:
    .venv/bin/python infra/build_vre.py

Reads:  workspace/vre-construction-src/
Writes: workspace/vre-construction/

What gets templated today: pricing.html
Everything else (index.html, services.html, knowledge.html, contact.html,
sitemap.xml, robots.txt) is left untouched in workspace/vre-construction/
until you say so.

Adding a price row: open workspace/vre-construction-src/pricing/<table>.csv
in Numbers, edit the row, save. Run this script. Deploy.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import jinja2
import markdown as md
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workspace" / "vre-construction-src"
OUT = ROOT / "workspace" / "vre-construction"


# ---------- markdown helpers --------------------------------------------------

# Custom inline renderer: handles **bold**, *italic*, `code`, and [text](url)
# without wrapping in <p>. Used for table cells, list items, callout text.
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITAL = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?!\w)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")


def md_inline(text: str) -> str:
    """Markdown for inline contexts (no <p> wrap). Bold, italic, links, code."""
    if text is None:
        return ""
    s = str(text)
    # Order matters: escape only what we don't generate; preserve raw HTML
    # since users might write `&mdash;` or `&rarr;`.
    s = _LINK.sub(r'<a href="\2">\1</a>', s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITAL.sub(r"<em>\1</em>", s)
    s = _CODE.sub(r"<code>\1</code>", s)
    return s


def md_block(text: str) -> str:
    """Markdown for block contexts (paragraphs, lists). Returns full HTML."""
    if text is None:
        return ""
    return md.markdown(str(text), extensions=["extra"])


# ---------- CSV loader --------------------------------------------------------

PRICE_HEADERS = {"range", "price", "cost"}


def load_csv(path: Path) -> dict:
    """Read a CSV. Returns {headers, rows, price_cols} where price_cols is a
    list of booleans, one per header, True if the column is the price column.
    """
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return {"headers": [], "rows": [], "price_cols": []}
    headers = rows[0]
    body = rows[1:]
    price_cols = [h.strip().lower() in PRICE_HEADERS for h in headers]
    return {"headers": headers, "rows": body, "price_cols": price_cols}


def load_all_csvs(table_dir: Path) -> dict[str, dict]:
    return {p.name: load_csv(p) for p in sorted(table_dir.glob("*.csv"))}


# ---------- page renderers ----------------------------------------------------

def render_pricing(env: jinja2.Environment, site: dict) -> str:
    page = yaml.safe_load((SRC / "pricing.yaml").read_text())
    csv_tables = load_all_csvs(SRC / "pricing")
    # sanity check: every referenced CSV exists
    for s in page.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("type") == "table" and b["csv"] not in csv_tables:
                raise SystemExit(f"pricing.yaml references missing CSV: {b['csv']}")
    tmpl = env.get_template("pricing.html.j2")
    return tmpl.render(
        site=site,
        this_page="pricing.html",
        meta=page["meta"],
        jsonld=page.get("jsonld"),
        hero=page["hero"],
        toc_title=page.get("toc_title"),
        sections=page["sections"],
        outro=page.get("outro"),
        csv_tables=csv_tables,
    )


def render_index(env: jinja2.Environment, site: dict) -> str:
    page = yaml.safe_load((SRC / "index.yaml").read_text())
    tmpl = env.get_template("index.html.j2")
    return tmpl.render(
        site=site,
        this_page="index.html",
        meta=page["meta"],
        hero=page["hero"],
        stats=page["stats"],
        how=page["how"],
        photo_band=page["photo_band"],
        services=page["services"],
        values=page["values"],
        testimonials=page["testimonials"],
    )


def _render_yaml_page(env: jinja2.Environment, site: dict, yaml_name: str, tmpl_name: str, this_page: str) -> str:
    page = yaml.safe_load((SRC / yaml_name).read_text())
    tmpl = env.get_template(tmpl_name)
    return tmpl.render(site=site, this_page=this_page, **page)


def render_services(env, site):
    return _render_yaml_page(env, site, "services.yaml", "services.html.j2", "services.html")


def render_contact(env, site):
    return _render_yaml_page(env, site, "contact.yaml", "contact.html.j2", "contact.html")


def render_knowledge(env, site):
    return _render_yaml_page(env, site, "knowledge.yaml", "knowledge.html.j2", "knowledge.html")


def render_instant_quote(env: jinja2.Environment, site: dict) -> str:
    page = yaml.safe_load((SRC / "quote.yaml").read_text())
    catalog = {"categories": page["categories"], "modifiers": page["modifiers"]}
    catalog_json = json.dumps(catalog, ensure_ascii=False)
    tmpl = env.get_template("instant-quote.html.j2")
    return tmpl.render(
        site=site,
        this_page="instant-quote.html",
        meta=page["meta"],
        hero=page["hero"],
        property_types=page["property_types"],
        categories=page["categories"],
        modifiers=page["modifiers"],
        contact=page["contact"],
        result=page["result"],
        outro_cta_h2=page.get("outro_cta_h2", ""),
        outro_cta_lede=page.get("outro_cta_lede", ""),
        catalog_json=catalog_json,
    )


# ---------- main --------------------------------------------------------------

def main() -> int:
    if not SRC.exists():
        print(f"source dir missing: {SRC}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    site = yaml.safe_load((SRC / "site.yaml").read_text())

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(SRC / "templates"),
        autoescape=jinja2.select_autoescape(["html"]),
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    env.filters["md_inline"] = md_inline
    env.filters["md_block"] = md_block

    targets: list[tuple[str, callable]] = [
        ("index.html",         render_index),
        ("services.html",      render_services),
        ("pricing.html",       render_pricing),
        ("knowledge.html",     render_knowledge),
        ("instant-quote.html", render_instant_quote),
        ("contact.html",       render_contact),
    ]

    for fname, render in targets:
        html = render(env, site)
        out_path = OUT / fname
        out_path.write_text(html, encoding="utf-8")
        print(f"wrote {out_path.relative_to(ROOT)} ({len(html):,} bytes)")

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
