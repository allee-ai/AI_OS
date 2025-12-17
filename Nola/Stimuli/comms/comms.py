#!/usr/bin/env python3
"""
Simple Twilio poller using only `requests`.

- Reads TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN from environment.
- Fetches recent messages from Twilio REST API.
- Appends new messages (by SID) to Stimuli/Email/inbox/inbox.json (array of objects).
- Downloads media into Stimuli/Email/media/<MessageSid>/ and records local paths.
"""

import os
import json
from pathlib import Path
from typing import List
import requests
from datetime import datetime

TW_ACCOUNT = os.getenv("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
API_BASE = "https://api.twilio.com/2010-04-01/Accounts"

# Destination paths
INBOX_FILE = Path("Stimuli/stimuli.json")
MEDIA_DIR = Path("Stimuli/Email/media")
INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

def _auth():
    if not TW_ACCOUNT or not TW_TOKEN:
        raise RuntimeError("Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars")
    return (TW_ACCOUNT, TW_TOKEN)

def load_inbox() -> List[dict]:
    if not INBOX_FILE.exists():
        return []
    try:
        return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_inbox(items: List[dict]) -> None:
    INBOX_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_messages(page_size: int = 50) -> List[dict]:
    auth = _auth()
    url = f"{API_BASE}/{TW_ACCOUNT}/Messages.json"
    params = {"PageSize": page_size}
    resp = requests.get(url, auth=auth, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # Twilio returns messages list under "messages"
    return data.get("messages", [])

def fetch_media_list(message_sid: str) -> List[dict]:
    auth = _auth()
    url = f"{API_BASE}/{TW_ACCOUNT}/Messages/{message_sid}/Media.json"
    resp = requests.get(url, auth=auth, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # endpoint typically returns list under "media_list" or "media"
    return data.get("media_list") or data.get("media") or data.get("media_list", []) or data.get("media", [])

def download_media_item(message_sid: str, media_item: dict) -> str:
    """
    media_item should contain 'sid' and/or 'uri' and 'content_type' if available.
    Returns local path (string) on success.
    """
    auth = _auth()
    uri = media_item.get("uri") or media_item.get("uri", "")
    media_sid = media_item.get("sid") or media_item.get("sid", "unknown")
    content_type = media_item.get("content_type") or media_item.get("content_type", "application/octet-stream")
    # Full URL for binary content: prefix api base and remove trailing ".json" if present
    if uri.startswith("/"):
        media_url = f"https://api.twilio.com{uri}"
    else:
        media_url = uri
    # remove trailing .json if present to get raw media
    if media_url.endswith(".json"):
        media_url = media_url[:-5]

    # deduce extension from content_type
    ext = content_type.split("/")[-1].split("+")[0] or "bin"
    out_dir = MEDIA_DIR / message_sid
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{media_sid}.{ext}"

    with requests.get(media_url, auth=auth, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in r.iter_content(8192):
                if chunk:
                    fh.write(chunk)
    return str(out_path)

def main():
    try:
        messages = fetch_messages(page_size=50)
    except Exception as e:
        print(f"Failed to fetch messages: {e}")
        return

    inbox = load_inbox()
    existing_sids = {m.get("sid") for m in inbox if m.get("sid")}
    appended = 0

    for msg in messages:
        sid = msg.get("sid")
        if not sid or sid in existing_sids:
            continue

        sender = msg.get("from") or msg.get("from_formatted") or ""
        body = msg.get("body") or ""
        date_received = msg.get("date_sent") or msg.get("date_created") or datetime.utcnow().isoformat()

        record = {
            "sid": sid,
            "sender": sender,
            "subject": "",
            "body": body,
            "received_at": date_received,
            "media": []
        }

        num_media = int(msg.get("num_media") or 0)
        if num_media > 0:
            try:
                media_list = fetch_media_list(sid)
            except Exception as e:
                record["media"].append({"error": f"failed to list media: {e}"})
                inbox.append(record); appended += 1; existing_sids.add(sid)
                continue

            for item in media_list:
                try:
                    local = download_media_item(sid, item)
                    record["media"].append({"local_path": local, "media_sid": item.get("sid"), "content_type": item.get("content_type")})
                except Exception as e:
                    record["media"].append({"error": str(e), "remote": item})

        inbox.append(record)
        appended += 1
        existing_sids.add(sid)

    if appended:
        save_inbox(inbox)
        print(f"Appended {appended} new message(s) to {INBOX_FILE}")
    else:
        print("No new messages.")

if __name__ == "__main__":
    main()