"""Classify high-degree concepts as scaffolding (LLM meta-language) or real.

Rule of thumb: scaffolding terms describe a system or analysis ABOUT something
(pros_of, cons_of, comparison_to, result_of, agent_*_description) rather than
referring to a real-world entity, person, file, or theme.

Outputs to data/scaffolding_concepts.json. Read-only.
"""
import json
import re
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, ".")
from data.db import get_connection


# Patterns that indicate the concept is the LLM analysing/commenting, not a fact
SCAFFOLD_PATTERNS = [
    re.compile(r"^pros_of_"),
    re.compile(r"^cons_of_"),
    re.compile(r"^benefits_of_"),
    re.compile(r"^reasons_(for|against)_"),
    re.compile(r"^comparison_to_"),
    re.compile(r"^result_of_"),
    re.compile(r"^number_of_"),
    re.compile(r"^action_pushes_to_"),
    re.compile(r"_description$"),
    re.compile(r"_suggestion$"),
    re.compile(r"_status$"),
    re.compile(r"_issue$"),
    re.compile(r"_issues$"),
    re.compile(r"_update$"),
    re.compile(r"_updates$"),
    re.compile(r"_changes$"),
    re.compile(r"_changes_needed$"),
    re.compile(r"_mismatch$"),
    re.compile(r"_cleanup$"),
    re.compile(r"_format$"),
    re.compile(r"_pattern$"),
    re.compile(r"_structure$"),
    re.compile(r"_components$"),
    re.compile(r"_layers$"),
    re.compile(r"_levels$"),
    re.compile(r"^current_(architecture|module|state|file|thread|code)"),
    re.compile(r"^new_(fact|module|tool_process|control_methods|email_needed)"),
    re.compile(r"^old_api_references$"),
    re.compile(r"^functions_to_add$"),
    re.compile(r"^components_to_move$"),
    re.compile(r"^push_changes_to_"),
    re.compile(r"^added_to_gitignore$"),
    re.compile(r"^api_(usage|status|error|tested|key_location|key_reference|directory_cleanup|endpoint_format|endpoint_suggestion|endpoint|update|changes|cleanliness|issue|mismatch)$"),
    re.compile(r"^state_(format|update|management|persistence|consistency|structure|block_format|awareness)$"),
    re.compile(r"^architecture_(test|docs|model|update|real|changes|components)$"),
    re.compile(r"^backend_(api|api_issues|update|structure|frontend_mapping)$"),
    re.compile(r"^frontend_(api_service|update|updates|integration|status|backend_sync|technologies|interface|issue|structure|change|changes|updates_required)$"),
    re.compile(r"^tool_(execution_flow|preference|management|utilization|structure|code_location|rag_index|value_levels|value_layers)$"),
    re.compile(r"^module_(structure|config|creation|functions|updates|flow|based_operations)$"),
    re.compile(r"^thread_(structure|api_suggestion|profiles_page|scoring|summary|names|local_models)$"),
    re.compile(r"^memory_(architecture|consolidation_stats|loop_function|services_removal|node_pattern|layer|system|linking)$"),
    re.compile(r"^agent_(architecture_description|role)$"),
    re.compile(r"^chat_(module|interface|ui)$"),
    re.compile(r"^assistant\.memory\.scope$"),
    re.compile(r"^conversation_state$"),
    re.compile(r"^demo_(flow|db_structure|perception)$"),
    re.compile(r"^github_(issues|update)$"),
    re.compile(r"^manifest_on_shutdown$"),
    re.compile(r"^sync_on_startup$"),
    re.compile(r"^model_(used|control|training|architecture|routing)$"),
    re.compile(r"^local_(ai|llm_integration|setup_required|db_usage|feed_integration|model_size)$"),
    re.compile(r"^read_write_local_db$"),
    re.compile(r"^single_source_of_truth$"),
    re.compile(r"^separation_of_concerns$"),
    re.compile(r"^db_state$"),
    re.compile(r"^server_(needs_restart|port_frontend)$"),
    re.compile(r"^run_(batch_file|script)$"),
    re.compile(r"^vs_code_file$"),
    re.compile(r"^updated_(code|files)$"),
    re.compile(r"^file_(updated|write|structure)$"),
    re.compile(r"^code_(architecture|health_architecture)$"),
    re.compile(r"^per_thread_schemas$"),
    re.compile(r"^batch_model_calls$"),
    re.compile(r"^row_limits_by_model$"),
    re.compile(r"^will_get_forked$"),
    re.compile(r"^viral_demo$"),
    re.compile(r"^business_model$"),
    re.compile(r"^ai_(role|usage|tasks|behavior|system|monopoly_prediction)$"),
    re.compile(r"^uses_(ai|docker)$"),
    re.compile(r"^trusts_ai$"),
    re.compile(r"^human_in_loop$"),
    re.compile(r"^conversation_state$"),
    re.compile(r"^global_state(_structure)?$"),
    re.compile(r"^incremental_state_(update|evolution)$"),
    re.compile(r"^separate_frontend$"),
    re.compile(r"^cons?_of_feature_folder$"),
    re.compile(r"^pros_of_feature_folder$"),
    re.compile(r"^backend_structure$"),
    re.compile(r"^memory_service_issue$"),
    re.compile(r"^new_module$"),
    re.compile(r"^state_manager$"),
    re.compile(r"^profile_(context|structure)$"),
    re.compile(r"^codebase_state$"),
    re.compile(r"^model_agnostic_architecture$"),
    re.compile(r"^benefits_of_model_agnosticism$"),
    re.compile(r"^db_backed_tools$"),
    re.compile(r"^test_tools$"),
    re.compile(r"^feature_tool_builder$"),
    re.compile(r"^reflex_thread(_goal)?$"),
    re.compile(r"^log_thread$"),
    re.compile(r"^current_project$"),  # too generic
    re.compile(r"^user\.general\.(new_fact|test_fact|needs_review|fact)$"),
    re.compile(r"^system\.architecture\."),
]


def is_scaffold(concept: str) -> bool:
    return any(p.search(concept) for p in SCAFFOLD_PATTERNS)


def main():
    out_path = Path("data/scaffolding_concepts.json")

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("""
            WITH degrees AS (
              SELECT concept_a c FROM concept_links
              UNION ALL
              SELECT concept_b c FROM concept_links
            )
            SELECT c, COUNT(*) deg FROM degrees GROUP BY c
            HAVING deg >= 100
            ORDER BY deg DESC
        """)
        candidates = cur.fetchall()

    scaffold = []
    real = []
    for concept, deg in candidates:
        if is_scaffold(concept):
            scaffold.append({"concept": concept, "degree": deg})
        else:
            real.append({"concept": concept, "degree": deg})

    out_path.write_text(json.dumps({
        "rule": "regex over scaffolding prefixes/suffixes",
        "scaffold": scaffold,
        "real": real,
    }, indent=2))

    print(f"high-degree concepts (deg>=100): {len(candidates)}")
    print(f"  caught as scaffold: {len(scaffold)}")
    print(f"  retained as real:   {len(real)}")
    print()
    print("── 25 highest-degree caught as scaffold (would be pruned) ──")
    for s in scaffold[:25]:
        print(f"  deg={s['degree']:>5}  {s['concept']}")
    print()
    print("── 25 highest-degree retained as real ──")
    for r in real[:25]:
        print(f"  deg={r['degree']:>5}  {r['concept']}")
    print()
    print("── retained, lower band (deg 100-300) — sanity check ──")
    lower = [r for r in real if 100 <= r["degree"] <= 300]
    for r in lower[:20]:
        print(f"  deg={r['degree']:>5}  {r['concept']}")


if __name__ == "__main__":
    main()
