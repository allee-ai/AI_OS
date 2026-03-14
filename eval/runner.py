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
    """
    start = time.time()
    model_lower = model.lower()

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
            # No STATE — call Ollama directly with same model but no context
            model_name = os.getenv('AIOS_MODEL_NAME', 'qwen2.5:7b')
            import ollama
            r = ollama.chat(model=model_name, messages=[
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

        r = ollama.chat(model=model, messages=messages)
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
    """List models available in Ollama."""
    try:
        import ollama
        models = ollama.list()
        return [m.model for m in models.get('models', models) if hasattr(m, 'model')]
    except Exception:
        try:
            import ollama
            result = ollama.list()
            if hasattr(result, 'models'):
                return [m.model for m in result.models]
            return []
        except Exception:
            return []
