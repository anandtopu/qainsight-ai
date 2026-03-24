"""
Conversation Agent — Chat interface for test analysis.

Answers natural-language questions about test results using:
  1. Structured queries against PostgreSQL (recent runs, failures, trends)
  2. MongoDB AI analysis payloads and run summaries
  3. ChromaDB semantic similarity search (when available)

The LLM synthesises retrieved context into a clear answer with source references.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import func, select

from app.core.config import settings
from app.db.mongo import Collections, get_mongo_db
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import (
    AIAnalysis, ChatMessage, ChatSession, Project, TestCase, TestRun,
)
from app.services.llm_factory import get_llm

logger = logging.getLogger("agents.conversation")

_SYSTEM = """\
You are QA Insight AI, an expert assistant for software quality analysis.
You have access to live test data from the QA platform. Always base your answers
on the provided context — do not hallucinate metrics or test names.
If the context is insufficient, say so clearly.
Format your response in markdown. Keep answers concise and actionable.
"""


class ConversationAgent:
    """
    Stateful conversation agent. Sessions are persisted to PostgreSQL.
    """

    async def chat(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
        project_id: Optional[str] = None,
    ) -> dict:
        """
        Process one user message and return the assistant reply.
        Stores both messages to the chat_messages table.
        """
        # Save user message
        await self._save_message(session_id, "user", user_message, sources=None)

        # Gather context
        context, sources = await self._retrieve_context(user_message, project_id)

        # Build message history for the LLM
        history = await self._load_recent_history(session_id, limit=10)

        messages = [SystemMessage(content=_SYSTEM + f"\n\n## Retrieved Context\n{context}")]
        for msg in history:
            cls = HumanMessage if msg["role"] == "user" else AIMessage
            messages.append(cls(content=msg["content"]))
        messages.append(HumanMessage(content=user_message))

        # Invoke LLM
        try:
            llm = get_llm()
            response = await llm.ainvoke(messages)
            reply = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            logger.error("LLM invocation failed: %s", exc)
            reply = "I'm having trouble connecting to the AI provider. Please try again."
            sources = []

        # Save assistant reply
        await self._save_message(session_id, "assistant", reply, sources=sources)

        # Update session updated_at
        await self._touch_session(session_id)

        return {"reply": reply, "sources": sources}

    # ── Context retrieval ──────────────────────────────────────────

    async def _retrieve_context(
        self, query: str, project_id: Optional[str]
    ) -> tuple[str, list[dict]]:
        """Multi-source retrieval: PostgreSQL + MongoDB."""
        parts: list[str] = []
        sources: list[dict] = []

        # 1. Recent test runs
        run_ctx, run_sources = await self._fetch_run_context(query, project_id)
        if run_ctx:
            parts.append(f"### Recent Test Runs\n{run_ctx}")
            sources.extend(run_sources)

        # 2. AI analysis findings
        analysis_ctx, analysis_sources = await self._fetch_analysis_context(query, project_id)
        if analysis_ctx:
            parts.append(f"### AI Analysis Findings\n{analysis_ctx}")
            sources.extend(analysis_sources)

        # 3. Run summaries from MongoDB
        summary_ctx = await self._fetch_run_summaries(project_id)
        if summary_ctx:
            parts.append(f"### Latest Run Summary\n{summary_ctx}")

        # 4. Semantic search via ChromaDB (optional)
        semantic_ctx = await self._semantic_search(query)
        if semantic_ctx:
            parts.append(f"### Semantically Similar Failures\n{semantic_ctx}")

        context = "\n\n".join(parts) if parts else "No relevant data found."
        return context, sources[:5]

    async def _fetch_run_context(
        self, query: str, project_id: Optional[str]
    ) -> tuple[str, list[dict]]:
        """Fetch recent test run stats from PostgreSQL."""
        try:
            async with AsyncSessionLocal() as db:
                q = (
                    select(
                        TestRun.id,
                        TestRun.build_number,
                        TestRun.branch,
                        TestRun.status,
                        TestRun.total_tests,
                        TestRun.failed_tests,
                        TestRun.pass_rate,
                        TestRun.created_at,
                    )
                    .order_by(TestRun.created_at.desc())
                    .limit(5)
                )
                if project_id:
                    q = q.where(TestRun.project_id == project_id)

                result = await db.execute(q)
                rows = result.all()

                if not rows:
                    return "", []

                lines = []
                src = []
                for r in rows:
                    lines.append(
                        f"- Build {r.build_number} ({r.branch or '?'}) | "
                        f"Status: {r.status} | "
                        f"{r.total_tests} tests, {r.failed_tests} failures, "
                        f"{r.pass_rate:.1f}% pass | {r.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )
                    src.append({"type": "test_run", "id": str(r.id), "build": r.build_number})

                return "\n".join(lines), src
        except Exception as exc:
            logger.debug("Run context fetch error: %s", exc)
            return "", []

    async def _fetch_analysis_context(
        self, query: str, project_id: Optional[str]
    ) -> tuple[str, list[dict]]:
        """Fetch recent AI analysis results."""
        try:
            async with AsyncSessionLocal() as db:
                q = (
                    select(
                        AIAnalysis.root_cause_summary,
                        AIAnalysis.failure_category,
                        AIAnalysis.confidence_score,
                        AIAnalysis.recommended_actions,
                        AIAnalysis.test_case_id,
                        TestCase.test_name,
                    )
                    .join(TestCase, TestCase.id == AIAnalysis.test_case_id)
                    .where(AIAnalysis.confidence_score >= 50)
                    .order_by(AIAnalysis.created_at.desc())
                    .limit(5)
                )
                if project_id:
                    q = q.join(TestRun, TestRun.id == TestCase.test_run_id).where(
                        TestRun.project_id == project_id
                    )

                result = await db.execute(q)
                rows = result.all()

                if not rows:
                    return "", []

                lines = []
                src = []
                for r in rows:
                    actions = ", ".join((r.recommended_actions or [])[:2])
                    lines.append(
                        f"- **{r.test_name}** [{r.failure_category}, {r.confidence_score}%]: "
                        f"{r.root_cause_summary or 'No summary'}. Actions: {actions}"
                    )
                    src.append({"type": "ai_analysis", "test_case_id": str(r.test_case_id)})

                return "\n".join(lines), src
        except Exception as exc:
            logger.debug("Analysis context fetch error: %s", exc)
            return "", []

    async def _fetch_run_summaries(self, project_id: Optional[str]) -> str:
        """Fetch the most recent run summary from MongoDB."""
        try:
            db = get_mongo_db()
            query = {}
            if project_id:
                query["project_id"] = project_id

            doc = await db[Collections.RUN_SUMMARIES].find_one(
                query,
                sort=[("generated_at", -1)],
            )
            if doc:
                return doc.get("executive_summary", "")
        except Exception as exc:
            logger.debug("Run summary fetch error: %s", exc)
        return ""

    async def _semantic_search(self, query: str) -> str:
        """ChromaDB semantic similarity search (optional — graceful if unavailable)."""
        try:
            from chromadb import HttpClient  # type: ignore
            from app.services.llm_factory import get_embedding_model

            client = HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            collection = client.get_or_create_collection(settings.CHROMA_COLLECTION)
            if collection.count() == 0:
                return ""

            embedder = get_embedding_model()
            vector = embedder.embed_query(query)
            results = collection.query(query_embeddings=[vector], n_results=3)

            docs = results.get("documents", [[]])[0]
            if docs:
                return "\n".join(f"- {d[:300]}" for d in docs)
        except Exception:
            pass
        return ""

    # ── Persistence helpers ────────────────────────────────────────

    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[list],
    ) -> None:
        async with AsyncSessionLocal() as db:
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                sources=sources,
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg)
            await db.commit()

    async def _load_recent_history(self, session_id: str, limit: int = 10) -> list[dict]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ChatMessage.role, ChatMessage.content)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = result.all()
            return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    async def _touch_session(self, session_id: str) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.updated_at = datetime.now(timezone.utc)
                await db.commit()
