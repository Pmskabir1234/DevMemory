# Developer Memory OS
# Architecture Decision Records (ADR)

Version: 1.0
Status: Active
Owner: Engineering
Last Updated: YYYY-MM-DD

---

# Purpose

This document records every significant architectural and technical decision
made during the project.

Every decision should answer:

- What was decided?
- Why was it decided?
- What alternatives were considered?
- What are the consequences?
- Can this decision be revisited?

This prevents repeatedly debating the same problems and helps future contributors understand why the system is designed the way it is.

---

# Decision Status

Possible statuses

- Proposed
- Accepted
- Deprecated
- Superseded

---

# ADR Template

---

## ADR-XXX

Status

Proposed / Accepted / Deprecated

Date

YYYY-MM-DD

Title

Short description

---

### Context

What problem are we solving?

---

### Decision

Chosen solution.

---

### Alternatives Considered

Option 1

Pros

Cons

Option 2

Pros

Cons

---

### Consequences

Positive

Negative

Future impact

---

### Revision

When should this decision be reconsidered?

---

# ============================================================
# Accepted Decisions
# ============================================================

---

# ADR-001

Status

Accepted

Date

YYYY-MM-DD

Title

CLI First Product

---

## Context

The product requires an interface that developers can access from anywhere,
regardless of editor.

Embedding all functionality inside VS Code would tightly couple the product
to a single IDE.

---

## Decision

The CLI is the primary interface.

VS Code acts only as an event collection client.

---

## Alternatives

### IDE-only Application

Pros

Simple

Cons

Locked to VS Code

Cannot support Neovim

Cannot support JetBrains

Limited automation

---

### Web Dashboard Only

Pros

Rich UI

Cons

Interrupts workflow

Requires browser

Not developer friendly

---

## Consequences

Positive

Editor independent

Easy automation

Future support for any editor

Negative

Requires CLI development

---

## Revision

Revisit if more than 70% of users request IDE-first workflows.

---

# ADR-002

Status

Accepted

Title

Local First Storage

---

## Context

Developers may work offline.

Many developers do not want source code uploaded.

---

## Decision

SQLite will be used as the default database.

---

## Alternatives

PostgreSQL

Pros

Scalable

Cons

Requires installation

MongoDB

Pros

Flexible

Cons

Unnecessary complexity

---

## Consequences

Positive

Portable

Zero setup

Fast

Reliable

Negative

Less scalable

---

## Revision

Replace SQLite when cloud synchronization becomes a feature.

---

# ADR-003

Status

Accepted

Title

FastAPI Backend

---

## Context

Backend must expose REST APIs and support future AI services.

---

## Decision

FastAPI

---

## Alternatives

Flask

Pros

Simple

Cons

Less structured

Django

Pros

Powerful

Cons

Heavy for MVP

---

## Consequences

Positive

Async

OpenAPI

Modern

Excellent typing

---

# ADR-004

Status

Accepted

Title

Automatic Session Detection

---

## Context

Developers should never manually create sessions.

---

## Decision

A session automatically ends after inactivity.

Timeout

15 minutes

---

## Alternatives

Manual Start/Stop

Git Commit Boundary

VS Code Shutdown

---

## Reason

Automatic detection creates the least friction.

---

## Consequences

Some long thinking pauses may split sessions.

Acceptable for MVP.

---

# ADR-005

Status

Accepted

Title

Only Capture Metadata

---

## Context

Uploading source code raises privacy concerns.

---

## Decision

Capture

File path

Timestamp

Workspace

Event type

Diagnostics

Summary

Do NOT capture

Entire source files

Secrets

Environment variables

---

## Consequences

Much safer.

Lower storage.

Lower legal risk.

---

# ADR-006

Status

Accepted

Title

AI Summarizes Sessions

---

## Context

Individual events provide little value.

Developers think in sessions.

---

## Decision

Generate one AI summary per session.

Not per event.

---

## Consequences

Lower AI cost.

Higher quality summaries.

Simpler querying.

---

# ADR-007

Status

Accepted

Title

No Vector Database in MVP

---

## Context

Project size is initially small.

Embedding infrastructure increases complexity.

---

## Decision

Search sessions directly from SQLite.

Pass retrieved sessions to LLM.

---

## Alternatives

Qdrant

Pinecone

Weaviate

---

## Consequences

Much simpler architecture.

Can migrate later.

---

# ADR-008

Status

Accepted

Title

Session is the Primary Memory Unit

---

## Context

Developers remember work sessions.

Not raw events.

---

## Decision

Events belong to Sessions.

Queries operate on Sessions.

---

## Consequences

Cleaner APIs.

Cleaner UI.

Smaller prompts.

---

# ADR-009

Status

Accepted

Title

One Backend Service

---

## Context

Microservices add operational overhead.

---

## Decision

Single FastAPI service.

---

## Future

Split only if scaling requires it.

---

# ADR-010

Status

Accepted

Title

Documentation Driven Development

---

## Context

Project should remain maintainable.

---

## Decision

Engineering starts with documentation.

Every feature requires updates to

SPECS.md

TASKS.md

PROGRESS.md

DECISIONS.md

before implementation is considered complete.

---

# Pending Decisions

The following decisions remain open.

---

## PENDING-001

Should terminal commands be captured?

Status

Proposed

---

## PENDING-002

Should Git diffs be summarized?

Status

Proposed

---

## PENDING-003

Should session timeout be configurable?

Status

Proposed

---

## PENDING-004

Should source code snippets be stored?

Status

Proposed

---

## PENDING-005

Should AI run locally or via API?

Status

Proposed

---

# Decision Rules

Before implementing any major feature

1. Read this document.

2. Check whether a decision already exists.

3. If not

Create a new ADR.

4. Never overwrite previous decisions.

5. If architecture changes

Create a new ADR that supersedes the old one.

Never silently modify history.

---

# End of Document