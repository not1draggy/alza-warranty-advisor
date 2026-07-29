# Roadmap

Status as of the current build. Items are marked done only when the feature works
end to end, is tested, and handles its failure cases.

## Phase 1 — Foundation ✅

- [x] Project setup: backend (FastAPI) and frontend (Next.js) skeletons
- [x] Configuration from environment variables only, with typed settings
- [x] Structured logging with request correlation ids
- [x] Typed error hierarchy and a single JSON error envelope
- [x] PostgreSQL schema with pgvector, Alembic migrations, HNSW index
- [x] Redis cache and Redis-backed rate limiting with in-process fallback
- [x] Optional accounts: bcrypt password hashing, JWT access tokens
- [x] Docker images for both services, Docker Compose for the whole stack

## Phase 2 — Evidence pipeline ✅

- [x] Product identification agent with calibrated confidence
- [x] Query-planning agent with a deterministic fallback plan
- [x] Modular search: Tavily, SerpAPI, Google Programmable Search
- [x] Canonical-URL de-duplication and per-domain diversity limits
- [x] Deterministic source classification, quality scoring and recency decay
- [x] Prompt-injection guard on user input and on retrieved evidence

## Phase 3 — RAG ✅

- [x] Sentence-aware chunking with overlap
- [x] Embedding generation, stored separately from documents
- [x] pgvector cosine retrieval with a keyword fallback when embeddings are absent
- [x] Content-hash de-duplication so re-ingesting a page is a no-op

## Phase 4 — Analysis and interface ✅

- [x] Repair-extraction agent with output clamping and citation validation
- [x] Probability and cost mathematics as pure, tested functions
- [x] Risk scoring, confidence scoring, verdict thresholds
- [x] Response composer with a deterministic fallback narrative
- [x] Numeric verification of generated wording against the computed analysis
- [x] Class-level estimate when no evidence is retrievable, labelled and capped
- [x] Streaming orchestrator emitting per-stage progress over SSE
- [x] Analysis UI: verdict, economics, failure modes, sources, assumptions
- [x] Two custom SVG charts with hover, keyboard focus and table views
- [x] Search history for signed-in users and anonymous sessions
- [x] Dark mode first with an explicitly designed light theme
- [x] Loading, empty, error and provider-missing states throughout
- [x] Slovak throughout: interface, generated wording, number and date formatting

## Phase 5 — Production ✅

- [x] 248 backend tests: business logic, guards, providers, full HTTP surface
- [x] End-to-end browser run against the real API and the production web build
- [x] Lint, format and type checks clean (ruff, mypy, eslint, tsc)
- [x] GitHub Actions: backend, migrations against real pgvector, frontend, images
- [x] Health, readiness and capability endpoints
- [x] Security headers, CORS allow-list, unprivileged containers

## Next

Work that would add value but is not required for the product to function:

- [ ] Full-page fetching for search results that expose only a short snippet
- [ ] Currency conversion with a cited, dated exchange-rate source
- [ ] Per-country service pricing (labour rates differ widely across markets)
- [ ] Human review queue for analyses with low confidence
- [ ] Prometheus metrics endpoint alongside the existing structured logs
- [ ] Frontend component tests once a browser runner is available in CI
