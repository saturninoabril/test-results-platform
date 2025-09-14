# Tasks: Comprehensive Development and Production Makefile

**Input**: Design documents from `/specs/002-create-makefile-so/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   ✅ Found: tech stack (Python 3.13+, FastAPI, uv, Docker), structure (single project)
2. Load optional design documents:
   ✅ data-model.md: Extract Makefile target categories and dependencies
   ✅ contracts/: makefile-interface.md → contract test tasks for all targets
   ✅ research.md: Extract tool decisions → setup tasks
3. Generate tasks by category:
   ✅ Setup: Makefile structure, documentation, help system
   ✅ Tests: contract tests for each Makefile target
   ✅ Core: development, quality, build, container, database, utility commands
   ✅ Integration: workflow validation, CI/CD simulation
   ✅ Polish: documentation validation, performance tests
4. Apply task rules:
   ✅ Different targets = mark [P] for parallel
   ✅ Dependent targets = sequential (no [P])
   ✅ Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   ✅ All contract targets have tests
   ✅ All command categories implemented
   ✅ All workflow scenarios covered
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different targets, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `Makefile` at repository root, tests in `tests/`
- Paths assume single project structure per plan.md

## Phase 3.1: Setup
- [ ] T001 Create basic Makefile structure with .PHONY declarations and shell configuration
- [ ] T002 Implement help system with categorized target documentation in Makefile
- [ ] T003 [P] Create tests/makefile/ directory for contract tests

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T004 [P] Contract test make install in tests/makefile/test_install_target.py
- [ ] T005 [P] Contract test make upgrade in tests/makefile/test_upgrade_target.py
- [ ] T006 [P] Contract test make dev in tests/makefile/test_dev_target.py
- [ ] T007 [P] Contract test make type-check in tests/makefile/test_typecheck_target.py
- [ ] T008 [P] Contract test make lint in tests/makefile/test_lint_target.py
- [ ] T009 [P] Contract test make format in tests/makefile/test_format_target.py
- [ ] T010 [P] Contract test make test-unit in tests/makefile/test_unit_target.py
- [ ] T011 [P] Contract test make test-integration in tests/makefile/test_integration_target.py
- [ ] T012 [P] Contract test make test-contract in tests/makefile/test_contract_target.py
- [ ] T013 [P] Contract test make test-all in tests/makefile/test_all_target.py
- [ ] T014 [P] Contract test make build in tests/makefile/test_build_target.py
- [ ] T015 [P] Contract test make docker-build in tests/makefile/test_docker_build_target.py
- [ ] T016 [P] Contract test make docker-build-prod in tests/makefile/test_docker_prod_target.py
- [ ] T017 [P] Contract test make docker-publish in tests/makefile/test_docker_publish_target.py
- [ ] T018 [P] Contract test make db-upgrade in tests/makefile/test_db_upgrade_target.py
- [ ] T019 [P] Contract test make clean in tests/makefile/test_clean_target.py
- [ ] T020 [P] Contract test make help in tests/makefile/test_help_target.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)
### Development Commands
- [ ] T021 [P] Implement make install target with uv sync in Makefile
- [ ] T022 [P] Implement make upgrade target with uv lock --upgrade in Makefile
- [ ] T023 Implement make dev target with FastAPI server startup in Makefile

### Quality Assurance Commands
- [ ] T024 [P] Implement make type-check target with mypy/pyright in Makefile
- [ ] T025 [P] Implement make lint target with ruff in Makefile
- [ ] T026 [P] Implement make format target with code formatting in Makefile
- [ ] T027 Implement make test-unit target with pytest unit tests in Makefile
- [ ] T028 Implement make test-integration target with pytest integration tests in Makefile
- [ ] T029 Implement make test-contract target with contract validation in Makefile
- [ ] T030 Implement make test-all target combining all test suites in Makefile

### Build and Container Commands
- [ ] T031 Implement make build target for production artifacts in Makefile
- [ ] T032 [P] Implement make docker-build target for development image in Makefile
- [ ] T033 Implement make docker-build-prod target for production image in Makefile
- [ ] T034 Implement make docker-publish target for registry publishing in Makefile

### Database Commands
- [ ] T035 [P] Implement make db-upgrade target with alembic migrations in Makefile
- [ ] T036 [P] Implement make db-downgrade target with alembic rollback in Makefile
- [ ] T037 [P] Implement make db-reset target for development database in Makefile
- [ ] T038 [P] Implement make db-seed target for test data in Makefile

### Utility Commands
- [ ] T039 [P] Implement make clean target for Python cache cleanup in Makefile
- [ ] T040 [P] Implement make clean-docker target for container cleanup in Makefile
- [ ] T041 [P] Implement make clean-all target for complete cleanup in Makefile

## Phase 3.4: Integration
- [ ] T042 Integration test complete development workflow in tests/makefile/test_dev_workflow.py
- [ ] T043 Integration test CI/CD pipeline simulation in tests/makefile/test_cicd_workflow.py
- [ ] T044 Integration test error handling and recovery in tests/makefile/test_error_handling.py
- [ ] T045 Cross-platform compatibility validation in tests/makefile/test_cross_platform.py

## Phase 3.5: Polish
- [ ] T046 [P] Unit tests for Makefile helper functions in tests/unit/test_makefile_helpers.py
- [ ] T047 Performance benchmarking for key targets in tests/performance/test_makefile_performance.py
- [ ] T048 [P] Validate quickstart.md workflow accuracy in tests/integration/test_quickstart_validation.py
- [ ] T049 [P] Documentation completeness check in tests/makefile/test_documentation.py
- [ ] T050 Final integration test of complete Makefile functionality in tests/integration/test_complete_makefile.py

## Dependencies
- Setup (T001-T003) before everything
- Contract tests (T004-T020) before implementation (T021-T041)
- T021 (install) blocks T023 (dev), T027-T030 (all test targets)
- T022 (upgrade) can run parallel with other setup
- T023 (dev) depends on T021 (install) and database targets
- T027-T030 (test targets) depend on T021 (install)
- T031 (build) depends on quality targets (T024-T026, T027-T030)
- T033 (docker-prod) depends on T031 (build)
- T034 (docker-publish) depends on T033 (docker-prod) and T030 (test-all)
- T035-T038 (database) can run parallel with development commands
- Integration (T042-T045) before polish (T046-T050)

## Parallel Example
```
# Launch contract tests together (T004-T020):
Task: "Contract test make install in tests/makefile/test_install_target.py"
Task: "Contract test make upgrade in tests/makefile/test_upgrade_target.py"
Task: "Contract test make type-check in tests/makefile/test_typecheck_target.py"
Task: "Contract test make lint in tests/makefile/test_lint_target.py"

# Launch independent implementation tasks (T021, T022, T024, T025):
Task: "Implement make install target with uv sync in Makefile"
Task: "Implement make upgrade target with uv lock --upgrade in Makefile"
Task: "Implement make type-check target with mypy/pyright in Makefile"
Task: "Implement make lint target with ruff in Makefile"
```

## Notes
- [P] tasks = different targets or independent files, no dependencies
- Verify contract tests fail before implementing targets
- Each target must return appropriate exit codes per contract specification
- Commit after each task completion
- Follow TDD: red (failing test) → green (implementation) → refactor

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   ✅ Each Makefile target → contract test task [P]
   ✅ Each target → implementation task with dependencies

2. **From Data Model**:
   ✅ Target categories → grouped implementation tasks
   ✅ Dependencies → sequential task ordering

3. **From User Stories** (quickstart.md):
   ✅ Development workflow → integration test scenarios
   ✅ CI/CD workflow → pipeline simulation tests

4. **Ordering**:
   ✅ Setup → Tests → Implementation → Integration → Polish
   ✅ Dependencies prevent parallel execution where needed

## Validation Checklist
*GATE: Checked by main() before returning*

- [x] All contract targets have corresponding tests (T004-T020)
- [x] All targets have implementation tasks (T021-T041)
- [x] All tests come before implementation (Phase 3.2 → 3.3)
- [x] Parallel tasks truly independent (different targets/files)
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task (Makefile is single file, properly sequenced)
- [x] Integration scenarios cover quickstart workflows (T042-T045)
- [x] TDD approach enforced with failing tests first