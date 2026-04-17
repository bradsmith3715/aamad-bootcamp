# Market Requirements Document (MRD)
## Recruitment Assistant — Candidate-Side, Tech Roles

| Field | Value |
|---|---|
| **Product concept** | Multi-agent Recruitment Assistant that discovers open tech positions for a candidate, ranks the candidate's resume against each role with transparent reasoning, and offers targeted improvement suggestions. |
| **Framework** | CrewAI (multi-agent orchestration) |
| **Primary user** | Job seekers pursuing software / tech roles (engineering, data, PM, design) |
| **Key differentiator** | Explainable ranking — every fit score, rejection, and recommendation is traceable to specific JD criteria and resume evidence. |
| **Context** | AAMAD bootcamp learning artifact. Figures below are directional and flagged where primary-source validation would be required for commercial use. |
| **Author** | @product-mgr |
| **Status** | Draft — pending handoff to @system-arch |

---

## 1. Executive Summary

### Market Opportunity
Job seekers in tech navigate a fragmented, opaque application funnel. They apply to dozens of roles through ATS portals, receive no feedback on ~95% of applications, and lack visibility into *why* their resume ranks poorly for a given JD. The candidate-side tooling market (resume builders, application trackers, job aggregators) is large and crowded, but existing tools are either **dumb keyword matchers** (no reasoning) or **black-box AI scorers** (no explanation). A multi-agent assistant that separates *discovery*, *ranking*, and *coaching* into specialized agents — each surfacing its reasoning — fills a real gap: candidates get actionable, explainable feedback instead of a mystery score.

### Technical Feasibility
CrewAI is well-suited to this workflow. The problem decomposes cleanly into four cooperating agents: a **Sourcing Agent** (queries job boards / aggregator APIs), a **Parser Agent** (extracts structured skills and requirements from JD + resume), a **Ranking Agent** (scores fit with chain-of-thought reasoning), and a **Coach Agent** (proposes resume edits and skill-gap remediations). All components rely on mature building blocks: LLM-based extraction, job-board APIs (or RSS/scraping fallbacks for MVP), and vector similarity for initial candidate/JD matching. No novel research required; primary risks are **data access** (most job boards restrict scraping) and **hallucination in coaching suggestions**.

### Recommended Approach
Build an MVP that accepts a resume + career-intent prompt, returns a ranked shortlist of 10–25 live roles from permitted sources (e.g., public RSS feeds, GitHub Jobs-style open sources, or a seeded test corpus for the bootcamp), and produces a per-role explainability panel showing matched criteria, gaps, and concrete resume-edit suggestions. Defer candidate outreach, interview prep, and ATS write-back to post-MVP. Prioritize **explainability UI** as the product's signature — it is cheap to implement on top of structured agent output and directly addresses the category's biggest pain point.

---

## 2. Detailed Findings by Dimension

### 2.1 Market Analysis & Opportunity Assessment

**Key Insights**
1. **Candidate-side tooling is crowded at the top of funnel, sparse in the middle.** Resume builders (Resume.io, Zety), trackers (Teal, Huntr, Simplify), and aggregators (LinkedIn, Indeed, Wellfound) dominate, but few tools connect discovery → ranking → coaching as one coherent loop.
2. **Tech job seekers are both the most demanding and most tool-tolerant segment.** Structured JDs, public skill taxonomies (e.g., stackshare, O*NET), and rich candidate signal (GitHub, Stack Overflow) make this segment the easiest technical wedge.
3. **Willingness-to-pay is moderate but real.** Products like Teal ($9–29/mo) and LinkedIn Premium ($30–60/mo) demonstrate candidates will pay for funnel clarity — but price ceiling is low vs. B2B recruiting tools.
4. **Macro tailwind: volume has exploded, signal has not.** Post-2023 tech layoffs and "easy apply" features have pushed application volumes up sharply; candidates need *filtering and prioritization*, not more listings.

**Data Points** *(directional — validate before commercial use)*
- Global online recruitment market: reported in the tens of billions USD with high-single-digit CAGR in several analyst reports.
- LinkedIn, Indeed, and Glassdoor together reach the majority of US tech job seekers.
- Typical application-to-interview conversion in tech is often cited in the low single digits, implying large unrealized "good fit" matches lost to poor targeting.

**Source categories for validation**
- Analyst reports: Gartner HR Tech, IDC, Grand View Research (recruitment software sizing).
- Candidate-behavior surveys: LinkedIn Workforce Reports, Glassdoor research, Jobvite Recruiter Nation.
- Product-pricing scans: public pricing pages of Teal, Huntr, Simplify, LinkedIn Premium.

**Implications**
- Target segment: tech job seekers, ICs at all levels, with initial focus on early-career and career-switchers (highest pain with resume framing).
- Positioning: *"The assistant that explains every match"* — lean hard into transparency as the wedge.
- Monetization is secondary for the bootcamp MVP; for post-bootcamp, freemium with paid explainability depth / unlimited ranks is the obvious shape.

---

### 2.2 Technical Feasibility & Requirements Analysis

**Key Insights**
1. **CrewAI fits the workflow shape.** The problem is naturally a sequential crew: Sourcing → Parsing → Ranking → Coaching, with the Ranking agent consuming structured output from Parser and the Coach consuming structured output from Ranker. Minimal branching; easy to reason about.
2. **Ranking quality hinges on JD/resume normalization, not on LLM choice.** Extracting *structured* requirement lists ("must have: 3+ yrs Python", "nice to have: Kubernetes") from free-form JDs is the hardest subproblem. This should be its own agent with strict JSON-schema output.
3. **Data access is the real constraint, not AI capability.** LinkedIn, Indeed, and most major boards prohibit scraping. MVP must rely on permitted sources: public RSS feeds (e.g., Hacker News "Who is hiring", some job boards), official APIs where available, or a seeded demo corpus for the bootcamp.
4. **Hallucination risk lives in the Coach agent.** Resume suggestions that invent experience the candidate doesn't have are a product-integrity hazard. Coach agent must ground every suggestion in evidence from the existing resume or explicitly label suggestions as "skill gaps you'd need to acquire."

**Architecture pattern (candidate for SAD handoff)**
- **Sourcing Agent** — given career-intent prompt + resume summary, queries permitted job sources, returns normalized JD records.
- **Parser Agent** — extracts structured skills, seniority, requirements from each JD and from the resume.
- **Ranking Agent** — computes a multi-criteria fit score per role with per-criterion reasoning (matched / partial / missing).
- **Coach Agent** — for each top-ranked role, produces evidence-grounded resume tweaks and labeled skill-gap advice.
- **Explainability view** — UI surfaces the criterion-level breakdown the Ranker produces. No new computation needed.

**Integrations (MVP)**
- Job source: 1–2 public/permitted feeds plus a seeded corpus for reproducible demos.
- LLM: single provider (e.g., OpenAI or Anthropic) behind a thin abstraction for later swap-out.
- Storage: lightweight (SQLite or a flat JSON store) — this is a bootcamp MVP, not a production service.

**Technical risks**
- Data access restrictions (High) — mitigate with permitted sources + demo corpus.
- JD parsing accuracy (Medium) — mitigate with strict schema + eval harness.
- Coaching hallucination (Medium) — mitigate with grounding rules in the Coach prompt and an evidence field in every suggestion.
- LLM cost per candidate session (Low–Medium for MVP) — cache JD parses; parse once, rank many.

---

### 2.3 User Experience & Workflow Analysis

**Primary user journey**
1. Candidate uploads or pastes resume, describes target role/seniority/location in a short prompt.
2. Assistant returns a ranked shortlist of live roles with an at-a-glance fit score.
3. Candidate opens a role → sees an explainability panel: matched criteria, partial matches, gaps, and Coach suggestions.
4. Candidate accepts one or more Coach suggestions → assistant produces a tailored resume variant for that role.
5. Candidate exports / copies the tailored resume and applies through the role's native link.

**Interface requirements**
- Chat-first MVP shell (aligns with AAMAD frontend scope) with structured cards for each ranked role.
- Per-role explainability drawer — non-negotiable, this *is* the differentiator.
- Minimal state: no account system for MVP; single-session in-memory flow is acceptable for the bootcamp.

**Automation vs. human-in-the-loop**
- Fully automated: sourcing, parsing, initial ranking, coach suggestion generation.
- Human-in-the-loop: candidate must review and accept Coach edits before any "tailored resume" is produced. Never auto-rewrite without explicit acceptance.

**Success metrics (MVP)**
| Metric | Target for MVP demo |
|---|---|
| Shortlist relevance (% of returned roles the candidate rates "worth a look") | ≥ 60% |
| Explainability clarity (candidate can articulate why role X ranked above role Y) | ≥ 90% of sessions |
| Coach suggestion acceptance rate | ≥ 30% of surfaced suggestions |
| Hallucinated-experience incidents (Coach suggests a skill not in resume, unlabeled) | 0 |
| End-to-end session time (resume in → tailored resume out) | ≤ 5 minutes |

**Adoption factors**
- **Enablers**: concrete reasoning, tailored output, no login friction.
- **Barriers**: candidate skepticism of AI scoring (addressed directly by explainability), resume-privacy concerns, fear of "AI-written" resumes being penalized by employers (addressed by keeping human-in-the-loop on every edit).

---

### 2.4 Production & Operations Requirements

*(Scoped lightly — this MRD is for a bootcamp MVP. Included for completeness and handoff traceability.)*

- **Deployment**: single-container web app; local or single-VM cloud host is sufficient for the bootcamp demo.
- **Observability**: log every agent call, prompt, and response with a session ID. This doubles as the explainability audit trail.
- **Security**: resumes contain PII. For the bootcamp, resumes stay in-session and are not persisted to disk beyond the active session; no third-party sharing. Document this explicitly in the PRD.
- **Compliance**: candidate-side tools sit outside most hiring-regulation scope (EEOC, NYC AEDT, EU AI Act target employer decision-making). Still, note the distinction in the PRD so it's auditable.
- **Cost**: LLM spend dominates; cache JD parses and bound per-session calls.
- **Operational risks**: rate-limiting from job sources, LLM provider outages. Both are acceptable for a demo MVP; handle with graceful degradation.

---

### 2.5 Innovation & Differentiation Analysis

**Unique value proposition**
*"Every score has a why."* Candidates see, per role, exactly which JD criteria they matched, partially matched, or missed — and get evidence-grounded advice on how to close the gap. No other category tool combines multi-agent sourcing + ranking + coaching behind a single explainable surface.

**Comparison to existing tools**
| Tool | Discovery | Ranking | Coaching | Explainability |
|---|---|---|---|---|
| LinkedIn | Strong | Implicit / opaque | None | None |
| Teal, Huntr | Aggregation only | Keyword match | Resume templates | Minimal |
| ChatGPT (ad-hoc) | Weak (no live data) | Good reasoning | Good but ungrounded | Conversational only |
| **This assistant (proposed)** | Focused / permitted sources | Multi-criteria, structured | Evidence-grounded, labeled | Per-criterion, per-role |

**Emerging-technology alignment**
- Structured LLM output (JSON-mode, schema-constrained generation) makes the Parser and Ranker far more reliable than a year ago.
- Agent frameworks (CrewAI, LangGraph) have matured to the point where the orchestration is table-stakes, not research.
- The bottleneck moves to **prompt engineering and evaluation harnesses**, which is tractable in a bootcamp timeframe.

**Monetization (post-bootcamp, non-binding)**
- Freemium: 3 ranks/day free, unlimited on a ~$10/mo tier.
- Paid add-ons: tailored resume exports in multiple formats, skill-gap learning plans, history.
- B2B2C: career-services licensing for universities and bootcamps is a plausible secondary channel.

---

## 3. Critical Decision Points

### Go / No-Go Factors
| Factor | Status |
|---|---|
| Can we source live job data from permitted sources for the demo? | **Go** — RSS feeds + demo corpus cover the MVP. |
| Can we produce structured JD parses with acceptable accuracy? | **Go** — mature LLM capability, bounded scope. |
| Can we ground Coach suggestions to prevent hallucinated experience? | **Go, conditional** — requires a grounding rule in the Coach prompt and a no-invent eval. |
| Is the MVP buildable in bootcamp timeline? | **Go** — scope is aggressive but tractable given the four-agent decomposition. |

### Architecture choices to pass to @system-arch
- **Framework**: CrewAI, sequential crew with four agents.
- **Data access**: seeded demo corpus + 1 permitted live source for the MVP.
- **LLM layer**: single provider behind a thin abstraction.
- **Frontend**: Next.js chat shell per AAMAD @frontend-eng scope, with structured role cards + explainability drawer.
- **Persistence**: minimal / session-scoped for the bootcamp.

### Market positioning
- Segment: tech job seekers, skewed toward early-career and career-switchers.
- Wedge: explainability.
- Competitive flank: avoid head-on LinkedIn/Indeed replication; pair with them as upstream sources where permitted.

### Resource / scope implications
- 4 agent definitions + 1 orchestrator for backend.
- 1 chat shell + 1 role-card + 1 explainability drawer for frontend.
- 1 JD-parsing eval set (≥ 20 hand-labeled JDs recommended) for QA.
- 1 coaching-grounding eval (≥ 10 resume/JD pairs, check for invented skills).

---

## 4. Risk Assessment Matrix

### High Risk
- **Data access / ToS violations.** Scraping LinkedIn, Indeed, etc. is out of scope. *Mitigation*: restrict MVP to permitted sources + seeded corpus; document this constraint visibly.
- **Hallucinated resume experience.** If the Coach agent suggests skills the candidate doesn't have without labeling them as gaps, the product is worse than useless. *Mitigation*: strict grounding rule + `evidence` field required in every suggestion; eval harness to catch regressions.

### Medium Risk
- **JD parsing variance.** Poorly parsed JDs produce bad rankings. *Mitigation*: schema-constrained output, eval set, fallback to simpler keyword extraction on parse failure.
- **LLM cost drift.** Per-session call counts can balloon. *Mitigation*: cache JD parses; one parse → many ranks.
- **Candidate trust in AI ranking.** Skepticism kills adoption. *Mitigation*: the explainability UI *is* the mitigation — make reasoning visible by default, not behind a click.

### Low Risk
- **LLM provider outage.** Acceptable failure mode for a demo; show graceful error.
- **UX polish.** Bootcamp MVP can ship rough; explainability correctness matters more than visual polish.

---

## 5. Actionable Recommendations

### Immediate Next Steps (48 hours)
1. **Review & approve this MRD** — confirm the candidate-side scope, tech-role focus, and explainability wedge are correct.
2. **Author the PRD** (@product-mgr next output) — translate MRD insights into feature-level requirements, user stories, and acceptance criteria.
3. **Identify the MVP data source** — pick one permitted live feed + seed a small demo corpus (10–25 JDs spanning junior → senior tech roles).

### Short-term Priorities (MVP build)
1. **@system-arch** produces SAD from this MRD + the forthcoming PRD.
2. **@project-mgr** scaffolds the CrewAI backend + Next.js frontend skeleton.
3. **@backend-eng** implements Sourcing, Parser, Ranking, Coach agents with schema-constrained I/O.
4. **@frontend-eng** implements chat shell, role-card list, and explainability drawer.
5. **@integration-eng** wires chat → backend crew → structured response.
6. **@qa-eng** builds JD-parsing eval + coaching-grounding eval.

### Longer-term (post-bootcamp, directional)
- Expand permitted data sources; explore partnerships with job boards that offer APIs.
- Add application-tracker integration (export to Teal/Huntr/Notion).
- Add a skill-gap learning plan (Coach agent recommends courses / projects).
- Explore university / bootcamp career-services as a B2B2C channel.

---

## 6. Handoff Checklist

- [x] Target user confirmed: job seekers, tech roles.
- [x] Differentiator confirmed: explainable multi-criteria ranking and grounded coaching.
- [x] MVP core loop defined: discover → rank → explain → suggest → tailor.
- [x] High/medium risks documented with mitigations.
- [x] Four-agent architecture proposed for @system-arch.
- [ ] PRD authored (next @product-mgr deliverable).
- [ ] MVP data source selected + demo corpus seeded.
- [ ] SAD handoff to @system-arch.

---

*Artifact path: `project-context/1.define/market-research.md`*
*Next artifact: `project-context/1.define/product-requirements-document.md`*
*Downstream owners: @system-arch (SAD), then @project-mgr for scaffold.*
