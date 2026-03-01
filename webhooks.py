"""
routers/webhooks.py — Stripe payments and webhooks
===================================================
Handles:
  - Create checkout session (start Premium subscription)
  - Stripe webhook (payment success → upgrade user)
  - Cancel subscription

Setup:
  1. Create product in Stripe Dashboard: "Receipt Shredder Premium" $4.99/mo
  2. Copy price ID (price_xxx) to STRIPE_PRICE_ID env var
  3. Set webhook endpoint: https://your-api.render.com/webhooks/stripe
  4. Copy webhook secret to STRIPE_WEBHOOK_SECRET env var

Endpoints:
  POST /webhooks/create-checkout    — returns Stripe checkout URL
  POST /webhooks/stripe             — Stripe webhook receiver
  GET  /webhooks/status             — check subscription status
"""

from fastapi import APIRouter, Depends, HTTPException, Request
import os
import database
from routers.auth import verify_token

router = APIRouter()

STRIPE_SECRET     = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SIG = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID   = os.getenv("STRIPE_PRICE_ID", "price_xxx")  # ← set in Stripe Dashboard
APP_URL           = os.getenv("APP_URL", "http://localhost:8081")


@router.post("/create-checkout")
def create_checkout(user_id: int = Depends(verify_token)):
    """
    Creates a Stripe Checkout session for Premium subscription.
    Returns a URL the frontend redirects the user to.
    """
    if not STRIPE_SECRET:
        raise HTTPException(500, "Stripe not configured")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET

        conn = database.get_conn()
        user = conn.execute("SELECT email, stripe_customer_id FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()

        # Create or reuse Stripe customer
        customer_id = user["stripe_customer_id"]
        if not customer_id:
            customer = stripe.Customer.create(email=user["email"])
            customer_id = customer.id
            conn = database.get_conn()
            conn.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer_id, user_id))
            conn.commit()
            conn.close()

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{APP_URL}/settings?upgraded=true",
            cancel_url=f"{APP_URL}/settings?upgraded=false",
            metadata={"user_id": str(user_id)}
        )
        return {"checkout_url": session.url}

    except Exception as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Receives Stripe events. Upgrades user on payment success.
    Downgrades on subscription cancellation.
    """
    if not STRIPE_SECRET:
        return {"status": "stripe_not_configured"}

    import stripe
    stripe.api_key = STRIPE_SECRET

    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SIG)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        _set_premium(user_id, True)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer_id = event["data"]["object"]["customer"]
        conn = database.get_conn()
        user = conn.execute("SELECT id FROM users WHERE stripe_customer_id=?", (customer_id,)).fetchone()
        conn.close()
        if user:
            _set_premium(user["id"], False)

    return {"status": "ok"}


def _set_premium(user_id: int, is_premium: bool):
    conn = database.get_conn()
    conn.execute("UPDATE users SET is_premium=? WHERE id=?", (1 if is_premium else 0, user_id))
    conn.commit()
    conn.close()


@router.get("/status")
def subscription_status(user_id: int = Depends(verify_token)):
    conn = database.get_conn()
    user = conn.execute("SELECT is_premium FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return {"is_premium": bool(user["is_premium"])}
