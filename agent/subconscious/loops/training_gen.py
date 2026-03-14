"""
Training Data Generator Loop
==============================
Background loop that uses the LLM (with STATE awareness) to generate
new training examples every 2 hours.

For each module section, reads existing examples as seeds, then asks the
model to produce new variations that demonstrate deeper reasoning.

Generated examples are written to finetune/generated/ and exposed as
a "generated" section in the training pipeline.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BackgroundLoop, LoopConfig

GENERATED_DIR = Path(__file__).parents[3] / "finetune" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# 2 hours default
DEFAULT_INTERVAL = float(os.getenv("AIOS_TRAINING_GEN_INTERVAL", "7200"))

# Modules to generate examples for
MODULES = ["linking_core", "identity", "philosophy", "log", "reflex", "form", "chat", "docs"]

# System prompt for the generator
GENERATOR_SYSTEM = """You are a training data generator for a Cognitive Operating System called AI OS (agent name: Nola).
Your job is to create high-quality training examples (question/answer pairs) that teach the model about its own architecture.

Each example must be a valid JSON object with this exact structure:
{"messages": [{"role": "system", "content": "== STATE ==\\n..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "metadata": {"source": "MODULE", "section": "generated", "type": "synthetic"}}

Rules:
- The assistant response must demonstrate DEEP understanding, not just regurgitate facts
- Include specific technical details: function names, table columns, formulas, data flows
- Vary question types: "how", "why", "what happens when", "explain the difference", "walk me through"
- The system content should be a realistic STATE block the model would actually see
- Generate exactly 5 examples per batch
- Output ONLY a JSON array of 5 objects, no explanation text before or after"""


class TrainingGenLoop(BackgroundLoop):
    """
    Background loop that generates synthetic training examples using the LLM.
    
    Runs every 2 hours. For each module:
    1. Reads the module's reasoning examples as seed context
    2. Fetches current STATE for context awareness
    3. Asks the LLM to generate new varied examples
    4. Validates and saves to finetune/generated/{module}.jsonl
    """
    
    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL,
        enabled: bool = True,
    ):
        config = LoopConfig(
            interval_seconds=interval,
            name="training_gen",
            enabled=enabled,
            max_errors=5,
            error_backoff=2.0,
            context_aware=True,
        )
        super().__init__(config, self._generate_all)
        self._last_module: Optional[str] = None
        self._total_generated = 0
        self._generation_count = 0
    
    @property
    def model(self) -> str:
        return os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["last_module"] = self._last_module
        base["total_generated"] = self._total_generated
        base["generation_count"] = self._generation_count
        base["generated_dir"] = str(GENERATED_DIR)
        return base
    
    def _get_seed_examples(self, module: str) -> str:
        """Get reasoning examples for a module as seed context."""
        try:
            from finetune.gold_examples import get_reasoning_for_module
            reasoning = get_reasoning_for_module(module)
            if not reasoning:
                return ""
            # Take up to 3 examples as seeds
            seeds = reasoning[:3]
            return json.dumps(seeds, indent=2)
        except Exception:
            return ""
    
    def _get_module_context(self, module: str) -> str:
        """Get module-specific context for generation."""
        try:
            from docs.train import MODULE_FEATURES
            info = MODULE_FEATURES.get(module, {})
            if not info:
                return ""
            features = info.get("top_features", [])
            purpose = info.get("purpose", "")
            return f"Module: {module}\nPurpose: {purpose}\nFeatures:\n" + "\n".join(f"  - {f}" for f in features)
        except Exception:
            return ""
    
    def _call_model(self, prompt: str) -> str:
        """Call the LLM to generate examples."""
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
                    "messages": [
                        {"role": "system", "content": GENERATOR_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        
        # Default: Ollama
        import ollama
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.7, "num_predict": 4096},
        )
        return response["message"]["content"].strip()
    
    def _parse_examples(self, raw: str, module: str) -> List[Dict[str, Any]]:
        """Parse and validate LLM output into training examples."""
        import re
        
        # Try to extract JSON array from the response
        raw = raw.strip()
        
        # Remove markdown code fences if present
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        # Find the JSON array
        bracket_start = raw.find('[')
        bracket_end = raw.rfind(']')
        if bracket_start == -1 or bracket_end == -1:
            return []
        
        raw = raw[bracket_start:bracket_end + 1]
        
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        
        if not isinstance(parsed, list):
            return []
        
        valid = []
        for item in parsed:
            # Validate structure
            if not isinstance(item, dict):
                continue
            messages = item.get("messages", [])
            if not isinstance(messages, list) or len(messages) != 3:
                continue
            
            roles = [m.get("role") for m in messages]
            if roles != ["system", "user", "assistant"]:
                continue
            
            # Ensure all messages have content
            if not all(m.get("content", "").strip() for m in messages):
                continue
            
            # Ensure assistant response is substantial (>50 chars)
            if len(messages[2].get("content", "")) < 50:
                continue
            
            # Force correct metadata
            item["metadata"] = {
                "source": module,
                "section": "generated",
                "type": "synthetic",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            valid.append(item)
        
        return valid
    
    def _generate_for_module(self, module: str) -> int:
        """Generate training examples for one module. Returns count generated."""
        self._last_module = module
        
        # Build context
        state_block = self._get_state(f"Generate training examples for {module}")
        seed_examples = self._get_seed_examples(module)
        module_context = self._get_module_context(module)
        
        prompt_parts = [f"Generate 5 new training examples for the '{module}' module."]
        
        if state_block:
            prompt_parts.append(f"\nCurrent system STATE:\n\"\"\"\n{state_block}\n\"\"\"")
        
        if module_context:
            prompt_parts.append(f"\nModule documentation:\n\"\"\"\n{module_context}\n\"\"\"")
        
        if seed_examples:
            prompt_parts.append(f"\nExisting examples (generate DIFFERENT ones, don't repeat these):\n\"\"\"\n{seed_examples}\n\"\"\"")
        
        prompt_parts.append(
            "\nGenerate 5 new examples that demonstrate deep reasoning about this module. "
            "Vary the question types. Include technical details. "
            "The assistant response should be thorough and show real understanding. "
            "Output ONLY a JSON array of 5 example objects."
        )
        
        prompt = "\n".join(prompt_parts)
        
        try:
            raw = self._call_model(prompt)
            examples = self._parse_examples(raw, module)
            
            if examples:
                output_path = GENERATED_DIR / f"{module}.jsonl"
                # Append to existing file
                with open(output_path, "a") as f:
                    for ex in examples:
                        f.write(json.dumps(ex) + "\n")
                
                self._total_generated += len(examples)
                return len(examples)
            
        except Exception as e:
            print(f"[TrainingGen] Error generating for {module}: {e}")
        
        return 0
    
    def _generate_all(self) -> None:
        """Generate training examples for all modules."""
        self._generation_count += 1
        total = 0

        # Run docstring extraction first (fast, deduped)
        try:
            from finetune.docstring_extractor import extract_and_save
            ds_counts = extract_and_save(deduplicate=True)
            ds_total = sum(ds_counts.values())
            if ds_total > 0:
                print(f"[TrainingGen] Extracted {ds_total} new docstring pairs")
        except Exception as e:
            print(f"[TrainingGen] Docstring extraction error: {e}")

        for module in MODULES:
            count = self._generate_for_module(module)
            total += count
            # Small delay between modules to avoid overloading
            if count > 0:
                time.sleep(2)
        
        # Log the generation run
        try:
            from agent.threads.log import log_event
            log_event(
                "training_gen",
                "training_gen",
                f"Generated {total} training examples across {len(MODULES)} modules (run #{self._generation_count})",
            )
        except Exception:
            pass
        
        print(f"[TrainingGen] Run #{self._generation_count}: generated {total} examples, total lifetime: {self._total_generated}")


# ─────────────────────────────────────────────────────
# Utility functions for the generated section
# ─────────────────────────────────────────────────────

def get_generated_examples(module: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read generated examples, optionally filtered by module."""
    examples = []
    if module:
        path = GENERATED_DIR / f"{module}.jsonl"
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            examples.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    else:
        for path in GENERATED_DIR.glob("*.jsonl"):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            examples.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    return examples


def get_generated_count(module: Optional[str] = None) -> int:
    """Count generated examples, optionally for a specific module."""
    count = 0
    if module:
        path = GENERATED_DIR / f"{module}.jsonl"
        if path.exists():
            with open(path) as f:
                count = sum(1 for line in f if line.strip())
    else:
        for path in GENERATED_DIR.glob("*.jsonl"):
            with open(path) as f:
                count += sum(1 for line in f if line.strip())
    return count


def get_generated_stats() -> Dict[str, int]:
    """Return generated example counts per module."""
    stats = {}
    for path in GENERATED_DIR.glob("*.jsonl"):
        module = path.stem
        with open(path) as f:
            stats[module] = sum(1 for line in f if line.strip())
    return stats


def clear_generated(module: Optional[str] = None) -> int:
    """Clear generated examples. Returns count cleared."""
    count = 0
    if module:
        path = GENERATED_DIR / f"{module}.jsonl"
        if path.exists():
            with open(path) as f:
                count = sum(1 for line in f if line.strip())
            path.unlink()
    else:
        for path in GENERATED_DIR.glob("*.jsonl"):
            with open(path) as f:
                count += sum(1 for line in f if line.strip())
            path.unlink()
    return count
