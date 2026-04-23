# Product Requirements Document (PRD) — Origin AI

**Persona:** @product-mgr
**Source artifacts:** `project-context/0.idea/idea.md`, `project-context/1.define/mrd.md`
**Date:** 2026-04-23
**Phase:** 1.define
**Scope:** MVP (Phase 1). Enhanced and Scale phases are informational and deferred.

---

## 1. Executive Summary

### Problem Statement

Solo developers start more projects than they finish. The gap between "I have an idea" and "I have a plan I can start executing" is high-friction: it requires simultaneously reasoning about audience, scope, stack choice, and prior art — usually in a notes app at 11pm with fading momentum. Existing PM tools (Jira, Linear, Notion) are team-shaped; AI PRD generators (ChatPRD, Notion AI) produce stakeholder-ready documents that are the wrong shape for a single builder who just wants to know what to build on Saturday morning.

Trace: MRD §1, §3 (persona), §3 (user journey).

### Solution Overview

Origin AI is a conversational multi-agent system that takes a rough project idea, conducts a short discovery dialogue, and produces a *builder-shaped* plan: an MRD, a PRD, a recommended tech stack with rationale, a handful of verified similar-GitHub repos, and a prioritized build plan the user can execute from. Every artifact is editable and traces back to the user's discovery answers.

Differentiators vs. existing tools (per MRD §5):
- **Builder-shaped, not PM-shaped.** Output is a build plan, not a stakeholder PRD.
- **Repo-grounded.** References are live-verified real repositories, not invented links.
- **Traceable.** Every recommendation cites which discovery answer produced it.

### Strategic Rationale

Multi-agent architecture is warranted (not incidental) because the workflow decomposes cleanly into four single-responsibility roles with deterministic hand-offs: conversational discovery, structured document synthesis, stack archetype matching, and grounded repo retrieval. Each role has different tool needs, different failure modes, and different quality gates — exactly the pattern CrewAI optimizes. A monolithic prompt would conflate these concerns, making both quality and determinism harder to enforce.

Business case is deferred: the MVP is a bootcamp learning artifact and a proof-of-concept. MVP success is measured by artifact quality and task completion rate, not revenue. Monetization considerations (MRD §5) anchor at the $10–$20/mo individual-dev tooling band and are out of scope for Phase 1.

---

## 2. Market Context & User Analysis

### Target Market

**Primary persona: Solo Developer / Indie Hacker** (MRD §3).
- 1–15 years coding experience.
- Builds side projects on evenings and weekends.
- Has more unfinished projects than finished ones.
- Currently relies on ad-hoc ChatGPT/Claude conversations and unstructured notes.

Market segment sizing is deferred to a live scan (MRD Open Questions). The MVP does not depend on market size for viability — it depends on being useful to N≈10–20 initial users.

**Geographic focus:** English-language, global. No localization in MVP.

### User Needs Analysis

Critical pain points (MRD §3):
- Momentum collapse between idea and first commit.
- Unstructured scoping leads to feature creep or underscoped MVPs.
- Stack-choice paralysis: "what should I build this with?"
- Prior-art discovery is expensive (hours of Googling, README skimming).

Adoption enablers: fast time-to-value (<15 min), editable artifacts (not a black box), verifiable references (real repos).

Adoption barriers: trust in AI-generated scope, perceived effort of answering discovery questions vs. just starting to code.

### Competitive Landscape

Per MRD §1:
- **ChatPRD** — closest analog, focused on PRD generation for PMs. Different persona.
- **Notion AI / Linear AI** — document/task generation inside team tools. Not a discovery workflow.
- **GitHub Copilot, Cursor, Devin, Replit Agent** — downstream of Origin AI (code, not plan).

Gap Origin AI fills: no tool combines conversational discovery + MRD/PRD + stack recommendation + grounded repo discovery in one solo-dev-shaped flow.

Feature differentiation (MVP):
- Repo-grounded references (verified via GitHub API).
- Traceable reasoning per artifact section.
- Builder-plan output, not stakeholder PRD.

Pricing benchmarks ($10–$20/mo individual tier) are informational. MVP is unpriced.

---

## 3. Technical Requirements & Architecture

> This section declares the agent/task/tool contract at the level @product-mgr owns. Detailed architecture (process model, API shape, runtime topology, data flow) is deferred to @system-arch in the SAD.

### CrewAI Framework Specifications

- **Framework:** CrewAI. Adapter rules: `.claude/rules/adapter-crewai.md`.
- **Process:** Sequential (deterministic, auditable). Hierarchical is not used in MVP (per adapter rule: hierarchical only when required by SAD).
- **Orchestration:** Four agents executing in order. Two human-in-the-loop gates: after discovery, after MRD/PRD synthesis.
- **Determinism settings (MVP-wide, per adapter rules):**
  - `memory = False`
  - `allow_delegation = False`
  - `verbose = False` (production)
  - `respect_context_window = True`
  - `max_iter ≤ 12`
  - `max_retry_limit ≥ 2`
  - `temperature ≤ 0.4` for all artifact-generation tasks
- **LLM provider / model:** Anthropic Claude via LiteLLM (to be confirmed by @system-arch). Provider prefix `anthropic/` required on Claude 4.x model IDs.

### Core Agent Definitions

Four agents, each with a single responsibility. Declared adapter-neutrally; YAML binding and exact tool wiring are @system-arch / @backend-eng's scope.

**Agent A1: Discovery Agent**
- role: "Solo-Developer Project Discovery Interviewer"
- goal: "Elicit enough structured context about a rough idea (audience, core job-to-be-done, must-haves, non-goals, constraints) to support MRD/PRD/stack/repo generation, using 5–10 conversational questions."
- backstory: "Experienced technical product interviewer who has scoped hundreds of side projects. Biased toward short, high-leverage questions and avoiding jargon."
- tools: none (conversation only).
- memory: False (conversation state passed via Task.context, not memory).
- delegation: False.
- human-in-the-loop: yes — user approves the structured scope before synthesis begins.

**Agent A2: Synthesizer Agent**
- role: "Builder-Shaped MRD/PRD Author"
- goal: "Transform approved discovery output into an MRD and PRD following AAMAD templates, with explicit traceability from each section to the discovery answer that produced it."
- backstory: "Senior product writer specializing in concise, builder-oriented specifications. Writes for readers who will execute, not for stakeholders who will approve."
- tools: file writer (structured artifact writes to a session output dir).
- memory: False.
- delegation: False.
- human-in-the-loop: yes — user approves draft artifacts before downstream agents run.

**Agent A3: Stack Recommender Agent**
- role: "Pragmatic Tech Stack Recommender for Side Projects"
- goal: "Recommend a concrete, coherent stack (frontend, backend, data, deploy) matched to the approved scope, with a one-paragraph rationale per component citing which scope constraints drove the choice."
- backstory: "Full-stack engineer with bias toward boring, well-documented choices for side projects; avoids over-engineering."
- tools: curated stack-archetype reference (static in MVP; see §4, F3).
- memory: False.
- delegation: False.
- human-in-the-loop: no (output is reviewable in the final build plan).

**Agent A4: Repo Finder Agent**
- role: "Grounded GitHub Prior-Art Retriever"
- goal: "Identify 3–5 real, active GitHub repositories relevant to the approved scope; each result must be verified to exist via the GitHub API before inclusion, with a one-line relevance rationale."
- backstory: "Research engineer who refuses to cite anything unverified; treats hallucinated links as a credibility failure."
- tools: GitHub search/read (public API, read-only).
- memory: False.
- delegation: False.
- human-in-the-loop: no.

**Consolidation (non-agent task): Build Plan Assembler**
- After A2–A4 complete, a deterministic task assembles the final build plan (milestones, first-week tasks, references). This may be a fifth agent or a template-fill task at @system-arch's discretion.

### Integration Requirements

- **External APIs (MVP):** LLM provider API (Anthropic via LiteLLM), GitHub public API (read-only search + repo metadata). No user-auth service in MVP.
- **Database:** none in MVP. Session state in memory; artifacts written to a session output directory.
- **Authentication:** none in MVP. Deferred.
- **Performance:** time-to-plan target <15 minutes end-to-end (see §7). Not a hard throughput requirement in MVP.

### Infrastructure Specifications

- **Compute:** single containerized backend (CrewAI + API layer) + minimal web frontend.
- **Deploy target:** any container host (Render, Fly.io, Railway, or local Docker). Exact target selected by @system-arch / @project-mgr.
- **Monitoring:** structured JSON logs to stdout. Per-agent lifecycle events, token usage, latency. No external observability stack in MVP.
- **Security:** API keys loaded from environment variables only. `.env.example` required. Prompt-injection sanitization on user input (per adapter-crewai rules).

---

## 4. Functional Requirements

Features traced to MRD §3 user journey.

### Core Features — Priority P0 (MVP)

**F1 — Idea Intake**
- User story: As a solo developer, I paste or type a 1–3 sentence project idea into a chat input so the system has a starting point.
- Acceptance criteria:
  - Chat input accepts freeform text up to 2,000 characters.
  - Input is sanitized for prompt-injection tokens before being passed to A1.
  - Empty or trivially short (<20 char) input is rejected with a helpful message.
- Traceability: MRD §3 journey step 1.

**F2 — Conversational Discovery**
- User story: As a solo developer, I answer 5–10 clarifying questions so the system has enough context to produce useful artifacts.
- Acceptance criteria:
  - A1 asks 5–10 questions total, one at a time, each building on prior answers.
  - A1 covers at minimum: target audience, core job-to-be-done, must-have features, explicit non-goals, hard constraints (time/budget/tech).
  - User can answer "skip" or "not sure" without blocking progress.
  - At end of discovery, A1 produces a structured scope summary and requests user approval before synthesis begins.
- Traceability: MRD §3 journey step 2, success metrics (time-to-plan).

**F3 — MRD + PRD Generation**
- User story: As a solo developer, I receive auto-generated MRD and PRD drafts so I have shareable, editable scoping documents.
- Acceptance criteria:
  - A2 produces artifacts matching `.cursor/templates/mr-template.md` and `.cursor/templates/prd-template.md` headings.
  - Required sections (Sources, Assumptions, Open Questions, Audit) are present per AAMAD core rules.
  - Each major section references the discovery answer(s) that produced it.
  - Artifacts are rendered in the UI and downloadable as markdown.
  - Artifacts are NOT wrapped in code fences (per aamad-core rule on raw template content).
- Traceability: MRD §3 journey step 3; aamad-core "State and Output" rule.

**F4 — Tech Stack Recommendation**
- User story: As a solo developer, I receive a concrete stack recommendation with rationale so I don't have to resolve stack-choice paralysis myself.
- Acceptance criteria:
  - A3 output names a specific stack covering frontend, backend, storage, and deploy surface (where applicable to the scope).
  - Each component has a 1–3 sentence rationale citing which scope constraint drove the choice.
  - Recommendations draw from a curated allow-list of stack archetypes (MVP constraint — prevents invented/obscure recommendations).
- Traceability: MRD §3 journey step 4, §5 differentiator.

**F5 — Grounded GitHub Reference Repos**
- User story: As a solo developer, I receive 3–5 similar real GitHub repositories with one-line relevance notes so I can see prior art instead of searching myself.
- Acceptance criteria:
  - A4 returns 3–5 repos.
  - Every repo URL resolves via the GitHub API (200 status, repo exists) before inclusion. Unverified results are dropped, not returned.
  - Each repo has a one-line "why this is relevant" sentence referencing the scope.
  - Fewer than 3 verified results produces a user-visible "we couldn't find strong references" message rather than fabrication.
- Traceability: MRD §5 differentiator (repo grounding); MRD risk-matrix "High Risk: fabricated repo links."

**F6 — Build Plan Output**
- User story: As a solo developer, I receive a consolidated build plan so I can start executing.
- Acceptance criteria:
  - Final output includes: 3–6 milestones, a first-week task list (5–10 concrete tasks), a link to each generated artifact, and the stack + repo references.
  - Output is rendered in the UI and downloadable as a single markdown file.
- Traceability: MRD §3 journey step 6.

**F7 — Minimal Chat Interface**
- User story: As a solo developer, I use a simple chat UI to complete the end-to-end flow without any configuration.
- Acceptance criteria:
  - Single-page web UI: chat pane + saved-artifact sidebar.
  - Streaming agent responses.
  - No sign-up, no auth, no settings in MVP.
  - Session resets on page reload (no persistence in MVP — see F-deferred list).
- Traceability: MRD §3 interface requirements.

**F8 — Traceability & Audit**
- User story: As a solo developer, I can see which discovery answer produced which recommendation so I can trust and edit the output.
- Acceptance criteria:
  - Each generated artifact includes an Audit section (timestamp, persona, model, temperature, token usage) per aamad-core rules.
  - Each major section in MRD/PRD/build-plan cites the discovery answer(s) that informed it.
- Traceability: MRD §5 differentiator (traceable reasoning); aamad-core Agent Contract.

### Enhanced Features — Priority P1 (Post-MVP, informational only)

- **F9 — Artifact Editing UI.** Inline edit of generated artifacts with re-generation triggered downstream.
- **F10 — Saved Projects + Auth.** User accounts, saved sessions, revisitable build plans.
- **F11 — Expanded Stack Archetypes.** Dynamic stack recommendations beyond the MVP allow-list.
- **F12 — Alternate Discovery Modes.** Guided templates for common project types (SaaS, CLI, browser extension, etc.).

### Future Features — Priority P2 (informational only)

- **F13 — Hand-off to Agentic Builders.** Export build plan to Devin / Replit Agent / Claude Code as a structured job.
- **F14 — Collaboration.** Share projects with a co-builder; deferred until multi-user demand is validated.
- **F15 — Analytics.** Aggregate signals on which stacks/archetypes correlate with finished projects.

---

## 5. Non-Functional Requirements

### Performance

- Time-to-plan (idea → saved build plan) median **<15 minutes** end-to-end (MVP target; MRD §3 success metric).
- Streaming agent responses: first token within 3 seconds of task start (wall-clock budget; soft target in MVP).
- Per-session LLM cost **<$0.50** at current frontier-model pricing (MVP target; MRD §4).

### Security & Compliance

- API keys loaded from environment variables only; no secrets in code or artifacts (aamad-core).
- `.env.example` enumerates all required env vars (adapter-crewai).
- User input sanitized before agent prompts (prompt-injection mitigation, adapter-crewai).
- No PII handling in MVP. User idea text is not persisted beyond the session.
- No regulatory compliance scope (GDPR, SOC2) in MVP — deferred with data persistence.

### Reliability & Scalability

- Single-user-at-a-time assumption in MVP; concurrent-session scaling is deferred.
- LLM-provider retry with backoff; `max_retry_limit ≥ 2` per adapter-crewai.
- GitHub API rate-limit handling: graceful degrade to fewer verified refs with user-visible message (F5).
- Agent failure rate **<5%** of runs (MVP target; MRD §3 success metric). A failure = a guardrail abort or Halt-and-Report.

### Determinism & Reproducibility

- `temperature ≤ 0.4` for artifact-generation tasks (adapter-crewai).
- `memory = False` for reproducibility (adapter-crewai).
- Prompt Trace captured per crew run; Audit block on every artifact.

---

## 6. User Experience Design

### Interface Requirements

- Single-page web chat UI. Chat pane + saved-artifact sidebar. Mobile-responsive but not mobile-first in MVP.
- Accessibility: semantic HTML, keyboard navigation for chat input + sidebar. WCAG AA nice-to-have; not a blocker for MVP.
- No settings panel, no dark-mode toggle, no onboarding — defer anything that isn't the golden path.

### Agent Interaction Design

- **Human-in-the-loop gates (2 in MVP):**
  1. After discovery (F2): user approves scope summary before F3 runs.
  2. After artifact synthesis (F3): user approves drafts before F4/F5 run.
- **Streaming:** agent output streams in real-time; user sees progress.
- **Error handling:** user-visible errors are plain English. On any Halt-and-Report, the UI offers "restart" and shows which stage failed.
- **Transparency:** each generated section renders with a "sourced from: [discovery answer]" hover/expand affordance (F8).

---

## 7. Success Metrics & KPIs

### Business Metrics (MVP — qualitative only)

- MVP is a bootcamp learning artifact and PoC. No revenue or acquisition targets.
- Post-MVP decision gate: "Would I pay $10–$20/mo for this?" — ask 10–20 users.

### Technical Metrics

- **Agent failure rate:** <5% of runs end in Halt-and-Report (MRD §3).
- **Per-session LLM cost:** <$0.50 median (MRD §4).
- **GitHub reference verification rate:** 100% of returned repos resolve via API (F5 acceptance).

### User Experience Metrics

- **Task completion rate:** ≥60% of sessions reach a saved build plan (MRD §3 success metric). Baseline; to be tightened after first N=20 sessions.
- **Time-to-plan (median):** <15 min (MRD §3).
- **Qualitative usefulness:** "Could you start building from this plan?" — Y/N survey at session end. Target: ≥70% Y across first 20 sessions.

---

## 8. Implementation Strategy

### Development Phases

**Phase 1 — MVP (in scope).**
- F1–F8 implemented end-to-end.
- 4 agents configured via YAML under `config/` (adapter-crewai rule).
- Single FastAPI/equivalent backend + minimal chat frontend.
- Deployed to a single container host OR runnable locally via Docker.
- Ships when: golden path (idea → build plan) works with all F1–F8 acceptance criteria met; qa.md documents smoke test results.

**Phase 2 — Enhanced (deferred).**
- F9–F12. Requires auth, persistence, database — a materially larger infra step.

**Phase 3 — Scale (deferred, informational).**
- F13–F15. Agentic hand-off, collaboration, analytics.

### Resource Requirements (MVP)

- **Team:** single builder (bootcamp student).
- **Infra:** LLM provider API (Anthropic), GitHub public API key, hobby-tier hosting.
- **Budget:** LLM spend is the dominant cost. Budget $20–$50 for initial 50–100 dev/test sessions.

### Risk Mitigation (recap from MRD §Risk Matrix)

- **High: fabricated GitHub repos.** Mitigation: F5 acceptance — live API verification required; drop unverified results.
- **High: low-quality artifacts.** Mitigation: expected_output schemas, guardrails, human-in-the-loop gates (F2/F3 approval).
- **Medium: cost drift on long conversations.** Mitigation: per-session token cap + session timeout.
- **Medium: LLM provider outage.** Mitigation: retry with backoff; graceful user-facing error.

---

## 9. Launch & Go-to-Market Strategy

Deferred. This is a bootcamp MVP, not a commercial launch.

Informational placeholders for future reference:
- **Beta cohort:** 10–20 solo developers recruited from Indie Hackers / personal network.
- **Feedback capture:** post-session 1-question survey + 3 qualitative interviews.
- **Public launch criteria:** ≥70% "Y" on usefulness survey across 20 sessions.
- **Pricing anchor (future, not committed):** $10–$20/mo individual tier per MRD §1 benchmarks.

---

## Quality Assurance Checklist

- [x] All requirements traceable to MRD findings (each feature cites MRD section).
- [x] Technical specifications feasible with CrewAI (sequential process, declared tools, adapter-crewai-compliant settings).
- [x] Success metrics aligned with MVP PoC objectives (task completion, time-to-plan, usefulness survey).
- [x] Resource requirements realistic and justified (single builder, bootcamp timeline, $20–$50 LLM budget).
- [x] Risk mitigation comprehensive and actionable (F5 repo verification, cost caps, retry policy, HITL gates).
- [x] Timeline achievable — MVP bounded to F1–F8, Enhanced/Scale explicitly deferred.
- [x] Template headings respected; no code fences around raw sections (aamad-core).
- [x] Sources, Assumptions, Open Questions, Audit sections present.

---

## Sources

- `project-context/0.idea/idea.md` — original idea brief.
- `project-context/1.define/mrd.md` — market research, persona, differentiators, risk matrix.
- `.cursor/templates/prd-template.md` — structural template.
- `.cursor/templates/mr-template.md` — referenced by F3 acceptance.
- `.claude/rules/aamad-core.md` — Agent Contract, Task Contract, State and Output, Security rules.
- `.claude/rules/adapter-crewai.md` — CrewAI-specific settings (memory, delegation, temperature, retries, YAML externalization).
- `.claude/agents/product-mgr.md` — persona scope boundary.

---

## Assumptions

- Anthropic Claude via LiteLLM is the MVP LLM provider, with `anthropic/` prefix on model IDs (per prior-session memory). @system-arch to confirm or override.
- GitHub public search API is sufficient for F5 at MVP volumes; rate limits will be addressed by token-authenticated requests and graceful degradation.
- A curated stack-archetype allow-list for F4 will be authored in-repo (no dependency on external corpus for MVP). Scope TBD between @product-mgr and @system-arch.
- Users are solo developers who are comfortable with a chat UI and do not need onboarding in MVP.
- Per-session cost budget of $0.50 is achievable with sensible token caps; to be instrumented in MVP.
- Session state lives in process memory; no persistence required for MVP acceptance.

---

## Open Questions

- **LLM model choice.** Exact model ID for A1 (conversation) vs. A2–A4 (artifact gen)? A smaller/cheaper model on A1 could reduce per-session cost materially. Owner: @system-arch.
- **Stack-archetype corpus.** Author from scratch, derive from "awesome" lists, or embed at runtime from a small curated JSON? Owner: @product-mgr + @system-arch.
- **Session output directory.** Where do artifacts land (user-local download, server-side session dir, both)? Owner: @system-arch (affects frontend/backend contract).
- **Human-in-the-loop UX.** How does the UI render the approval gates without feeling like a form? Owner: @frontend-eng in Phase 2.
- **Prompt-injection test corpus.** What canned adversarial inputs will QA use to validate F1 sanitization? Owner: @qa-eng.
- **Cost instrumentation.** Per-agent token accounting — capture in Audit block per adapter-crewai; confirm the logging shape with @backend-eng.
- **F4 fallback.** If the approved scope doesn't cleanly match any archetype in the allow-list, what does A3 return? Proposed default: "best partial match + explicit caveat." Owner: @product-mgr.

---

## Audit

- **Timestamp:** 2026-04-23
- **Persona:** @product-mgr
- **Action:** authored PRD for Origin AI from MRD and idea brief.
- **Inputs read:** `project-context/0.idea/idea.md`, `project-context/1.define/mrd.md`, `.cursor/templates/prd-template.md`, `.cursor/templates/mr-template.md`, `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/agents/product-mgr.md`.
- **Output:** `project-context/1.define/prd.md` (this file).
- **Model / tooling:** authored via Claude Code main thread (model: claude-opus-4-7[1m]); single-pass authoring, not a crew run.
- **Temperature / determinism:** N/A for this authoring pass; crew runs implementing this PRD MUST honor `temperature ≤ 0.4` per adapter-crewai.
- **Scope boundary respected:** persona architecture / agent contract declared at PRD level; process model, API shape, runtime topology explicitly deferred to @system-arch.
- **Prohibited actions attempted:** none.
- **Template headings check:** Sections 1–9 + QA Checklist present. Sources / Assumptions / Open Questions / Audit present per aamad-core.
- **No code fences around raw template content.** Confirmed.
- **Handoff:** ready for @system-arch to derive SAD and SFS from this PRD + MRD.
