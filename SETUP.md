# Receipt Shredder & Expense Categorizer
## Complete Setup, Run & Deploy Guide

---

## 📁 Project Structure

```
receipt-shredder/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # SQLite schema + Fernet encryption
│   ├── ai_service.py        # Claude API calls (Haiku + Sonnet)
│   ├── image_utils.py       # Pillow preprocessing
│   ├── requirements.txt
│   ├── .env.example
│   └── routers/
│       ├── auth.py          # JWT auth + Google OAuth
│       ├── receipts.py      # Upload, list, feedback
│       ├── insights.py      # Spending analytics
│       ├── export.py        # CSV + PDF generation
│       └── webhooks.py      # Stripe payments
├── frontend/
│   ├── App.js               # Navigation + auth state
│   ├── app.json             # Expo config
│   ├── package.json
│   └── src/
│       ├── screens/
│       │   ├── LoginScreen.js
│       │   ├── OnboardingScreen.js
│       │   ├── DashboardScreen.js
│       │   ├── UploadScreen.js
│       │   ├── ReceiptsScreen.js
│       │   ├── InsightsScreen.js
│       │   └── SettingsScreen.js
│       └── utils/
│           ├── api.js       # All API calls
│           └── AuthContext.js
├── render.yaml              # Render deployment
└── SETUP.md                 # This file
```

---

## ⚡ Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Expo CLI: `npm install -g expo-cli`
- An Anthropic API key: https://console.anthropic.com

### 1. Clone & setup backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Generate FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste output into .env as FERNET_KEY

# Start backend
uvicorn main:app --reload --port 8000
# ✅ API running at http://localhost:8000
# ✅ Docs at http://localhost:8000/docs
```

### 2. Setup frontend

```bash
cd frontend
npm install

# Set API URL (optional, defaults to localhost:8000)
echo 'EXPO_PUBLIC_API_URL=http://localhost:8000' > .env

# Start Expo
npx expo start

# Press W for web browser, A for Android emulator, I for iOS
```

### 3. Test with a sample receipt

```bash
# Upload a test receipt (replace with real image path)
curl -X POST http://localhost:8000/receipts/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/receipt.jpg"
```

---

## 🔐 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Yes | Get from console.anthropic.com |
| `SECRET_KEY` | ✅ Yes | JWT signing secret (32+ char random string) |
| `FERNET_KEY` | ✅ Yes | DB encryption key (generate per instructions above) |
| `STRIPE_SECRET_KEY` | For payments | sk_test_... from Stripe Dashboard |
| `STRIPE_WEBHOOK_SECRET` | For payments | whsec_... from Stripe webhook settings |
| `STRIPE_PRICE_ID` | For payments | price_... from Stripe product |
| `GOOGLE_CLIENT_ID` | For Google login | From Google Cloud Console |
| `APP_URL` | Yes | Frontend URL (for Stripe redirects) |
| `DB_PATH` | No | Defaults to receipt_shredder.db in current dir |

---

## 🚀 Deploy to Production

### Backend → Render (Free)

1. Push repo to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com)
3. New → Blueprint → Connect repo
4. Render detects `render.yaml` automatically
5. Add env vars in Render Dashboard → Environment
6. Deploy! URL: `https://receipt-shredder-api.onrender.com`

**Note:** Free tier sleeps after 15 minutes of inactivity. First request may take ~30s.
To avoid cold starts, upgrade to Render Starter ($7/mo) or add a cron to ping the health endpoint.

### Frontend → Vercel (Free)

```bash
cd frontend
npm install -g vercel

# Build web version
npx expo export --platform web

# Deploy to Vercel
vercel deploy dist/
# Follow prompts. URL: https://receipt-shredder-xxx.vercel.app
```

Then update:
- `render.yaml`: `APP_URL: https://your-app.vercel.app`
- Backend CORS in `main.py`: add your Vercel URL
- Frontend `api.js`: update `BASE_URL`

---

## 💳 Stripe Setup (Premium Features)

1. Create account at [stripe.com](https://stripe.com)
2. Dashboard → Products → Create product
   - Name: "Receipt Shredder Premium"
   - Price: $4.99/month, recurring
   - Copy `price_xxx` ID → `STRIPE_PRICE_ID`
3. Developers → API Keys → Copy `sk_test_xxx` → `STRIPE_SECRET_KEY`
4. Webhooks → Add endpoint:
   - URL: `https://your-api.render.com/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.deleted`
   - Copy signing secret → `STRIPE_WEBHOOK_SECRET`

---

## 🧪 Testing

### Test AI extraction quality

```python
# backend/test_extraction.py
import asyncio
import ai_service

async def test():
    with open("test_receipt.jpg", "rb") as f:
        image_bytes = f.read()
    
    extracted = await ai_service.extract_receipt(image_bytes)
    print("Extracted:", extracted)
    
    categorized = await ai_service.categorize_receipt(
        extracted,
        profile={"state": "NC", "user_type": "freelancer"},
        past_corrections=[]
    )
    print("Categorized:", categorized)

asyncio.run(test())
```

### Test with curl

```bash
# 1. Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password123"}'
# Returns: {"token": "...", "user_id": 1}

# 2. Upload receipt
curl -X POST http://localhost:8000/receipts/upload \
  -H "Authorization: Bearer TOKEN_HERE" \
  -F "file=@receipt.jpg"

# 3. Get insights
curl http://localhost:8000/insights/summary \
  -H "Authorization: Bearer TOKEN_HERE"
```

---

## 🔧 Edge Cases & Error Handling

### Blurry images
- `image_utils.py` detects blur via Laplacian variance
- `blurry_warning: true` returned in API response
- Frontend shows yellow warning banner
- Processing continues (don't block; AI may still extract partial data)

### Handwritten receipts
- Haiku handles handwriting reasonably well at high confidence
- Set `confidence < 0.65` threshold → auto-flag `needs_review: true`
- User sees ⚠️ indicator and can correct via feedback form

### Non-English receipts
- Claude's multilingual ability handles Spanish, French, Portuguese well
- Extraction prompt doesn't specify language — model adapts
- Vendor names preserved in original language

### Large batches
- Premium batch endpoint: max 10 files per request
- Use sequential processing to respect Anthropic rate limits
- For 100+ receipts: implement a job queue (Redis + Celery) — see Tweaks section

### API failures
- All Claude calls wrapped in try/except
- Returns partial result with `confidence: 0.1` and `issues: ["parse_error"]`
- User sees the receipt with flagged review status

---

## 💡 Potential Tweaks & Scaling

### Scale to PostgreSQL
```python
# In database.py, replace:
DB_PATH = os.getenv("DB_PATH", "receipt_shredder.db")
def get_conn():
    return sqlite3.connect(DB_PATH)

# With:
from sqlalchemy import create_engine
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")
engine = create_engine(DATABASE_URL)
```

### Add job queue for large batches
```bash
pip install celery redis
# Use Celery for async receipt processing
# Prevents API timeout on large uploads
```

### Privacy/local processing mode
- Use Tesseract OCR locally for initial text extraction
- Only send to Claude for categorization (not raw image)
- Reduces privacy exposure; increases extraction cost slightly

### Add email forwarding
- Use Zapier/Make.com to forward emails → webhook → `/receipts/upload`
- Or use Mailgun inbound email → parse attachments

### Mobile push notifications
- Add Expo Notifications for monthly summary alerts
- Notify when deductible threshold reached ($500, $1000)

### Family sharing (Premium)
- Add `household_id` to users table
- Share receipts within household_id
- Aggregate insights across household

### TurboTax export
- TurboTax accepts CSV in specific format
- Map deductible categories to Schedule C line items
- Add `/export/turbotax` endpoint

### On-device AI (Privacy mode)
- Use a small quantized model (llama.cpp via react-native-llama)
- Slower but fully private
- Best for users in high-security environments

---

## 💰 Cost Calculator

| Usage | Cost/month |
|---|---|
| 100 receipts/mo (free users) | ~$0.40 Claude API |
| 1,000 receipts/mo | ~$4.00 Claude API |
| 10,000 receipts/mo | ~$40 (use Batch API for 50% off nightly jobs) |
| Render free tier | $0 |
| Vercel free tier | $0 |
| Stripe | 2.9% + $0.30 per transaction |

**Break-even:** ~10 premium users ($50/mo) covers 10,000 scans comfortably.

---

## 🐛 Common Issues

**"Module not found: expo-image-picker"**
```bash
npx expo install expo-image-picker
```

**"ANTHROPIC_API_KEY not set"**
```bash
# Make sure .env is in backend/ directory
# And you're running: uvicorn main:app (not python main.py)
# Load dotenv: pip install python-dotenv
# Add to main.py top: from dotenv import load_dotenv; load_dotenv()
```

**Render free tier cold start delay**
- Normal. First request after idle period takes 20-30s.
- Add `/health` ping every 14 minutes via a free cron service (cron-job.org)

**SQLite "database is locked" on Render**
```python
# Add timeout to get_conn():
conn = sqlite3.connect(DB_PATH, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent writes
```
