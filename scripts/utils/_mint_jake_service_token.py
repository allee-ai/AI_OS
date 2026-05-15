"""One-shot: mint a long-lived JWT for the jake-app `sales` user and stash
it in the macOS keychain so form_server can read it the same way it reads
the Proton Bridge password.

Run this once. If you ever rotate JWT_SECRET on the jake-app box, run it
again. The token has no refresh — it's a single artifact.

Storage:
    security add-generic-password -U -s AIOS-Jake-Token -a sales -w <TOKEN>
"""

import subprocess
from datetime import datetime, timedelta, timezone

import jwt

JWT_SECRET = "pk-jwt-x9f2m7q4w8-prod"
USER_ID = 3
USERNAME = "sales"
ROLE = "sales"
YEARS = 10


def main() -> None:
    exp = datetime.now(timezone.utc) + timedelta(days=365 * YEARS)
    payload = {
        "sub": str(USER_ID),
        "username": USERNAME,
        "role": ROLE,
        "exp": exp,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    subprocess.run(
        [
            "security", "add-generic-password",
            "-U",  # update if exists
            "-s", "AIOS-Jake-Token",
            "-a", "sales",
            "-w", token,
        ],
        check=True,
    )
    print(f"stored AIOS-Jake-Token (sales) — len={len(token)}, exp={exp.isoformat()}")
    print("read it back with:")
    print('  security find-generic-password -s AIOS-Jake-Token -a sales -w')


if __name__ == "__main__":
    main()
