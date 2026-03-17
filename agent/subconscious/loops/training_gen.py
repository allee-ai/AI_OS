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

# Modules to generate examples for (original thread modules)
THREAD_MODULES = ["linking_core", "identity", "philosophy", "log", "reflex", "form", "chat", "docs"]

# Expanded: every source directory in the codebase
ALL_MODULES = THREAD_MODULES + [
    "workspace", "feeds", "agent_core", "agent_services",
    "form_tools", "parsers", "data_db", "scripts", "subconscious",
]

# Backwards compat
MODULES = ALL_MODULES

# System prompt for the generator
GENERATOR_SYSTEM = """You are a training data generator for a Cognitive Operating System called AI OS.
Your job is to create high-quality training examples that teach a small language model
how to answer questions about its own codebase, architecture, and capabilities.

You will be given:
1. ACTUAL SOURCE CODE from the module
2. MECHANICAL EXAMPLES — low-quality auto-generated Q&A pairs that the system currently produces
3. The current STATE block that the model sees at runtime

Your task: Generate 5 BETTER training examples that replace the mechanical ones.

Each example must be a valid JSON object with this exact structure:
{"messages": [{"role": "system", "content": "== STATE ==\\n..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

Quality rules:
- The system content MUST be a realistic STATE block (copy/adapt from the one provided)
- The user question should be NATURAL — how a real person would ask, not "What API endpoints does X have?"
- The assistant response must show DEEP understanding derived from the source code
- Include specific function names, table columns, formulas, variable names FROM the actual code
- Responses should be concise but thorough — 100-300 words, not essays
- Vary question types: "how does X work?", "what happens when Y?", "why is Z designed this way?"
- DO NOT just list endpoints or table columns — explain behavior, data flow, design decisions
- The model being trained is a personal AI assistant — responses should be first-person ("I have...", "My system...")

Output ONLY a valid JSON array of 5 objects. No explanation text before or after."""

# Module → source directory mapping
MODULE_DIRS: Dict[str, str] = {
    # Thread modules
    "linking_core":    "agent/threads/linking_core",
    "identity":        "agent/threads/identity",
    "philosophy":      "agent/threads/philosophy",
    "log":             "agent/threads/log",
    "reflex":          "agent/threads/reflex",
    "form":            "agent/threads/form",
    # Top-level modules
    "chat":            "chat",
    "docs":            "docs",
    "workspace":       "workspace",
    "feeds":           "Feeds",
    # Sub-packages
    "agent_core":      "agent/core",
    "agent_services":  "agent/services",
    "form_tools":      "agent/threads/form/tools",
    "parsers":         "chat/parsers",
    "data_db":         "data/db",
    "scripts":         "scripts",
    "subconscious":    "agent/subconscious",
}

# Human-readable labels
MODULE_LABELS: Dict[str, str] = {
    "linking_core":    "Concept Graph (Hebbian linking)",
    "identity":        "Identity & Profile Facts",
    "philosophy":      "Worldview & Values",
    "log":             "Event Log & Observations",
    "reflex":          "Feed→Tool Automations",
    "form":            "Tool Registry",
    "chat":            "Chat Sessions",
    "docs":            "Documentation",
    "workspace":       "Workspace & Summarizer",
    "feeds":           "Feed Sources & Polling",
    "agent_core":      "Core Config & Secrets",
    "agent_services":  "Agent Service Layer",
    "form_tools":      "Tool Executables",
    "parsers":         "Chat Import Parsers",
    "data_db":         "Database Layer",
    "scripts":         "CLI Scripts & Server",
    "subconscious":    "Background Loops & Orchestrator",
}

ROOT = Path(__file__).resolve().parents[3]


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
        """Model for generation — defaults to kimi-k2 (biggest available)."""
        return os.getenv("AIOS_TRAINING_GEN_MODEL",
                         os.getenv("AIOS_MODEL_NAME", "kimi-k2:1t-cloud"))
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["last_module"] = self._last_module
        base["total_generated"] = self._total_generated
        base["generation_count"] = self._generation_count
        base["generated_dir"] = str(GENERATED_DIR)
        return base
    
    # Map modules to their best-matching Claude example files
    CLAUDE_SEED_MAP: Dict[str, str] = {
        "identity": "claude_identity", "form": "claude_form_tools",
        "form_tools": "claude_form_tools", "subconscious": "claude_subconscious",
        "architecture": "claude_architecture", "agent_core": "claude_architecture",
        "agent_services": "claude_architecture", "linking_core": "claude_orchestrator",
        "log": "claude_threads_detail", "reflex": "claude_threads_detail",
        "philosophy": "claude_threads_detail", "chat": "claude_architecture",
        "docs": "claude_training_pipeline", "scripts": "claude_training_pipeline",
        "feeds": "claude_architecture", "workspace": "claude_architecture",
        "data_db": "claude_architecture", "parsers": "claude_architecture",
    }

    def _get_seed_examples(self, module: str) -> str:
        """Get reasoning examples for a module as seed context.
        
        Prefers high-quality Claude-generated examples when available,
        falls back to gold_examples.py.
        """
        seeds: list = []

        # 1. Try Claude seeds first
        claude_file = self.CLAUDE_SEED_MAP.get(module)
        if claude_file:
            claude_path = GENERATED_DIR / f"{claude_file}.jsonl"
            if claude_path.exists():
                try:
                    with open(claude_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                seeds.append(json.loads(line))
                except Exception:
                    pass

        # 2. Fall back to gold examples if we have fewer than 2 Claude seeds
        if len(seeds) < 2:
            try:
                from finetune.gold_examples import get_reasoning_for_module
                reasoning = get_reasoning_for_module(module)
                if reasoning:
                    seeds.extend(reasoning[:3])
            except Exception:
                pass

        if not seeds:
            return ""
        return json.dumps(seeds[:5], indent=2)
    
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
    
    def _read_source_code(self, module: str, max_chars: int = 8000) -> str:
        """Read actual source files for a module, truncated to budget."""
        source_dir = MODULE_DIRS.get(module)
        if not source_dir:
            return ""
        
        full_dir = ROOT / source_dir
        if not full_dir.exists():
            return ""
        
        parts = []
        total = 0
        # Prioritize key files
        priority_names = ["schema.py", "adapter.py", "api.py", "__init__.py"]
        py_files = sorted(full_dir.glob("*.py"), key=lambda p: (
            p.name not in priority_names,
            priority_names.index(p.name) if p.name in priority_names else 99
        ))
        
        for py_file in py_files:
            if py_file.name.startswith("__pycache__"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                # Truncate individual files if needed
                if len(content) > 3000:
                    content = content[:3000] + "\n# ... (truncated)"
                header = f"# === {source_dir}/{py_file.name} ===\n"
                chunk = header + content + "\n"
                if total + len(chunk) > max_chars:
                    break
                parts.append(chunk)
                total += len(chunk)
            except Exception:
                continue
        
        return "\n".join(parts)
    
    def _get_mechanical_examples(self, module: str, max_examples: int = 10) -> str:
        """Read the existing mechanical (crappy) training examples for a module."""
        module_file = ROOT / "finetune" / f"{module}_train.jsonl"
        if not module_file.exists():
            return ""
        
        examples = []
        try:
            with open(module_file) as f:
                for line in f:
                    if len(examples) >= max_examples:
                        break
                    obj = json.loads(line.strip())
                    msgs = obj.get("messages", [])
                    meta = obj.get("metadata", {})
                    section = meta.get("section", "")
                    # Only grab the mechanical ones (api, cli, schema sections)
                    if section in ("api", "cli", "schema"):
                        user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
                        asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
                        examples.append(f"Q: {user_msg}\nA: {asst_msg}")
        except Exception:
            pass
        
        if not examples:
            return ""
        return "MECHANICAL EXAMPLES TO IMPROVE:\n" + "\n---\n".join(examples)
    
    # ── File-level generation support ──────────────────────
    
    @staticmethod
    def discover_files(module: str) -> List[str]:
        """Return list of .py file paths (relative to ROOT) for a module.
        Only includes direct children, not subdirectories covered by other modules."""
        source_dir = MODULE_DIRS.get(module)
        if not source_dir:
            return []
        full_dir = ROOT / source_dir
        if not full_dir.exists():
            return []

        # Modules whose source_dir is a subdirectory of another module
        # use rglob; others use only direct .py files to avoid overlap
        sub_modules = {"form_tools", "parsers"}
        glob_fn = full_dir.rglob if module in sub_modules else full_dir.glob

        files = []
        for py_file in sorted(glob_fn("*.py")):
            if "__pycache__" in str(py_file):
                continue
            rel = str(py_file.relative_to(ROOT))
            # Skip files belonging to a more-specific sub-module
            if module not in sub_modules:
                skip = False
                for sub_mod, sub_dir in MODULE_DIRS.items():
                    if sub_mod == module:
                        continue
                    if sub_dir.startswith(source_dir + "/") and rel.startswith(sub_dir):
                        skip = True
                        break
                if skip:
                    continue
            files.append(rel)
        return files
    
    @staticmethod
    def _read_single_file(rel_path: str, max_chars: int = 12000) -> str:
        """Read a single file's contents, truncated to budget."""
        full = ROOT / rel_path
        if not full.exists():
            return ""
        try:
            content = full.read_text(encoding="utf-8")
            if len(content) > max_chars:
                content = content[:max_chars] + "\n# ... (truncated)"
            return f"# === {rel_path} ===\n{content}"
        except Exception:
            return ""
    
    def generate_for_file(self, rel_path: str, module: str = "") -> int:
        """Generate training examples for a single file. Returns count generated."""
        # Determine module from path if not given
        if not module:
            for mod, src_dir in MODULE_DIRS.items():
                if rel_path.startswith(src_dir):
                    module = mod
                    break
            if not module:
                module = Path(rel_path).stem
        
        self._last_module = f"{module}/{Path(rel_path).name}"
        source_code = self._read_single_file(rel_path)
        if not source_code:
            return 0
        
        state_block = self._get_state(f"Training examples for {rel_path}")
        seed_examples = self._get_seed_examples(module)
        existing_questions = self._get_existing_questions(module)
        
        prompt_parts = [
            f"Generate 5 high-quality training examples for the file '{rel_path}'.",
            f"Module: {module}. These will train a small 3B model to understand this file.",
            f"\nACTUAL SOURCE CODE:\n\"\"\"\n{source_code}\n\"\"\"",
        ]
        
        if state_block:
            prompt_parts.append(
                f"\nCURRENT STATE BLOCK (use as system prompt in examples):\n"
                f"\"\"\"\n{state_block[:2000]}\n\"\"\""
            )
        
        if seed_examples:
            prompt_parts.append(
                f"\nGOOD examples to match in quality:\n"
                f"\"\"\"\n{seed_examples[:2000]}\n\"\"\""
            )
        
        if existing_questions:
            prompt_parts.append(
                f"\n{existing_questions}\n\n"
                "^ Already covered. Generate examples about DIFFERENT aspects of this file."
            )
        
        prompt_parts.append(
            "\nGenerate 5 examples teaching SPECIFIC things from this file. "
            "Use first person ('I have...', 'My system...'). Be concise but thorough. "
            "Output ONLY a JSON array of 5 example objects."
        )
        
        prompt = "\n".join(prompt_parts)
        
        try:
            raw = self._call_model(prompt)
            examples = self._parse_examples(raw, module)
            
            # Tag with file path for tracking
            for ex in examples:
                ex["metadata"]["file"] = rel_path
            
            if examples:
                output_path = GENERATED_DIR / f"{module}.jsonl"
                with open(output_path, "a") as f:
                    for ex in examples:
                        f.write(json.dumps(ex) + "\n")
                self._total_generated += len(examples)
                return len(examples)
        except Exception as e:
            print(f"[TrainingGen] Error generating for {rel_path}: {e}")
        
        return 0
    
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
        from .base import acquire_ollama_gate, release_ollama_gate
        import ollama
        if not acquire_ollama_gate():
            raise RuntimeError("Ollama gate timeout")
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": GENERATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.7, "num_predict": 4096},
            )
            return response["message"]["content"].strip()
        finally:
            release_ollama_gate()
    
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
    
    def _get_existing_questions(self, module: str, max_questions: int = 30) -> str:
        """Read questions already generated for this module to avoid duplicates."""
        output_path = GENERATED_DIR / f"{module}.jsonl"
        if not output_path.exists():
            return ""
        
        questions = []
        try:
            with open(output_path) as f:
                for line in f:
                    obj = json.loads(line.strip())
                    msgs = obj.get("messages", [])
                    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
                    if user_msg:
                        questions.append(user_msg)
        except Exception:
            pass
        
        if not questions:
            return ""
        # Show most recent first (most likely to overlap), cap at max
        recent = questions[-max_questions:]
        return "ALREADY GENERATED (do NOT repeat these topics):\n" + "\n".join(f"- {q}" for q in recent)

    def _generate_for_module(self, module: str) -> int:
        """Generate training examples for one module. Returns count generated."""
        self._last_module = module
        
        # Build rich context from actual code and existing examples
        state_block = self._get_state(f"Generate training examples for {module}")
        source_code = self._read_source_code(module)
        mechanical = self._get_mechanical_examples(module)
        seed_examples = self._get_seed_examples(module)
        module_context = self._get_module_context(module)
        existing_questions = self._get_existing_questions(module)
        
        prompt_parts = [
            f"Generate 5 high-quality training examples for the '{module}' module.",
            f"These will train a small 3B model to understand its own codebase.",
        ]
        
        if source_code:
            prompt_parts.append(f"\nACTUAL SOURCE CODE:\n\"\"\"\n{source_code}\n\"\"\"")
        
        if mechanical:
            prompt_parts.append(
                f"\n{mechanical}\n\n"
                "^ These are the BAD examples the system currently generates. "
                "They are too mechanical ('What API endpoints does X have?' → listing). "
                "Generate BETTER ones that teach real understanding of the code above."
            )
        
        if state_block:
            prompt_parts.append(
                f"\nCURRENT STATE BLOCK (use this or adapt it for the system prompt in your examples):\n"
                f"\"\"\"\n{state_block[:2000]}\n\"\"\""
            )
        
        if module_context:
            prompt_parts.append(f"\nModule documentation:\n\"\"\"\n{module_context}\n\"\"\"")
        
        if seed_examples:
            prompt_parts.append(
                f"\nGOOD examples to match in quality (don't repeat these):\n"
                f"\"\"\"\n{seed_examples[:2000]}\n\"\"\""
            )
        
        if existing_questions:
            prompt_parts.append(
                f"\n{existing_questions}\n\n"
                "^ These questions have ALREADY been generated. "
                "You MUST cover DIFFERENT topics, functions, or design aspects. "
                "Explore parts of the source code not yet covered above."
            )
        
        prompt_parts.append(
            "\nGenerate 5 examples. Each should teach something SPECIFIC from the source code. "
            "Use first person ('I have...', 'My system...'). Be concise but thorough. "
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

    def generate_seeded_batch(self, questions_per_module: int = 10) -> Dict[str, int]:
        """Generate a batch of seeded examples across all modules.
        
        Calls _generate_for_module() ceil(N/5) times per module
        since each call produces ~5 examples.
        Returns dict of {module: examples_generated}.
        """
        import math
        calls_per = math.ceil(questions_per_module / 5)
        results: Dict[str, int] = {}
        for module in MODULES:
            count = 0
            for _ in range(calls_per):
                count += self._generate_for_module(module)
                time.sleep(1)
            results[module] = count
            if count > 0:
                time.sleep(2)
        total = sum(results.values())
        print(f"[TrainingGen] Seeded batch: {total} examples across {len(MODULES)} modules")
        return results


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


def get_all_targets() -> List[Dict[str, Any]]:
    """Return all module targets with file lists, labels, and generated counts."""
    gen_stats = get_generated_stats()
    # Build per-file counts from generated examples
    file_counts: Dict[str, Dict[str, int]] = {}
    for path in GENERATED_DIR.glob("*.jsonl"):
        module = path.stem
        file_counts[module] = {}
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ex = json.loads(line)
                        fpath = ex.get("metadata", {}).get("file", "")
                        if fpath:
                            file_counts[module][fpath] = file_counts[module].get(fpath, 0) + 1
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    targets = []
    for module in ALL_MODULES:
        source_dir = MODULE_DIRS.get(module, "")
        files = TrainingGenLoop.discover_files(module)
        generated = gen_stats.get(module, 0)
        fc = file_counts.get(module, {})
        file_details = [
            {
                "path": f,
                "name": Path(f).name,
                "generated": fc.get(f, 0),
            }
            for f in files
        ]
        targets.append({
            "module": module,
            "label": MODULE_LABELS.get(module, module),
            "source_dir": source_dir,
            "files": file_details,
            "file_count": len(files),
            "generated_total": generated,
        })
    return targets
