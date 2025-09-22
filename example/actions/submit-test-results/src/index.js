const core = require('@actions/core');
const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

/**
 * Test Results Submission Action
 * Submits test results and artifacts to the Test Results Management API
 */

class TestResultsSubmitter {
  constructor() {
    this.apiEndpoint = core.getInput('api-endpoint', { required: true });
    this.token = core.getInput('automation-token', { required: true });
    this.framework = core.getInput('framework', { required: true });
    this.environmentName = core.getInput('environment-name', { required: true });
    this.browser = core.getInput('browser') || 'chrome';
    this.os = core.getInput('os') || 'ubuntu';
    this.resultsFile = core.getInput('results-file', { required: true });
    this.suiteName = core.getInput('suite-name') || 'CI Test Suite';
    this.artifactsPath = core.getInput('artifacts-path');
    this.uploadArtifacts = core.getInput('upload-artifacts') === 'true';
    this.tags = (core.getInput('tags') || 'ci,automated').split(',').map(tag => tag.trim());

    this.headers = {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json',
      'User-Agent': 'GitHub-Actions-Test-Results-Submitter/1.0'
    };

    // Parse framework name and version
    const [frameworkName, frameworkVersion] = this.framework.split('@');
    this.frameworkName = frameworkName;
    this.frameworkVersion = frameworkVersion || '1.0.0';
  }

  async run() {
    try {
      core.info(`🚀 Submitting test results to ${this.apiEndpoint}`);
      core.info(`📋 Framework: ${this.frameworkName}@${this.frameworkVersion}`);
      core.info(`🖥️  Environment: ${this.environmentName} (${this.browser}/${this.os})`);
      core.info(`📄 Results file: ${this.resultsFile}`);

      // Step 1: Prepare framework metadata (no longer using framework entities)
      const frameworkMetadata = {
        name: this.frameworkName,
        version: this.frameworkVersion,
        source: 'github-actions',
        created_by: process.env.GITHUB_ACTOR || 'github-actions',
        repository: process.env.GITHUB_REPOSITORY || 'unknown',
        run_id: process.env.GITHUB_RUN_ID || 'unknown'
      };
      core.info(`✅ Framework metadata: ${this.frameworkName}@${this.frameworkVersion}`);

      // Step 2: Prepare environment metadata (environments may still exist but referenced by metadata)
      const environmentMetadata = {
        name: this.environmentName,
        browser: this.browser,
        os: this.os,
        source: 'github-actions',
        created_by: process.env.GITHUB_ACTOR || 'github-actions',
        repository: process.env.GITHUB_REPOSITORY || 'unknown',
        run_id: process.env.GITHUB_RUN_ID || 'unknown',
        runner_os: process.env.RUNNER_OS || 'unknown',
        runner_arch: process.env.RUNNER_ARCH || 'unknown'
      };
      core.info(`✅ Environment metadata: ${this.environmentName}`);

      // Step 3: Parse test results
      const resultsData = await this.parseResults();
      core.info(`📊 Parsed ${resultsData.results.length} test results`);

      // Step 4: Create test suite with metadata instead of IDs
      const suiteId = await this.createSuite(frameworkMetadata, environmentMetadata, resultsData);
      core.setOutput('suite-id', suiteId);
      core.info(`✅ Suite ID: ${suiteId}`);

      // Step 5: Submit test results
      const resultIds = await this.submitResults(suiteId, resultsData.results);
      core.setOutput('results-count', resultIds.length);
      core.info(`✅ Submitted ${resultIds.length} test results`);

      // Step 6: Upload artifacts if specified
      let artifactsCount = 0;
      if (this.uploadArtifacts && this.artifactsPath) {
        artifactsCount = await this.uploadArtifacts(resultIds, this.artifactsPath);
        core.setOutput('artifacts-count', artifactsCount);
        core.info(`✅ Uploaded ${artifactsCount} artifacts`);
      }

      core.info('🎉 Test results submission completed successfully!');

    } catch (error) {
      core.setFailed(`❌ Action failed: ${error.message}`);
      console.error('Error details:', error);
    }
  }

  // Framework entities removed - framework info now stored in suite metadata
  // This method is no longer needed but kept for reference

  // Environment entities may still exist but are referenced via metadata
  // This method is no longer used in the main flow but kept for reference

  async parseResults() {
    try {
      const resultsContent = await fs.readFile(this.resultsFile, 'utf-8');
      const resultsData = JSON.parse(resultsContent);

      // Auto-detect format based on structure
      if (resultsData.config && resultsData.suites) {
        // Playwright format
        return this.parsePlaywrightResults(resultsData);
      } else if (resultsData.stats && resultsData.results) {
        // Cypress format
        return this.parseCypressResults(resultsData);
      } else if (Array.isArray(resultsData)) {
        // Generic array format
        return { results: resultsData, stats: { total: resultsData.length } };
      } else {
        throw new Error('Unsupported test results format');
      }

    } catch (error) {
      throw new Error(`Failed to parse results file: ${error.message}`);
    }
  }

  parsePlaywrightResults(data) {
    const results = [];
    const stats = { total: 0, passed: 0, failed: 0, skipped: 0 };

    // Extract tests from all suites
    function extractTests(suites, projectName = '') {
      for (const suite of suites || []) {
        for (const spec of suite.specs || []) {
          for (const test of spec.tests || []) {
            const result = {
              name: test.title,
              full_title: `${suite.title ? suite.title + ' ' : ''}${test.title}`,
              status: test.results?.[0]?.status === 'passed' ? 'passed' :
                     test.results?.[0]?.status === 'skipped' ? 'skipped' : 'failed',
              duration_ms: test.results?.[0]?.duration || 0,
              external_id: `${projectName}-${suite.title}-${test.title}`.replace(/\s+/g, '-'),
              tags: [...this.tags, projectName].filter(Boolean),
              metadata: {
                project: projectName,
                suite: suite.title,
                retry_count: test.results?.[0]?.retry || 0,
                error: test.results?.[0]?.error || null,
                attachments: test.results?.[0]?.attachments || []
              }
            };

            results.push(result);
            stats.total++;
            if (result.status === 'passed') stats.passed++;
            else if (result.status === 'failed') stats.failed++;
            else if (result.status === 'skipped') stats.skipped++;
          }
        }

        // Recursively process nested suites
        if (suite.suites) {
          extractTests(suite.suites, projectName);
        }
      }
    }

    // Process each project
    for (const suite of data.suites || []) {
      extractTests([suite], suite.title || '');
    }

    return { results, stats };
  }

  parseCypressResults(data) {
    const results = [];
    const stats = data.stats || {};

    function extractTests(testData) {
      for (const result of testData.results || []) {
        for (const suite of result.suites || []) {
          for (const test of suite.tests || []) {
            const testResult = {
              name: test.title,
              full_title: test.fullTitle || test.title,
              status: test.state || 'failed',
              duration_ms: test.duration || 0,
              external_id: test.uuid || `cypress-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              tags: [...this.tags, 'cypress'],
              error_message: test.err?.message || null,
              metadata: {
                suite: suite.title,
                file: result.file,
                retry_count: 0,
                cypress_test: true,
                test_uuid: test.uuid
              }
            };

            results.push(testResult);
          }
        }
      }
    }

    extractTests(data);

    return {
      results,
      stats: {
        total: stats.tests || results.length,
        passed: stats.passes || results.filter(r => r.status === 'passed').length,
        failed: stats.failures || results.filter(r => r.status === 'failed').length,
        skipped: stats.pending || results.filter(r => r.status === 'skipped').length
      }
    };
  }

  async createSuite(frameworkMetadata, environmentMetadata, resultsData) {
    try {
      const suiteData = {
        name: this.suiteName,
        total_count: resultsData.stats.total,
        passed_count: resultsData.stats.passed,
        failed_count: resultsData.stats.failed,
        skipped_count: resultsData.stats.skipped,
        duration_ms: resultsData.results.reduce((sum, r) => sum + (r.duration_ms || 0), 0),
        // Framework info now stored in framework_metadata
        framework_metadata: frameworkMetadata,
        // Environment info now stored in environment_metadata
        environment_metadata: environmentMetadata,
        // CI/CD info stored in ci_run_metadata
        ci_run_metadata: {
          source: 'github-actions',
          repository: process.env.GITHUB_REPOSITORY || 'unknown',
          run_id: process.env.GITHUB_RUN_ID || 'unknown',
          run_number: process.env.GITHUB_RUN_NUMBER || 'unknown',
          sha: process.env.GITHUB_SHA || 'unknown',
          ref: process.env.GITHUB_REF || 'unknown',
          actor: process.env.GITHUB_ACTOR || 'unknown',
          workflow: process.env.GITHUB_WORKFLOW || 'unknown'
        }
      };

      const response = await this.apiRequest('POST', '/api/v1/suites', suiteData);
      return response.id;

    } catch (error) {
      throw new Error(`Failed to create suite: ${error.message}`);
    }
  }

  async submitResults(suiteId, results) {
    const resultIds = [];

    for (const result of results) {
      try {
        const resultData = {
          ...result,
          suite_id: suiteId
        };

        const response = await this.apiRequest('POST', '/api/v1/results', resultData);
        resultIds.push(response.id);

      } catch (error) {
        core.warning(`Failed to submit result "${result.name}": ${error.message}`);
      }
    }

    return resultIds;
  }

  async uploadArtifacts(resultIds, artifactsPath) {
    let uploadedCount = 0;

    try {
      const files = await this.findArtifactFiles(artifactsPath);
      core.info(`Found ${files.length} artifact files`);

      for (const file of files.slice(0, 50)) { // Limit to 50 files
        try {
          // Try to associate with a result based on filename
          const resultId = this.findResultForFile(resultIds, file) || resultIds[0];

          if (resultId) {
            await this.uploadArtifact(resultId, file);
            uploadedCount++;
          }
        } catch (error) {
          core.warning(`Failed to upload artifact ${file}: ${error.message}`);
        }
      }

    } catch (error) {
      core.warning(`Failed to upload artifacts: ${error.message}`);
    }

    return uploadedCount;
  }

  async findArtifactFiles(artifactsPath) {
    const files = [];

    try {
      const entries = await fs.readdir(artifactsPath, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(artifactsPath, entry.name);

        if (entry.isFile() && this.isArtifactFile(entry.name)) {
          files.push(fullPath);
        } else if (entry.isDirectory()) {
          // Recursively search subdirectories (limit depth)
          const subFiles = await this.findArtifactFiles(fullPath);
          files.push(...subFiles);
        }
      }
    } catch (error) {
      core.warning(`Could not read artifacts directory ${artifactsPath}: ${error.message}`);
    }

    return files;
  }

  isArtifactFile(filename) {
    const extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.webm', '.json', '.html', '.txt', '.log'];
    const lowerName = filename.toLowerCase();
    return extensions.some(ext => lowerName.endsWith(ext));
  }

  findResultForFile(resultIds, filePath) {
    // Simple heuristic: use first result ID
    // In practice, this could be more sophisticated based on filename patterns
    return resultIds[0];
  }

  async uploadArtifact(resultId, filePath) {
    try {
      const filename = path.basename(filePath);
      const fileContent = await fs.readFile(filePath);

      // Determine artifact type based on file extension
      const ext = path.extname(filename).toLowerCase();
      const artifactType = this.getArtifactType(ext);

      // Create FormData for file upload
      const FormData = require('form-data');
      const form = new FormData();

      form.append('file', fileContent, {
        filename: filename,
        contentType: this.getContentType(ext)
      });

      form.append('artifact_type', artifactType);
      form.append('metadata', JSON.stringify({
        original_filename: filename,
        file_size: fileContent.length,
        uploaded_by: 'github-actions',
        upload_source: 'ci'
      }));

      const response = await this.apiRequestForm('POST', `/api/v1/results/${resultId}/artifacts`, form);
      core.info(`📎 Uploaded artifact: ${filename}`);
      return response.id;

    } catch (error) {
      throw new Error(`Failed to upload artifact: ${error.message}`);
    }
  }

  getArtifactType(extension) {
    const typeMap = {
      '.png': 'screenshot',
      '.jpg': 'screenshot',
      '.jpeg': 'screenshot',
      '.gif': 'screenshot',
      '.webp': 'screenshot',
      '.mp4': 'video',
      '.webm': 'video',
      '.json': 'report',
      '.html': 'report',
      '.txt': 'log',
      '.log': 'log'
    };
    return typeMap[extension] || 'other';
  }

  getContentType(extension) {
    const typeMap = {
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
      '.mp4': 'video/mp4',
      '.webm': 'video/webm',
      '.json': 'application/json',
      '.html': 'text/html',
      '.txt': 'text/plain',
      '.log': 'text/plain'
    };
    return typeMap[extension] || 'application/octet-stream';
  }

  async apiRequest(method, endpoint, data = null) {
    const url = `${this.apiEndpoint}${endpoint}`;

    const options = {
      method,
      headers: this.headers
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    // Use node-fetch for HTTP requests
    const fetch = require('node-fetch');
    const response = await fetch(url, options);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed (${response.status}): ${errorText}`);
    }

    return await response.json();
  }

  async apiRequestForm(method, endpoint, formData) {
    const url = `${this.apiEndpoint}${endpoint}`;

    const headers = {
      ...this.headers
    };
    delete headers['Content-Type']; // Let form-data set the boundary

    const fetch = require('node-fetch');
    const response = await fetch(url, {
      method,
      headers,
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed (${response.status}): ${errorText}`);
    }

    return await response.json();
  }
}

// Main execution
async function main() {
  const submitter = new TestResultsSubmitter();
  await submitter.run();
}

if (require.main === module) {
  main().catch(error => {
    core.setFailed(error.message);
  });
}

module.exports = TestResultsSubmitter;