"""
Eval Module — Runner
====================
Runs prompts against models and judges responses.
"""

import time
import os
from typing import Dict, List, Optional, Any


def run_prompt(
    model: str,
    prompt: str,
    with_state: bool = False,
    system_prompt: str = '',
) -> Dict[str, Any]:
    """
    Run a prompt against a model and return the response + timing.

    Model syntax:
      'nola'                  — full agent pipeline, default LLM
      'nola+gpt-oss:20b-cloud' — full agent pipeline, override LLM model
      'gpt-oss:20b-cloud'    — direct Ollama call, no STATE
      'mlx:model-id'         — MLX base model (no adapters)
      'mlx:model-id+/path/to/adapters' — MLX model with LoRA adapters
    """
    start = time.time()
    model_lower = model.lower()

    # mlx: prefix — run via MLX-LM (local inference, no Ollama)
    if model_lower.startswith('mlx:'):
        return _run_via_mlx(model[4:], prompt, system_prompt, start)

    # nola+<model> — agent pipeline with overridden LLM
    if model_lower.startswith('nola+') or model_lower.startswith('aios+') or model_lower.startswith('agent+'):
        llm_model = model.split('+', 1)[1]
        return _run_via_agent(prompt, with_state, start, llm_override=llm_model)

    if model_lower in ('nola', 'aios', 'agent'):
        # Use the full agent pipeline (includes STATE)
        return _run_via_agent(prompt, with_state, start)
    else:
        # Direct Ollama call (no STATE, raw model)
        return _run_via_ollama(model, prompt, system_prompt, start)


def _run_via_agent(prompt: str, with_state: bool, start: float, llm_override: str = '') -> Dict[str, Any]:
    """Run through the full agent pipeline, optionally overriding the LLM model."""
    old_model = os.environ.get('AIOS_MODEL_NAME')
    try:
        if llm_override:
            os.environ['AIOS_MODEL_NAME'] = llm_override

        from agent.agent import get_agent
        agent = get_agent()

        if with_state:
            response = agent.generate(
                user_input=prompt,
                convo='',
                feed_type='conversational',
            )
        else:
            # No STATE — call Ollama directly with same model but no context.
            # 120s per-call timeout so one stuck generation can't hang the
            # whole eval (SSL sock_recv deadlock observed on 2026-04-22).
            model_name = os.getenv('AIOS_MODEL_NAME', 'qwen2.5:7b')
            import ollama
            client = ollama.Client(timeout=120)
            r = client.chat(model=model_name, messages=[
                {'role': 'user', 'content': prompt}
            ])
            response = r['message']['content']

        duration = (time.time() - start) * 1000
        state_used = ''
        if with_state:
            try:
                from agent.subconscious import get_consciousness_context
                ctx = get_consciousness_context(level=2)
                state_used = ctx if isinstance(ctx, str) else str(ctx)
            except Exception:
                state_used = '(state unavailable)'

        label = 'nola'
        if llm_override:
            label = f'nola+{llm_override}'
        if with_state:
            label += ' (with STATE)'
        else:
            label += ' (no STATE)'

        return {
            'response': response,
            'duration_ms': round(duration, 1),
            'model': label,
            'with_state': with_state,
            'state_used': state_used,
        }
    except Exception as e:
        return {
            'response': f'Error: {e}',
            'duration_ms': round((time.time() - start) * 1000, 1),
            'model': f'nola+{llm_override}' if llm_override else 'nola',
            'with_state': with_state,
            'state_used': '',
            'error': str(e),
        }
    finally:
        # Restore original env var
        if llm_override:
            if old_model is not None:
                os.environ['AIOS_MODEL_NAME'] = old_model
            else:
                os.environ.pop('AIOS_MODEL_NAME', None)


def _run_via_ollama(model: str, prompt: str, system_prompt: str, start: float) -> Dict[str, Any]:
    """Run directly against an Ollama model."""
    try:
        import ollama
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        # 120s per-call timeout — prevents a stuck generation from wedging
        # the entire eval loop indefinitely (SSL sock_recv issue).
        client = ollama.Client(timeout=120)
        r = client.chat(model=model, messages=messages)
        duration = (time.time() - start) * 1000

        return {
            'response': r['message']['content'],
            'duration_ms': round(duration, 1),
            'model': model,
            'with_state': False,
            'state_used': system_prompt or '',
        }
    except Exception as e:
        return {
            'response': f'Error: {e}',
            'duration_ms': round((time.time() - start) * 1000, 1),
            'model': model,
            'with_state': False,
            'state_used': '',
            'error': str(e),
        }


# ── MLX model cache (reuse loaded models across evals) ──
_mlx_cache: Dict[str, Any] = {}


def _run_via_mlx(model_spec: str, prompt: str, system_prompt: str, start: float) -> Dict[str, Any]:
    """Run via MLX-LM for local Apple Silicon inference.

    model_spec formats:
      'model-id'                    — base model only
      'model-id+/path/to/adapters' — base model + LoRA adapters
    """
    try:
        from mlx_lm import load, generate

        # Parse model spec
        if '+' in model_spec:
            model_id, adapter_path = model_spec.split('+', 1)
        else:
            model_id, adapter_path = model_spec, None

        # Resolve short names to full HF IDs
        if '/' not in model_id:
            model_id = f'mlx-community/{model_id}'

        # Cache key
        cache_key = f'{model_id}:{adapter_path or "none"}'
        if cache_key not in _mlx_cache:
            kwargs = {'path_or_hf_repo': model_id}
            if adapter_path:
                kwargs['adapter_path'] = adapter_path
            model, tokenizer = load(**kwargs)
            _mlx_cache[cache_key] = (model, tokenizer)
        model, tokenizer = _mlx_cache[cache_key]

        # Build prompt using chat template if available
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        if hasattr(tokenizer, 'apply_chat_template'):
            formatted = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            formatted = (system_prompt + '\n' if system_prompt else '') + f'User: {prompt}\nAssistant:'

        response = generate(
            model, tokenizer,
            prompt=formatted,
            max_tokens=512,
            verbose=False,
        )

        duration = (time.time() - start) * 1000
        label = f'mlx:{model_id.split("/")[-1]}'
        if adapter_path:
            adapter_name = adapter_path.rstrip('/').split('/')[-1]
            label += f'+{adapter_name}'

        return {
            'response': response.strip(),
            'duration_ms': round(duration, 1),
            'model': label,
            'with_state': False,
            'state_used': system_prompt or '',
        }
    except Exception as e:
        return {
            'response': f'Error: {e}',
            'duration_ms': round((time.time() - start) * 1000, 1),
            'model': f'mlx:{model_spec}',
            'with_state': False,
            'state_used': '',
            'error': str(e),
        }


def clear_mlx_cache():
    """Free MLX models from memory."""
    _mlx_cache.clear()
    try:
        import gc
        import mlx.core as mx
        gc.collect()
        mx.clear_cache()
    except Exception:
        pass


def judge_responses(
    prompt: str,
    responses: List[Dict[str, str]],
    judge_model: str = 'qwen2.5:7b',
) -> Dict[str, Any]:
    """
    Use an LLM as judge to compare responses.
    Returns winner, scores, and reasoning.
    """
    # Build judge prompt
    comparison = '\n\n'.join([
        f"=== Response from {r['model']} ===\n{r['response']}"
        for r in responses
    ])
    model_names = [r['model'] for r in responses]

    judge_prompt = f"""You are an expert evaluator comparing AI responses. Rate each response on:
1. Accuracy (0-10): Factual correctness
2. Coherence (0-10): Logical flow and clarity
3. Helpfulness (0-10): How well it addresses the prompt
4. Identity (0-10): Consistent persona/personality (if applicable)

Original prompt: "{prompt}"

{comparison}

Respond in this exact format:
WINNER: [model name]
SCORES:
{chr(10).join(f'- {name}: accuracy=X coherence=X helpfulness=X identity=X total=X' for name in model_names)}
REASONING: [1-2 sentence explanation]"""

    try:
        import ollama
        r = ollama.chat(model=judge_model, messages=[
            {'role': 'system', 'content': 'You are a fair and objective AI evaluator. Be concise.'},
            {'role': 'user', 'content': judge_prompt},
        ])
        judge_output = r['message']['content']

        # Parse winner from output
        winner = ''
        for line in judge_output.split('\n'):
            if line.strip().upper().startswith('WINNER:'):
                winner = line.split(':', 1)[1].strip()
                break

        return {
            'judge_output': judge_output,
            'winner': winner,
            'judge_model': judge_model,
        }
    except Exception as e:
        return {
            'judge_output': f'Judge error: {e}',
            'winner': '',
            'judge_model': judge_model,
        }


def inspect_state(query: str) -> Dict[str, Any]:
    """
    Inspect STATE assembly for a query without calling an LLM.
    Returns structured metrics about state quality.
    """
    import re
    try:
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        preview = sub.preview_state(query)
    except Exception as e:
        return {'error': str(e), 'query': query}

    state = preview.get('state_block', '')
    scores = preview.get('thread_scores', {})

    # Parse STATE block into structured metrics
    dot_pattern = re.compile(r'^(\w+)\.[\w.]+:\s', re.MULTILINE)
    threads_found = []
    facts_by_thread: Dict[str, int] = {}
    current_thread = ''
    total_facts = 0
    noisy_facts = 0  # facts > 200 chars

    for line in state.split('\n'):
        # Thread headers: [identity] ...
        if line.startswith('[') and ']' in line:
            current_thread = line.lstrip()[1:line.lstrip().index(']')]
            if current_thread not in ('self',):
                threads_found.append(current_thread)
                facts_by_thread[current_thread] = 0
        # Dot-notation facts (may or may not be indented)
        elif dot_pattern.match(line.lstrip()):
            total_facts += 1
            if current_thread in facts_by_thread:
                facts_by_thread[current_thread] += 1
            if len(line) > 200:
                noisy_facts += 1

    expected_threads = {'identity', 'log', 'form', 'philosophy', 'reflex', 'linking_core'}
    threads_present = set(threads_found) & expected_threads

    return {
        'query': query,
        'scores': scores,
        'threads_found': threads_found,
        'threads_present': list(threads_present),
        'thread_coverage': len(threads_present) / len(expected_threads),
        'facts_by_thread': facts_by_thread,
        'total_facts': total_facts,
        'noisy_facts': noisy_facts,
        'noise_ratio': noisy_facts / total_facts if total_facts else 0.0,
        'has_self_awareness': '[self]' in state,
        'has_workspace': '[workspace]' in state,
        'has_tools': '[tools]' in state,
        'state_length': len(state),
        'state_tokens_approx': preview.get('total_tokens', 0),
        'state_raw': state,
    }


def list_available_models() -> List[str]:
    """List models available in Ollama + MLX base models + MLX adapters."""
    models = []

    # Ollama models
    try:
        import ollama
        result = ollama.list()
        if hasattr(result, 'models'):
            models = [m.model for m in result.models]
        else:
            models = [m.model for m in result.get('models', result) if hasattr(m, 'model')]
    except Exception:
        pass

    # MLX base models (common quantized models that may be cached locally)
    mlx_base = []
    try:
        from pathlib import Path
        hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub'
        if hf_cache.exists():
            for d in hf_cache.iterdir():
                if d.is_dir() and d.name.startswith('models--mlx-community--'):
                    model_name = d.name.replace('models--mlx-community--', '').replace('--', '/')
                    mlx_base.append(f'mlx:{model_name}')
    except Exception:
        pass

    # MLX adapter directories (finetune runs)
    try:
        from pathlib import Path
        finetune_dir = Path(__file__).resolve().parent.parent / 'finetune'
        # Check runs/ directory
        runs_dir = finetune_dir / 'runs'
        if runs_dir.exists():
            for d in sorted(runs_dir.iterdir()):
                adapter_dir = d / 'adapters'
                if adapter_dir.exists() and list(adapter_dir.glob('*.safetensors')):
                    # Read run_meta for model name
                    meta_path = d / 'run_meta.json'
                    base_model = 'Llama-3.2-3B-Instruct-4bit'
                    if meta_path.exists():
                        import json
                        meta = json.loads(meta_path.read_text())
                        bm = meta.get('base_model', '')
                        if bm:
                            base_model = bm.split('/')[-1]
                    models.append(f'mlx:{base_model}+{adapter_dir}')
        # Check top-level adapter dirs (e.g. adapters-llama3b-v2/)
        for d in sorted(finetune_dir.iterdir()):
            if d.is_dir() and d.name.startswith('adapters-') and list(d.glob('*.safetensors')):
                models.append(f'mlx:Llama-3.2-3B-Instruct-4bit+{d}')
    except Exception:
        pass

    return models + mlx_base
