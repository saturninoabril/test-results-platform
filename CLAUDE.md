# Claude Code Context

## Current Feature: Test Results Management API

**Language**: Python 3.13+
**Framework**: FastAPI
**Database**: PostgreSQL 17 with SQLAlchemy
**Storage**: S3-compatible (MinIO dev, AWS S3 prod) for test artifacts
**Authentication**: JWT with GitHub SSO
**Testing**: pytest, pytest-asyncio, pytest-minio

## Recent Changes
- Feature 002: Comprehensive Development and Production Makefile specification and planning completed
- Added standardized command interface for all development workflows (type-check, test, build, deploy)
- Integrated uv dependency management with upgrade capabilities
- Designed multi-stage Docker builds and container publishing workflow
- Established TDD approach for Makefile target validation with contract tests
- Feature 001: Test Results Management API specification completed with S3 storage, real examples, and CI/CD integration
- Created data model with 5 core entities based on real Playwright and Cypress test result analysis
- Enhanced TestResult entity with tags, external_id, full_title fields from real examples

## Project Structure
```
src/
├── models/          # SQLAlchemy models
├── services/        # Business logic libraries
├── cli/            # Command-line interfaces
└── lib/            # Shared utilities

tests/
├── contract/       # Contract tests
├── integration/    # Integration tests
└── unit/          # Unit tests
```

## Libraries
- **test-results**: CRUD operations for test data management
- **auth**: JWT + GitHub OAuth authentication handling
- **database**: SQLAlchemy models and connection management
- **storage**: S3-compatible file storage operations with aioboto3

## Key Requirements
- TDD approach: tests written first, must fail before implementation
- Library-first architecture: every feature as standalone library
- Real dependencies in tests: actual PostgreSQL, no mocks
- Structured JSON logging for observability
- Performance target: <200ms p95 response time, 1000 req/s capacity
- Primary integration: GitHub Actions CI/CD pipelines with bearer token authentication
- Automation token management with scoped permissions and expiration

## Data Model Entities
- TestFramework: name, version, metadata (supports Playwright 1.55.0, Cypress 7.2.0, extensible)
- TestEnvironment: name, browser, os, metadata (execution context)
- TestSuite: groups test results, tracks counts and duration
- TestResult: enhanced with tags, external_id, full_title based on real test examples
- TestArtifact: screenshots, videos, reports, logs stored in S3 with metadata

## Example Data Sources
- resource/playwright-test-results.json: 23 tests across 4 projects (setup, ipad, chrome, firefox)
- resource/cypress-test-results.json: 8 accessibility tests with detailed metadata
- Real test data from Mattermost E2E test suite used for schema validation

## CI/CD Integration
- Bearer token authentication for automated systems
- GitHub Actions workflow examples for Playwright and Cypress
- Reusable actions for test result submission
- Matrix build support for multiple browsers/environments
- Artifact upload integration (screenshots, videos, reports)

## Next Phase
Ready for /tasks command to generate implementation tasks following TDD principles with CI/CD integration support.