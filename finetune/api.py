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
    return {"files": files}
