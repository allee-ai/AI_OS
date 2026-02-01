"""
Finetune API - MLX finetuning management
========================================
Start and configure MLX finetuning jobs on Mac.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import subprocess
import logging
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
            for thread in threads:
                thread_file = FINETUNE_DIR / f"{thread}_train.jsonl"
                if thread_file.exists():
                    with open(thread_file) as f:
                        for line in f:
                            combined.write(line)
                            total_examples += 1
        
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
