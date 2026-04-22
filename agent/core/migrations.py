"""
Schema Migrations
=================
Single function that brings any database (state.db or state_demo.db)
up to the current schema.  Every call is idempotent — safe to run on
every startup and on every mode toggle.

All init functions already use CREATE TABLE IF NOT EXISTS and guard
ALTER TABLE ADD COLUMN with try/except, so calling them twice is free.
"""

import os
import sqlite3
from contextlib import closing


def ensure_all_schemas() -> None:
    """
    Sync schema on BOTH databases (state.db and state_demo.db),
    regardless of which mode is currently active.  Schema only — no data.
    """
    from data.db import get_db_path, STATE_DB, DEMO_DB

    active = get_db_path()

    # Sync the active DB first
    ensure_schema()

    # Sync the other DB by temporarily pointing STATE_DB_PATH at it
    other = DEMO_DB if active.resolve() == STATE_DB.resolve() else STATE_DB
    if other.exists():
        old_env = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = str(other)
        try:
            ensure_schema()
        except Exception as exc:
            try:
                from agent.threads.log.schema import log_event
                log_event(
                    event_type="warn:demo_db_stale",
                    data=f"Secondary DB schema sync failed: {exc}",
                    metadata={"db": str(other), "error": str(exc)},
                    source="migrations",
                )
            except Exception:
                pass
        finally:
            if old_env is None:
                os.environ.pop("STATE_DB_PATH", None)
            else:
                os.environ["STATE_DB_PATH"] = old_env


def ensure_schema() -> None:
    """
    Run all table-creation and column-migration logic against the
    currently-active database.  Each module is wrapped individually
    so one failure doesn't block the rest.
    """
    from data.db import get_connection

    errors: list[str] = []

    def _try(label: str, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            errors.append(f"{label}: {e}")

    # -- Identity (order matters: types → profiles → facts) ----------------
    _try("identity/profile_types", _init_identity)

    # -- Philosophy --------------------------------------------------------
    _try("philosophy", _init_philosophy)

    # -- Linking Core ------------------------------------------------------
    _try("linking_core", _init_linking_core)

    # -- Log ---------------------------------------------------------------
    _try("log", _init_log)

    # -- Temp memory -------------------------------------------------------
    _try("temp_memory", _init_temp_memory)

    # -- Chat --------------------------------------------------------------
    _try("chat", _init_chat)

    # -- Workspace ---------------------------------------------------------
    _try("workspace", _init_workspace)

    # -- Form tools --------------------------------------------------------
    _try("form_tools", _init_form_tools)

    # -- Secrets -----------------------------------------------------------
    _try("secrets", _init_secrets)

    # -- Reflex triggers ---------------------------------------------------
    _try("reflex", _init_reflex)

    # -- Tool traces -------------------------------------------------------
    _try("tool_traces", _init_tool_traces)

    # -- Training templates ------------------------------------------------
    _try("training_templates", _init_training_templates)

    # -- Tables without exported init functions (inlined) ------------------
    _try("memory_loop_state", _init_memory_loop_state)
    _try("custom_loops", _init_custom_loops)
    _try("service_config", _init_service_config)

    if errors:
        import sys
        for e in errors:
            print(f"[ensure_schema] {e}", file=sys.stderr)
        # Log schema drift events
        try:
            from agent.threads.log.schema import log_event
            for e in errors:
                log_event(
                    event_type="error:schema_drift",
                    data=f"Migration failed: {e}",
                    metadata={"error": e, "db": str(get_db_path())},
                    source="migrations",
                )
        except Exception:
            pass  # Log table may not exist yet during first boot


# ── Thin wrappers (lazy imports to avoid circular deps) ──────────────────

def _init_identity():
    from agent.threads.identity.schema import (
        init_profile_types, init_profiles, init_fact_types, init_profile_facts
    )
    init_profile_types()
    init_profiles()
    init_fact_types()
    init_profile_facts()


def _init_philosophy():
    from agent.threads.philosophy.schema import (
        init_philosophy_profile_types, init_philosophy_profiles,
        init_philosophy_fact_types, init_philosophy_profile_facts
    )
    init_philosophy_profile_types()
    init_philosophy_profiles()
    init_philosophy_fact_types()
    init_philosophy_profile_facts()


def _init_linking_core():
    from agent.threads.linking_core.schema import (
        init_concept_links_table, init_cooccurrence_table
    )
    init_concept_links_table()
    init_cooccurrence_table()


def _init_log():
    from agent.threads.log.schema import (
        init_event_log_table, init_system_log_table,
        init_server_log_table, init_log_module_table,
        init_function_log_table,
        init_llm_inference_table, init_activation_log_table,
        init_loop_run_table,
    )
    init_event_log_table()
    init_system_log_table()
    init_server_log_table()
    init_function_log_table()
    init_llm_inference_table()
    init_activation_log_table()
    init_loop_run_table()
    init_log_module_table("events")
    init_log_module_table("sessions")


def _init_temp_memory():
    from agent.subconscious.temp_memory.store import _ensure_table
    _ensure_table()


def _init_chat():
    from chat.schema import init_convos_tables
    init_convos_tables()


def _init_workspace():
    from workspace.schema import init_workspace_tables
    init_workspace_tables()


def _init_form_tools():
    from agent.threads.form.schema import init_form_tools_table
    init_form_tools_table()


def _init_secrets():
    from agent.core.secrets import init_secrets_table
    init_secrets_table()


def _init_reflex():
    from agent.threads.reflex.schema import (
        init_triggers_table,
        init_meta_thoughts_table,
    )
    init_triggers_table()
    init_meta_thoughts_table()


# ── Inlined for tables with no exported init function ────────────────────

def _init_memory_loop_state():
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_loop_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


def _init_custom_loops():
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_loops (
                name TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT 'temp_memory',
                interval_seconds REAL NOT NULL DEFAULT 300,
                model TEXT,
                prompt TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def _init_service_config():
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_config (
                service_id TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                settings_json TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def _init_tool_traces():
    """Tool execution traces with weights for STATE visibility."""
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                output TEXT,
                weight REAL NOT NULL DEFAULT 0.5,
                duration_ms INTEGER DEFAULT 0,
                session_id TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_traces_weight
            ON tool_traces(weight DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_traces_created
            ON tool_traces(created_at DESC)
        """)
        conn.commit()


def _init_training_templates():
    """Training data format templates — edit once, regenerate all examples."""
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                section TEXT NOT NULL,
                name TEXT NOT NULL,
                question_template TEXT NOT NULL,
                answer_template TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(module, section, name)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_training_templates_module
            ON training_templates(module, section)
        """)
        conn.commit()
