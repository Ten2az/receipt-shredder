"""
routers/auth.py — Authentication endpoints
==========================================
Supports:
  - Email/password signup + login (bcrypt hashed)
  - Google OAuth (ID token verification)
  - JWT access tokens (30 day expiry for mobile UX)
  - Profile quiz submission (stored as JSON blob)

Endpoints:
  POST /auth/signup
  POST /auth/login
  POST /auth/google
  GET  /auth/me
  PUT  /auth/profile
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt
import os
import json
from datetime import datetime, timedelta
import database

router = APIRouter()
security = HTTPBearer()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM  = "HS256"
TOKEN_DAYS = 30

# ── Token helpers ─────────────────────────────────────────────────────────────
def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Dependency — returns user_id from JWT. Use in protected routes."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")

# ── Pydantic models ───────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str  # From Google Sign-In SDK

class ProfileRequest(BaseModel):
    state: str              # e.g. "NC", "CA"
    user_type: str          # "personal", "freelancer", "small_business"
    tax_year: int
    categories_focus: list[str]  # ["Food", "Office Supplies"]
    privacy_mode: bool = False

# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/signup")
def signup(req: SignupRequest):
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    conn = database.get_conn()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (req.email, hashed)
        )
        conn.commit()
        user_id = conn.execute(
            "SELECT id FROM users WHERE email=?", (req.email,)
        ).fetchone()["id"]
        return {"token": create_token(user_id), "user_id": user_id}
    except Exception:
        raise HTTPException(409, "Email already registered")
    finally:
        conn.close()

@router.post("/login")
def login(req: LoginRequest):
    conn = database.get_conn()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email=?", (req.email,)
    ).fetchone()
    conn.close()
    if not row or not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    return {"token": create_token(row["id"]), "user_id": row["id"]}

@router.post("/google")
def google_login(req: GoogleAuthRequest):
    """
    Verify Google ID token. Requires google-auth library.
    Note: Set GOOGLE_CLIENT_ID in .env for production.
    """
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
        info = id_token.verify_oauth2_token(req.id_token, grequests.Request(), GOOGLE_CLIENT_ID)
        email = info["email"]
        google_id = info["sub"]
    except Exception:
        raise HTTPException(401, "Invalid Google token")

    conn = database.get_conn()
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        user_id = row["id"]
        conn.execute("UPDATE users SET google_id=? WHERE id=?", (google_id, user_id))
    else:
        conn.execute(
            "INSERT INTO users (email, google_id) VALUES (?, ?)", (email, google_id)
        )
        user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
    conn.commit()
    conn.close()
    return {"token": create_token(user_id), "user_id": user_id}

@router.get("/me")
def get_me(user_id: int = Depends(verify_token)):
    conn = database.get_conn()
    row = conn.execute(
        "SELECT id, email, is_premium, profile FROM users WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "User not found")
    return {
        "id": row["id"],
        "email": row["email"],
        "is_premium": bool(row["is_premium"]),
        "profile": json.loads(row["profile"]) if row["profile"] else None
    }

@router.put("/profile")
def update_profile(req: ProfileRequest, user_id: int = Depends(verify_token)):
    profile_json = json.dumps(req.dict())
    conn = database.get_conn()
    conn.execute("UPDATE users SET profile=? WHERE id=?", (profile_json, user_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}
