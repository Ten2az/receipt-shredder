"""
ai_service.py — All Claude API interactions
============================================
Two-stage pipeline to minimize cost:
  Stage 1 (Haiku,  ~$0.0008): Extract raw data from receipt image
  Stage 2 (Sonnet, ~$0.003):  Categorize, flag deductibles, generate insight

Total per scan: ~$0.004 — well within $0.01–0.05 target.

Batch API note: Nightly summary jobs use /v1/messages/batches (50% off).
"""

import os
import json
import base64
import anthropic
from typing import Optional

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Stage 1: Haiku extraction ─────────────────────────────────────────────────
EXTRACT_PROMPT = """Extract receipt data. Return ONLY valid JSON, no explanation.

JSON format:
{
  "date": "YYYY-MM-DD or null",
  "vendor": "store name",
  "items": [{"name": "item", "qty": 1, "price": 0.00}],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "cash/card/unknown",
  "currency": "USD",
  "confidence": 0.0-1.0,
  "issues": ["blurry", "partial", "handwritten"] or []
}

If unclear, set confidence < 0.6 and list issues. Use null for missing fields."""

async def extract_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Stage 1: Send receipt image to Haiku for fast, cheap OCR extraction.
    Cost: ~$0.0008 per call including vision tokens.
    
    Handles: JPEG, PNG, WebP, GIF
    Falls back to text prompt if image quality is poor.
    """
    b64 = base64.standard_b64encode(image_bytes).decode()

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Cheapest vision model
            max_tokens=600,                      # Receipt data is compact
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64
                        }
                    },
                    {"type": "text", "text": EXTRACT_PROMPT}
                ]
            }]
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)

    except json.JSONDecodeError:
        # Model returned non-JSON — mark for manual review
        return {
            "date": None, "vendor": "Unknown", "items": [],
            "subtotal": 0.0, "tax": 0.0, "total": 0.0,
            "payment_method": "unknown", "currency": "USD",
            "confidence": 0.1, "issues": ["parse_error"]
        }


# ── Stage 2: Sonnet categorization + deductible flagging ─────────────────────
CATEGORIZE_PROMPT_TEMPLATE = """Categorize this receipt and flag tax deductibles.
User profile: {profile}
Receipt data: {receipt_json}

Categories (pick best): Food & Dining, Groceries, Transportation, Gas & Fuel,
Office Supplies, Software & Tech, Medical, Entertainment, Utilities, 
Home Office, Education, Travel, Clothing, Personal Care, Other

US State: {state}

Return ONLY valid JSON:
{{
  "category": "...",
  "subcategory": "...",
  "is_deductible": true/false,
  "deductible_type": "Business Meal/Home Office/Vehicle/Medical/Other or null",
  "deductible_pct": 0-100,
  "state_notes": "state-specific tip or null",
  "confidence": 0.0-1.0,
  "insight_nudge": "one short insight or null"
}}

State-specific rules to apply:
- NC: 4.75% general sales tax; food at 2%
- CA: No sales tax on groceries; home office deduction strict
- TX: No income tax; track deductibles for federal only
- NY: Clothing <$110 tax-exempt
Apply relevant rules for {state}."""

async def categorize_receipt(
    extracted: dict,
    user_profile: dict,
    past_corrections: list[dict]
) -> dict:
    """
    Stage 2: Sonnet categorizes and flags deductibles.
    Cost: ~$0.003 per call.
    
    past_corrections: list of {original, corrected} for personalization.
    If user has >3 corrections for a category, inject as few-shot examples.
    """
    state = user_profile.get("state", "US")
    
    # Personalization: inject up to 3 past corrections as context
    profile_note = ""
    if past_corrections:
        examples = past_corrections[-3:]  # Most recent corrections
        profile_note = f"User previously corrected: {json.dumps(examples)}"

    profile_str = f"{user_profile.get('user_type','personal')} user, {state}. {profile_note}"

    prompt = CATEGORIZE_PROMPT_TEMPLATE.format(
        profile=profile_str,
        receipt_json=json.dumps(extracted, indent=None),  # Compact to save tokens
        state=state
    )

    msg = client.messages.create(
        model="claude-sonnet-4-6",  # Better reasoning for nuanced deductible rules
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "category": "Other", "subcategory": None,
            "is_deductible": False, "deductible_type": None,
            "deductible_pct": 0, "state_notes": None,
            "confidence": 0.5, "insight_nudge": None
        }


# ── Monthly insights via Batch API (50% cheaper) ─────────────────────────────
INSIGHT_PROMPT_TEMPLATE = """Analyze spending for {month}:
Data: {summary_json}

Return JSON:
{{
  "total_spent": 0.00,
  "vs_last_month_pct": 0.0,
  "top_category": "...",
  "deductible_total": 0.00,
  "nudges": ["tip1", "tip2"],
  "badges": ["First Upload", "Tax Saver"],
  "tax_estimate": "estimated deductible savings: $X.XX"
}}"""

def create_insight_batch_request(user_id: int, month: str, summary: dict) -> dict:
    """
    Create a batch request object for Anthropic's Batch API.
    Caller collects these across users and submits one batch per night.
    """
    return {
        "custom_id": f"insight-{user_id}-{month}",
        "params": {
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{
                "role": "user",
                "content": INSIGHT_PROMPT_TEMPLATE.format(
                    month=month,
                    summary_json=json.dumps(summary, indent=None)
                )
            }]
        }
    }

async def run_insight_batch(requests: list[dict]) -> dict[str, dict]:
    """
    Submit batch to Anthropic (50% discount vs real-time).
    Returns {custom_id: parsed_result}.
    Note: Batches complete within 24h. Poll /batches/{id}/results.
    """
    batch = client.messages.batches.create(requests=requests)
    return {"batch_id": batch.id, "status": batch.processing_status}
