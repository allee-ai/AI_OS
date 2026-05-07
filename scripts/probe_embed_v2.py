"""Probe Ollama Cloud embedding using the new /api/embed endpoint."""
import json
import urllib.request

models = [
    "nomic-embed-text:latest-cloud",
    "embeddinggemma:latest-cloud",
    "mxbai-embed-large:latest-cloud",
    "bge-m3:latest-cloud",
]
for m in models:
    payload = json.dumps({"model": m, "input": "hi there"}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
            embs = data.get("embeddings") or [data.get("embedding") or []]
            dim = len(embs[0]) if embs and embs[0] else 0
            print(f"  {m:42s} dim={dim}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:140]
        print(f"  {m:42s} HTTP {e.code}: {body}")
    except Exception as e:
        print(f"  {m:42s} ERR={type(e).__name__}: {str(e)[:140]}")
