# Product Requirements Document (PRD)
## Recruitment Assistant — Candidate-Side, Tech Roles

| Field | Value |
|---|---|
| **Product** | Recruitment Assistant — multi-agent candidate-side tool |
| **Framework** | CrewAI (sequential crew) |
| **Primary user** | Job seekers pursuing tech roles (engineering, data, PM, design) |
| **Context** | AAMAD bootcamp learning artifact |
| **Upstream artifact** | `project-context/1.define/mrd.md` |
| **Author** | @product-mgr |
| **Status** | Draft — pending handoff to @system-arch |

---

## 1. Executive Summary

### Problem Statement *(from MRD §2.1, §2.3)*
Tech job seekers face a high-volume, low-signal application funnel:
- Application volumes have risen sharply while response rates stay low; typical interview conversion sits in the low single digits.
- Existing candidate tools split into two camps: **keyword matchers** (no reasoning) and **black-box AI scorers** (no explanation). Neither tells the candidate *why* a role ranks where it does or *what to change*.
- The result: candidates spray applications, can't prioritize, and get no feedback loop.

### Solution Overview
A CrewAI multi-agent assistant that, for a given resume and career-intent prompt:
1. **Discovers** live open tech roles from permitted sources.
2. **Ranks** each role against the candidate's resume with per-criterion reasoning.
3. **Explains** each ranking — matched, partial, missing criteria, visible by default.
4. **Suggests** evidence-grounded resume edits and labeled skill-gap remediations.
5. **Tailors** a resume variant for a selected role once the candidate accepts suggestions.

**Unique value proposition**: *"Every score has a why."* Explainability is not a setting — it is the surface.

### Strategic Rationale
- **Why multi-agent**: the workflow decomposes cleanly into four cooperating specialists (Sourcing, Parser, Ranking, Coach) with structured handoffs. A single-prompt approach would conflate extraction, scoring, and coaching and lose explainability.
- **Why now**: schema-constrained LLM output and mature agent frameworks (CrewAI) make structured, auditable agent pipelines tractable in a bootcamp timeframe.
- **Bootcamp success criterion**: a demonstrably-working four-agent crew with a visible explainability surface, not a commercial launch.

---

## 2. Market Context & User Analysis

### Target Market
**Primary persona — "Mid-funnel tech seeker"**
- Early-career to mid-career IC (0–8 yrs experience), pursuing software, data, PM, or design roles.
- Applies to 10–100+ roles across a job search; uses 2–5 tools in parallel (LinkedIn, Indeed, a tracker, a resume builder, ChatGPT).
- Pain: volume without signal. Can't tell which roles are worth tailoring for.
- Values: transparency, control, time saved on tailoring, credible feedback on resume quality.

**Secondary persona — "Career switcher"**
- Transitioning into tech from adjacent field or via bootcamp.
- Acute pain on resume framing and skill-gap awareness.
- Highest marginal value from the Coach agent.

### User Needs *(from MRD §2.3)*
| Need | Current state | This product addresses via |
|---|---|---|
| Find relevant roles fast | Infinite-scroll boards, weak filters | Sourcing agent + Ranker prioritization |
| Understand fit before applying | Opaque "match" scores | Per-criterion explainability drawer |
| Know what to change | Generic resume tips | Coach agent grounded in candidate's own resume |
| Not fabricate experience | AI rewrites that invent skills | Coach `evidence` field + skill-gap labeling |
| Stay in control | Black-box automation | Human-in-the-loop on every Coach edit |

### Competitive Landscape *(from MRD §2.5)*
| Tool | Discovery | Ranking | Coaching | Explainability |
|---|---|---|---|---|
| LinkedIn / Indeed | Strong | Implicit / opaque | None | None |
| Teal, Huntr, Simplify | Aggregation | Keyword match | Templates | Minimal |
| ChatGPT (ad-hoc) | Weak | Good reasoning | Ungrounded | Conversational |
| **This assistant** | Focused | Multi-criteria, structured | Evidence-grounded, labeled | Per-criterion, per-role |

Price benchmarks (directional, post-bootcamp only): Teal $9–29/mo, LinkedIn Premium $30–60/mo. The bootcamp MVP has no pricing model.

---

## 3. Technical Requirements & Architecture

### CrewAI Framework Specifications
- **Crew type**: sequential crew with four agents.
- **Orchestration**: Sourcing → Parser → Ranking → Coach. No loops; no agent-to-agent delegation beyond the prescribed handoff.
- **I/O contract**: every agent produces JSON that conforms to a declared schema. The next agent consumes that schema, not free-form text.
- **Shared context**: session-scoped memory holding the parsed resume, the list of parsed JDs, and accumulated rankings. No persistence across sessions in the MVP.

### Core Agent Definitions

```yaml
agent: sourcing_agent
role: "Tech-role sourcer"
goal: "Return a normalized list of 10–25 live, relevant tech job postings given a resume summary and career-intent prompt."
backstory: "You specialize in navigating permitted public job feeds and a seeded demo corpus. You never scrape sources that disallow it."
tools: [job_feed_fetcher, demo_corpus_reader]
memory: session
delegation: false
output_schema: JobList  # [{id, title, company, location, url, raw_description, source}]
```

```yaml
agent: parser_agent
role: "Structured requirement extractor"
goal: "Convert free-form JDs and the candidate's resume into strict structured records (skills, seniority, requirements, evidence spans)."
backstory: "You are a precision extractor. You prefer 'unknown' over inventing a value."
tools: [llm_structured_extract]
memory: session
delegation: false
output_schema: ParsedJob, ParsedResume  # skills[], must_have[], nice_to_have[], seniority, years_experience, evidence_spans[]
```

```yaml
agent: ranking_agent
role: "Multi-criteria fit ranker"
goal: "For each parsed JD, produce a per-criterion fit breakdown (matched / partial / missing) and an overall score with reasoning."
backstory: "You never collapse reasoning into a single number. The breakdown is the product."
tools: [llm_structured_rank]
memory: session
delegation: false
output_schema: RankedJob  # {job_id, overall_score, criteria:[{name, status, evidence_in_resume, required_in_jd, notes}]}
```

```yaml
agent: coach_agent
role: "Evidence-grounded resume coach"
goal: "Propose resume edits and skill-gap advice for a selected ranked role. Every suggestion carries an evidence field pointing to existing resume content, or is explicitly labeled as a gap."
backstory: "You never invent experience. If the candidate does not have a skill, you say so; you do not write it into the resume."
tools: [llm_structured_coach]
memory: session
delegation: false
output_schema: CoachPlan  # {edits:[{target_section, suggested_text, evidence_span}], gaps:[{skill, learn_path_hint}]}
```

### Integration Requirements
| Area | MVP | Notes |
|---|---|---|
| Job sources | 1 permitted live feed + seeded demo corpus of 10–25 JDs | ToS-safe only; no LinkedIn/Indeed scraping |
| LLM | Single provider behind a thin abstraction | Abstraction enables later provider swaps |
| Resume ingest | Paste text or upload `.txt` / `.md` | PDF parsing deferred post-MVP |
| Storage | In-memory session state | No DB in MVP |
| Auth | None | Single-session, no accounts |

### Infrastructure Specifications
- **Deployment**: single container (backend) + static web frontend; local or single-VM cloud host sufficient for the bootcamp demo.
- **Compute**: sized for 1–5 concurrent sessions. No autoscaling required.
- **Networking**: HTTPS for frontend; LLM and job-feed calls egress only.
- **Logging**: structured logs of every agent call (prompt, response, latency, session id) — these logs *are* the audit trail.
- **Monitoring**: minimal (process up/down + LLM error rate). Out of scope: APM, tracing.

---

## 4. Functional Requirements

### P0 — Core (MVP must-ship)

**F-1: Resume + intent intake**
- *User story*: As a tech job seeker, I can paste my resume and describe the kind of role I want, so the assistant can start working.
- *Acceptance criteria*:
  - Resume accepted as pasted text (min 200 chars) or uploaded `.txt`/`.md` file (≤ 200 KB).
  - Career-intent prompt accepted as free text (max 500 chars).
  - On submit, UI shows a progress indicator while the crew runs.
  - Input validation errors (empty resume, oversize file) display inline, no crash.

**F-2: Role discovery**
- *User story*: As a candidate, I get a shortlist of real open tech roles relevant to my resume and intent.
- *Acceptance criteria*:
  - Sourcing agent returns 10–25 roles from permitted sources + seeded corpus.
  - Each role has: title, company, location, source, URL, raw JD text.
  - No role is scraped from a disallowed source (enforced by allowlist).
  - If sourcing fails, UI shows a clear error and falls back to the demo corpus.

**F-3: Structured parsing**
- *User story*: As a candidate, I trust that the system understands my resume and each JD consistently.
- *Acceptance criteria*:
  - Parser returns a `ParsedJob` for every role and one `ParsedResume` per session.
  - Schema fields: skills, must-haves, nice-to-haves, seniority, years of experience, evidence spans.
  - Parse failures are caught; the role is retained with a `parse_status: degraded` flag rather than dropped silently.

**F-4: Multi-criterion ranking with explainability**
- *User story*: As a candidate, I can see exactly which JD criteria I matched, partially matched, or missed for each role.
- *Acceptance criteria*:
  - Ranker returns a `RankedJob` per role with `overall_score` and a `criteria[]` list.
  - Each criterion carries: name, status (matched / partial / missing), `required_in_jd` snippet, `evidence_in_resume` snippet (or null if missing), short notes.
  - UI renders a per-role explainability drawer showing the criteria list by default — not behind a click.
  - Shortlist is sorted by overall score, ties broken deterministically.

**F-5: Evidence-grounded coaching**
- *User story*: As a candidate, I get concrete suggestions to improve my resume for a selected role, with clear labeling of what I'd need to learn vs. what I already have.
- *Acceptance criteria*:
  - Coach output separates `edits[]` (rewording existing resume content) from `gaps[]` (skills the candidate lacks).
  - Every `edits[]` item has a non-null `evidence_span` pointing to existing resume text.
  - `gaps[]` items are never auto-inserted into resume edits.
  - QA eval: on a 10-pair resume/JD eval set, zero Coach suggestions invent unlabeled experience.

**F-6: Resume tailoring on accept**
- *User story*: As a candidate, I can accept specific Coach suggestions and receive a tailored resume variant for one selected role.
- *Acceptance criteria*:
  - Candidate selects one ranked role, then accepts/rejects individual Coach `edits[]`.
  - Tailored resume is produced only from accepted edits; rejected edits are ignored.
  - Candidate can copy or download the tailored resume as `.md`.
  - Original resume is never overwritten in session state.

**F-7: Chat-shell UI with explainability drawer**
- *User story*: As a candidate, I interact with the assistant in a conversational interface and see ranked roles as structured cards.
- *Acceptance criteria*:
  - Chat input + message log per AAMAD `@frontend-eng` scope.
  - Ranked roles render as cards with score, title, company.
  - Clicking a card opens the explainability drawer (criteria breakdown + Coach plan).
  - Responsive on desktop widths; mobile polish deferred.

### P1 — Enhanced (post-MVP, within bootcamp if time)
- **F-8**: PDF resume ingest.
- **F-9**: Save/restore session (add minimal persistence).
- **F-10**: Multiple tailored resume exports (one per selected role in the session).
- **F-11**: Application-tracker export (CSV of accepted roles).

### P2 — Future (out of scope for bootcamp)
- **F-12**: Skill-gap learning plan (Coach recommends courses/projects for gaps).
- **F-13**: Interview prep agent (role-specific question generator).
- **F-14**: Expanded sources via partner APIs.
- **F-15**: Authenticated accounts and application history.

---

## 5. Non-Functional Requirements

### Performance
- End-to-end session (resume in → ranked shortlist rendered): ≤ 90 seconds for 15 roles on MVP hardware.
- Coach plan for a selected role: ≤ 20 seconds.
- Tailored resume generation on accept: ≤ 15 seconds.
- Frontend TTI: ≤ 3 seconds on desktop Chrome over broadband.

### Reliability
- MVP target: session completion rate ≥ 90% (crew runs to Coach stage without unrecoverable error).
- Graceful degradation: any single agent failure displays a meaningful error and retains partial progress where possible.
- Uptime targets do not apply — this is a bootcamp demo, not a 24/7 service.

### Security & Privacy
- Resumes are PII. In MVP:
  - Resume text is held only in session memory; not persisted to disk or DB.
  - Resume text is sent to the LLM provider as part of prompts — disclose this in a visible privacy note on the input screen.
  - No third-party sharing; no analytics on resume content.
- No authentication in MVP.
- HTTPS for frontend; secrets (LLM keys) managed via environment variables, never in repo.

### Compliance
- Candidate-side tools sit outside most hiring-decision regulations (EEOC, NYC AEDT, EU AI Act — these govern employer decision systems). Document this distinction explicitly so it's auditable.

### Scalability
- Not a concern for MVP. Single-digit concurrent sessions target. Post-bootcamp scaling is a future-phase topic.

---

## 6. User Experience Design

### Interface Requirements
- Chat-first shell with structured output regions (role cards, explainability drawer).
- Single-page flow; no multi-step wizard.
- Accessibility: semantic HTML, keyboard navigable, sufficient contrast. WCAG AA as a directional target, not a gate for the bootcamp demo.

### Agent Interaction Design
- **Transparency default**: criteria breakdown visible by default on the ranked role card. Collapsing is opt-in.
- **Feedback affordances**: candidate can accept/reject Coach edits individually; rejection is one click and reversible within the session.
- **Error handling**: every agent failure produces a human-readable message in the chat log with a retry affordance. No silent failures.
- **Explainability as product surface**, not a debug panel: written in candidate-friendly language, not internal agent jargon.

### Core User Journey
1. Candidate lands on the chat shell.
2. Pastes resume + types career-intent prompt → submits.
3. Progress indicator; crew runs (Sourcing → Parser → Ranking).
4. Ranked role cards appear, sorted by fit score.
5. Candidate opens a role → explainability drawer shows criteria breakdown + (on demand) a Coach plan.
6. Candidate accepts some Coach edits → taps "Tailor resume" → receives tailored variant.
7. Candidate copies/exports the tailored resume and exits to apply via the role's native link.

---

## 7. Success Metrics & KPIs

### Bootcamp / Product Metrics *(primary for this context)*
| Metric | Target | Measured how |
|---|---|---|
| Shortlist relevance ("worth a look" rate) | ≥ 60% | User rating in demo sessions |
| Explainability clarity (user can articulate rank order) | ≥ 90% | Qualitative check in demo sessions |
| Coach suggestion acceptance rate | ≥ 30% | Accept/reject log |
| Hallucinated experience incidents (unlabeled) | 0 | QA eval + manual review |
| End-to-end session time | ≤ 5 min | Instrumented timings |

### Technical Metrics
- JD parsing schema validity rate: ≥ 95% on eval set.
- Ranker criterion coverage: ≥ 90% of JD must-haves appear as ranked criteria.
- Crew run success rate: ≥ 90%.
- Median end-to-end latency: ≤ 90 s for 15 roles.

### Business Metrics
*Not applicable to the bootcamp MVP.* For a future commercial phase: activation rate, D7/D30 retention, paid-conversion on freemium gating — deferred.

---

## 8. Implementation Strategy

### Phase 1 — MVP (bootcamp scope)
- Four-agent CrewAI backend (Sourcing, Parser, Ranking, Coach) with strict JSON schemas.
- Next.js chat shell with role cards and explainability drawer (@frontend-eng).
- One permitted live source + seeded 10–25 JD demo corpus.
- JD-parsing eval set (≥ 20 hand-labeled JDs) and Coach-grounding eval (≥ 10 resume/JD pairs).
- Logging of every agent call as an audit trail.

### Phase 2 — Enhanced (post-MVP)
- PDF resume ingest.
- Session persistence.
- Multi-role tailoring.
- Tracker export.

### Phase 3 — Scale (out of bootcamp scope)
- Skill-gap learning plans.
- Interview prep agent.
- Expanded data partnerships.
- Accounts, history, analytics.

### Resource Requirements *(bootcamp)*
- AAMAD personas per `AGENTS.md`:
  - @system-arch: SAD + SFS.
  - @project-mgr: scaffold, dependencies, env setup.
  - @backend-eng: CrewAI agents and endpoints.
  - @frontend-eng: chat shell, cards, drawer.
  - @integration-eng: wire frontend ↔ backend.
  - @qa-eng: parsing and grounding evals, smoke tests.

### Risk Mitigation *(carried from MRD §4)*
| Risk | Mitigation |
|---|---|
| Data access / ToS | Permitted sources + seeded demo corpus; allowlist enforced in code |
| Hallucinated resume experience | Coach grounding rule, required `evidence_span`, no-invent eval in QA |
| JD parse variance | Schema-constrained output, eval set, `parse_status: degraded` fallback |
| LLM cost / latency | Cache JD parses per session; parse once, rank many |
| Candidate trust | Explainability-by-default UI (the feature *is* the mitigation) |

---

## 9. Launch & Go-to-Market Strategy

*This is a bootcamp learning artifact. Commercial GTM depth is intentionally light per MRD §2.1 scope note.*

### Demo & Review Plan *(replaces beta for bootcamp)*
- **Audience**: bootcamp cohort / reviewers.
- **Scenario 1 (happy path)**: early-career backend engineer resume + intent → shortlist + explainability + one tailored resume.
- **Scenario 2 (career switcher)**: bootcamp grad resume + intent → demonstrates Coach gap labeling without invention.
- **Scenario 3 (degradation)**: forced sourcing failure → demo corpus fallback and honest error messaging.

### Future Market Launch *(post-bootcamp, directional)*
- Freemium B2C: 3 ranks/day free, ~$10/mo paid tier for unlimited and tailored-exports.
- B2B2C secondary: career-services at universities and bootcamps.
- Positioning anchor: *"The assistant that explains every match."*

### Success Criteria for Bootcamp Delivery
- All P0 features pass acceptance criteria.
- JD-parsing and Coach-grounding evals meet thresholds.
- Demo runs end-to-end on all three scenarios without manual intervention.
- MRD → PRD → SAD → code traceability is intact and reviewable.

---

## 10. Quality Assurance Checklist

- [x] All requirements traceable to MRD findings (MRD section references inline throughout).
- [x] Technical specifications feasible with CrewAI (sequential crew, structured I/O).
- [x] Success metrics aligned with bootcamp objectives (clarity, grounding, end-to-end completion).
- [x] Resource requirements match AAMAD persona roster.
- [x] Risk mitigations carried through from MRD with concrete controls.
- [ ] Timeline milestones — to be set by @project-mgr during scaffold.
- [ ] SAD handoff — pending @system-arch.

---

## 11. Handoff Notes for @system-arch

Key decisions already locked in this PRD that the SAD should preserve:
1. **Sequential four-agent crew**: Sourcing → Parser → Ranking → Coach. No agent-to-agent delegation beyond this chain in MVP.
2. **Schema-constrained I/O between agents**: `JobList`, `ParsedJob`, `ParsedResume`, `RankedJob`, `CoachPlan`. These schemas are the interface contracts.
3. **Explainability is a first-class UI surface**, not a debug panel — the `criteria[]` breakdown produced by the Ranker renders directly to the candidate.
4. **Coach grounding rule**: every edit requires an `evidence_span`; gaps are separate and never auto-inserted into edits.
5. **No persistence in MVP**: session-scoped memory only; resume PII never touches disk.
6. **Data source allowlist**: ToS-safe permitted feeds + seeded demo corpus only.

SAD should produce: component diagram, agent task definitions, schema definitions, sequence diagram for the main happy path, and per-feature SFS documents for the P0 features above.

---

*Artifact path: `project-context/1.define/prd.md`*
*Upstream: `project-context/1.define/mrd.md`*
*Next artifact: SAD by @system-arch in `project-context/1.define/` (path per system-arch persona spec).*
