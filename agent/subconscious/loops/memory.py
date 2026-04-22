"""
Memory Loop
===========
Periodically extracts facts from recent conversations.
"""

import re
import ast
from typing import Optional, Dict, Any

from .base import BackgroundLoop, LoopConfig


# ── Default prompts (editable at runtime) ───────────────────

DEFAULT_PROMPTS = {
    "extract": """Extract ONLY high-value personal facts about the user from this conversation.

RULES:
- Only extract facts a personal assistant would genuinely need to remember
- Good facts: name, occupation, hobbies, preferences, relationships, goals, location, tools they use
- BAD facts (DO NOT EXTRACT): error messages, API paths, code snippets, technical debug info,
  file names, git operations, installation steps, HTTP status codes, stack traces
- Each fact needs a "key" (1-2 word label) and "text" (the actual fact)
- If the user mentions another person, set "profile" to that person's name (lowercase)
- If the fact is about the user themselves, set "profile" to "primary_user"
- Maximum 3 facts per conversation — only the most important ones

ONLY output a Python list. No explanation.

Example:
[{"key": "hobby", "text": "User enjoys rock climbing", "profile": "primary_user"}, {"key": "partner", "text": "User's partner is named Ike", "profile": "primary_user"}, {"key": "occupation", "text": "Ike works as a veterinarian", "profile": "ike"}]

If nothing worth remembering, output: []""",
}


class MemoryLoop(BackgroundLoop):
    """
    Periodically extracts facts from recent conversations.
    
    Processes new conversation turns and extracts identity/philosophy facts
    into temp_memory for user review before consolidation.
    """
    
    def __init__(self, interval: float = 60.0, model: str = None):  # 1 minute
        config = LoopConfig(
            interval_seconds=interval,
            name="memory",
            enabled=True
        )
        super().__init__(config, self._extract)
        self._last_processed_turn_id: Optional[int] = self._load_last_turn_id()
        self._model = model  # None = use env/default
        self._prompts: Dict[str, str] = {k: v for k, v in DEFAULT_PROMPTS.items()}
    
    @property
    def model(self) -> str:
        """Get the model used for fact extraction."""
        if self._model:
            return self._model
        from agent.services.role_model import resolve_role
        return resolve_role("MEMORY").model
    
    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    @property
    def provider(self) -> str:
        """Get the provider for the extraction model (ollama | openai)."""
        from agent.services.role_model import resolve_role
        return resolve_role("MEMORY").provider

    def _call_model(self, messages: list, temperature: float = 0.1) -> str:
        """Route extraction call to the configured provider."""
        model = self.model
        prov = self.provider

        if prov == "openai":
            return self._call_openai(model, messages, temperature)

        # Default: ollama
        return self._call_ollama_extract(model, messages, temperature)

    def _call_ollama_extract(self, model: str, messages: list, temperature: float) -> str:
        from .base import acquire_ollama_gate, release_ollama_gate, is_llm_enabled
        if not is_llm_enabled():
            return ""
        import ollama
        if not acquire_ollama_gate():
            raise RuntimeError("Ollama gate timeout")
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature},
            )
            return response['message']['content'].strip()
        finally:
            release_ollama_gate()

    def _call_openai(self, model: str, messages: list, temperature: float) -> str:
        """Call an OpenAI-compatible endpoint for extraction."""
        import os, json, urllib.request
        from agent.services.role_model import resolve_role

        cfg = resolve_role("MEMORY")
        api_key = cfg.api_key or os.getenv("OPENAI_API_KEY", "")
        base_url = (cfg.endpoint or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")

        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
    
    def _load_last_turn_id(self) -> Optional[int]:
        """Load _last_processed_turn_id from DB so it survives restart."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_loop_state (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                cur.execute(
                    "SELECT value FROM memory_loop_state WHERE key = 'last_processed_turn_id'"
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
        except Exception:
            return None
    
    def _save_last_turn_id(self, turn_id: int) -> None:
        """Persist _last_processed_turn_id to DB."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_loop_state (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                conn.execute(
                    "INSERT OR REPLACE INTO memory_loop_state (key, value) VALUES (?, ?)",
                    ("last_processed_turn_id", str(turn_id))
                )
                conn.commit()
        except Exception:
            pass
    
    def get_unprocessed_count(self) -> int:
        """Return the number of conversation turns not yet read by the memory loop."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                if self._last_processed_turn_id:
                    cur.execute(
                        "SELECT COUNT(*) FROM convo_turns WHERE id > ?",
                        (self._last_processed_turn_id,)
                    )
                else:
                    cur.execute("SELECT COUNT(*) FROM convo_turns")
                return cur.fetchone()[0]
        except Exception:
            return 0
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["model"] = self.model
        base["provider"] = self.provider
        base["unprocessed_turns"] = self.get_unprocessed_count()
        base["last_processed_turn_id"] = self._last_processed_turn_id
        base["prompts"] = {k: v for k, v in getattr(self, '_prompts', DEFAULT_PROMPTS).items()}
        return base
    
    def _extract(self) -> str:
        """Extract facts from recent conversation turns. Returns summary."""
        import json
        import os
        from contextlib import closing
        
        # 1. Get recent conversation turns since last_processed_turn_id
        try:
            from data.db import get_connection
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                
                if self._last_processed_turn_id:
                    cur.execute("""
                        SELECT ct.id, ct.user_message, ct.assistant_message, c.session_id
                        FROM convo_turns ct
                        JOIN convos c ON ct.convo_id = c.id
                        WHERE ct.id > ?
                        ORDER BY ct.id ASC
                        LIMIT 10
                    """, (self._last_processed_turn_id,))
                else:
                    cur.execute("""
                        SELECT ct.id, ct.user_message, ct.assistant_message, c.session_id
                        FROM convo_turns ct
                        JOIN convos c ON ct.convo_id = c.id
                        ORDER BY ct.id DESC
                        LIMIT 10
                    """)
                
                turns = cur.fetchall()
            
            if not turns:
                return "No new turns to process"
            
        except Exception as e:
            print(f"[MemoryLoop] DB error: {e}")
            return f"DB error: {e}"
        
        # 2. Extract facts from each turn
        total_facts = 0
        fact_texts = []
        for turn in turns:
            turn_id, user_msg, assistant_msg, session_id = turn
            
            if not user_msg:
                continue
            
            convo_text = f"User: {user_msg}"
            if assistant_msg:
                convo_text += f"\nAssistant: {assistant_msg}"
            
            facts = self._extract_facts_from_text(convo_text, session_id)
            
            # 3. Store in temp_memory
            if facts:
                try:
                    from agent.subconscious.temp_memory import add_fact
                    for fact in facts:
                        add_fact(
                            session_id=session_id,
                            text=fact.get("text", ""),
                            source="conversation",
                            metadata={
                                "hier_key": fact.get("key"),
                                "category": fact.get("category", "general"),
                                "confidence": fact.get("confidence", 0.5),
                                "profile": fact.get("profile", "primary_user"),
                                "turn_id": turn_id,
                            }
                        )
                        total_facts += 1
                        fact_texts.append(fact.get("text", "")[:80])
                except Exception as e:
                    print(f"[MemoryLoop] Failed to store fact: {e}")
            
            # 4. Update last_processed_turn_id
            self._last_processed_turn_id = turn_id
            self._save_last_turn_id(turn_id)
        
        # Log extraction run
        summary = f"Processed {len(turns)} turns, extracted {total_facts} facts"
        if fact_texts:
            summary += "\n" + "\n".join(f"  - {t}" for t in fact_texts[:10])
        try:
            from agent.threads.log import log_event
            log_event(
                "system:memory_extract",
                "memory_loop",
                f"Processed {len(turns)} turns, extracted {total_facts} facts"
            )
        except:
            pass
        return summary
    
    def _extract_facts_from_text(self, text: str, session_id: str) -> list:
        """
        Extract facts from conversation text using LLM.
        Returns list of dicts: [{"key": "user.likes.coffee", "text": "User enjoys coffee"}]
        """
        import os
        
        if len(text) < 30:
            return []
        
        # Build STATE preamble when context_aware is enabled
        state_block = self._get_state("extract facts from conversation")
        state_preamble = ""
        if state_block:
            state_preamble = f"""You have access to the following consciousness context about yourself and the user:

{state_block}

Use this context to extract MORE RELEVANT facts — avoid duplicating what you already know,
and pay attention to the user's identity/interests when deciding what's worth remembering.

"""
        
        prompt = state_preamble + getattr(self, '_prompts', DEFAULT_PROMPTS).get("extract", DEFAULT_PROMPTS["extract"]) + '''

Conversation:
"""
''' + text + '''
"""

Python list:'''

        try:
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    raw_output = self._call_model(
                        [{"role": "user", "content": prompt}],
                        temperature=0.1,
                    )
                    
                    facts = self._parse_python_list(raw_output)
                    
                    if facts is not None:
                        validated = [f for f in facts if self._validate_fact(f)]
                        return validated
                    
                    if attempt < max_attempts - 1:
                        prompt = f'''Your previous output was not a valid Python list:
{raw_output}

Try again. Output ONLY a Python list like:
[{{"key": "favorite_food", "text": "fact"}}]

Or if no facts: []'''
                        
                except Exception as e:
                    print(f"[MemoryLoop] Attempt {attempt+1} failed: {e}")
                    continue
            
            return []
            
        except Exception as e:
            print(f"[MemoryLoop] Extraction error: {e}")
            return []
    
    def _parse_python_list(self, raw: str) -> list:
        """Parse LLM output as Python list using ast.literal_eval."""
        if not raw:
            return None
        
        raw = raw.strip()
        
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        list_start = raw.find('[')
        if list_start > 0:
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
                return result
        except (ValueError, SyntaxError):
            pass
        
        try:
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return result
        except (ValueError, SyntaxError):
            pass
        
        return None
    
    def _validate_fact(self, fact: dict) -> bool:
        """Validate a fact dict before storing — filters noise aggressively."""
        if not isinstance(fact, dict):
            return False
        if not fact.get("text") or not fact.get("key"):
            return False
        
        text = fact.get("text", "")
        key = fact.get("key", "")
        
        if len(text) < 10 or len(text) > 500:
            return False
        
        if not isinstance(key, str):
            return False
        
        text_lower = text.lower()
        
        # Reject technical noise — these are NOT personal facts
        noise_patterns = [
            r'^[\[\]\{\}]+$',
            r'^["\s]+$',
            r'^\[.*\]$',
            r'^(ok|yes|no|hi|hello|thanks)\.?$',
            r'(500 internal server error|404 not found|403 forbidden)',
            r'(GET|POST|PUT|DELETE|PATCH)\s+/api/',
            r'(\.gitignore|\.env|node_modules|__pycache__|\.pyc)',
            r'(traceback|stacktrace|errno|exception|error code)',
            r'(pip install|npm install|brew install|apt-get)',
            r'(import\s+\w+|from\s+\w+\s+import)',
            r'(localhost:\d+|127\.0\.0\.1|0\.0\.0\.0)',
            r'(\.js|\.ts|\.py|\.json|\.yaml|\.yml|\.md)$',
            r'(commit\s+[a-f0-9]{7,}|merge\s+branch)',
        ]
        for pattern in noise_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # Reject if it looks like code (has too many special chars)
        special_chars = sum(1 for c in text if c in '{}[]()=><;|&@#$%^*~`')
        if special_chars > len(text) * 0.15:
            return False
        
        if "." in key:
            fact["key"] = key.rsplit(".", 1)[-1]
        
        if not fact["key"].strip():
            return False
        
        return True
