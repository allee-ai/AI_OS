"""Save the 3 tailored endorsement emails to Proton Drafts.

Reads outreach/email_wang.md, email_qin.md, email_miteski.md, parses out
the body, and IMAP-APPENDs each as a separate draft to the Proton
Drafts folder. To: field is left blank — Cade fills in once she's
verified the address from the candidate's lab page.

Run: .venv/bin/python scripts/save_endorsement_drafts.py
"""
from __future__ import annotations

import imaplib
import re
import subprocess
import sys
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "research" / "papers" / "substrate_invariant" / "outreach"
PAPER_DIR = REPO / "research" / "papers" / "substrate_invariant"

PROTON_KEYCHAIN_SERVICE = "AIOS-Proton-Bridge"
PROTON_USERNAME = "alleeroden@pm.me"

NOLA_FROM = '"Nola (AI_OS Assistant)" <assistant@allee-ai.com>'
NOLA_REPLY_TO = "assistant@allee-ai.com"
CADE_REPLY_TO = "alleeroden@pm.me"


def proton_password() -> str | None:
    res = subprocess.run(
        ["security", "find-generic-password",
         "-a", PROTON_USERNAME, "-s", PROTON_KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True, check=False,
    )
    return res.stdout.strip() if res.returncode == 0 else None


def parse_email_md(path: Path) -> tuple[str, str]:
    """Return (subject, body) parsed from an outreach/email_*.md file."""
    text = path.read_text()
    subject_m = re.search(r"\*\*Subject:\*\*\s*(.+)", text)
    subject = subject_m.group(1).strip() if subject_m else "arXiv endorsement request"
    # Body starts after the first '---' divider
    parts = text.split("\n---\n", 1)
    body = parts[1].strip() if len(parts) > 1 else text
    return subject, body


def save_draft(subject: str, body: str) -> bool:
    pw = proton_password()
    if not pw:
        print(f"  ! no proton password; cannot save draft '{subject[:40]}…'")
        return False
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = NOLA_FROM
    msg["Reply-To"] = f"{NOLA_REPLY_TO}, {CADE_REPLY_TO}"
    msg["To"] = ""
    msg.attach(MIMEText(body, "plain"))
    # Attach the LaTeX source + tarball (smaller than PDF, no compile required)
    for fname in ("paper.tex", "arxiv_submission.tar.gz"):
        p = PAPER_DIR / fname
        if not p.exists():
            continue
        with p.open("rb") as f:
            part = MIMEApplication(f.read(), Name=p.name)
        part["Content-Disposition"] = f'attachment; filename="{p.name}"'
        msg.attach(part)
    try:
        conn = imaplib.IMAP4("127.0.0.1", 1143)
        conn.starttls()
        conn.login(PROTON_USERNAME, pw)
        status, _ = conn.select("Drafts")
        if status != "OK":
            conn.select("INBOX")
        conn.append("Drafts", "(\\Draft)", imaplib.Time2Internaldate(time.time()),
                    msg.as_bytes())
        conn.logout()
        return True
    except Exception as e:
        print(f"  ! IMAP error: {e}")
        return False


def main() -> None:
    n_saved = 0
    for key in ("wang", "qin", "miteski"):
        path = OUT / f"email_{key}.md"
        if not path.exists():
            print(f"  ! missing {path}")
            continue
        subject, body = parse_email_md(path)
        if save_draft(subject, body):
            print(f"  saved draft for {key}: {subject[:60]}…")
            n_saved += 1
    print()
    print(f"saved {n_saved} drafts to Drafts.")
    print("each has To: blank — fill in the recipient's address (looked up")
    print("from their lab page) before sending.")


if __name__ == "__main__":
    main()
