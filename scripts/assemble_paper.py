"""Assemble the substrate-invariant paper from session memory drafts.

Reads the 11 locked section drafts + title + abstract from the Copilot
memory-tool directory, strips per-section meta-notes and version markers,
and writes a single clean Markdown manuscript plus an arXiv-ready LaTeX
source to research/papers/substrate_invariant/.

Run: .venv/bin/python scripts/assemble_paper.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "research" / "papers" / "substrate_invariant"
MEM_DIR = Path(
    "/Users/cade/Library/Application Support/Code/User/workspaceStorage/"
    "1d1eb7ce2af3f8d35653fa92652e7e62/GitHub.copilot-chat/memory-tool/"
    "memories/NDkzNzEyM2UtZWVlZi00NjI2LTliNzMtYzEwMzk3MmU4ZWU5"
)

TITLE = "Self as Substrate-Invariant: A Falsifiable Account of Identity in Clocked LLM Systems"
SUBTITLE = "The substrate hypothesis, two preregistered experiments, and what existing evals were always measuring"
AUTHOR = "Cade Roden"
AFFIL = "Independent"
EMAIL = "alleeroden@pm.me"

SECTIONS = [
    # (memory filename, section header, section number)
    ("abstract_draft.md", "Abstract", None),
    ("intro_draft.md", "Introduction", 1),
    ("related_work_draft.md", "Related Work", 2),
    ("substrate_spec_draft.md", "The Clocked-Substrate Framework", 3),
    ("aios_instantiation_draft.md", "AI\\_OS as a Concrete Instantiation", 4),
    ("evals_reframed_draft.md", "Existing Evaluations, Reframed", 5),
    ("experiments_draft.md", "Two Falsifiable Experiments", 6),
    ("self_invariant_draft.md", "Self as Substrate-Invariant", 7),
    ("limitations_draft.md", "Limitations", 8),
    ("cogsci_draft.md", "Relation to Cognitive Science and Dynamical-Systems Cognition", 9),
    ("conclusion_draft.md", "Conclusion", 10),
]


def clean_draft(text: str) -> str:
    """Strip meta-notes, version markers, and section header from a draft."""
    lines = text.splitlines()
    out: list[str] = []
    skip = False
    for line in lines:
        # Drop the top-level title line (we re-emit our own headers)
        if line.startswith("# §") or line.startswith("# Abstract"):
            continue
        # Drop version-marker subsections like "## v15 (locked) — ~258 words"
        if re.match(r"^##\s+v\d+", line):
            continue
        # Drop everything from meta-notes onward
        low = line.strip().lower()
        if low.startswith("## meta-notes") or low.startswith("## v") and "notes" in low:
            skip = True
        if skip:
            continue
        out.append(line)
    cleaned = "\n".join(out).strip() + "\n"
    # Collapse runs of >2 blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def latex_escape(text: str) -> str:
    """Minimal LaTeX escaping for body prose. Preserves $...$ math."""
    # Protect math spans
    parts = re.split(r"(\$[^\$]+\$)", text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # math span
            out.append(part)
            continue
        # Escape special chars (skip & since we don't use it raw; & stays raw if any)
        part = part.replace("\\", "\\textbackslash{}")
        part = part.replace("_", "\\_")
        part = part.replace("%", "\\%")
        part = part.replace("#", "\\#")
        part = part.replace("&", "\\&")
        part = part.replace("~", "\\textasciitilde{}")
        part = part.replace("^", "\\textasciicircum{}")
        # Restore textbackslash sequence we just damaged for math — our split protects math spans
        part = part.replace("\\textbackslash{}_", "\\_")  # safety
        out.append(part)
    return "".join(out)


def md_to_latex_body(md: str) -> str:
    """Translate cleaned markdown body into LaTeX body fragments.

    Handles: # / ## / ### headers, **bold**, *italic*, `code`, lists,
    fenced code blocks, and inline math.
    """
    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    in_list_ul = False
    in_list_ol = False

    def close_lists():
        nonlocal in_list_ul, in_list_ol
        if in_list_ul:
            out.append("\\end{itemize}")
            in_list_ul = False
        if in_list_ol:
            out.append("\\end{enumerate}")
            in_list_ol = False

    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```"):
            close_lists()
            if not in_code:
                out.append("\\begin{verbatim}")
                in_code = True
            else:
                out.append("\\end{verbatim}")
                in_code = False
            continue
        if in_code:
            out.append(raw)
            continue

        if not line.strip():
            close_lists()
            out.append("")
            continue

        # Headers within a section -> subsection / subsubsection
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            close_lists()
            out.append(f"\\subsubsection*{{{inline_md(m.group(1))}}}")
            continue
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            close_lists()
            out.append(f"\\subsection*{{{inline_md(m.group(1))}}}")
            continue
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            close_lists()
            out.append(f"\\paragraph{{{inline_md(m.group(1))}}}")
            continue

        # Lists
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if in_list_ol:
                out.append("\\end{enumerate}")
                in_list_ol = False
            if not in_list_ul:
                out.append("\\begin{itemize}")
                in_list_ul = True
            out.append(f"  \\item {inline_md(m.group(1))}")
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m:
            if in_list_ul:
                out.append("\\end{itemize}")
                in_list_ul = False
            if not in_list_ol:
                out.append("\\begin{enumerate}")
                in_list_ol = True
            out.append(f"  \\item {inline_md(m.group(1))}")
            continue

        close_lists()
        out.append(inline_md(line))

    close_lists()
    if in_code:
        out.append("\\end{verbatim}")
    return "\n".join(out)


def inline_md(text: str) -> str:
    """Inline markdown -> LaTeX, preserving math."""
    parts = re.split(r"(\$[^\$]+\$)", text)
    rendered = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            rendered.append(part)  # math passthrough
            continue
        # Escape first
        s = latex_escape(part)
        # Bold then italic
        s = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\emph{\1}", s)
        # Inline code
        s = re.sub(r"`([^`]+)`", r"\\texttt{\1}", s)
        # Em-dashes
        s = s.replace(" — ", "---")
        rendered.append(s)
    return "".join(rendered)


def assemble_markdown() -> str:
    md_parts = [
        f"# {TITLE}",
        "",
        f"*{SUBTITLE}*",
        "",
        f"**{AUTHOR}** \\\n*{AFFIL}* — {EMAIL}",
        "",
        "---",
        "",
    ]
    for fname, header, num in SECTIONS:
        body = clean_draft((MEM_DIR / fname).read_text())
        if num is None:
            md_parts.append(f"## {header}")
        else:
            md_parts.append(f"## {num}. {header}")
        md_parts.append("")
        md_parts.append(body.strip())
        md_parts.append("")
    return "\n".join(md_parts)


def assemble_latex() -> str:
    preamble = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{microtype}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{titlesec}
\titlespacing*{\section}{0pt}{14pt}{6pt}
\titlespacing*{\subsection}{0pt}{10pt}{4pt}
\setlist{topsep=2pt,itemsep=2pt}
\setlength{\parskip}{6pt}
\setlength{\parindent}{0pt}

\title{""" + TITLE.replace("_", "\\_") + r"""\\[4pt]\large \emph{""" + SUBTITLE + r"""}}
\author{""" + AUTHOR + r""" \\ \small """ + AFFIL + r""" --- \texttt{""" + EMAIL + r"""}}
\date{April 2026}

\begin{document}
\maketitle
"""
    body_parts: list[str] = []
    for fname, header, num in SECTIONS:
        cleaned = clean_draft((MEM_DIR / fname).read_text())
        latex_body = md_to_latex_body(cleaned)
        if num is None:
            body_parts.append(r"\begin{abstract}")
            body_parts.append(latex_body)
            body_parts.append(r"\end{abstract}")
        else:
            # Use a header that doesn't escape & we control numbering
            body_parts.append(f"\\section{{{header}}}")
            body_parts.append(latex_body)
        body_parts.append("")
    closing = r"\end{document}"
    return preamble + "\n" + "\n".join(body_parts) + "\n" + closing


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = assemble_markdown()
    tex = assemble_latex()
    (OUT_DIR / "paper.md").write_text(md)
    (OUT_DIR / "paper.tex").write_text(tex)
    wc = word_count(md)
    print(f"wrote {OUT_DIR / 'paper.md'} ({len(md):,} chars, ~{wc:,} words)")
    print(f"wrote {OUT_DIR / 'paper.tex'} ({len(tex):,} chars)")


if __name__ == "__main__":
    main()
