# Implementation Plan: Comprehensive Development and Production Makefile

**Branch**: `002-create-makefile-so` | **Date**: 2025-09-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-create-makefile-so/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, or `GEMINI.md` for Gemini CLI).
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Create a comprehensive Makefile that provides standardized commands for all common development and production tasks including type checking, testing, building, container publishing, and dependency management. The Makefile will serve as a centralized command interface for developers and CI/CD systems, incorporating user-specified requirements for dependency upgrade commands.

## Technical Context
**Language/Version**: Python 3.13+ (FastAPI application)
**Primary Dependencies**: FastAPI, SQLAlchemy, PostgreSQL, Docker, uv (dependency management)
**Storage**: PostgreSQL 17 with alembic migrations, MinIO/S3 for artifacts
**Testing**: pytest, pytest-asyncio, pytest-minio (real dependencies, no mocks)
**Target Platform**: Linux containers (Docker), development on multiple platforms
**Project Type**: Single project (API server with CLI tools)
**Performance Goals**: <200ms p95 response time, 1000 req/s capacity
**Constraints**: TDD approach mandatory, library-first architecture, real dependencies in tests
**Scale/Scope**: Test results management platform, CI/CD integration, containerized deployment
**User Requirements**: Use Makefile for all commands, include dependency upgrading commands

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 1 (single project - Makefile automation tool)
- Using framework directly? (Yes - Make tool directly, no wrapper layers)
- Single data model? (N/A - Makefile is infrastructure, not data model)
- Avoiding patterns? (Yes - direct command execution, no complex patterns)

**Architecture**:
- EVERY feature as library? (N/A - Makefile is infrastructure tooling)
- Libraries listed: N/A (Makefile targets, not libraries)
- CLI per library: N/A (Makefile provides CLI interface)
- Library docs: N/A (Makefile documentation via targets)

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? (Yes - test Makefile targets fail first)
- Git commits show tests before implementation? (Yes - test execution before target implementation)
- Order: Contract→Integration→E2E→Unit strictly followed? (Yes - contract tests for target interfaces)
- Real dependencies used? (Yes - actual tools: uv, docker, pytest, etc.)
- Integration tests for: Makefile target execution, command combinations
- FORBIDDEN: Implementation before test, skipping RED phase

**Observability**:
- Structured logging included? (Yes - proper output formatting in targets)
- Frontend logs → backend? (N/A - infrastructure tooling)
- Error context sufficient? (Yes - error handling in Makefile targets)

**Versioning**:
- Version number assigned? (N/A - Makefile is part of project versioning)
- BUILD increments on every change? (Follows project versioning)
- Breaking changes handled? (Yes - backward compatibility for existing targets)

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 1 (Single project) - Makefile goes in repository root

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `/scripts/bash/update-agent-context.sh claude` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each Makefile target → contract test task [P]
- Each command category → implementation task [P]
- Each user scenario from quickstart → integration test task
- Validation tasks to ensure targets work correctly

**Specific Task Categories**:
1. **Contract Tests** (Parallel execution possible):
   - Test each Makefile target exists and responds correctly
   - Verify exit codes for success/failure scenarios
   - Validate output format and error handling

2. **Core Makefile Implementation**:
   - Basic Makefile structure with help system
   - Development commands (install, upgrade, dev)
   - Quality assurance commands (type-check, lint, format, test-*)
   - Build and container commands
   - Database management commands
   - Utility commands (clean, help)

3. **Integration Tests**:
   - Complete development workflow validation
   - CI/CD pipeline simulation
   - Cross-platform compatibility verification
   - Error recovery testing

4. **Documentation and Validation**:
   - Quickstart guide validation
   - Help text accuracy verification
   - Performance benchmarking for key commands

**Ordering Strategy**:
- TDD order: Contract tests → Implementation → Integration tests
- Dependency order: Basic structure → Core commands → Advanced features
- Mark [P] for parallel execution (independent target groups)
- Validation tasks run after implementation completion

**Estimated Output**: 18-22 numbered, ordered tasks in tasks.md

**Key Dependencies**:
- Contract tests must fail before implementation
- Integration tests require working Makefile targets
- Documentation validation requires completed quickstart guide

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (N/A - no deviations)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*