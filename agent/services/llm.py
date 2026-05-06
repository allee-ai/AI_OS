"""
LLM Provider Abstraction
=========================
Unified interface for calling LLMs across providers.
Providers auto-detect based on API keys in environment.

Usage:
    from agent.services.llm import generate, available_providers, available_models

    # Specific provider
    text = generate("Hello", provider="gemini")

    # Specific provider + model
    text = generate("Hello", provider="claude", model="claude-sonnet-4-20250514")

    # Aggregate: round-robin across all available free-tier providers
    text = generate("Hello", provider="aggregate")

    # Default: uses AIOS_MODEL_PROVIDER / AIOS_MODEL_NAME env vars
    text = generate("Hello")

    # With full messages list
    text = generate(messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ])

    # Discovery
    providers = available_providers()   # [OllamaProvider, GeminiProvider, ...]
    models = available_models()         # [{"id": "gemini-2.0-flash", "provider": "gemini", ...}, ...]
"""

import json
import os
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


# ── Base Class ──────────────────────────────────────────────

class LLMProvider(ABC):
    """Base class for LLM providers."""

    name: str = ""
    key_env: str = ""           # env var holding the API key ("" = no key needed)
    default_model: str = ""
    rpm: int = 10               # requests per minute (for rate limiting)
    style: str = ""             # protocol style: gemini, anthropic, openai, ollama

    # Models offered by this provider (id, display_name, context_length)
    catalog: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        """True if this provider is configured and reachable."""
        if self.key_env:
            return bool(os.environ.get(self.key_env))
        return True  # subclass should override for connectivity check

    def get_api_key(self) -> str:
        return os.environ.get(self.key_env, "") if self.key_env else ""

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]],
                 model: Optional[str] = None,
                 temperature: float = 0.7,
                 max_tokens: int = 2048) -> str:
        """Generate a completion. Returns the assistant's text."""
        ...

    def list_models(self) -> List[Dict[str, Any]]:
        """Return models with provider tag. Only if provider is available."""
        if not self.is_available():
            return []
        return [
            {**m, "provider": self.name}
            for m in self.catalog
        ]

    def __repr__(self):
        avail = "✓" if self.is_available() else "✗"
        return f"<{self.__class__.__name__} [{avail}] {self.name}>"


# ── Ollama ──────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    name = "ollama"
    key_env = ""
    default_model = "qwen2.5:7b"
    rpm = 999
    style = "ollama"
    catalog = [
        {"id": "qwen2.5:7b", "display": "Qwen 2.5 7B", "context": 32768},
        {"id": "llama3.2:3b", "display": "Llama 3.2 3B", "context": 131072},
        {"id": "mistral:7b", "display": "Mistral 7B", "context": 32768},
        {"id": "gemma2:9b", "display": "Gemma 2 9B", "context": 8192},
    ]

    def is_available(self) -> bool:
        try:
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            req = urllib.request.Request(f"{host}/api/tags")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """List actually-pulled Ollama models, falling back to catalog."""
        if not self.is_available():
            return []
        try:
            import ollama as _ollama
            response = _ollama.list()
            models = []
            for m in response.get("models", []):
                mid = m.get("name", m.get("model", ""))
                if not mid:
                    continue
                size = m.get("size", 0)
                size_str = f"{size / 1e9:.1f}GB" if size > 0 else ""
                models.append({
                    "id": mid,
                    "display": mid.replace(":", " ").title(),
                    "provider": self.name,
                    "description": f"Local {size_str}".strip(),
                })
            return models if models else [
                {**m, "provider": self.name} for m in self.catalog
            ]
        except Exception:
            return [{**m, "provider": self.name} for m in self.catalog]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        model = model or os.getenv("AIOS_MODEL_NAME", self.default_model)
        try:
            import ollama as _ollama
        except ImportError:
            raise RuntimeError("ollama not installed. Run: pip install ollama")

        # Cloud routing convention: cloud-tagged models (e.g.
        # "gpt-oss:120b-cloud", "kimi-k2:1t-cloud") route through the
        # *local* ollama daemon to Ollama Cloud automatically once the
        # user has run `ollama signin`. No separate host or auth header
        # required \u2014 the daemon handles it.
        #
        # OLLAMA_HOST is honored as a fallback for custom remote daemons
        # (self-hosted, separate machine, etc).
        host = os.getenv("OLLAMA_HOST", "").strip()
        try:
            if host:
                client = _ollama.Client(host=host)
                response = client.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature, "num_predict": max_tokens},
                )
            else:
                response = _ollama.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature, "num_predict": max_tokens},
                )
            return response["message"]["content"].strip()
        except Exception as e:
            try:
                from agent.threads.log.schema import log_event
                log_event(
                    event_type="error:model_routing",
                    data=f"Ollama generate failed: {e}",
                    metadata={
                        "model": model, "provider": "ollama",
                        "host": host or "local", "error": str(e),
                    },
                    source="llm.ollama",
                )
            except Exception:
                pass
            raise


# ── Gemini ──────────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    name = "gemini"
    key_env = "GEMINI_API_KEY"
    default_model = "gemini-2.0-flash"
    rpm = 15
    style = "gemini"
    catalog = [
        {"id": "gemini-2.0-flash", "display": "Gemini 2.0 Flash", "context": 1048576},
        {"id": "gemini-2.5-flash-preview-05-20", "display": "Gemini 2.5 Flash", "context": 1048576},
        {"id": "gemini-1.5-pro", "display": "Gemini 1.5 Pro", "context": 2097152},
    ]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError(f"Set {self.key_env}")

        model = model or self.default_model
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")

        # Extract system + user from messages
        system_text = ""
        user_parts = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                user_parts.append({"text": m["content"]})

        body: Dict[str, Any] = {
            "contents": [{"parts": user_parts}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Claude (Anthropic) ─────────────────────────────────────

class ClaudeProvider(LLMProvider):
    name = "claude"
    key_env = "ANTHROPIC_API_KEY"
    default_model = "claude-sonnet-4-20250514"
    rpm = 5
    style = "anthropic"
    catalog = [
        {"id": "claude-sonnet-4-20250514", "display": "Claude Sonnet 4", "context": 200000},
        {"id": "claude-3-5-haiku-20241022", "display": "Claude 3.5 Haiku", "context": 200000},
    ]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError(f"Set {self.key_env}")

        model = model or self.default_model

        # Anthropic wants system separately
        system_text = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                api_messages.append({"role": m["role"], "content": m["content"]})

        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "temperature": temperature,
        }
        if system_text:
            body["system"] = system_text

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"].strip()


# ── OpenAI ──────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    name = "openai"
    key_env = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"
    rpm = 3
    style = "openai"
    catalog = [
        {"id": "gpt-4o-mini", "display": "GPT-4o Mini", "context": 128000},
        {"id": "gpt-4o", "display": "GPT-4o", "context": 128000},
        {"id": "gpt-4.1-mini", "display": "GPT-4.1 Mini", "context": 1047576},
        {"id": "gpt-4.1", "display": "GPT-4.1", "context": 1047576},
    ]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError(f"Set {self.key_env}")

        model = model or self.default_model
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return _openai_compat_call(
            url=f"{base_url.rstrip('/')}/chat/completions",
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# ── OpenRouter ──────────────────────────────────────────────

class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    key_env = "OPENROUTER_API_KEY"
    default_model = "google/gemini-2.0-flash-exp:free"
    rpm = 10
    style = "openai"
    catalog = [
        {"id": "google/gemini-2.0-flash-exp:free", "display": "Gemini 2.0 Flash (free)", "context": 1048576},
        {"id": "mistralai/mistral-small-3.1-24b-instruct:free", "display": "Mistral Small 3.1 (free)", "context": 96000},
        {"id": "qwen/qwen3-235b-a22b:free", "display": "Qwen3 235B (free)", "context": 40960},
    ]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError(f"Set {self.key_env}")

        model = model or self.default_model
        return _openai_compat_call(
            url="https://openrouter.ai/api/v1/chat/completions",
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers={
                "HTTP-Referer": "https://github.com/nicholasgcoles/ai-os",
                "X-Title": "AI-OS",
            },
        )


# ── HTTP (Custom Endpoint) ─────────────────────────────────

class HTTPProvider(LLMProvider):
    name = "http"
    key_env = ""
    default_model = ""
    rpm = 999
    style = "openai"
    catalog = []

    def is_available(self) -> bool:
        return bool(os.getenv("AIOS_MODEL_ENDPOINT"))

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        endpoint = os.getenv("AIOS_MODEL_ENDPOINT", "")
        if not endpoint:
            raise ValueError("Set AIOS_MODEL_ENDPOINT")

        api_key = os.getenv("OPENAI_API_KEY", "")
        model = model or os.getenv("AIOS_MODEL_NAME", "")

        if api_key:
            return _openai_compat_call(
                url=f"{endpoint.rstrip('/')}/chat/completions",
                api_key=api_key,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # Bare HTTP — try simple JSON
        payload = json.dumps({"messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("message") or body.get("content") or str(body)


# ── Shared OpenAI-Compatible Caller ────────────────────────

def _openai_compat_call(url: str, api_key: str, model: str,
                        messages: List[Dict[str, str]],
                        temperature: float = 0.7,
                        max_tokens: int = 2048,
                        extra_headers: Optional[Dict[str, str]] = None) -> str:
    """Shared caller for any OpenAI-compatible API."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    choices = body.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "").strip()
    return str(body)


# ── MLX (Apple Silicon local models) ────────────────────────

class MLXProvider(LLMProvider):
    name = "mlx"
    key_env = ""
    default_model = ""
    rpm = 999
    style = "mlx"
    catalog = []

    _model_cache: Dict[str, Any] = {}

    def _scan_models(self) -> List[Dict[str, Any]]:
        """Scan for trained models in finetune/runs/ and experiments/runs/."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        models = []
        scan_dirs = [
            root / "finetune" / "runs",
            root / "experiments" / "runs",
        ]
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for run_dir in sorted(scan_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                # Check for model directories
                for model_name in ["self_model", "final_model", "pretrained_model"]:
                    model_dir = run_dir / model_name
                    safetensors = model_dir / "model.safetensors"
                    if safetensors.exists():
                        model_id = str(model_dir)
                        label = f"{run_dir.parent.parent.name}/{run_dir.name}/{model_name}"
                        size_mb = safetensors.stat().st_size / 1e6
                        models.append({
                            "id": model_id,
                            "display": label,
                            "context": 2048,
                            "description": f"Local MLX {size_mb:.0f}MB",
                        })
                # Also check root-level model.safetensors (fused models like 3b-v1-final)
                if (run_dir / "model.safetensors").exists():
                    model_id = str(run_dir)
                    label = f"{run_dir.parent.parent.name}/{run_dir.name}"
                    size_mb = (run_dir / "model.safetensors").stat().st_size / 1e6
                    models.append({
                        "id": model_id,
                        "display": label,
                        "context": 2048,
                        "description": f"Local MLX {size_mb:.0f}MB",
                    })
        return models

    def is_available(self) -> bool:
        try:
            import mlx_lm  # noqa: F401
            return True
        except ImportError:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        return [{**m, "provider": self.name} for m in self._scan_models()]

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        try:
            from mlx_lm import load, generate as mlx_generate
        except ImportError:
            raise RuntimeError("mlx-lm not installed. Run: pip install mlx-lm")

        model_path = model or self.default_model
        if not model_path:
            raise ValueError("No MLX model specified. Provide a model path.")

        # Cache loaded models
        if model_path not in self._model_cache:
            try:
                loaded_model, tokenizer = load(path_or_hf_repo=model_path)
            except Exception as e:
                try:
                    from agent.threads.log.schema import log_event
                    log_event(
                        event_type="error:model_routing",
                        data=f"MLX model load failed: {e}",
                        metadata={"model": model_path, "provider": "mlx", "error": str(e)},
                        source="llm.mlx",
                    )
                except Exception:
                    pass
                raise
            self._model_cache[model_path] = (loaded_model, tokenizer)
        loaded_model, tokenizer = self._model_cache[model_path]

        # Format with chat template
        if hasattr(tokenizer, "apply_chat_template"):
            formatted = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Fallback
            parts = []
            for m in messages:
                if m["role"] == "system":
                    parts.append(m["content"])
                elif m["role"] == "user":
                    parts.append(f"User: {m['content']}")
                elif m["role"] == "assistant":
                    parts.append(f"Assistant: {m['content']}")
            parts.append("Assistant:")
            formatted = "\n".join(parts)

        response = mlx_generate(
            loaded_model, tokenizer,
            prompt=formatted,
            max_tokens=max_tokens,
            verbose=False,
        )
        return response.strip()


# ── VS Code Keyboard (pipe, not an LLM) ─────────────────────

class VSCodeKeyboardProvider(LLMProvider):
    """Route `generate` into this Mac's VS Code Copilot Chat window.

    This is not a model — the "reply" is an acknowledgement. The real
    response is whatever Copilot types back in the VS Code chat UI.
    Use it to turn any aios chat surface (web UI, phone via /chat API,
    CLI) into a remote into the active Copilot window.

    Availability is gated to macOS hosts whose short hostname matches
    AIOS_KEYBOARD_HOSTNAME (if set) so the VM never selects a provider
    it cannot actually invoke. When unset, any macOS host with VS Code
    installed is eligible.
    """

    name = "vscode"
    key_env = ""
    default_model = "copilot"
    rpm = 60
    style = "keyboard"
    catalog = [
        {
            "id": "copilot",
            "display": "VS Code Copilot (Keyboard)",
            "context": 0,
            "description": "Forwards the message into VS Code Copilot Chat on this Mac.",
        },
    ]

    def is_available(self) -> bool:
        import platform, socket
        if platform.system() != "Darwin":
            return False
        pin = os.getenv("AIOS_KEYBOARD_HOSTNAME", "").strip()
        if pin:
            host = socket.gethostname().split(".")[0].lower()
            if host != pin.split(".")[0].lower():
                return False
        return os.path.exists("/Applications/Visual Studio Code.app")

    def generate(self, messages, model=None, temperature=0.7, max_tokens=2048):
        """Forward the last user message to VS Code Copilot and wait for reply.

        Protocol: we tag the forwarded prompt with a unique turn_id and
        instruct Copilot (me, in the chat) to write its reply to
        data/mobile_replies/<turn_id>.md via the create_file tool. We
        poll that file until it appears or we time out, then return
        the contents as the provider's generation.

        Timeout is AIOS_VSCODE_REPLY_TIMEOUT seconds (default 180).
        A timeout returns a short apology string so upstream callers
        don't hang the whole request chain.
        """
        import socket, secrets, time
        from pathlib import Path

        text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break
        if not text:
            return "[vscode-keyboard: empty message, nothing forwarded]"

        try:
            from agent.services.vs_bridge import forward as _vs_forward
        except Exception as e:
            return f"[vscode-keyboard: vs_bridge import failed — {e}]"

        host = socket.gethostname().split(".")[0]
        repo_root = Path(__file__).resolve().parents[2]
        reply_dir = repo_root / "data" / "mobile_replies"
        reply_dir.mkdir(parents=True, exist_ok=True)
        turn_id = secrets.token_hex(6)
        reply_path = reply_dir / f"{turn_id}.md"

        # Build the prompt with the reply-file directive. Explicit and
        # short — Copilot follows it reliably.
        prompt = (
            f"[chat turn={turn_id}]\n"
            f"{text}\n\n"
            f"^ message from an aios chat surface (phone / web / cli).\n"
            f"respond naturally here, AND write the same reply (markdown ok) to:\n"
            f"  {reply_path}\n"
            f"use the create_file tool. the caller is polling that file; if it "
            f"never appears the caller sees a timeout. keep the in-chat response "
            f"brief and put the full answer in the file."
        )

        ok = _vs_forward(prompt, source="chat_provider")
        if not ok:
            return f"[vscode-keyboard: forward failed on {host} — check accessibility permissions]"

        timeout_s = float(os.getenv("AIOS_VSCODE_REPLY_TIMEOUT", "180"))
        poll_ms = float(os.getenv("AIOS_VSCODE_REPLY_POLL_MS", "500"))
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if reply_path.exists():
                try:
                    content = reply_path.read_text(encoding="utf-8", errors="replace").strip()
                    if content:
                        return content
                except Exception:
                    pass
            time.sleep(poll_ms / 1000.0)
        return (
            f"[vscode-keyboard: Copilot @ {host} did not produce a reply within "
            f"{int(timeout_s)}s. the paste was delivered (turn={turn_id}); the reply "
            f"may still appear in VS Code but the polling caller has timed out.]"
        )


# ── Provider Registry ───────────────────────────────────────

PROVIDER_CLASSES: Dict[str, type] = {
    "mlx": MLXProvider,
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "http": HTTPProvider,
    "vscode": VSCodeKeyboardProvider,
}

# Singletons — instantiated on first access
_instances: Dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    """Get a provider instance by name."""
    if name not in _instances:
        cls = PROVIDER_CLASSES.get(name)
        if not cls:
            raise ValueError(f"Unknown provider: {name}. "
                             f"Available: {', '.join(PROVIDER_CLASSES)}")
        _instances[name] = cls()
    return _instances[name]


def available_providers() -> List[LLMProvider]:
    """Return all providers that are currently configured/reachable."""
    result = []
    for name in PROVIDER_CLASSES:
        p = get_provider(name)
        if p.is_available():
            result.append(p)
    return result


def available_models() -> List[Dict[str, Any]]:
    """Return models from all configured providers."""
    models = []
    for p in available_providers():
        models.extend(p.list_models())
    return models


# ── Aggregate (Round-Robin) ─────────────────────────────────

_aggregate_index = 0


def _next_aggregate_provider() -> LLMProvider:
    """Round-robin across all available providers."""
    global _aggregate_index
    providers = available_providers()
    if not providers:
        raise RuntimeError("No LLM providers available. Set an API key or start Ollama.")
    p = providers[_aggregate_index % len(providers)]
    _aggregate_index += 1
    return p


# ── Main Generate Function ─────────────────────────────────

def generate(prompt: Optional[str] = None,
             *,
             messages: Optional[List[Dict[str, str]]] = None,
             system: Optional[str] = None,
             provider: Optional[str] = None,
             model: Optional[str] = None,
             role: Optional[str] = None,
             temperature: float = 0.7,
             max_tokens: int = 2048) -> str:
    """Generate text from an LLM.

    Args:
        prompt:      Simple user prompt (convenience — builds messages list)
        messages:    Full messages list (overrides prompt if both given)
        system:      System prompt (prepended if using prompt= style)
        provider:    Provider name, "aggregate" for round-robin, or None for env default
        model:       Override model name (optional)
        role:        Role tag (e.g. "GOAL", "SELF_IMPROVE", "EVOLVE") used to
                     look up per-role provider/model overrides via
                     agent.services.role_model.resolve_role().  Only used
                     when *provider* and *model* are not explicitly passed.
        temperature: Sampling temperature
        max_tokens:  Max output tokens

    Returns:
        Generated text string.
    """
    # Build messages from prompt if needed
    if messages is None:
        if prompt is None:
            raise ValueError("Provide either prompt= or messages=")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

    # ── Demo-mode kill-switch ─────────────────────────────────────────
    # Two ways to disable real LLM calls:
    #   1. AIOS_NO_LLM=1            (explicit override, any DB)
    #   2. running on state_demo.db AND AIOS_DEMO_ALLOW_LLM is NOT set
    # Visitors browsing the public iframe must not burn tokens; they get
    # a canned reply explaining what they're looking at and how to run it.
    _no_llm = os.getenv("AIOS_NO_LLM", "").lower() in ("1", "true", "yes")
    if not _no_llm:
        try:
            from data.db import is_demo_mode
            if is_demo_mode() and os.getenv("AIOS_DEMO_ALLOW_LLM", "").lower() not in ("1", "true", "yes"):
                _no_llm = True
        except Exception:
            pass
    if _no_llm:
        return (
            "[demo mode — LLM calls disabled]\n\n"
            "You're looking at the real AI_OS interface in read-only demo mode. "
            "All the threads, memory, and tools are wired to a sample database, "
            "but generation is turned off so visitors don't burn tokens on the "
            "owner's account.\n\n"
            "To talk to the real one, run AI_OS locally:\n"
            "  https://github.com/allee-ai/AI_OS"
        )
    # ──────────────────────────────────────────────────────────────────

    # ── Chat-only demo gate ───────────────────────────────────────────
    # When AIOS_DEMO_LLM_CHAT_ONLY=1, only the user-facing chat path is
    # allowed to make real LLM calls. Every background role (memory,
    # consolidation, naming, summary, thought, goal, evolve, …) gets a
    # canned response so visitors can't trigger expensive backend work.
    #
    # Detection: the chat path resolves role upstream (in agent.agent.generate)
    # and passes explicit provider+model with role=None. Every other role
    # in the codebase calls generate(role="MEMORY"|"NAMING"|...). So the
    # gate is: if role is set AND it's not CHAT, block.
    if os.getenv("AIOS_DEMO_LLM_CHAT_ONLY", "").lower() in ("1", "true", "yes"):
        if role and role.upper() != "CHAT":
            return (
                "[demo mode — only chat is live]\n\n"
                f"Background role '{role}' is disabled in the public demo. "
                "Only the user-facing chat is wired to a real LLM here. "
                "Run AI_OS locally to enable the full subconscious:\n"
                "  https://github.com/allee-ai/AI_OS"
            )
    # ──────────────────────────────────────────────────────────────────

    # Apply per-role overrides when caller didn't pin provider/model.
    if role and (provider is None or model is None):
        try:
            from agent.services.role_model import resolve_role
            cfg = resolve_role(role)
            if provider is None:
                provider = cfg.provider
            if model is None:
                model = cfg.model
        except Exception:
            pass

    # Resolve provider
    if provider == "aggregate":
        p = _next_aggregate_provider()
    elif provider:
        p = get_provider(provider)
    else:
        # Use env default
        env_provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama").lower()
        p = get_provider(env_provider)

    # Cross-provider rate gate: skip if cooling down. CHAT bypasses the
    # gate (user is interacting; let it fail loudly). Background roles
    # respect the gate to avoid worsening the cooldown.
    try:
        from agent.services import rate_gate as _rg
        is_chat = (role or "").upper() == "CHAT"
        if not is_chat:
            skip, reason = _rg.should_skip(p.name)
            if skip:
                raise RuntimeError(
                    f"rate_gate:{reason} — provider {p.name} is cooling down"
                )
    except RuntimeError:
        raise
    except Exception:
        pass  # rate_gate unavailable — fall through

    import time as _time
    _t0 = _time.monotonic()
    try:
        out = p.generate(messages, model=model, temperature=temperature, max_tokens=max_tokens)
    except BaseException as _err:
        try:
            from agent.services import rate_gate as _rg
            if _rg.is_rate_limit_error(_err):
                _rg.record_429(p.name, str(_err))
            else:
                _rg.record_other_error(p.name)
        except Exception:
            pass
        raise
    try:
        from agent.services import rate_gate as _rg
        _rg.record_success(p.name, duration_seconds=_time.monotonic() - _t0)
    except Exception:
        pass
    return out
