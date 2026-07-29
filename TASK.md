# Warranty Advisor AI
## Product Specification

# Mission

Build a complete production-ready AI application for Alza that helps customers decide whether purchasing an extended warranty is financially worthwhile.

This is NOT a prototype.

This is NOT a proof of concept.

This is NOT a design exercise.

Build a real production-ready application.

The repository should be deployable using Docker Compose with minimal configuration.

---

# Business Problem

Customers often refuse to purchase an extended warranty because they only see its price.

Example:

Extended Warranty

3 years

65.70 €

The customer has no idea whether repairing the product after the manufacturer's warranty expires would cost €50 or €500.

The application should answer this question using publicly available repair information.

---

# Goal

The application should estimate the financial risk of owning a product after the manufacturer's warranty expires.

The customer should immediately understand whether the warranty is financially worthwhile.

The explanation should be understandable for non-technical users.

---

# User Input

The user enters:

• Product name

or

• Model number

Example:

Samsung 75NU8000

Warranty extension:

+1 year, +2 years, +3 years

Warranty price:

The user will type the price

---

# System Workflow

The application must automatically perform the following steps.

## Step 1

Identify the exact product.

Determine:

Manufacturer

Model

Category

Release year

Technical specifications

Aliases

Alternative model names

Country variations

---

## Step 2

Search public information.

Search sources such as:

Authorized service centers

Manufacturer documentation

Repair manuals

OEM spare part catalogs

Repair communities

Repair forums

Public repair databases

Service price lists

Diagnostic price lists

Technician travel fees

Labor costs

Replacement part prices

Reliability reports

Known defects

Warranty discussions

Official manufacturer documentation

High-quality repair websites

---

## Step 3

Extract repair information.

Identify:

Common failures

Affected components

Typical repair prices

Typical labor costs

Availability of parts

Difficulty of repair

Repair time

Repair success rate

---

## Step 4

Estimate probabilities.

Estimate:

Probability of each failure

Expected repair cost

Worst-case repair cost

Average repair cost

Probability-weighted repair value

Risk score

Confidence score

Mark clearly whenever a value is estimated.

---

## Step 5

Generate customer explanation.

The explanation should answer:

Should I buy the warranty?

Why?

What usually fails?

How expensive are repairs?

How risky is this model?

How reliable is the estimate?

---

# Output

The final answer should contain:

Product summary

Repair summary

Most common failures

Expected repair costs

Average repair costs

Worst case repair costs

Failure probability

Risk score

Warranty recommendation

Confidence score

Retrieval date

Sources

Source quality

Charts where appropriate

Warnings about uncertainty

---

# Citations

Every factual statement must include:

Source

Retrieved date

Confidence score

Estimated values clearly labeled

Never invent:

URLs

Repair prices

Statistics

Failure probabilities

Sources

If insufficient evidence exists, explain the uncertainty instead of guessing.

---

# AI Architecture

Implement an agent-based architecture.

Suggested agents:

Product Identification Agent

Web Search Agent

Source Ranking Agent

Citation Verification Agent

Repair Cost Agent

Failure Analysis Agent

Probability Estimation Agent

Confidence Scoring Agent

Response Composer

Cache Manager

RAG Agent

The architecture may be improved if a better design exists.

---

# Search

The system should support:

Tavily

Google Search

SerpAPI

Future search providers

Search should be modular.

---

# RAG

Implement Retrieval-Augmented Generation.

Store:

Documents

Embeddings

Source metadata

Retrieval timestamps

Confidence values

Use pgvector.

---

# Database

Design the best possible relational database.

Expected entities include:

Products

Manufacturers

Categories

Repairs

Repair Components

Failure Statistics

Repair Prices

Labor Prices

Sources

Embeddings

Search History

Users

Cached Results

Confidence Scores

The schema may differ if a better architecture exists.

---

# Cache

Frequently searched products should be cached.

Cache should expire automatically.

Avoid unnecessary external searches.

Reuse verified information whenever possible.

---

# Frontend

Build a modern web application.

Technology:

Next.js

TypeScript

TailwindCSS

shadcn/ui

React Query

Responsive

Dark mode

Accessible

Fast

Streaming responses

Search history

Loading states

Error handling

Professional UI

---

# Backend

FastAPI

Python

SQLAlchemy

Pydantic

REST API

Streaming

Structured logging

Rate limiting

Validation

Authentication-ready architecture

---

# Infrastructure

Docker

Docker Compose

Environment variables

GitHub Actions

Health checks

Monitoring

Structured logging

Production-ready deployment

---

# Security

Validate all input.

Protect against:

Prompt injection

SQL injection

XSS

CSRF

API abuse

Never expose secrets.

Environment variables only.

---

# Performance

Parallelize expensive operations.

Use async.

Cache expensive requests.

Lazy loading.

Optimize database queries.

Avoid duplicated searches.

---

# Testing

Implement:

Unit tests

Integration tests

API tests

Critical business logic tests

---

# Product Quality

The application should feel like a polished commercial SaaS product.

The UI should be intuitive enough that a customer understands the recommendation within five seconds.

Professional animations.

Professional typography.

Consistent design.

High accessibility.

---

# Integration with Alza

Design the architecture so that the application can later be integrated directly into Alza's product pages.

Example:

Samsung TV

799 €

Extended Warranty

65.70 €

AI Recommendation

"The average repair cost after the manufacturer's warranty is approximately €280. The most common failure is LED backlight failure. Purchasing the warranty is recommended."

---

# Engineering Autonomy

If implementation details are missing:

Choose the solution an experienced CTO of a successful SaaS company would choose.

Do not wait for user confirmation.

Do not stop after planning.

Do not stop after generating documentation.

Do not stop after creating architecture.

Continue implementing until the application is fully functional.

---

# Definition of Done

The project is complete only if:

✓ Frontend fully works

✓ Backend fully works

✓ Database fully works

✓ AI orchestration works

✓ Search works

✓ RAG works

✓ Citations work

✓ Confidence scoring works

✓ Docker Compose starts the entire application

✓ GitHub Actions succeed

✓ Tests pass

✓ Error handling is complete

✓ Logging is implemented

✓ Monitoring is implemented

✓ The application is production-ready

If any item above is incomplete, continue implementing automatically.
