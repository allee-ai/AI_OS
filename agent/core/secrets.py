"""
Secrets Management
==================

Secure storage for API keys, OAuth tokens, and other credentials.
Uses Fernet symmetric encryption with a machine-derived key.

Tables:
- secrets: Encrypted credentials keyed by feed/service name
"""

import os
import json
import base64
import sqlite3
from contextlib import closing
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Lazy import to avoid circular deps
def get_connection():
    from data.db import get_connection as _get_conn
    return _get_conn()

# Try to import cryptography, gracefully degrade if not available
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None


# ============================================================================
# Key Derivation
# ============================================================================

def _get_machine_id() -> bytes:
    """Get a stable machine identifier for key derivation."""
    # Try various sources for a stable ID
    sources = [
        "/etc/machine-id",
        "/var/lib/dbus/machine-id",
        os.path.expanduser("~/.aios_machine_id"),
    ]
    
    for path in sources:
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read().strip().encode()
    
    # Fallback: create a stable ID in user home
    fallback_path = os.path.expanduser("~/.aios_machine_id")
    if not os.path.exists(fallback_path):
        import uuid
        machine_id = str(uuid.uuid4())
        with open(fallback_path, "w") as f:
            f.write(machine_id)
        return machine_id.encode()
    
    with open(fallback_path, "r") as f:
        return f.read().strip().encode()


def _derive_key(salt: bytes = b"aios_secrets_v1") -> bytes:
    """Derive encryption key from machine ID."""
    if not CRYPTO_AVAILABLE:
        return b""
    
    machine_id = _get_machine_id()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(machine_id))


def _get_fernet() -> Optional[Any]:
    """Get Fernet instance for encryption/decryption."""
    if not CRYPTO_AVAILABLE:
        return None
    key = _derive_key()
    return Fernet(key)


# ============================================================================
# Table Initialization
# ============================================================================

def init_secrets_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create secrets table if it doesn't exist."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            feed_name TEXT,
            value_encrypted TEXT NOT NULL,
            secret_type TEXT DEFAULT 'api_key',
            metadata_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(key, feed_name)
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_secrets_feed ON secrets(feed_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_secrets_key ON secrets(key)")
    
    if own_conn:
        conn.commit()
        conn.close()


# ============================================================================
# CRUD Operations
# ============================================================================

def store_secret(
    key: str,
    value: str,
    feed_name: Optional[str] = None,
    secret_type: str = "api_key",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Store an encrypted secret.
    
    Args:
        key: Identifier (e.g., "access_token", "api_key", "refresh_token")
        value: The secret value to encrypt
        feed_name: Associated feed/service (e.g., "gmail", "discord")
        secret_type: Type hint ("api_key", "oauth_token", "refresh_token", "password")
        metadata: Additional info (scopes, expiry, etc.)
    
    Returns:
        Secret ID or None
    """
    fernet = _get_fernet()
    
    if fernet:
        encrypted = fernet.encrypt(value.encode()).decode()
    else:
        # Fallback: base64 encode (NOT secure, but allows function to work)
        encrypted = base64.b64encode(value.encode()).decode()
    
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Upsert
        cur.execute("""
            INSERT INTO secrets (key, feed_name, value_encrypted, secret_type, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key, feed_name) DO UPDATE SET
                value_encrypted = excluded.value_encrypted,
                secret_type = excluded.secret_type,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
        """, (key, feed_name, encrypted, secret_type, metadata_json))
        
        secret_id = cur.lastrowid
        conn.commit()
        
        # Log the event (without the actual secret value!)
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="system",
                data=f"Secret stored: {key}" + (f" for {feed_name}" if feed_name else ""),
                metadata={"key": key, "feed_name": feed_name, "secret_type": secret_type},
                source="secrets"
            )
        except ImportError:
            pass  # Log thread not available
    
    return secret_id


def get_secret(key: str, feed_name: Optional[str] = None) -> Optional[str]:
    """
    Retrieve and decrypt a secret.
    
    Args:
        key: Secret identifier
        feed_name: Associated feed/service
    
    Returns:
        Decrypted secret value or None if not found
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        if feed_name:
            cur.execute(
                "SELECT value_encrypted FROM secrets WHERE key = ? AND feed_name = ?",
                (key, feed_name)
            )
        else:
            cur.execute(
                "SELECT value_encrypted FROM secrets WHERE key = ? AND feed_name IS NULL",
                (key,)
            )
        
        row = cur.fetchone()
        if not row:
            return None
        
        encrypted = row[0]
        fernet = _get_fernet()
        
        if fernet:
            try:
                return fernet.decrypt(encrypted.encode()).decode()
            except Exception:
                # Try base64 fallback (for legacy/unencrypted)
                try:
                    return base64.b64decode(encrypted).decode()
                except Exception:
                    return None
        else:
            # No crypto, try base64
            try:
                return base64.b64decode(encrypted).decode()
            except Exception:
                return encrypted  # Return as-is


def get_secrets_for_feed(feed_name: str) -> Dict[str, str]:
    """Get all secrets for a specific feed."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        cur.execute(
            "SELECT key, value_encrypted FROM secrets WHERE feed_name = ?",
            (feed_name,)
        )
        
        fernet = _get_fernet()
        secrets = {}
        
        for key, encrypted in cur.fetchall():
            if fernet:
                try:
                    secrets[key] = fernet.decrypt(encrypted.encode()).decode()
                except Exception:
                    try:
                        secrets[key] = base64.b64decode(encrypted).decode()
                    except Exception:
                        pass
            else:
                try:
                    secrets[key] = base64.b64decode(encrypted).decode()
                except Exception:
                    secrets[key] = encrypted
        
        return secrets


def delete_secret(key: str, feed_name: Optional[str] = None) -> bool:
    """Delete a secret."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        if feed_name:
            cur.execute(
                "DELETE FROM secrets WHERE key = ? AND feed_name = ?",
                (key, feed_name)
            )
        else:
            cur.execute(
                "DELETE FROM secrets WHERE key = ? AND feed_name IS NULL",
                (key,)
            )
        
        deleted = cur.rowcount > 0
        conn.commit()
        
        if deleted:
            try:
                from agent.threads.log.schema import log_event
                log_event(
                    event_type="system",
                    data=f"Secret deleted: {key}" + (f" for {feed_name}" if feed_name else ""),
                    metadata={"key": key, "feed_name": feed_name},
                    source="secrets"
                )
            except ImportError:
                pass
        
        return deleted


def delete_secrets_for_feed(feed_name: str) -> int:
    """Delete all secrets for a feed (e.g., on disconnect)."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        cur.execute("DELETE FROM secrets WHERE feed_name = ?", (feed_name,))
        count = cur.rowcount
        conn.commit()
        
        if count > 0:
            try:
                from agent.threads.log.schema import log_event
                log_event(
                    event_type="system",
                    data=f"All secrets deleted for feed: {feed_name}",
                    metadata={"feed_name": feed_name, "count": count},
                    source="secrets"
                )
            except ImportError:
                pass
        
        return count


def list_secrets(feed_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List secrets (metadata only, NOT values).
    
    Returns list of {key, feed_name, secret_type, created_at, updated_at}
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_secrets_table(conn)
        
        if feed_name:
            cur.execute("""
                SELECT key, feed_name, secret_type, metadata_json, created_at, updated_at
                FROM secrets WHERE feed_name = ?
                ORDER BY updated_at DESC
            """, (feed_name,))
        else:
            cur.execute("""
                SELECT key, feed_name, secret_type, metadata_json, created_at, updated_at
                FROM secrets
                ORDER BY feed_name, key
            """)
        
        results = []
        for row in cur.fetchall():
            metadata = json.loads(row[3]) if row[3] else None
            results.append({
                "key": row[0],
                "feed_name": row[1],
                "secret_type": row[2],
                "metadata": metadata,
                "created_at": row[4],
                "updated_at": row[5],
            })
        
        return results


# ============================================================================
# OAuth Token Helpers
# ============================================================================

def store_oauth_tokens(
    feed_name: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    scopes: Optional[List[str]] = None
) -> None:
    """Store OAuth tokens for a feed."""
    metadata = {}
    if expires_at:
        metadata["expires_at"] = expires_at
    if scopes:
        metadata["scopes"] = scopes
    
    store_secret("access_token", access_token, feed_name, "oauth_token", metadata)
    
    if refresh_token:
        store_secret("refresh_token", refresh_token, feed_name, "refresh_token")


def get_oauth_tokens(feed_name: str) -> Optional[Dict[str, Any]]:
    """Get OAuth tokens for a feed."""
    access_token = get_secret("access_token", feed_name)
    if not access_token:
        return None
    
    refresh_token = get_secret("refresh_token", feed_name)
    
    # Get metadata for expiry info
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT metadata_json FROM secrets WHERE key = 'access_token' AND feed_name = ?",
            (feed_name,)
        )
        row = cur.fetchone()
        metadata = json.loads(row[0]) if row and row[0] else {}
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": metadata.get("expires_at"),
        "scopes": metadata.get("scopes", []),
    }


# ============================================================================
# Utility
# ============================================================================

def has_crypto() -> bool:
    """Check if cryptography is available."""
    return CRYPTO_AVAILABLE
