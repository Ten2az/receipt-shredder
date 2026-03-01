"""
Receipt Shredder & Expense Categorizer — FastAPI Backend (main.py)
==================================================================
Entry point. Mounts all routers, configures CORS, initializes DB.

Cost strategy:
  - Claude Haiku  (~$0.0008/call) → raw OCR extraction
  - Claude Sonnet (~$0.003/call)  → categorization + insights
  - Batch API (50% off)           → nightly insight summaries
  - SQLite                        → zero infrastructure cost

Local dev:
  uvicorn main:app --reload --port 8000

Deploy to Render (free tier):
  Set env vars: ANTHROPIC_API_KEY, SECRET_KEY, STRIPE_SECRET_KEY
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import database
from routers import auth, receipts, insights, export, webhooks

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield

app = FastAPI(title="Receipt Shredder API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",       # Expo dev
        "http://localhost:3000",       # Web dev
        "https://your-app.vercel.app", # ← replace with real Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
app.include_router(export.router,   prefix="/export",   tags=["export"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

@app.get("/health")
def health():
    return {"status": "ok"}
