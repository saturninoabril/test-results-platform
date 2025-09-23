# Implementation Plan: Playwright Custom Reporter with Real-Time API Integration


**Branch**: `003-create-actual-playwright` | **Date**: 2025-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-create-actual-playwright/spec.md`

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
Implement a Playwright custom reporter that integrates with the Test Results Platform API to provide real-time test result submission. The system will capture test start events, completion events with status, and upload test artifacts (screenshots, videos, traces) as tests execute. A TypeScript client library will be created to handle secure API communication, with the API enhanced to accommodate Playwright-specific test data structures.

## Technical Context
**Language/Version**: TypeScript/JavaScript (Node.js) for Playwright reporter, Python 3.13+ for API backend
**Primary Dependencies**: @playwright/test (reporter interface), FastAPI (backend), aioboto3 (S3 storage), SQLAlchemy (ORM)
**Storage**: PostgreSQL 17 for test metadata, S3-compatible storage (MinIO dev/AWS S3 prod) for artifacts
**Testing**: pytest for backend, Playwright built-in testing for reporter integration
**Target Platform**: CI/CD environments (GitHub Actions, Jenkins, etc.), cross-platform Node.js
**Project Type**: single (extending existing test-results-platform)
**Performance Goals**: Real-time submission (<100ms per event), handle 1000+ concurrent test executions
**Constraints**: Must not block test execution if API fails, secure authentication, backward compatible
**Scale/Scope**: Support large test suites (1000+ tests), multiple concurrent CI pipelines, artifact files up to 50MB each

**Additional Context from User**: Example Playwright test can be found at example/playwright/ folder where custom_reporter.ts can be found. Create a Typescript client of the Test Results Platform so that saving of test results and status can be handled easily. Modify the API to accommodate Playwright-specific test report data and shape. Use of client should be in a secure manner.

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 1 (extending existing test-results-platform) ✓
- Using framework directly? Yes (FastAPI, Playwright native APIs) ✓
- Single data model? Yes (extending existing entities, adding TestEvent) ✓
- Avoiding patterns? Yes (no Repository/UoW, direct SQLAlchemy) ✓

**Architecture**:
- EVERY feature as library? Yes (typescript-client library, playwright-reporter library) ✓
- Libraries listed:
  - `typescript-client`: HTTP client for Test Results Platform API with authentication, retry logic, artifact uploads
  - `playwright-reporter`: Playwright reporter implementation with real-time API integration
- CLI per library: Yes (planned for client library with --help/--version/--format) ✓
- Library docs: llms.txt format planned in Phase 1 ✓

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? Yes (contract tests written first, must fail) ✓
- Git commits show tests before implementation? Yes (TDD approach mandated) ✓
- Order: Contract→Integration→E2E→Unit strictly followed? Yes ✓
- Real dependencies used? Yes (actual PostgreSQL, S3, real API calls) ✓
- Integration tests for: new libraries, contract changes, shared schemas? Yes ✓
- FORBIDDEN: Implementation before test, skipping RED phase ✓

**Observability**:
- Structured logging included? Yes (JSON logging in both client and reporter) ✓
- Frontend logs → backend? Yes (reporter logs sent as TestEvents) ✓
- Error context sufficient? Yes (detailed error types, stack traces, recovery context) ✓

**Versioning**:
- Version number assigned? Yes (feature branch 003, follows MAJOR.MINOR.BUILD) ✓
- BUILD increments on every change? Yes (planned in task execution) ✓
- Breaking changes handled? Yes (backward compatible API extensions) ✓

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

**Structure Decision**: [DEFAULT to Option 1 unless Technical Context indicates web/mobile app]

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
- API contract endpoints → contract test tasks [P]
- Data model extensions → database migration and model update tasks [P]
- TypeScript client library → client implementation and tests [P]
- Playwright reporter integration → reporter implementation and tests
- Integration scenarios from quickstart → end-to-end integration tests

**Specific Task Categories**:
1. **Database & Models** (Parallel execution):
   - Create TestEvent entity model
   - Add Playwright-specific fields to existing entities (TestResult, TestEnvironment, TestSuite, TestArtifact)
   - Create database migrations for new fields and TestEvent table
   - Add database indexes for performance

2. **API Extensions** (Sequential after database):
   - Implement Playwright-specific API endpoints (/playwright/*)
   - Add authentication middleware for JWT tokens
   - Implement presigned S3 URL generation for artifact uploads
   - Add real-time event endpoints

3. **TypeScript Client Library** (Parallel with API):
   - Implement HTTP client with retry logic and circuit breaker
   - Implement authentication and token management
   - Implement artifact upload flow (presigned URLs + S3 upload + registration)
   - Implement error handling and resilience patterns

4. **Playwright Reporter** (After client library):
   - Enhance existing custom_reporter.ts with real-time API integration
   - Implement lifecycle event handlers (onBegin, onTestBegin, onTestEnd, onEnd)
   - Implement artifact detection and upload logic
   - Add configuration management and error handling

5. **Testing & Integration** (After implementation):
   - Contract tests for all new API endpoints
   - Integration tests with real PostgreSQL and S3
   - Playwright test suite that uses the custom reporter
   - Performance tests for concurrent test execution scenarios

**Ordering Strategy**:
- TDD order: Contract tests → Implementation → Integration tests
- Dependency order: Database → API → Client → Reporter → Integration
- Mark [P] for parallel execution where dependencies allow
- Include performance and security testing throughout

**Estimated Output**: 35-40 numbered, ordered tasks focusing on TDD approach and real-world integration

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
- [ ] Complexity deviations documented

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*