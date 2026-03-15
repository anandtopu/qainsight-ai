"""Async MongoDB client using Motor."""
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase  # type: ignore

from app.core.config import settings

_client: Optional[AsyncIOMotorClient] = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
        )
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_mongo_client()[settings.MONGO_DB]


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


# Collection name constants
class Collections:
    RAW_ALLURE_JSON = "raw_allure_json"
    RAW_TESTNG_XML = "raw_testng_xml"
    REST_API_PAYLOADS = "rest_api_payloads"
    EXECUTION_LOGS = "execution_logs"
    AI_ANALYSIS_PAYLOADS = "ai_analysis_payloads"
    OCP_POD_EVENTS = "ocp_pod_events"
