"""
Demo Audit Loop
================
Periodically audits frontend/public/demo-data.json for completeness,
shape correctness, and data quality using the Kimi K2 model.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BackgroundLoop, LoopConfig

DEFAULT_PROMPTS = {
    "audit": """You are auditing demo mock data for a React frontend.
Each line below is an API endpoint key followed by the first 300 chars of its JSON response.

Audit checklist:
1. Are any endpoint responses clearly empty or placeholder where real data is expected?
2. Do any responses have obviously wrong shapes (e.g. object where array expected)?
3. Is any PII present (real names, emails, addresses, API keys)?
4. Are there endpoints that a typical dashboard would need but are missing?
5. Data quality: any null fields that should be populated, or unrealistic values?

Output a concise JSON array of issue objects:
[{"endpoint": "...", "severity": "high|medium|low", "issue": "..."}]
If everything looks good, output: []""",
}


# Resolve the demo-data path relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEMO_DATA_PATH = _PROJECT_ROOT / "frontend" / "public" / "demo-data.json"


class DemoAuditLoop(BackgroundLoop):
    """
    Reads demo-data.json explicitly, sends batches of endpoint
    responses to Kimi K2 for structural/quality audit, and logs
    findings via the log thread.
    """

    def __init__(
        self,
        interval: float = 900.0,
        model: str = "kimi-k2:1t-cloud",
        enabled: bool = True,
    ):
        config = LoopConfig(
            interval_seconds=interval,
            name="demo_audit",
            enabled=enabled,
        )
        super().__init__(config, self._audit_demo)
        self._model = model
        self._prompts: Dict[str, str] = {k: v for k, v in DEFAULT_PROMPTS.items()}
        self._last_issues: list[str] = []

    # ------------------------------------------------------------------
    # core task
    # ------------------------------------------------------------------

    def _audit_demo(self) -> str:
        if not _DEMO_DATA_PATH.exists():
            self._log("demo-data.json not found – skipping audit")
            return "demo-data.json not found"

        data: Dict[str, Any] = json.loads(_DEMO_DATA_PATH.read_text())
        if not data:
            self._log("demo-data.json is empty")
            return "demo-data.json is empty"

        # Build a compact summary (endpoint -> first 300 chars of JSON)
        summary_lines: list[str] = []
        for key in sorted(data.keys()):
            snippet = json.dumps(data[key])[:300]
            summary_lines.append(f"{key}  →  {snippet}")

        summary_text = "\n".join(summary_lines)

        audit_instruction = self._prompts.get("audit", DEFAULT_PROMPTS["audit"])
        prompt = f"""{audit_instruction}

DEMO DATA ({len(data)} endpoints):
\"\"\"
{summary_text}
\"\"\"
"""

        try:
            raw = self._call_model(prompt)
            issues = self._parse_issues(raw)
            self._last_issues = [
                f"[{i.get('severity','?').upper()}] {i.get('endpoint','?')}: {i.get('issue','')}"
                for i in issues
            ]

            if issues:
                self._log(
                    f"Found {len(issues)} issue(s) in demo-data.json:\n"
                    + "\n".join(self._last_issues)
                )
                self._write_facts(issues)
                self._notify(
                    f"Demo audit found {len(issues)} issue(s) in demo-data.json",
                    priority="high" if any(
                        i.get("severity") == "high" for i in issues
                    ) else "normal",
                )
                return f"Found {len(issues)} issues:\n" + "\n".join(self._last_issues)
            else:
                self._log("Demo data audit passed – no issues found")
                return "Demo data audit passed – no issues found"

        except Exception as exc:
            self._log(f"Audit model call failed: {exc}")
            return f"Audit model call failed: {exc}"

    # ------------------------------------------------------------------
    # model helper  (mirrors CustomLoop._call_model_chain pattern)
    # ------------------------------------------------------------------

    def _call_model(self, prompt: str) -> str:
        from agent.services.role_model import resolve_role
        cfg = resolve_role("DEMO_AUDIT")
        provider = cfg.provider

        if provider == "openai":
            base_url = cfg.endpoint or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            api_key = cfg.api_key or os.getenv("OPENAI_API_KEY", "")
            import requests

            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

        # Default: Ollama
        from .base import is_llm_enabled
        if not is_llm_enabled():
            return ""
        import ollama

        response = ollama.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        return response["message"]["content"].strip()

    # ------------------------------------------------------------------
    # parsing + logging helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_issues(raw: str) -> list[dict]:
        import re, ast

        raw = raw.strip()
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if code_match:
            raw = code_match.group(1).strip()

        start = raw.find("[")
        if start < 0:
            return []
        raw = raw[start:]

        depth, end = 0, 0
        for i, ch in enumerate(raw):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            raw = raw[:end]

        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            fixed = raw.replace("true", "True").replace("false", "False").replace("null", "None")
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
        except (ValueError, SyntaxError):
            pass

        return []

    def _log(self, message: str) -> None:
        try:
            from agent.threads.log import log_event
            log_event("system", message, source="demo_audit")
        except Exception:
            print(f"[DemoAuditLoop] {message}")

    def _write_facts(self, issues: list[dict]) -> None:
        """Store each issue as a temp fact visible in the loop detail panel."""
        try:
            from agent.subconscious.temp_memory.store import add_fact
            for issue in issues:
                sev = issue.get("severity", "medium").upper()
                endpoint = issue.get("endpoint", "?")
                text = issue.get("issue", "")
                add_fact(
                    session_id="demo_audit",
                    text=f"[{sev}] {endpoint}: {text}",
                    source="loop:demo_audit",
                    metadata={
                        "hier_key": f"demo_audit.{endpoint}",
                        "confidence": {"high": 0.9, "medium": 0.6, "low": 0.3}.get(
                            issue.get("severity", "medium"), 0.5
                        ),
                    },
                )
        except Exception as exc:
            print(f"[DemoAuditLoop] Failed to write facts: {exc}")

    @staticmethod
    def _notify(message: str, priority: str = "normal") -> None:
        """Post a notification visible in the Subconscious Notifications panel."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS notifications ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "type TEXT NOT NULL DEFAULT 'alert',"
                    "message TEXT NOT NULL,"
                    "priority TEXT NOT NULL DEFAULT 'normal',"
                    "context TEXT NOT NULL DEFAULT '{}',"
                    "read INTEGER NOT NULL DEFAULT 0,"
                    "dismissed INTEGER NOT NULL DEFAULT 0,"
                    "response TEXT,"
                    "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
                    ")"
                )
                conn.execute(
                    "INSERT INTO notifications (type, message, priority) VALUES (?, ?, ?)",
                    ("alert", message, priority),
                )
                conn.commit()
        except Exception as exc:
            print(f"[DemoAuditLoop] Failed to create notification: {exc}")
        # Mirror warn+ severity into shared meta bus so the model hears it.
        try:
            if (priority or "").lower() in ("high", "urgent", "warn", "warning"):
                from agent.subconscious.meta_mirror import mirror_to_meta
                w = 0.85 if (priority or "").lower() in ("urgent", "high") else 0.7
                mirror_to_meta(
                    kind_hint="alert",
                    content=message,
                    weight=w,
                    confidence=0.7,
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # stats override
    # ------------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["model"] = self._model
        base["demo_data_path"] = str(_DEMO_DATA_PATH)
        base["last_issues"] = self._last_issues
        base["prompts"] = {k: v for k, v in getattr(self, '_prompts', DEFAULT_PROMPTS).items()}
        return base
