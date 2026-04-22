"""
Conversation Concept Extraction Loop
=====================================
Backfills the concept graph from imported and historical conversations.

Two extraction modes:
1. **Entity matching** (default, fast): matches text tokens against known
   fact keys, profile IDs, and tool names.  No LLM call required.
2. **LLM extraction** (opt-in via ``use_llm=True``): calls a model to
   discover NEW facts from the conversation text, stages them in
   ``temp_facts`` for review, invalidates the entity registry, then runs
   entity matching.  Each LLM call is also saved as a training example
   in ``finetune/auto_generated/concept_extractions.jsonl``.

After processing all pending conversations the loop runs consolidation
to promote heavily-reinforced SHORT links to LONG.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BackgroundLoop, LoopConfig


# DB key used to track which conversations have been processed
_PROGRESS_KEY = "convo_concepts_last_id"

# Where LLM extraction training examples are saved
_TRAINING_DIR = Path(__file__).resolve().parents[3] / "finetune" / "auto_generated"

# ── Extraction prompt ────────────────────────────────────────
_EXTRACT_SYSTEM = """You are a fact extraction engine for a personal AI memory system.
Given a conversation, extract concrete facts worth remembering as a JSON array.

Rules:
- Each fact is {"key": "<flat_name>", "text": "<human description>"}
- Keys are 1-3 words joined by underscore: favorite_language, project_name, deploy_target
- Only extract SPECIFIC, FACTUAL information — no opinions, no vague statements
- Prefer facts about: people, preferences, projects, tools, decisions, status, goals
- If the conversation is code-heavy with no personal facts, output: []
- Maximum 8 facts per conversation

Output ONLY a JSON array. No explanation."""


class ConvoConceptLoop(BackgroundLoop):
    """
    Processes un-extracted conversations into the concept graph.

    Supports two modes:
    - **Entity matching** (fast, deterministic): token-matches against known entities
    - **LLM extraction** (richer, slower): calls model to discover new facts,
      stages them, then links.  Each call generates training data.

    Set ``use_llm=True`` to enable the LLM path.
    """

    def __init__(
        self,
        interval: float = 300.0,
        enabled: bool = True,
        batch_size: int = 20,
        use_llm: bool = False,
    ):
        config = LoopConfig(
            interval_seconds=interval,
            name="convo_concepts",
            enabled=enabled,
        )
        super().__init__(config, self._process_batch)
        self.batch_size = batch_size
        self.use_llm = use_llm
        self._prompts: Dict[str, str] = {"extract": _EXTRACT_SYSTEM}
        self._total_processed = 0
        self._total_concepts = 0
        self._total_links = 0
        self._total_facts_extracted = 0

    @property
    def model(self) -> str:
        from agent.services.role_model import resolve_role
        return resolve_role("CONVO_CONCEPTS").model

    @property
    def provider(self) -> str:
        from agent.services.role_model import resolve_role
        return resolve_role("CONVO_CONCEPTS").provider

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base.update({
            "total_processed": self._total_processed,
            "total_concepts": self._total_concepts,
            "total_links": self._total_links,
            "total_facts_extracted": self._total_facts_extracted,
            "use_llm": self.use_llm,
            "model": self.model if self.use_llm else "(entity-match)",
            "prompts": dict(self._prompts),
        })
        return base

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _process_batch(self) -> str:
        """Process up to batch_size un-extracted conversations. Returns summary."""
        from data.db import get_connection
        from contextlib import closing

        last_id = self._get_progress()

        # Find un-processed conversations
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                "SELECT id, session_id FROM convos WHERE id > ? ORDER BY id LIMIT ?",
                (last_id, self.batch_size),
            ).fetchall()

        if not rows:
            self._run_consolidation()
            return "All caught up — ran consolidation"

        for convo_id, session_id in rows:
            self._extract_conversation(convo_id, session_id)

        new_last_id = rows[-1][0]
        self._set_progress(new_last_id)

        if len(rows) < self.batch_size:
            self._run_consolidation()

        return f"Processed {len(rows)} conversations, {self._total_concepts} concepts, {self._total_links} links"

    def _extract_conversation(self, convo_id: int, session_id: str) -> None:
        """Extract concepts from a single conversation."""
        from data.db import get_connection
        from contextlib import closing

        with closing(get_connection(readonly=True)) as conn:
            turn_rows = conn.execute(
                "SELECT user_message, assistant_message FROM convo_turns "
                "WHERE convo_id = ? ORDER BY turn_index",
                (convo_id,),
            ).fetchall()

        if not turn_rows:
            return

        turns = []
        for user_msg, asst_msg in turn_rows:
            turn: Dict[str, str] = {}
            if user_msg:
                turn["user"] = user_msg
            if asst_msg:
                turn["assistant"] = asst_msg
            if turn:
                turns.append(turn)

        if not turns:
            return

        # ── LLM extraction (discovers new facts → training data) ─────
        if self.use_llm:
            self._llm_extract_facts(turns, session_id)

        # ── Entity-match extraction (links known entities in graph) ───
        try:
            from agent.threads.linking_core.schema import (
                extract_and_record_conversation_concepts,
            )
            result = extract_and_record_conversation_concepts(
                turns, session_id=session_id, learning_rate=0.1,
            )
            self._total_processed += 1
            self._total_concepts += len(result.get("concepts", []))
            self._total_links += result.get("links_created", 0)
        except Exception as e:
            print(f"[convo_concepts] Failed on convo {convo_id}: {e}")

    # ------------------------------------------------------------------
    # LLM fact extraction
    # ------------------------------------------------------------------

    def _llm_extract_facts(self, turns: List[Dict[str, str]], session_id: str) -> None:
        """Call the LLM to extract facts, validate, stage, and save training data."""
        # Build conversation text (cap at ~4000 chars to fit prompt window)
        chunks: List[str] = []
        char_budget = 4000
        for turn in turns:
            if turn.get("user"):
                chunks.append(f"User: {turn['user']}")
            if turn.get("assistant"):
                chunks.append(f"Assistant: {turn['assistant']}")
        convo_text = "\n".join(chunks)
        if len(convo_text) > char_budget:
            convo_text = convo_text[:char_budget] + "\n[...truncated]"

        if len(convo_text) < 50:
            return

        # Call model
        prompt = f"Conversation:\n\"\"\"\n{convo_text}\n\"\"\"\n\nJSON array:"
        try:
            raw = self._call_model(
                [
                    {"role": "system", "content": self._prompts.get("extract", _EXTRACT_SYSTEM)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
        except Exception as e:
            print(f"[convo_concepts] LLM call failed for {session_id}: {e}")
            return

        # Parse
        facts = self._parse_facts(raw)
        if not facts:
            # Still save as training example (empty extraction is valid)
            self._save_training_example(convo_text, "[]", session_id)
            return

        # Validate each fact
        valid_facts = [f for f in facts if self._validate_fact(f)]
        if not valid_facts:
            self._save_training_example(convo_text, "[]", session_id)
            return

        # Stage valid facts in temp_memory
        try:
            from agent.subconscious.temp_memory import add_fact
            for fact in valid_facts:
                add_fact(
                    session_id=session_id,
                    text=fact["text"],
                    source="backfill",
                    metadata={
                        "hier_key": fact["key"],
                        "category": "general",
                        "confidence": 0.5,
                    },
                )
            self._total_facts_extracted += len(valid_facts)
        except Exception as e:
            print(f"[convo_concepts] Failed to stage facts for {session_id}: {e}")

        # Invalidate entity registry so new fact keys become matchable
        try:
            from agent.threads.linking_core.schema import invalidate_entity_registry
            invalidate_entity_registry()
        except Exception:
            pass

        # Save training example
        self._save_training_example(
            convo_text,
            json.dumps(valid_facts, ensure_ascii=False),
            session_id,
        )

    def _call_model(self, messages: list, temperature: float = 0.1) -> str:
        """Route to ollama or openai, following MemoryLoop's pattern."""
        model = self.model
        prov = self.provider

        if prov == "openai":
            return self._call_openai(model, messages, temperature)
        return self._call_ollama(model, messages, temperature)

    def _call_ollama(self, model: str, messages: list, temperature: float) -> str:
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
            return response["message"]["content"].strip()
        finally:
            release_ollama_gate()

    def _call_openai(self, model: str, messages: list, temperature: float) -> str:
        import urllib.request
        from agent.services.role_model import resolve_role

        cfg = resolve_role("CONVO_CONCEPTS")
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()

    # ------------------------------------------------------------------
    # Validation & parsing (noise defense)
    # ------------------------------------------------------------------

    # Keys that indicate hallucinated or useless extractions
    _JUNK_KEYS = {
        "name", "user", "assistant", "message", "text", "response",
        "conversation", "chat", "n/a", "none", "unknown", "test",
    }

    def _validate_fact(self, fact: dict) -> bool:
        """Reject noise before it hits the DB."""
        if not isinstance(fact, dict):
            return False
        key = fact.get("key", "")
        text = fact.get("text", "")
        if not key or not text:
            return False
        # Key must be a simple identifier
        if not re.match(r'^[a-z][a-z0-9_]{1,40}$', key):
            return False
        # Reject known junk keys
        if key in self._JUNK_KEYS:
            return False
        # Text must be substantive
        if len(text) < 10 or len(text) > 500:
            return False
        return True

    def _parse_facts(self, raw: str) -> Optional[List[dict]]:
        """Parse LLM output as a JSON array of fact dicts."""
        if not raw:
            return None
        raw = raw.strip()

        # Strip markdown code fences
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()

        # Find the JSON array
        start = raw.find('[')
        end = raw.rfind(']')
        if start == -1 or end == -1:
            return None

        try:
            parsed = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, list):
            return None
        return parsed

    # ------------------------------------------------------------------
    # Training data output
    # ------------------------------------------------------------------

    def _save_training_example(self, convo_text: str, facts_json: str, session_id: str) -> None:
        """Append one extraction as a training example for the future 7B model."""
        _TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        outpath = _TRAINING_DIR / "concept_extractions.jsonl"

        example = {
            "messages": [
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"Conversation:\n\"\"\"\n{convo_text}\n\"\"\"\n\nJSON array:"},
                {"role": "assistant", "content": facts_json},
            ],
            "metadata": {
                "source": "convo_concepts",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        with open(outpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    def _run_consolidation(self) -> None:
        """Run link consolidation (SHORT → LONG promotion)."""
        try:
            from agent.threads.linking_core.schema import consolidate_links
            consolidate_links(fire_threshold=5, strength_threshold=0.5)
        except Exception as e:
            print(f"[convo_concepts] Consolidation failed: {e}")

    # ------------------------------------------------------------------
    # Progress tracking (uses memory_loop_state table)
    # ------------------------------------------------------------------

    def _get_progress(self) -> int:
        """Get the last processed conversation id."""
        from data.db import get_connection
        from contextlib import closing

        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT value FROM memory_loop_state WHERE key = ?",
                (_PROGRESS_KEY,),
            ).fetchone()
        return int(row[0]) if row else 0

    def _set_progress(self, convo_id: int) -> None:
        """Update the last processed conversation id."""
        from data.db import get_connection
        from contextlib import closing

        with closing(get_connection()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_loop_state (key, value) VALUES (?, ?)",
                (_PROGRESS_KEY, str(convo_id)),
            )
            conn.commit()


# ------------------------------------------------------------------
# Standalone helpers (for CLI / scripts)
# ------------------------------------------------------------------

def get_backfill_status() -> Dict[str, Any]:
    """Return progress of the conversation concept backfill."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection(readonly=True)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM convos").fetchone()[0]
        row = conn.execute(
            "SELECT value FROM memory_loop_state WHERE key = ?",
            (_PROGRESS_KEY,),
        ).fetchone()
        last_id = int(row[0]) if row else 0
        processed = conn.execute(
            "SELECT COUNT(*) FROM convos WHERE id <= ?", (last_id,)
        ).fetchone()[0]

    return {
        "total_conversations": total,
        "processed": processed,
        "remaining": total - processed,
        "last_processed_id": last_id,
    }


def reset_backfill() -> None:
    """Reset backfill progress so all conversations are reprocessed."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection()) as conn:
        conn.execute(
            "DELETE FROM memory_loop_state WHERE key = ?", (_PROGRESS_KEY,),
        )
        conn.commit()
