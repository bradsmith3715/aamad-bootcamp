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

- **MVP (Phase 1, this SAD):** F1–F8 from PRD. Single-user, in-memory session, downloadable artifacts. **One container** (single Python service: FastHTML + HTMX + CrewAI), deployable locally via Docker or to a hobby-tier container host.
- **Enhanced (Phase 2, deferred):** F9–F12. Introduces persistence (SQLite → Postgres path), auth (e.g. Starlette session middleware + a lightweight auth provider), saved projects, artifact editing UI.
- **Scale (Phase 3, deferred):** F13–F15. Hand-off to agentic builders, collaboration, analytics. Requires materially different infra — explicitly out of scope.

### Technical Architecture Decisions (ADR-style, abbreviated)

Each decision records: context, decision, consequences, trade-offs.

**ADR-1: Single Python service using FastHTML + HTMX + CrewAI.** *(revised r2 — supersedes the r1 two-service FastAPI + Next.js decision.)*
- *Context:* User decision 2026-04-23 consolidates the runtime. CrewAI is Python-native; FastHTML (Starlette-based Python framework) owns both HTTP endpoints and server-rendered HTML. A second JavaScript runtime is not justified for MVP scope.
- *Decision:* One Python process runs FastHTML + HTMX + CrewAI. No separate frontend container, no Node runtime, no cross-runtime RPC. FastHTML route handlers return either HTML fragments (for HTMX partial swaps) or full pages (initial load only).
- *Consequences:* One container, one dependency set, one deploy pipeline. No CORS, no proxy, no JSON-to-HTML translation layer. The full request flow stays in one language and one process.
- *Trade-off:* Departs from the template's implied Next.js architecture. Justified by user decision and MVP-simplicity. Frontend ceiling is HTMX's partial-swap model; if Origin AI later requires rich SPA patterns, a migration would be needed.

**ADR-2: UI is FastHTML-rendered HTML + HTMX; no Next.js, no assistant-ui, no React.** *(revised r2 — supersedes the r1 Next.js/assistant-ui/Tailwind decision.)*
- *Context:* ADR-1 consolidated the runtime to Python. The UI layer needs to be renderable from Python.
- *Decision:* FastHTML's `ft` (fasttag) style generates HTML from Python functions. HTMX attributes (`hx-post`, `hx-get`, `hx-swap`, `hx-ext="sse"`) drive client-side interactivity via partial-page swaps. Minimal CSS: PicoCSS (class-less, small, CDN-hostable) is the default choice; vanilla CSS is acceptable. Tailwind is NOT used. No TypeScript, no JS bundler, no component framework. Custom "tool renderers" from the prior design become Python functions returning HTML fragments.
- *Consequences:* The full UI is a set of Python functions. Zero frontend build step. Accessibility baseline is easier to hold than with a JS-heavy SPA (semantic HTML by default). No client-side state framework needed — server is the source of truth.
- *Trade-off:* No client-side routing, no offline, no rich component ecosystem. For a single-page two-gate chat flow, none of these are MVP requirements.

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

**ADR-5: LLM provider = Claude API (Anthropic) via CrewAI's LiteLLM layer, with `anthropic/` model-ID prefix.** *(reconfirmed r2 — user decision 2026-04-23 matches r1 reasoning.)*
- *Context:* User explicitly confirmed "Claude API" as the MVP provider. CrewAI uses LiteLLM internally; Claude 4.x IDs in CrewAI/LiteLLM require the `anthropic/` prefix or routing breaks.
- *Decision:* Use `anthropic/claude-*` IDs in agent YAML. No direct `anthropic` SDK integration, no custom CrewAI LLM wrapper. Env var `ANTHROPIC_API_KEY` required. Per-agent model IDs (e.g. a cheaper/faster model for A1 Discovery vs. a frontier model for A2 Synthesizer) TBD by @backend-eng — still open.
- *Consequences:* Known-good provider path; predictable pricing; CrewAI's native logging and retry semantics apply.
- *Trade-off:* Locked to Anthropic for MVP; provider swap would require LiteLLM config changes (not a code rewrite) plus re-verification.

**ADR-6: Sequential CrewAI process; A5 Orchestrator runs as T0 and T5 bookend tasks (NOT hierarchical manager mode).** *(revised r2 — now accounts for the 5-agent decomposition from PRD r2.)*
- *Context:* PRD r2 §3 declares five agents including a dedicated A5 Orchestrator. MRD r2 raised an open question: does the orchestrator use CrewAI hierarchical/manager mode (`allow_delegation=True` on A5) or run as a coordinator inside a still-sequential process? Adapter-crewai rule strongly prefers sequential for determinism.
- *Decision:* Stay with `Process.sequential`. The A5 Orchestrator runs as **T0** (session initialization: structure the user's raw idea, seed per-session context, compute `session_id` + output dir) and **T5** (build-plan consolidation from T1–T4 outputs, final Prompt-Trace capture, Audit block emission). Task sequencing is owned by the sequential process; HITL gate pauses between T1→T2 and T2→T3/T4 are owned by the HTTP layer, which halts crew invocation, waits for user approval via HTMX POST, and resumes by kicking off the next task batch. `allow_delegation=False` for every agent including A5.
- *Consequences:* Fully deterministic task dispatch — no LLM-driven routing variance. The orchestrator owns "orchestration" semantically (a named agent role responsible for session state and audit) rather than through CrewAI's hierarchical manager mechanics. Easier to reason about, test, log, and reproduce. Matches adapter-crewai's determinism bias.
- *Trade-off:* A5 cannot adaptively skip, retry, or reorder tasks based on inspection of outputs. Retries remain `max_retry_limit=2` at the CrewAI task level; adaptive workflow control is deferred.

**ADR-7: Streaming transport = SSE, consumed by HTMX's `sse` extension (`hx-ext="sse"`).** *(revised r2 — transport unchanged; consumer is now HTMX instead of assistant-ui.)*
- *Context:* ADR-1 / ADR-2 eliminated the React consumer. The streaming shape (one-directional, agent output → client, plain text/event-stream) still matches SSE well, and HTMX has a first-class SSE extension.
- *Decision:* FastHTML streams SSE from `GET /session/{id}/stream` using Starlette's native streaming response. Each SSE `data:` body is an **HTML fragment** (not JSON). The client page loads HTMX's SSE extension, declares `hx-ext="sse" sse-connect="/session/{id}/stream"`, and uses `sse-swap="message"` / `sse-swap="artifact"` / `sse-swap="hitl_request"` to target each event type into the correct DOM region. Event types: `message`, `artifact`, `hitl_request`, `error`, `done`. Non-streaming endpoints (POST user message, POST HITL approval) use plain `hx-post` returning HTML fragments.
- *Consequences:* No bespoke JS consumer. The browser's native SSE handling + HTMX's extension do all the work. Easy to test with `curl`. Reconnection, heartbeats, and disconnect-detection come from the HTMX SSE extension's defaults.
- *Trade-off:* HTMX's SSE extension is an optional extension file (hosted self or CDN); it must be loaded alongside core HTMX. Well-maintained but an additional moving part.

---

## 2. Multi-Agent System Specification

### Agent Architecture Requirements

Five agents from PRD r2 §3. Each enforces adapter-crewai determinism settings: `memory=False`, `allow_delegation=False`, `verbose=False`, `respect_context_window=True`, `max_iter ≤ 12`, `max_retry_limit ≥ 2`, `temperature ≤ 0.4`.

| Agent ID | Role | Tools (whitelisted) | HITL Gate | Runs as |
|---|---|---|---|---|
| A5 Orchestrator (T0) | Session Orchestrator for Origin AI Crew | `artifact_writer`, Audit/Prompt-Trace hooks | none | T0 (session init) |
| A1 Discovery | Solo-Developer Project Discovery Interviewer | *(none — conversation only)* | Post-discovery scope approval | T1 |
| A2 Synthesizer | Builder-Shaped MRD/PRD Author | `artifact_writer` | Post-synthesis artifact approval | T2 |
| A3 Stack Recommender | Pragmatic Tech Stack Recommender | `stack_archetype_lookup` (local static JSON) | none | T3 |
| A4 Repo Finder | Grounded GitHub Prior-Art Retriever | `github_search`, `github_repo_verify` | none | T4 |
| A5 Orchestrator (T5) | Session Orchestrator for Origin AI Crew (second turn) | `artifact_writer`, Audit/Prompt-Trace hooks | none | T5 (consolidation) |

Per ADR-6, A5 runs as both T0 and T5 — initializing the session up front and consolidating outputs at the end. No hierarchical manager mode; `allow_delegation=False` on every agent.

Memory: short-term only. Context passes between tasks via `Task.context`, not CrewAI memory (per adapter-crewai rule on determinism).

Tool integration:
- `artifact_writer` — writes markdown artifacts to a per-session output directory (`/tmp/origin-ai/sessions/<session-id>/`). Local filesystem only; no cloud storage in MVP.
- `stack_archetype_lookup` — reads from a curated JSON file in the repo (`backend/data/stack_archetypes.json`). Static for MVP; dynamic corpus is Phase 2.
- `github_search` — GitHub REST API v3 `/search/repositories`. Token-authenticated for rate-limit headroom. Read-only.
- `github_repo_verify` — GitHub REST API `/repos/{owner}/{repo}` GET. Must return 200 for a result to be included (F5 hard acceptance).

### Task Orchestration Specification

```
Task T0 (A5 Orchestrator — session init)
   ↓   output: session_context.json (session_id, normalized_idea, output_dir)
Task T1 (A1 Discovery)
   ↓   output: structured_scope.json
   ↓   HITL gate: user approval (held by HTTP layer)
Task T2 (A2 Synthesizer)
   ↓   output: mrd.md, prd.md  (written via artifact_writer)
   ↓   HITL gate: user approval (held by HTTP layer)
Task T3 (A3 Stack Recommender)    ─┐
   output: stack_recommendation.md │   T3 and T4 run sequentially for MVP
Task T4 (A4 Repo Finder)          ─┘   (parallel is a Phase 2 optimization)
   output: references.md
Task T5 (A5 Orchestrator — consolidation)
   output: build_plan.md + appended Audit on every artifact from T1–T4
```

- Each task declares `expected_output` with a target file path under the session dir and required markdown headings (per adapter-crewai).
- Context passing: explicit via `Task.context`. No reliance on memory or chat history.
- Retry: `max_retry_limit=2` per agent. On final failure, A5 (T5) emits a Halt-and-Report block and the HTTP layer propagates a user-visible error event over SSE.
- Execution budget per task: `max_execution_time` set per agent. Proposed: T0=10s, T1=60s per turn, T2=180s, T3=90s, T4=120s, T5=60s. Tunable in YAML.
- Token budget per session: soft cap 80K tokens, hard cap 120K. Exceeding the soft cap emits a warning in Audit; exceeding the hard cap triggers Halt-and-Report in T5.
- **HITL gate mechanics (ADR-6 consequence):** the crew does NOT run as one `kickoff()` call. The HTTP layer drives three kickoffs: (a) T0+T1 up to the scope gate; (b) T2 up to the artifact gate; (c) T3+T4+T5. Between kickoffs, session state sits in memory awaiting an HTMX `hx-post` to `/session/{id}/approve`.

### CrewAI Framework Configuration

- Crew `Process.sequential`.
- Config externalized to `backend/config/agents.yaml` and `backend/config/tasks.yaml` per adapter-crewai.
- Variable placeholders (`{user_idea}`, `{approved_scope}`, etc.) bound at runtime. Preflight validates all placeholders are resolved; fails fast on missing bindings.
- Tools bound explicitly at agent construction — no dynamic tool attachment.
- Prompt Trace: before execution, the final system+user prompt is rendered and persisted to `logs/prompt-trace-<session-id>.md`. Artifact Audit references the trace file.
- `step_callback` emits lifecycle events (task start/end, tool call, token count) to `logs/trace-<session-id>.log` — NOT into the artifact, per adapter-crewai rule.

---

## 3. Frontend Architecture Specification (FastHTML + HTMX)

### Technology Stack (ADR-1, ADR-2)

- **Framework:** FastHTML (Starlette-based Python framework). Renders HTML from Python using the `ft` fasttag style.
- **Interactivity:** HTMX (loaded as a single `<script>` from CDN or self-hosted) + HTMX's `sse` extension for streaming.
- **Styling:** PicoCSS (default; class-less, minimal CSS footprint, CDN-hostable). Vanilla CSS is acceptable. Tailwind is NOT used.
- **Types:** Python type hints on route handlers and HTML-producing functions. No TypeScript.
- **State:** none on the client. Server is the source of truth; every interaction results in a partial HTML swap that reflects current server state.

### Application Structure

```
app/
├── main.py                     # FastHTML app instance, route registration
├── routes/
│   ├── pages.py                # Full-page handlers (initial load)
│   ├── messages.py             # POST /session/{id}/message, POST /session/{id}/approve
│   ├── stream.py               # GET /session/{id}/stream (SSE)
│   ├── artifacts.py            # GET /session/{id}/artifact/{name}
│   └── health.py               # /healthz, /readyz
├── views/
│   ├── layout.py               # Base page + <head> tags + HTMX script includes
│   ├── chat.py                 # Chat pane fragment
│   ├── artifacts.py            # Artifact card fragments (mrd, prd, stack, refs, build_plan)
│   ├── hitl.py                 # Approval-gate fragment
│   └── errors.py               # Error-banner fragment
├── static/                     # PicoCSS, HTMX core + sse extension (self-hosted OK)
└── (crew/, tools/, sanitizer/, config/ — see §4 Backend)
```

- All UI is server-rendered HTML. No client-side build step. No JS files other than HTMX core + HTMX sse extension.
- Route handlers return either full pages (initial load) or HTML fragments (HTMX `hx-swap` targets, SSE event bodies).

### HTMX Interaction Patterns

- **Streaming agent output:** the chat region declares `hx-ext="sse" sse-connect="/session/{id}/stream"`. Per-event `sse-swap` attributes target different DOM regions:
  - `sse-swap="message"` → appended to the chat transcript.
  - `sse-swap="artifact"` → swapped into the artifact sidebar.
  - `sse-swap="hitl_request"` → swapped into the HITL gate region at the bottom of the chat.
  - `sse-swap="error"` → swapped into the persistent error banner.
  - `sse-swap="done"` → triggers a final status update.
- **User message submission:** `<form hx-post="/session/{id}/message" hx-swap="beforeend" hx-target="#chat">`. Submit returns a user-bubble HTML fragment; the server asynchronously processes the message and streams subsequent agent output over the already-open SSE connection.
- **HITL approval:** `<button hx-post="/session/{id}/approve" hx-vals='{"gate":"scope","approved":true}'>Approve</button>`. Server resumes crew kickoff on 200.
- **Artifact download:** plain `<a href="/session/{id}/artifact/{name}" download>` — no HTMX required.
- **Custom "tool renderer" replacements:** Python functions in `views/artifacts.py` return HTML fragments per artifact type (MRD card, PRD card, stack card, references card, build-plan card). Each card exposes "Download" and a collapsible "View traceability" HTMX region.

### User Interface Requirements

- Single page, left chat pane + right artifact sidebar.
- Responsive: works on ≥360px viewports; no mobile-specific features in MVP.
- Accessibility: semantic HTML (native advantage of server-rendered HTML); keyboard-navigable chat input + sidebar. WCAG AA is a Phase 2 target.
- Loading states: per-message "typing…" placeholder (HTMX `hx-indicator`); per-artifact "generating…" placeholder replaced by the rendered card via SSE swap.
- Error states: a persistent banner region that receives `sse-swap="error"` events.

---

## 4. Backend Architecture Specification

### API Architecture (FastHTML, single service)

- **Runtime:** Python 3.12+, FastHTML (Starlette-based), CrewAI, Uvicorn. One process owns UI rendering AND HTTP endpoints AND CrewAI execution.
- **Endpoints (MVP):**
  - `GET /` — initial page load; returns a full HTML page with an empty chat region, the artifact sidebar, HTMX `<script>` tags, and an initial "paste your idea" form. A fresh `session_id` (UUID) is generated server-side and embedded into the returned HTML; the session-state dict is created lazily on the first POST.
  - `POST /session/{id}/message` — submit user idea or discovery answer. HTMX form body: `content=<text>`. Returns an HTML fragment of the user message bubble for immediate `hx-swap="beforeend"` insertion; agent output follows asynchronously over SSE.
  - `GET /session/{id}/stream` — SSE stream. Each event's `data:` is an HTML fragment keyed by event type (`message`, `artifact`, `hitl_request`, `error`, `done`).
  - `POST /session/{id}/approve` — HITL approval. HTMX form body: `gate=<scope|artifacts>&approved=<true|false>`. Returns an HTML fragment acknowledging the approval; the HTTP layer then kicks off the next task batch (see ADR-6 HITL mechanics).
  - `GET /session/{id}/artifact/{name}` — returns raw markdown with `Content-Disposition: attachment` for direct download.
  - `GET /healthz` — liveness. `GET /readyz` — readiness (verifies `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` are present and usable).
- **Streaming:** SSE with `text/event-stream` via Starlette's streaming response. Heartbeat events every 20s to keep proxies from dropping the connection. HTMX's `sse` extension handles reconnection.
- **Validation:** server-side validators on every form-body handler (length, content type). Reject oversized inputs (user message >2000 chars per F1) with an HTML error fragment.
- **Rate limiting:** in-process token-bucket per-session for MVP (e.g. 20 messages per session per minute). No Redis dependency.
- **CORS:** not applicable — single service, same origin. No `CORS_ORIGIN` env var needed.
- **Error shape:** errors rendered as HTML fragments into the error region (client-facing); structured JSON error records written to stdout logs with `trace_id` for operators. Never leak stack traces to HTML responses.

### Database Architecture

**MVP: no database.** Session state lives in a `dict[session_id, SessionState]` in process memory. Artifacts written to `/tmp/origin-ai/sessions/<session-id>/` on disk (ephemeral; cleared on container restart).

Future-proof schema sketch (Phase 2, informational — do not implement now):
- `User(id, email, created_at)`
- `Session(id, user_id, created_at, idea_text)`
- `Artifact(id, session_id, type, content, created_at)`
- Chosen DB (Phase 2): SQLite for development, Postgres for production.

### CrewAI Integration Layer

- A single `CrewRunner` class wraps crew kickoff and exposes an async iterator that yields SSE events as HTML fragments.
- Agent configs loaded from `app/crew/config/agents.yaml` (five agents including A5 orchestrator); tasks from `app/crew/config/tasks.yaml` (T0–T5). Preflight validates all placeholders + all whitelisted tools resolve.
- Custom tools live under `app/crew/tools/` and are imported and bound explicitly in `CrewRunner.__init__` — no dynamic registration.
- Per ADR-6, the runner is invoked in three batches to support HITL gate pauses:
  - Batch 1: T0 (A5 init) + T1 (A1 Discovery) — pauses at scope gate.
  - Batch 2: T2 (A2 Synthesizer) — pauses at artifact gate.
  - Batch 3: T3 (A3 Stack) + T4 (A4 Repo) + T5 (A5 Consolidation) — runs to completion.
- Between batches, session state (approved scope, approved artifacts, accumulated Task.context) is held in the session-state dict.
- `step_callback` emits structured events; the event-to-HTML-fragment mapper (in `app/views/`) turns each into an `sse-swap`-targeted fragment. Filtering: internal chain-of-thought is NOT forwarded to the client; only tool-call summaries, partial agent output, and artifact announcements are.

### Authentication & Security Specifications

- **No user auth in MVP (ADR-4).**
- **API key management:** LLM provider key (`ANTHROPIC_API_KEY`) and GitHub token (`GITHUB_TOKEN`) loaded from env vars; `.env.example` enumerates all required vars (adapter-crewai rule).
- **Input sanitization:** prompt-injection mitigation on user input before embedding in agent prompts — strip/escape known injection tokens, limit length, reject binary content. Per adapter-crewai: "sanitize quoted inputs to neutralize prompt-injection tokens." HTML output paths MUST escape any user-supplied content that is rendered back as HTML (standard XSS hygiene — FastHTML's `ft` primitives escape by default; guard any raw-HTML paths explicitly).
- **Rate limiting:** per-session token-bucket (above). Per-IP rate limit deferred until a public deploy is chosen.
- **CORS:** N/A — single service, same origin (ADR-1 consequence).
- **No PII** logged. User idea text is treated as sensitive and is NOT written to persistent logs — only to session-scoped files that live alongside the ephemeral session dir.

---

## 5. DevOps & Deployment Architecture

### CI/CD Pipeline

**MVP (lean):**
- GitHub Actions workflow: lint (ruff, mypy) + unit tests + build Docker image on every push to `master`. No JS toolchain needed.
- No automated deploy in MVP. Deploy is a manual `docker run` (or `docker compose up` with a single service) against the chosen host, so a failed build cannot accidentally ship.
- Deferred: blue-green, rollback automation, E2E smoke gates — Phase 2.

### Deployment Configuration

**Target (chosen for MVP):** local Docker or a single hobby-tier container host (Render, Fly.io, or Railway). AWS App Runner is not selected for MVP because it adds IAM/VPC/IaC surface not justified by MVP acceptance.

**One container in MVP** (ADR-1 consequence):
- `origin-app` — FastHTML + HTMX + CrewAI in a single Python process. Exposes a single port (default `:8000`).

Single `.env` drives the service. Docker compose file ships in-repo for local dev consistency even though there's only one service (makes env-var handling uniform with future services).

Health checks:
- `GET /healthz` — 200 if process alive.
- `GET /readyz` — 200 if `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` are present and validated by a cached probe call.

**Deferred to Phase 2:** IaC (Terraform/CloudFormation), multi-environment pipelines, auto-scaling policies, blue-green, disaster recovery.

### Monitoring & Observability

**MVP:**
- Structured JSON logs to stdout from the single service. Include `session_id`, `task_id`, `event`, `duration_ms`, `token_count` where applicable.
- Trace logs per session under `logs/` (see §2).
- Audit block on every produced artifact (adapter-crewai).
- No external log aggregator, APM, or dashboard in MVP. Container host's log viewer is sufficient.

**Deferred:** OpenTelemetry, Grafana, alert routing, user-behavior analytics.

---

## 6. Data Flow & Integration Architecture

### Request/Response Flow (happy path)

1. Browser loads `GET /`. FastHTML returns a full HTML page with an embedded `session_id`, the idea-input form, and `hx-ext="sse" sse-connect="/session/{id}/stream"` on the chat region. The SSE connection opens immediately.
2. User types an idea into the form. HTMX submits `POST /session/{id}/message`. FastHTML returns an HTML fragment (user message bubble) inserted via `hx-swap="beforeend"`. The server then invokes `CrewRunner.kickoff_batch_1` (T0 init + T1 discovery).
3. T0 initializes session state. T1 (A1 Discovery) runs; each question streams as an `sse-swap="message"` HTML fragment appended to the chat. User answers via the same form POST; the server re-invokes T1 for the next turn (or the crew is structured to take multiple user-message inputs — implementation detail for @backend-eng).
4. After N questions, T1 emits `hitl_request(gate=scope)`: an HTMX approval card fragment (`<div id="hitl" hx-swap-oob="true">...</div>`) swaps into the HITL region via SSE. User clicks "Approve" → `hx-post` to `/session/{id}/approve`. Server kicks off `batch_2`.
5. T2 (A2 Synthesizer) runs. Streams partial output as `sse-swap="message"` fragments; produces `mrd.md` and `prd.md`; emits `sse-swap="artifact"` fragments that append cards to the artifact sidebar. Then emits `hitl_request(gate=artifacts)`. User approves. Server kicks off `batch_3`.
6. T3 (A3 Stack) and T4 (A4 Repo) run sequentially. Each produces an artifact and emits an `artifact` event.
7. T5 (A5 Orchestrator — consolidation) assembles `build_plan.md`, appends Audit blocks on all artifacts from T1–T4, captures the full Prompt Trace, and emits a final `artifact` event followed by `done`.
8. User downloads any artifact via plain `<a href="/session/{id}/artifact/{name}" download>`.

### External Integration Requirements

| Service | Purpose | Failure mode | Mitigation |
|---|---|---|---|
| Anthropic Claude API (via CrewAI's LiteLLM) | LLM calls for A1–A5 | 5xx, rate limit, timeout | Retry with backoff (`max_retry_limit=2`); on final failure, Halt-and-Report + user-visible error |
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
| `app.main` (FastHTML) | Service | App instance, route registration, middleware | F7 |
| `app.routes.pages` | Routes | Full-page handler (`GET /`) | F7 |
| `app.routes.messages` | Routes | `POST /session/{id}/message`, `POST /session/{id}/approve` | F1, F2 |
| `app.routes.stream` | Routes | `GET /session/{id}/stream` (SSE) | F7 streaming |
| `app.routes.artifacts` | Routes | Artifact download | F3, F6 |
| `app.views.*` | UI | HTML fragment generators (chat, artifact cards, HITL cards, errors) | F7, F8 |
| `app.crew.crew_runner` | Module | CrewAI orchestration across T0–T5 batches, Prompt Trace, Audit | §2, F8 |
| `app.crew.agents.a5_orchestrator` | Agent | Session init (T0) + consolidation (T5) | F6, F8 |
| `app.crew.agents.a1_discovery` | Agent | Conversational discovery | F2 |
| `app.crew.agents.a2_synthesizer` | Agent | MRD/PRD generation | F3 |
| `app.crew.agents.a3_stack_rec` | Agent | Stack recommendation | F4 |
| `app.crew.agents.a4_repo_finder` | Agent | Grounded GitHub repo retrieval | F5 |
| `app.crew.tools.artifact_writer` | Tool | Markdown artifact writes | F3, F6 |
| `app.crew.tools.stack_archetype_lookup` | Tool | Static JSON lookup | F4 |
| `app.crew.tools.github_search` | Tool | GitHub search API wrapper | F5 |
| `app.crew.tools.github_repo_verify` | Tool | GitHub repo existence check | F5 hard gate |
| `app.sanitizer` | Module | Prompt-injection input cleaning | §4 security |
| `app.crew.config/agents.yaml`, `tasks.yaml` | Config | Externalized CrewAI config (5 agents, 6 tasks T0–T5) | adapter-crewai |
| `app.static/` | Assets | HTMX core, HTMX sse extension, PicoCSS (self-hosted OK) | F7 |

### Process / Runtime View — see §2 orchestration diagram

- HITL gates pause the crew between T1→T2 and T2→T3. The HTTP layer drives three `CrewRunner` invocations (batch 1: T0+T1; batch 2: T2; batch 3: T3+T4+T5); between batches, session state sits in memory awaiting approval. Approvals arrive as HTMX `hx-post` to `/session/{id}/approve`.
- On any agent Halt-and-Report, the SSE stream emits an `error` fragment and the session is marked failed; the user can start a new session by reloading.

### Deployment View

```
[ Browser ]
    │  HTTPS (HTML + HTMX + SSE over one connection each)
    ▼
[ origin-app (FastHTML + HTMX + CrewAI, single Python process :8000) ]
    │                           │
    │                           ├──→ Anthropic Claude API (via CrewAI/LiteLLM)
    │                           └──→ GitHub REST API
    ▼
/tmp/origin-ai/sessions/<id>/ (ephemeral artifact dir on container fs)
```

Single host in MVP. **One container.** Docker compose file ships in-repo for env-var consistency, even though there's only one service.

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

- **ADR-1 (r2)** Single Python service: FastHTML + HTMX + CrewAI, one container. *Supersedes r1 two-service split.*
- **ADR-2 (r2)** UI = FastHTML-rendered HTML + HTMX + PicoCSS. No Next.js, no assistant-ui, no React. *Supersedes r1 Next.js/assistant-ui/Tailwind stack.*
- **ADR-3** No database in MVP.
- **ADR-4** No auth in MVP.
- **ADR-5 (r2 reconfirmed)** Claude API (Anthropic) via CrewAI's LiteLLM layer with `anthropic/` prefix.
- **ADR-6 (r2)** Sequential CrewAI process; A5 Orchestrator runs as T0 and T5 bookend tasks; HTTP layer drives three kickoff batches to support HITL gates. `allow_delegation=False` on every agent. *Revised r2 to account for 5-agent decomposition.*
- **ADR-7 (r2)** SSE transport; consumer is HTMX's `sse` extension. SSE event bodies are HTML fragments (not JSON). *Transport unchanged from r1; consumer changed.*

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
| HTMX SSE extension is an optional JS file | Low | Self-host in `app/static/`; no CDN dependency at runtime. Pinned to a specific HTMX version in the HTML. |
| FastHTML is a less-mature framework than FastAPI | Low | FastHTML is Starlette-based; underlying runtime is well-established. Migration to Starlette + a thin HTML helper layer is a feasible escape hatch if needed. |

---

## Future Work (explicitly deferred)

- **F9 Artifact editing UI** — Phase 2. Requires a richer rendering layer and regeneration plumbing.
- **F10 Auth + saved projects** — Phase 2. Introduces DB, session middleware (Starlette `SessionMiddleware` + a lightweight auth provider like OAuth proxy), migrations, privacy review.
- **F11 Expanded stack archetypes** — Phase 2. Possibly a RAG corpus or community-maintained list.
- **F12 Alternate discovery modes** — Phase 2. Multiple T1 agents with templated question sets.
- **F13 Hand-off to agentic builders** — Phase 3.
- **F14 Collaboration** — Phase 3.
- **F15 Analytics** — Phase 3.
- **Parallel T3/T4** — Phase 2 performance optimization.
- **IaC (Terraform/CloudFormation)** — Phase 2.
- **APM, Grafana, OpenTelemetry** — Phase 2.
- **GDPR / SOC2 compliance** — gated by Phase 2 persistence introduction.
- **PostgreSQL (via SQLAlchemy or similar Python ORM)** — Phase 2 with F10. Prisma is NOT planned — the stack is Python-only now.
- **Auth provider integration** (e.g. GitHub OAuth via Starlette session middleware) — Phase 2 with F10. NextAuth is NOT planned — no Node runtime.

---

## Traceability Matrix (PRD → SAD)

| PRD Feature | SAD Location | SFS target (to be authored) |
|---|---|---|
| F1 Idea Intake | §4 endpoints, §4 security (sanitizer) | sfs/f1-idea-intake.md |
| F2 Conversational Discovery | §2 A1, §6 flow step 2–4 | sfs/f2-discovery.md |
| F3 MRD + PRD Generation | §2 A2, §4 artifact_writer | sfs/f3-mrd-prd-gen.md |
| F4 Stack Recommendation | §2 A3, stack_archetype_lookup | sfs/f4-stack-rec.md |
| F5 Grounded GitHub Refs | §2 A4, github_* tools, Risks | sfs/f5-repo-finder.md |
| F6 Build Plan Output | §2 T5 (A5 Orchestrator consolidation), §6 flow step 7 | sfs/f6-build-plan.md |
| F7 Minimal Chat UI | §3 (FastHTML + HTMX), ADR-1, ADR-2, ADR-7 | sfs/f7-chat-ui.md |
| F8 Traceability & Audit | §2 Prompt Trace, §Views Data View | sfs/f8-audit.md |

Per-feature SFS files are the next deliverable from @system-arch via `*create-sfs`.

---

## Sources

- `project-context/1.define/prd.md` (r2 — 5 agents, Claude API via LiteLLM, FastHTML + HTMX stack)
- `project-context/1.define/mrd.md` (r2 — user-confirmed decisions 2026-04-23)
- `project-context/0.idea/idea.md`
- `.cursor/templates/sad-template.md`
- `.claude/rules/aamad-core.md`
- `.claude/rules/adapter-crewai.md`
- `.claude/rules/adapter-registry.md`
- `.claude/agents/system-arch.md`
- FastHTML docs — fastht.ml / github.com/AnswerDotAI/fasthtml (framework reference)
- HTMX docs — htmx.org (core + `sse` extension reference)
- Adapter: `AAMAD_ADAPTER=crewai` (default per adapter-registry)

---

## Assumptions

- **User-confirmed 2026-04-23:** Claude API (Anthropic) via CrewAI's LiteLLM layer is the MVP LLM; `anthropic/` prefix is required on Claude 4.x model IDs.
- **User-confirmed 2026-04-23:** FastHTML + HTMX is the UI stack; a single Python service owns HTML + HTTP + CrewAI. No Next.js, no React.
- Session state in process memory is acceptable for MVP (page reload loses state — consistent with PRD F7 acceptance).
- GitHub public REST API with a bot token provides sufficient headroom for F5 at MVP volumes (~100 lookups/day).
- Single-container Docker deploy to a hobby-tier host is acceptable; AWS App Runner and IaC are Phase 2.
- The operator will deploy MVP behind a shared secret or keep it unlisted — no auth in MVP means public deploy is an operator decision with cost-abuse risk.
- Per-session soft cap of 80K tokens is sufficient for a full T0→T5 run (to be instrumented; may need adjustment after initial sessions).
- HTMX's `sse` extension is expressive enough to deliver the streaming chat UX, HITL gate interstitials, and artifact-card swaps without a JavaScript SPA. To be validated during Build phase; fallback is HTMX polling (`hx-get` + `hx-trigger="every 2s"`).
- FastHTML's async route handlers integrate cleanly with CrewAI's async kickoff API; long-running crew batches run in the same process without blocking SSE streams. To be validated during Build phase.
- The A5 Orchestrator owning session init (T0) and consolidation (T5) is preferable to leaving those as deterministic non-agent tasks because it centralizes Prompt-Trace + Audit capture into one named role, simplifying adapter-crewai compliance.

---

## Open Questions

- **Model selection per agent.** Does A1 (conversation) warrant a cheaper/faster model than A2/A5 (artifact generation and consolidation)? Owner: @backend-eng before crew wiring.
- **Stack archetype JSON shape.** Schema for `stack_archetypes.json` — fields, cardinality, example entries. Owner: @product-mgr + @backend-eng.
- **GitHub query strategy.** What search query does A4 construct from the approved scope? Keyword extraction, language filter, min-star threshold? Owner: @backend-eng.
- **HITL timeout.** If a user walks away after the scope gate, how long does the session sit in memory? Proposed: 60 minutes idle → expire. Owner: @backend-eng.
- ~~**Streaming proxy.**~~ **Resolved 2026-04-23 (SAD r2 ADR-1):** single service, same origin, no proxy, no CORS.
- **Logs location in production.** `logs/` under the container's writable volume vs. stdout only. Current plan: both — trace files on disk, lifecycle events on stdout. Confirm with operator deployment constraints. Owner: @project-mgr.
- **Prompt-injection corpus.** PRD deferred corpus authoring to @qa-eng — SAD needs the corpus in hand before §9 security testing can complete. Owner: @qa-eng.
- **A5 Orchestrator's Prompt-Trace responsibility split.** How much Prompt-Trace / Audit capture lives inside A5's T0/T5 tasks vs. CrewAI's `step_callback` hooks? Both touch the same data; risk is double-writes or gaps. Owner: @backend-eng during crew wiring.
- **FastHTML + CrewAI concurrency model validation.** Starlette/FastHTML is async; CrewAI's `kickoff_async` returns an awaitable but runs tasks that may internally block on LLM calls. Confirm long crew batches do not starve SSE streams on the same event loop. Owner: @backend-eng; spike if uncertain.
- **HTMX SSE reconnection UX.** On transient disconnect, HTMX's SSE extension reconnects; but does the server re-emit buffered events or replay from start? Propose: stateful replay up to the last acknowledged event, else user restarts. Owner: @backend-eng.
- **CSS approach confirmation.** PicoCSS is the default (class-less). Does @frontend-eng want to override with vanilla CSS, plain stylesheets, or something else? Owner: @frontend-eng.

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

### Revision — 2026-04-23 (r2)

- **Timestamp:** 2026-04-23
- **Persona:** @system-arch
- **Command:** `*create-sad --mvp` (revision pass on existing SAD)
- **Adapter:** `AAMAD_ADAPTER=crewai` (default; not overridden)
- **Action:** revised SAD to absorb three user-confirmed decisions landed in `mrd.md` r2 and `prd.md` r2: (1) Claude API via CrewAI/LiteLLM with `anthropic/` prefix; (2) crew expanded to 5 agents with dedicated A5 Orchestrator; (3) runtime stack consolidated to single FastHTML + HTMX Python service.
- **ADRs revised (all within `§1 Technical Architecture Decisions`, with r2 markers and r1 text superseded):**
  - **ADR-1** — r1 "Python FastAPI backend separate from the frontend" → r2 "Single Python service using FastHTML + HTMX + CrewAI." Eliminates the two-deployable topology.
  - **ADR-2** — r1 "Next.js 14 + assistant-ui + Tailwind" → r2 "FastHTML-rendered HTML + HTMX + PicoCSS." Eliminates the JS toolchain.
  - **ADR-5** — reconfirmed; wording updated to "Claude API (Anthropic) via CrewAI's LiteLLM layer," matching PRD r2 phrasing. Substantive content unchanged.
  - **ADR-6** — r1 "Sequential, not hierarchical" → r2 "Sequential; A5 Orchestrator runs as T0 and T5 bookend tasks. `allow_delegation=False` on every agent including A5. HTTP layer drives three kickoff batches to support HITL gates." Resolves the MRD r2 Open Question on orchestrator delegation mode.
  - **ADR-7** — r1 "SSE over HTTP, consumed by assistant-ui" → r2 "SSE over HTTP, consumed by HTMX's `sse` extension. SSE event bodies are HTML fragments (not JSON)." Transport unchanged; consumer changed.
- **Cascading sections revised (knock-on from ADR changes):**
  - §1 Core vs. Future Features: one-container MVP (from two-container).
  - §2 Agent Architecture Requirements: agent table expanded to 5 rows including A5, with T0/T5 run markers. "Non-agent deterministic task T5 Build Plan Assembler" removed — now owned by A5.
  - §2 Task Orchestration Specification: T0 added; T5 re-attributed to A5; HITL gate mechanics clarified (HTTP layer drives three kickoff batches).
  - §3 Frontend Architecture Specification: entirely rewritten. No more Next.js, App Router, assistant-ui, shadcn, Tailwind, Zustand, TypeScript. Replaced with FastHTML + HTMX + PicoCSS + Python-only views and route handlers. Application Structure diagram replaced.
  - §4 Backend Architecture Specification: FastAPI replaced with FastHTML. Endpoints now return HTML fragments (not JSON). CORS eliminated. CrewRunner now invoked in three batches per HITL mechanics. HTML-output XSS escaping added to security.
  - §5 DevOps & Deployment: two containers → one container. CI lint lines simplified (no JS toolchain). Single `.env` still applies.
  - §6 Request/Response Flow: rewritten for FastHTML's full-page initial load + HTMX partial swaps + SSE HTML-fragment consumption. External integrations table updated to name CrewAI/LiteLLM path.
  - §4 Authentication & Security: CORS removed; HTML XSS-escaping noted.
  - Views — Logical View: component catalog updated to `app.*` Python module layout; `frontend` (Next.js) component removed; A5 Orchestrator agent added; T5 non-agent task removed.
  - Views — Deployment View: single-container ASCII diagram.
  - Architectural Decisions (consolidated): all r2 markers applied.
  - Risks: added HTMX SSE extension dependency and FastHTML maturity as Low risks with mitigations.
  - Future Work: "NextAuth integration" → "Auth provider integration (Starlette session middleware + OAuth)"; "PostgreSQL / Prisma" → "PostgreSQL via Python ORM"; explicit note that NextAuth / Prisma are NOT planned.
  - Traceability Matrix: F6 re-attributed to A5; F7 references ADR-1/2/7 explicitly.
  - Sources: PRD and MRD noted as r2; FastHTML and HTMX docs added.
  - Assumptions: rewritten to reflect user-confirmed decisions; added HTMX SSE, FastHTML/CrewAI concurrency, and A5 rationale assumptions.
  - Open Questions: "Streaming proxy" resolved (single service). Model-selection Open Question updated to cite A5. Added A5 Prompt-Trace split, FastHTML/CrewAI concurrency validation, HTMX SSE reconnection UX, and CSS confirmation Open Questions.
- **Sections NOT changed** (deliberate, for reviewer confidence): ADR-3 (no DB), ADR-4 (no auth), Stakeholders & Concerns, Viewpoints, Quality Attributes, §7 Performance & Scalability, §8 Security & Compliance structural items other than CORS/XSS noted, §9 Testing Strategy (still applies — unit tests per layer, E2E via Playwright still valid against HTMX; adjust assertions from JSON to HTML), §10 Launch Strategy.
- **ADR-3 / ADR-4 preserved intact** — the DB and auth deferrals are unaffected by this revision.
- **Inputs read:** `project-context/1.define/sad.md` (prior revision), `project-context/1.define/prd.md` (r2), `project-context/1.define/mrd.md` (r2), `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/adapter-registry.md`, `.claude/agents/system-arch.md`.
- **Output:** `project-context/1.define/sad.md` (this file, r2).
- **Model / tooling:** revised via Claude Code main thread (model: claude-opus-4-7[1m]). Single-pass revision, not a crew run.
- **Temperature / determinism:** N/A for authoring pass; downstream crew runs MUST honor `temperature ≤ 0.4`, `memory=False`, `allow_delegation=False` per adapter-crewai.
- **Template headings:** all section headings preserved; title of §3 changed from "(Next.js + assistant-ui)" to "(FastHTML + HTMX)" to reflect the new stack (per aamad-core "Outputs follow template headings exactly" — the template text in `sad-template.md` does not prescribe the specific stack in the heading, so this change is consistent).
- **No code fences around raw template content.** Confirmed.
- **Prohibited actions attempted:** none. Original r1 Audit preserved; revision appended per aamad-core append-only convention.
- **Open Questions resolved in r2:** orchestrator delegation mode (ADR-6), streaming proxy (ADR-1 consequence).
- **Handoff:**
  - @product-mgr and @system-arch alignment on the define artifacts is now complete for this iteration.
  - @system-arch to produce SFS files (`project-context/1.define/sfs/f*.md`) next via `*create-sfs`.
  - @project-mgr can begin environment scaffolding — Python-only workspace (no Node), `pyproject.toml` with `crewai`, `python-fasthtml`, `anthropic` (via litellm), and a Dockerfile for the single service.
