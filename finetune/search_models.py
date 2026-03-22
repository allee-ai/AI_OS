"""Search HuggingFace for small MLX-compatible models."""
from huggingface_hub import HfApi
api = HfApi()

searches = [
    "mlx-community pythia",
    "mlx-community gpt2",
    "mlx-community Qwen2.5 0.5B",
    "mlx-community SmolLM",
    "mlx-community Qwen 0.5",
]

for q in searches:
    print(f"\n--- {q} ---")
    try:
        models = list(api.list_models(search=q, sort="downloads", limit=5))
        for m in models:
            print(f"  {m.id}  (downloads={m.downloads})")
        if not models:
            print("  (none)")
    except Exception as e:
        print(f"  error: {e}")
