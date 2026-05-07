"""Probe Ollama Cloud embedding models via the python client (handles auth)."""
import sys
import ollama

models = [
    "nomic-embed-text:latest-cloud",
    "embeddinggemma:latest-cloud",
    "mxbai-embed-large:latest-cloud",
    "bge-m3:latest-cloud",
    "nomic-embed-text",  # local for comparison
]
for m in models:
    try:
        r = ollama.embeddings(model=m, prompt="hi there")
        emb = r.get("embedding", [])
        print(f"  {m:42s} dim={len(emb)}")
    except Exception as e:
        msg = str(e)
        print(f"  {m:42s} ERR={type(e).__name__}: {msg[:140]}")
