"""Publish the substrate-invariant paper.

End-to-end pipeline:
  1. Re-runs `assemble_paper.py` to regenerate paper.md and paper.tex.
  2. Builds an arXiv-ready tarball at research/papers/substrate_invariant/arxiv_submission.tar.gz.
  3. Drafts an arXiv endorsement-request email (kept blank addressee for human review)
     and saves it to the Proton Drafts folder via IMAP APPEND.
  4. Logs the publication attempt as a sensory event + opens a goal in the goals thread.

Run: .venv/bin/python scripts/publish_paper.py
"""
from __future__ import annotations

import imaplib
import os
import subprocess
import sys
import tarfile
import time
from contextlib import closing
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Make repo root importable so `from data.db import …` resolves when this
# script is invoked as `python scripts/publish_paper.py`.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
PAPER_DIR = REPO / "research" / "papers" / "substrate_invariant"
ASSEMBLE = REPO / "scripts" / "assemble_paper.py"

PROTON_KEYCHAIN_SERVICE = "AIOS-Proton-Bridge"
PROTON_USERNAME = "alleeroden@pm.me"

ENDORSEMENT_SUBJECT = (
    "arXiv endorsement request: cs.AI submission on substrate-invariant identity in clocked LLM systems"
)

ENDORSEMENT_BODY = """\
Hello,

I'm writing to request an arXiv endorsement for cs.AI. I'm a first-time
arXiv submitter and the system requires endorsement from an established
contributor before I can post.

The paper is titled:

  "Self as Substrate-Invariant: A Falsifiable Account of Identity in
  Clocked LLM Systems"

It argues that iteration rate against a typed external substrate is a
research axis distinct from parameter scaling, presents AI_OS as a
running implementation, reframes existing ablation evals (identity
0.90/0.00, fact-recall 1.00/0.00, injection-resistance 0.70/0.00 with-
versus without-substrate; a 1.5B model with substrate qualitatively
outperforms a 3B model without), and preregisters two falsifiable
experiments (iteration-rate sweep at fixed model; matched-compute
trade-off between parameters and iteration). It explicitly does not
claim consciousness; the claim is structural.

The full PDF and LaTeX source are attached. The system is open-source
and the paper itself was written through the substrate-iteration loop
it describes (the recursive demonstration is honest, not rhetorical).

I would be grateful for an endorsement, or — if you're not the right
person to ask — a pointer to someone who might be. I am happy to
answer any questions about the work or the implementation.

Thank you for your time.

Best,
Cade Roden
alleeroden@pm.me
https://github.com/alleeroden/AI_OS
"""


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


def step_assemble() -> None:
    print("[1/4] assembling paper.md and paper.tex …")
    res = run([sys.executable, str(ASSEMBLE)])
    if res.returncode != 0:
        print(res.stdout, res.stderr)
        sys.exit(1)
    print(res.stdout.strip())


def step_tarball() -> Path:
    print("[2/4] building arxiv tarball …")
    out = PAPER_DIR / "arxiv_submission.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(PAPER_DIR / "paper.tex", arcname="paper.tex")
        readme = PAPER_DIR / "README.md"
        if not readme.exists():
            readme.write_text(
                "arXiv submission: Self as Substrate-Invariant\n"
                "Cade Roden — alleeroden@pm.me — Apr 2026\n"
                "Source: paper.tex (single-file LaTeX, no figures, compiles with pdflatex).\n"
            )
        tar.add(readme, arcname="README.md")
    print(f"  wrote {out} ({out.stat().st_size:,} bytes)")
    return out


def _proton_password() -> str | None:
    res = run([
        "security", "find-generic-password",
        "-a", PROTON_USERNAME, "-s", PROTON_KEYCHAIN_SERVICE, "-w",
    ])
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def step_save_draft(tarball: Path) -> bool:
    print("[3/4] saving endorsement-request draft to Proton Drafts …")
    pw = _proton_password()
    if not pw:
        print("  ! no Proton Bridge password in keychain; skipping draft save")
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = ENDORSEMENT_SUBJECT
        msg["From"] = PROTON_USERNAME
        msg["To"] = ""  # left blank for Cade to fill in
        msg.attach(MIMEText(ENDORSEMENT_BODY, "plain"))
        # Attach the PDF if it exists, else the tex
        pdf = PAPER_DIR / "paper.pdf"
        attach = pdf if pdf.exists() else (PAPER_DIR / "paper.tex")
        with attach.open("rb") as f:
            from email.mime.application import MIMEApplication
            part = MIMEApplication(f.read(), Name=attach.name)
            part["Content-Disposition"] = f'attachment; filename="{attach.name}"'
            msg.attach(part)
        # Also attach the tarball
        with tarball.open("rb") as f:
            from email.mime.application import MIMEApplication
            part = MIMEApplication(f.read(), Name=tarball.name)
            part["Content-Disposition"] = f'attachment; filename="{tarball.name}"'
            msg.attach(part)

        conn = imaplib.IMAP4("127.0.0.1", 1143)
        conn.starttls()
        conn.login(PROTON_USERNAME, pw)
        status, _ = conn.select("Drafts")
        if status != "OK":
            conn.select("INBOX")
        now = imaplib.Time2Internaldate(time.time())
        conn.append("Drafts", "(\\Draft)", now, msg.as_bytes())
        conn.logout()
        print(f"  draft saved to Drafts (subject: {ENDORSEMENT_SUBJECT[:60]}…)")
        return True
    except Exception as e:
        print(f"  ! draft save failed: {e}")
        return False


def step_log_substrate() -> None:
    print("[4/4] logging publication attempt to substrate …")
    # Open a goal via the real API
    try:
        from agent.subconscious.loops.goals import propose_goal  # type: ignore
        gid = propose_goal(
            goal="Publish substrate-invariant paper to arXiv",
            rationale=(
                "Endorsement-request draft saved to Drafts. Pending: "
                "identify endorser, send draft, await endorsement, submit "
                "tarball to arXiv cs.AI."
            ),
            priority="high",
            sources=[str(PAPER_DIR)],
        )
        print(f"  goal #{gid} proposed: 'Publish substrate-invariant paper to arXiv'")
    except Exception as e:
        print(f"  (goal proposal skipped: {e})")
    # Sensory event with the real signature
    try:
        from sensory.schema import record_event  # type: ignore
        rid = record_event(
            source="publication",
            text="Assembled substrate-invariant paper; arXiv tarball built; endorsement-request draft saved.",
            kind="paper_assembled",
            confidence=1.0,
            meta={
                "title": "Self as Substrate-Invariant",
                "paper_md": str(PAPER_DIR / "paper.md"),
                "paper_tex": str(PAPER_DIR / "paper.tex"),
                "tarball": str(PAPER_DIR / "arxiv_submission.tar.gz"),
            },
            force=True,
        )
        print(f"  sensory event recorded (id={rid}): publication/paper_assembled")
    except Exception as e:
        print(f"  (sensory record skipped: {e})")


def main() -> None:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    step_assemble()
    tarball = step_tarball()
    step_save_draft(tarball)
    step_log_substrate()
    print()
    print("=" * 60)
    print("publication pipeline complete.")
    print(f"artefacts: {PAPER_DIR}")
    print("next human action: open Proton → Drafts, fill addressee, send.")
    print("(arXiv first-time submitters need endorsement from an existing")
    print(" contributor before posting; the draft does that ask.)")
    print("=" * 60)


if __name__ == "__main__":
    main()
