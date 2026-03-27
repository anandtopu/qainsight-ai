"""Multi-agent system for test report processing and analysis.

Keep package imports lazy to avoid importing optional dependencies (e.g. motor)
during unrelated unit tests.
"""

__all__ = ["QueryIntent", "classify_intent", "run_offline_pipeline"]


def __getattr__(name: str):
    if name in {"QueryIntent", "classify_intent"}:
        from app.agents.conversation import QueryIntent, classify_intent

        exports = {
            "QueryIntent": QueryIntent,
            "classify_intent": classify_intent,
        }
        return exports[name]
    if name == "run_offline_pipeline":
        from app.agents.workflow import run_offline_pipeline

        return run_offline_pipeline
    raise AttributeError(f"module 'app.agents' has no attribute {name}")
