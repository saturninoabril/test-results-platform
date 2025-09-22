# Data Model Extensions for Playwright Integration

## Entity Extensions

### TestResult Entity Extensions
The existing TestResult entity needs these Playwright-specific extensions:

**New Fields**:
- `location`: JSON field containing file path, line number, and column number where test is defined
- `retry_count`: Integer tracking which retry attempt this result represents (Playwright supports test retries)
- `project_name`: String identifying which Playwright project/browser configuration ran this test
- `timeout`: Integer milliseconds indicating test-specific timeout configuration

**Enhanced Fields**:
- `external_id`: Use Playwright's test.id() or generate from test.titlePath() + project
- `full_title`: Built from test.titlePath().join(' › ') for nested describe blocks
- `tags`: Extract from test annotations (@slow, @smoke, etc.) and project tags

**JSON Metadata Structure**:
```json
{
  "location": {
    "file": "/path/to/test/file.spec.ts",
    "line": 42,
    "column": 5
  },
  "playwright": {
    "testId": "abc123def",
    "workerIndex": 2,
    "parallelIndex": 1,
    "repeatEachIndex": 0,
    "annotations": [
      {"type": "slow", "description": "This test is slow"}
    ]
  }
}
```

### TestArtifact Entity Extensions
Extend to support Playwright-specific artifact types:

**New Artifact Types**:
- `trace`: Playwright trace files (.zip format)
- `video`: Test execution videos (.webm format)
- `screenshot`: Screenshots at failure points (.png format)
- `logs`: Console logs and debug output (.txt format)

**Enhanced Metadata Structure**:
```json
{
  "playwright": {
    "attachmentName": "trace",
    "contentType": "application/zip",
    "captureTime": "2025-09-20T10:30:45Z",
    "testStep": "page.click('button')",
    "viewport": {"width": 1280, "height": 720}
  }
}
```

### TestEnvironment Entity Extensions
Add browser and execution context information:

**New Fields**:
- `browser_name`: chromium, firefox, webkit
- `browser_version`: Specific version string
- `viewport`: JSON with width/height information
- `device_name`: For mobile testing (iPhone 12, Pixel 5, etc.)

**Enhanced Metadata Structure**:
```json
{
  "playwright": {
    "projectName": "Desktop Chrome",
    "browserName": "chromium",
    "browserVersion": "118.0.5993.70",
    "viewport": {"width": 1280, "height": 720},
    "deviceScaleFactor": 1,
    "isMobile": false,
    "hasTouch": false,
    "colorScheme": "light",
    "locale": "en-US",
    "timezoneId": "America/New_York",
    "userAgent": "Mozilla/5.0..."
  }
}
```

### TestSuite Entity Extensions
Add Playwright configuration context:

**Enhanced Fields**:
- `framework_version`: Playwright version (from config.version)
- `metadata`: Include Playwright config details

**Metadata Structure**:
```json
{
  "playwright": {
    "version": "1.55.0",
    "workers": 4,
    "fullyParallel": true,
    "retries": 2,
    "timeout": 30000,
    "projects": ["chromium", "firefox", "webkit"],
    "globalSetup": "./global-setup.ts",
    "globalTeardown": "./global-teardown.ts"
  }
}
```

## New Entity: TestEvent
For real-time progress tracking during test execution:

**Fields**:
- `id`: UUID primary key
- `suite_id`: Foreign key to TestSuite
- `test_external_id`: Foreign key reference (not enforced FK)
- `event_type`: Enum (test_started, test_ended, suite_started, suite_ended, error)
- `timestamp`: DateTime when event occurred
- `data`: JSON with event-specific information
- `created_at`: DateTime

**Event Types and Data Structures**:

**test_started**:
```json
{
  "testTitle": "should login successfully",
  "fullTitle": "Authentication › Login › should login successfully",
  "estimatedDuration": 5000,
  "retryIndex": 0
}
```

**test_ended**:
```json
{
  "testTitle": "should login successfully",
  "status": "passed",
  "duration": 4532,
  "artifactCount": 2
}
```

**suite_started**:
```json
{
  "totalTests": 150,
  "estimatedDuration": 300000,
  "projects": ["chromium", "firefox"]
}
```

**error**:
```json
{
  "errorType": "api_failure",
  "message": "Failed to upload artifact",
  "testTitle": "should login successfully",
  "recoverable": true
}
```

## State Transitions

### TestResult Status Flow
```
pending → running → (passed|failed|skipped|flaky)
                 → retrying → running → (passed|failed)
```

### TestSuite Status Flow
```
created → running → (passed|failed|interrupted)
```

### TestEvent Processing Flow
```
Event Created → Queued → Processed → Archived (after 30 days)
```

## Data Validation Rules

### TestResult Validation
- `external_id` must be unique within a test suite
- `retry_count` must be >= 0 and <= suite.max_retries
- `duration` must be positive for completed tests
- `location.file` must be a valid file path
- Status transitions must follow the defined flow

### TestArtifact Validation
- Artifact `type` must be in allowed list for Playwright
- `file_size` must be <= 50MB for trace files
- `storage_path` must follow S3 key naming conventions
- `content_type` must match artifact type expectations

### TestEnvironment Validation
- `browser_name` must be one of: chromium, firefox, webkit
- `viewport` dimensions must be positive integers
- `device_name` must be from Playwright's device registry if specified

## Performance Considerations

### Indexing Strategy
- Index on `(suite_id, external_id)` for TestResult lookups
- Index on `(suite_id, timestamp)` for TestEvent queries
- Index on `test_external_id` for TestEvent filtering
- Composite index on `(suite_id, status, created_at)` for dashboard queries

### Data Retention Policy
- TestEvent records: Archive after 30 days, delete after 90 days
- TestArtifact files: Keep for 1 year, then move to cold storage
- TestResult records: Keep indefinitely for trend analysis
- Failed upload retry data: Keep for 7 days

### Query Optimization
- Use pagination for large test result sets
- Implement result caching for dashboard aggregations
- Stream real-time events using WebSocket for UI updates
- Batch artifact metadata updates to reduce database load

## API Response Models

### Playwright Test Result Response
```json
{
  "id": "uuid",
  "suite_id": "uuid",
  "external_id": "test-123",
  "title": "should login successfully",
  "full_title": "Authentication › Login › should login successfully",
  "status": "passed",
  "duration": 4532,
  "retry_count": 0,
  "location": {
    "file": "./tests/auth.spec.ts",
    "line": 15,
    "column": 3
  },
  "artifacts": [
    {
      "type": "screenshot",
      "url": "https://s3.../screenshot.png",
      "size": 45632
    }
  ],
  "metadata": {
    "playwright": {
      "projectName": "Desktop Chrome",
      "browserName": "chromium"
    }
  },
  "created_at": "2025-09-20T10:30:00Z",
  "updated_at": "2025-09-20T10:30:05Z"
}
```

This data model extension provides comprehensive support for Playwright's rich test execution context while maintaining backward compatibility with the existing Test Results Platform architecture.