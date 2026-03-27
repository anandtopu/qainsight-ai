/**
 * QA Insight — Mocha Reporter
 * ==============================
 * Streams individual test results to QA Insight AI in real-time.
 *
 * Setup (.mocharc.js / .mocharc.yaml)
 * --------------------------------------
 *   // .mocharc.js
 *   module.exports = {
 *     reporter: './node_modules/qainsight-reporter/dist/mocha-reporter',
 *     reporterOptions: {
 *       qainsightUrl:       process.env.QAINSIGHT_URL,
 *       qainsightToken:     process.env.QAINSIGHT_TOKEN,
 *       qainsightProject:   process.env.QAINSIGHT_PROJECT_ID,
 *       qainsightBuild:     process.env.QAINSIGHT_BUILD || `mocha-${Date.now()}`,
 *       qainsightBranch:    process.env.QAINSIGHT_BRANCH,
 *     },
 *   }
 *
 *   // CLI
 *   mocha --reporter ./qainsight-mocha-reporter.js \
 *         --reporter-option qainsightUrl=http://localhost:8000 \
 *         --reporter-option qainsightToken=<jwt> \
 *         --reporter-option qainsightProject=<uuid>
 *
 * Environment variables (fallback when reporter options are absent)
 * -----------------------------------------------------------------
 *   QAINSIGHT_URL          Server base URL
 *   QAINSIGHT_TOKEN        JWT access token
 *   QAINSIGHT_PROJECT_ID   Target project UUID
 *   QAINSIGHT_BUILD        Build identifier
 *   QAINSIGHT_BRANCH       Git branch
 *   QAINSIGHT_COMMIT       Git commit SHA
 */

import { QAInsightReporter, LiveSession, type TestStatus } from './qainsight-reporter'

// ── Minimal Mocha type stubs (avoid hard dep on @types/mocha) ─────────────────

interface MochaRunner {
  on(event: string, listener: (...args: unknown[]) => void): this
  stats: { passes: number; failures: number; pending: number }
}

interface MochaTest {
  fullTitle(): string
  titlePath(): string[]
  duration?: number
  err?: Error & { stack?: string }
  isPassed(): boolean
  isFailed(): boolean
  isPending(): boolean
  parent?: { fullTitle(): string }
}

interface MochaOptions {
  reporterOptions?: {
    qainsightUrl?:     string
    qainsightToken?:   string
    qainsightProject?: string
    qainsightBuild?:   string
    qainsightBranch?:  string
    qainsightCommit?:  string
    [key: string]: unknown
  }
}

// ── Reporter ───────────────────────────────────────────────────────────────────

export default class QAInsightMochaReporter {
  private reporter: QAInsightReporter | null = null
  private session: LiveSession | null = null
  private readonly baseUrl: string
  private readonly token: string
  private readonly projectId: string
  private readonly buildNumber: string
  private readonly branch: string | undefined
  private readonly commitHash: string | undefined

  constructor(runner: MochaRunner, options: MochaOptions = {}) {
    const ro = options.reporterOptions ?? {}

    this.baseUrl     = ro.qainsightUrl     ?? process.env['QAINSIGHT_URL']          ?? ''
    this.token       = ro.qainsightToken   ?? process.env['QAINSIGHT_TOKEN']         ?? ''
    this.projectId   = ro.qainsightProject ?? process.env['QAINSIGHT_PROJECT_ID']   ?? ''
    this.buildNumber = ro.qainsightBuild   ?? process.env['QAINSIGHT_BUILD']         ?? `mocha-${Date.now()}`
    this.branch      = ro.qainsightBranch  ?? process.env['QAINSIGHT_BRANCH']
    this.commitHash  = ro.qainsightCommit  ?? process.env['QAINSIGHT_COMMIT']

    if (!this.baseUrl || !this.token || !this.projectId) {
      console.warn(
        '[QAInsight] Reporter disabled: missing URL, token, or projectId.',
      )
      return
    }

    this._attachHooks(runner)
  }

  // ── Runner hooks ───────────────────────────────────────────────────────────

  private _attachHooks(runner: MochaRunner): void {
    runner.on('start', () => this._onStart())
    runner.on('pass',  (test: unknown) => this._onPass(test as MochaTest))
    runner.on('fail',  (test: unknown) => this._onFail(test as MochaTest))
    runner.on('pending', (test: unknown) => this._onPending(test as MochaTest))
    runner.on('end',   () => this._onEnd())
  }

  private _onStart(): void {
    this.reporter = new QAInsightReporter({
      baseUrl:   this.baseUrl,
      token:     this.token,
      projectId: this.projectId,
      framework: 'mocha',
    })

    this.reporter
      .startSession({
        buildNumber: this.buildNumber,
        branch:      this.branch,
        commitHash:  this.commitHash,
      })
      .then((s) => {
        this.session = s
        console.log(`[QAInsight] Mocha session started: ${s.sessionId}`)
      })
      .catch((err) => {
        console.error('[QAInsight] Failed to start session:', err)
      })
  }

  private _onPass(test: MochaTest): void {
    this._record(test, 'PASSED')
  }

  private _onFail(test: MochaTest): void {
    this._record(test, 'FAILED')
  }

  private _onPending(test: MochaTest): void {
    this._record(test, 'SKIPPED')
  }

  private _onEnd(): void {
    if (!this.session || !this.reporter) return

    this.session
      .close()
      .then(() => this.reporter!.closeSession(this.session!.sessionId))
      .then(() => {
        const { sent, failed } = this.session!.stats
        console.log(`[QAInsight] Mocha session closed: sent=${sent} failed=${failed}`)
      })
      .catch((err) => console.error('[QAInsight] Failed to close session:', err))
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  private _record(test: MochaTest, status: TestStatus): void {
    if (!this.session) return

    const suite  = test.parent?.fullTitle() || undefined
    const error  = test.err?.message
    const stack  = test.err?.stack

    this.session
      .record(test.fullTitle(), status, test.duration ?? 0, {
        suiteName:  suite,
        error,
        stackTrace: stack,
      })
      .catch((e) => console.debug('[QAInsight] record error:', e))
  }
}
