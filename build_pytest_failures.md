Run pytest tests/ -v \
/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/site-packages/pytest_asyncio/plugin.py:208: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.3.4, pluggy-1.6.0 -- /opt/hostedtoolcache/Python/3.11.15/x64/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/qainsight-ai/qainsight-ai/backend
plugins: asyncio-0.24.0, Faker-40.11.1, mock-3.14.0, cov-6.0.0, anyio-4.7.0, langsmith-0.7.22
asyncio: mode=Mode.STRICT, default_loop_scope=None
collecting ... collected 81 items

tests/services/test_batch1_pure_services.py::test_allure_parser_uses_parent_suite_and_tags PASSED [  1%]

TOTAL                                            8328   5866    30%
Coverage XML written to file coverage.xml

=========================== short test summary info ============================
FAILED tests/services/test_service_layer_refactors.py::test_deprecate_managed_test_case_sets_status_and_audits - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_apply_review_action_updates_review_and_test_case - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_recompute_plan_counts_updates_all_aggregates - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_list_project_runs_enriches_paginated_runs - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_search_test_cases_query_returns_rows_and_pagination - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_generate_ai_cases_persists_created_cases_when_requested - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_review_test_case_with_ai_creates_review_when_missing - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_generate_ai_strategy_creates_strategy_and_audits - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_list_audit_logs_returns_paginated_filtered_entries - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_upsert_notification_preference_updates_existing_preference - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_resolve_notification_overrides_returns_none_when_preference_missing - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_release_service_list_releases_enriches_run_counts - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_release_service_link_test_run_returns_existing_link_message - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_report_service_email_trends_report_sends_built_email - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_analytics_service_flaky_tests_returns_items_and_total - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_analytics_service_list_defects_returns_pagination_metadata - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_stream_service_create_session_stores_token_and_initializes_live_state - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_stream_service_ingest_event_batch_validates_and_refreshes_token - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_stream_service_list_active_sessions_combines_sources - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_stream_service_close_session_marks_complete_and_queues_followup_work - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_feedback_service_submit_feedback_backpropagates_incorrect_correction - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_feedback_service_jira_resolution_webhook_creates_feedback_for_invalid_resolution - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_chat_service_get_run_summaries_merges_ai_summaries_and_stubs - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/services/test_service_layer_refactors.py::test_chat_service_send_message_updates_default_title_and_dispatches_agent - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_agent.py::TestAgentToolCallLogic::test_backend_timeout_identified - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_agent.py::TestAgentToolCallLogic::test_flaky_test_detected - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_agent.py::TestAgentToolCallLogic::test_insufficient_telemetry_handling - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_analysis_agent.py::TestAnalysisAgentAnalyzeOne::test_analyse_one_returns_timeout_fallback - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_analysis_agent.py::TestAnalysisAgentAnalyzeOne::test_analyse_one_returns_error_fallback_on_exception - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_storage.py::test_local_storage_provider - RuntimeError: There is no current event loop in thread 'MainThread'.
=================== 30 failed, 51 passed, 1 warning in 7.78s ===================
sys:1: RuntimeWarning: coroutine 'test_local_storage_provider' was never awaited
Error: Process completed with exit code 1.
