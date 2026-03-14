"""
Eval Module — API
=================
FastAPI router for running evaluations and managing benchmarks.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from .schema import (
    init_eval_tables, seed_benchmarks,
    get_benchmarks, create_benchmark, delete_benchmark,
    save_result, get_results, get_result,
    save_comparison, get_comparisons,
    get_runs, get_run,
)
from .runner import run_prompt, judge_responses, list_available_models
from .evals import list_evals, run_eval, run_all, EVAL_REGISTRY

router = APIRouter(prefix="/api/eval", tags=["eval"])


# ── Models ──

class RunRequest(BaseModel):
    prompt: str
    models: List[str]  # e.g. ['nola', 'qwen2.5:7b', 'mistral:7b']
    benchmark_type: str = 'custom'
    with_state: bool = True  # for Nola model
    judge_model: str = 'qwen2.5:7b'
    system_prompt: str = ''  # optional system prompt for comparison models
    benchmark_id: str = ''

class BenchmarkCreate(BaseModel):
    name: str
    type: str  # state_vs_no_state, ai_vs_ai, base_vs_finetuned, adversarial, custom
    description: str = ''
    prompts: List[str]


# ── Endpoints ──

@router.on_event("startup")
async def startup():
    init_eval_tables()
    seed_benchmarks()


@router.get("/models")
async def get_models():
    """List available Ollama models + Nola + nola+cloud combos."""
    models = list_available_models()
    nola_options = ['nola']
    # Add nola+cloud combos for cloud models
    for m in models:
        if m.endswith('-cloud'):
            nola_options.append(f'nola+{m}')
    return {"models": nola_options + models}


@router.post("/run")
async def run_evaluation(req: RunRequest):
    """Run a prompt against multiple models, optionally judge."""
    results = []
    for model in req.models:
        ml = model.lower()
        is_nola = ml in ('nola', 'aios', 'agent') or ml.startswith(('nola+', 'aios+', 'agent+'))
        r = run_prompt(
            model=model,
            prompt=req.prompt,
            with_state=req.with_state if is_nola else False,
            system_prompt=req.system_prompt if not is_nola else '',
        )

        # Save result
        rid = save_result(
            benchmark_type=req.benchmark_type,
            model_name=r['model'],
            prompt=req.prompt,
            response=r['response'],
            with_state=r.get('with_state', False),
            state_used=r.get('state_used', ''),
            duration_ms=r.get('duration_ms', 0),
            benchmark_id=req.benchmark_id,
        )
        r['id'] = rid
        results.append(r)

    # Judge if multiple results
    judge_result = None
    if len(results) > 1:
        judge_result = judge_responses(
            prompt=req.prompt,
            responses=[{'model': r['model'], 'response': r['response']} for r in results],
            judge_model=req.judge_model,
        )

        # Update scores from judge
        for r in results:
            save_result(
                benchmark_type=req.benchmark_type,
                model_name=r['model'],
                prompt=req.prompt,
                response=r['response'],
                with_state=r.get('with_state', False),
                state_used=r.get('state_used', ''),
                score=10.0 if r['model'] == judge_result.get('winner', '') else 5.0,
                judge_model=req.judge_model,
                judge_output=judge_result.get('judge_output', ''),
                duration_ms=r.get('duration_ms', 0),
                benchmark_id=req.benchmark_id,
            )

        # Save comparison
        result_ids = [r['id'] for r in results]
        save_comparison(
            benchmark_type=req.benchmark_type,
            prompt=req.prompt,
            result_ids=result_ids,
            winner=judge_result.get('winner', ''),
            summary=judge_result.get('judge_output', ''),
            judge_model=req.judge_model,
            benchmark_id=req.benchmark_id,
        )

    return {
        "results": results,
        "judge": judge_result,
        "prompt": req.prompt,
        "benchmark_type": req.benchmark_type,
    }


@router.post("/run/state-comparison")
async def run_state_comparison(prompt: str, judge_model: str = 'qwen2.5:7b'):
    """Quick shortcut: run same prompt with and without STATE."""
    # With STATE
    r_state = run_prompt('nola', prompt, with_state=True)
    rid_state = save_result(
        benchmark_type='state_vs_no_state', model_name='nola (with STATE)',
        prompt=prompt, response=r_state['response'],
        with_state=True, state_used=r_state.get('state_used', ''),
        duration_ms=r_state.get('duration_ms', 0),
    )
    r_state['id'] = rid_state

    # Without STATE
    r_no = run_prompt('nola', prompt, with_state=False)
    rid_no = save_result(
        benchmark_type='state_vs_no_state', model_name='nola (no STATE)',
        prompt=prompt, response=r_no['response'],
        with_state=False, duration_ms=r_no.get('duration_ms', 0),
    )
    r_no['id'] = rid_no

    # Judge
    judge_result = judge_responses(
        prompt=prompt,
        responses=[
            {'model': 'nola (with STATE)', 'response': r_state['response']},
            {'model': 'nola (no STATE)', 'response': r_no['response']},
        ],
        judge_model=judge_model,
    )

    save_comparison(
        benchmark_type='state_vs_no_state', prompt=prompt,
        result_ids=[rid_state, rid_no],
        winner=judge_result.get('winner', ''),
        summary=judge_result.get('judge_output', ''),
        judge_model=judge_model,
    )

    return {
        "with_state": r_state,
        "without_state": r_no,
        "judge": judge_result,
    }


# ── Results ──

@router.get("/results")
async def list_results(
    benchmark_type: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """List evaluation results."""
    return {"results": get_results(benchmark_type, model, limit)}


@router.get("/results/{result_id}")
async def get_single_result(result_id: str):
    """Get a single result by ID."""
    r = get_result(result_id)
    if not r:
        raise HTTPException(404, "Result not found")
    return r


# ── Comparisons ──

@router.get("/comparisons")
async def list_comparisons(
    benchmark_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List comparison results."""
    return {"comparisons": get_comparisons(benchmark_type, limit)}


# ── Benchmarks ──

@router.get("/benchmarks")
async def list_benchmarks(benchmark_type: Optional[str] = None):
    """List benchmark prompt sets."""
    return {"benchmarks": get_benchmarks(benchmark_type)}


@router.post("/benchmarks")
async def create_new_benchmark(req: BenchmarkCreate):
    """Create a new benchmark prompt set."""
    return create_benchmark(req.name, req.type, req.description, req.prompts)


@router.delete("/benchmarks/{benchmark_id}")
async def remove_benchmark(benchmark_id: str):
    """Delete a benchmark."""
    if not delete_benchmark(benchmark_id):
        raise HTTPException(404, "Benchmark not found")
    return {"deleted": True}


# ── Structured Evals ──

class EvalRunRequest(BaseModel):
    save: bool = False
    overrides: dict = {}  # e.g. {"model": "mistral:7b", "num_prompts": 5}


class CompareModelsRequest(BaseModel):
    eval_name: str
    models: List[str]  # e.g. ["nola+gpt-oss:20b-cloud", "nola+kimi-k2:1t-cloud"]
    save: bool = False
    overrides: dict = {}


@router.get("/evals")
async def list_available_evals():
    """List all structured evals with their defaults."""
    return {"evals": list_evals()}


@router.post("/evals/{name}/run")
async def run_single_eval(name: str, req: EvalRunRequest):
    """Run a single structured eval."""
    if name not in EVAL_REGISTRY:
        raise HTTPException(404, f"Unknown eval: {name}")
    result = run_eval(name, save=req.save, **req.overrides)
    return result


@router.post("/evals/run-all")
async def run_all_evals(req: EvalRunRequest):
    """Run all structured evals."""
    results = run_all(save=req.save, **req.overrides)
    total_pass = sum(1 for r in results if r.get("status") == "pass")
    avg = sum(r.get("score", 0) for r in results) / len(results) if results else 0
    return {
        "results": results,
        "summary": {"total": len(results), "passed": total_pass, "average_score": round(avg, 3)},
    }


@router.post("/evals/compare-models")
async def compare_models(req: CompareModelsRequest):
    """Run one eval across multiple models. Returns per-model results."""
    if req.eval_name not in EVAL_REGISTRY:
        raise HTTPException(404, f"Unknown eval: {req.eval_name}")

    results = {}
    for model in req.models:
        overrides = {**req.overrides, "model": model}
        result = run_eval(req.eval_name, save=req.save, **overrides)
        results[model] = result

    # Build summary matrix
    summary = {
        "eval_name": req.eval_name,
        "models": req.models,
        "scores": {m: r.get("score", 0) for m, r in results.items()},
        "statuses": {m: r.get("status", "error") for m, r in results.items()},
    }
    return {"results": results, "summary": summary}


@router.post("/evals/compare-all")
async def compare_all_models(req: CompareModelsRequest):
    """Run ALL evals across multiple models. Returns full comparison matrix."""
    matrix = {}
    for eval_name in EVAL_REGISTRY:
        matrix[eval_name] = {}
        for model in req.models:
            overrides = {**req.overrides, "model": model}
            result = run_eval(eval_name, save=req.save, **overrides)
            matrix[eval_name][model] = {
                "score": result.get("score", 0),
                "status": result.get("status", "error"),
                "passed": result.get("passed", 0),
                "total": result.get("total", 0),
            }

    return {
        "matrix": matrix,
        "models": req.models,
        "evals": list(EVAL_REGISTRY.keys()),
    }


@router.get("/runs")
async def list_eval_runs(limit: int = Query(50, ge=1, le=500)):
    """List saved eval run history."""
    return {"runs": get_runs(limit=limit)}


@router.get("/runs/{run_id}")
async def get_eval_run(run_id: str):
    """Get a single eval run by ID."""
    r = get_run(run_id)
    if not r:
        raise HTTPException(404, "Eval run not found")
    return r
