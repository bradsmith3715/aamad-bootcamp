# AAMAD Agent Framework

This project uses the AAMAD framework for multi-agent development.
See the full agent definitions in the IDE-specific directories.

## Agent Personas
- **@product-mgr** — Product Manager: Orchestrates product vision and requirements
- **@system.arch** — System Architect: Produces SAD and SFS documents
- **@project.mgr** — Project Manager: Scaffolds project and environment
- **@frontend.eng** — Frontend Developer: Builds MVP chat interface
- **@backend.eng** — Backend Developer: Builds CrewAI backend
- **@integration.eng** — Integration Engineer: Connects frontend and backend
- **@qa.eng** — QA Engineer: Validates MVP functionality

## Workflow
1. **Define** (Phase 1): @product-mgr → Market Research → PRD → @system.arch → SAD
2. **Build** (Phase 2): @project.mgr → @frontend.eng / @backend.eng → @integration.eng → @qa.eng
3. **Deliver** (Phase 3): DevOps deployment

## Rules
All development follows AAMAD core rules. See project-context/ for artifacts.

## Agent Definitions
See `.cursor/agents/` for Cursor agent definitions.
