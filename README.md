# Closira Enquiry Engine

A production-grade FastAPI backend service that powers Closira's inbound customer enquiry pipeline. Handles enquiry creation, async SOP classification, follow-ups, escalations, and full conversation history tracking.

Built with **Python 3.11+**, **FastAPI**, **Async SQLAlchemy**, and **SQLite** — designed to demonstrate clean backend architecture, async workflows, and service-oriented design.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Setup & Run](#setup--run)
- [API Documentation](#api-documentation)
- [SOP Matching Engine](#sop-matching-engine)
- [Async Processing: BackgroundTasks vs Celery](#async-processing-backgroundtasks-vs-celery)
- [Database Design](#database-design)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [Trade-offs & Assumptions](#trade-offs--assumptions)
- [Future Improvements](#future-improvements)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Request                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Controller Layer (thin HTTP handlers)                           │
│  - Request validation (Pydantic)                                │
│  - Response formatting                                          │
│  - HTTP status codes                                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service Layer (business logic)                                  │
│  - Orchestrates operations                                      │
│  - Applies business rules                                       │
│  - Delegates to repositories                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository Layer (data access)                                  │
│  - SQLAlchemy queries                                           │
│  - Transaction management                                       │
│  - Query optimization                                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Database (SQLite / PostgreSQL)                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Background Workers                                             │
│  - SOP classification (async, non-blocking)                     │
│  - Auto-escalation on no match                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Pattern:** Controller → Service → Repository (clean separation of concerns)

---

## Project Structure

```
closira-backend/
├── src/
│   ├── app.py                          # FastAPI application factory
│   ├── config/
│   │   ├── settings.py                 # Pydantic settings (env management)
│   │   └── logging.py                  # Structured JSON logger setup
│   ├── constants/
│   │   ├── enums.py                    # Channel, EnquiryStatus enums
│   │   ├── messages.py                 # Centralised response messages
│   │   └── sop_catalog.py             # SOP definitions (keywords + responses)
│   ├── controllers/
│   │   ├── enquiry_controller.py       # Enquiry endpoints (thin handlers)
│   │   └── health_controller.py        # Health check endpoint
│   ├── db/
│   │   └── session.py                  # Async engine, session factory, init_db()
│   ├── middlewares/
│   │   └── error_handler.py            # Global exception handlers
│   ├── models/
│   │   ├── base.py                     # SQLAlchemy declarative base
│   │   ├── enquiry.py                  # Enquiry ORM model
│   │   └── status_event.py            # StatusEvent audit log model
│   ├── repositories/
│   │   └── enquiry_repository.py       # Data access layer
│   ├── routes/
│   │   └── __init__.py                 # Route registration
│   ├── schemas/
│   │   ├── enquiry.py                  # Request/response Pydantic models
│   │   └── responses.py               # Standard API response envelope
│   ├── services/
│   │   ├── enquiry_service.py          # Business logic orchestration
│   │   └── sop_matcher.py             # SOP classification engine
│   └── workers/
│       └── enquiry_worker.py           # Background task processor
├── tests/
│   ├── conftest.py                     # Test fixtures & DB setup
│   ├── test_enquiry_endpoints.py       # API integration tests
│   ├── test_health.py                  # Health endpoint tests
│   └── test_sop_matcher.py            # SOP matcher unit tests
├── logs/                               # Application logs (gitignored)
├── .env.example                        # Environment template
├── .gitignore
├── api_tests.http                      # VS Code REST Client test file
├── pytest.ini                          # Pytest configuration
├── requirements.txt                    # Python dependencies
└── README.md
```

---

## Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | FastAPI | Async-first, auto-generated docs, Pydantic integration |
| ORM | SQLAlchemy 2.0 (async) | Type-safe queries, relationship mapping, migration-ready |
| Database | SQLite + aiosqlite | Zero-setup dev experience, swap to PostgreSQL via env var |
| Validation | Pydantic v2 | Fast, type-safe, powers both schemas and settings |
| Logging | python-json-logger | Structured JSON logs, machine-parseable |
| Testing | pytest + httpx | Async test support, real HTTP client simulation |
| Server | Uvicorn | ASGI server, production-ready with workers |

---

## Setup & Run

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd closira-backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env            # Defaults work for local development

# 5. Start the server
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Base URL:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

The database and all tables are created automatically on first startup.

---

## API Documentation

### Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| `POST` | `/api/enquiry` | Create a new inbound enquiry | 202 |
| `POST` | `/api/enquiry/{id}/followup` | Schedule a follow-up | 200 |
| `POST` | `/api/enquiry/{id}/escalate` | Escalate to human agent | 200 |
| `GET` | `/api/enquiry/{id}/history` | Full history + timeline | 200 |
| `GET` | `/api/health` | Service health check | 200 |

### Standard Response Format

All endpoints return a consistent envelope:

```json
{
  "success": true,
  "message": "Human-readable description",
  "data": { },
  "metadata": { }
}
```

### Example: Create an Enquiry

```bash
curl -X POST http://localhost:8000/api/enquiry \
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
  "success": true,
  "message": "Enquiry received and queued for processing.",
  "data": {
    "enquiry_id": "enq_a3f9c821",
    "status": "new"
  },
  "metadata": {
    "async_processing": true
  }
}
```

### Example: Get History (after background processing)

```bash
curl http://localhost:8000/api/enquiry/enq_a3f9c821/history
```

**Response:**
```json
{
  "success": true,
  "message": "Enquiry history retrieved.",
  "data": {
    "id": "enq_a3f9c821",
    "customer_name": "Sarah Mitchell",
    "channel": "whatsapp",
    "message": "Hi, I wanted to know about your pricing plans.",
    "status": "sop_matched",
    "sop_matched": "pricing_question",
    "suggested_response": "Great question! Our pricing depends on...",
    "timeline": [
      { "status": "new", "note": "Enquiry received and queued for processing." },
      { "status": "sop_matched", "note": "SOP matched: pricing_question" }
    ]
  },
  "metadata": { "timeline_count": 2 }
}
```

---

## SOP Matching Engine

The SOP (Standard Operating Procedure) matcher classifies inbound messages using keyword-based scoring.

### Supported SOPs

| SOP | Trigger Keywords |
|-----|-----------------|
| `booking_enquiry` | book, appointment, schedule, reserve, slot |
| `pricing_question` | price, cost, fee, quote, charge, how much, rate |
| `complaint` | complaint, unhappy, disappointed, refund, angry |
| `after_hours` | closed, after hours, tonight, weekend, holiday |
| `general_support` | help, support, issue, problem, not working, broken |

### Matching Strategy

1. Normalize message to lowercase
2. Score each SOP by counting keyword occurrences
3. Highest-scoring SOP above the confidence threshold wins
4. If no SOP matches → auto-escalate for human review

### Why Keyword-Based?

- **Transparent:** Every match decision is explainable and auditable
- **Fast:** Sub-millisecond execution, no external API calls
- **Extensible:** Add new SOPs by appending to the catalog
- **Production path:** Replace with embeddings or a fine-tuned classifier

---

## Async Processing: BackgroundTasks vs Celery

### Decision: FastAPI BackgroundTasks ✅

| Factor | BackgroundTasks | Celery |
|--------|----------------|--------|
| Setup | Zero — built into FastAPI | Redis/RabbitMQ broker required |
| Dependencies | None | celery, redis, Docker |
| Best for | Lightweight, single-process tasks | Distributed, high-volume workloads |
| Retry support | Manual | Built-in |
| Dev experience | Clone and run | Docker-compose required |

**Why BackgroundTasks here:**
- SOP matching is lightweight (~1ms: keyword scan + 1 DB write)
- Single-process workload — no need for a message broker
- Zero additional infrastructure for development

**When to switch to Celery:**
- Multi-server deployments where tasks must survive restarts
- Tasks needing retries, rate limiting, or delayed scheduling
- Workloads exceeding ~100 concurrent enquiries/second

---

## Database Design

### Schema

```
┌─────────────────────────────────────────────────────┐
│  enquiries                                          │
├──────────────────────┬──────────────────────────────┤
│ id                   │ STRING PK (enq_<uuid8>)      │
│ customer_name        │ STRING NOT NULL (indexed)     │
│ channel              │ ENUM (whatsapp/email/call)    │
│ message              │ TEXT NOT NULL                 │
│ status               │ ENUM (indexed)               │
│ sop_matched          │ STRING NULLABLE              │
│ suggested_response   │ TEXT NULLABLE                │
│ escalation_reason    │ TEXT NULLABLE                │
│ follow_up_delay_min  │ STRING NULLABLE              │
│ follow_up_template   │ TEXT NULLABLE                │
│ created_at           │ DATETIME (indexed)           │
│ updated_at           │ DATETIME                     │
└──────────────────────┴──────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────┐
│  status_events (append-only audit log)              │
├──────────────────────┬──────────────────────────────┤
│ id                   │ UUID PK                      │
│ enquiry_id           │ FK → enquiries.id            │
│ status               │ ENUM                         │
│ note                 │ TEXT NULLABLE                │
│ created_at           │ DATETIME                     │
└──────────────────────┴──────────────────────────────┘
```

### Design Decisions

- **Append-only events:** StatusEvent is an immutable audit log — never updated, only appended
- **Denormalized status:** `enquiries.status` stores current state for fast reads
- **Human-readable IDs:** `enq_<8-char-hex>` for easy debugging in logs
- **Composite indexes:** Optimized for common query patterns (channel+status, created_at)

### Switching to PostgreSQL

```bash
# 1. Update .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/closira

# 2. Add asyncpg to requirements
pip install asyncpg

# No application code changes needed.
```

---

## Running Tests

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Run specific test file
pytest tests/test_sop_matcher.py -v

# Run only endpoint tests
pytest tests/test_enquiry_endpoints.py -v
```

Tests use a **separate file-based SQLite database** (`test_closira.db`) — fully isolated from development data. The schema is recreated fresh for each test function.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | Closira Enquiry Engine | Application name (shown in docs/logs) |
| `APP_VERSION` | 1.0.0 | API version |
| `APP_ENV` | development | Environment identifier |
| `DEBUG` | false | Enable SQLAlchemy echo and debug logging |
| `DATABASE_URL` | sqlite+aiosqlite:///./closira.db | Database connection string |
| `LOG_LEVEL` | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `SOP_CONFIDENCE_THRESHOLD` | 1 | Minimum keyword hits for SOP match |

---

## Trade-offs & Assumptions

| Area | Decision | Rationale |
|------|----------|-----------|
| **Database** | SQLite for dev | Zero-setup, swap to PostgreSQL via env var |
| **Background tasks** | FastAPI BackgroundTasks | No broker needed at this scale |
| **SOP matching** | Keyword-based | Transparent, fast, auditable |
| **Follow-up execution** | Stored but not sent | Would need Celery beat in production |
| **Authentication** | None | Out of scope — would use JWT in production |
| **Multi-tenancy** | Single tenant | No tenant_id — production would isolate data |
| **Migrations** | Auto-create tables | Production would use Alembic |

---

## Future Improvements

- **Authentication:** JWT-based auth with role-based access control
- **Alembic migrations:** Version-controlled schema changes
- **Celery integration:** For delayed follow-up execution and retries
- **Semantic SOP matching:** Replace keywords with sentence embeddings
- **WebSocket support:** Real-time enquiry status updates
- **Rate limiting:** Protect endpoints from abuse
- **Pagination:** For listing enquiries at scale
- **Multi-tenancy:** Tenant isolation for SaaS deployment
- **Observability:** OpenTelemetry tracing, Prometheus metrics
- **CI/CD:** GitHub Actions pipeline with automated testing

---

## License

MIT
