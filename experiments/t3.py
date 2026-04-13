"""
T3 Experiment — 3-Layer Training Pipeline
==========================================
Orchestrates the full SmolLM2-135M pipeline:
  Layer 1 — REPEAT:     Memorize raw codebase text (blob pretraining)
  Layer 2 — UNDERSTAND: Self-referential SFT (learn to talk about itself)
  Layer 3 — GENERALIZE: Full instruction SFT (optional, for general use)

Phases:
  1. Build pretrain data (raw text from codebase)
  2. Verify base model exists
  3. Continued pretraining on raw text (Layer 1)
  4. Fuse pretrained weights → standalone model
  5. Self-knowledge SFT (Layer 2)
  6. Fuse self-knowledge weights → self-model
  7. General SFT on instruction pairs (Layer 3)
  8. Fuse general SFT weights → final model
  9. Run knowledge retention evals (base vs self vs final)

Progress is tracked in a JSON status file, updated after each phase.
"""

import json
import os
import re
import subprocess
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("experiments.t3")

ROOT = Path(__file__).resolve().parent.parent  # AI_OS root
FINETUNE_DIR = ROOT / "finetune"
EXPERIMENTS_DIR = Path(__file__).resolve().parent
RUNS_DIR = EXPERIMENTS_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# ── Default Config ──────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "base_model": "finetune/runs/smol-135m-base",
    # Continued pretraining
    "pretrain_iters": 2500,
    "pretrain_batch_size": 4,
    "pretrain_lr": "5e-5",
    "pretrain_seq_length": 2048,
    "pretrain_save_every": 500,
    "pretrain_eval_every": 500,
    "pretrain_report_every": 50,
    # Layer 2: Self-knowledge SFT
    "self_sft_iters": 1500,
    "self_sft_batch_size": 2,
    "self_sft_lr": "2e-5",
    "self_sft_seq_length": 2048,
    "self_sft_save_every": 500,
    "self_sft_eval_every": 200,
    "self_sft_report_every": 50,
    # Self-SFT data directory (built by experiments/build_self_sft.py)
    "self_sft_data_dir": "experiments/self_sft",
    # Layer 3: General SFT (optional)
    "sft_iters": 2000,
    "sft_batch_size": 2,
    "sft_lr": "1e-5",
    "sft_seq_length": 2048,
    "sft_save_every": 500,
    "sft_eval_every": 200,
    "sft_report_every": 50,
    # General SFT data directory (must contain train.jsonl)
    "sft_data_dir": "finetune/runs/full-v1",
    # Whether to run Layer 3 (general SFT)
    "run_general_sft": False,
    # Eval models to compare
    "eval_models": [],  # auto-populated: base + self + final
}

PHASES = [
    {"id": "build_data", "name": "Build Pretrain Data", "description": "Export all code, docs, conversations as raw text JSONL"},
    {"id": "check_base", "name": "Verify Base Model", "description": "Confirm SmolLM2-135M base model exists"},
    {"id": "pretrain", "name": "Layer 1: REPEAT", "description": "Full finetune on raw codebase text — memorize everything"},
    {"id": "fuse_pretrain", "name": "Fuse Layer 1", "description": "Merge pretrain adapters into standalone model"},
    {"id": "self_sft", "name": "Layer 2: UNDERSTAND", "description": "Self-knowledge SFT — learn to talk about itself"},
    {"id": "fuse_self_sft", "name": "Fuse Layer 2", "description": "Merge self-SFT adapters into self-model"},
    {"id": "sft", "name": "Layer 3: GENERALIZE", "description": "General instruction SFT (optional)"},
    {"id": "fuse_sft", "name": "Fuse Layer 3", "description": "Merge general SFT adapters into final model"},
    {"id": "eval", "name": "Knowledge Retention Eval", "description": "Compare base vs self-model vs final on self-knowledge probes"},
]


# ── Status Management ───────────────────────────────────────────────────

def _status_path(run_id: str) -> Path:
    return RUNS_DIR / run_id / "status.json"


def _read_status(run_id: str) -> Optional[Dict[str, Any]]:
    path = _status_path(run_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _write_status(run_id: str, status: Dict[str, Any]):
    path = _status_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, default=str))


def _update_phase(run_id: str, phase_id: str, phase_status: str, detail: str = "", **extras):
    """Update a single phase's status in the run status file."""
    status = _read_status(run_id)
    if not status:
        return
    for p in status["phases"]:
        if p["id"] == phase_id:
            p["status"] = phase_status
            if detail:
                p["detail"] = detail
            p.update(extras)
            break
    if phase_status == "running":
        status["current_phase"] = phase_id
    status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _write_status(run_id, status)


def _parse_training_log(log_path: Path) -> List[Dict[str, Any]]:
    """Parse mlx_lm training output for loss values."""
    entries = []
    if not log_path.exists():
        return entries
    for line in log_path.read_text().splitlines():
        # mlx_lm format: "Iter 50: Train loss 3.456, Learning Rate 5.000e-05, ..."
        m = re.match(r'Iter\s+(\d+):\s+Train loss\s+([\d.]+)', line)
        if m:
            entries.append({"iter": int(m.group(1)), "train_loss": float(m.group(2))})
        # Also capture val loss: "Iter 500: Val loss 2.789, ..."
        m2 = re.match(r'Iter\s+(\d+):\s+Val loss\s+([\d.]+)', line)
        if m2:
            it = int(m2.group(1))
            val = float(m2.group(2))
            # Attach to existing entry if same iter
            for e in entries:
                if e["iter"] == it:
                    e["val_loss"] = val
                    break
            else:
                entries.append({"iter": it, "val_loss": val})
    return entries


# ── Pipeline Runner ─────────────────────────────────────────────────────

def create_run(config: Optional[Dict] = None) -> Dict[str, Any]:
    """Create a new T3 experiment run. Returns the initial status."""
    run_id = str(uuid.uuid4())[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    merged = {**DEFAULT_CONFIG, **(config or {})}

    status = {
        "run_id": run_id,
        "status": "pending",
        "config": merged,
        "current_phase": None,
        "phases": [
            {"id": p["id"], "name": p["name"], "description": p["description"], "status": "pending", "detail": ""}
            for p in PHASES
        ],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": None,
    }
    _write_status(run_id, status)
    return status


def run_pipeline(run_id: str):
    """Execute the full T3 pipeline. Meant to be called in a background task."""
    status = _read_status(run_id)
    if not status:
        logger.error(f"Run {run_id} not found")
        return

    config = status["config"]
    run_dir = RUNS_DIR / run_id
    status["status"] = "running"
    _write_status(run_id, status)

    # Pause subconscious loops during training
    loops_paused = False
    try:
        from agent.subconscious import pause_loops
        pause_loops(wait=True, timeout=120.0)
        loops_paused = True
    except Exception as e:
        logger.warning(f"Could not pause loops: {e}")

    try:
        # ── Phase 1: Build pretrain data ────────────────────────────
        _run_phase_build_data(run_id, config, run_dir)

        # ── Phase 2: Check base model ──────────────────────────────
        _run_phase_check_base(run_id, config)

        # ── Phase 3: Continued pretraining ─────────────────────────
        _run_phase_pretrain(run_id, config, run_dir)

        # ── Phase 4: Fuse pretrained weights ───────────────────────
        _run_phase_fuse_pretrain(run_id, config, run_dir)

        # ── Phase 5: Self-knowledge SFT (Layer 2) ─────────────────
        _run_phase_self_sft(run_id, config, run_dir)

        # ── Phase 6: Fuse self-SFT ────────────────────────────────
        _run_phase_fuse_self_sft(run_id, config, run_dir)

        # ── Phase 7: General SFT (Layer 3, optional) ──────────────
        if config.get("run_general_sft", False):
            _run_phase_sft(run_id, config, run_dir)
            # ── Phase 8: Fuse general SFT ──────────────────────────
            _run_phase_fuse_sft(run_id, config, run_dir)
        else:
            _update_phase(run_id, "sft", "skipped", "Layer 3 disabled (run_general_sft=False)")
            _update_phase(run_id, "fuse_sft", "skipped", "Layer 3 disabled")

        # ── Phase 9: Eval ──────────────────────────────────────────
        _run_phase_eval(run_id, config, run_dir)

        # Mark complete
        status = _read_status(run_id)
        status["status"] = "completed"
        status["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _write_status(run_id, status)
        logger.info(f"T3 pipeline complete: {run_id}")

    except Exception as e:
        logger.error(f"T3 pipeline failed at run {run_id}: {e}")
        status = _read_status(run_id)
        if status:
            status["status"] = "failed"
            status["error"] = str(e)
            _write_status(run_id, status)
    finally:
        if loops_paused:
            try:
                from agent.subconscious import resume_loops
                resume_loops()
            except Exception as e:
                logger.warning(f"Could not resume loops: {e}")


# ── Individual Phase Runners ────────────────────────────────────────────

def _run_phase_build_data(run_id: str, config: Dict, run_dir: Path):
    """Phase 1: Build pretrain data from codebase."""
    _update_phase(run_id, "build_data", "running", "Exporting codebase as raw text...")

    pretrain_dir = run_dir / "pretrain_data"
    pretrain_dir.mkdir(exist_ok=True)

    try:
        result = subprocess.run(
            ["python3", str(FINETUNE_DIR / "build_pretrain_data.py"), "--output", str(pretrain_dir)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"build_pretrain_data.py failed: {result.stderr[:500]}")

        # Count output
        train_file = pretrain_dir / "train.jsonl"
        line_count = sum(1 for _ in open(train_file)) if train_file.exists() else 0
        _update_phase(run_id, "build_data", "completed", f"Exported {line_count} text chunks", chunks=line_count)
    except Exception as e:
        _update_phase(run_id, "build_data", "failed", str(e))
        raise


def _run_phase_check_base(run_id: str, config: Dict):
    """Phase 2: Verify base model exists."""
    _update_phase(run_id, "check_base", "running", "Checking base model...")

    base_model = ROOT / config["base_model"]
    model_file = base_model / "model.safetensors"
    weights_dir = base_model / "weights"  # Some models use directory of shards

    if model_file.exists() or weights_dir.exists():
        _update_phase(run_id, "check_base", "completed", f"Found at {base_model}")
    else:
        # Try to convert from HuggingFace
        _update_phase(run_id, "check_base", "running", "Downloading and converting base model...")
        try:
            result = subprocess.run(
                ["python3", "-m", "mlx_lm", "convert",
                 "--hf-path", "HuggingFaceTB/SmolLM2-135M",
                 "--mlx-path", str(base_model)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Model download failed: {result.stderr[:500]}")
            _update_phase(run_id, "check_base", "completed", "Downloaded and converted SmolLM2-135M")
        except Exception as e:
            _update_phase(run_id, "check_base", "failed", str(e))
            raise


def _run_phase_pretrain(run_id: str, config: Dict, run_dir: Path):
    """Phase 3: Continued pretraining on raw text."""
    _update_phase(run_id, "pretrain", "running", "Starting continued pretraining...")

    base_model = str(ROOT / config["base_model"])
    pretrain_dir = run_dir / "pretrain_data"
    weights_dir = run_dir / "pretrain_weights"
    log_file = run_dir / "pretrain_training.log"

    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", base_model,
        "--data", str(pretrain_dir),
        "--train",
        "--fine-tune-type", "full",
        "--num-layers", "-1",
        "--batch-size", str(config["pretrain_batch_size"]),
        "--iters", str(config["pretrain_iters"]),
        "--learning-rate", str(config["pretrain_lr"]),
        "--steps-per-report", str(config["pretrain_report_every"]),
        "--steps-per-eval", str(config["pretrain_eval_every"]),
        "--save-every", str(config["pretrain_save_every"]),
        "--max-seq-length", str(config["pretrain_seq_length"]),
        "--grad-checkpoint",
        "--adapter-path", str(weights_dir),
        "--seed", "42",
    ]

    _run_training_subprocess(run_id, "pretrain", cmd, log_file)


def _run_phase_fuse_pretrain(run_id: str, config: Dict, run_dir: Path):
    """Phase 4: Fuse pretrained weights into standalone model."""
    _update_phase(run_id, "fuse_pretrain", "running", "Fusing pretrained weights...")

    base_model = str(ROOT / config["base_model"])
    weights_dir = run_dir / "pretrain_weights"
    fused_dir = run_dir / "pretrained_model"

    try:
        result = subprocess.run(
            ["python3", "-m", "mlx_lm", "fuse",
             "--model", base_model,
             "--adapter-path", str(weights_dir),
             "--save-path", str(fused_dir)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Fuse failed: {result.stderr[:500]}")
        _update_phase(run_id, "fuse_pretrain", "completed", f"Fused to {fused_dir.name}")
    except Exception as e:
        _update_phase(run_id, "fuse_pretrain", "failed", str(e))
        raise


def _run_phase_self_sft(run_id: str, config: Dict, run_dir: Path):
    """Phase 5: Self-knowledge SFT (Layer 2) — learn to talk about itself."""
    _update_phase(run_id, "self_sft", "running", "Starting self-knowledge SFT (Layer 2)...")

    fused_dir = run_dir / "pretrained_model"
    self_sft_data = str(ROOT / config["self_sft_data_dir"])
    self_sft_weights = run_dir / "self_sft_weights"
    log_file = run_dir / "self_sft_training.log"

    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", str(fused_dir),
        "--data", self_sft_data,
        "--train",
        "--fine-tune-type", "full",
        "--num-layers", "-1",
        "--batch-size", str(config["self_sft_batch_size"]),
        "--iters", str(config["self_sft_iters"]),
        "--learning-rate", str(config["self_sft_lr"]),
        "--steps-per-report", str(config["self_sft_report_every"]),
        "--steps-per-eval", str(config["self_sft_eval_every"]),
        "--save-every", str(config["self_sft_save_every"]),
        "--max-seq-length", str(config["self_sft_seq_length"]),
        "--grad-checkpoint",
        "--adapter-path", str(self_sft_weights),
        "--seed", "42",
    ]

    _run_training_subprocess(run_id, "self_sft", cmd, log_file)


def _run_phase_fuse_self_sft(run_id: str, config: Dict, run_dir: Path):
    """Phase 6: Fuse self-SFT weights into self-model."""
    _update_phase(run_id, "fuse_self_sft", "running", "Fusing self-knowledge weights...")

    fused_dir = run_dir / "pretrained_model"
    self_sft_weights = run_dir / "self_sft_weights"
    self_model_dir = run_dir / "self_model"

    try:
        result = subprocess.run(
            ["python3", "-m", "mlx_lm", "fuse",
             "--model", str(fused_dir),
             "--adapter-path", str(self_sft_weights),
             "--save-path", str(self_model_dir)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Fuse failed: {result.stderr[:500]}")
        _update_phase(run_id, "fuse_self_sft", "completed", f"Self-model at {self_model_dir.name}")
    except Exception as e:
        _update_phase(run_id, "fuse_self_sft", "failed", str(e))
        raise


def _run_phase_sft(run_id: str, config: Dict, run_dir: Path):
    """Phase 7: General SFT (Layer 3) — instruction tuning."""
    _update_phase(run_id, "sft", "running", "Starting general SFT (Layer 3)...")

    # Layer 3 builds on the self-model from Layer 2
    self_model_dir = run_dir / "self_model"
    sft_data = str(ROOT / config["sft_data_dir"])
    sft_weights = run_dir / "sft_weights"
    log_file = run_dir / "sft_training.log"

    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", str(self_model_dir),
        "--data", sft_data,
        "--train",
        "--fine-tune-type", "full",
        "--num-layers", "-1",
        "--batch-size", str(config["sft_batch_size"]),
        "--iters", str(config["sft_iters"]),
        "--learning-rate", str(config["sft_lr"]),
        "--steps-per-report", str(config["sft_report_every"]),
        "--steps-per-eval", str(config["sft_eval_every"]),
        "--save-every", str(config["sft_save_every"]),
        "--max-seq-length", str(config["sft_seq_length"]),
        "--grad-checkpoint",
        "--adapter-path", str(sft_weights),
        "--seed", "42",
    ]

    _run_training_subprocess(run_id, "sft", cmd, log_file)


def _run_phase_fuse_sft(run_id: str, config: Dict, run_dir: Path):
    """Phase 8: Fuse general SFT weights into final model."""
    _update_phase(run_id, "fuse_sft", "running", "Fusing general SFT weights into final model...")

    self_model_dir = run_dir / "self_model"
    sft_weights = run_dir / "sft_weights"
    final_dir = run_dir / "final_model"

    try:
        result = subprocess.run(
            ["python3", "-m", "mlx_lm", "fuse",
             "--model", str(self_model_dir),
             "--adapter-path", str(sft_weights),
             "--save-path", str(final_dir)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Fuse failed: {result.stderr[:500]}")
        _update_phase(run_id, "fuse_sft", "completed", f"Final model at {final_dir.name}")
    except Exception as e:
        _update_phase(run_id, "fuse_sft", "failed", str(e))
        raise


def _run_phase_eval(run_id: str, config: Dict, run_dir: Path):
    """Phase 9: Run knowledge retention evals on base vs self vs final."""
    _update_phase(run_id, "eval", "running", "Running knowledge retention evals...")

    base_model = str(ROOT / config["base_model"])
    self_model = run_dir / "self_model"
    final_model = run_dir / "final_model"

    # Models to compare — always include base + self_model
    models = [
        f"mlx:{base_model}",
        f"mlx:{self_model}",
    ]
    # Add final model only if Layer 3 was run
    if final_model.exists():
        models.append(f"mlx:{final_model}")

    results = {}
    try:
        from eval.evals import run_eval
        from eval.runner import clear_mlx_cache

        for model_path in models:
            if "self_model" in model_path:
                label = "self"
            elif "final_model" in model_path:
                label = "final"
            else:
                label = "base"
            _update_phase(run_id, "eval", "running", f"Evaluating {label} model...")

            model_results = {}

            # Run knowledge_retention eval
            kr = run_eval("knowledge_retention", save=True, model=model_path)
            model_results["knowledge_retention"] = {
                "score": kr.get("score", 0),
                "passed": kr.get("passed", 0),
                "total": kr.get("total", 0),
                "status": kr.get("status", "error"),
                "details": kr.get("details", []),
            }

            # Run identity_persistence eval
            try:
                ip = run_eval("identity_persistence", save=True, model=model_path)
                model_results["identity_persistence"] = {
                    "score": ip.get("score", 0),
                    "passed": ip.get("passed", 0),
                    "total": ip.get("total", 0),
                    "status": ip.get("status", "error"),
                }
            except Exception as e:
                model_results["identity_persistence"] = {"score": 0, "status": "error", "error": str(e)}

            results[label] = model_results

            # Clear cache between models to free memory
            clear_mlx_cache()

        # Save results to status
        eval_summary = {
            "models": results,
            "improvement": {},
        }

        # Calculate improvement across layers
        if "base" in results and "self" in results:
            for eval_name in results["base"]:
                base_score = results["base"][eval_name].get("score", 0)
                self_score = results["self"][eval_name].get("score", 0)
                entry = {
                    "base_score": base_score,
                    "self_score": self_score,
                    "delta_base_to_self": round(self_score - base_score, 3),
                }
                if "final" in results and eval_name in results["final"]:
                    final_score = results["final"][eval_name].get("score", 0)
                    entry["final_score"] = final_score
                    entry["delta_self_to_final"] = round(final_score - self_score, 3)
                    entry["delta_base_to_final"] = round(final_score - base_score, 3)
                eval_summary["improvement"][eval_name] = entry

        status = _read_status(run_id)
        status["results"] = eval_summary
        _write_status(run_id, status)
        _update_phase(run_id, "eval", "completed", "Eval complete")

    except Exception as e:
        _update_phase(run_id, "eval", "failed", str(e))
        raise


# ── Training Subprocess Helper ──────────────────────────────────────────

def _run_training_subprocess(run_id: str, phase_id: str, cmd: List[str], log_file: Path):
    """Run an mlx_lm training command, streaming output to log file and updating status."""
    try:
        with open(log_file, "w") as lf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            last_update = 0.0
            for line in proc.stdout:
                lf.write(line)
                lf.flush()

                # Update status periodically (every 10 seconds)
                now = time.time()
                if now - last_update > 10:
                    # Parse current iteration from output
                    m = re.match(r'Iter\s+(\d+):', line)
                    if m:
                        current_iter = int(m.group(1))
                        # Determine total iters for this phase
                        status = _read_status(run_id)
                        config = status["config"] if status else {}
                        total_iters = config.get(f"{phase_id}_iters", 0)
                        pct = f"{current_iter}/{total_iters}" if total_iters else str(current_iter)
                        _update_phase(run_id, phase_id, "running", f"Iter {pct}", current_iter=current_iter)
                    last_update = now

            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"Training failed with exit code {proc.returncode}")

        # Parse final loss values
        loss_data = _parse_training_log(log_file)
        final_loss = loss_data[-1]["train_loss"] if loss_data else None
        detail = f"Completed. Final loss: {final_loss:.4f}" if final_loss else "Completed"
        _update_phase(run_id, phase_id, "completed", detail, loss_curve=loss_data)

    except Exception as e:
        _update_phase(run_id, phase_id, "failed", str(e))
        raise


# ── Listing / Querying ──────────────────────────────────────────────────

def list_runs() -> List[Dict[str, Any]]:
    """List all T3 experiment runs."""
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        status_file = d / "status.json"
        if status_file.exists():
            try:
                s = json.loads(status_file.read_text())
                runs.append({
                    "run_id": s["run_id"],
                    "status": s["status"],
                    "current_phase": s.get("current_phase"),
                    "created_at": s.get("created_at"),
                    "completed_at": s.get("completed_at"),
                    "has_results": s.get("results") is not None,
                })
            except Exception:
                pass
    return runs


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Get full status of a T3 run."""
    return _read_status(run_id)


def get_training_curves(run_id: str) -> Dict[str, List[Dict]]:
    """Get training loss curves for a run."""
    run_dir = RUNS_DIR / run_id
    curves = {}

    pretrain_log = run_dir / "pretrain_training.log"
    if pretrain_log.exists():
        curves["pretrain"] = _parse_training_log(pretrain_log)

    sft_log = run_dir / "sft_training.log"
    if sft_log.exists():
        curves["sft"] = _parse_training_log(sft_log)

    return curves
