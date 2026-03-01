"""
routers/insights.py — Spending insights and analytics
======================================================
Generates AI-powered insights from aggregated receipt data.
Uses caching to avoid re-running Sonnet on every page load.

Cache strategy:
  - Monthly insights cached in insight_cache table
  - Invalidated when new receipt uploaded in that month
  - Nightly batch job regenerates all (50% cheaper via Batch API)

Endpoints:
  GET /insights/summary          — current month overview
  GET /insights/trends           — 6-month spending trends
  GET /insights/deductibles      — tax deductible summary
  POST /insights/regenerate      — force refresh (premium)
"""

from fastapi import APIRouter, Depends
from datetime import datetime
import json
import database
import ai_service
from routers.auth import verify_token

router = APIRouter()

def get_month_summary(user_id: int, month: str) -> dict:
    """Aggregate raw receipt data into a summary dict for AI analysis."""
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT total, tax_amount, category, is_deductible, deductible_type, receipt_date
        FROM receipts
        WHERE user_id=? AND strftime('%Y-%m', receipt_date)=?
    """, (user_id, month)).fetchall()
    conn.close()

    if not rows:
        return {}

    by_category = {}
    total_spent = 0.0
    total_deductible = 0.0
    deductible_types = {}

    for r in rows:
        cat = r["category"] or "Other"
        amt = r["total"] or 0.0
        by_category[cat] = by_category.get(cat, 0.0) + amt
        total_spent += amt
        if r["is_deductible"]:
            total_deductible += amt
            dt = r["deductible_type"] or "Other"
            deductible_types[dt] = deductible_types.get(dt, 0.0) + amt

    return {
        "month": month,
        "total_spent": round(total_spent, 2),
        "receipt_count": len(rows),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        "total_deductible": round(total_deductible, 2),
        "deductible_by_type": deductible_types
    }


@router.get("/summary")
async def get_summary(user_id: int = Depends(verify_token)):
    """
    Returns AI-generated insights for the current month.
    Uses cached result if available; otherwise calls Sonnet (~$0.003).
    """
    month = datetime.now().strftime("%Y-%m")
    conn = database.get_conn()

    # Check cache
    cached = conn.execute(
        "SELECT insight_json FROM insight_cache WHERE user_id=? AND month=?",
        (user_id, month)
    ).fetchone()
    conn.close()

    if cached:
        return json.loads(cached["insight_json"])

    # Generate fresh insights
    summary = get_month_summary(user_id, month)
    if not summary:
        return {
            "month": month, "total_spent": 0.0, "receipt_count": 0,
            "nudges": ["Upload your first receipt to get started!"],
            "badges": [], "by_category": {}
        }

    # Get prev month for % comparison
    year, m = int(month[:4]), int(month[5:])
    prev_m = f"{year}-{m-1:02d}" if m > 1 else f"{year-1}-12"
    prev_summary = get_month_summary(user_id, prev_m)

    if prev_summary.get("total_spent", 0) > 0:
        pct_change = ((summary["total_spent"] - prev_summary["total_spent"]) / prev_summary["total_spent"]) * 100
        summary["vs_last_month_pct"] = round(pct_change, 1)
    else:
        summary["vs_last_month_pct"] = None

    # Award badges (gamification)
    badges = _compute_badges(user_id, summary)
    summary["badges"] = badges

    # Call Sonnet for AI nudges
    req = ai_service.create_insight_batch_request(user_id, month, summary)
    try:
        msg = __import__("anthropic").Anthropic(
            api_key=__import__("os").getenv("ANTHROPIC_API_KEY")
        ).messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=req["params"]["messages"]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ai_result = json.loads(raw)
        summary["nudges"] = ai_result.get("nudges", [])
        summary["tax_estimate"] = ai_result.get("tax_estimate")
    except Exception:
        summary["nudges"] = ["Keep uploading receipts for personalized insights!"]
        summary["tax_estimate"] = None

    # Cache result
    conn = database.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO insight_cache (user_id, month, insight_json) VALUES (?,?,?)",
        (user_id, month, json.dumps(summary))
    )
    conn.commit()
    conn.close()

    return summary


@router.get("/trends")
def get_trends(months: int = 6, user_id: int = Depends(verify_token)):
    """Returns spending by category over the last N months for chart display."""
    from datetime import datetime, timedelta
    conn = database.get_conn()

    result = []
    now = datetime.now()
    for i in range(months - 1, -1, -1):
        d = now.replace(day=1) - timedelta(days=i * 28)
        m = d.strftime("%Y-%m")
        row = conn.execute("""
            SELECT SUM(total) as total, COUNT(*) as count
            FROM receipts WHERE user_id=? AND strftime('%Y-%m', receipt_date)=?
        """, (user_id, m)).fetchone()
        result.append({
            "month": m,
            "total": round(row["total"] or 0.0, 2),
            "count": row["count"] or 0
        })

    conn.close()
    return {"trends": result}


@router.get("/deductibles")
def get_deductibles(
    year: int = None,
    user_id: int = Depends(verify_token)
):
    """Tax deductible summary, optionally filtered by year."""
    if not year:
        year = datetime.now().year
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT deductible_type, SUM(total) as total, COUNT(*) as count
        FROM receipts
        WHERE user_id=? AND is_deductible=1 AND strftime('%Y', receipt_date)=?
        GROUP BY deductible_type
        ORDER BY total DESC
    """, (user_id, str(year))).fetchall()
    conn.close()

    total_deductible = sum(r["total"] for r in rows if r["total"])
    return {
        "year": year,
        "total_deductible": round(total_deductible, 2),
        "estimated_tax_savings": round(total_deductible * 0.22, 2),  # Approx 22% bracket
        "by_type": [
            {"type": r["deductible_type"] or "Other", "total": round(r["total"], 2), "count": r["count"]}
            for r in rows
        ]
    }


def _compute_badges(user_id: int, summary: dict) -> list[str]:
    """Award gamification badges based on activity."""
    badges = []
    conn = database.get_conn()
    total_count = conn.execute(
        "SELECT COUNT(*) as c FROM receipts WHERE user_id=?", (user_id,)
    ).fetchone()["c"]
    conn.close()

    if total_count >= 1:   badges.append("First Upload 🎉")
    if total_count >= 10:  badges.append("Receipt Rookie 📄")
    if total_count >= 50:  badges.append("Scan Master 🔍")
    if summary.get("total_deductible", 0) > 100:
        badges.append("Tax Saver 💰")
    if summary.get("receipt_count", 0) >= 10:
        badges.append("Organized 🗂️")

    return badges
