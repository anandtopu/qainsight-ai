"""
Redis Streams infrastructure for event-driven, fault-tolerant processing.

Stream names and consumer group constants used across producers and consumers.
"""

# ── Stream names ──────────────────────────────────────────────────────────────
LIVE_EVENTS_STREAM  = "qainsight:stream:live_events"   # live test execution events
INGESTION_STREAM    = "qainsight:stream:ingestion_jobs" # report upload notifications
ANALYSIS_STREAM     = "qainsight:stream:analysis_tasks" # per-test analysis requests
DLQ_STREAM          = "qainsight:stream:dlq"            # dead-letter queue

# ── Consumer group names ──────────────────────────────────────────────────────
LIVE_GROUP      = "live-processors"
INGESTION_GROUP = "ingestion-processors"
ANALYSIS_GROUP  = "analysis-processors"

# ── Redis key namespaces ──────────────────────────────────────────────────────
LIVE_STATE_KEY  = "qainsight:live:state:{run_id}"   # Hash per active run
LIVE_ACTIVE_SET = "qainsight:live:active"           # Set of active run IDs
DEDUP_KEY       = "qainsight:dedup:{task}:{key}"    # Deduplication locks
CIRCUIT_KEY     = "qainsight:circuit:llm"           # Circuit breaker state

# ── Limits ────────────────────────────────────────────────────────────────────
LIVE_STREAM_MAXLEN      = 100_000   # max entries retained in live stream
INGESTION_STREAM_MAXLEN = 10_000
ANALYSIS_STREAM_MAXLEN  = 50_000
DLQ_STREAM_MAXLEN       = 5_000

# ── Consumer settings ─────────────────────────────────────────────────────────
CONSUMER_BATCH_SIZE     = 50        # messages read per iteration
CONSUMER_BLOCK_MS       = 1_000     # block timeout for XREADGROUP
STALE_CLAIM_INTERVAL_S  = 30        # seconds between XAUTOCLAIM sweeps
STALE_IDLE_MS           = 30_000    # messages idle > this get reclaimed
MAX_DELIVERY_ATTEMPTS   = 3         # move to DLQ after this many failures
