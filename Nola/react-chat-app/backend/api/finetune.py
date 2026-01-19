from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
import re
from pathlib import Path
import subprocess
import logging

router = APIRouter()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finetune")

class FinetuneConfig(BaseModel):
    rank: Optional[int] = None
    alpha: Optional[int] = None
    batch_size: Optional[int] = None
    grad_accumulation_steps: Optional[int] = None
    learning_rate: Optional[str] = None
    iters: Optional[int] = None

def find_project_root(current_path: Path) -> Path:
    # Traverse up until we see 'finetune' directory
    # Nola/react-chat-app/backend/api/finetune.py -> Nola/react-chat-app/backend/api -> ...
    for parent in current_path.parents:
        if (parent / "finetune").exists():
            return parent
    return current_path.parents[4] # Fallback

def run_training_script(script_path: Path, cwd: Path):
    try:
        logger.info(f"Starting training script: {script_path} in {cwd}")
        # Using bash to run the script
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
        current_file = Path(__file__).resolve()
        project_root = find_project_root(current_file)
        finetune_dir = project_root / "finetune"
        config_path = finetune_dir / "mlx_config.yaml"
        script_path = finetune_dir / "train_mac.sh"

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
             # Matches float or scientific notation
             content = re.sub(r"(learning_rate:\s*)([\d\.e-]+)", f"\\g<1>{config.learning_rate}", content)
        if config.iters is not None:
             content = re.sub(r"(iters:\s*)(\d+)", f"\\g<1>{config.iters}", content)

        # Write updated config
        config_path.write_text(content, encoding="utf-8")
        logger.info(f"Action: Training started by user. Updated config provided.")

        # Run script
        background_tasks.add_task(run_training_script, script_path, finetune_dir)

        return {
            "status": "success", 
            "message": "Training initiated.", 
            "config_update": config.dict(exclude_unset=True)
        }

    except Exception as e:
        logger.error(f"Error starting finetune: {e}")
        raise HTTPException(status_code=500, detail=str(e))
