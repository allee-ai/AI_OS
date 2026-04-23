"""
finetune/_api_templates.py
==========================
Extracted from finetune/api.py to keep the main router file under the
soft 1500-LOC ceiling. This module imports the shared `router` object
from finetune.api and registers its route handlers against it. Loading
this module is a side-effect: it MUST be imported from finetune/api.py
at the bottom so FastAPI sees the registrations.

Routes registered here:
  /api/finetune/templates*                    (CRUD + seed + preview)
  /api/finetune/build-state                   (state-on-demand helper)
  /api/finetune/general-knowledge/*           (topic scanner + examples CRUD)

Do not import this module from outside the finetune package.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

from .api import router


# ─────────────────────────────────────────────────────────────
# Training Templates — CRUD + Seed
# ─────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    module: str
    section: str
    name: str
    question_template: str
    answer_template: str


class TemplateUpdate(BaseModel):
    question_template: Optional[str] = None
    answer_template: Optional[str] = None
    enabled: Optional[bool] = None
    name: Optional[str] = None


@router.get("/templates")
async def list_templates(module: Optional[str] = None, section: Optional[str] = None):
    """List training templates, optionally filtered by module/section."""
    from data.db import get_connection
    from contextlib import closing

    query = "SELECT id, module, section, name, question_template, answer_template, enabled, created_at, updated_at FROM training_templates WHERE 1=1"
    params: list = []
    if module:
        query += " AND module = ?"
        params.append(module)
    if section:
        query += " AND section = ?"
        params.append(section)
    query += " ORDER BY module, section, id"

    with closing(get_connection(readonly=True)) as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        rows = conn.execute(query, params).fetchall()
    return {"templates": rows}


@router.get("/templates/{template_id}")
async def get_template(template_id: int):
    """Get a single template by ID."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection(readonly=True)) as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        row = conn.execute(
            "SELECT id, module, section, name, question_template, answer_template, enabled, created_at, updated_at FROM training_templates WHERE id = ?",
            (template_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"template": row}


@router.post("/templates")
async def create_template(body: TemplateCreate):
    """Create a new training template."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection()) as conn:
        try:
            cur = conn.execute(
                """INSERT INTO training_templates (module, section, name, question_template, answer_template)
                   VALUES (?, ?, ?, ?, ?)""",
                (body.module, body.section, body.name, body.question_template, body.answer_template),
            )
            conn.commit()
            template_id = cur.lastrowid
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=409, detail=f"Template '{body.name}' already exists for {body.module}/{body.section}")
            raise HTTPException(status_code=500, detail=str(e))
    return {"id": template_id, "status": "created"}


@router.put("/templates/{template_id}")
async def update_template(template_id: int, body: TemplateUpdate):
    """Update a training template."""
    from data.db import get_connection
    from contextlib import closing

    fields = []
    params: list = []
    if body.question_template is not None:
        fields.append("question_template = ?")
        params.append(body.question_template)
    if body.answer_template is not None:
        fields.append("answer_template = ?")
        params.append(body.answer_template)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)
    if body.name is not None:
        fields.append("name = ?")
        params.append(body.name)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields.append("updated_at = datetime('now')")
    params.append(template_id)

    with closing(get_connection()) as conn:
        result = conn.execute(
            f"UPDATE training_templates SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "updated", "id": template_id}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int):
    """Delete a training template."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection()) as conn:
        result = conn.execute("DELETE FROM training_templates WHERE id = ?", (template_id,))
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "id": template_id}


# ── Default linking_core templates (for seed) ───────────────────────

_DEFAULT_TEMPLATES = [
    {
        "module": "linking_core",
        "section": "data",
        "name": "association",
        "question_template": "What's related to {concept_a}?",
        "answer_template": (
            "My linking_core graph has {concept_a} ↔ {concept_b} "
            "(strength: {strength:.2f}, fired {fire_count} times). "
            "This is a LONG-potentiated link — it's been reinforced enough "
            "to persist in long-term memory."
        ),
    },
    {
        "module": "linking_core",
        "section": "data",
        "name": "spread_activation",
        "question_template": "What connects to {seed} in your mind?",
        "answer_template": (
            "Spread activation from '{seed}' reaches: {chain}. "
            "These are the concepts that light up through my Hebbian graph — "
            "each hop follows the strongest links first."
        ),
    },
]


@router.post("/templates/seed")
async def seed_default_templates():
    """Seed the database with default templates (skips existing)."""
    from data.db import get_connection
    from contextlib import closing

    created = 0
    skipped = 0
    with closing(get_connection()) as conn:
        for tpl in _DEFAULT_TEMPLATES:
            existing = conn.execute(
                "SELECT id FROM training_templates WHERE module = ? AND section = ? AND name = ?",
                (tpl["module"], tpl["section"], tpl["name"]),
            ).fetchone()
            if existing:
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO training_templates (module, section, name, question_template, answer_template)
                   VALUES (?, ?, ?, ?, ?)""",
                (tpl["module"], tpl["section"], tpl["name"], tpl["question_template"], tpl["answer_template"]),
            )
            created += 1
        conn.commit()
    return {"created": created, "skipped": skipped, "total_defaults": len(_DEFAULT_TEMPLATES)}


# ── Preview template with sample data ────────────────────────────────

@router.post("/templates/{template_id}/preview")
async def preview_template(template_id: int, limit: int = 3):
    """Preview what a template produces with real data from the module."""
    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection(readonly=True)) as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        tpl = conn.execute(
            "SELECT * FROM training_templates WHERE id = ?", (template_id,)
        ).fetchone()

    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    previews = []
    if tpl["module"] == "linking_core" and tpl["section"] == "data":
        if tpl["name"] == "association":
            from agent.threads.linking_core.schema import get_long_links
            links = get_long_links(limit=limit)
            for link in links:
                try:
                    q = tpl["question_template"].format_map(link)
                    a = tpl["answer_template"].format_map(link)
                    previews.append({"user": q, "assistant": a, "data": link})
                except (KeyError, ValueError) as e:
                    previews.append({"error": str(e), "data": link})
        elif tpl["name"] == "spread_activation":
            from agent.threads.linking_core.schema import get_long_links, spread_activate
            links = get_long_links(limit=30)
            seeds = list(set([l["concept_a"] for l in links]))[:limit]
            for seed in seeds:
                activated = spread_activate([seed], activation_threshold=0.3, max_hops=2, limit=5)
                if activated:
                    row = {"seed": seed, "chain": ", ".join([a["concept"] for a in activated])}
                    try:
                        q = tpl["question_template"].format_map(row)
                        a = tpl["answer_template"].format_map(row)
                        previews.append({"user": q, "assistant": a, "data": row})
                    except (KeyError, ValueError) as e:
                        previews.append({"error": str(e), "data": row})

    return {"template": tpl, "previews": previews}


# ─────────────────────────────────────────────────────────────
# On-demand STATE builder — per-example toggle
# ─────────────────────────────────────────────────────────────

class BuildStateRequest(BaseModel):
    query: str


@router.post("/build-state")
async def build_state_for_example(body: BuildStateRequest):
    """Build STATE system prompt on demand for a given query."""
    try:
        from agent.subconscious.orchestrator import build_state
        state = build_state(body.query)
        return {"state": state}
    except Exception as e:
        return {"state": f"== STATE ==\n[error] {e}\n== END STATE ==", "error": str(e)}


# ─────────────────────────────────────────────────────────────
# General Knowledge — topic scanner + training data CRUD
# ─────────────────────────────────────────────────────────────

@router.get("/general-knowledge/topics")
async def gk_list_topics():
    """Fast list of all topics with example counts (no codebase scan)."""
    from finetune.general_knowledge import get_all_topics_summary
    return {"topics": get_all_topics_summary()}


@router.get("/general-knowledge/scan")
async def gk_scan_codebase():
    """Full codebase scan — returns topics with file match counts."""
    from finetune.general_knowledge import scan_codebase
    topics = scan_codebase()
    return {"topics": topics}


@router.get("/general-knowledge/topics/{topic_id}/examples")
async def gk_get_examples(topic_id: str):
    """Get all training examples for a topic."""
    from finetune.general_knowledge import get_topic_examples, TOPIC_MAP
    if topic_id not in TOPIC_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id}")
    return {"topic": topic_id, "examples": get_topic_examples(topic_id)}


class GKExampleBody(BaseModel):
    messages: list


@router.post("/general-knowledge/topics/{topic_id}/examples")
async def gk_add_example(topic_id: str, body: GKExampleBody):
    """Add a training example to a topic."""
    from finetune.general_knowledge import save_topic_example, TOPIC_MAP
    if topic_id not in TOPIC_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id}")
    result = save_topic_example(topic_id, {"messages": body.messages})
    return result


@router.put("/general-knowledge/topics/{topic_id}/examples/{index}")
async def gk_update_example(topic_id: str, index: int, body: GKExampleBody):
    """Update a training example by index."""
    from finetune.general_knowledge import update_topic_example, TOPIC_MAP
    if topic_id not in TOPIC_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id}")
    try:
        result = update_topic_example(topic_id, index, {"messages": body.messages})
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/general-knowledge/topics/{topic_id}/examples/{index}")
async def gk_delete_example(topic_id: str, index: int):
    """Delete a training example by index."""
    from finetune.general_knowledge import delete_topic_example, TOPIC_MAP
    if topic_id not in TOPIC_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id}")
    try:
        result = delete_topic_example(topic_id, index)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
