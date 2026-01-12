from fastapi import APIRouter, HTTPException
import sqlite3
import json
from pathlib import Path

router = APIRouter(prefix="/api/database", tags=["database"])

# Database path - adjust based on your structure
DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "db" / "state.db"

def get_db_connection():
    """Create database connection"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

@router.get("/tables")
async def get_tables():
    """Get list of all tables in the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tables: {str(e)}")


@router.get("/threads-summary")
async def get_threads_summary():
    """Get a summary of all threads and their modules with row counts.
    
    This is the main endpoint for the frontend to understand what data exists.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all registered threads and modules
        cursor.execute("""
            SELECT thread_name, module_name FROM threads_registry 
            ORDER BY thread_name, module_name;
        """)
        registry = cursor.fetchall()
        
        summary = {}
        for row in registry:
            thread_name = row["thread_name"]
            module_name = row["module_name"]
            table_name = f"{thread_name}_{module_name}"
            
            if thread_name not in summary:
                summary[thread_name] = {"modules": [], "total_rows": 0}
            
            # Get row count for this module
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
                count = cursor.fetchone()["cnt"]
            except Exception:
                count = 0
            
            summary[thread_name]["modules"].append(module_name)
            summary[thread_name]["total_rows"] += count
        
        conn.close()
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching threads summary: {str(e)}")


@router.get("/thread/{thread_name}")
async def get_thread_data(thread_name: str, context_level: int = 2):
    """Get all data for a specific thread at given context level.
    
    Args:
        thread_name: Thread name (identity, log, form, philosophy, reflex)
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get modules for this thread
        cursor.execute("""
            SELECT module_name FROM threads_registry 
            WHERE thread_name = ? ORDER BY module_name;
        """, (thread_name,))
        modules = [row[0] for row in cursor.fetchall()]
        
        if not modules:
            raise HTTPException(status_code=404, detail=f"Thread '{thread_name}' not found")
        
        data = []
        for module in modules:
            table_name = f"{thread_name}_{module}"
            try:
                cursor.execute(f"""
                    SELECT key, metadata_json, data_json, level, weight, updated_at
                    FROM {table_name} 
                    WHERE level <= ?
                    ORDER BY weight DESC, key
                """, (context_level,))
                rows = cursor.fetchall()
                
                for row in rows:
                    data.append({
                        "module": module,
                        "key": row["key"],
                        "context_level": row["level"],
                        "level_label": f"L{row['level']}",
                        "data": json.loads(row["data_json"]) if row["data_json"] else {},
                        "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                        "weight": row["weight"],
                        "updated_at": row["updated_at"]
                    })
            except Exception:
                pass
        
        conn.close()
        return {"thread": thread_name, "context_level": context_level, "modules": modules, "data": data}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching thread data: {str(e)}")


@router.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        conn.close()
        
        schema = [
            {
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": col[3],
                "default_value": col[4],
                "pk": col[5]
            }
            for col in columns
        ]
        
        return {"table": table_name, "columns": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching schema: {str(e)}")

@router.get("/records/{table_name}")
async def get_table_records(table_name: str, limit: int = 100, context_level: int = 2):
    """Get records from a specific table.
    
    Args:
        table_name: Name of the table to query
        limit: Maximum records to return
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    Returns only the data for the requested context level.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Map context level to column name
        level_col_map = {1: "data_l1_json", 2: "data_l2_json", 3: "data_l3_json"}
        level_col = level_col_map.get(context_level, "data_l2_json")
        
        # For identity_sections, return only the requested context level
        if table_name == "identity_sections":
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = {
                    "key": row["key"],
                    "context_level": context_level,
                    "data": json.loads(row[level_col]),
                    "metadata": json.loads(row["metadata_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                records.append(record)
            
            conn.close()
            return {"table": table_name, "records": records, "count": len(records), "context_level": context_level}
        
        elif table_name == "identity_meta":
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = {
                    "key": row["key"],
                    "context_level": context_level,
                    "data": json.loads(row[level_col]),
                    "metadata": json.loads(row["metadata_json"]),
                    "updated_at": row["updated_at"]
                }
                records.append(record)
            
            conn.close()
            return {"table": table_name, "records": records, "count": len(records), "context_level": context_level}
        
        else:
            # Generic query for other tables
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            records = [dict(row) for row in rows]
            conn.close()
            return {"table": table_name, "records": records, "count": len(records)}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching records: {str(e)}")

@router.get("/identity-hea")
async def get_identity_hea(context_level: int = 2):
    """Get identity data formatted for HEA table display.
    
    Uses the new thread schema (identity_user_profile, identity_nola_self, etc.)
    
    Args:
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    Returns only the data at or below the requested context level.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all identity modules from threads_registry
        cursor.execute("""
            SELECT module_name FROM threads_registry 
            WHERE thread_name = 'identity' ORDER BY module_name;
        """)
        modules = [row[0] for row in cursor.fetchall()]
        
        level_label = f"L{context_level}"
        hea_data = []
        
        for module in modules:
            table_name = f"identity_{module}"
            try:
                # Get rows at or below the requested level
                cursor.execute(f"""
                    SELECT key, metadata_json, data_json, level, weight, updated_at
                    FROM {table_name} 
                    WHERE level <= ?
                    ORDER BY weight DESC, key
                """, (context_level,))
                rows = cursor.fetchall()
                
                for row in rows:
                    hea_data.append({
                        "module": module,
                        "key": row["key"],
                        "context_level": row["level"],
                        "level_label": f"L{row['level']}",
                        "data": json.loads(row["data_json"]) if row["data_json"] else {},
                        "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                        "weight": row["weight"],
                        "updated_at": row["updated_at"]
                    })
            except Exception:
                # Table might not exist yet
                pass
        
        conn.close()
        return {"thread": "identity", "context_level": context_level, "data": hea_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching HEA data: {str(e)}")


@router.get("/identity/{module_key}")
async def get_identity_module(module_key: str, context_level: int = 2):
    """Get data for a specific identity module at a given context level.
    
    Uses new thread schema (identity_{module_key} tables).
    
    Args:
        module_key: Module name (user_profile, nola_self, machine_context)
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    Returns all rows for the requested module at or below the context level.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        table_name = f"identity_{module_key}"
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?;
        """, (table_name,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail=f"Module '{module_key}' not found")
        
        # Get rows at or below the requested level
        cursor.execute(f"""
            SELECT key, metadata_json, data_json, level, weight, updated_at
            FROM {table_name} 
            WHERE level <= ?
            ORDER BY weight DESC, key
        """, (context_level,))
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append({
                "key": row["key"],
                "level": row["level"],
                "data": json.loads(row["data_json"]) if row["data_json"] else {},
                "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                "weight": row["weight"],
                "updated_at": row["updated_at"]
            })
        
        return {
            "module": module_key,
            "context_level": context_level,
            "level_label": f"L{context_level}",
            "rows": data,
            "count": len(data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching module data: {str(e)}")


@router.get("/identity-changes")
async def get_identity_changes(context_level: int = 2, limit: int = 50):
    """Get tracked changes to identity data over time.
    
    Args:
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
        limit: Maximum number of changes to return
    
    Returns list of changes showing what was modified and when.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if the identity_changes table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='identity_changes';
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Create the table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS identity_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    module TEXT NOT NULL,
                    field TEXT NOT NULL,
                    old_value_json TEXT,
                    new_value_json TEXT,
                    context_level INTEGER DEFAULT 2,
                    change_type TEXT DEFAULT 'update'
                );
            """)
            conn.commit()
            conn.close()
            return {"changes": [], "count": 0, "context_level": context_level}
        
        # Query changes for the specified context level
        cursor.execute("""
            SELECT * FROM identity_changes 
            WHERE context_level = ?
            ORDER BY timestamp DESC
            LIMIT ?;
        """, (context_level, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        changes = []
        for row in rows:
            changes.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "module": row["module"],
                "field": row["field"],
                "oldValue": json.loads(row["old_value_json"]) if row["old_value_json"] else None,
                "newValue": json.loads(row["new_value_json"]) if row["new_value_json"] else None,
                "context_level": row["context_level"],
                "change_type": row["change_type"]
            })
        
        return {"changes": changes, "count": len(changes), "context_level": context_level}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching changes: {str(e)}")


@router.get("/events")
async def get_events(
    event_type: str = None,
    session_id: str = None,
    source: str = None,
    limit: int = 100
):
    """Get logged events from the database.
    
    Events are the 'where and when' timeline - lightweight markers of:
    - system:startup, system:shutdown
    - conversation:start, conversation:end
    - memory:extract, memory:consolidate
    - identity:push, identity:pull
    - errors
    
    Args:
        event_type: Filter to specific event type (optional)
        session_id: Filter to specific session (optional)
        source: Filter to specific component (optional)
        limit: Maximum events to return
    
    Returns most recent events first.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if events table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='events';
        """)
        if not cursor.fetchone():
            conn.close()
            return {"events": [], "count": 0, "message": "No events table yet"}
        
        # Build query with filters
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            events.append({
                "id": row["id"],
                "timestamp": row["ts"],
                "level": row["level"],
                "source": row["source"],
                "event_type": row["event_type"],
                "message": row["message"],
                "session_id": row["session_id"],
                "payload": json.loads(row["payload_json"]) if row["payload_json"] else {}
            })
        
        return {"events": events, "count": len(events)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")


@router.get("/events/stats")
async def get_event_stats():
    """Get statistics about logged events.
    
    Returns counts by event_type, recent sessions, and date range.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if events table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='events';
        """)
        if not cursor.fetchone():
            conn.close()
            return {"total": 0, "by_type": {}, "sessions": [], "message": "No events table yet"}
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]
        
        # Count by type
        cursor.execute("""
            SELECT event_type, COUNT(*) as cnt 
            FROM events 
            GROUP BY event_type 
            ORDER BY cnt DESC
        """)
        by_type = {row["event_type"]: row["cnt"] for row in cursor.fetchall()}
        
        # Recent sessions
        cursor.execute("""
            SELECT DISTINCT session_id, MIN(ts) as started, COUNT(*) as events
            FROM events 
            WHERE session_id IS NOT NULL
            GROUP BY session_id
            ORDER BY started DESC
            LIMIT 10
        """)
        sessions = [
            {"session_id": row["session_id"], "started": row["started"], "events": row["events"]}
            for row in cursor.fetchall()
        ]
        
        # Date range
        cursor.execute("SELECT MIN(ts), MAX(ts) FROM events")
        row = cursor.fetchone()
        date_range = {"min": row[0], "max": row[1]}
        
        conn.close()
        
        return {
            "total": total,
            "by_type": by_type,
            "sessions": sessions,
            "date_range": date_range
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching event stats: {str(e)}")
