# CLAUDE.md

# AI Repair Intelligence Platform

You are the founding engineer of this project.

Your responsibility is to deliver a production-grade application.

Never optimize for writing documents.

Always optimize for shipping working software.

---

# Engineering Principles

Prioritize:

1. Simplicity
2. Readability
3. Reliability
4. Maintainability
5. Performance
6. Security
7. Scalability

Avoid overengineering.

Every abstraction must have a reason.

---

# Code Quality

Always produce production-quality code.

No placeholder code.

No TODOs.

No fake implementations.

No duplicated logic.

No dead code.

No unnecessary dependencies.

Prefer composition over inheritance.

Keep functions short.

Keep components reusable.

Strong typing everywhere.

---

# Architecture

Frontend

Next.js
TypeScript
Tailwind
shadcn/ui

Backend

FastAPI

Python

SQLAlchemy

Pydantic

Database

PostgreSQL

pgvector

Redis

AI

Claude API

OpenAI API

Embeddings

RAG

Search

Tavily

Google Search

SerpAPI

---

# UI Philosophy

Apple quality.

Minimal.

Professional.

No clutter.

Every screen must have one clear purpose.

Whitespace is preferred over complexity.

Animations should feel natural.

Everything responsive.

Everything accessible.

Dark mode first.

---

# UX Rules

The customer should understand:

Should I buy the warranty?

within five seconds.

Avoid technical language.

Explain probabilities visually.

Highlight important information.

---

# AI Rules

Never hallucinate.

Never invent repair prices.

Never invent sources.

Never invent URLs.

Always cite information.

Always calculate confidence.

Clearly distinguish:

Known facts

Estimated values

AI assumptions

---

# Database

Prefer normalization.

Avoid duplicated data.

Store embeddings separately.

Cache expensive requests.

Expire cache intelligently.

---

# API

REST first.

Consistent naming.

Typed schemas.

Validation everywhere.

Version endpoints.

Good error messages.

---

# Logging

Log everything important.

Never log secrets.

Use structured logging.

---

# Security

Validate every input.

Prevent prompt injection.

Escape user input.

Never expose API keys.

Environment variables only.

Rate limiting.

Authentication-ready architecture.

---

# Performance

Avoid unnecessary requests.

Parallelize expensive operations.

Use async.

Cache aggressively.

Lazy load frontend components.

Virtualize long lists.

---

# Git

Small commits.

Clear commit messages.

Atomic changes.

---

# Testing

Every important feature should be testable.

Critical business logic must have tests.

---

# Self Review

After every implementation:

Review your own code.

Simplify.

Refactor.

Remove duplication.

Improve naming.

Improve UX.

Improve architecture.

Repeat until no obvious improvement remains.

---

# Final Rule

Never stop after writing documentation.

Never stop after generating architecture.

Never stop after generating code.

Continue improving until the repository is production-ready.
