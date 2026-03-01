"""
routers/receipts.py — Receipt upload, listing, and feedback
============================================================
Core workflow per upload:
  1. Receive image bytes
  2. Preprocess (Pillow: rotate, enhance, resize)
  3. Haiku: extract structured data
  4. Sonnet: categorize + flag deductibles
  5. Encrypt sensitive fields + store in SQLite
  6. Return result with confidence score

Free tier limit: 20 receipts/month
Premium ($4.99/mo): unlimited

Endpoints:
  POST /receipts/upload       — single image upload
  POST /receipts/batch        — up to 10 at once (premium)
  GET  /receipts              — paginated list
  GET  /receipts/{id}         — single receipt
  PUT  /receipts/{id}/feedback — thumbs up/down + correction
  DELETE /receipts/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import json
import database
import ai_service
import image_utils
from routers.auth import verify_token

router = APIRouter()

FREE_TIER_LIMIT = 20  # receipts per month

# ── Upload ────────────────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: int = Depends(verify_token)
):
    """
    Main upload endpoint. Two-stage AI pipeline:
      Haiku (extraction) + Sonnet (categorization)
    Total cost: ~$0.004 per receipt.
    """
    # 1. Check free tier limit
    conn = database.get_conn()
    user = conn.execute("SELECT is_premium, profile FROM users WHERE id=?", (user_id,)).fetchone()
    if not user["is_premium"]:
        from datetime import datetime
        month = datetime.now().strftime("%Y-%m")
        count = conn.execute(
            "SELECT COUNT(*) as c FROM receipts WHERE user_id=? AND strftime('%Y-%m', upload_date)=?",
            (user_id, month)
        ).fetchone()["c"]
        if count >= FREE_TIER_LIMIT:
            conn.close()
            raise HTTPException(402, f"Free tier limit ({FREE_TIER_LIMIT}/month) reached. Upgrade to Premium.")

    # 2. Validate file type
    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        conn.close()
        raise HTTPException(400, "Only image files supported (JPEG, PNG, WebP)")

    image_bytes = await file.read()
    if len(image_bytes) > 15 * 1024 * 1024:  # 15MB limit
        conn.close()
        raise HTTPException(400, "File too large (max 15MB)")

    # 3. Preprocess image
    processed_bytes, img_meta = image_utils.preprocess_receipt(image_bytes)
    mime_type = image_utils.bytes_to_mime(processed_bytes)

    # 4. Stage 1: Haiku extraction
    extracted = await ai_service.extract_receipt(processed_bytes, mime_type)

    # 5. Get user profile + past corrections for personalization
    profile = json.loads(user["profile"]) if user["profile"] else {"state": "US", "user_type": "personal"}
    corrections = conn.execute(
        "SELECT original_category, corrected_category FROM ai_feedback WHERE user_id=? ORDER BY id DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    past_corrections = [{"original": r["original_category"], "corrected": r["corrected_category"]} for r in corrections]

    # 6. Stage 2: Sonnet categorization
    categorized = await ai_service.categorize_receipt(extracted, profile, past_corrections)

    # 7. Encrypt and store
    vendor_enc  = database.encrypt(extracted.get("vendor", "Unknown"))
    items_enc   = database.encrypt(json.dumps(extracted.get("items", [])))
    raw_enc     = database.encrypt(json.dumps(extracted))

    needs_review = extracted.get("confidence", 1.0) < 0.65 or bool(img_meta.get("blurry"))

    conn.execute("""
        INSERT INTO receipts
          (user_id, receipt_date, vendor_enc, total, tax_amount, items_enc,
           category, subcategory, is_deductible, deductible_type, state_flags,
           confidence, needs_review, raw_text_enc)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        user_id,
        extracted.get("date"),
        vendor_enc,
        extracted.get("total", 0.0),
        extracted.get("tax", 0.0),
        items_enc,
        categorized.get("category", "Other"),
        categorized.get("subcategory"),
        1 if categorized.get("is_deductible") else 0,
        categorized.get("deductible_type"),
        json.dumps({"state_notes": categorized.get("state_notes")}),
        extracted.get("confidence", 0.5),
        1 if needs_review else 0,
        raw_enc
    ))
    conn.commit()
    receipt_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.close()

    return {
        "receipt_id": receipt_id,
        "vendor": extracted.get("vendor"),
        "date": extracted.get("date"),
        "total": extracted.get("total"),
        "category": categorized.get("category"),
        "is_deductible": categorized.get("is_deductible"),
        "deductible_type": categorized.get("deductible_type"),
        "state_notes": categorized.get("state_notes"),
        "confidence": extracted.get("confidence"),
        "needs_review": needs_review,
        "blurry_warning": img_meta.get("blurry"),
        "nudge": categorized.get("insight_nudge")
    }


@router.post("/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    user_id: int = Depends(verify_token)
):
    """
    Premium only: upload up to 10 receipts at once.
    Processes sequentially to avoid rate limits.
    """
    conn = database.get_conn()
    user = conn.execute("SELECT is_premium FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not user["is_premium"]:
        raise HTTPException(403, "Batch upload requires Premium")
    if len(files) > 10:
        raise HTTPException(400, "Max 10 files per batch")

    results = []
    for f in files:
        # Reuse single upload logic
        from fastapi import Request
        try:
            result = await upload_receipt(file=f, user_id=user_id)
            results.append({"filename": f.filename, "status": "ok", **result})
        except Exception as e:
            results.append({"filename": f.filename, "status": "error", "error": str(e)})

    return {"results": results}


# ── List + fetch ───────────────────────────────────────────────────────────────
@router.get("")
def list_receipts(
    page: int = 1,
    limit: int = 20,
    category: Optional[str] = None,
    month: Optional[str] = None,  # YYYY-MM
    user_id: int = Depends(verify_token)
):
    conn = database.get_conn()
    filters = ["user_id=?"]
    params = [user_id]

    if category:
        filters.append("category=?")
        params.append(category)
    if month:
        filters.append("strftime('%Y-%m', receipt_date)=?")
        params.append(month)

    where = " AND ".join(filters)
    offset = (page - 1) * limit

    rows = conn.execute(
        f"SELECT * FROM receipts WHERE {where} ORDER BY upload_date DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    total = conn.execute(f"SELECT COUNT(*) as c FROM receipts WHERE {where}", params).fetchone()["c"]
    conn.close()

    receipts = []
    for r in rows:
        receipts.append({
            "id": r["id"],
            "date": r["receipt_date"],
            "vendor": database.decrypt(r["vendor_enc"]),
            "total": r["total"],
            "category": r["category"],
            "subcategory": r["subcategory"],
            "is_deductible": bool(r["is_deductible"]),
            "needs_review": bool(r["needs_review"]),
            "confidence": r["confidence"],
            "upload_date": r["upload_date"]
        })

    return {"receipts": receipts, "total": total, "page": page}


@router.get("/{receipt_id}")
def get_receipt(receipt_id: int, user_id: int = Depends(verify_token)):
    conn = database.get_conn()
    row = conn.execute(
        "SELECT * FROM receipts WHERE id=? AND user_id=?", (receipt_id, user_id)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Receipt not found")

    return {
        "id": row["id"],
        "date": row["receipt_date"],
        "vendor": database.decrypt(row["vendor_enc"]),
        "total": row["total"],
        "tax_amount": row["tax_amount"],
        "items": json.loads(database.decrypt(row["items_enc"])) if row["items_enc"] else [],
        "category": row["category"],
        "subcategory": row["subcategory"],
        "is_deductible": bool(row["is_deductible"]),
        "deductible_type": row["deductible_type"],
        "state_flags": json.loads(row["state_flags"]) if row["state_flags"] else {},
        "confidence": row["confidence"],
        "needs_review": bool(row["needs_review"]),
        "user_feedback": row["user_feedback"]
    }


# ── Feedback loop ─────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    feedback: int           # 1=correct, -1=incorrect
    corrected_category: Optional[str] = None
    corrected_vendor: Optional[str] = None
    corrected_total: Optional[float] = None
    corrected_date: Optional[str] = None

@router.put("/{receipt_id}/feedback")
def submit_feedback(
    receipt_id: int,
    req: FeedbackRequest,
    user_id: int = Depends(verify_token)
):
    """
    User thumbs up/down on AI result.
    Corrections stored for few-shot personalization on future scans.
    """
    conn = database.get_conn()
    row = conn.execute(
        "SELECT * FROM receipts WHERE id=? AND user_id=?", (receipt_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Receipt not found")

    # Update receipt with corrections
    updates = {"user_feedback": req.feedback}
    if req.corrected_category:
        conn.execute(
            "INSERT INTO ai_feedback (user_id, receipt_id, original_category, corrected_category) VALUES (?,?,?,?)",
            (user_id, receipt_id, row["category"], req.corrected_category)
        )
        updates["category"] = req.corrected_category
    if req.corrected_vendor:
        updates["vendor_enc"] = database.encrypt(req.corrected_vendor)
    if req.corrected_total is not None:
        updates["total"] = req.corrected_total
    if req.corrected_date:
        updates["receipt_date"] = req.corrected_date

    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE receipts SET {set_clause} WHERE id=?",
        list(updates.values()) + [receipt_id]
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@router.delete("/{receipt_id}")
def delete_receipt(receipt_id: int, user_id: int = Depends(verify_token)):
    conn = database.get_conn()
    conn.execute("DELETE FROM receipts WHERE id=? AND user_id=?", (receipt_id, user_id))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
