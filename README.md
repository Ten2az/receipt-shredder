# 🧾 Receipt Shredder & Expense Categorizer

> AI-powered receipt scanning, expense categorization, and tax deduction flagging — built for personal and small household use.

![Version](https://img.shields.io/badge/version-1.0.0-purple)
![Stack](https://img.shields.io/badge/stack-Expo%20%7C%20FastAPI%20%7C%20Claude-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ What It Does

Snap a photo of any receipt → AI extracts the data, categorizes the expense, flags tax deductibles, and builds your spending dashboard. No manual entry.

| Feature | Free | Premium ($4.99/mo) |
|---|:---:|:---:|
| Receipt scanning | 20/month | Unlimited |
| AI extraction & categorization | ✅ | ✅ |
| State-specific tax deduction flags | ✅ | ✅ |
| Spending dashboard + trends | ✅ | ✅ |
| CSV export | ✅ | ✅ |
| PDF export (IRS-ready) | — | ✅ |
| Batch upload (10 at once) | — | ✅ |
| Family sharing | — | 🔜 |
| TurboTax export | — | 🔜 |

---

## 🏗 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Mobile/Web | React Native + Expo | One codebase: iOS, Android, Web |
| Backend | Python + FastAPI | Fast, async, great for file uploads |
| AI | Claude Haiku + Sonnet | Haiku for cheap OCR, Sonnet for smart categorization |
| Database | SQLite | Zero infrastructure cost for MVP |
| Storage encryption | Fernet (cryptography) | Sensitive fields encrypted at rest |
| Payments | Stripe | Industry-standard subscriptions |
| Backend hosting | Render (free tier) | Free, auto-deploys from GitHub |
| Frontend hosting | Vercel (free tier) | Free, instant web deploys |

---

## 💰 Cost Per Scan

| Step | Model | Cost |
|---|---|---|
| Image extraction (OCR) | Claude Haiku | ~$0.0008 |
| Categorization + deductibles | Claude Sonnet | ~$0.003 |
| **Total per receipt** | | **~$0.004** |

Nightly insight summaries use Anthropic's **Batch API (50% discount)**.

---

## 📁 Project Structure

```
receipt-shredder/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLite schema + Fernet encryption
│   ├── ai_service.py        # Claude API calls (2-stage pipeline)
│   ├── image_utils.py       # Pillow image preprocessing
│   ├── requirements.txt
│   ├── .env.example
│   └── routers/
│       ├── auth.py          # JWT + Google OAuth
│       ├── receipts.py      # Upload, list, feedback loop
│       ├── insights.py      # Spending analytics + caching
│       ├── export.py        # CSV + PDF generation
│       └── webhooks.py      # Stripe payments
├── frontend/
│   ├── App.js               # Navigation + auth state
│   ├── app.json             # Expo config
│   ├── package.json
│   └── src/
│       ├── screens/
│       │   ├── LoginScreen.js
│       │   ├── OnboardingScreen.js   # Profile quiz
│       │   ├── DashboardScreen.js    # Home + spending overview
│       │   ├── UploadScreen.js       # Camera + gallery + results
│       │   ├── ReceiptsScreen.js     # History + filters
│       │   ├── InsightsScreen.js     # Charts + deductibles
│       │   └── SettingsScreen.js     # Profile + premium + privacy
│       └── utils/
│           ├── api.js               # All backend API calls
│           └── AuthContext.js       # Global auth state
├── render.yaml              # Render.com deploy config
├── SETUP.md                 # Full setup + deployment guide
└── README.md                # This file
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11+, Node.js 18+
- [Anthropic API key](https://console.anthropic.com)
- Expo CLI: `npm install -g expo-cli`

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
# Generate FERNET_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

uvicorn main:app --reload --port 8000
# ✅ API: http://localhost:8000
# ✅ Docs: http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npx expo start
# Press W → web, A → Android, I → iOS
```

---

## 🔐 Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...       # Required
SECRET_KEY=your-32-char-secret     # Required — JWT signing
FERNET_KEY=...                     # Required — DB encryption
STRIPE_SECRET_KEY=sk_test_...      # For payments
STRIPE_WEBHOOK_SECRET=whsec_...    # For payments
STRIPE_PRICE_ID=price_...          # Your $4.99/mo product
GOOGLE_CLIENT_ID=...               # For Google login (optional)
APP_URL=http://localhost:8081      # Frontend URL
```

---

## 🚀 Deploy

### Backend → [Render](https://render.com) (free)
1. Push to GitHub
2. Render → New → Blueprint → connect repo
3. `render.yaml` auto-configures everything
4. Add env vars in Render dashboard

### Frontend → [Vercel](https://vercel.com) (free)
```bash
cd frontend
npx expo export --platform web
npx vercel deploy dist/
```

---

## 🧠 How the AI Pipeline Works

```
📷 Photo upload
      ↓
  [Pillow] Auto-rotate, enhance contrast, resize, detect blur
      ↓
  [Claude Haiku] Extract: date, vendor, items, total, tax (~$0.0008)
      ↓
  [Claude Sonnet] Categorize + flag deductibles + state rules (~$0.003)
      ↓
  [SQLite] Encrypt sensitive fields, store result
      ↓
  📊 Dashboard updated
```

**Personalization loop:** Every correction (👍/✏️ Fix It) is stored. The last 3 corrections are injected as context into the next Sonnet call, gradually tuning the AI to your spending patterns.

---

## 🗺 State-Specific Tax Rules (Built-in)

| State | Rule Applied |
|---|---|
| **NC** | 4.75% general sales tax; food at 2% |
| **CA** | No sales tax on groceries; strict home office rules |
| **TX** | No state income tax; tracks federal deductibles only |
| **NY** | Clothing under $110 tax-exempt |
| All states | IRS 50% business meal rule, home office deduction |

---

## 🎮 Gamification Badges

| Badge | Trigger |
|---|---|
| 🎉 First Upload | Upload your first receipt |
| 📄 Receipt Rookie | 10+ receipts |
| 🔍 Scan Master | 50+ receipts |
| 💰 Tax Saver | $100+ in deductibles |
| 🗂️ Organized | 10+ receipts in a month |

---

## 🔒 Privacy & Security

- **Fernet encryption** on all sensitive fields (vendor, line items, raw OCR text)
- Amounts stored plaintext only for aggregation queries
- **No data sharing** with third parties
- JWT tokens with 30-day expiry
- Read-only Anthropic API key (no training on your data)
- Images processed transiently — not stored after extraction

---

## 🔧 Scaling Beyond MVP

| Need | Solution |
|---|---|
| More users | Swap SQLite → PostgreSQL (change one line in `database.py`) |
| Large batch jobs | Add Celery + Redis job queue |
| Higher privacy | Add Tesseract local OCR; only send text to Claude |
| Email forwarding | Mailgun inbound → `/receipts/upload` webhook |
| Push notifications | Expo Notifications for monthly summaries |

See `SETUP.md` for full implementation notes on each.

---

## 📄 License

MIT — use freely, attribution appreciated.

---

*Built with Claude by Anthropic · Expo · FastAPI*
