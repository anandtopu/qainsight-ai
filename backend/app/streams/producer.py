"""
Redis Streams producer — thin, fire-and-forget event publisher.

HTTP endpoints call these functions to enqueue events immediately and return 202.
The actual work happens asynchronously in the stream consumer.
"""
import json
import logging
from typing import Any

from app.db.redis_client import get_redis
from app.streams import (
    ANALYSIS_STREAM,
    ANALYSIS_STREAM_MAXLEN,
    DLQ_STREAM,
    DLQ_STREAM_MAXLEN,
    INGESTION_STREAM,
    INGESTION_STREAM_MAXLEN,
    LIVE_EVENTS_STREAM,
    LIVE_STREAM_MAXLEN,
)

logger = logging.getLogger("streams.producer")


async def publish_live_event(run_id: str, event: dict) -> str:
    """
    Publish a live test execution event to the live events stream.
    Returns the Redis message ID.

    Event types: run_start | test_result | run_complete
    """
    redis = get_redis()
    msg_id = await redis.xadd(
        LIVE_EVENTS_STREAM,
        {
            "run_id": run_id,
            "event_type": event.get("type", "test_result"),
            # Serialise the full payload — consumers decode it
            "payload": json.dumps(event),
        },
        maxlen=LIVE_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug("Published live event run=%s type=%s id=%s", run_id, event.get("type"), msg_id)
    return msg_id


async def publish_ingestion_job(sentinel_dict: dict, minio_prefix: str) -> str:
    """
    Publish a test report ingestion job to the ingestion stream.
    Called by the webhook handler after a sentinel file is uploaded.
    """
    redis = get_redis()
    msg_id = await redis.xadd(
        INGESTION_STREAM,
        {
            "sentinel": json.dumps(sentinel_dict),
            "minio_prefix": minio_prefix,
        },
        maxlen=INGESTION_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug("Published ingestion job prefix=%s id=%s", minio_prefix, msg_id)
    return msg_id


async def publish_analysis_request(
    test_case_id: str,
    test_name: str,
    run_id: str,
    project_id: str,
    priority: str = "normal",
) -> str:
    """
    Publish a single-test analysis request.
    Used by both the live consumer (immediate analysis on failure) and
    the offline pipeline (batch analysis after ingestion).
    """
    redis = get_redis()
    msg_id = await redis.xadd(
        ANALYSIS_STREAM,
        {
            "test_case_id": test_case_id,
            "test_name": test_name,
            "run_id": run_id,
            "project_id": project_id,
            "priority": priority,
        },
        maxlen=ANALYSIS_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug("Published analysis request test=%s id=%s", test_name, msg_id)
    return msg_id


async def publish_to_dlq(
    source_stream: str,
    original_msg_id: str,
    original_data: dict[str, Any],
    error: str,
    attempt_count: int,
) -> str:
    """
    Move an unprocessable message to the dead-letter queue.
    DLQ entries are retained for 24h for manual inspection and replay.
    """
    redis = get_redis()
    msg_id = await redis.xadd(
        DLQ_STREAM,
        {
            "source_stream": source_stream,
            "original_msg_id": original_msg_id,
            "original_data": json.dumps(original_data),
            "error": str(error)[:1000],
            "attempt_count": str(attempt_count),
        },
        maxlen=DLQ_STREAM_MAXLEN,
        approximate=True,
    )
    logger.error(
        "DLQ: stream=%s msg=%s attempts=%d error=%s",
        source_stream, original_msg_id, attempt_count, error,
    )
    return msg_id


async def get_stream_info() -> dict:
    """Return length and lag info for all streams (for monitoring/health endpoint)."""
    redis = get_redis()
    info = {}
    for name, stream in [
        ("live_events", LIVE_EVENTS_STREAM),
        ("ingestion", INGESTION_STREAM),
        ("analysis", ANALYSIS_STREAM),
        ("dlq", DLQ_STREAM),
    ]:
        try:
            length = await redis.xlen(stream)
            info[name] = {"length": length, "stream": stream}
        except Exception:
            info[name] = {"length": -1, "stream": stream, "error": "unavailable"}
    return info
