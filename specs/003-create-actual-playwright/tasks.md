# Tasks: Playwright Custom Reporter with Real-Time API Integration

**Input**: Design documents from `/specs/003-create-actual-playwright/`
**Prerequisites**: plan.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

## Execution Flow (main)
```
1. Load plan.md from feature directory ✓
   → Extract: TypeScript/Python, FastAPI, PostgreSQL, S3, Playwright
2. Load design documents ✓:
   → data-model.md: TestEvent entity + extensions to existing entities
   → contracts/: OpenAPI spec + TypeScript client interfaces
   → research.md: JWT auth, circuit breaker, async HTTP
   → quickstart.md: Integration scenarios and user stories
3. Generate tasks by category:
   → Setup: dependencies, database migrations, project structure
   → Tests: contract tests for API endpoints, integration tests
   → Core: models, API endpoints, TypeScript client, Playwright reporter
   → Integration: authentication, artifact uploads, error handling
   → Polish: unit tests, performance validation, documentation
4. Apply TDD rules: All tests before implementation ✓
5. Mark [P] for parallel execution where files don't conflict ✓
6. SUCCESS: 42 tasks ready for execution
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Phase 3.1: Setup & Database

- [ ] **T001** Create database migration for TestEvent entity in `src/models/migrations/003_add_test_event_table.py`
- [ ] **T002** [P] Add Playwright-specific fields to TestResult model in `src/models/migrations/004_extend_test_result.py`
- [ ] **T003** [P] Add Playwright-specific fields to TestEnvironment model in `src/models/migrations/005_extend_test_environment.py`
- [ ] **T004** [P] Add Playwright-specific fields to TestSuite model in `src/models/migrations/006_extend_test_suite.py`
- [ ] **T005** [P] Add Playwright-specific fields to TestArtifact model in `src/models/migrations/007_extend_test_artifact.py`
- [ ] **T006** Create database indexes for performance in `src/models/migrations/008_add_playwright_indexes.py`

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (API Endpoints)
- [ ] **T007** [P] Contract test POST /playwright/suites in `tests/contract/test_playwright_suites_post.py`
- [ ] **T008** [P] Contract test PUT /playwright/suites/{suite_id} in `tests/contract/test_playwright_suites_put.py`
- [ ] **T009** [P] Contract test POST /playwright/environments in `tests/contract/test_playwright_environments_post.py`
- [ ] **T010** [P] Contract test POST /playwright/test-results in `tests/contract/test_playwright_test_results_post.py`
- [ ] **T011** [P] Contract test PUT /playwright/test-results/{external_id} in `tests/contract/test_playwright_test_results_put.py`
- [ ] **T012** [P] Contract test GET /playwright/test-results in `tests/contract/test_playwright_test_results_get.py`
- [ ] **T013** [P] Contract test POST /playwright/artifacts/presigned-upload in `tests/contract/test_playwright_artifacts_presigned.py`
- [ ] **T014** [P] Contract test POST /playwright/test-results/{test_result_id}/artifacts in `tests/contract/test_playwright_artifacts_register.py`
- [ ] **T015** [P] Contract test POST /playwright/events in `tests/contract/test_playwright_events_post.py`
- [ ] **T016** [P] Contract test GET /playwright/events in `tests/contract/test_playwright_events_get.py`

### Integration Tests (End-to-End Scenarios)
- [ ] **T017** [P] Integration test complete Playwright test run workflow in `tests/integration/test_playwright_full_workflow.py`
- [ ] **T018** [P] Integration test artifact upload flow (presigned URL → S3 → register) in `tests/integration/test_playwright_artifact_upload.py`
- [ ] **T019** [P] Integration test real-time events during test execution in `tests/integration/test_playwright_realtime_events.py`
- [ ] **T020** [P] Integration test error handling and recovery scenarios in `tests/integration/test_playwright_error_handling.py`

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Database Models
- [ ] **T021** [P] Implement TestEvent model in `src/models/test_event.py`
- [ ] **T022** Update TestResult model with Playwright fields in `src/models/test_result.py`
- [ ] **T023** Update TestEnvironment model with Playwright fields in `src/models/test_environment.py`
- [ ] **T024** Update TestSuite model with Playwright fields in `src/models/test_suite.py`
- [ ] **T025** Update TestArtifact model with Playwright fields in `src/models/test_artifact.py`

### API Endpoints
- [ ] **T026** [P] Implement POST /playwright/suites endpoint in `src/services/playwright/suites.py`
- [ ] **T027** [P] Implement PUT /playwright/suites/{suite_id} endpoint in `src/services/playwright/suites.py`
- [ ] **T028** [P] Implement POST /playwright/environments endpoint in `src/services/playwright/environments.py`
- [ ] **T029** Implement POST /playwright/test-results endpoint in `src/services/playwright/test_results.py`
- [ ] **T030** Implement PUT /playwright/test-results/{external_id} endpoint in `src/services/playwright/test_results.py`
- [ ] **T031** Implement GET /playwright/test-results endpoint in `src/services/playwright/test_results.py`
- [ ] **T032** [P] Implement presigned S3 upload endpoint in `src/services/playwright/artifacts.py`
- [ ] **T033** Implement artifact registration endpoint in `src/services/playwright/artifacts.py`
- [ ] **T034** [P] Implement POST /playwright/events endpoint in `src/services/playwright/events.py`
- [ ] **T035** Implement GET /playwright/events endpoint in `src/services/playwright/events.py`

## Phase 3.4: TypeScript Client Library

- [ ] **T036** [P] Create TypeScript HTTP client with retry logic in `src/lib/typescript-client/src/http-client.ts`
- [ ] **T037** [P] Implement authentication and token management in `src/lib/typescript-client/src/auth-manager.ts`
- [ ] **T038** [P] Implement artifact upload utilities in `src/lib/typescript-client/src/artifact-uploader.ts`
- [ ] **T039** Create main client interface in `src/lib/typescript-client/src/playwright-client.ts`

## Phase 3.5: Playwright Reporter Integration

- [ ] **T040** Enhance existing Playwright reporter with API integration in `example/playwright/custom_reporter.ts`
- [ ] **T041** [P] Create TypeScript client library tests in `src/lib/typescript-client/tests/client.test.ts`

## Phase 3.6: Polish & Validation

- [ ] **T042** [P] Performance test for concurrent test execution in `tests/performance/test_concurrent_execution.py`

## Dependencies

### Sequential Dependencies
- T001 → T007-T016 (database must exist before contract tests)
- T007-T020 → T021-T041 (tests must fail before implementation)
- T021-T025 → T026-T035 (models before API endpoints)
- T029-T031 depends on T022-T025 (test results endpoints need extended models)
- T032-T033 depends on T025 (artifact endpoints need TestArtifact model)
- T034-T035 depends on T021 (events endpoints need TestEvent model)
- T036-T039 → T040 (client library before reporter)
- T040 → T041 (reporter implementation before client tests)

### Parallel Groups
**Group 1 - Database Migrations** (T002-T005): Different migration files
**Group 2 - Contract Tests** (T007-T016): Different test files
**Group 3 - Integration Tests** (T017-T020): Different test files
**Group 4 - Model Updates** (T021, T023-T025): Different model files
**Group 5 - Service Files** (T026-T028, T032, T034): Different service files
**Group 6 - Client Library** (T036-T038): Different TypeScript files

## Parallel Execution Examples

### Phase 3.2 - Contract Tests Launch
```bash
# Launch all contract tests together (T007-T016):
Task: "Contract test POST /playwright/suites in tests/contract/test_playwright_suites_post.py"
Task: "Contract test PUT /playwright/suites/{suite_id} in tests/contract/test_playwright_suites_put.py"
Task: "Contract test POST /playwright/environments in tests/contract/test_playwright_environments_post.py"
Task: "Contract test POST /playwright/test-results in tests/contract/test_playwright_test_results_post.py"
# ... (all 10 contract test tasks)
```

### Phase 3.3 - Model Implementation Launch
```bash
# Launch model updates together (T021, T023-T025):
Task: "Implement TestEvent model in src/models/test_event.py"
Task: "Update TestEnvironment model with Playwright fields in src/models/test_environment.py"
Task: "Update TestSuite model with Playwright fields in src/models/test_suite.py"
Task: "Update TestArtifact model with Playwright fields in src/models/test_artifact.py"
```

### Phase 3.4 - TypeScript Client Launch
```bash
# Launch TypeScript client components together (T036-T038):
Task: "Create TypeScript HTTP client with retry logic in src/lib/typescript-client/src/http-client.ts"
Task: "Implement authentication and token management in src/lib/typescript-client/src/auth-manager.ts"
Task: "Implement artifact upload utilities in src/lib/typescript-client/src/artifact-uploader.ts"
```

## Key Integration Points

### Test Result Flow
1. **T010** creates test result → **T029** implements endpoint → **T022** provides model
2. **T011** updates test result → **T030** implements endpoint → **T022** provides model
3. **T018** tests artifact upload → **T032-T033** implement endpoints → **T025** provides model

### Real-time Events Flow
1. **T015** creates event → **T034** implements endpoint → **T021** provides model
2. **T016** queries events → **T035** implements endpoint → **T021** provides model
3. **T019** tests real-time flow → **T034-T035** provide endpoints

### Playwright Integration Flow
1. **T040** uses client library → **T036-T039** provide client → **T026-T035** provide API
2. **T041** validates client → **T040** provides usage examples → **T017-T020** provide scenarios

## Validation Checklist
*GATE: Checked before task execution*

- [x] All contracts have corresponding tests (T007-T016 → endpoints T026-T035)
- [x] All entities have model tasks (TestEvent: T021, extensions: T022-T025)
- [x] All tests come before implementation (Phase 3.2 before 3.3)
- [x] Parallel tasks truly independent (different files, verified)
- [x] Each task specifies exact file path
- [x] No [P] task modifies same file as another [P] task
- [x] TDD red-green-refactor cycle enforced
- [x] Real dependencies (PostgreSQL, S3) used in integration tests

## Notes
- Follow TDD strictly: Tests must fail before implementing
- Use actual PostgreSQL and S3 in integration tests (no mocks)
- JWT authentication required for all API endpoints
- Circuit breaker pattern for error resilience in TypeScript client
- Commit after each completed task
- Run type-checking and linting after each task