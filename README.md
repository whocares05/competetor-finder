# Competitor Finder SaaS (Production MVP)

An AI-native, multi-tenant intelligence platform that returns a ranked list of real, verified competitors for any business globally.

## Core Architectural Principle
**The LLM never hallucinates or supplies competitor facts from memory.** All competitor records originate from live search and web extraction at query time, verified via HTTP/DNS signals, enriched through specialized providers, and scored by a small LLM judge against strict JSON schemas. Every returned competitor carries a verified `source_url` and a `fetched_at` timestamp.

---

## Monorepo Architecture

```
.
├── backend/            # FastAPI, SQLAlchemy 2.0, pgvector, Redis, arq workers
├── frontend/           # Next.js 14+ (App Router), TypeScript, Tailwind CSS
├── docker-compose.yml  # Local stack (Postgres + pgvector, Redis, Backend, Worker, Frontend)
├── .env.example        # Reference environment variables
└── README.md
```

### Key Subsystems
- **Provider Gateway**: Enforces token-bucket rate limiting, quota tracking, spend caps, and circuit breakers across all third-party adapters (SerpAPI, Firecrawl, Apify, Fallback search).
- **Config-Driven Tiering**: Centralized rules (`backend/app/config/tiers.py`) controlling provider allowances, candidate verification limits, and model escalation without touching pipeline logic.
- **Append-Only Credit Ledger**: Pre-reserves search credits, settles actual cost upon pipeline completion, and issues atomic refunds on failures or shortfalls.
- **pgvector Market Map**: Vector embeddings (multilingual 384-dim or OpenAI 1536-dim) stored with HNSW indexing for rapid semantic deduplication and candidate ranking.

---

## Quickstart & Local Setup

### 1. Prerequisites
- Docker & Docker Compose v2+
- Python 3.12+ (if running backend outside Docker)
- Node.js v20+ (if running frontend outside Docker)

### 2. Environment Configuration
Copy `.env.example` to `.env` at the project root:
```bash
cp .env.example .env
```
Fill in the API keys:
- `ANTHROPIC_API_KEY`: Required for pipeline understanding and judge stages.
- `SERPAPI_KEY`: Required for live web and maps discovery.
- `FIRECRAWL_API_KEY`: Required for listicle scraping and candidate verification.
- `FALLBACK_SEARCH_API_KEY`: Brave Search or Serper fallback key.
- `APIFY_TOKEN`: Required if running in `paid` tier.

### 3. Running with Docker Compose
Start the complete infrastructure:
```bash
docker compose up --build
```
Services will become available at:
- Frontend Dashboard: [http://localhost:3000](http://localhost:3000)
- Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/healthz](http://localhost:8000/healthz)

---

## Running Locally Without Docker

### Backend Setup
1. Create and activate a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run Alembic database migrations:
   ```bash
   alembic upgrade head
   ```
4. Start FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
5. In a separate terminal, start the background search worker:
   ```bash
   python -m app.workers.search_worker
   ```

### Frontend Setup
1. Install Node packages:
   ```bash
   cd frontend
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```

---

## Plan Tiers (`PLAN_TIER`)

The platform supports two runtime tiers configured via the `PLAN_TIER` environment variable:

| Feature | `free` Tier | `paid` Tier |
|---|---|---|
| **Max Competitors** | 10 | 50 |
| **SerpAPI Calls** | Up to 3 per search | Up to 4–6 per search |
| **Firecrawl Budget** | Scrape only, `num_competitors * 2` | Extract API, `num_competitors * 4` |
| **Apify Enrichment** | Disabled (skipped gracefully) | Enabled on final shortlist |
| **Embeddings** | Local Multilingual SentenceTransformers | Local or Paid API (`EMBEDDING_PROVIDER`) |
| **LLM Model** | Claude 3.5 Haiku | Claude 3.5 Haiku + Sonnet escalation on low confidence |

To switch tiers, simply update `.env`:
```env
PLAN_TIER=paid
```
and restart the application.

---

## Running Automated Tests & Evaluations

### Backend Unit Tests
Execute the unit test suite with mocked providers (zero API cost):
```bash
cd backend
pytest tests/ -v
```

### Evaluation Benchmark
Run precision@10 evaluation against diverse industry benchmarks:
```bash
cd backend
python -m eval.eval
```
