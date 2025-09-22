// TypeScript Client Library Type Definitions
// Test Results Platform Playwright Integration Client

export interface PlaywrightClientConfig {
  /** Base URL of the Test Results Platform API */
  baseUrl: string;
  /** JWT authentication token */
  authToken: string;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Number of retry attempts for failed requests */
  retries?: number;
  /** Whether to upload artifacts automatically */
  uploadArtifacts?: boolean;
  /** Custom HTTP headers to include with requests */
  headers?: Record<string, string>;
}

export interface TestLocation {
  file: string;
  line: number;
  column: number;
}

export interface CreateTestSuiteRequest {
  name: string;
  framework: 'playwright';
  version: string;
  testCount: number;
  status: 'created' | 'running';
  startTime: string;
  metadata?: {
    playwright?: {
      workers?: number;
      fullyParallel?: boolean;
      retries?: number;
      timeout?: number;
      projects?: string[];
    };
  };
}

export interface CreateTestEnvironmentRequest {
  name: string;
  browserName: 'chromium' | 'firefox' | 'webkit';
  browserVersion?: string;
  os: string;
  viewport?: {
    width: number;
    height: number;
  };
  deviceName?: string;
  metadata?: {
    playwright?: {
      deviceScaleFactor?: number;
      isMobile?: boolean;
      hasTouch?: boolean;
      colorScheme?: 'light' | 'dark';
    };
  };
}

export interface CreateTestResultRequest {
  suiteId: string;
  environmentId: string;
  externalId?: string;
  title: string;
  fullTitle: string;
  status: 'pending' | 'running';
  location?: TestLocation;
  retryCount?: number;
  projectName?: string;
  timeout?: number;
  tags?: string[];
  startTime: string;
  metadata?: {
    playwright?: {
      testId?: string;
      workerIndex?: number;
      parallelIndex?: number;
      annotations?: Array<{
        type: string;
        description?: string;
      }>;
    };
  };
}

export interface UpdateTestResultRequest {
  status: 'passed' | 'failed' | 'skipped' | 'flaky' | 'retrying';
  duration?: number;
  endTime?: string;
  errorMessage?: string;
  retryCount?: number;
}

export interface ArtifactUploadRequest {
  filename: string;
  contentType: string;
  artifactType: 'screenshot' | 'video' | 'trace' | 'logs';
  fileSize?: number;
}

export interface TestEvent {
  suiteId: string;
  testExternalId?: string;
  eventType: 'test_started' | 'test_ended' | 'suite_started' | 'suite_ended' | 'error';
  timestamp: string;
  data: any;
}

// Response types

export interface TestSuiteResponse {
  id: string;
  name: string;
  framework: string;
  version: string;
  testCount: number;
  status: string;
  startTime: string;
  endTime?: string;
  duration?: number;
  metadata?: any;
}

export interface TestEnvironmentResponse {
  id: string;
  name: string;
  browserName: string;
  browserVersion?: string;
  os: string;
  viewport?: { width: number; height: number };
  deviceName?: string;
  metadata?: any;
}

export interface TestResultResponse {
  id: string;
  suiteId: string;
  environmentId: string;
  externalId?: string;
  title: string;
  fullTitle: string;
  status: string;
  duration?: number;
  retryCount: number;
  projectName?: string;
  timeout?: number;
  errorMessage?: string;
  location?: TestLocation;
  tags: string[];
  startTime: string;
  endTime?: string;
  metadata?: any;
}

export interface ArtifactRecord {
  id: string;
  testResultId: string;
  type: string;
  filename: string;
  storagePath: string;
  fileSize: number;
  contentType: string;
  downloadUrl: string;
  metadata?: any;
}

export interface PresignedUploadResponse {
  uploadUrl: string;
  downloadUrl: string;
  expiresAt: string;
  storagePath: string;
}

// Client interface

export interface PlaywrightTestResultsClient {
  /**
   * Create a new test suite
   */
  createTestSuite(request: CreateTestSuiteRequest): Promise<TestSuiteResponse>;

  /**
   * Update test suite with final results
   */
  updateTestSuite(suiteId: string, update: {
    status: 'passed' | 'failed' | 'interrupted';
    endTime: string;
    duration?: number;
  }): Promise<TestSuiteResponse>;

  /**
   * Create a test environment configuration
   */
  createTestEnvironment(request: CreateTestEnvironmentRequest): Promise<TestEnvironmentResponse>;

  /**
   * Create a new test result record
   */
  createTestResult(request: CreateTestResultRequest): Promise<TestResultResponse>;

  /**
   * Update an existing test result
   */
  updateTestResult(externalId: string, suiteId: string, update: UpdateTestResultRequest): Promise<TestResultResponse>;

  /**
   * Get presigned URL for artifact upload
   */
  getPresignedUploadUrl(request: ArtifactUploadRequest): Promise<PresignedUploadResponse>;

  /**
   * Register an artifact after successful upload
   */
  registerArtifact(testResultId: string, artifact: {
    type: string;
    filename: string;
    storagePath: string;
    fileSize: number;
    contentType: string;
    metadata?: any;
  }): Promise<ArtifactRecord>;

  /**
   * Upload a file to S3 using presigned URL
   */
  uploadArtifact(filePath: string, uploadUrl: string, contentType: string): Promise<void>;

  /**
   * Complete artifact upload flow (get presigned URL + upload + register)
   */
  uploadArtifactComplete(
    testResultId: string,
    filePath: string,
    artifactType: 'screenshot' | 'video' | 'trace' | 'logs',
    metadata?: any
  ): Promise<ArtifactRecord>;

  /**
   * Create a real-time test event
   */
  createTestEvent(event: TestEvent): Promise<{ id: string }>;

  /**
   * Health check - verify API connectivity
   */
  healthCheck(): Promise<{ status: string; timestamp: string }>;
}

// Error types

export class TestResultsClientError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: any
  ) {
    super(message);
    this.name = 'TestResultsClientError';
  }
}

export class AuthenticationError extends TestResultsClientError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends TestResultsClientError {
  constructor(message: string = 'Rate limit exceeded', retryAfter?: number) {
    super(message, 429);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }

  retryAfter?: number;
}

export class NetworkError extends TestResultsClientError {
  constructor(message: string = 'Network error') {
    super(message);
    this.name = 'NetworkError';
  }
}

// Factory function

export declare function createPlaywrightClient(config: PlaywrightClientConfig): PlaywrightTestResultsClient;

// Utility types for Playwright integration

export interface PlaywrightTestCase {
  id(): string;
  title: string;
  titlePath(): string[];
  location: {
    file: string;
    line: number;
    column: number;
  };
  annotations?: Array<{ type: string; description?: string }>;
}

export interface PlaywrightTestResult {
  status: 'passed' | 'failed' | 'skipped' | 'flaky';
  duration: number;
  error?: {
    message: string;
    stack?: string;
  };
  attachments?: Array<{
    name: string;
    path?: string;
    body?: Buffer;
    contentType: string;
  }>;
}

export interface PlaywrightConfig {
  version?: string;
  workers?: number;
  fullyParallel?: boolean;
  retries?: number;
  timeout?: number;
  projects?: Array<{
    name: string;
    use: {
      browserName: string;
      viewport?: { width: number; height: number };
    };
  }>;
}

export interface PlaywrightSuite {
  allTests(): PlaywrightTestCase[];
}

// Reporter integration helpers

export interface ReporterOptions extends Partial<PlaywrightClientConfig> {
  /** Enable debug logging */
  debug?: boolean;
  /** Custom suite name prefix */
  suiteNamePrefix?: string;
  /** Tags to add to all tests */
  defaultTags?: string[];
}

export declare class TestResultsPlatformReporter {
  constructor(options?: ReporterOptions);

  onBegin(config: PlaywrightConfig, suite: PlaywrightSuite): Promise<void>;
  onTestBegin(test: PlaywrightTestCase, result: PlaywrightTestResult): Promise<void>;
  onTestEnd(test: PlaywrightTestCase, result: PlaywrightTestResult): Promise<void>;
  onEnd(result: { status: string; startTime: number }): Promise<void>;
  onError?(error: Error): void;
  onExit?(): Promise<void>;

  printsToStdio?(): boolean;
}