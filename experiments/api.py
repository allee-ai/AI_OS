"""
Experiments API — T3 Pipeline Management
=========================================
Endpoints to launch, monitor, and review T3 pretraining experiments.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from .t3 import create_run, run_pipeline, list_runs, get_run, get_training_curves

router = APIRouter(prefix="/api/experiments", tags=["experiments"])
logger = logging.getLogger("experiments.api")


class T3StartRequest(BaseModel):
    """Configuration overrides for a T3 experiment run."""
    pretrain_iters: Optional[int] = None
    pretrain_batch_size: Optional[int] = None
    pretrain_lr: Optional[str] = None
    sft_iters: Optional[int] = None
    sft_batch_size: Optional[int] = None
    sft_lr: Optional[str] = None
    sft_data_dir: Optional[str] = None


@router.post("/t3/start")
async def start_t3(req: T3StartRequest, background_tasks: BackgroundTasks):
    """Launch a new T3 experiment pipeline.
    
    The pipeline runs in the background:
    1. Build pretrain data from codebase
    2. Verify/download base model
    3. Continued pretraining on raw text
    4. Fuse pretrained weights
    5. SFT on instruction pairs
    6. Fuse final model
    7. Run knowledge retention evals (base vs final)
    
    Returns the run_id to poll for status.
    """
    # Check no other run is active
    for r in list_runs():
        if r["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail=f"Run {r['run_id']} is already in progress. Wait for it to complete."
            )

    # Build config overrides (only non-None values)
    overrides = {k: v for k, v in req.model_dump().items() if v is not None}

    run = create_run(overrides)
    run_id = run["run_id"]

    # Launch pipeline in background
    background_tasks.add_task(run_pipeline, run_id)
    logger.info(f"T3 experiment launched: {run_id}")

    return {
        "status": "launched",
        "run_id": run_id,
        "message": "T3 pipeline started. Poll /api/experiments/t3/status/{run_id} for progress.",
    }


@router.get("/t3/runs")
async def list_t3_runs():
    """List all T3 experiment runs."""
    return {"runs": list_runs()}


@router.get("/t3/status/{run_id}")
async def get_t3_status(run_id: str):
    """Get full status of a T3 run including phase progress."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return run


@router.get("/t3/curves/{run_id}")
async def get_t3_curves(run_id: str):
    """Get training loss curves for a T3 run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return get_training_curves(run_id)


@router.get("/t3/results/{run_id}")
async def get_t3_results(run_id: str):
    """Get eval results for a completed T3 run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    if not run.get("results"):
        raise HTTPException(400, "Run has no results yet (still in progress or failed before eval)")
    return {
        "run_id": run_id,
        "status": run["status"],
        "results": run["results"],
        "config": run["config"],
    }


@router.get("/t3/defaults")
async def get_t3_defaults():
    """Get default T3 experiment configuration."""
    from .t3 import DEFAULT_CONFIG, PHASES
    return {
        "config": DEFAULT_CONFIG,
        "phases": [{"id": p["id"], "name": p["name"], "description": p["description"]} for p in PHASES],
    }
