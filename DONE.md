# Definition of Done

The project is finished only if every box is true. Each line states what was
built and how it was verified.

- [x] **frontend complete** — Next.js 15 App Router, TypeScript, Tailwind,
      shadcn-style primitives, React Query. Analysis form, live streaming
      progress, verdict card, economics, failure modes, two charts, sources,
      assumptions, history. `npm run build` and `npm run lint` pass.

- [x] **backend complete** — FastAPI with SQLAlchemy 2 async, Pydantic v2
      schemas, versioned REST API: analysis (sync + SSE), history, products,
      auth, health, readiness, capabilities.

- [x] **AI agents complete** — identification, query planning, evidence
      verification, repair extraction, probability estimation, confidence
      scoring, citation handling, response composer, narrative verification,
      security guard, cache manager and the orchestrator that sequences them.
      The verdict headline is derived from the computed decision, and every
      figure in the generated wording is checked against the analysis before it
      is shown.

- [x] **search complete** — Tavily, SerpAPI and Google Programmable Search
      behind one interface, fanned out concurrently, de-duplicated by canonical
      URL, cached, and resilient to any single provider failing.

- [x] **caching complete** — Redis JSON cache for search results and product
      identity; analyses cached in PostgreSQL by request fingerprint with a TTL;
      `refresh: true` bypasses it. Every cache path degrades to a live call when
      Redis is unavailable.

- [x] **authentication complete** — register, login and `/me` with bcrypt
      hashing and signed JWTs. The product works anonymously; signing in moves
      history from a device-local session to the account.

- [x] **docker works** — Dockerfiles for both services (multi-stage, unprivileged
      users, health checks) and a Compose file wiring pgvector, Redis, the API
      and the web app with health-gated startup and migrations on boot.
      `docker compose config` validates. *Image builds could not be executed in
      this sandbox: the egress policy returns 403 for Docker Hub's blob CDN
      (`production.cloudfront.docker.com`). CI builds both images.*

- [x] **GitHub Actions work** — four jobs: backend lint/types/tests with a
      coverage floor, migrations applied and rolled back against real
      PostgreSQL + pgvector, frontend lint/typecheck/build, and both Docker
      images built with layer caching.

- [x] **tests pass** — 218 tests. Probability and cost mathematics, confidence
      scoring, source classification, the injection guard, extraction clamping,
      narrative verification, search de-duplication, provider failover, the
      orchestrator's degraded paths, and the full HTTP surface including SSE.
      Additionally verified by running the real stack and driving the real UI in
      a headless browser end to end.

- [x] **production ready** — health and readiness probes, graceful degradation
      when any provider is missing, request timeouts and retries, connection
      pooling, migrations on container start, restart policies.

- [x] **responsive** — fluid layout from 360px upwards; charts scale by viewBox;
      form and result grids reflow at `sm` and `lg`.

- [x] **secure** — prompt-injection and SQL-injection screening on input,
      sanitisation of retrieved content, parameterised queries throughout,
      rate limiting, bcrypt, JWT, CORS allow-list, security headers, secrets in
      environment variables only and never logged.

- [x] **accessible** — semantic landmarks, skip link, labelled form controls,
      `aria-live` progress and results, keyboard-focusable chart marks,
      `role="meter"` with numeric text beside every bar, icon + text for every
      verdict so nothing depends on colour, and `prefers-reduced-motion` support.

- [x] **monitoring** — `/health`, `/ready` (checks database and cache) and
      `/capabilities` (reports configured providers without exposing keys), plus
      per-request duration and status logging and container health checks.

- [x] **logging** — structlog with JSON output in production, request ids
      propagated through a context variable and returned in the `x-request-id`
      header and in error bodies. Secrets are never logged.

- [x] **documentation** — README covering the pipeline, the mathematics, the
      no-invention guarantees, the data model, the API and the security posture;
      ROADMAP with current status; REVIEW with the self-review findings;
      `.env.example`; Makefile with the common tasks.
