package ai.qainsight.testng;

import ai.qainsight.QAInsightReporter;
import ai.qainsight.QAInsightReporter.*;

import org.testng.*;

import java.util.logging.Logger;

/**
 * TestNG Listener — streams test results to QA Insight AI in real-time.
 *
 * <h3>Usage (testng.xml)</h3>
 * <pre>{@code
 * <suite name="My Suite">
 *   <listeners>
 *     <listener class-name="ai.qainsight.testng.QAInsightListener"/>
 *   </listeners>
 *   <test name="API Tests">
 *     <classes>
 *       <class name="com.example.ApiTest"/>
 *     </classes>
 *   </test>
 * </suite>
 * }</pre>
 *
 * <h3>Programmatic registration</h3>
 * <pre>{@code
 * TestNG testng = new TestNG();
 * testng.addListener(new QAInsightListener());
 * testng.setTestClasses(new Class[]{ MyTest.class });
 * testng.run();
 * }</pre>
 *
 * <h3>Configuration via environment variables</h3>
 * <pre>
 *   QAINSIGHT_URL          Server base URL     (required)
 *   QAINSIGHT_TOKEN        JWT access token    (required)
 *   QAINSIGHT_PROJECT_ID   Target project UUID (required)
 *   QAINSIGHT_BUILD        CI build number     (optional)
 *   QAINSIGHT_BRANCH       Git branch name     (optional)
 *   QAINSIGHT_COMMIT       Git commit SHA      (optional)
 * </pre>
 *
 * <h3>Configuration via JVM system properties (takes precedence)</h3>
 * <pre>
 *   -Dqainsight.url=...
 *   -Dqainsight.token=...
 *   -Dqainsight.projectId=...
 *   -Dqainsight.build=...
 * </pre>
 */
public class QAInsightListener implements ISuiteListener, ITestListener {

    private static final Logger LOG = Logger.getLogger(QAInsightListener.class.getName());

    private QAInsightReporter reporter;
    private LiveSession       session;

    // ── ISuiteListener ────────────────────────────────────────────────────────

    @Override
    public void onStart(ISuite suite) {
        String url       = prop("qainsight.url",       "QAINSIGHT_URL");
        String token     = prop("qainsight.token",     "QAINSIGHT_TOKEN");
        String projectId = prop("qainsight.projectId", "QAINSIGHT_PROJECT_ID");

        if (url.isEmpty() || token.isEmpty() || projectId.isEmpty()) {
            LOG.warning("QAInsightListener: disabled — missing URL, token, or projectId");
            return;
        }

        reporter = new QAInsightReporter.Builder()
            .baseUrl(url)
            .token(token)
            .projectId(projectId)
            .framework("testng")
            .build();

        try {
            session = reporter.startSession(
                SessionOptions.builder()
                    .buildNumber(prop("qainsight.build",  "QAINSIGHT_BUILD",
                                    "testng-" + System.currentTimeMillis()))
                    .branch(     nullable("qainsight.branch", "QAINSIGHT_BRANCH"))
                    .commitHash( nullable("qainsight.commit", "QAINSIGHT_COMMIT"))
                    .build()
            );
            LOG.info("QAInsightListener: session started: " + session.getSessionId());
        } catch (Exception e) {
            LOG.warning("QAInsightListener: failed to start session: " + e.getMessage());
            session = null;
        }
    }

    @Override
    public void onFinish(ISuite suite) {
        if (session == null) return;
        session.close();
        LOG.info("QAInsightListener: suite finished — session closed: " + session.getSessionId());
    }

    // ── ITestListener ─────────────────────────────────────────────────────────

    @Override
    public void onTestSuccess(ITestResult result) {
        record(result, TestStatus.PASSED);
    }

    @Override
    public void onTestFailure(ITestResult result) {
        record(result, TestStatus.FAILED);
    }

    @Override
    public void onTestSkipped(ITestResult result) {
        record(result, TestStatus.SKIPPED);
    }

    @Override
    public void onTestFailedButWithinSuccessPercentage(ITestResult result) {
        record(result, TestStatus.BROKEN);
    }

    @Override
    public void onTestFailedWithTimeout(ITestResult result) {
        record(result, TestStatus.BROKEN);
    }

    // These are required by the interface but we have nothing to do here
    @Override public void onStart(ITestContext context) {}
    @Override public void onFinish(ITestContext context) {}
    @Override public void onTestStart(ITestResult result) {}

    // ── Helper ────────────────────────────────────────────────────────────────

    private void record(ITestResult result, TestStatus status) {
        if (session == null) return;

        long durationMs = result.getEndMillis() - result.getStartMillis();
        String testName  = result.getMethod().getMethodName();
        String suiteName = result.getTestClass().getName();

        String error = null;
        String stack = null;
        Throwable t  = result.getThrowable();
        if (t != null) {
            error = t.getMessage();
            java.io.StringWriter sw = new java.io.StringWriter();
            t.printStackTrace(new java.io.PrintWriter(sw));
            stack = sw.toString();
        }

        RecordOptions opts = RecordOptions.builder()
            .suiteName(suiteName)
            .className(result.getTestClass().getRealClass().getName())
            .error(error)
            .stackTrace(stack)
            .build();

        session.record(testName, status, durationMs, opts);
    }

    private static String prop(String sysProp, String envVar) {
        String v = System.getProperty(sysProp);
        if (v != null && !v.isEmpty()) return v;
        v = System.getenv(envVar);
        return v != null ? v : "";
    }

    private static String prop(String sysProp, String envVar, String defaultVal) {
        String v = prop(sysProp, envVar);
        return v.isEmpty() ? defaultVal : v;
    }

    private static String nullable(String sysProp, String envVar) {
        String v = prop(sysProp, envVar);
        return v.isEmpty() ? null : v;
    }
}
