# Data Model: Test Results Management API

## Core Entities

### Test Framework
Represents testing tools and their versions.

**Fields**:
- `id`: UUID, primary key
- `name`: String (e.g., "playwright", "cypress"), unique
- `version`: String (e.g., "1.55.0", "7.2.0")
- `metadata`: JSONB (framework-specific configuration)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Validation Rules**:
- name: required, lowercase, alphanumeric with hyphens
- version: required, semantic version format
- metadata: optional, valid JSON

**Example Metadata**:
- Playwright: `{"actualWorkers": 1, "projects": ["setup", "ipad", "chrome", "firefox"]}`
- Cypress: `{"mocha": {"version": "7.2.0"}, "platform": "linux", "browser": "electron", "headless": true}`

### Test Environment
Captures execution context and configuration.

**Fields**:
- `id`: UUID, primary key
- `name`: String (e.g., "staging", "production")
- `browser`: String (e.g., "chromium", "firefox")
- `os`: String (e.g., "ubuntu-22.04", "macos-13")
- `metadata`: JSONB (environment-specific details)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Validation Rules**:
- name: required, 1-100 characters
- browser: optional, from predefined list
- os: optional, from predefined list
- metadata: optional, valid JSON

### Test Suite
Groups test results from a single execution run.

**Fields**:
- `id`: UUID, primary key
- `name`: String (test suite name)
- `total_tests`: Integer (count of tests in suite)
- `passed_tests`: Integer (count of passed tests)
- `failed_tests`: Integer (count of failed tests)
- `skipped_tests`: Integer (count of skipped tests)
- `duration_ms`: Integer (total execution time)
- `started_at`: Timestamp (suite execution start)
- `completed_at`: Timestamp (suite execution end)
- `metadata`: JSONB (suite-specific data)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Validation Rules**:
- name: required, 1-200 characters
- framework_id: required, must exist
- environment_id: required, must exist
- total_tests: required, >= 0
- passed_tests + failed_tests + skipped_tests = total_tests
- duration_ms: required, >= 0
- started_at: required
- completed_at: required, >= started_at

**Relationships**:
- has_many: test_results

### Test Result
Individual test execution outcome.

**Fields**:
- `id`: UUID, primary key
- `suite_id`: UUID, foreign key to test_suites
- `test_name`: String (name/path of the test)
- `full_title`: String (complete test path with suite hierarchy)
- `status`: Enum ("passed", "failed", "skipped", "pending")
- `duration_ms`: Integer (test execution time)
- `error_message`: Text (failure details, nullable)
- `stack_trace`: Text (error stack trace, nullable)
- `retry_count`: Integer (number of retries, default 0)
- `tags`: JSON Array (test tags/annotations)
- `external_id`: String (framework-specific test ID, nullable)
- `metadata`: JSONB (test-specific data)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Validation Rules**:
- suite_id: required, must exist
- test_name: required, 1-500 characters
- full_title: required, 1-1000 characters
- status: required, one of allowed values
- duration_ms: required, >= 0
- retry_count: >= 0
- tags: array of strings, max 20 tags
- external_id: optional, framework-specific format
- metadata: optional, valid JSON

**Example Data**:
- Playwright: `test_name: "manages focus when opening and closing settings modal with keyboard"`, `tags: ["accessibility", "settings"]`, `external_id: "c27dc2d4fd7579bfae82-84088ebe5b793a8b0db8"`
- Cypress: `test_name: "MM-T1470 Verify Tab Support in Channels section"`, `full_title: "Verify Accessibility Support in Channel Sidebar Navigation MM-T1470 Verify Tab Support in Channels section"`, `external_id: "c8554ed9-b1f8-4b8b-8b40-e8e9486095e3"`

**Relationships**:
- belongs_to: test_suite
- has_many: test_artifacts

### Test Artifact
Files associated with test execution (screenshots, videos, reports).

**Fields**:
- `id`: UUID, primary key
- `result_id`: UUID, foreign key to test_results (nullable for suite-level artifacts)
- `suite_id`: UUID, foreign key to test_suites (nullable for result-level artifacts)
- `artifact_type`: Enum ("screenshot", "video", "report", "log", "trace", "other")
- `file_name`: String (original filename)
- `file_size`: Integer (size in bytes)
- `mime_type`: String (MIME type)
- `storage_key`: String (S3 object key)
- `storage_url`: String (signed URL, nullable - generated on demand)
- `checksum`: String (SHA-256 hash for integrity)
- `metadata`: JSONB (artifact-specific data)
- `created_at`: Timestamp
- `expires_at`: Timestamp (for automatic cleanup)

**Validation Rules**:
- One of result_id or suite_id must be provided (not both)
- artifact_type: required, one of allowed values
- file_name: required, 1-255 characters, valid filename
- file_size: required, > 0, <= 100MB
- mime_type: required, valid MIME type
- storage_key: required, unique, S3-compatible key format
- checksum: required, valid SHA-256 hash

**Relationships**:
- belongs_to: test_result (optional)
- belongs_to: test_suite (optional)

## Database Indexes

### Performance Indexes
- `test_results(suite_id)` - Suite-based queries
- `test_results(test_name)` - Test name searches
- `test_results(status)` - Status filtering
- `test_results(created_at)` - Time-based queries
- `test_suites(framework_id)` - Framework filtering
- `test_suites(environment_id)` - Environment filtering
- `test_suites(started_at)` - Time-based suite queries
- `test_artifacts(result_id)` - Result artifact queries
- `test_artifacts(suite_id)` - Suite artifact queries
- `test_artifacts(artifact_type)` - Type-based filtering
- `test_artifacts(expires_at)` - Cleanup queries

### Composite Indexes
- `test_results(suite_id, status)` - Suite status filtering
- `test_results(status, created_at)` - Status + time queries
- `test_suites(framework_id, started_at)` - Framework + time queries
- `test_artifacts(result_id, artifact_type)` - Result artifact type filtering
- `test_artifacts(suite_id, artifact_type)` - Suite artifact type filtering

### Unique Constraints
- `test_artifacts(storage_key)` - Unique S3 object keys

## State Transitions

### Test Result Status
```
[initial] -> passed (test succeeded)
[initial] -> failed (test failed)
[initial] -> skipped (test not executed)

# No transitions between states - immutable once set
```

### Test Suite Lifecycle
```
[created] -> running (execution started)
running -> completed (all tests finished)
running -> failed (suite execution error)

# Suite completion automatically calculated from test results
```

## Data Integrity Rules

### Referential Integrity
- All foreign keys must reference existing records
- Cascade delete: Suite deletion removes associated test results
- Restrict delete: Cannot delete framework/environment if referenced

### Business Logic Constraints
- Suite test counts must match actual test result counts
- Suite duration must be >= sum of test durations
- Test retry count cannot exceed configured maximum
- Screenshot paths must be accessible file locations

### Audit Trail
- All entities track creation and update timestamps
- Soft delete option for data retention compliance
- Change log for suite and result modifications