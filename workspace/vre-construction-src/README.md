# vre-construction.com — source

The pricing page is now built from this directory instead of hand-edited.
Everything else (index, services, contact, knowledge) is still raw HTML
in `workspace/vre-construction/` for now.

## Edit a price

1. Open `pricing/<table>.csv` in Numbers (or any spreadsheet / text editor).
2. Edit the cell. Save.
3. Build: `.venv/bin/python infra/build_vre.py`
4. Deploy: `bash infra/deploy_site.sh vre-construction.com workspace/vre-construction`

That's it. The build script regenerates `workspace/vre-construction/pricing.html`
from `pricing.yaml` + the CSVs + `templates/pricing.html.j2`.

## Add a new pricing table

1. Drop a new CSV in `pricing/`. Header row first. Any column whose header
   is `Range`, `Price`, or `Cost` (case-insensitive) auto-styles as the
   price column.
2. In `pricing.yaml`, add a `table` block to the appropriate section:
   ```yaml
   - type: table
     csv: yournew.csv
   ```
3. Build + deploy.

## Edit prose (intro, callouts, warnings, section text)

Edit `pricing.yaml`. Each section has `blocks` — an ordered list. Block types:

| type             | fields              | purpose                                       |
|------------------|---------------------|-----------------------------------------------|
| `text`           | `md`                | Paragraph(s) of markdown.                     |
| `kv`             | `items: [[k, v]]`   | Definition list, label + description.         |
| `bullets`        | `items: [...]`      | Unordered bullet list.                        |
| `bullets_ordered`| `items: [...]`      | Numbered list.                                |
| `h3`             | `text`              | Subheading inside a section.                  |
| `table`          | `csv`               | Render a CSV as a table.                      |
| `callout`        | `md`                | Purple-tinted info box.                       |
| `warn`           | `md`                | Pink-tinted warning box.                      |
| `cta_mini`       | `md`                | Small call-to-action box.                     |
| `twocol`         | `up_title`, `up`, `down_title`, `down` | Side-by-side pros/cons. |

Markdown supported in text fields: `**bold**`, `*italic*`, `` `code` ``,
`[link](url)`. No paragraphs inside inline contexts (table cells, list items)
— they stay single-line.

## Add or rearrange sections

`pricing.yaml` → `sections:` is an ordered list. Each section needs an
`id` (for the anchor link), `num` (the "01", "02"…), `title`, and `blocks`.
The TOC auto-generates from this list. Reorder freely; numbers don't have
to be sequential if you don't want them to be.

## Change the nav across all pages

Eventually. Right now only `pricing.html` is templated, so editing
`site.yaml` will only affect the pricing page nav. To template the other
pages, add a render function in `infra/build_vre.py` and a Jinja template.

## Files

```
workspace/vre-construction-src/
├── site.yaml                   ← brand, nav, footer (site-wide)
├── pricing.yaml                ← pricing page structure + prose
├── pricing/                    ← editable CSVs (one per table)
│   ├── diagnostic.csv
│   ├── outlets.csv
│   └── … (16 total)
└── templates/
    └── pricing.html.j2         ← Jinja template (CSS + structure)
```

Output: `workspace/vre-construction/pricing.html`
