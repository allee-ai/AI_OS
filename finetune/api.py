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

router = APIRouter(prefix="/api/finetune", tags=["finetune"])

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finetune")

# Finetune directory is this module's directory
FINETUNE_DIR = Path(__file__).resolve().parent


class FinetuneConfig(BaseModel):
    rank: Optional[int] = None
    alpha: Optional[int] = None
    batch_size: Optional[int] = None
    grad_accumulation_steps: Optional[int] = None
    learning_rate: Optional[str] = None
    iters: Optional[int] = None


def run_training_script(script_path: Path, cwd: Path):
    """Run training script in background."""
    try:
        logger.info(f"Starting training script: {script_path} in {cwd}")
        subprocess.Popen(
            ["/bin/bash", script_path.name],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info("Training process spawned successfully.")
    except Exception as e:
        logger.error(f"Failed to start training subprocess: {e}")


@router.post("/start")
async def start_finetune(config: FinetuneConfig, background_tasks: BackgroundTasks):
    """
    Updates mlx_config.yaml and launches training script in background.
    """
    try:
        config_path = FINETUNE_DIR / "mlx_config.yaml"
        script_path = FINETUNE_DIR / "train_mac.sh"

        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found at {config_path}")
        
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Training script not found at {script_path}")

        # Read config content
        content = config_path.read_text("utf-8")

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

        # Write updated config
        config_path.write_text(content, encoding="utf-8")
        logger.info(f"Action: Training started by user. Updated config provided.")

        # Run script
        background_tasks.add_task(run_training_script, script_path, FINETUNE_DIR)

        return {
            "status": "success", 
            "message": "Training initiated.", 
            "config_update": config.model_dump(exclude_unset=True)
        }

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
    
    # 2. Export from each thread
    threads = ["linking_core", "identity", "philosophy", "log", "reflex", "form"]
    
    for thread in threads:
        try:
            module = __import__(f"agent.threads.{thread}.train", fromlist=["export_training_data"])
            export_result = module.export_training_data()
            results[thread] = export_result
        except Exception as e:
            results[thread] = {"error": str(e)}
    
    # 3. Combine into unified dataset
    try:
        combined_path = FINETUNE_DIR / "aios_combined.jsonl"
        total_examples = 0
        
        with open(combined_path, 'w') as combined:
            # Thread-exported training data
            for thread in threads:
                thread_file = FINETUNE_DIR / f"{thread}_train.jsonl"
                if thread_file.exists():
                    with open(thread_file) as f:
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

        results["user_approved"] = {"examples": approved_count}
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


@router.get("/export/stats")
async def get_export_stats():
    """Get stats about exportable data from all threads."""
    stats = {}
    
    threads = ["linking_core", "identity", "philosophy", "log", "reflex", "form"]
    
    for thread in threads:
        try:
            module = __import__(f"agent.threads.{thread}.train", fromlist=["get_export_stats"])
            stats[thread] = module.get_export_stats()
        except Exception as e:
            stats[thread] = {"error": str(e)}
    
    return {"stats": stats}


@router.post("/export/{thread}")
async def export_thread_training_data(thread: str):
    """Export training data from a specific thread."""
    valid_threads = ["linking_core", "identity", "philosophy", "log", "reflex", "form"]
    
    if thread not in valid_threads:
        raise HTTPException(status_code=400, detail=f"Invalid thread. Must be one of: {valid_threads}")
    
    try:
        module = __import__(f"agent.threads.{thread}.train", fromlist=["export_training_data"])
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
ALL_MODULES = ["linking_core", "identity", "philosophy", "log", "reflex", "form", "chat", "cli"]


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
    config = _get_module_config()
    modules = []
    for name in ALL_MODULES:
        info: Dict[str, Any] = {"name": name, "enabled": config.get(name, True)}
        try:
            if name in ["chat", "cli"]:
                mod = __import__(f"{name}.train", fromlist=["get_export_stats"])
            else:
                mod = __import__(f"agent.threads.{name}.train", fromlist=["get_export_stats"])
            info["stats"] = mod.get_export_stats()
        except Exception as e:
            info["stats"] = {"error": str(e)}
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
        if name in ["chat", "cli"]:
            mod = __import__(f"{name}.train", fromlist=["export_training_data"])
        else:
            mod = __import__(f"agent.threads.{name}.train", fromlist=["export_training_data"])
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
