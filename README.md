# Closira Enquiry Engine

A lightweight backend service that simulates Closira's core customer enquiry-handling workflow. Built with **Python + FastAPI**, async processing via **BackgroundTasks**, and **SQLite** via `aiosqlite`.

Accepts inbound customer enquiries across WhatsApp, email, and phone — classifies them against hardcoded SOPs using keyword matching, suggests automated responses, and escalates unmatched enquiries for human review.

---

## Table of Contents

- [Setup & Run](#setup--run)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Database Schema & Reasoning](#database-schema--reasoning)
- [Async Processing: BackgroundTasks vs Celery](#async-processing-backgroundtasks-vs-celery)
- [SOP Matching Logic](#sop-matching-logic)
- [Running Tests](#running-tests)
- [Trade-offs & Known Limitations](#trade-offs--known-limitations)

---

## Setup & Run

### Prerequisites
- Python 3.10+
- pip

### Steps

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd closira-backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file (defaults are fine for local dev)
cp .env.example .env

# 5. Run the server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be live at:
- **Base URL:** `http://localhost:8000`
- **Interactive Docs (Swagger):** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

The SQLite database (`closira.db`) and all tables are created automatically on first startup — no migrations needed.

---

## Project Structure

```
closira-backend/
├── src/
│   ├── main.py              # FastAPI app, lifespan, global error handler
│   ├── config.py            # Pydantic settings (reads .env)
│   ├── logger.py            # Structured JSON logging setup
│   ├── database.py          # Async SQLAlchemy engine, session factory, init_db()
│   ├── models.py            # ORM models: Enquiry, StatusEvent, enums
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── service.py           # Business logic: create, escalate, follow-up
│   ├── sop_matcher.py       # Keyword-based SOP matching engine
│   ├── routes.py            # All API endpoint handlers
│   └── worker.py            # Background task: match SOP or auto-escalate
├── tests/
│   ├── conftest.py          # Pytest fixtures, isolated test DB
│   ├── test_endpoints.py    # API integration tests (all 5 endpoints)
│   └── test_sop_matcher.py  # Unit tests for SOP matching logic
├── logs/                    # Structured JSON logs (gitignored)
├── .env.example             # Environment template
├── .gitignore
├── api_tests.http           # VS Code REST Client file (all endpoints)
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/enquiry` | Create a new inbound enquiry. Returns `job_id` immediately (202). |
| `POST` | `/enquiry/{id}/followup` | Schedule a follow-up (delay in minutes + optional template). |
| `POST` | `/enquiry/{id}/escalate` | Manually escalate to a human agent with a reason. |
| `GET` | `/enquiry/{id}/history` | Full history: message, SOP match, suggested response, timeline. |
| `GET` | `/health` | API status + database connectivity check. |

Full interactive docs with example payloads at `/docs` after running the server.

### Example: Create an Enquiry

```bash
curl -X POST http://localhost:8000/enquiry \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Sarah Mitchell",
    "channel": "whatsapp",
    "message": "Hi, I wanted to know about your pricing plans."
  }'
```

**Response (202 Accepted):**
```json
{
  "job_id": "enq_a3f9c821",
  "status": "new",
  "message": "Enquiry received and queued for processing."
}
```

### Example: Get History (after background task runs)

```bash
curl http://localhost:8000/enquiry/enq_a3f9c821/history
```

**Response:**
```json
{
  "id": "enq_a3f9c821",
  "customer_name": "Sarah Mitchell",
  "channel": "whatsapp",
  "message": "Hi, I wanted to know about your pricing plans.",
  "status": "sop_matched",
  "sop_matched": "pricing_question",
  "suggested_response": "Great question! Our pricing depends on the package you choose...",
  "escalation_reason": null,
  "created_at": "2025-05-24T10:30:00",
  "updated_at": "2025-05-24T10:30:01",
  "timeline": [
    { "id": "...", "status": "new", "note": "Enquiry received and queued for processing.", "created_at": "..." },
    { "id": "...", "status": "sop_matched", "note": "SOP matched: pricing_question", "created_at": "..." }
  ]
}
```

### Example: Escalate

```bash
curl -X POST http://localhost:8000/enquiry/enq_a3f9c821/escalate \
  -H "Content-Type: application/json" \
  -d '{"reason": "Customer is very upset and demanding a manager."}'
```

**Response:**
```json
{
  "enquiry_id": "enq_a3f9c821",
  "status": "escalated",
  "reason": "Customer is very upset and demanding a manager.",
  "message": "Enquiry escalated to a human agent."
}
```

### Example: Schedule Follow-up

```bash
curl -X POST http://localhost:8000/enquiry/enq_a3f9c821/followup \
  -H "Content-Type: application/json" \
  -d '{"delay_minutes": 30, "message_template": "Hi {customer_name}, following up!"}'
```

**Response:**
```json
{
  "enquiry_id": "enq_a3f9c821",
  "status": "follow_up_scheduled",
  "follow_up_in_minutes": 30,
  "message": "Follow-up scheduled successfully."
}
```

---

## Database Schema & Reasoning

### Why SQLite?

1. **Zero setup friction** — No Docker, no server process, no connection string configuration. Clone and run in under 2 minutes.
2. **Async support** — `aiosqlite` provides a proper async driver compatible with SQLAlchemy 2.0's async engine.
3. **Good enough for a prototype** — Handles concurrent reads well, serialises writes acceptably for demo workloads.

**Switching to PostgreSQL** requires only:
1. Change `DATABASE_URL` in `.env` to `postgresql+asyncpg://user:pass@host/db`
2. Add `asyncpg` to requirements
3. No application code changes.

### Schema

```
┌──────────────────────────────────────────────────────┐
│  enquiries                                           │
├──────────────────┬───────────────────────────────────┤
│ id               │ STRING PK (enq_<uuid8>)           │
│ customer_name    │ STRING NOT NULL                   │
│ channel          │ ENUM (whatsapp, email, call)       │
│ message          │ TEXT NOT NULL                     │
│ status           │ ENUM (new, processing, ...)        │
│ sop_matched      │ STRING NULLABLE                   │
│ suggested_response│ TEXT NULLABLE                    │
│ escalation_reason│ TEXT NULLABLE                     │
│ follow_up_delay_minutes │ STRING NULLABLE            │
│ follow_up_template│ TEXT NULLABLE                    │
│ created_at       │ DATETIME (indexed)                │
│ updated_at       │ DATETIME                          │
└──────────────────┴───────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  status_events (append-only audit log)               │
├──────────────────┬───────────────────────────────────┤
│ id               │ UUID PK                           │
│ enquiry_id       │ FK → enquiries.id (indexed)       │
│ status           │ ENUM                              │
│ note             │ TEXT NULLABLE                     │
│ created_at       │ DATETIME                          │
└──────────────────┴───────────────────────────────────┘
```

**Status lifecycle:**
```
new → processing → sop_matched
                 ↘ escalated (auto, no SOP match)
new → follow_up_scheduled
any → escalated (manual)
```

**Design notes:**
- `StatusEvent` is an append-only audit log — every status change is a new row, never an update. This gives full traceability.
- `enquiries.status` stores the current state for fast lookups (denormalised).
- Human-readable IDs (`enq_<8-char-hex>`) make logs and debugging easy.

---

## Async Processing: BackgroundTasks vs Celery

### Decision: FastAPI BackgroundTasks ✅

| Factor | FastAPI BackgroundTasks | Celery |
|--------|------------------------|--------|
| Setup complexity | Zero — built into FastAPI | High — needs Redis/RabbitMQ broker |
| Dependencies | None extra | `celery`, `redis`, Docker |
| Suitable for | Lightweight, single-process tasks | Distributed, high-volume workloads |
| Retry support | Manual | Built-in |
| Monitoring | Via structured logs | Flower dashboard |
| Dev experience | Clone and run | Docker-compose required |

**Why BackgroundTasks won here:**

The SOP matching task is lightweight — an in-memory keyword scan + one DB write, completing in <10ms. Adding a Celery broker would triple setup complexity with no benefit at this scale. For an assignment that values "clone and run in 2 minutes", this is the right trade-off.

**When to switch to Celery:**
- Multi-server deployments where tasks must survive a server restart
- Tasks needing retries, rate limiting, or scheduling (e.g., actually *sending* the follow-up after N minutes)
- Workloads exceeding ~100 concurrent enquiries/second

---

## SOP Matching Logic

Five hardcoded SOPs defined in `src/sop_matcher.py`:

| SOP Name | Trigger Keywords |
|----------|-----------------|
| `booking_enquiry` | book, appointment, schedule, reserve, slot |
| `pricing_question` | price, cost, fee, quote, charge, how much, rate, pricing |
| `complaint` | complaint, unhappy, disappointed, refund, angry, poor, bad |
| `after_hours` | closed, after hours, tonight, weekend, holiday |
| `general_support` | help, support, issue, problem, not working, broken, error |

**Matching rules:**
- Case-insensitive
- Highest keyword-hit-count wins (not first-match)
- If **no SOP matches**, the enquiry is **automatically escalated** with reason: `"No SOP matched for inbound message. Requires human review."`
- Escalation event is logged in structured JSON format

---

## Running Tests

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Only SOP unit tests
pytest tests/test_sop_matcher.py -v

# Only API integration tests
pytest tests/test_endpoints.py -v
```

Tests use a **separate file-based SQLite database** (`test_closira.db`) — fully isolated from dev data. Schema is recreated fresh for each test function.

**Test coverage:**
- Health check endpoint
- Enquiry creation (happy path + validation errors)
- History retrieval (found + 404)
- Escalation (happy path + 404 + timeline verification)
- Follow-up scheduling (happy path + 404 + invalid delay)
- SOP matching (all 5 SOPs + no-match + case insensitivity + scoring)

---

## Trade-offs & Known Limitations

| Area | Trade-off / Limitation |
|------|------------------------|
| **Follow-up execution** | `delay_minutes` is stored but the follow-up is never actually sent. Production would need Celery beat or APScheduler. |
| **Multi-tenancy** | No `tenant_id`. Production would isolate data per business. |
| **SQLite concurrency** | Serialises writes — fine for a prototype, bottleneck under load. |
| **SOP matching** | Keyword-based, highest-score-wins. A real system would use embeddings or a classifier. |
| **Auth** | No authentication. Production would require JWT bearer tokens. |
| **Task durability** | BackgroundTasks are in-process — if the server crashes mid-task, the task is lost. |
| **Pagination** | History endpoint returns all events. Production would paginate. |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | Closira Enquiry Engine | Shown in docs and logs |
| `APP_VERSION` | 1.0.0 | API version |
| `APP_ENV` | development | Environment identifier |
| `DEBUG` | false | Enable SQL echo logging |
| `DATABASE_URL` | sqlite+aiosqlite:///./closira.db | DB connection string |
| `LOG_LEVEL` | INFO | Logging level |
