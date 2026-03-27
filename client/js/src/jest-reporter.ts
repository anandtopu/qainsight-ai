/**
 * QA Insight — Jest Custom Reporter
 * ====================================
 * Streams individual test results to QA Insight AI in real-time.
 *
 * Setup (jest.config.js / jest.config.ts)
 * ----------------------------------------
 *   module.exports = {
 *     reporters: [
 *       'default',
 *       ['<rootDir>/node_modules/qainsight-reporter/dist/jest-reporter', {
 *         baseUrl:     process.env.QAINSIGHT_URL     || 'http://localhost:8000',
 *         token:       process.env.QAINSIGHT_TOKEN,
 *         projectId:   process.env.QAINSIGHT_PROJECT_ID,
 *         buildNumber: process.env.QAINSIGHT_BUILD   || `jest-${Date.now()}`,
 *         branch:      process.env.QAINSIGHT_BRANCH,
 *         framework:   'jest',
 *       }],
 *     ],
 *   }
 *
 * Environment variables (alternative to inline config)
 * -----------------------------------------------------
 *   QAINSIGHT_URL          QA Insight server base URL
 *   QAINSIGHT_TOKEN        JWT access token
 *   QAINSIGHT_PROJECT_ID   Target project UUID
 *   QAINSIGHT_BUILD        CI build identifier (optional)
 *   QAINSIGHT_BRANCH       Git branch name (optional)
 *   QAINSIGHT_COMMIT       Git commit SHA (optional)
 */

import { QAInsightReporter, LiveSession, type TestStatus } from './qainsight-reporter'

// ── Types (subset of @jest/reporters to avoid hard dependency) ─────────────────

interface JestConfig {
  rootDir: string
  [key: string]: unknown
}

interface TestCaseResult {
  ancestorTitles: string[]
  fullName: string
  title: string
  status: 'passed' | 'failed' | 'skipped' | 'pending' | 'todo' | 'disabled'
  duration?: number | null
  failureMessages: string[]
  failureDetails: unknown[]
}

interface TestResult {
  testFilePath: string
  testResults: TestCaseResult[]
}

interface AggregatedResult {
  numTotalTests: number
  numPassedTests: number
  numFailedTests: number
  numPendingTests: number
  numSkippedTests: number
  startTime: number
}

interface Test {
  path: string
}

// ── Reporter Options ───────────────────────────────────────────────────────────

interface QAInsightJestReporterOptions {
  baseUrl?: string
  token?: string
  projectId?: string
  buildNumber?: string
  branch?: string
  commitHash?: string
  framework?: string
  batchSize?: number
  batchIntervalMs?: number
}

// ── Jest Reporter ──────────────────────────────────────────────────────────────

export default class QAInsightJestReporter {
  private readonly opts: Required<
    Pick<QAInsightJestReporterOptions, 'baseUrl' | 'token' | 'projectId'>
  > &
    QAInsightJestReporterOptions

  private reporter: QAInsightReporter | null = null
  private session: LiveSession | null = null
  private startTime = 0

  constructor(_globalConfig: JestConfig, options: QAInsightJestReporterOptions = {}) {
    const baseUrl   = options.baseUrl   ?? process.env['QAINSIGHT_URL']          ?? ''
    const token     = options.token     ?? process.env['QAINSIGHT_TOKEN']         ?? ''
    const projectId = options.projectId ?? process.env['QAINSIGHT_PROJECT_ID']   ?? ''

    if (!baseUrl || !token || !projectId) {
      console.warn(
        '[QAInsight] Reporter disabled: missing baseUrl, token, or projectId. ' +
          'Set QAINSIGHT_URL, QAINSIGHT_TOKEN, QAINSIGHT_PROJECT_ID env vars.',
      )
    }

    this.opts = {
      ...options,
      baseUrl,
      token,
      projectId,
      buildNumber:    options.buildNumber ?? process.env['QAINSIGHT_BUILD'] ?? `jest-${Date.now()}`,
      branch:         options.branch      ?? process.env['QAINSIGHT_BRANCH'],
      commitHash:     options.commitHash  ?? process.env['QAINSIGHT_COMMIT'],
      framework:      options.framework   ?? 'jest',
    }
  }

  /** Called before any tests run. */
  async onRunStart(results: AggregatedResult): Promise<void> {
    if (!this.opts.baseUrl || !this.opts.token || !this.opts.projectId) return

    this.startTime = results.startTime ?? Date.now()

    try {
      this.reporter = new QAInsightReporter({
        baseUrl:   this.opts.baseUrl,
        token:     this.opts.token,
        projectId: this.opts.projectId,
        framework: this.opts.framework ?? 'jest',
        batchSize: this.opts.batchSize,
        batchIntervalMs: this.opts.batchIntervalMs,
      })

      this.session = await this.reporter.startSession({
        buildNumber: this.opts.buildNumber,
        branch:      this.opts.branch,
        commitHash:  this.opts.commitHash,
        totalTests:  results.numTotalTests,
      })

      console.log(`[QAInsight] Session started: ${this.session.sessionId}`)
    } catch (err) {
      console.error('[QAInsight] Failed to start session:', err)
      this.session = null
    }
  }

  /**
   * Called after each individual test case completes.
   * Requires Jest >= 27.4 (uses `onTestCaseResult`).
   * For older Jest, results are batched per file via `onTestResult`.
   */
  onTestCaseResult(_test: Test, testCaseResult: TestCaseResult): void {
    if (!this.session) return

    const status = this._mapStatus(testCaseResult.status)
    const suiteParts = testCaseResult.ancestorTitles
    const suiteName  = suiteParts.join(' > ') || undefined

    const error =
      testCaseResult.failureMessages.length > 0
        ? testCaseResult.failureMessages[0]!.split('\n')[0]
        : undefined
    const stackTrace =
      testCaseResult.failureMessages.length > 0
        ? testCaseResult.failureMessages.join('\n---\n')
        : undefined

    // Fire-and-forget: Jest doesn't await non-async reporter methods
    this.session
      .record(testCaseResult.fullName, status, testCaseResult.duration ?? 0, {
        suiteName,
        error,
        stackTrace,
      })
      .catch((e) => console.debug('[QAInsight] record error:', e))
  }

  /**
   * Fallback for Jest < 27.4: process the full test file result.
   * Called after each test *file* completes.
   */
  onTestResult(_test: Test, testResult: TestResult): void {
    if (!this.session) return

    for (const tc of testResult.testResults) {
      const status    = this._mapStatus(tc.status)
      const suiteName = tc.ancestorTitles.join(' > ') || undefined
      const error     = tc.failureMessages[0]?.split('\n')[0]
      const stack     = tc.failureMessages.join('\n---\n') || undefined

      this.session
        .record(tc.fullName, status, tc.duration ?? 0, { suiteName, error, stackTrace: stack })
        .catch((e) => console.debug('[QAInsight] record error:', e))
    }
  }

  /** Called after all test files have run. */
  async onRunComplete(_contexts: unknown, _results: AggregatedResult): Promise<void> {
    if (!this.session || !this.reporter) return

    try {
      await this.session.close()
      await this.reporter.closeSession(this.session.sessionId)
      const { sent, failed } = this.session.stats
      console.log(`[QAInsight] Session closed: sent=${sent} failed=${failed}`)
    } catch (err) {
      console.error('[QAInsight] Failed to close session:', err)
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  private _mapStatus(
    jestStatus: 'passed' | 'failed' | 'skipped' | 'pending' | 'todo' | 'disabled',
  ): TestStatus {
    switch (jestStatus) {
      case 'passed':   return 'PASSED'
      case 'failed':   return 'FAILED'
      case 'skipped':
      case 'pending':
      case 'todo':
      case 'disabled': return 'SKIPPED'
      default:         return 'SKIPPED'
    }
  }
}
