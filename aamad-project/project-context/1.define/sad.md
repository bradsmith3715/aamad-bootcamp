# System Architecture Document (SAD) — Origin AI (MVP)

**Persona:** @system-arch
**Mode:** `*create-sad --mvp` — lean SAD for Phase 1 MVP only. Enhanced and Scale capabilities are listed as Future Work with rationale.
**Source artifacts:** `project-context/1.define/mrd.md`, `project-context/1.define/prd.md`, `project-context/0.idea/idea.md`
**Adapter:** `AAMAD_ADAPTER=crewai` (default; governs runtime semantics per `.claude/rules/adapter-crewai.md`)
**Date:** 2026-04-23
**Phase:** 1.define

---

## Stakeholders & Concerns

- **Solo developer / end user (primary).** Concerns: fast time-to-plan, output quality, ability to edit artifacts, trust in references. Addresses PRD §2, §6, §7.
- **@product-mgr.** Concerns: scope adherence, traceability from discovery answers to generated content. Addresses PRD §4 (F3, F8).
- **@backend-eng.** Concerns: deterministic crew execution, YAML-externalized agent/task configs, bounded token/cost budget, observable agent lifecycle. Addresses adapter-crewai rules.
- **@frontend-eng.** Concerns: stable streaming API contract, clear HITL gate semantics, deterministic artifact-rendering shape. Addresses PRD §6, F7.
- **@integration-eng.** Concerns: reliable frontend↔backend contract, error-propagation shape. Addresses PRD §7.
- **@qa-eng.** Concerns: testable acceptance criteria (F1–F8), reproducibility, prompt-injection validation. Addresses PRD §9 QA checklist.
- **@project-mgr.** Concerns: reproducible environment, minimal dependency surface, clean deploy path.

---

## Viewpoints (ISO/IEC/IEEE 42010)

This SAD presents five views, each answering a distinct stakeholder concern:

- **Logical View** — components, responsibilities, contracts. For backend/frontend engineers.
- **Process / Runtime View** — agent execution flow, task orchestration, HITL gates. For backend/integration engineers.
- **Deployment View** — container topology, hosting target. For project-mgr.
- **Data View** — data elements, lifetime, persistence (or lack thereof). For product-mgr, qa-eng.
- **Interface View** — frontend↔backend API contract + external service contracts. For integration/frontend engineers.

Correspondence rules:
- Every PRD feature (F1–F8) MUST appear in both the Logical and Process views.
- Every agent declared in PRD §3 MUST appear in the Logical View element catalog.
- Every external dependency MUST appear in both the Logical and Deployment views.

---

## 1. MVP Architecture Philosophy & Principles

### MVP Design Principles

- **Ship the golden path, nothing more.** F1–F8 only; auth, persistence, accounts, analytics dashboards are deferred with rationale in §10.
- **Deterministic by default.** Sequential crew process, `memory=False`, `temperature ≤ 0.4`, YAML-externalized agent/task definitions, explicit tool whitelists — all per adapter-crewai rules.
- **Grounded > generative.** F5 GitHub references MUST live-verify; never fabricate. A failed verification drops the result rather than returning a plausible-looking fake.
- **Observable by default (lean).** Structured JSON logs to stdout; no external APM. Every agent run emits a Prompt Trace and Audit record (adapter-crewai).
- **Minimal dependency surface.** Every new dependency must justify its existence against MVP acceptance criteria.

### Core vs. Future Features Decision Framework

- **MVP (Phase 1, this SAD):** F1–F8 from PRD. Single-user, in-memory session, downloadable artifacts. One container each for backend + frontend, deployable locally via Docker or to a hobby-tier container host.
- **Enhanced (Phase 2, deferred):** F9–F12. Introduces persistence (SQLite → Postgres path), auth (NextAuth or equivalent), saved projects, artifact editing UI.
- **Scale (Phase 3, deferred):** F13–F15. Hand-off to agentic builders, collaboration, analytics. Requires materially different infra — explicitly out of scope.

### Technical Architecture Decisions (ADR-style, abbreviated)

Each decision records: context, decision, consequences, trade-offs.

**ADR-1: Python FastAPI backend separate from the frontend, not Next.js API routes.**
- *Context:* CrewAI is Python-native. The template suggests Next.js API routes invoking CrewAI, but that implies a cross-runtime call from Node into Python.
- *Decision:* Single Python FastAPI service owns CrewAI execution and exposes a streaming HTTP API. The Next.js frontend calls this API directly (optionally via a thin Next.js route proxy if CORS forces it).
- *Consequences:* Two deployable artifacts instead of one; cleaner separation of concerns; avoids embedding Python in a Node runtime. Frontend can be a static build if proxy isn't needed.
- *Trade-off:* Deviates from the template's implied single-runtime architecture. Documented as a template-versus-MVP-fit decision.

**ADR-2: Next.js 14 App Router + assistant-ui + Tailwind.**
- *Context:* Template requires this stack; PRD F7 requires a minimal chat UI.
- *Decision:* Adopt App Router (server components where sensible, client components for streaming chat) + assistant-ui + Tailwind + shadcn/ui. TypeScript throughout.
- *Consequences:* Fast path to a production-quality chat UI; assistant-ui handles streaming and tool rendering.
- *Trade-off:* assistant-ui + Next.js is heavier than strictly necessary for MVP. Justified by template conformance and downstream reuse.

**ADR-3: No database in MVP.**
- *Context:* PRD explicitly defers persistence. Adding a DB introduces migration, backup, schema, and deployment complexity not needed for MVP acceptance.
- *Decision:* Session state lives in process memory. Artifacts are produced as markdown, streamed to the frontend, and offered as downloads. No server-side persistence.
- *Consequences:* A page reload loses session state (expected per F7 acceptance). No data retention concerns for MVP.
- *Trade-off:* Users can't resume a session across devices. Deferred to Phase 2.

**ADR-4: No authentication in MVP.**
- *Context:* PRD explicitly defers auth.
- *Decision:* No login, no NextAuth, no user identity. Origin AI is a single-user tool per browser session in MVP.
- *Consequences:* No account takeover surface; no PII. Hosting must put the app behind rate limiting or keep it unlisted to avoid abuse.
- *Trade-off:* Public deployment risks cost abuse — see §5 deploy rationale.

**ADR-5: LLM provider = Anthropic Claude via LiteLLM, with `anthropic/` model-ID prefix.**
- *Context:* CrewAI uses LiteLLM under the hood. Prior-session memory flags that Claude 4.x IDs in CrewAI/LiteLLM require the `anthropic/` prefix or routing breaks.
- *Decision:* Use `anthropic/claude-*` IDs explicitly in agent YAML. Provider selection via env var `LLM_PROVIDER` to keep the swap path open, but MVP ships with Anthropic.
- *Consequences:* Known-good provider path; predictable pricing.
- *Trade-off:* Locked to one provider for MVP; swap requires a config change plus re-verification, not code changes.

**ADR-6: Sequential CrewAI process, not hierarchical.**
- *Context:* PRD §3 declares four agents with deterministic hand-offs. Adapter-crewai rule: prefer sequential unless hierarchical is required.
- *Decision:* `Process.sequential`. Two HITL pauses (post-discovery, post-synthesis) implemented via task boundaries, not delegation.
- *Consequences:* Simpler to reason about, test, and log. Easier to enforce Prompt Trace and Audit.
- *Trade-off:* Loses conditional branching that a manager agent could provide. Not needed for MVP.

**ADR-7: Streaming transport = Server-Sent Events (SSE) over HTTP.**
- *Context:* assistant-ui supports SSE streaming. Simpler than WebSockets; bi-directional communication isn't needed (user sends requests; server streams responses).
- *Decision:* SSE from FastAPI → frontend for agent output. Normal POST for user submissions and HITL approvals.
- *Consequences:* Firewall-friendly, cacheable, simple to test with `curl`.
- *Trade-off:* One-directional per connection; fine for this workflow.

---

## 2. Multi-Agent System Specification

### Agent Architecture Requirements

Four agents from PRD §3. Each enforces adapter-crewai determinism settings: `memory=False`, `allow_delegation=False`, `verbose=False`, `respect_context_window=True`, `max_iter ≤ 12`, `max_retry_limit ≥ 2`, `temperature ≤ 0.4`.

| Agent ID | Role | Tools (whitelisted) | HITL Gate |
|---|---|---|---|
| A1 Discovery | Solo-Developer Project Discovery Interviewer | *(none — conversation only)* | Post-discovery scope approval |
| A2 Synthesizer | Builder-Shaped MRD/PRD Author | `artifact_writer` | Post-synthesis artifact approval |
| A3 Stack Recommender | Pragmatic Tech Stack Recommender | `stack_archetype_lookup` (local static JSON) | none |
| A4 Repo Finder | Grounded GitHub Prior-Art Retriever | `github_search`, `github_repo_verify` | none |

Plus a non-agent deterministic task **T5 Build Plan Assembler** — template-fill from A2/A3/A4 outputs.

Memory: short-term only. Context passes between tasks via `Task.context`, not CrewAI memory (per adapter-crewai rule on determinism).

Tool integration:
- `artifact_writer` — writes markdown artifacts to a per-session output directory (`/tmp/origin-ai/sessions/<session-id>/`). Local filesystem only; no cloud storage in MVP.
- `stack_archetype_lookup` — reads from a curated JSON file in the repo (`backend/data/stack_archetypes.json`). Static for MVP; dynamic corpus is Phase 2.
- `github_search` — GitHub REST API v3 `/search/repositories`. Token-authenticated for rate-limit headroom. Read-only.
- `github_repo_verify` — GitHub REST API `/repos/{owner}/{repo}` GET. Must return 200 for a result to be included (F5 hard acceptance).

### Task Orchestration Specification

```
Task T1 (A1 Discovery)
   ↓   output: structured_scope.json
   ↓   HITL gate: user approval
Task T2 (A2 Synthesizer)
   ↓   output: mrd.md, prd.md  (written via artifact_writer)
   ↓   HITL gate: user approval
Task T3 (A3 Stack Recommender)    ─┐
   output: stack_recommendation.md │   T3 and T4 run sequentially for MVP
Task T4 (A4 Repo Finder)          ─┘   (parallel is a Phase 2 optimization)
   output: references.md
Task T5 (Build Plan Assembler — deterministic)
   output: build_plan.md
```

- Each task declares `expected_output` with a target file path under the session dir and required markdown headings (per adapter-crewai).
- Context passing: explicit via `Task.context`. No reliance on memory or chat history.
- Retry: `max_retry_limit=2` per agent. On final failure, task emits a Halt-and-Report block and the orchestrator propagates a user-visible error.
- Execution budget per task: `max_execution_time` set per agent. Proposed: T1=60s per turn, T2=180s, T3=90s, T4=120s. Tunable in YAML.
- Token budget per session: soft cap 80K tokens, hard cap 120K. Exceeding the soft cap emits a warning in Audit; exceeding the hard cap triggers Halt-and-Report.

### CrewAI Framework Configuration

- Crew `Process.sequential`.
- Config externalized to `backend/config/agents.yaml` and `backend/config/tasks.yaml` per adapter-crewai.
- Variable placeholders (`{user_idea}`, `{approved_scope}`, etc.) bound at runtime. Preflight validates all placeholders are resolved; fails fast on missing bindings.
- Tools bound explicitly at agent construction — no dynamic tool attachment.
- Prompt Trace: before execution, the final system+user prompt is rendered and persisted to `logs/prompt-trace-<session-id>.md`. Artifact Audit references the trace file.
- `step_callback` emits lifecycle events (task start/end, tool call, token count) to `logs/trace-<session-id>.log` — NOT into the artifact, per adapter-crewai rule.

---

## 3. Frontend Architecture Specification (Next.js + assistant-ui)

### Technology Stack

- **Framework:** Next.js 14+ App Router (ADR-2).
- **UI:** assistant-ui for chat, shadcn/ui for structural components.
- **Styling:** Tailwind CSS.
- **Types:** TypeScript end-to-end.
- **State:** Zustand for client-side session state (current session id, HITL gate status, artifact list). Kept minimal — server drives streaming content.

### Application Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                 # Single chat page (MVP)
│   └── api/
│       └── proxy/route.ts       # Optional proxy to FastAPI; omit if CORS solved directly
├── components/
│   ├── chat/                    # assistant-ui wrappers + custom tool renderers
│   ├── artifacts/               # MRD/PRD/stack/refs/build-plan renderers
│   └── hitl/                    # Approval-gate components
├── lib/
│   ├── api.ts                   # FastAPI client (SSE + POST)
│   └── store.ts                 # Zustand store
└── public/
```

- **Server vs. client components:** `layout.tsx` server; the chat surface is a client component (streaming requires it).

### assistant-ui Integration

- **Streaming:** SSE consumer wired to FastAPI `/chat/stream` endpoint. Messages render incrementally.
- **Custom tool renderers:** one per artifact type (MRD card, PRD card, stack card, references card, build-plan card). Each card exposes "Download" and "View traceability" affordances.
- **HITL approval gates:** rendered inline in the chat as an interactive card (`Approve scope` / `Request changes`). User click POSTs to `/session/{id}/approve`.
- **Feedback collection:** single post-session `useful? Y/N` control; stored in session memory only (no persistence in MVP).
- **Theming:** default assistant-ui theme + a minimal Origin AI logo/color accent.

### User Interface Requirements

- Single chat page, left-dominant chat pane + right-side sidebar listing produced artifacts with download links.
- Responsive: works on ≥360px viewports; no mobile-specific features in MVP.
- Accessibility: semantic HTML, keyboard-navigable chat input + artifact list. WCAG AA is a Phase 2 target.
- Loading states: per-message typing indicator while a task runs; per-artifact "generating…" placeholder replaced by the rendered card.
- Error states: a persistent banner with "Restart session" on any unrecoverable error.

---

## 4. Backend Architecture Specification

### API Architecture

- **Runtime:** Python 3.12+, FastAPI, CrewAI, Uvicorn.
- **Endpoints (MVP):**
  - `POST /session` — create new session. Returns `{session_id}`. Idempotency via client-generated UUID optional.
  - `POST /session/{id}/message` — submit user idea or discovery answer. Body: `{role: "user", content: string}`.
  - `GET /session/{id}/stream` — SSE stream of agent output and lifecycle events. Events: `message`, `artifact`, `hitl_request`, `error`, `done`.
  - `POST /session/{id}/approve` — HITL approval. Body: `{gate: "scope" | "artifacts", approved: bool, edits?: string}`.
  - `GET /session/{id}/artifact/{name}` — download a produced artifact (markdown).
  - `GET /healthz` — liveness. `GET /readyz` — readiness (LLM key present, GitHub key present).
- **Streaming:** SSE with `text/event-stream`. `ping` events every 20s to keep proxies from dropping the connection.
- **Validation:** Pydantic models for every request/response body. Reject oversized inputs (user message >2000 chars per F1).
- **Rate limiting:** in-process token-bucket per-session for MVP (e.g. 20 messages per session per minute). No Redis dependency.
- **CORS:** explicit allow-list of frontend origin via env var `CORS_ORIGIN`.
- **Error shape:** `{error: {code, message, retriable: bool, trace_id}}`. Never leak stack traces to clients.

### Database Architecture

**MVP: no database.** Session state lives in a `dict[session_id, SessionState]` in process memory. Artifacts written to `/tmp/origin-ai/sessions/<session-id>/` on disk (ephemeral; cleared on container restart).

Future-proof schema sketch (Phase 2, informational — do not implement now):
- `User(id, email, created_at)`
- `Session(id, user_id, created_at, idea_text)`
- `Artifact(id, session_id, type, content, created_at)`
- Chosen DB (Phase 2): SQLite for development, Postgres for production.

### CrewAI Integration Layer

- A single `CrewRunner` class wraps crew kickoff and exposes an async iterator that yields SSE events.
- Agent configs loaded from `backend/config/agents.yaml`; tasks from `backend/config/tasks.yaml`. Preflight validates all placeholders + all whitelisted tools resolve.
- Custom tools live under `backend/tools/` and are imported and bound explicitly in `CrewRunner.__init__` — no dynamic registration.
- `step_callback` emits structured events that the SSE handler forwards to the client (filtered — internal chain-of-thought is NOT forwarded to the client; only tool-call summaries and artifact announcements are).

### Authentication & Security Specifications

- **No user auth in MVP (ADR-4).**
- **API key management:** LLM provider key (`ANTHROPIC_API_KEY`) and GitHub token (`GITHUB_TOKEN`) loaded from env vars; `.env.example` enumerates all required vars (adapter-crewai rule).
- **Input sanitization:** prompt-injection mitigation on user input before embedding in agent prompts — strip/escape known injection tokens, limit length, reject binary content. Per adapter-crewai: "sanitize quoted inputs to neutralize prompt-injection tokens."
- **Rate limiting:** per-session token-bucket (above). Per-IP rate limit deferred until a public deploy is chosen.
- **CORS:** single allowed origin via env var.
- **No PII** logged. User idea text is treated as sensitive and is NOT written to persistent logs — only to session-scoped files that live alongside the ephemeral session dir.

---

## 5. DevOps & Deployment Architecture

### CI/CD Pipeline

**MVP (lean):**
- GitHub Actions workflow: lint (ruff, mypy for backend; eslint, tsc for frontend) + unit tests + build Docker images on every push to `master`.
- No automated deploy in MVP. Deploy is a manual `docker compose up` against the chosen host, so a failed build cannot accidentally ship.
- Deferred: blue-green, rollback automation, E2E smoke gates — Phase 2.

### Deployment Configuration

**Target (chosen for MVP):** local `docker compose` or a single hobby-tier container host (Render, Fly.io, or Railway). AWS App Runner is not selected for MVP because it adds IAM/VPC/IaC surface not justified by MVP acceptance.

Two containers in MVP:
- `origin-backend` — FastAPI + CrewAI. Exposes `:8000`.
- `origin-frontend` — Next.js standalone build. Exposes `:3000`.

Compose file ships in-repo. Single `.env` drives both services.

Health checks:
- Backend: `GET /healthz` (200 if process alive), `GET /readyz` (200 if `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` are present and validated by a cached probe call).
- Frontend: default Next.js health.

**Deferred to Phase 2:** IaC (Terraform/CloudFormation), multi-environment pipelines, auto-scaling policies, blue-green, disaster recovery.

### Monitoring & Observability

**MVP:**
- Structured JSON logs to stdout from both services. Include `session_id`, `task_id`, `event`, `duration_ms`, `token_count` where applicable.
- Trace logs per session under `logs/` (see §2).
- Audit block on every produced artifact (adapter-crewai).
- No external log aggregator, APM, or dashboard in MVP. Container host's log viewer is sufficient.

**Deferred:** OpenTelemetry, Grafana, alert routing, user-behavior analytics.

---

## 6. Data Flow & Integration Architecture

### Request/Response Flow (happy path)

1. User opens the frontend. Client generates a `session_id` (UUID) and calls `POST /session`.
2. User types an idea. Client POSTs to `/session/{id}/message`; opens SSE on `/session/{id}/stream`.
3. Backend kicks off the crew. T1 (A1 Discovery) runs; streams questions to client over SSE. Client POSTs each answer back via `/session/{id}/message`.
4. After N questions, T1 emits a `hitl_request(gate=scope)` event with the structured scope. Client renders approval card. User approves → POST to `/session/{id}/approve`.
5. T2 runs. Produces `mrd.md` and `prd.md`. Streams `artifact` events. Emits `hitl_request(gate=artifacts)`. User approves.
6. T3 + T4 run (sequential for MVP). Each produces an artifact. Streams `artifact` events.
7. T5 assembles `build_plan.md`. Streams the final artifact. Emits `done`.
8. Client allows download of each artifact via `GET /session/{id}/artifact/{name}`.

### External Integration Requirements

| Service | Purpose | Failure mode | Mitigation |
|---|---|---|---|
| Anthropic API (via LiteLLM) | LLM calls for A1/A2/A3/A4 | 5xx, rate limit, timeout | Retry with backoff (`max_retry_limit=2`); on final failure, Halt-and-Report + user-visible error |
| GitHub REST API | `github_search`, `github_repo_verify` (F5) | 4xx auth, 403 rate limit, 5xx | Token-authenticated requests; degrade to fewer refs with user-visible "couldn't find strong references" (F5 acceptance) |

No webhooks, no data sync, no third-party fallbacks in MVP.

### Analytics & Feedback Architecture

**MVP:**
- End-of-session 1-question survey ("Could you start building from this plan?" Y/N). Stored in-memory; emitted to stdout on session close. No persistence, no dashboard in MVP.
- Per-session telemetry in stdout logs: token count, wall time, agent failure flag. Operator reads logs to compute PRD §7 KPIs by hand during the initial 20-session validation cohort.

**Deferred:** event pipeline, analytics DB, dashboards.

---

## 7. Performance & Scalability Specifications

### Performance Requirements

- **Time-to-plan (end-to-end):** <15 min median (PRD §7).
- **First-token latency per agent turn:** <3 s (PRD §5 soft target).
- **Per-session LLM cost:** <$0.50 median (PRD §5).
- **Concurrent users (MVP):** 1 — single-user-at-a-time assumption. Concurrent sessions will work (Python async), but are not a requirement.

### Scalability Architecture

**Out of scope for MVP.** Declared in Future Work:
- Horizontal scaling triggers, load balancing, DB scaling — Phase 2+.
- Parallel execution of T3/T4 — Phase 2 performance optimization.

### Resource Optimization

- **Token usage optimization:** per-agent `max_tokens` caps in YAML; Task-level expected_output prevents run-on generation.
- **Memory:** per-session state is small (< a few MB including artifacts). Bounded by process memory.
- **CPU/bandwidth:** negligible at MVP scale.

---

## 8. Security & Compliance Architecture

### Security Framework

- **Authn/Authz:** none in MVP (ADR-4). If deployed publicly, operator MUST place the app behind a shared secret or network-level restriction to prevent cost abuse.
- **Encryption in transit:** HTTPS at the host edge (Render/Fly/Railway all terminate TLS). Backend-frontend over loopback or host-internal network.
- **Encryption at rest:** N/A — no persistence in MVP beyond ephemeral session files.
- **API security:** input validation via Pydantic; prompt-injection sanitization on user message content.
- **Vulnerability management:** `pip-audit` / `npm audit` in CI.

### Data Privacy & Compliance

- **User data handling:** user idea text is treated as sensitive — not logged to stdout, not persisted beyond session lifetime.
- **GDPR / SOC2:** out of scope for MVP (no user accounts, no persistent storage). If/when Phase 2 introduces auth + persistence, a GDPR-lite review is a prerequisite.
- **Audit logging:** every crew run appends an Audit block per artifact (adapter-crewai).
- **Consent:** N/A — no data collection beyond the active session.

---

## 9. Testing & Quality Assurance Specifications

### Testing Strategy

- **Unit tests (backend):** pydantic models, tool wrappers (mocked HTTP), prompt-injection sanitizer, build-plan assembler. Target coverage: meaningful coverage on non-LLM code paths.
- **Unit tests (frontend):** component rendering of artifact cards + HITL gates. SSE hook with a mocked stream.
- **Integration tests:**
  - Crew kickoff with a mocked LLM (LiteLLM `mock_response`) exercising the T1→T5 chain end-to-end.
  - GitHub tool integration test against the real API using a dedicated test token; runs nightly, not per-commit.
- **End-to-end tests:** Playwright test covering the golden path (idea → approve scope → approve artifacts → download build plan). Runs against a mocked-LLM backend to stay deterministic.
- **Performance testing:** deferred.
- **Security testing:**
  - Prompt-injection corpus (owner: @qa-eng per PRD Open Questions) — canned adversarial messages that MUST NOT escape the sanitizer.
  - `pip-audit` / `npm audit` in CI.

### Quality Gates

- **CI:** lint + typecheck + unit tests MUST pass on every push.
- **Per-artifact:** expected_output headings MUST match template; absence produces a Diagnostic and aborts before write (adapter-crewai).
- **Per-crew-run:** Prompt Trace generated; Audit appended; token count within hard cap.
- **F5 hard gate:** every returned GitHub repo MUST return 200 on verify — automated test asserts this against a fixture + smoke test.

---

## 10. MVP Launch & Feedback Strategy

### Beta Testing Framework

- **Cohort:** 10–20 solo developers (personal network + Indie Hackers).
- **Feedback capture:** end-of-session Y/N survey + structured post-session notes form (offline, no integration in MVP). Three 15-min qualitative interviews after the first 10 sessions.
- **Feature flags:** out of scope for MVP — all F1–F8 ship on. Phase 2 re-evaluates.
- **Success metrics:** PRD §7 — task completion ≥60%, time-to-plan <15 min median, usefulness Y ≥70%.

### User Experience Optimization

- **Onboarding:** minimal placeholder text in the chat input ("Paste your project idea here…") is the only onboarding in MVP.
- **Help / docs:** README in-repo; a one-page about section linked from the frontend is acceptable but not required.
- **Feedback loop:** issues go to a GitHub issue tracker on the project repo. No in-app feedback widget in MVP.

### Business Metrics & Analytics

**Deferred.** MVP is a bootcamp PoC — no revenue, acquisition, or funnel tracking. Operator reads stdout logs to compute KPIs by hand for the validation cohort.

---

## Views

### Logical View — Component Catalog

| Component | Type | Responsibility | PRD Trace |
|---|---|---|---|
| `frontend` (Next.js + assistant-ui) | Client | Chat UI, artifact rendering, HITL gates, artifact download | F7, F8 |
| `backend.api` (FastAPI) | Service | HTTP/SSE endpoints, input validation, session state | F1, F7 |
| `backend.crew_runner` | Module | CrewAI orchestration, Prompt Trace, Audit | §2, F8 |
| `backend.agents.a1_discovery` | Agent | Conversational discovery | F2 |
| `backend.agents.a2_synthesizer` | Agent | MRD/PRD generation | F3 |
| `backend.agents.a3_stack_rec` | Agent | Stack recommendation | F4 |
| `backend.agents.a4_repo_finder` | Agent | Grounded GitHub repo retrieval | F5 |
| `backend.tasks.t5_plan_assembler` | Task (deterministic) | Build-plan consolidation | F6 |
| `backend.tools.artifact_writer` | Tool | Markdown artifact writes | F3, F6 |
| `backend.tools.stack_archetype_lookup` | Tool | Static JSON lookup | F4 |
| `backend.tools.github_search` | Tool | GitHub search API wrapper | F5 |
| `backend.tools.github_repo_verify` | Tool | GitHub repo existence check | F5 hard gate |
| `backend.sanitizer` | Module | Prompt-injection input cleaning | §4 security |
| `backend.config/agents.yaml`, `tasks.yaml` | Config | Externalized CrewAI config | adapter-crewai |

### Process / Runtime View — see §2 orchestration diagram

- HITL gates pause the crew between T1→T2 and T2→T3. The backend holds session state until the user approves via `POST /session/{id}/approve`.
- On any agent Halt-and-Report, the SSE stream emits `error` and the session is marked failed; the user can start a new session.

### Deployment View

```
[ Browser ]
    │ HTTPS
    ▼
[ origin-frontend (Next.js :3000) ]
    │ SSE + POST
    ▼
[ origin-backend (FastAPI + CrewAI :8000) ]
    │                           │
    │                           ├──→ Anthropic API (LLM)
    │                           └──→ GitHub REST API
    ▼
/tmp/origin-ai/sessions/<id>/ (ephemeral artifact dir)
```

Single host in MVP. Two containers; one compose file.

### Data View

- **Session state (in-memory):** `session_id`, `created_at`, `messages[]`, `structured_scope`, `hitl_approvals{}`, `artifacts[]`, `token_count`, `cost_estimate`.
- **Artifacts (filesystem):** markdown files under `/tmp/origin-ai/sessions/<id>/`. Cleared on container restart.
- **Trace logs (filesystem):** `logs/prompt-trace-<id>.md`, `logs/trace-<id>.log`. Retention: until container restart in MVP. No PII scrubbing required because only agent-side prompts/outputs are logged, and user idea text is embedded in prompts (accepted risk — not deployed publicly without operator gating per ADR-4).
- **No persistent storage in MVP.**

### Interface View — API contract headline

Enumerated in §4 endpoints. SSE event types: `message`, `artifact`, `hitl_request`, `error`, `done`. Detailed request/response schemas are an SFS-level concern, not SAD.

---

## Quality Attributes (ISO/IEC/IEEE 42010)

- **Determinism:** sequential process + `temperature ≤ 0.4` + `memory=False` + YAML-externalized config. Primary.
- **Auditability:** Prompt Trace + Audit block per run. Primary.
- **Reliability:** retry with backoff, HITL gates for quality control. Secondary.
- **Performance:** <15 min time-to-plan, <$0.50 per session. Secondary (MVP targets, not strict SLOs).
- **Security:** input sanitization, env-only secrets, no auth in MVP. Secondary.
- **Scalability:** out of scope for MVP.

---

## Architectural Decisions (consolidated)

- **ADR-1** FastAPI backend, Next.js frontend, two deployables.
- **ADR-2** Next.js 14 App Router + assistant-ui + Tailwind.
- **ADR-3** No database in MVP.
- **ADR-4** No auth in MVP.
- **ADR-5** Anthropic Claude via LiteLLM with `anthropic/` prefix.
- **ADR-6** Sequential CrewAI process.
- **ADR-7** SSE transport for streaming.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Hallucinated GitHub repos (PRD high risk) | High | F5 hard gate: `github_repo_verify` MUST 200; drop unverified results |
| Low artifact quality | High | expected_output schemas, Task.guardrail, HITL gates, `temperature ≤ 0.4` |
| Cost drift on long conversations | Medium | Per-session token caps (soft 80K / hard 120K); session timeouts |
| Anthropic outage / rate limit | Medium | Retry w/ backoff; user-visible error; no automatic failover in MVP |
| GitHub API rate limit | Medium | Token-authenticated requests; degrade-to-fewer-refs fallback |
| Public deploy abuse (no auth) | Medium | MVP deploy behind shared secret or unlisted; operator guidance in README |
| Prompt injection via user idea text | Medium | Sanitizer module; prompt-injection QA corpus (PRD OQ) |
| Filename/case convention drift across define artifacts | Low | Resolved 2026-04-23: standardized on lowercase (`mrd.md`, `prd.md`, `sad.md`) to match persona specs. |

---

## Future Work (explicitly deferred)

- **F9 Artifact editing UI** — Phase 2. Requires a richer rendering layer and regeneration plumbing.
- **F10 Auth + saved projects** — Phase 2. Introduces DB, NextAuth/equivalent, migrations, privacy review.
- **F11 Expanded stack archetypes** — Phase 2. Possibly a RAG corpus or community-maintained list.
- **F12 Alternate discovery modes** — Phase 2. Multiple T1 agents with templated question sets.
- **F13 Hand-off to agentic builders** — Phase 3.
- **F14 Collaboration** — Phase 3.
- **F15 Analytics** — Phase 3.
- **Parallel T3/T4** — Phase 2 performance optimization.
- **IaC (Terraform/CloudFormation)** — Phase 2.
- **APM, Grafana, OpenTelemetry** — Phase 2.
- **GDPR / SOC2 compliance** — gated by Phase 2 persistence introduction.
- **PostgreSQL / Prisma** — Phase 2 with F10.
- **NextAuth integration** — Phase 2 with F10.

---

## Traceability Matrix (PRD → SAD)

| PRD Feature | SAD Location | SFS target (to be authored) |
|---|---|---|
| F1 Idea Intake | §4 endpoints, §4 security (sanitizer) | sfs/f1-idea-intake.md |
| F2 Conversational Discovery | §2 A1, §6 flow step 2–4 | sfs/f2-discovery.md |
| F3 MRD + PRD Generation | §2 A2, §4 artifact_writer | sfs/f3-mrd-prd-gen.md |
| F4 Stack Recommendation | §2 A3, stack_archetype_lookup | sfs/f4-stack-rec.md |
| F5 Grounded GitHub Refs | §2 A4, github_* tools, Risks | sfs/f5-repo-finder.md |
| F6 Build Plan Output | §2 T5, §6 flow step 7 | sfs/f6-build-plan.md |
| F7 Minimal Chat UI | §3 whole section | sfs/f7-chat-ui.md |
| F8 Traceability & Audit | §2 Prompt Trace, §Views Data View | sfs/f8-audit.md |

Per-feature SFS files are the next deliverable from @system-arch via `*create-sfs`.

---

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/mrd.md`
- `project-context/0.idea/idea.md`
- `.cursor/templates/sad-template.md`
- `.claude/rules/aamad-core.md`
- `.claude/rules/adapter-crewai.md`
- `.claude/rules/adapter-registry.md`
- `.claude/agents/system-arch.md`
- Adapter: `AAMAD_ADAPTER=crewai` (default per adapter-registry)

---

## Assumptions

- Anthropic Claude via LiteLLM is the MVP LLM; `anthropic/` prefix is required on Claude 4.x model IDs (prior-session memory).
- Next.js 14 App Router + assistant-ui + Tailwind is the frontend stack, per template; PRD did not contest it.
- Session state in process memory is acceptable for MVP (page reload loses state — consistent with PRD F7 acceptance).
- GitHub public REST API with a bot token provides sufficient headroom for F5 at MVP volumes (~100 lookups/day).
- Two-container Docker deploy to a hobby-tier host is acceptable; AWS App Runner and IaC are Phase 2.
- The operator will deploy MVP behind a shared secret or keep it unlisted — no auth in MVP means public deploy is an operator decision with cost-abuse risk.
- Per-session soft cap of 80K tokens is sufficient for a full T1→T5 run (to be instrumented; may need adjustment after initial sessions).
- assistant-ui's SSE consumer + custom tool-renderer extension points are expressive enough for MVP artifact display without material forking.

---

## Open Questions

- **Model selection per agent.** Does A1 (conversation) warrant a cheaper/faster model than A2–A4 (artifact generation)? Owner: @backend-eng before crew wiring.
- **Stack archetype JSON shape.** Schema for `stack_archetypes.json` — fields, cardinality, example entries. Owner: @product-mgr + @backend-eng.
- **GitHub query strategy.** What search query does A4 construct from the approved scope? Keyword extraction, language filter, min-star threshold? Owner: @backend-eng.
- **HITL timeout.** If a user walks away after the scope gate, how long does the session sit in memory? Proposed: 60 minutes idle → expire. Owner: @backend-eng.
- **Streaming proxy.** Does the frontend call FastAPI directly (CORS) or via a Next.js proxy route? Decide when hosting target is chosen. Owner: @integration-eng.
- **Logs location in production.** `logs/` under the container's writable volume vs. stdout only. Current plan: both — trace files on disk, lifecycle events on stdout. Confirm with operator deployment constraints. Owner: @project-mgr.
- **Prompt-injection corpus.** PRD deferred corpus authoring to @qa-eng — SAD needs the corpus in hand before §9 security testing can complete. Owner: @qa-eng.

---

## Audit

- **Timestamp:** 2026-04-23
- **Persona:** @system-arch
- **Command:** `*create-sad --mvp`
- **Adapter:** `AAMAD_ADAPTER=crewai` (default; not overridden)
- **Inputs read:** `project-context/1.define/prd.md`, `project-context/1.define/mrd.md`, `project-context/0.idea/idea.md`, `.cursor/templates/sad-template.md`, `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/adapter-registry.md`, `.claude/agents/system-arch.md`.
- **Output:** `project-context/1.define/sad.md` (this file).
- **Model / tooling:** authored via Claude Code main thread (model: claude-opus-4-7[1m]). Single-pass authoring, not a crew run.
- **Temperature / determinism:** N/A for authoring pass; downstream crew runs MUST honor `temperature ≤ 0.4`, `memory=False`, `allow_delegation=False` per adapter-crewai.
- **Template headings:** all 10 template sections present; plus Stakeholders, Viewpoints, Views, Quality Attributes, ADRs, Risks, Future Work, Traceability Matrix, Sources, Assumptions, Open Questions, Audit per AAMAD and ISO/IEC/IEEE 42010.
- **No code fences around raw template content.** Confirmed.
- **Prohibited actions attempted:** none.
- **Scope boundary:** architecture decisions only; per-feature SFS authoring is the next step via `*create-sfs`.
- **Handoff:**
  - @system-arch to produce SFS files (`project-context/1.define/sfs/f*.md`) next.
  - @project-mgr can begin environment scaffolding (Python + Node workspaces, Docker compose skeleton) in parallel, blocked only on the filename-convention Open Question.
