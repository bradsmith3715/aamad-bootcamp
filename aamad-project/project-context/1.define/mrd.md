# Market Research Document (MRD) — Origin AI

**Persona:** @product-mgr
**Source idea:** project-context/0.idea/idea.md
**Date:** 2026-04-23
**Phase:** 1.define

---

## Executive Summary

**Market Opportunity.** Origin AI targets solo developers and indie hackers who start more projects than they finish, largely because the gap between a raw idea and an executable plan is high-friction. Adjacent categories — AI coding copilots (GitHub Copilot, Cursor), AI product/PM assistants (Notion AI, Linear, ChatPRD), and agentic dev tools (Devin, Replit Agent, Claude Code) — demonstrate sustained willingness-to-pay in the $10–$50/month range for individual-developer productivity. Origin AI occupies a narrow, defensible wedge upstream of coding assistants: **idea → validated scope → build plan**, before a line of code is written. Direct competitors exist (ChatPRD, PM-focused GPTs) but none appear to couple conversational discovery, MRD/PRD generation, tech-stack recommendation, and GitHub reference-repo surfacing into a single solo-dev-shaped workflow.

**Technical Feasibility.** The MVP is highly feasible on CrewAI. The core workflow is a bounded multi-agent crew of five: a discovery agent (Socratic Q&A), a synthesizer agent (MRD/PRD generation), a stack-recommender agent (matches scope to known archetypes), a repo-finder agent (GitHub search API), and a dedicated orchestrator agent that owns task sequencing, HITL gate enforcement, and Audit/Prompt-Trace capture. The runtime is a single Python service using **FastHTML + HTMX** — server-rendered UI and HTTP endpoints consolidated in one framework — backed by the **Claude API** (via CrewAI's LiteLLM layer with `anthropic/` model IDs) for all LLM calls. All required primitives are available today. Risks are deterministic-output quality, cost control on long conversations, and RAG freshness for stack recommendations, all mitigable with prompt design, caching, and token budgets.

**Recommended Approach.** Build an MVP that proves the single claim: *"From a paragraph of idea to a structured build plan in under 15 minutes, with traceable reasoning the user can edit."* Monetization and scale considerations are deferred. Success of the MVP is measured by task completion rate (user reaches a saved build plan), time-to-plan, and qualitative plan usefulness, not by MAU or revenue.

---

## 1. Market Analysis & Opportunity Assessment

### Key Insights
- **Solo-dev segment is large and underserved by planning tools.** Most planning/PM tools (Jira, Linear, Notion) are team-shaped; solo developers typically plan in notes apps or in their head, then lose scope discipline mid-build. Origin AI's wedge is "PM-in-a-box for one person."
- **AI-for-PM is an active, validated category.** ChatPRD, Notion AI, and Linear's AI features have demonstrated that LLMs can materially speed PRD drafting. Origin AI extends this from document generation to a guided end-to-end scoping workflow tailored to the *builder*, not the product manager.
- **Adjacent categories prove willingness-to-pay.** GitHub Copilot ($10–$19/mo), Cursor ($20/mo), ChatGPT Plus ($20/mo), Claude Pro ($20/mo), Replit Core (~$20/mo) form a well-established price band for individual-developer tools.
- **GitHub as reference-corpus is a real differentiator.** Surfacing "here are three repos that already do something like this" compresses the research loop that currently costs solo devs hours of Googling and README skimming.

### Data Points
- Addressable segment (order-of-magnitude estimate, *to validate*): the global developer population is commonly cited at ~28–30M (GitHub/Stack Overflow surveys); the share actively starting side projects is materially smaller, likely single-digit millions. [ASSUMPTION — see Open Questions.]
- Price-point anchors from adjacent tools: $10–$20/mo individual tier is the dominant pattern. [Public pricing pages of Copilot, Cursor, ChatGPT, Claude, as of 2026.]
- No known direct competitor unifies *conversational scoping + MRD/PRD gen + stack rec + repo discovery* in one flow. [ASSUMPTION — competitive scan pending.]

### Source Citations
- GitHub Copilot pricing — github.com/features/copilot (pricing, public).
- Cursor pricing — cursor.com (public).
- ChatPRD — chatprd.ai (public; closest direct analog for PRD-gen).
- Stack Overflow Developer Survey (most recent edition) — stackoverflow.co/developer-survey for developer-population baselines.
- GitHub Octoverse (most recent) — github.blog/octoverse.

*Citation target per template: 15–20 sources. Current document lists high-confidence anchors; remaining sources flagged in Open Questions pending a live market scan.*

### Implications
- Positioning should be "builder's co-pilot *before* the code," not "PM tool."
- Pricing for a future paid tier should anchor in the $10–$20/mo individual band; MVP is unpriced (validation-first).
- Competitive moat is not the LLM — it is the *workflow shape* (discovery → plan → references) and the quality of the build-plan artifact.

---

## 2. Technical Feasibility & Requirements Analysis

### Key Insights
- **CrewAI is a good fit.** The workflow decomposes cleanly into five single-responsibility agents (discovery, synthesizer, stack-recommender, repo-finder, orchestrator) with deterministic hand-offs; this is exactly the pattern CrewAI optimizes for.
- **Sequential process is sufficient for MVP.** Per adapter-crewai rules, prefer sequential for deterministic builds. Hierarchical/manager crews are unnecessary for MVP scope.
- **Tool surface is small.** Required tools: (a) web/GitHub search (for reference repos and stack facts), (b) structured file writer (for MRD/PRD/build-plan artifacts), (c) optional RAG over a curated stack-archetype corpus. All three are low-risk.
- **Determinism demands low temperature and strict expected_output schemas.** Temperature ≤ 0.4 per AAMAD rules; expected_output declares target path + required headings; guardrails validate structure before write.

### Data Points
- CrewAI supports sequential/hierarchical processes, YAML-externalized agent/task definitions, and tool binding — all requirements of AAMAD adapter-crewai rules.
- Token budget per full run (estimate): a 10-minute discovery conversation plus three artifact generations is tractable under 100K tokens total with a frontier model, comfortably within a $0.10–$0.50 per-session cost envelope depending on model. [ASSUMPTION — to instrument in MVP.]

### Source Citations
- CrewAI documentation — docs.crewai.com (framework capability confirmation).
- AAMAD adapter rules — `.claude/rules/adapter-crewai.md` (project-local contract).

### Implications
- Build the MVP as five agents (discovery, synthesizer, stack-recommender, repo-finder, orchestrator), all YAML-configured. The orchestrator is its own agent (not an inline deterministic task) so task sequencing, HITL gate handling, and Prompt-Trace/Audit capture are a single owned responsibility.
- Enforce `temperature ≤ 0.4`, `memory=False`, explicit tool whitelists per the adapter rules. Per adapter-crewai, `allow_delegation=False` for build personas; the orchestrator is the one role where delegation may be enabled, subject to @system-arch justification in the SAD.
- Treat GitHub search as the highest-risk external dependency (rate limits, API key management) and bind it only to the repo-finder agent.
- LLM calls use the Claude API (Anthropic) via CrewAI's native LiteLLM layer with the `anthropic/` model-ID prefix — no custom LLM wrapper required.

---

## 3. User Experience & Workflow Analysis

### Primary Persona: Solo Developer / Indie Hacker
- **Context:** 1–15 years coding experience, builds side projects on evenings/weekends, has more ideas than finished projects.
- **Pain:** Friction between "I have an idea" and "I have a plan I can start executing Saturday morning." Loses momentum in the gap.
- **Current workaround:** ChatGPT/Claude for ad-hoc brainstorming, unstructured notes, half-written READMEs.
- **Willingness to pay:** Aligned with the $10–$20/mo individual-dev tooling band once value is proven. MVP is free.

### User Journey (MVP)
1. User opens a chat UI and pastes/types a rough idea (1–3 sentences).
2. Discovery agent asks 5–10 clarifying questions (audience, core job-to-be-done, must-haves, non-goals, constraints).
3. Synthesizer produces an MRD + PRD draft, rendered in the UI and saved as artifacts the user can edit.
4. Stack-recommender proposes a concrete stack with rationale (e.g., "Next.js + Supabase because X, Y, Z").
5. Repo-finder surfaces 3–5 similar GitHub repos with a one-line "why this is relevant" for each.
6. User receives a consolidated build plan (milestones, first-week tasks) and can export/download.

### Interface Requirements (MVP)
- Single chat pane; streaming responses; saved-artifact sidebar.
- Human-in-the-loop at two gates: after discovery (approve scope before doc gen) and after doc gen (approve before stack/repo work).
- No auth, no persistence beyond session for MVP. [Deferred.]

### Success Metrics (MVP)
- **Task completion rate:** % of sessions that reach a saved build plan.
- **Time-to-plan:** median minutes from first message to build-plan delivery. Target: <15 min.
- **Qualitative usefulness:** post-session 1-question survey ("Could you start building from this plan?" Y/N) or manual review of N=20 plans.
- **Agent failure rate:** % of runs hitting a guardrail/Halt. Target: <5%.

### User Adoption Factors
- **Enablers:** fast time-to-value, editable artifacts (not a black box), references to real repos.
- **Barriers:** trust in AI-generated scope, perceived effort of a discovery conversation vs. just starting to code.

### Source Citations
- Stack Overflow Developer Survey — developer behavior and tool-adoption baselines.
- Indie Hackers (public forum) — qualitative signal on solo-dev pain points. [ASSUMPTION — pending structured scan.]

### Implications
- UX must make the discovery conversation feel *short and useful*, not like a form.
- Artifacts must be editable and exportable, or trust evaporates.
- Defer auth, multi-project management, collaboration for post-MVP.

---

## 4. Production & Operations Requirements

### Deployment Architecture (MVP)
- **Single Python service: FastHTML + HTMX.** FastHTML serves both the HTTP endpoints and server-rendered HTML pages; HTMX handles client-side interactivity (streaming updates, HITL gate approvals, artifact downloads) via partial-page swaps. This replaces the earlier two-service split (FastAPI backend + separate JS frontend) and eliminates the need for Next.js, assistant-ui, SSE plumbing, and a second runtime.
- Deploy target: any container host (Render, Fly.io, Railway, or local Docker for bootcamp).
- No database for MVP; session state in memory; artifacts written to a per-session directory on the container filesystem and downloadable via HTMX-served links.

### Monitoring & Observability
- Per AAMAD rules: log each agent/task lifecycle event, capture `CrewOutput.raw`, append Prompt Trace + Audit to artifacts.
- MVP observability: structured JSON logs to stdout; no external observability stack required.

### Security Considerations
- API keys (LLM provider, GitHub) loaded from env vars; `.env.example` required (per adapter-crewai rules).
- Input validation at API entry; sanitize user input embedded into agent prompts (prompt-injection mitigation already mandated by AAMAD rules).
- No PII handling in MVP; user ideas may be sensitive, so the retention policy is "do not persist beyond session" until an explicit persistence feature ships.

### Cost Structure (MVP, estimates)
- LLM: $0.10–$0.50 per completed session at current frontier-model pricing. [ASSUMPTION — to instrument.]
- Hosting: <$20/mo on a hobby tier.
- Development: within bootcamp timeline; no external headcount.

### Risk Assessment
- **Operational:** LLM provider outage or rate-limit → degrade gracefully with a clear user-facing error. Mitigation: retry with backoff (already specified in adapter rules, `max_retry_limit ≥ 2`).
- **Cost drift:** long conversations can blow token budgets. Mitigation: per-session token cap + early-termination guardrail.
- **Quality drift:** agents hallucinate stacks/repos that don't exist. Mitigation: GitHub repo-finder must verify repo existence via API before including; stack-recommender output is validated against a curated allow-list of archetypes for MVP.

### Source Citations
- AAMAD adapter-crewai rules — `.claude/rules/adapter-crewai.md`.
- Render / Fly.io / Railway pricing — public pricing pages.

### Implications
- MVP ops burden is negligible; this is not the constraint on project viability.
- Cost and quality guardrails must be wired from day one, not retrofitted.

---

## 5. Innovation & Differentiation Analysis

### Unique Value Propositions
- **Builder-shaped, not PM-shaped.** Output is a *build plan* with stack and references, not a stakeholder-ready PRD.
- **Traceable reasoning.** Every artifact section traces back to user answers from discovery; the user can see *why* a recommendation was made and edit the input that produced it.
- **Repo-grounded.** "Here are three real repos doing something similar" is a tangible differentiator over generic PRD-gen tools.

### Emerging Technologies
- Improvements in long-context, tool-using LLMs directly reduce Origin AI's engineering burden. The product rides the capability curve rather than fighting it.
- Agent frameworks (CrewAI, LangGraph, AutoGen) are maturing; Origin AI's adapter-abstracted design (per AAMAD) allows framework migration without persona rewrites.

### Patent Landscape
- No known blocking IP in "conversational PRD generation." [ASSUMPTION — full IP scan out of scope for MVP.]

### Future Trends
- Agentic dev tools (Devin, Replit Agent) are moving *downstream* of Origin AI (plan → code). A future integration is plausible: Origin AI hands a build plan to an agentic builder.
- Custom GPTs and Claude Projects partially commoditize document generation; Origin AI's defensibility is in the *workflow* and *repo grounding*, not raw LLM output.

### Partnership Opportunities
- GitHub (reference repos, eventual repo scaffolding).
- Agentic code-execution tools (hand-off target for the build plan).
- Hosting providers targeting indie devs (Fly, Render, Vercel) — co-marketing.

### Monetization Strategies (deferred; informational only)
- Free tier with N sessions/month; paid tier at $10–$20/mo for unlimited sessions and saved projects.
- Team tier only if/when multi-user demand is validated.

### Source Citations
- CrewAI, LangGraph, AutoGen documentation (public).
- Devin / Replit Agent public announcements.

### Implications
- Defensibility is workflow + data (repo corpus + curated stack archetypes), not the model.
- Design MVP so the plan-to-build hand-off (future partnership) is clean.

---

## Critical Decision Points

- **Go/No-Go Factors**
  - Can the crew reliably produce a usable build plan in <15 minutes for a realistic idea? (MVP validation target.)
  - Can GitHub repo recommendations be grounded and verifiable? (Quality gate for differentiation.)
  - Can per-session cost be held under $0.50? (Viability gate for a free tier.)
- **Technical Architecture Choices (user-confirmed 2026-04-23)**
  - Framework: CrewAI (confirmed; aligns with repo and AAMAD adapter rules).
  - Execution: sequential process, memory off, temperature ≤ 0.4.
  - Agents: 5 — discovery, synthesizer, stack-recommender, repo-finder, orchestrator.
  - Runtime stack: single Python service using **FastHTML + HTMX** (consolidates backend + server-rendered frontend; replaces the earlier FastAPI + Next.js/assistant-ui split).
  - LLM: **Claude API** (Anthropic) via CrewAI's LiteLLM layer with `anthropic/` model IDs.
  - No auth; no persistence in MVP.
- **Market Positioning**
  - "The fastest path from idea to build plan for solo developers." Not a PM tool. Not a coding copilot.
- **Resource Requirements**
  - One builder (the bootcamp student), bootcamp timeline, single repo.

---

## Risk Assessment Matrix

- **High Risk**
  - Output quality: incoherent or hallucinated plans erode trust instantly. Mitigation: guardrails, review gates, expected_output schemas.
  - GitHub repo grounding: fabricated repo links are a credibility killer. Mitigation: live API verification before inclusion.
- **Medium Risk**
  - Cost per session drift with long conversations. Mitigation: token caps + session timeouts.
  - Competitive encroachment by ChatPRD or Notion AI adding discovery flows. Mitigation: ship MVP and iterate on repo-grounding differentiator.
- **Low Risk**
  - Hosting/infra complexity (minimal for MVP).
  - Framework lock-in (mitigated by AAMAD adapter abstraction).

---

## Actionable Recommendations

- **Immediate Next Steps (≤48 hours)**
  - Hand this MRD to @system-arch for SAD derivation.
  - @product-mgr to draft PRD in `project-context/1.define/prd.md` building on the MVP scope defined here.
  - Resolve the Open Questions below that are cheap to close (pricing anchors, direct-competitor scan).
- **Short-term Priorities (30 days)**
  - Build MVP per SAD: 4-agent CrewAI crew + minimal chat frontend + artifact export.
  - Instrument task-completion rate, time-to-plan, per-session cost.
  - Run 10–20 internal user sessions with real ideas; capture qualitative feedback.
- **Long-term Strategy (6–12 months, informational only)**
  - Persistence and saved projects.
  - Paid tier with $10–$20/mo anchor pricing.
  - Hand-off integration with an agentic code-execution tool.

---

## Sources

- idea.md — `project-context/0.idea/idea.md` (primary input).
- AAMAD core rules — `.claude/rules/aamad-core.md`.
- AAMAD CrewAI adapter rules — `.claude/rules/adapter-crewai.md`.
- CrewAI documentation — docs.crewai.com.
- GitHub Copilot pricing — github.com/features/copilot.
- Cursor pricing — cursor.com.
- ChatPRD — chatprd.ai.
- Stack Overflow Developer Survey — stackoverflow.co/developer-survey.
- GitHub Octoverse — github.blog/octoverse.
- Render / Fly.io / Railway — public pricing pages.

*Live scan to expand to 15–20 cited sources pending (see Open Questions).*

---

## Assumptions

- Solo-developer TAM is single-digit millions; exact figure deferred to live market scan.
- No direct competitor unifies conversational discovery + MRD/PRD + stack rec + repo discovery in one flow; a structured competitive scan is pending.
- Per-session LLM cost of $0.10–$0.50 at current frontier-model pricing; to be instrumented in MVP.
- Target willingness-to-pay is in the $10–$20/mo individual-dev tool band; to be validated with user interviews post-MVP.
- GitHub public search API is sufficient for repo discovery at MVP volumes; rate-limit headroom to be verified.
- Users will tolerate a 5–10-question discovery conversation if it produces a useful artifact in <15 minutes.
- "Claude API" as used here means Anthropic Claude models invoked through CrewAI's native LiteLLM layer with the `anthropic/` model-ID prefix, NOT a direct `anthropic` SDK integration with a custom CrewAI LLM wrapper. Direct-SDK interpretation would require a materially different backend build.
- "FastHTML + HTMX replaces FastAPI" is interpreted as replacing both the FastAPI backend AND the separate Next.js/assistant-ui frontend selected in the earlier SAD draft — consolidating to a single Python service. A narrower interpretation (e.g., keep Next.js, only swap backend) would contradict the "frontend stack" framing and is not assumed.
- FastHTML's HTMX-driven streaming and partial-update patterns are expressive enough to replace the SSE + assistant-ui tool-renderer design for MVP artifact display. To be validated during @system-arch's SAD update.

---

## Open Questions

- What is the verified addressable market size for "solo developers who start side projects"? Source: Stack Overflow Survey + GitHub Octoverse cross-reference.
- Full competitive scan: ChatPRD, Notion AI (PRD mode), Linear AI, custom-GPTs marketplace — feature-by-feature matrix. Owner: @product-mgr.
- ~~Which LLM provider/model anchors MVP?~~ **Resolved 2026-04-23:** Claude API (Anthropic) via CrewAI/LiteLLM. Specific model IDs per agent (cheaper for A1 Discovery vs. frontier for A2 Synthesizer?) remains open for @system-arch / @backend-eng.
- Is there a curated stack-archetype corpus (e.g., public "awesome" lists) suitable for grounding the stack-recommender, or does it need to be authored in-repo?
- Pricing research gap: what do solo devs actually pay for PM-adjacent tools today (Notion, Linear personal tiers)? Survey needed.
- Post-MVP: does a plan-to-agentic-builder hand-off (Devin, Replit Agent, Claude Code) belong on the roadmap, or is it out of scope?
- **Orchestrator agent — delegation mode.** With 5 agents including a dedicated orchestrator, does the orchestrator use CrewAI hierarchical/manager mode (`allow_delegation=true` on it only) or does it run as a first-agent coordinator inside a still-sequential process? Owner: @system-arch — resolve in the SAD update.
- **FastHTML + HTMX feasibility for streaming.** Can FastHTML + HTMX deliver the streaming agent-output UX that assistant-ui + SSE gave the earlier design, without a materially worse user experience? Owner: @system-arch / @frontend-eng. Spike if uncertain.
- **Downstream cascade required.** This MRD update invalidates PRD §3 (4-agent decomposition) and SAD §§1–5 (two-service Next.js + FastAPI topology, ADR-1, ADR-2, ADR-5, ADR-7). @product-mgr to revise `prd.md`; @system-arch to revise `sad.md`. Tracking these as blocking before any Build-phase scaffolding.

---

## Audit

- **Timestamp:** 2026-04-23
- **Persona:** @product-mgr
- **Action:** authored initial MRD for Origin AI from idea.md
- **Inputs read:** `project-context/0.idea/idea.md`, `.cursor/templates/mr-template.md`, `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `AGENTS.md`, `.claude/agents/product-mgr.md`
- **Output:** `project-context/1.define/mrd.md` (this file)
- **Model / tooling:** authored via Claude Code main thread (model: claude-opus-4-7[1m]); no external web search performed in this pass — live market validation deferred to Open Questions.
- **Temperature / determinism:** N/A (single-pass authoring, not a crew run); crew runs for PRD/SAD will honor adapter-crewai rule of temperature ≤ 0.4.
- **Prohibited actions attempted:** none.
- **Template headings check:** Executive Summary, 5 Research Dimensions, Critical Decision Points, Risk Assessment Matrix, Actionable Recommendations, Sources, Assumptions, Open Questions, Audit — all present.
- **Handoff:** ready for @product-mgr to author PRD and for @system-arch to begin SAD derivation once PRD lands.

### Revision — 2026-04-23 (r2)

- **Timestamp:** 2026-04-23
- **Persona:** @product-mgr
- **Action:** revised MRD to incorporate three user-confirmed decisions: (1) LLM provider = Claude API via CrewAI/LiteLLM with `anthropic/` prefix; (2) crew expanded to 5 agents — discovery, synthesizer, stack-recommender, repo-finder, plus a dedicated orchestrator agent; (3) runtime stack consolidated to a single FastHTML + HTMX Python service, replacing the earlier two-service FastAPI + Next.js/assistant-ui topology.
- **Sections updated:** Executive Summary (Technical Feasibility paragraph); §2 Key Insights and Implications; §4 Deployment Architecture; Critical Decision Points (Technical Architecture Choices); Assumptions (added 3 decision-scoped assumptions); Open Questions (resolved LLM-provider question; added orchestrator-delegation, FastHTML-streaming-feasibility, and downstream-cascade items).
- **Interpretation choices made (flagged in Assumptions for downstream validation):**
  - "Claude API" read as the upstream provider name, reached via CrewAI's native LiteLLM layer — NOT a direct `anthropic` SDK integration. Matches SAD ADR-5.
  - "FastHTML + HTMX replacing FastAPI" read as consolidation of both the FastAPI backend AND the Next.js/assistant-ui frontend into one Python service. Narrower readings are not assumed.
- **Downstream impact (not applied in this pass — out of @product-mgr scope for an MRD update):**
  - `prd.md` §3 Technical Requirements & Architecture and §6 UX references to a chat-UI frontend need revision to reflect 5 agents and the FastHTML + HTMX stack.
  - `sad.md` Executive Summary, ADR-1 (FastAPI + Next.js split), ADR-2 (Next.js/assistant-ui/Tailwind), ADR-5 (LLM provider — reconfirm Claude API phrasing), ADR-6 (sequential vs. orchestrator-managed), ADR-7 (SSE transport — likely superseded by HTMX patterns), §3 Frontend Architecture, §4 Backend Architecture, §6 Data Flow, Views, and Traceability Matrix all need revision.
  - No Build-phase scaffolding should begin until the PRD and SAD are revised and re-approved.
- **Inputs read:** `project-context/1.define/mrd.md` (prior revision), `project-context/1.define/prd.md`, `project-context/1.define/sad.md`, `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/agents/product-mgr.md`.
- **Output:** `project-context/1.define/mrd.md` (this file, r2).
- **Model / tooling:** revised via Claude Code main thread (model: claude-opus-4-7[1m]).
- **Temperature / determinism:** N/A (single-pass authoring).
- **Prohibited actions attempted:** none. Original Audit entry preserved; revision appended per aamad-core append-only Audit convention.
- **Handoff:** @product-mgr to revise `prd.md`; @system-arch to revise `sad.md`. Both are blocking before @project-mgr scaffolds.
