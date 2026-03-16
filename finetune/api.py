"""
Finetune API - MLX finetuning management
========================================
Start and configure MLX finetuning jobs on Mac.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from pathlib import Path
import subprocess
import logging
import json
import re
import time

router = APIRouter(prefix="/api/finetune", tags=["finetune"])

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finetune")

# Finetune directory is this module's directory
FINETUNE_DIR = Path(__file__).resolve().parent


class FinetuneConfig(BaseModel):
    base_model: Optional[str] = None       # MLX model ID, e.g. "mlx-community/Qwen2.5-7B-Instruct-4bit"
    run_name: Optional[str] = None          # Human label, e.g. "1.5b-test"
    rank: Optional[int] = None
    alpha: Optional[int] = None
    scale: Optional[float] = None           # LoRA scale (1.0 is standard, >2 risks collapse)
    dropout: Optional[float] = None         # LoRA dropout (0.0-0.5)
    batch_size: Optional[int] = None
    grad_accumulation_steps: Optional[int] = None
    learning_rate: Optional[str] = None
    iters: Optional[int] = None
    warmup: Optional[int] = None            # LR warmup steps
    max_seq_length: Optional[int] = None    # Max context window for training


# ── Known MLX models (downloadable from HF) ─────────────────────────
MLX_MODELS = [
    {"id": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",  "label": "Qwen 2.5 1.5B (4-bit)",  "size_gb": 1.0, "ram_gb": 4},
    {"id": "mlx-community/Qwen2.5-7B-Instruct-4bit",    "label": "Qwen 2.5 7B (4-bit)",    "size_gb": 4.5, "ram_gb": 8},
    {"id": "mlx-community/Mistral-7B-Instruct-v0.3-4bit","label": "Mistral 7B v0.3 (4-bit)","size_gb": 4.1, "ram_gb": 8},
    {"id": "mlx-community/Llama-3.2-3B-Instruct-4bit",  "label": "Llama 3.2 3B (4-bit)",   "size_gb": 1.8, "ram_gb": 4},
    {"id": "mlx-community/Llama-3.2-1B-Instruct-4bit",  "label": "Llama 3.2 1B (4-bit)",   "size_gb": 0.7, "ram_gb": 3},
]


# ── Runs directory for named adapter sets ────────────────────────────
RUNS_DIR = FINETUNE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def run_training_script(script_path: Path, cwd: Path, env_overrides: Optional[Dict[str, str]] = None):
    """Run training script in background with optional env overrides."""
    import os as _os
    try:
        env = {**_os.environ, **(env_overrides or {})}
        logger.info(f"Starting training script: {script_path} in {cwd}")
        subprocess.Popen(
            ["/bin/bash", script_path.name],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        logger.info("Training process spawned successfully.")
    except Exception as e:
        logger.error(f"Failed to start training subprocess: {e}")


@router.get("/models")
async def list_models():
    """List available MLX base models for finetuning."""
    # Check which are already cached locally
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    result = []
    for m in MLX_MODELS:
        cached = False
        # HF cache dir format: models--org--name
        cache_name = "models--" + m["id"].replace("/", "--")
        if (hf_cache / cache_name).exists():
            cached = True
        result.append({**m, "cached": cached})
    return {"models": result}


@router.get("/runs")
async def list_runs():
    """List previous finetune runs (named adapter sets)."""
    runs = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir()):
            if d.is_dir():
                meta_path = d / "run_meta.json"
                meta = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                    except Exception:
                        pass
                adapter_files = list(d.glob("adapters/*.safetensors")) + list(d.glob("adapters/*.npz"))
                runs.append({
                    "name": d.name,
                    "path": str(d),
                    "has_adapters": len(adapter_files) > 0,
                    "adapter_count": len(adapter_files),
                    **meta,
                })
    return {"runs": runs}


@router.post("/start")
async def start_finetune(config: FinetuneConfig, background_tasks: BackgroundTasks):
    """
    Updates mlx_config.yaml and launches training script in background.
    
    - config.base_model: MLX model to finetune (default: Qwen2.5-7B-Instruct-4bit)
    - config.run_name: Label for this run (default: auto-generated timestamp)
    """
    try:
        config_path = FINETUNE_DIR / "mlx_config.yaml"
        script_path = FINETUNE_DIR / "train_mac.sh"

        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found at {config_path}")
        
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Training script not found at {script_path}")

        # Resolve model
        base_model = config.base_model or "mlx-community/Llama-3.2-3B-Instruct-4bit"

        # Resolve run name
        from datetime import datetime, timezone
        run_name = config.run_name or f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        # Sanitize: only alphanumeric, dash, underscore, dot
        run_name = re.sub(r'[^a-zA-Z0-9._-]', '-', run_name)
        run_dir = RUNS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        adapter_dir = run_dir / "adapters"
        adapter_dir.mkdir(parents=True, exist_ok=True)

        # Read config content
        content = config_path.read_text("utf-8")

        # Update model in config
        content = re.sub(r'(model:\s*")([^"]+)(")', f'\\g<1>{base_model}\\g<3>', content)
        # Fallback for unquoted model line
        content = re.sub(r'^(model:\s*)(.+)$', f'model: "{base_model}"', content, flags=re.MULTILINE)

        # Update values via regex to preserve comments
        if config.rank is not None:
            content = re.sub(r"(rank:\s*)(\d+)", f"\\g<1>{config.rank}", content)
        if config.alpha is not None:
            content = re.sub(r"(alpha:\s*)(\d+)", f"\\g<1>{config.alpha}", content)
        if config.batch_size is not None:
            content = re.sub(r"(batch_size:\s*)(\d+)", f"\\g<1>{config.batch_size}", content)
        if config.grad_accumulation_steps is not None:
            content = re.sub(r"(grad_accumulation_steps:\s*)(\d+)", f"\\g<1>{config.grad_accumulation_steps}", content)
        if config.learning_rate is not None:
            content = re.sub(r"(learning_rate:\s*)([\d\.e-]+)", f"\\g<1>{config.learning_rate}", content)
        if config.iters is not None:
            content = re.sub(r"(iters:\s*)(\d+)", f"\\g<1>{config.iters}", content)
        if config.scale is not None:
            content = re.sub(r"(scale:\s*)[\d.]+", f"\\g<1>{config.scale}", content)
        if config.dropout is not None:
            content = re.sub(r"(dropout:\s*)[\d.]+", f"\\g<1>{config.dropout}", content)
        if config.warmup is not None:
            content = re.sub(r"(warmup:\s*)(\d+)", f"\\g<1>{config.warmup}", content)
        if config.max_seq_length is not None:
            content = re.sub(r"(max_seq_length:\s*)(\d+)", f"\\g<1>{config.max_seq_length}", content)

        # Write updated config
        config_path.write_text(content, encoding="utf-8")

        # Save run metadata
        run_meta = {
            "base_model": base_model,
            "run_name": run_name,
            "config": config.model_dump(exclude_unset=True),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "training",
        }
        (run_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

        logger.info(f"Training started: run={run_name}, model={base_model}")

        # Pass model + adapter path to script via env vars
        env_overrides = {
            "AIOS_FT_MODEL": base_model,
            "AIOS_FT_ADAPTER_DIR": str(adapter_dir),
            "AIOS_FT_RUN_NAME": run_name,
            "AIOS_FT_RUN_DIR": str(run_dir),
        }
        background_tasks.add_task(run_training_script, script_path, FINETUNE_DIR, env_overrides)

        return {
            "status": "success", 
            "message": f"Training initiated: {run_name}",
            "run_name": run_name,
            "base_model": base_model,
            "adapter_dir": str(adapter_dir),
            "config_update": config.model_dump(exclude_unset=True),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting finetune: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_finetune_config():
    """Get current finetune configuration."""
    config_path = FINETUNE_DIR / "mlx_config.yaml"
    
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    
    content = config_path.read_text("utf-8")
    return {"config": content, "path": str(config_path)}


@router.get("/data")
async def list_training_data():
    """List available training data files."""
    files = []
    for f in FINETUNE_DIR.glob("*.jsonl"):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "lines": sum(1 for _ in open(f))
        })
    
    # Also check auto_generated folder
    auto_dir = FINETUNE_DIR / "auto_generated"
    if auto_dir.exists():
        for f in auto_dir.glob("*.jsonl"):
            files.append({
                "name": f"auto_generated/{f.name}",
                "size": f.stat().st_size,
                "lines": sum(1 for _ in open(f))
            })
    
    return {"files": files}


# ─────────────────────────────────────────────────────────────
# Module Import Helper
# ─────────────────────────────────────────────────────────────

def _import_train_module(name: str):
    """Import the train module for a given module name."""
    if name == "chat":
        return __import__("chat.train", fromlist=["export_training_data", "get_export_stats", "get_sections"])
    elif name == "docs":
        return __import__("docs.train", fromlist=["export_training_data", "get_export_stats", "get_sections"])
    else:
        return __import__(f"agent.threads.{name}.train", fromlist=["export_training_data", "get_export_stats", "get_sections"])


# ─────────────────────────────────────────────────────────────
# Export Endpoints - Pull from all threads
# ─────────────────────────────────────────────────────────────

@router.post("/export")
async def export_all_training_data():
    """
    Export training data from all threads.
    
    This is the full neuroplasticity pipeline:
    1. Consolidates LONG-potentiated concept links
    2. Exports each thread's data to module-specific JSONL
    3. Combines into unified training dataset
    """
    results = {}
    
    # 1. Consolidate concept links (SHORT → LONG promotion)
    try:
        from agent.threads.linking_core.schema import consolidate_links
        consolidation = consolidate_links(fire_threshold=5, strength_threshold=0.5)
        results["consolidation"] = consolidation
    except Exception as e:
        results["consolidation"] = {"error": str(e)}
    
    # 2. Export from each module
    for name in ALL_MODULES:
        try:
            module = _import_train_module(name)
            export_result = module.export_training_data()
            results[name] = export_result
        except Exception as e:
            results[name] = {"error": str(e)}
    
    # 2b. Export reasoning (curated) examples
    try:
        from finetune.gold_examples import get_reasoning_examples
        reasoning = get_reasoning_examples()
        reasoning_path = FINETUNE_DIR / "reasoning_train.jsonl"
        with open(reasoning_path, "w") as f:
            for ex in reasoning:
                f.write(json.dumps(ex) + "\n")
        results["reasoning"] = {"examples": len(reasoning), "path": str(reasoning_path)}
    except Exception as e:
        results["reasoning"] = {"error": str(e)}
    
    # 3. Combine into unified dataset
    try:
        combined_path = FINETUNE_DIR / "aios_combined.jsonl"
        total_examples = 0
        
        with open(combined_path, 'w') as combined:
            # Module-exported training data
            for name in ALL_MODULES:
                module_file = FINETUNE_DIR / f"{name}_train.jsonl"
                if module_file.exists():
                    with open(module_file) as f:
                        for line in f:
                            combined.write(line)
                            total_examples += 1

            # User-approved responses (thumbs up)
            approved_file = FINETUNE_DIR / "user_approved.jsonl"
            approved_count = 0
            if approved_file.exists():
                with open(approved_file) as f:
                    for line in f:
                        combined.write(line)
                        total_examples += 1
                        approved_count += 1

            # Reasoning (curated) training examples
            reasoning_file = FINETUNE_DIR / "reasoning_train.jsonl"
            reasoning_count = 0
            if reasoning_file.exists():
                with open(reasoning_file) as f:
                    for line in f:
                        combined.write(line)
                        total_examples += 1
                        reasoning_count += 1

            # Generated (synthetic) training examples
            generated_count = 0
            generated_dir = FINETUNE_DIR / "generated"
            if generated_dir.exists():
                for gen_file in generated_dir.glob("*.jsonl"):
                    with open(gen_file) as gf:
                        for line in gf:
                            if line.strip():
                                combined.write(line if line.endswith("\n") else line + "\n")
                                total_examples += 1
                                generated_count += 1

        results["user_approved"] = {"examples": approved_count}
        results["reasoning_included"] = {"examples": reasoning_count}
        results["generated_included"] = {"examples": generated_count}
        results["combined"] = {
            "path": str(combined_path),
            "total_examples": total_examples
        }
    except Exception as e:
        results["combined"] = {"error": str(e)}
    
    return {
        "status": "exported",
        "results": results
    }


# Personal data sources — section="data" from these modules contains user-specific info
PERSONAL_SOURCES = {"identity", "linking_core", "chat", "log", "philosophy", "reflex"}


@router.post("/export/base")
async def export_base_training_data():
    """
    Filter aios_combined.jsonl → aios_base.jsonl, keeping only system knowledge.

    Strips section="data" from personal sources (identity, linking_core, chat,
    log, philosophy, reflex) which contain profile facts, conversation turns,
    and concept associations. Keeps: api, cli, schema, generated, reasoning,
    and non-personal data sections.
    """
    combined_path = FINETUNE_DIR / "aios_combined.jsonl"
    base_path = FINETUNE_DIR / "aios_base.jsonl"

    if not combined_path.exists():
        raise HTTPException(status_code=400, detail="Run POST /api/finetune/export first to create aios_combined.jsonl")

    kept = 0
    stripped = 0

    with open(combined_path) as src, open(base_path, "w") as dst:
        for line in src:
            try:
                obj = json.loads(line)
                meta = obj.get("metadata", {})
                source = meta.get("source", "")
                section = meta.get("section", "")

                # Strip personal data sections from known personal sources
                if source in PERSONAL_SOURCES and section == "data":
                    stripped += 1
                    continue

                dst.write(line)
                kept += 1
            except json.JSONDecodeError:
                continue

    return {
        "status": "exported",
        "path": str(base_path),
        "kept": kept,
        "stripped": stripped,
        "total_source": kept + stripped,
    }


@router.get("/export/stats")
async def get_export_stats():
    """Get stats about exportable data from all modules."""
    stats = {}
    
    for name in ALL_MODULES:
        try:
            mod = _import_train_module(name)
            stats[name] = mod.get_export_stats()
        except Exception as e:
            stats[name] = {"error": str(e)}
    
    # Include reasoning example stats
    try:
        from finetune.gold_examples import get_reasoning_stats
        stats["reasoning"] = get_reasoning_stats()
    except Exception as e:
        stats["reasoning"] = {"error": str(e)}
    
    # Include generated example stats
    try:
        from agent.subconscious.loops.training_gen import get_generated_stats
        stats["generated"] = get_generated_stats()
    except Exception as e:
        stats["generated"] = {"error": str(e)}
    
    return {"stats": stats}


@router.post("/export/{thread}")
async def export_thread_training_data(thread: str):
    """Export training data from a specific module."""
    if thread not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Invalid module. Must be one of: {ALL_MODULES}")
    
    try:
        module = _import_train_module(thread)
        result = module.export_training_data()
        return {"status": "exported", "thread": thread, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Adapter Loading — Close the export → train → load loop
# ─────────────────────────────────────────────────────────────

class AdapterLoadRequest(BaseModel):
    adapter_path: Optional[str] = None  # default: finetune/adapters/
    base_model: Optional[str] = None    # default: from env AIOS_MODEL_NAME
    model_name: Optional[str] = None    # name for the fused model, default: aios-finetuned


@router.post("/load")
async def load_adapter(request: AdapterLoadRequest):
    """
    Load trained LoRA adapters into Ollama for inference.
    
    Creates a new Ollama model that combines base + adapters.
    After loading, set AIOS_MODEL_NAME to the new model name.
    """
    import os
    adapter_dir = Path(request.adapter_path) if request.adapter_path else FINETUNE_DIR / "adapters"
    
    if not adapter_dir.exists():
        raise HTTPException(status_code=404, detail=f"Adapter directory not found: {adapter_dir}")
    
    # Check for adapter files
    adapter_files = list(adapter_dir.glob("*.safetensors")) + list(adapter_dir.glob("*.npz"))
    if not adapter_files:
        raise HTTPException(status_code=404, detail=f"No adapter files found in {adapter_dir}")
    
    base_model = request.base_model or os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    model_name = request.model_name or "aios-finetuned"
    
    # Create Modelfile for Ollama
    modelfile_path = FINETUNE_DIR / "Modelfile"
    modelfile_content = f"FROM {base_model}\nADAPTER {adapter_dir}\n"
    modelfile_path.write_text(modelfile_content, encoding="utf-8")
    
    try:
        import ollama
        # Create the model with adapters
        ollama.create(model=model_name, modelfile=modelfile_content)
        
        # Store the active finetuned model name in service_config
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute(
                    """INSERT INTO service_config (service_id, settings_json, updated_at)
                       VALUES ('finetune', ?, datetime('now'))
                       ON CONFLICT(service_id) DO UPDATE SET
                           settings_json = ?, updated_at = datetime('now')""",
                    (json.dumps({"active_model": model_name, "base_model": base_model,
                                 "adapter_path": str(adapter_dir)}),) * 2
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not persist finetune config: {e}")
        
        logger.info(f"Adapter loaded: {model_name} (base: {base_model}, adapters: {adapter_dir})")
        return {
            "status": "loaded",
            "model_name": model_name,
            "base_model": base_model,
            "adapter_path": str(adapter_dir),
            "adapter_files": [f.name for f in adapter_files],
            "message": f"Model '{model_name}' created. Set AIOS_MODEL_NAME={model_name} to use it."
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="ollama package not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create model: {e}")


@router.get("/load/status")
async def get_adapter_status():
    """Get the currently loaded finetuned model info."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT settings_json FROM service_config WHERE service_id = 'finetune'"
            ).fetchone()
            if row and row[0]:
                return {"status": "loaded", **json.loads(row[0])}
    except Exception:
        pass
    return {"status": "none", "message": "No finetuned model loaded"}


# ─────────────────────────────────────────────────────────────
# Module Enable/Disable — Control what goes into training
# ─────────────────────────────────────────────────────────────

# All exportable modules (threads + chat + cli)
ALL_MODULES = ["linking_core", "identity", "philosophy", "log", "reflex", "form", "chat", "docs"]


def _get_module_config() -> Dict[str, bool]:
    """Get enabled/disabled status for each finetune module."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT settings_json FROM service_config WHERE service_id = 'finetune_modules'"
            ).fetchone()
            if row and row[0]:
                return json.loads(row[0])
    except Exception:
        pass
    # Default: all enabled
    return {m: True for m in ALL_MODULES}


def _set_module_config(config: Dict[str, bool]) -> None:
    """Persist module enable/disable config."""
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        conn.execute(
            """INSERT INTO service_config (service_id, settings_json, updated_at)
               VALUES ('finetune_modules', ?, datetime('now'))
               ON CONFLICT(service_id) DO UPDATE SET
                   settings_json = ?, updated_at = datetime('now')""",
            (json.dumps(config),) * 2
        )
        conn.commit()


@router.get("/modules")
async def list_finetune_modules():
    """List all finetune modules with enabled status and exportable counts."""
    from finetune.gold_examples import get_reasoning_count_for_module
    config = _get_module_config()
    modules = []
    for name in ALL_MODULES:
        info: Dict[str, Any] = {"name": name, "enabled": config.get(name, True)}
        try:
            mod = _import_train_module(name)
            info["stats"] = mod.get_export_stats()
        except Exception as e:
            info["stats"] = {"error": str(e)}
        info["reasoning_count"] = get_reasoning_count_for_module(name)
        # Include generated example count
        try:
            from agent.subconscious.loops.training_gen import get_generated_count
            info["generated_count"] = get_generated_count(name)
        except Exception:
            info["generated_count"] = 0
        modules.append(info)
    return {"modules": modules}


@router.put("/modules/{name}/enabled")
async def toggle_finetune_module(name: str, enabled: bool = True):
    """Enable or disable a module for finetune export."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}. Valid: {ALL_MODULES}")
    config = _get_module_config()
    config[name] = enabled
    _set_module_config(config)
    return {"module": name, "enabled": enabled}


@router.get("/modules/{name}/preview")
async def preview_module_data(name: str, limit: int = 5):
    """Preview sample training examples from a module."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}")
    try:
        mod = _import_train_module(name)
        # Export to temp to read samples
        result = mod.export_training_data()
        path = Path(result.get("path", ""))
        samples = []
        if path.exists():
            with open(path) as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    try:
                        samples.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return {"module": name, "samples": samples, "total": result.get("examples", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{name}/sections")
async def get_module_sections(name: str):
    """Get available training sections for a module (data, api, cli, schema, reasoning)."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}")
    try:
        mod = _import_train_module(name)
        sections = mod.get_sections()
        # Add reasoning section count
        from finetune.gold_examples import get_reasoning_count_for_module
        reasoning_count = get_reasoning_count_for_module(name)
        if reasoning_count > 0:
            sections["reasoning"] = {"description": "Curated, hand-crafted reasoning examples", "examples": reasoning_count}
        # Add generated section count
        try:
            from agent.subconscious.loops.training_gen import get_generated_examples
            gen_all = get_generated_examples(name)
            # Docstring-typed examples enrich their respective sections
            ds_by_section: Dict[str, int] = {}
            non_docstring = 0
            for ex in gen_all:
                meta = ex.get("metadata", {})
                if meta.get("type") == "docstring":
                    sec = meta.get("section", "data")
                    ds_by_section[sec] = ds_by_section.get(sec, 0) + 1
                else:
                    non_docstring += 1
            # Bump existing section counts with docstring additions
            for sec, count in ds_by_section.items():
                if sec in sections:
                    sections[sec]["examples"] = sections[sec].get("examples", 0) + count
            if non_docstring > 0:
                sections["generated"] = {"description": "LLM-generated synthetic examples", "examples": non_docstring}
        except Exception:
            pass
        return {"module": name, "sections": sections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Section Detail + Approval + Unified
# ─────────────────────────────────────────────────────────────

def _get_all_examples_for_module(name: str) -> List[Dict[str, Any]]:
    """Collect ALL examples for a module across all section sources."""
    examples = []

    # 1. Module-exported data (data, api, cli, schema sections)
    try:
        mod = _import_train_module(name)
        result = mod.export_training_data()
        path = Path(result.get("path", ""))
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            examples.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    except Exception:
        pass

    # 2. Reasoning examples
    try:
        from finetune.gold_examples import get_reasoning_for_module
        examples.extend(get_reasoning_for_module(name))
    except Exception:
        pass

    # 3. Generated examples
    try:
        from agent.subconscious.loops.training_gen import get_generated_examples
        examples.extend(get_generated_examples(name))
    except Exception:
        pass

    # 4. Approved examples
    approved_path = FINETUNE_DIR / "approved" / f"{name}.jsonl"
    if approved_path.exists():
        with open(approved_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ex = json.loads(line)
                        if not ex.get("metadata"):
                            ex["metadata"] = {}
                        ex["metadata"]["section"] = "approved"
                        examples.append(ex)
                    except json.JSONDecodeError:
                        pass

    return examples


@router.get("/modules/{name}/sections/{section}")
async def get_section_examples(name: str, section: str, page: int = 1, per_page: int = 50):
    """Get all training examples for a module+section pair, paginated."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}")

    examples = []

    if section == "reasoning":
        from finetune.gold_examples import get_reasoning_for_module
        examples = get_reasoning_for_module(name)
    elif section == "generated":
        try:
            from agent.subconscious.loops.training_gen import get_generated_examples
            examples = get_generated_examples(name)
        except Exception:
            examples = []
    elif section == "approved":
        approved_path = FINETUNE_DIR / "approved" / f"{name}.jsonl"
        if approved_path.exists():
            with open(approved_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            examples.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    else:
        # data, api, cli, schema — export then filter by metadata.section
        try:
            mod = _import_train_module(name)
            result = mod.export_training_data(sections=[section])
            path = Path(result.get("path", ""))
            if path.exists():
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                ex = json.loads(line)
                                examples.append(ex)
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        # Also include docstring-sourced examples whose metadata.section matches
        try:
            from agent.subconscious.loops.training_gen import get_generated_examples
            for ex in get_generated_examples(name):
                meta = ex.get("metadata", {})
                if meta.get("type") == "docstring" and meta.get("section") == section:
                    examples.append(ex)
        except Exception:
            pass

    # Add index IDs for tracking
    for i, ex in enumerate(examples):
        ex["_id"] = i

    total = len(examples)
    start = (page - 1) * per_page
    end = start + per_page
    page_examples = examples[start:end]

    return {
        "module": name,
        "section": section,
        "examples": page_examples,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


class ApprovalRequest(BaseModel):
    example_ids: List[int]
    action: str  # "approve" or "reject"


@router.post("/modules/{name}/sections/generated/approve")
async def approve_generated_examples(name: str, body: ApprovalRequest):
    """Approve or reject generated examples. Approved → finetune/approved/{module}.jsonl."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}")
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    # Load all generated examples
    try:
        from agent.subconscious.loops.training_gen import get_generated_examples
        all_gen = get_generated_examples(name)
    except Exception:
        all_gen = []

    if not all_gen:
        raise HTTPException(status_code=404, detail="No generated examples found")

    selected = [all_gen[i] for i in body.example_ids if 0 <= i < len(all_gen)]
    if not selected:
        raise HTTPException(status_code=400, detail="No valid example_ids")

    approved_dir = FINETUNE_DIR / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    approved_path = approved_dir / f"{name}.jsonl"

    if body.action == "approve":
        with open(approved_path, "a") as f:
            for ex in selected:
                if not ex.get("metadata"):
                    ex["metadata"] = {}
                ex["metadata"]["approved"] = True
                f.write(json.dumps(ex) + "\n")
    else:
        # Flag as rejected in generated file (rewrite without deleting)
        gen_path = FINETUNE_DIR / "generated" / f"{name}.jsonl"
        if gen_path.exists():
            rejected_ids = set(body.example_ids)
            lines = []
            with open(gen_path) as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ex = json.loads(line)
                        if i in rejected_ids:
                            if not ex.get("metadata"):
                                ex["metadata"] = {}
                            ex["metadata"]["rejected"] = True
                        lines.append(json.dumps(ex))
                    except json.JSONDecodeError:
                        lines.append(line)
            with open(gen_path, "w") as f:
                for l in lines:
                    f.write(l + "\n")

    # Log to unified_events
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="finetune_approval",
            source="finetune",
            data=f"{body.action}d {len(selected)} generated examples for {name}",
            metadata={"module": name, "action": body.action, "count": len(selected)},
        )
    except Exception:
        pass

    return {
        "status": body.action + "d",
        "module": name,
        "count": len(selected),
    }


class GenerateRequest(BaseModel):
    module: Optional[str] = None   # None = all modules
    file: Optional[str] = None     # Specific file path (relative to root)


@router.post("/generate")
async def trigger_generation(body: GenerateRequest, background_tasks: BackgroundTasks):
    """On-demand trigger for kimi-k2 training data generation."""
    from agent.subconscious.loops.training_gen import (
        TrainingGenLoop, ALL_MODULES, get_generated_count,
    )

    loop = TrainingGenLoop(enabled=True)

    # File-level generation
    if body.file:
        module = body.module or ""
        before = get_generated_count(module) if module else 0

        def _run_file():
            loop.generate_for_file(body.file, module)

        background_tasks.add_task(_run_file)
        return {
            "status": "started",
            "mode": "file",
            "file": body.file,
            "module": module,
        }

    # Module-level generation
    target_modules = ALL_MODULES
    if body.module:
        if body.module not in ALL_MODULES:
            raise HTTPException(status_code=400, detail=f"Unknown module: {body.module}")
        target_modules = [body.module]

    before = {m: get_generated_count(m) for m in target_modules}

    def _run():
        for mod in target_modules:
            loop._generate_for_module(mod)

    background_tasks.add_task(_run)

    return {
        "status": "started",
        "mode": "module",
        "modules": target_modules,
        "before_counts": before,
    }


@router.get("/generate/targets")
async def list_generation_targets():
    """List all module targets with files, generated counts, and labels."""
    from agent.subconscious.loops.training_gen import get_all_targets, ALL_MODULES, MODULE_LABELS
    targets = get_all_targets()
    return {
        "targets": targets,
        "total_modules": len(ALL_MODULES),
        "total_files": sum(t["file_count"] for t in targets),
        "total_generated": sum(t["generated_total"] for t in targets),
    }


@router.post("/generate/all-files")
async def trigger_all_files_generation(
    background_tasks: BackgroundTasks,
    module: Optional[str] = None,
):
    """Generate examples for every file across all modules (or one module). Runs in background."""
    from agent.subconscious.loops.training_gen import (
        TrainingGenLoop, ALL_MODULES, MODULE_DIRS,
    )

    target_modules = ALL_MODULES
    if module:
        if module not in ALL_MODULES:
            raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
        target_modules = [module]

    loop = TrainingGenLoop(enabled=True)
    file_list = []
    for mod in target_modules:
        for f in loop.discover_files(mod):
            file_list.append((mod, f))

    def _run_all():
        for mod, fpath in file_list:
            try:
                loop.generate_for_file(fpath, mod)
                time.sleep(1)  # Throttle between files
            except Exception as e:
                print(f"[TrainingGen] Error on {fpath}: {e}")

    background_tasks.add_task(_run_all)

    return {
        "status": "started",
        "modules": target_modules,
        "total_files": len(file_list),
        "files": [f for _, f in file_list],
    }


@router.get("/unified")
async def get_unified_examples(
    module: Optional[str] = None,
    section: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
):
    """Get ALL training examples across all modules, filterable."""
    all_examples = []

    target_modules = [module] if module and module in ALL_MODULES else ALL_MODULES

    for mod_name in target_modules:
        mod_examples = _get_all_examples_for_module(mod_name)
        # Tag each with module name for unified display
        for ex in mod_examples:
            if not ex.get("metadata"):
                ex["metadata"] = {}
            if "source" not in ex["metadata"]:
                ex["metadata"]["source"] = mod_name
        all_examples.extend(mod_examples)

    # Filter by section if specified
    if section:
        all_examples = [
            ex for ex in all_examples
            if ex.get("metadata", {}).get("section") == section
        ]

    # Add IDs
    for i, ex in enumerate(all_examples):
        ex["_id"] = i

    total = len(all_examples)
    start = (page - 1) * per_page
    end = start + per_page
    page_examples = all_examples[start:end]

    return {
        "examples": page_examples,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "filters": {"module": module, "section": section},
    }


# ── Docstring extraction ───────────────────────────────────────────────

@router.get("/docstrings/stats")
async def docstring_stats():
    """Get count of extractable docstrings per module."""
    from finetune.docstring_extractor import get_stats
    return {"stats": get_stats(), "total": sum(get_stats().values())}


@router.post("/docstrings/extract")
async def extract_docstrings(module: Optional[str] = None, deduplicate: bool = True):
    """
    Extract docstrings from source code and save as training pairs.
    Optionally filter to a single module.  Dedup is on by default.
    """
    from finetune.docstring_extractor import extract_and_save, extract_module
    import json as _json

    if module:
        if module not in ALL_MODULES:
            raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
        from finetune.docstring_extractor import extract_module as _ext, _content_hash, _load_dedup_index, _save_dedup_index
        pairs = _ext(module)
        seen = _load_dedup_index() if deduplicate else set()
        unique = [p for p in pairs if _content_hash(p) not in seen]
        if deduplicate:
            for p in unique:
                seen.add(_content_hash(p))
            _save_dedup_index(seen)
        if unique:
            out_dir = FINETUNE_DIR / "generated"
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / f"{module}.jsonl", "a") as f:
                for p in unique:
                    f.write(_json.dumps(p) + "\n")
        return {"module": module, "extracted": len(unique), "total_available": len(pairs)}

    counts = extract_and_save(deduplicate=deduplicate)
    return {"counts": counts, "total": sum(counts.values())}


class ModuleExportRequest(BaseModel):
    sections: Optional[List[str]] = None  # None = all sections


@router.post("/modules/{name}/export")
async def export_module_with_sections(name: str, body: ModuleExportRequest = ModuleExportRequest()):
    """Export training data for a specific module with section selection."""
    if name not in ALL_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {name}")
    try:
        mod = _import_train_module(name)
        
        # Separate reasoning and generated from other sections for the module export
        include_reasoning = False
        include_generated = False
        module_sections = body.sections
        if module_sections is not None:
            if "reasoning" in module_sections:
                include_reasoning = True
            if "generated" in module_sections:
                include_generated = True
            module_sections = [s for s in module_sections if s not in ("reasoning", "generated")]
        else:
            include_reasoning = True
            include_generated = True

        kwargs = {}
        if module_sections is not None:
            kwargs["sections"] = module_sections
        result = mod.export_training_data(**kwargs)
        output_path = result.get("path", "")

        # Append reasoning examples to the module's output file
        if include_reasoning and output_path:
            from finetune.gold_examples import get_reasoning_for_module
            reasoning = get_reasoning_for_module(name)
            if reasoning:
                with open(output_path, "a") as f:
                    for ex in reasoning:
                        f.write(json.dumps(ex) + "\n")
                result["examples"] = result.get("examples", 0) + len(reasoning)
                result["reasoning_examples"] = len(reasoning)

        # Append generated examples to the module's output file
        if include_generated and output_path:
            try:
                from agent.subconscious.loops.training_gen import get_generated_examples
                gen = get_generated_examples(name)
                if gen:
                    with open(output_path, "a") as f:
                        for ex in gen:
                            f.write(json.dumps(ex) + "\n")
                    result["examples"] = result.get("examples", 0) + len(gen)
                    result["generated_examples"] = len(gen)
            except Exception:
                pass

        return {"status": "exported", "module": name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
