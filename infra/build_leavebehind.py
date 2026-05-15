"""Build the printable investor leave-behind PDF.

One page, Letter, brand-consistent. Drops at:
  workspace/vre-construction/investor-leavebehind.pdf

So it's downloadable from https://vre-construction.com/investor-leavebehind.pdf
after the next deploy.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "darwin" and "/opt/homebrew/lib" not in os.environ.get(
    "DYLD_FALLBACK_LIBRARY_PATH", ""
):
    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
        "/opt/homebrew/lib" + (":" + existing if existing else "")
    )

import jinja2
import yaml
import weasyprint

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workspace" / "vre-construction-src"
OUT = ROOT / "workspace" / "vre-construction" / "investor-leavebehind.pdf"


def main() -> int:
    site = yaml.safe_load((SRC / "site.yaml").read_text())
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(SRC / "templates"),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    tmpl = env.get_template("leavebehind.html.j2")
    html = tmpl.render(site=site)

    pdf_bytes = weasyprint.HTML(
        string=html,
        base_url=str(SRC / "templates"),
    ).write_pdf()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(pdf_bytes)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(pdf_bytes):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
