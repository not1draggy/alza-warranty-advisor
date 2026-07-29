# Warranty Advisor AI

Answers one question in five seconds: **should I buy this extended warranty?**

The customer types a product and the price of the extension. The system finds
public repair information for that model, works out what repairs are likely to
cost after the manufacturer's warranty ends, and compares that against the price
of the extension — showing its sources and its uncertainty.

```
Samsung 75NU8000  ·  +3 years  ·  65.70 €

  Worth buying — repairs usually cost more
  21% chance of a repair · 152 € expected spend · 66 € extension

  Most likely: backlight failure, typically 280 €   [samsung.com] [ifixit.com]
  Confidence 72% · 9 sources across 5 websites
```

---

## Quick start

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY and TAVILY_API_KEY
make up                       # docker compose up --build -d
```

* Web app — <http://localhost:3000>
* API docs — <http://localhost:8000/docs>
* Health — <http://localhost:8000/api/v1/health>

The stack starts without any provider keys. In that state it reports honestly
that it cannot produce an estimate rather than inventing one; `GET
/api/v1/capabilities` tells the UI which providers are live.

### Minimum useful configuration

| Variable | Why it matters |
| --- | --- |
| `ANTHROPIC_API_KEY` | Product identification, evidence extraction, wording |
| `TAVILY_API_KEY` | Web search (or `SERPAPI_API_KEY`, or Google Programmable Search) |
| `OPENAI_API_KEY` | Embeddings for vector retrieval; without it retrieval falls back to keyword matching |
| `SECRET_KEY` | Signs access tokens — set a real value in production (`openssl rand -hex 32`) |

---

## How an analysis is produced

```
  guard ──▶ cache ──▶ identify ──▶ plan queries ──▶ search ──▶ verify sources
                                                                     │
    persist ◀── compose ◀── quantify ◀── extract ◀── store + retrieve (RAG)
```

| Stage | What happens | Where |
| --- | --- | --- |
| **Guard** | Rejects input that reads like an instruction rather than a product name; sanitises retrieved text before it reaches any prompt | `agents/guard.py` |
| **Cache** | An identical (product, term, price, currency) request within the TTL is served from the stored analysis | `services/repository.py` |
| **Identify** | Manufacturer, model, category, release year, aliases, and a calibrated identification confidence | `agents/identify.py` |
| **Search** | 4–7 generated queries fanned out across every configured provider, de-duplicated by canonical URL | `agents/evidence.py`, `services/search/` |
| **Verify** | Deterministic source classification and scoring; low-quality domains are dropped and no single site may supply more than three pages | `services/source_quality.py` |
| **Retrieve** | Documents are chunked, embedded and stored once; retrieval is pgvector cosine similarity with a keyword fallback | `services/rag.py` |
| **Extract** | Failure modes with annual probability, cost range, difficulty, parts availability, and the evidence indices that support them | `agents/extraction.py` |
| **Quantify** | Probability and cost mathematics, risk score, confidence score, verdict | `agents/risk.py`, `agents/confidence.py` |
| **Compose** | Plain-language wording over numbers it is not allowed to change; the headline comes from the verdict and every figure is verified before display | `agents/composer.py`, `agents/verification.py` |

The streaming endpoint emits each stage as a Server-Sent Event, so the UI shows
real progress instead of a spinner.

### The mathematics

Every number the customer sees comes from these formulas, which live in
`backend/app/agents/risk.py` and are covered by tests:

| Quantity | Formula |
| --- | --- |
| Probability of failure *i* over *n* years | `1 - (1 - p_i)^n` |
| Probability of any failure | `1 - Π(1 - w_i)` |
| Expected repair spend | `Σ w_i × typical_i` |
| Average repair, given one happens | `expected / P(any failure)` |
| Worst case | `max(maximum_i)` — the most expensive single repair |
| Break-even probability | `warranty_price / average_repair` |
| Risk score (0–100) | `100 × (0.50·likelihood + 0.30·exposure + 0.20·severity)` |

Failure modes are treated as independent. That is the conservative choice:
correlated failures would raise the joint probability, so the model never
overstates the case for buying the warranty.

### Never inventing data

* Extraction may only use text present in the retrieved evidence.
* Every displayed value carries an origin — `sourced`, `derived` or `estimated`
  — and the UI labels it.
* A citation index the model cannot support downgrades that value to `estimated`
  automatically (`agents/extraction.py`).
* Absurd outputs are clamped: annual probability caps at 0.35, cost ranges are
  reordered rather than trusted blindly, zero-cost entries are dropped.
* With no usable evidence the verdict is `insufficient_evidence` and no cost
  figures are shown at all.
* The verdict headline is derived from the computed decision, so the wording can
  never contradict the recommendation.
* Every monetary amount and percentage in the generated wording is matched against
  the values the pipeline computed; an unsupported figure discards the whole
  narrative in favour of a deterministic one (`agents/verification.py`).

---

## Repository layout

```
backend/
  app/
    agents/       identification, evidence, extraction, risk, confidence, composer, guard, orchestrator
    api/v1/       analysis (sync + SSE), history, products, auth, health
    core/         settings, structured logging, typed errors, rate limiting, security
    db/           SQLAlchemy models, async session
    schemas/      request/response contracts
    services/     LLM router, search router, embeddings, RAG store, cache, repository
  alembic/        migrations (pgvector extension + HNSW index)
  tests/          218 tests
frontend/
  src/app/        routes: analysis, history
  src/components/ verdict, detail panels, SVG charts, form, progress
  src/lib/        typed API client, SSE reader, formatting
```

### Data model

`Product` ← `FailureMode` ← `RepairCostEstimate` / `FailureModeCitation` → `Source`
← `Document` ← `DocumentChunk` (embedding). `Analysis` stores both the normalised
outcome columns and the rendered payload, so a cache hit is a single row read.
`SearchHistory` links a user or an anonymous session id to an analysis.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/analyses` | Run an analysis and return the result |
| `POST` | `/api/v1/analyses/stream` | Same, as Server-Sent Events (`stage`, `result`, `error`) |
| `GET` | `/api/v1/analyses/{id}` | Fetch a stored analysis |
| `GET` | `/api/v1/history` | Recent searches for a user or anonymous session |
| `GET` | `/api/v1/products` | Search products the system already knows |
| `GET` | `/api/v1/products/{id}` | Known repair profile for a product |
| `POST` | `/api/v1/auth/register` · `/login` · `GET /me` | Optional accounts for durable history |
| `GET` | `/api/v1/health` · `/ready` · `/capabilities` | Liveness, readiness, configured providers |

Errors share one envelope:

```json
{ "error": { "code": "unsafe_input", "message": "…", "request_id": "…" } }
```

---

## Development

```bash
make setup      # backend venv + frontend node_modules
make test       # pytest with coverage
make lint       # ruff, mypy, eslint, tsc
make dev-api    # uvicorn on :8000
make dev-web    # next dev on :3000
```

Tests run against SQLite with fake LLM and search providers, so no external
service or API key is needed. The model layer declares SQLite variants for the
JSONB and pgvector columns; migrations are additionally applied against real
PostgreSQL + pgvector in CI.

---

## Security

* Input is normalised and screened for prompt-injection and SQL-injection shapes
  before it reaches a model or the database.
* Retrieved web content is treated as untrusted data: role markers are stripped,
  instruction-shaped text is redacted, and prompts state that evidence is data.
* Redis-backed fixed-window rate limiting, with an in-process fallback so a cache
  outage degrades throughput rather than removing protection.
* Passwords are hashed with bcrypt; access tokens are signed JWTs.
* Secrets are read from the environment only, are never logged, and
  `/capabilities` reports provider names without keys.
* Both containers run as unprivileged users; security headers are applied by the
  API middleware and by Next.js.

---

## Integrating into a product page

The analysis endpoint is self-contained — product string, term, price, currency
in; verdict, economics and citations out. A product page can call it directly and
render the verdict headline plus `economics.expected_repair_cost`, or embed the
streaming endpoint for the full breakdown. `session_id` is optional and only
drives history.
