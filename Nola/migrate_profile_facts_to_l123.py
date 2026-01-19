#!/usr/bin/env python3
"""
Migration script: Add L1/L2/L3 verbosity columns to profile_facts.
Migrates existing 'value' column to l2_value (standard), generates l1 (brief) and l3 (detailed).
"""

import sqlite3
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import Nola.threads.schema as schema


def migrate_profile_facts_to_l123():
    """Migrate existing profile_facts from single value to l1/l2/l3 verbosity levels."""
    conn = schema.get_connection()
    cur = conn.cursor()
    
    # Check if we need migration (old schema has 'value' column)
    cur.execute("PRAGMA table_info(profile_facts)")
    columns = {row[1] for row in cur.fetchall()}
    
    if 'value' in columns:
        print("✓ Found old schema with 'value' column. Starting migration...")
        
        # Get all existing facts
        cur.execute("SELECT profile_id, key, fact_type, value, weight FROM profile_facts")
        old_facts = cur.fetchall()
        
        print(f"  Found {len(old_facts)} facts to migrate")
        
        # Drop old table
        cur.execute("DROP TABLE profile_facts")
        conn.commit()
        print("  Dropped old profile_facts table")
        
        # Create new table with l1/l2/l3 columns
        schema.init_profile_facts(conn)
        print("  Created new profile_facts table with l1/l2/l3 columns")
        
        # Migrate each fact
        for profile_id, key, fact_type, value, weight in old_facts:
            # Generate L1 (brief - first ~10 words or 50 chars)
            words = value.split()
            if len(words) > 10:
                l1_value = ' '.join(words[:10]) + '...'
            elif len(value) > 50:
                l1_value = value[:50] + '...'
            else:
                l1_value = value
            
            # L2 is the original value (standard detail)
            l2_value = value
            
            # Generate L3 (detailed - add context if short, otherwise keep same)
            if len(value) < 100:
                # For short facts, add a contextual prefix
                l3_value = f"{key}: {value}"
            else:
                l3_value = value
            
            # Insert with new schema
            cur.execute("""
                INSERT INTO profile_facts 
                (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight, 
                 access_count, last_accessed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight))
        
        conn.commit()
        print(f"✓ Successfully migrated {len(old_facts)} facts to L1/L2/L3 schema")
        
    elif 'l1_value' in columns and 'l2_value' in columns and 'l3_value' in columns:
        print("✓ Schema already has l1/l2/l3 columns. No migration needed.")
        
    else:
        print("⚠ Unknown schema state. Please check profile_facts table manually.")
        return False
    
    # Verify migration
    cur.execute("SELECT COUNT(*) FROM profile_facts")
    count = cur.fetchone()[0]
    print(f"\n✓ Migration complete. {count} facts in new schema.")
    
    return True


if __name__ == '__main__':
    try:
        success = migrate_profile_facts_to_l123()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
