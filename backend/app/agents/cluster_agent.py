"""
Stage 2b: Failure Clustering Agent.
Embeds all error messages for the run and groups them into semantic failure clusters.
Reduces O(n) LLM calls → O(k) deep investigations where k << n.
"""
import json
import logging

from app.agents.base import BaseAgent
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import TestCase
from app.tools.embed_and_cluster import embed_and_cluster

logger = logging.getLogger("agents.cluster")


class ClusterAgent(BaseAgent):
    stage_name = "failure_clustering"

    async def run(self, state: dict) -> dict:
        pipeline_run_id: str = state["pipeline_run_id"]
        project_id: str = state["project_id"]
        failed_test_ids: list[str] = state.get("failed_test_ids", [])

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(project_id, {"status": "running", "message": "Clustering failure patterns..."})

        if not failed_test_ids:
            await self.mark_stage_done(pipeline_run_id, result_data={"clusters": 0})
            return {"failure_clusters": [], "cluster_map": {}}

        # Fetch error messages for all failed tests
        test_id_to_error: dict[str, str] = {}
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(TestCase.id, TestCase.test_name, TestCase.error_message)
                .where(TestCase.id.in_(failed_test_ids))
            )
            for row in result:
                tc_id = str(row.id)
                error = row.error_message or f"Test '{row.test_name}' failed with no error message"
                test_id_to_error[tc_id] = error

        test_ids = list(test_id_to_error.keys())
        errors = [test_id_to_error[tid] for tid in test_ids]

        # Call the clustering tool
        try:
            result_json = await embed_and_cluster.ainvoke({
                "error_messages_json": json.dumps({"test_ids": test_ids, "error_messages": errors})
            })
            result_data = json.loads(result_json)
            clusters = result_data.get("clusters", [])
        except Exception as exc:
            logger.warning("Clustering failed, treating each test as its own cluster: %s", exc)
            clusters = [
                {
                    "cluster_id": f"cl_{i+1:03d}",
                    "label": errors[i][:80] if i < len(errors) else "unknown",
                    "member_test_ids": [test_ids[i]],
                    "representative_error": errors[i][:300] if i < len(errors) else "",
                    "size": 1,
                }
                for i in range(len(test_ids))
            ]

        # Build reverse map: test_id → cluster_id
        cluster_map: dict[str, str] = {}
        for cluster in clusters:
            for tid in cluster.get("member_test_ids", []):
                cluster_map[tid] = cluster["cluster_id"]

        logger.info(
            "Pipeline %s: clustered %d failures into %d clusters",
            pipeline_run_id, len(failed_test_ids), len(clusters),
        )
        await self.mark_stage_done(
            pipeline_run_id,
            result_data={"cluster_count": len(clusters), "failure_count": len(failed_test_ids)},
        )
        await self.broadcast_progress(project_id, {
            "status": "completed",
            "message": f"Grouped {len(failed_test_ids)} failures into {len(clusters)} clusters",
        })

        return {"failure_clusters": clusters, "cluster_map": cluster_map}
