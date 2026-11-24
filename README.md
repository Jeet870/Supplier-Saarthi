# Supplier Saarthi

**Voice-First Supplier Accountability Ledger for Indian Kirana Stores.**

Supplier Saarthi empowers small grocery store owners (kirana dukaandars) to record delivery discrepancies, short shipments, damaged items, and verbal distributor promises in under 10 seconds using natural spoken Hinglish.

---

## 🌟 What the App Does

Neighborhood kirana stores receive 15–30 supplier deliveries every week while attending to customer footfall. Short shipments, damaged packets, price mismatches, and verbal promises (*"agli delivery mein replace kar denge"*, *"30 din ka udhaar"*) are routinely forgotten or disputed when payment is due.

**Supplier Saarthi solves this in 4 frictionless steps:**
1. **Speak Natural Voice**: The merchant speaks mixed Hindi/English into the mobile browser (*"Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye"*).
2. **Instant Structured Extraction**: Groq Whisper and LLM models transcribe the voice, match catalog SKUs, calculate shortage quantities, and extract promise conditions.
3. **Deterministic Spoken Read-Back**: The phone speaks back a clear Hindi confirmation (*"Sharma Distributors se Maggi Noodles 1 carton kam aaya. Sahi hai?"*).
4. **1-Tap Settle & Share**: Tap **Haan** to confirm. Save records to Supabase, organize chronological supplier timelines, attach bill photos, share summaries via WhatsApp in 1-click, or work completely offline.

---

## 🚀 Live Deployment & Demo

* **Live Web Service**: Hosted on Render (`https://<your-render-service>.onrender.com`)
* **Health Check Endpoint**: `/health` -> `{"status": "ok"}`
* **Keep-Alive Monitor**: UptimeRobot 5-minute HTTP monitor configured to prevent cold starts on the free hosting tier.

---

## 🔄 How to Reset Demo Data

To return the database to the clean initial demo story (4 suppliers, 5 products, 7 initial timeline records):
* **Option 1 (Hidden UI Trigger)**: Tap the **"Supplier Saarthi"** header logo **5 times in 3 seconds** on any mobile screen. A prompt will ask for confirmation and automatically reset the demo state.
* **Option 2 (API Route)**:
  ```bash
  curl -X POST https://<your-render-service>.onrender.com/api/demo/reset
  ```

---

## 💻 Fresh Clone Setup (Run on Your Computer)

Follow these steps from a fresh clone to run Supplier Saarthi locally:

### 1. Prerequisites
* Python 3.10 to 3.13 installed
* Git

### 2. Clone the Repository
```bash
git clone https://github.com/Jeet870/Supplier-Saarthi.git
cd Supplier-Saarthi
```

### 3. Create & Activate Virtual Environment
* **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  ```
* **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
* **Windows**: `copy .env.example .env`
* **macOS / Linux**: `cp .env.example .env`

Fill in your API credentials in `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
```

### 6. Initialize Database (If Using Fresh Supabase Instance)
Open the Supabase SQL Editor and execute:
1. `db/schema.sql` (Tables, Foreign Keys, RLS rules)
2. `db/seed.sql` (Seed suppliers, products, and initial demo records)

### 7. Run the Application
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser at:
* **Home Screen**: `http://localhost:8000/`
* **Health Check**: `http://localhost:8000/health` -> `{"status": "ok"}`
* **API Documentation**: `http://localhost:8000/docs`

---

## 🧪 Testing & Accuracy Benchmarks

Run the automated test suite and accuracy benchmarks:

* **Unit & Integration Tests**:
  ```bash
  pytest
  ```
* **30-Sentence Benchmark Accuracy Evaluation**:
  ```bash
  python scripts/eval_utterances.py
  ```
  *Current Benchmark Score:*
  * Supplier Identification: **95.7%** (Target: 90%)
  * Product Identification: **94.4%** (Target: 85%)
  * Quantity Extraction: **96.2%** (Target: 85%)

* **Noisy-Room Kirana Stress Test (10 Real Utterances)**:
  ```bash
  python scripts/eval_noisy.py
  ```
  *Current Noise Robustness Score:* **90.0%** (9/10 Passed under ambient fan/market noise)

---

## 📡 Key API Routes

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health check (`{"status": "ok"}`) |
| `POST` | `/api/transcribe` | Transcribe voice audio to text using Whisper |
| `POST` | `/api/extract` | Extract structured delivery/promise records with readback text |
| `POST` | `/api/query` | Natural Hinglish voice query assistant for pending items |
| `POST` | `/api/records` | Persist confirmed discrepancy or promise record |
| `GET` | `/api/timeline/{id}` | Combined chronological timeline of deliveries and promises |
| `GET` | `/api/pending` | Query open unresolved records with supplier & type filters |
| `PATCH` | `/api/records/{id}/status` | Update record status (`RESOLVED`, `FULFILLED`) |
| `POST` | `/api/photos` | Upload bill / damaged stock photo to Supabase storage |
| `POST` | `/api/demo/reset` | Restore demo data to clean 7-record baseline |

---

## 🔒 Security & Contribution Rules

* Never commit `.env` or real API keys to version control.
* All external keys start with `gsk_` (Groq) or `eyJ` (Supabase) and must stay in `.env` only.
* Supabase service keys are strictly used server-side in `app/db.py` and are never exposed to browser templates.
