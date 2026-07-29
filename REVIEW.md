# Self review

A pass over the finished implementation, looking for defects rather than for
things to praise. Everything under *Fixed* was found and corrected in this build;
each carries a regression test.

## Fixed

### 1. Rate-limit scope was caller-controlled (security)

`enforce_rate_limit` declared `scope: str = "api"`. FastAPI turns a plain
argument on a dependency into a **query parameter**, so any caller could send
`?scope=<random>` and land in a fresh bucket on every request — walking straight
past the limit.

Fixed by removing the parameter and fixing the scope inside the function; the
limiter's `scope` is now keyword-only so it cannot be re-exposed by accident.
`tests/test_hardening.py` asserts that no operation in the OpenAPI schema exposes
a `scope` parameter.

### 2. Evidence links dropped on repeat analyses (correctness)

Citations were resolved only against the sources ingested during the current
request. Retrieval is product-scoped and returns passages from earlier runs too,
so on a second analysis of the same product any passage from a previously stored
page produced no `FailureModeCitation` row and left `RepairCostEstimate.source_id`
null. The analysis payload still showed citations, so this only surfaced in the
stored repair profile behind `GET /products/{id}` — quiet data loss.

Fixed with `repository.sources_by_url`, which resolves against the whole store.
The regression test runs two analyses with *different* search results and asserts
the citation rows exist; reverting the fix makes it fail.

### 3. Positional placeholders used as citation identifiers

`Citation.source_id` was set to `f"chunk-{index}"` — a position in a transient
list, not an identifier. It is now the stored source id, falling back to the URL
when a source has no row yet.

### 4. Unbounded growth in the rate-limiter fallback

The in-process window used when Redis is unavailable never pruned its map, so a
prolonged outage turned into a slow memory leak. It now evicts expired entries
past a ceiling and clears entirely under a key-space flood.

### 5. `LIKE` metacharacters unescaped in product search

Not an injection — the query was parameterised — but `%` or `_` in the search
term acted as wildcards, so `?q=%%` returned the entire table. Metacharacters are
now escaped with an explicit `ESCAPE` clause.

### 6. Provider typing was not actually checked

`system` and `output_config` were passed to the Anthropic SDK as bare `dict`s, so
mypy could not verify them against the SDK's overloads. They now use
`TextBlockParam`, `OutputConfigParam` and `JSONOutputFormatParam`; `mypy app`
runs clean and is enforced in CI.

### 7. Frontend: choosing an example discarded the form

The form was remounted via `key`, resetting the price and term the customer had
already typed. It now syncs the product field only.

## Found by running it, not by testing it

The suite was green when the following three were still broken. Booting the real
stack and driving the real UI in a browser is what surfaced them.

### 8. `CORS_ORIGINS` crashed startup (deployment-blocking)

`cors_origins` was typed as `list[str]`. pydantic-settings JSON-decodes
list-typed fields **inside the environment source**, before any validator runs, so
the comma-separated value shipped in `.env.example` and `docker-compose.yml`
raised `SettingsError` and the API never started. Tests never hit it because they
never set the variable.

It is now read as a string and parsed into a list by a property that accepts both
the comma form and a JSON array.

### 9. The wording could contradict the numbers

The composed narrative claimed "well above the 66 EUR the extension costs" while
the panel beside it read €49 expected against a €66 extension — and the headline
said "Worth buying" while the computed verdict was `not_recommended`. The prompt
forbids inventing figures, but nothing enforced it.

Two changes:

* **The headline is no longer written by the model.** It is derived from the
  verdict, so the recommendation and the wording cannot disagree by construction.
* **Every figure in the summary and reasons is verified** against the values the
  pipeline computed (`agents/verification.py`). Any monetary amount or percentage
  that does not match one, within rounding tolerance, causes the whole narrative
  to be discarded in favour of the deterministic template. Bare integers are
  ignored — "3 years" is not a claim about money or risk.

### 10. The sticky header cut the verdict in half

`scrollIntoView` on the result section ignored the sticky header, hiding the
verdict chip and the top of the headline — the two things the customer is meant
to read first. Fixed with `scroll-mt-20`.

## Deliberate decisions worth stating

**No fabricated baselines.** An earlier design had category-level default failure
rates for products with no evidence. That is inventing data, so it was removed
along with the column that stored it. With no usable evidence the verdict is
`insufficient_evidence` and no cost figures are shown at all.

**Failure modes are treated as independent.** Correlated failures would raise the
joint probability, so independence understates risk. That is the right direction
to be wrong in: the system never overstates the case for buying the warranty.

**No arbitrary page fetching.** Evidence comes from search-provider snippets and
the full text Tavily returns, not from fetching URLs the model chooses. Fetching
arbitrary URLs server-side is an SSRF surface that would need address filtering
and redirect control to do safely; the extra evidence did not justify that here.
It is on the roadmap.

**Worst case is the most expensive single repair,** not the sum of all failures.
Summing would describe a scenario where everything breaks at once, which is not
what a customer means by "worst case".

**The composer sees no evidence.** It receives the finished analysis and rewrites
it in plain language. It cannot introduce a number, and when it returns nothing
usable a deterministic template built from the same figures takes over.

## Known limitations

* Repair prices are not currency-converted. Evidence in another currency keeps
  its own and says so in the note rather than being converted at an uncited rate.
* Labour rates differ widely by country; the estimate reflects whatever markets
  the retrieved sources happen to describe.
* The frontend has no automated tests — it is verified by type checking, linting
  and a production build. A browser test runner is on the roadmap.
* Docker image builds could not be executed in the development sandbox: the
  egress policy returns 403 for Docker Hub's blob CDN. `docker compose config`
  validates locally, and CI builds both images — that job is green, so the
  Dockerfiles are verified, just not from inside the sandbox.
