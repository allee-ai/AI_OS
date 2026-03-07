"""
Custom Chain-of-Thought Loops
==============================
User-defined loops with iterative reasoning.
"""

import re
import ast
from typing import Optional, Dict, Any, List

from .base import BackgroundLoop, LoopConfig


# Valid sources for custom loops
CUSTOM_LOOP_SOURCES = [
    "convos",        # Conversation turns
    "feeds",         # Feed items
    "temp_memory",   # Pending facts
    "identity",      # Identity thread facts
    "philosophy",    # Philosophy thread facts
    "log",           # Log events
    "workspace",     # Workspace files
]

# Valid targets for custom loop output
CUSTOM_LOOP_TARGETS = [
    "temp_memory",   # Store as temp facts for review
    "log",           # Write to log thread
]


def _ensure_custom_loops_table() -> None:
    """Create custom_loops table if it doesn't exist."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_loops (
                    name TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT 'temp_memory',
                    interval_seconds REAL NOT NULL DEFAULT 300,
                    model TEXT,
                    prompt TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    max_iterations INTEGER NOT NULL DEFAULT 1,
                    max_tokens_per_iter INTEGER NOT NULL DEFAULT 2048,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Migrate: add columns if table pre-dates this version
            try:
                conn.execute("ALTER TABLE custom_loops ADD COLUMN max_iterations INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE custom_loops ADD COLUMN max_tokens_per_iter INTEGER NOT NULL DEFAULT 2048")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        print(f"[CustomLoop] Failed to create table: {e}")


def save_custom_loop_config(
    name: str,
    source: str,
    target: str,
    interval: float,
    model: Optional[str],
    prompt: str,
    enabled: bool = True,
    max_iterations: int = 1,
    max_tokens_per_iter: int = 2048,
) -> Dict[str, Any]:
    """Save or update a custom loop config in the database."""
    _ensure_custom_loops_table()
    
    if source not in CUSTOM_LOOP_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of: {CUSTOM_LOOP_SOURCES}")
    if target not in CUSTOM_LOOP_TARGETS:
        raise ValueError(f"Invalid target '{target}'. Must be one of: {CUSTOM_LOOP_TARGETS}")
    if interval < 5:
        raise ValueError("Interval must be >= 5 seconds")
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    if not name.strip():
        raise ValueError("Name cannot be empty")
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    if max_iterations > 20:
        raise ValueError("max_iterations must be <= 20")
    if max_tokens_per_iter < 64:
        raise ValueError("max_tokens_per_iter must be >= 64")
    
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO custom_loops
                    (name, source, target, interval_seconds, model, prompt, enabled,
                     max_iterations, max_tokens_per_iter, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (name.strip(), source, target, interval, model, prompt.strip(),
                  int(enabled), max_iterations, max_tokens_per_iter))
            conn.commit()
        
        return {
            "name": name.strip(),
            "source": source,
            "target": target,
            "interval_seconds": interval,
            "model": model,
            "prompt": prompt.strip(),
            "enabled": enabled,
            "max_iterations": max_iterations,
            "max_tokens_per_iter": max_tokens_per_iter,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to save custom loop: {e}")


def get_custom_loop_configs() -> List[Dict[str, Any]]:
    """Get all custom loop configs from the database."""
    _ensure_custom_loops_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name, source, target, interval_seconds, model, prompt,
                       enabled, max_iterations, max_tokens_per_iter, created_at, updated_at
                FROM custom_loops
            """)
            rows = cur.fetchall()
            return [
                {
                    "name": r[0], "source": r[1], "target": r[2],
                    "interval_seconds": r[3], "model": r[4], "prompt": r[5],
                    "enabled": bool(r[6]),
                    "max_iterations": r[7] if r[7] else 1,
                    "max_tokens_per_iter": r[8] if r[8] else 2048,
                    "created_at": r[9], "updated_at": r[10],
                }
                for r in rows
            ]
    except Exception:
        return []


def get_custom_loop_config(name: str) -> Optional[Dict[str, Any]]:
    """Get a single custom loop config by name."""
    configs = get_custom_loop_configs()
    for c in configs:
        if c["name"] == name:
            return c
    return None


def delete_custom_loop_config(name: str) -> bool:
    """Delete a custom loop config from the database."""
    _ensure_custom_loops_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM custom_loops WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


class CustomLoop(BackgroundLoop):
    """
    User-defined chain-of-thought loop with iterative reasoning.
    
    Reads from a source, passes through an LLM with a custom prompt,
    and writes results to a target.
    
    When max_iterations > 1, each iteration receives the previous iteration's
    output as additional context, building a chain of thought.
    """
    
    def __init__(
        self,
        name: str,
        source: str,
        target: str = "temp_memory",
        interval: float = 300.0,
        model: Optional[str] = None,
        prompt: str = "",
        enabled: bool = True,
        max_iterations: int = 1,
        max_tokens_per_iter: int = 2048,
    ):
        config = LoopConfig(
            interval_seconds=interval,
            name=name,
            enabled=enabled,
        )
        super().__init__(config, self._run_chain)
        self.source = source
        self.target = target
        self._model = model
        self.prompt = prompt
        self.max_iterations = max(1, min(max_iterations, 20))
        self.max_tokens_per_iter = max(64, max_tokens_per_iter)
        self._last_iteration_count = 0
        self._last_token_estimate = 0
    
    @property
    def model(self) -> str:
        import os
        if self._model:
            return self._model
        return os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    
    @model.setter
    def model(self, value: str) -> None:
        self._model = value
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["source"] = self.source
        base["target"] = self.target
        base["model"] = self.model
        base["prompt_preview"] = self.prompt[:80] + ("..." if len(self.prompt) > 80 else "")
        base["is_custom"] = True
        base["max_iterations"] = self.max_iterations
        base["max_tokens_per_iter"] = self.max_tokens_per_iter
        base["last_iteration_count"] = self._last_iteration_count
        base["last_token_estimate"] = self._last_token_estimate
        return base
    
    def to_config_dict(self) -> Dict[str, Any]:
        """Serialize this loop's configuration for API responses."""
        return {
            "name": self.config.name,
            "source": self.source,
            "target": self.target,
            "interval_seconds": self.config.interval_seconds,
            "model": self._model,
            "prompt": self.prompt,
            "enabled": self.config.enabled,
            "max_iterations": self.max_iterations,
            "max_tokens_per_iter": self.max_tokens_per_iter,
        }
    
    def _read_source(self) -> List[str]:
        """Read content from the configured source."""
        items = []
        try:
            if self.source == "convos":
                from data.db import get_connection
                from contextlib import closing
                with closing(get_connection(readonly=True)) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT user_message, assistant_message
                        FROM convo_turns
                        ORDER BY id DESC LIMIT 10
                    """)
                    for row in cur.fetchall():
                        text = f"User: {row[0]}"
                        if row[1]:
                            text += f"\nAssistant: {row[1]}"
                        items.append(text)
            
            elif self.source == "feeds":
                from data.db import get_connection
                from contextlib import closing
                with closing(get_connection(readonly=True)) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT title, content FROM feed_items
                        ORDER BY created_at DESC LIMIT 10
                    """)
                    for row in cur.fetchall():
                        items.append(f"{row[0]}: {row[1][:200]}" if row[1] else row[0])
            
            elif self.source == "temp_memory":
                from agent.subconscious.temp_memory import get_all_pending
                for fact in get_all_pending()[:20]:
                    items.append(f"[{fact.status}] {fact.text}")
            
            elif self.source == "identity":
                from agent.threads.identity.schema import pull_profile_facts
                facts = pull_profile_facts(limit=20)
                for f in facts:
                    items.append(f"{f.get('key', '')}: {f.get('l1_value', '')}")
            
            elif self.source == "philosophy":
                from agent.threads.philosophy.schema import pull_philosophy_profile_facts
                facts = pull_philosophy_profile_facts(limit=20)
                for f in facts:
                    items.append(f"{f.get('key', '')}: {f.get('l1_value', '')}")
            
            elif self.source == "log":
                from agent.threads.log import get_recent_events
                events = get_recent_events(limit=20)
                for e in events:
                    items.append(f"[{e.get('timestamp', '')}] {e.get('event_type', '')}: {e.get('description', '')}")
            
            elif self.source == "workspace":
                from workspace.schema import list_workspace_files
                files = list_workspace_files()
                for f in files[:10]:
                    items.append(f"{f.get('path', '')}: {f.get('description', '')}")
        
        except Exception as e:
            print(f"[CustomLoop:{self.config.name}] Source read error: {e}")
        
        return items
    
    def _write_target(self, results: List[Dict[str, Any]]) -> int:
        """Write processed results to the configured target. Returns count written."""
        written = 0
        try:
            if self.target == "temp_memory":
                from agent.subconscious.temp_memory import add_fact
                for result in results:
                    add_fact(
                        session_id=f"custom:{self.config.name}",
                        text=result.get("text", ""),
                        source=f"loop:{self.config.name}",
                        metadata={
                            "hier_key": result.get("key", f"custom.{self.config.name}"),
                            "confidence": result.get("confidence", 0.5),
                        }
                    )
                    written += 1
            
            elif self.target == "log":
                from agent.threads.log import log_event
                for result in results:
                    log_event(
                        f"custom:{self.config.name}",
                        "custom_loop",
                        result.get("text", ""),
                    )
                    written += 1
        
        except Exception as e:
            print(f"[CustomLoop:{self.config.name}] Target write error: {e}")
        
        return written
    
    def _run_chain(self) -> None:
        """Execute iterative chain-of-thought: read source -> LLM x N -> write target."""
        source_items = self._read_source()
        if not source_items:
            return
        
        source_text = "\n---\n".join(source_items)
        total_tokens = 0
        chain_history: List[str] = []
        all_results: List[Dict[str, Any]] = []
        
        for iteration in range(self.max_iterations):
            if iteration == 0:
                full_prompt = f"""{self.prompt}

SOURCE DATA:
\"\"\"
{source_text}
\"\"\"

{f"[Iteration {iteration + 1} of {self.max_iterations}]" if self.max_iterations > 1 else ""}

Output a Python list of dicts with "key" and "text" fields.
If nothing worth noting, output: []

Python list:"""
            else:
                chain_context = "\n\n".join(
                    f"--- Iteration {i+1} output ---\n{h}" for i, h in enumerate(chain_history)
                )
                full_prompt = f"""{self.prompt}

SOURCE DATA:
\"\"\"
{source_text}
\"\"\"

PREVIOUS ITERATIONS (build on these, go deeper, refine, or synthesize):
\"\"\"
{chain_context}
\"\"\"

[Iteration {iteration + 1} of {self.max_iterations}] — Deepen your analysis. Find what you missed. Refine or challenge previous outputs.

Output a Python list of dicts with "key" and "text" fields.
If nothing new worth adding, output: []

Python list:"""
            
            prompt_tokens = len(full_prompt) // 4
            if total_tokens + prompt_tokens > self.max_tokens_per_iter:
                break
            
            try:
                raw = self._call_model_chain(full_prompt)
                
                response_tokens = len(raw) // 4
                total_tokens += prompt_tokens + response_tokens
                
                results = self._parse_results(raw)
                
                chain_history.append(raw)
                all_results.extend(results)
                
                if not results and iteration > 0:
                    break
                    
            except Exception as e:
                print(f"[CustomLoop:{self.config.name}] Iteration {iteration + 1} error: {e}")
                break
        
        self._last_iteration_count = len(chain_history)
        self._last_token_estimate = total_tokens
        
        if all_results:
            written = self._write_target(all_results)
            try:
                from agent.threads.log import log_event
                log_event(
                    f"custom:{self.config.name}",
                    "custom_loop",
                    f"Processed {len(source_items)} items in {len(chain_history)} iterations (~{total_tokens} tokens), wrote {written} results"
                )
            except Exception:
                pass
    
    def _call_model_chain(self, prompt: str) -> str:
        """Call the LLM for a chain iteration."""
        import os
        provider = os.getenv("AIOS_EXTRACT_PROVIDER", os.getenv("AIOS_MODEL_PROVIDER", "ollama"))
        
        if provider == "openai":
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            api_key = os.getenv("OPENAI_API_KEY", "")
            import requests
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        
        # Default: Ollama
        import ollama
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}
        )
        return response["message"]["content"].strip()
    
    def _parse_results(self, raw: str) -> List[Dict[str, Any]]:
        """Parse LLM output into list of result dicts."""
        if not raw:
            return []
        
        raw = raw.strip()
        
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        list_start = raw.find('[')
        if list_start < 0:
            return []
        raw = raw[list_start:]
        
        bracket_count = 0
        end_pos = 0
        for i, char in enumerate(raw):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i + 1
                    break
        if end_pos > 0:
            raw = raw[:end_pos]
        
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict) and r.get("text")]
        except (ValueError, SyntaxError):
            pass
        
        try:
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict) and r.get("text")]
        except (ValueError, SyntaxError):
            pass
        
        return []
