"""
Thought Loop — Proactive Agent Reasoning
=========================================
The agent thinks without being asked, surfacing insights, alerts, and suggestions.
"""

import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .base import BackgroundLoop, LoopConfig


# ─────────────────────────────────────────────────────────────
# Thought Log DB helpers
# ─────────────────────────────────────────────────────────────

def _ensure_thought_log_table() -> None:
    """Create thought_log table if it doesn't exist."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS thought_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thought TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'insight',
                    priority TEXT NOT NULL DEFAULT 'low',
                    source_summary TEXT,
                    acted_on INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[ThoughtLoop] Failed to create table: {e}")


def get_thought_log(limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get recent thoughts from the thought log."""
    _ensure_thought_log_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            if category:
                cur.execute(
                    "SELECT id, thought, category, priority, source_summary, acted_on, created_at "
                    "FROM thought_log WHERE category = ? ORDER BY id DESC LIMIT ?",
                    (category, limit)
                )
            else:
                cur.execute(
                    "SELECT id, thought, category, priority, source_summary, acted_on, created_at "
                    "FROM thought_log ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [
                {
                    "id": r[0], "thought": r[1], "category": r[2],
                    "priority": r[3], "source_summary": r[4],
                    "acted_on": bool(r[5]), "created_at": r[6],
                }
                for r in cur.fetchall()
            ]
    except Exception:
        return []


def save_thought(thought: str, category: str = "insight", priority: str = "low",
                 source_summary: str = "") -> int:
    """Save a thought to the log. Returns the thought ID."""
    _ensure_thought_log_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO thought_log (thought, category, priority, source_summary) VALUES (?, ?, ?, ?)",
                (thought, category, priority, source_summary)
            )
            conn.commit()
            return cur.lastrowid or 0
    except Exception as e:
        print(f"[ThoughtLoop] Failed to save thought: {e}")
        return 0


def mark_thought_acted(thought_id: int) -> bool:
    """Mark a thought as acted upon."""
    _ensure_thought_log_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("UPDATE thought_log SET acted_on = 1 WHERE id = ?", (thought_id,))
            conn.commit()
            return True
    except Exception:
        return False


THOUGHT_CATEGORIES = ["insight", "alert", "reminder", "suggestion", "question"]
THOUGHT_PRIORITIES = ["low", "medium", "high", "urgent"]


# ── Default prompts (editable at runtime) ───────────────────

DEFAULT_PROMPTS = {
    "think": """You are the proactive thinking module of a personal AI assistant.
Your job: review the current state below and surface anything the user should know,
any connections worth noting, or actions worth suggesting.

Categories (pick one per thought):
- insight: a pattern, connection, or synthesis you noticed
- alert: something time-sensitive or important the user should see
- reminder: something the user might have forgotten or should follow up on
- suggestion: a helpful action the user could take
- question: something you'd like to ask the user to improve your understanding

Priority levels: low, medium, high, urgent

If there's nothing genuinely worth surfacing, output exactly: []

Otherwise output a Python list of dicts. Each dict has:
- "thought": the insight text (1-2 sentences, conversational)
- "category": one of [insight, alert, reminder, suggestion, question]
- "priority": one of [low, medium, high, urgent]

Be selective — only surface things that genuinely matter. Quality over quantity.
Maximum 3 thoughts per cycle.""",
}


# ─────────────────────────────────────────────────────────────
# ThoughtLoop class
# ─────────────────────────────────────────────────────────────

class ThoughtLoop(BackgroundLoop):
    """
    Proactive reasoning loop — the agent thinks without being asked.
    
    Gathers context from multiple sources (events, facts, feeds, conversations),
    passes it through the LLM with a metacognitive prompt, and logs insights,
    alerts, and suggestions to the thought_log table.
    
    Thoughts are broadcast via WebSocket for real-time frontend notifications.
    """
    
    def __init__(self, interval: float = 120.0, model: Optional[str] = None, enabled: bool = True):
        config = LoopConfig(
            interval_seconds=interval,
            name="thought",
            enabled=enabled,
        )
        super().__init__(config, self._think)
        self._model = model
        self._thought_count = 0
        self._prompts: Dict[str, str] = {k: v for k, v in DEFAULT_PROMPTS.items()}
    
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
        base["model"] = self.model
        base["thought_count"] = self._thought_count
        base["prompts"] = {k: v for k, v in getattr(self, '_prompts', DEFAULT_PROMPTS).items()}
        return base
    
    def _gather_context(self) -> Dict[str, List[str]]:
        """Gather context from all available sources for proactive reasoning."""
        ctx: Dict[str, List[str]] = {}
        
        # Recent events
        try:
            from agent.threads.log import get_recent_events
            events = get_recent_events(limit=15)
            ctx["recent_events"] = [
                f"[{e.get('timestamp', '')}] {e.get('event_type', '')}: {e.get('description', '')}"
                for e in events
            ]
        except Exception:
            pass
        
        # Pending facts awaiting review
        try:
            from agent.subconscious.temp_memory import get_all_pending
            pending = get_all_pending()
            if pending:
                ctx["pending_facts"] = [
                    f"[{f.status}] {f.text}" for f in pending[:10]
                ]
        except Exception:
            pass
        
        # Recent conversation turns
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT user_message, assistant_message
                    FROM convo_turns ORDER BY id DESC LIMIT 5
                """)
                turns = []
                for row in cur.fetchall():
                    t = f"User: {row[0]}"
                    if row[1]:
                        t += f"\nAssistant: {row[1][:200]}"
                    turns.append(t)
                if turns:
                    ctx["recent_conversations"] = turns
        except Exception:
            pass
        
        # Feed events
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT event_type, description, timestamp
                    FROM unified_events
                    WHERE source LIKE 'feed:%'
                    ORDER BY id DESC LIMIT 10
                """)
                feed_events = [
                    f"[{r[2]}] {r[0]}: {r[1]}" for r in cur.fetchall()
                ]
                if feed_events:
                    ctx["feed_activity"] = feed_events
        except Exception:
            pass
        
        # Identity highlights
        try:
            from agent.threads.identity.schema import pull_profile_facts
            facts = pull_profile_facts(profile_id="primary_user", limit=8)
            if facts:
                ctx["user_profile"] = [
                    f"{f.get('key', '')}: {f.get('l1_value', '')}" for f in facts if f.get('l1_value')
                ]
        except Exception:
            pass
        
        # Previous thoughts (avoid repetition)
        try:
            recent_thoughts = get_thought_log(limit=5)
            if recent_thoughts:
                ctx["previous_thoughts"] = [t["thought"] for t in recent_thoughts]
        except Exception:
            pass
        
        return ctx
    
    def _think(self) -> None:
        """Execute one proactive thinking cycle."""
        # When context_aware, use the full orchestrator STATE instead of ad-hoc context
        state_block = self._get_state("proactive thinking about the user")
        
        if state_block:
            # Full STATE path — the orchestrator already assembled identity,
            # philosophy, linking, log, workspace, etc.
            ctx_text = state_block
            total_items = len(state_block.splitlines())
        else:
            # Fallback: manual context gathering
            context = self._gather_context()
            total_items = sum(len(v) for v in context.values())
            if total_items < 2:
                return
            ctx_parts = []
            for source, items in context.items():
                ctx_parts.append(f"## {source.replace('_', ' ').title()}")
                ctx_parts.extend(items)
                ctx_parts.append("")
            ctx_text = "\n".join(ctx_parts)
        
        # Grab previous thoughts either way (needed for de-dup)
        try:
            previous_thoughts = [t["thought"] for t in get_thought_log(limit=5)]
        except Exception:
            previous_thoughts = []
        
        prompt = f"""{getattr(self, '_prompts', DEFAULT_PROMPTS).get("think", DEFAULT_PROMPTS["think"])}

CURRENT STATE:
\"\"\"
{ctx_text}
\"\"\"

PREVIOUS THOUGHTS (do NOT repeat these):
{json.dumps(previous_thoughts)}

Python list:"""
        
        try:
            response = self._call_model(prompt)
            results = self._parse_results(response)
            
            for result in results[:3]:
                thought_text = result.get("thought", "").strip()
                category = result.get("category", "insight")
                priority = result.get("priority", "low")
                
                if not thought_text:
                    continue
                if category not in THOUGHT_CATEGORIES:
                    category = "insight"
                if priority not in THOUGHT_PRIORITIES:
                    priority = "low"
                
                thought_id = save_thought(
                    thought=thought_text,
                    category=category,
                    priority=priority,
                    source_summary=f"{total_items} items from {len(context)} sources",
                )
                self._thought_count += 1
                
                if priority in ("high", "urgent"):
                    try:
                        from agent.subconscious.temp_memory import add_fact
                        add_fact(
                            session_id="thought_loop",
                            text=thought_text,
                            source="thought_loop",
                            metadata={
                                "category": category,
                                "priority": priority,
                                "thought_id": thought_id,
                            }
                        )
                    except Exception:
                        pass
                
                self._broadcast_thought(thought_id, thought_text, category, priority)
                
                try:
                    from agent.threads.log import log_event
                    log_event(
                        "system:thought",
                        "thought_loop",
                        f"[{priority}:{category}] {thought_text[:120]}"
                    )
                except Exception:
                    pass
        
        except Exception as e:
            print(f"[ThoughtLoop] Error: {e}")
    
    def _call_model(self, prompt: str) -> str:
        """Call the LLM for thinking."""
        import os
        provider = os.getenv("AIOS_EXTRACT_PROVIDER", os.getenv("AIOS_MODEL_PROVIDER", "ollama"))
        
        if provider == "openai":
            return self._call_openai(prompt)
        return self._call_ollama(prompt)
    
    def _call_ollama(self, prompt: str) -> str:
        import ollama
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3}
        )
        return response["message"]["content"].strip()
    
    def _call_openai(self, prompt: str) -> str:
        import os, requests
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("OPENAI_API_KEY", "")
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    
    def _broadcast_thought(self, thought_id: int, text: str, category: str, priority: str) -> None:
        """Broadcast a thought to connected WebSocket clients."""
        try:
            import asyncio
            from chat.api import websocket_manager
            
            message = {
                "type": "thought",
                "thought_id": thought_id,
                "text": text,
                "category": category,
                "priority": priority,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(websocket_manager.broadcast(message), loop)
                    return
            except RuntimeError:
                pass
            
            try:
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(websocket_manager.broadcast(message))
                new_loop.close()
            except Exception:
                pass
                
        except Exception:
            pass
    
    def _parse_results(self, raw: str) -> List[Dict[str, Any]]:
        """Parse LLM output into list of thought dicts."""
        import ast
        
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
                return [r for r in result if isinstance(r, dict) and r.get("thought")]
        except (ValueError, SyntaxError):
            pass
        
        try:
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict) and r.get("thought")]
        except (ValueError, SyntaxError):
            pass
        
        return []
