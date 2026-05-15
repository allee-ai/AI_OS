"""Auth router — login, current user, and admin user management."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from backend.database import get_db
from backend.auth import verify_password, hash_password, create_token, get_current_user, require_admin

router = APIRouter(tags=["auth"])

ALLOWED_ROLES = ("admin", "sales")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = %s",
        (req.username,),
    )
    user = cur.fetchone()
    db.close()
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Bad credentials")
    token = create_token(user["id"], user["username"], user["role"])
    return {"token": token, "role": user["role"], "username": user["username"]}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {"id": user["sub"], "username": user["username"], "role": user["role"]}


# ── Admin: user management ────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # admin | sales


class UserPasswordUpdate(BaseModel):
    password: str


@router.get("/users")
def list_users(_admin: dict = Depends(require_admin)):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/users")
def create_user(req: UserCreate, _admin: dict = Depends(require_admin)):
    if req.role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Role must be one of {ALLOWED_ROLES}")
    if not req.username.strip() or len(req.password) < 4:
        raise HTTPException(400, "Username required, password must be ≥4 chars")
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (req.username,))
    if cur.fetchone():
        db.close()
        raise HTTPException(409, "Username already exists")
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s) RETURNING id",
        (req.username.strip(), hash_password(req.password), req.role),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    db.close()
    return {"id": new_id, "username": req.username, "role": req.role}


@router.patch("/users/{user_id}/password")
def reset_user_password(user_id: int, req: UserPasswordUpdate, _admin: dict = Depends(require_admin)):
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be ≥4 chars")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(req.password), user_id),
    )
    db.commit()
    db.close()
    return {"updated": 1}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if str(admin["sub"]) == str(user_id):
        raise HTTPException(400, "Can't delete your own account")
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    db.close()
    return {"deleted": 1}

