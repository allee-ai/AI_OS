"""Quick test of new log tables + executor hardening."""
from agent.core.migrations import ensure_schema
ensure_schema()
print("Schema synced")

# Test new log tables
from agent.threads.log.schema import log_llm_call, get_llm_calls, get_llm_stats
lid = log_llm_call(model="smol-135m", prompt_tokens=50, completion_tokens=30, latency_ms=120.5, caller="test")
print(f"LLM log created: id={lid}")
calls = get_llm_calls(limit=1)
print(f"LLM calls query: {len(calls)} result(s), model={calls[0]['model']}")
stats = get_llm_stats()
print(f"LLM stats: {stats['total_calls']} calls, {stats['total_tokens']} tokens")

from agent.threads.log.schema import log_activation, get_activations
aid = log_activation(concept_a="coffee", concept_b="morning", activation_type="strengthen", strength_before=0.3, strength_after=0.7, trigger="test")
print(f"Activation log created: id={aid}")
acts = get_activations(concept="coffee", limit=1)
print(f"Activation query: delta={acts[0]['strength_delta']}")

from agent.threads.log.schema import log_loop_run, get_loop_runs, get_loop_stats
rid = log_loop_run(loop_name="memory", duration_ms=450, items_processed=12, items_changed=3)
print(f"Loop run log created: id={rid}")
lstats = get_loop_stats()
print(f"Loop stats: {lstats['total_runs']} runs, loops={[l['loop'] for l in lstats['by_loop']]}")

# Test executor hardening
from agent.threads.form.tools.executor import ToolExecutor
executor = ToolExecutor()

err = executor._validate_params({"a": "x" * 100000})
print(f"Param validation (too large): {err[:50]}...")

err2 = executor._validate_params({"ok": True})
print(f"Param validation (normal): {err2}")

big = "x" * 600000
truncated = executor._truncate_output(big)
print(f"Output truncation: {len(big)} -> {len(truncated)} chars")

print(f"Rate limited (no prior call): {executor._check_rate_limit('test_tool')}")
executor._record_call("test_tool")
print(f"Rate limited (just called): {executor._check_rate_limit('test_tool')}")

print("\nAll tests passed!")
