# Research: Test Results Management API

## Example Data Analysis

**Decision**: Data model based on analysis of real Playwright and Cypress test results from Mattermost

**Rationale**:
- Playwright example shows hierarchical structure: config → suites → specs → tests → results
- Cypress example shows simpler structure: stats → results → suites → tests
- Both include timing, status, retry information, and metadata
- Playwright includes project/browser matrix testing (setup, ipad, chrome, firefox)
- Cypress includes UUID-based test identification and detailed test code

**Key Findings**:
- Playwright: 23 tests across multiple browsers, complex nested structure with attachments
- Cypress: 8 tests in single browser, flatter structure with rich metadata
- Both support tags/annotations for test categorization
- Duration tracking at multiple levels (test, suite, overall)
- Error information, retry counts, and execution context captured

**Alternatives considered**:
- Generic JSON schema: Misses framework-specific optimizations
- Single unified model: Loses framework-specific metadata richness

## Performance Requirements

**Decision**: 1000 requests/second, <200ms p95 response time, 100k test results/day capacity

**Rationale**:
- Modern CI/CD pipelines generate high-volume test data
- Multiple teams running concurrent test suites
- Need responsive API for dashboard/reporting queries
- FastAPI + PostgreSQL can handle this scale with proper indexing

**Alternatives considered**:
- Lower targets (100 req/s): Insufficient for enterprise CI/CD
- Higher targets (10k req/s): Over-engineering for initial release

## Data Retention Policy

**Decision**: 90-day retention with archive option, configurable per project

**Rationale**:
- Balance storage costs with debugging needs
- Most test failures analyzed within weeks
- Archive allows long-term trend analysis
- Configurable for different team needs

**Alternatives considered**:
- Indefinite retention: Storage cost concerns
- 30-day retention: Too short for some debugging scenarios
- Fixed policy: Doesn't accommodate different team needs

## Authentication & Authorization

**Decision**: JWT tokens with GitHub SSO, role-based access (admin/user/readonly)

**Rationale**:
- GitHub SSO integrates with existing dev workflow
- JWT stateless approach scales well
- Role-based access supports team permissions
- Aligns with provided technical requirements

**Alternatives considered**:
- API keys only: Less secure, no user identity
- OAuth with multiple providers: Added complexity for MVP
- Session-based auth: Doesn't scale as well

## Concurrent Usage & Scale

**Decision**: Support 50 concurrent users, 100k test results/day, 10GB storage/month

**Rationale**:
- Reasonable starting point for mid-size teams
- PostgreSQL connection pooling handles concurrency
- Monitoring will inform scaling decisions

**Alternatives considered**:
- Higher concurrency targets: Premature optimization
- Lower limits: May constrain adoption

## FastAPI + PostgreSQL Best Practices

**Decision**: Use SQLAlchemy 2.0 with async, Pydantic v2 models, connection pooling

**Rationale**:
- SQLAlchemy 2.0 async provides better performance
- Pydantic v2 offers improved validation and serialization
- Connection pooling essential for concurrent access
- Follows current FastAPI documentation patterns

**Alternatives considered**:
- SQLAlchemy 1.4: Older version, worse async support
- Raw SQL queries: More error-prone, harder to maintain
- Alternative ORMs: Less ecosystem support

## PostgreSQL Schema Design

**Decision**: Normalized schema with indexes on query fields, JSONB for extensible metadata

**Rationale**:
- Normalized design ensures data integrity
- Indexes on test_name, suite_id, status, created_at for common queries
- JSONB allows framework-specific metadata without schema changes
- Foreign key constraints maintain referential integrity

**Alternatives considered**:
- Document database: Less ACID guarantees
- Denormalized schema: Data duplication issues
- Pure JSON storage: Loses relational benefits

## Testing Framework Integration

**Decision**: Standardized JSON payload format with framework adapters

**Rationale**:
- Common interface simplifies API design
- Framework adapters handle format translation
- Easy to add new frameworks
- JSON is widely supported

**Alternatives considered**:
- Framework-specific endpoints: API proliferation
- Binary formats: Harder to debug and extend
- GraphQL: Added complexity for CRUD operations

## Error Handling & Validation

**Decision**: Pydantic validation with detailed error responses, structured error codes

**Rationale**:
- Pydantic provides comprehensive validation
- Detailed errors help client debugging
- Structured codes enable programmatic handling
- Follows REST API best practices

**Alternatives considered**:
- Simple HTTP codes only: Less informative
- Custom validation: More work, less reliable
- Minimal error details: Harder to debug

## File Storage Architecture

**Decision**: S3-compatible storage with MinIO for development, AWS S3 for production

**Rationale**:
- S3 API standard provides vendor flexibility
- MinIO enables local development without AWS dependency
- Cost-effective for large file storage (screenshots, videos, reports)
- Built-in redundancy and durability
- Scales independently from database storage

**Alternatives considered**:
- Local filesystem storage: No redundancy, scaling issues
- Database blob storage: Poor performance, expensive
- Other cloud providers: S3 API compatibility provides flexibility

## File Storage Strategy

**Decision**: Structured bucket organization with signed URLs for secure access

**Rationale**:
- Bucket per environment (dev/staging/prod) for isolation
- Organized by date and test suite for easy cleanup
- Signed URLs provide time-limited secure access
- Metadata stored in database, files referenced by key

**Alternatives considered**:
- Single bucket: Environment isolation issues
- Direct file serving: Security and bandwidth concerns
- Embedded file data: Database bloat and performance issues

## Storage Libraries & Integration

**Decision**: aioboto3 for async S3 operations, separate storage service library

**Rationale**:
- aioboto3 provides async S3 client for FastAPI compatibility
- Separate library enables testing with MinIO and prod with S3
- Consistent API regardless of backend storage
- Support for multipart uploads for large files

**Alternatives considered**:
- boto3 sync client: Blocking operations in async FastAPI
- Direct MinIO client: Vendor lock-in, different APIs
- Multiple storage backends: Added complexity

## Backup & Recovery

**Decision**: PostgreSQL WAL archiving + daily snapshots, S3 bucket versioning + lifecycle policies

**Rationale**:
- WAL archiving provides point-in-time recovery for database
- S3 versioning protects against accidental file deletion
- Lifecycle policies automatically manage retention and costs
- Cross-region replication for disaster recovery

**Alternatives considered**:
- Application-level backups: Less reliable
- No backup strategy: Unacceptable data loss risk
- Single-region storage: Disaster recovery risk

## GitHub Actions CI/CD Integration

**Decision**: Primary API usage through GitHub Actions workflows with bearer token authentication

**Rationale**:
- GitHub Actions is widely adopted for CI/CD in development teams
- Bearer tokens provide stateless, scalable authentication for automated systems
- Integration fits naturally into existing test automation workflows
- Supports both push-based (CI) and pull-based (scheduled) result submission

**Alternatives considered**:
- Jenkins integration: More complex setup, less standardized
- GitLab CI: Limited to GitLab users
- Manual API calls: Not scalable for automated testing

## Bearer Token Authentication Strategy

**Decision**: JWT bearer tokens with GitHub Actions secrets management

**Rationale**:
- JWT tokens can include scope and expiration for security
- GitHub Actions secrets provide secure token storage
- Stateless authentication scales better than session-based
- Supports both organization-level and repository-level tokens

**Alternatives considered**:
- API keys with basic auth: Less secure, no expiration
- GitHub App installation: More complex for simple use cases
- OAuth flows: Not suitable for automated systems

## CI/CD Integration Patterns

**Decision**: Multi-stage integration with test execution, result submission, and artifact upload

**Rationale**:
- Stage 1: Run tests and generate results JSON
- Stage 2: Submit test results to API with bearer token
- Stage 3: Upload artifacts (screenshots, videos) to S3 via API
- Stage 4: Optional notification/reporting based on results
- Supports both individual test runs and test matrix scenarios

**Alternatives considered**:
- Single-step submission: Less flexible for different test types
- Direct S3 upload: Bypasses API access control and tracking
- Webhook-based: Requires API to pull from external sources

## GitHub Actions Workflow Architecture

**Decision**: Reusable workflow components with standardized token usage

**Rationale**:
- Composite actions for test result submission
- Reusable workflows for common patterns (Playwright, Cypress)
- Standardized environment variables for API configuration
- Support for matrix builds (multiple browsers/environments)

**Alternatives considered**:
- Custom actions marketplace: Publishing overhead
- Shell scripts only: Less GitHub Actions integration
- Monolithic workflows: Harder to maintain and reuse