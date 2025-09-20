import type {
  FullConfig, FullResult, Reporter, Suite, TestCase, TestResult
} from '@playwright/test/reporter';

class MyReporter implements Reporter {
  onBegin(config: FullConfig, suite: Suite) {
    // Save config, suite and environment to test-results-platform
    console.log(JSON.stringify(config));
    console.log(JSON.stringify(suite));
    console.log(`Starting the run with ${suite.allTests().length} tests`);
  }

  onTestBegin(test: TestCase, result: TestResult) {
    // Save test and mark started in test-results-platform
    console.log(`Starting test ${test.title}`);
  }

  onTestEnd(test: TestCase, result: TestResult) {
    // Save test results and mark ended in test-results-platform
    console.log(`Finished test ${test.title}: ${result.status}`);
  }

  onEnd(result: FullResult) {
    // Mark the suite ended in test-results-platform
    console.log(`Finished the run: ${result.status}`);
  }
}

export default MyReporter;
