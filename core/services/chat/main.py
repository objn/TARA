from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from core.configs.settings import ENV, Env
from core.services.agents.main import Agent, AgentRunResult
from core.services.agents.tools.remote_tools import register_mcp_tools
from core.services.provider.openai import provider as default_provider

JsonDict = Dict[str, Any]


def _require_env() -> Env:
    if ENV is not None:
        return ENV
    return Env.load()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


class ChatMode(str, Enum):
    agent = "agent"
    multiagent = "multiagent"


class CreateTopicRequestDTO(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatTopicDTO(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime


class SendMessageRequestDTO(BaseModel):
    topic_id: uuid.UUID
    role: Literal["system", "user", "assistant", "tool", "developer"] = "user"
    content: str = Field(min_length=1)
    agent: Optional[str] = Field(default=None, max_length=80)
    meta: JsonDict = Field(default_factory=dict)


class ChatMessageDTO(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    role: str
    content: str
    agent: Optional[str] = None
    meta: JsonDict = Field(default_factory=dict)
    created_at: datetime


class MultiAgentConfigDTO(BaseModel):
    """
    Minimal multi-agent configuration:
    - agents: ordered list of agent names to run sequentially
    """

    agents: List[str] = Field(min_length=1)


class RunChatRequestDTO(BaseModel):
    topic_id: uuid.UUID
    prompt: str = Field(min_length=1)
    mode: ChatMode = ChatMode.agent
    system: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    multiagent: Optional[MultiAgentConfigDTO] = None


class RunChatResponseDTO(BaseModel):
    topic: ChatTopicDTO
    user_message: ChatMessageDTO
    assistant_message: ChatMessageDTO
    run_id: str
    mode: ChatMode


class ChatStorageError(RuntimeError):
    pass


class ReasoningStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class PostgresConfig:
    url: str


@dataclass(frozen=True)
class RedisConfig:
    url: str
    ttl_seconds: int = 60 * 30


class ChatPostgresStore:
    def __init__(self, cfg: PostgresConfig):
        self.cfg = cfg

        try:
            import psycopg  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "Missing Postgres dependency. Install: `pip install psycopg[binary]`"
            ) from e

        self._psycopg = psycopg

    def _connect(self):
        # autocommit keeps usage simple for this lightweight store
        return self._psycopg.connect(self.cfg.url, autocommit=True)

    def ensure_schema(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS public.chat_topics (
          id uuid PRIMARY KEY,
          title text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.chat_messages (
          id uuid PRIMARY KEY,
          topic_id uuid NOT NULL REFERENCES public.chat_topics(id) ON DELETE CASCADE,
          role text NOT NULL,
          content text NOT NULL,
          agent text NULL,
          meta jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_topic_created_at
          ON public.chat_messages(topic_id, created_at ASC);
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
        except Exception as e:  # pragma: no cover
            raise ChatStorageError(str(e)) from e

    def create_topic(self, title: str) -> ChatTopicDTO:
        topic_id = uuid.uuid4()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO public.chat_topics(id, title) VALUES (%s, %s);",
                        (topic_id, title),
                    )
                    cur.execute(
                        "SELECT id, title, created_at FROM public.chat_topics WHERE id=%s;",
                        (topic_id,),
                    )
                    row = cur.fetchone()
        except Exception as e:  # pragma: no cover
            raise ChatStorageError(str(e)) from e

        if not row:  # pragma: no cover
            raise ChatStorageError("Failed to create topic.")

        return ChatTopicDTO(id=row[0], title=row[1], created_at=row[2])

    def get_topic(self, topic_id: uuid.UUID) -> ChatTopicDTO:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, created_at FROM public.chat_topics WHERE id=%s;",
                        (topic_id,),
                    )
                    row = cur.fetchone()
        except Exception as e:  # pragma: no cover
            raise ChatStorageError(str(e)) from e

        if not row:
            raise ChatStorageError("Topic not found.")

        return ChatTopicDTO(id=row[0], title=row[1], created_at=row[2])

    def insert_message(
        self,
        *,
        topic_id: uuid.UUID,
        role: str,
        content: str,
        agent: Optional[str] = None,
        meta: Optional[JsonDict] = None,
    ) -> ChatMessageDTO:
        msg_id = uuid.uuid4()
        meta_json = meta or {}
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.chat_messages(id, topic_id, role, content, agent, meta)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb);
                        """,
                        (msg_id, topic_id, role, content, agent, _json_dumps(meta_json)),
                    )
                    cur.execute(
                        """
                        SELECT id, topic_id, role, content, agent, meta, created_at
                        FROM public.chat_messages WHERE id=%s;
                        """,
                        (msg_id,),
                    )
                    row = cur.fetchone()
        except Exception as e:  # pragma: no cover
            raise ChatStorageError(str(e)) from e

        if not row:  # pragma: no cover
            raise ChatStorageError("Failed to insert message.")

        return ChatMessageDTO(
            id=row[0],
            topic_id=row[1],
            role=row[2],
            content=row[3],
            agent=row[4],
            meta=row[5] or {},
            created_at=row[6],
        )

    def list_messages(self, topic_id: uuid.UUID, *, limit: int = 200) -> List[ChatMessageDTO]:
        limit = max(1, min(int(limit), 1000))
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, topic_id, role, content, agent, meta, created_at
                        FROM public.chat_messages
                        WHERE topic_id=%s
                        ORDER BY created_at ASC
                        LIMIT %s;
                        """,
                        (topic_id, limit),
                    )
                    rows = cur.fetchall() or []
        except Exception as e:  # pragma: no cover
            raise ChatStorageError(str(e)) from e

        return [
            ChatMessageDTO(
                id=r[0],
                topic_id=r[1],
                role=r[2],
                content=r[3],
                agent=r[4],
                meta=r[5] or {},
                created_at=r[6],
            )
            for r in rows
        ]


class ReasoningRedisStore:
    def __init__(self, cfg: RedisConfig):
        self.cfg = cfg
        try:
            import redis  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError("Missing Redis dependency. Install: `pip install redis`") from e

        self._redis = redis
        self._client = self._redis.Redis.from_url(self.cfg.url, decode_responses=True)

    def _key(self, topic_id: uuid.UUID, run_id: str) -> str:
        return f"tara:chat:{topic_id}:run:{run_id}:reasoning"

    def put(self, *, topic_id: uuid.UUID, run_id: str, payload: JsonDict) -> None:
        k = self._key(topic_id, run_id)
        try:
            self._client.set(k, _json_dumps(payload), ex=int(self.cfg.ttl_seconds))
        except Exception as e:  # pragma: no cover
            raise ReasoningStoreError(str(e)) from e

    def get(self, *, topic_id: uuid.UUID, run_id: str) -> Optional[JsonDict]:
        k = self._key(topic_id, run_id)
        try:
            raw = self._client.get(k)
        except Exception as e:  # pragma: no cover
            raise ReasoningStoreError(str(e)) from e
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {"_value": obj}
        except Exception:
            return {"raw": raw}


class NoOpReasoningStore:
    def put(self, *, topic_id: uuid.UUID, run_id: str, payload: JsonDict) -> None:
        _ = (topic_id, run_id, payload)

    def get(self, *, topic_id: uuid.UUID, run_id: str) -> Optional[JsonDict]:
        _ = (topic_id, run_id)
        return None


class RunStateRedisStore:
    """Ephemeral orchestration snapshot per run_id (TTL). Key: tara:run:{run_id}:state"""

    def __init__(self, cfg: RedisConfig):
        self.cfg = cfg
        try:
            import redis  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError("Missing Redis dependency. Install: `pip install redis`") from e

        self._redis = redis
        self._client = self._redis.Redis.from_url(self.cfg.url, decode_responses=True)

    def _key(self, run_id: str) -> str:
        return f"tara:run:{run_id}:state"

    def put(self, *, run_id: str, payload: JsonDict) -> None:
        k = self._key(run_id)
        try:
            self._client.set(k, _json_dumps(payload), ex=int(self.cfg.ttl_seconds))
        except Exception as e:  # pragma: no cover
            raise ReasoningStoreError(str(e)) from e

    def delete(self, *, run_id: str) -> None:
        try:
            self._client.delete(self._key(run_id))
        except Exception as e:  # pragma: no cover
            raise ReasoningStoreError(str(e)) from e


class NoOpRunStateStore:
    def put(self, *, run_id: str, payload: JsonDict) -> None:
        _ = (run_id, payload)

    def delete(self, *, run_id: str) -> None:
        _ = run_id


def _format_context(messages: Sequence[ChatMessageDTO], *, max_chars: int = 8000) -> str:
    # Keep it deterministic, compact, and safe.
    lines: List[str] = []
    for m in messages:
        role = (m.role or "").strip().lower()
        who = f"{role}"
        if m.agent:
            who += f"({m.agent})"
        content = (m.content or "").strip()
        if not content:
            continue
        lines.append(f"{who}: {content}")
    s = "\n".join(lines).strip()
    if len(s) <= max_chars:
        return s
    return s[-max_chars:]


class MultiAgentOrchestrator:
    """
    Minimal sequential orchestrator:
    - runs named agents in order
    - each agent sees the same chat context + prompt + previous agent output
    """

    def __init__(self, *, agents: Dict[str, Agent]):
        self.agents = agents

    def run(
        self,
        *,
        agent_names: Sequence[str],
        prompt: str,
        context: str,
        model: Optional[str],
        reasoning_effort: Optional[str],
    ) -> Tuple[str, Dict[str, AgentRunResult]]:
        results: Dict[str, AgentRunResult] = {}
        carry = ""
        for name in agent_names:
            agent = self.agents.get(name)
            if not agent:
                raise ValueError(f"Unknown agent: {name}")

            task = prompt.strip()
            if context:
                task = f"{task}\n\n[chat_context]\n{context}"
            if carry:
                task = f"{task}\n\n[previous_agent_output]\n{carry}"

            res = agent.run(task, model=model, reasoning_effort=reasoning_effort)
            results[name] = res
            carry = res.final_answer.strip()

        return carry, results


class ChatService:
    def __init__(
        self,
        *,
        pg: Optional[ChatPostgresStore] = None,
        reasoning: Optional[ReasoningRedisStore] = None,
        run_state: Optional[RunStateRedisStore] = None,
        provider=default_provider,
    ):
        cfg = _require_env()

        if pg is None:
            if not cfg.DATABASE_URL:
                raise ChatStorageError("DATABASE_URL is not set.")
            pg = ChatPostgresStore(PostgresConfig(url=cfg.DATABASE_URL))
        if reasoning is None:
            if not cfg.REDIS_URL:
                if cfg.DATASTORE_FAIL_MODE == "degraded":
                    reasoning = NoOpReasoningStore()  # type: ignore[assignment]
                else:
                    raise ReasoningStoreError("REDIS_URL is not set.")
            else:
                reasoning = ReasoningRedisStore(
                    RedisConfig(url=cfg.REDIS_URL, ttl_seconds=int(cfg.REDIS_REASONING_TTL_SECONDS))
                )

        if run_state is None:
            if not cfg.REDIS_URL:
                if cfg.DATASTORE_FAIL_MODE == "degraded":
                    run_state = NoOpRunStateStore()  # type: ignore[assignment]
                else:
                    run_state = None
            else:
                state_ttl = int(cfg.REDIS_RUN_STATE_TTL_SECONDS or cfg.REDIS_REASONING_TTL_SECONDS)
                run_state = RunStateRedisStore(RedisConfig(url=cfg.REDIS_URL, ttl_seconds=state_ttl))

        self.pg = pg
        self.reasoning = reasoning
        self.run_state = run_state
        self.provider = provider
        self._cfg = cfg

        # Default single agent registry (can be extended by caller)
        self._agents: Dict[str, Agent] = {"default": Agent(provider=self.provider)}
        try:
            register_mcp_tools(self._agents["default"])
        except Exception:
            pass

    def register_agent(self, name: str, agent: Agent) -> None:
        self._agents[name] = agent

    def ensure_schema(self) -> None:
        self.pg.ensure_schema()

    def create_topic(self, title: str) -> ChatTopicDTO:
        self.ensure_schema()
        return self.pg.create_topic(title=title)

    def send_message(self, req: SendMessageRequestDTO) -> ChatMessageDTO:
        self.ensure_schema()
        _ = self.pg.get_topic(req.topic_id)
        return self.pg.insert_message(
            topic_id=req.topic_id,
            role=req.role,
            content=req.content,
            agent=req.agent,
            meta=req.meta,
        )

    def list_messages(self, topic_id: uuid.UUID, *, limit: int = 200) -> List[ChatMessageDTO]:
        self.ensure_schema()
        _ = self.pg.get_topic(topic_id)
        return self.pg.list_messages(topic_id, limit=limit)

    def run_chat(self, req: RunChatRequestDTO) -> RunChatResponseDTO:
        self.ensure_schema()
        topic = self.pg.get_topic(req.topic_id)

        # 1) Save user message.
        user_msg = self.pg.insert_message(
            topic_id=req.topic_id,
            role="user",
            content=req.prompt,
            agent=None,
            meta={"system": req.system} if req.system else {},
        )

        # 2) Build context.
        messages = self.pg.list_messages(req.topic_id, limit=200)
        context = _format_context(messages)

        # 3) Run agent(s).
        run_id = uuid.uuid4().hex
        started_at = time.time()

        if self.run_state is not None:
            try:
                self.run_state.put(
                    run_id=run_id,
                    payload={
                        "status": "running",
                        "topic_id": str(req.topic_id),
                        "mode": str(req.mode),
                    },
                )
            except ReasoningStoreError:
                if self._cfg.DATASTORE_FAIL_MODE == "strict":
                    raise

        if req.mode == ChatMode.agent:
            agent = self._agents.get("default") or Agent(provider=self.provider)
            task = req.prompt.strip()
            if context:
                task = f"{task}\n\n[chat_context]\n{context}"
            if req.system:
                task = f"[system]\n{req.system.strip()}\n\n{task}"

            res = agent.run(task, model=req.model, reasoning_effort=req.reasoning_effort)
            final_answer = res.final_answer.strip()
            reasoning_payload: JsonDict = {
                "mode": "agent",
                "run_id": run_id,
                "topic_id": str(req.topic_id),
                "elapsed_ms": int((time.time() - started_at) * 1000),
                "reasoning": {
                    "problem_definition": res.reasoning.problem_definition,
                    "planning": res.reasoning.planning,
                    "analysis_and_design": res.reasoning.analysis_and_design,
                    "implementation": res.reasoning.implementation,
                    "testing": res.reasoning.testing,
                    "reporting": res.reasoning.reporting,
                    "assumptions": res.reasoning.assumptions,
                    "raw_json": res.reasoning.raw_json,
                },
                "tool_steps": [
                    {"tool": s.tool, "args": s.args, "result": s.result} for s in (res.steps or [])
                ],
                "raw_messages": res.raw_messages,
            }
            try:
                self.reasoning.put(topic_id=req.topic_id, run_id=run_id, payload=reasoning_payload)
            except ReasoningStoreError:
                if self._cfg.DATASTORE_FAIL_MODE == "strict":
                    raise

        elif req.mode == ChatMode.multiagent:
            cfg = req.multiagent or MultiAgentConfigDTO(agents=["default"])
            orch = MultiAgentOrchestrator(agents=self._agents)
            final_answer, results = orch.run(
                agent_names=cfg.agents,
                prompt=req.prompt,
                context=context if not req.system else f"[system]\n{req.system.strip()}\n\n{context}",
                model=req.model,
                reasoning_effort=req.reasoning_effort,
            )

            reasoning_payload = {
                "mode": "multiagent",
                "run_id": run_id,
                "topic_id": str(req.topic_id),
                "elapsed_ms": int((time.time() - started_at) * 1000),
                "agents": cfg.agents,
                "by_agent": {
                    name: {
                        "final_answer": r.final_answer,
                        "reasoning": {
                            "problem_definition": r.reasoning.problem_definition,
                            "planning": r.reasoning.planning,
                            "analysis_and_design": r.reasoning.analysis_and_design,
                            "implementation": r.reasoning.implementation,
                            "testing": r.reasoning.testing,
                            "reporting": r.reasoning.reporting,
                            "assumptions": r.reasoning.assumptions,
                            "raw_json": r.reasoning.raw_json,
                        },
                        "tool_steps": [
                            {"tool": s.tool, "args": s.args, "result": s.result} for s in (r.steps or [])
                        ],
                        "raw_messages": r.raw_messages,
                    }
                    for name, r in results.items()
                },
            }
            try:
                self.reasoning.put(topic_id=req.topic_id, run_id=run_id, payload=reasoning_payload)
            except ReasoningStoreError:
                if self._cfg.DATASTORE_FAIL_MODE == "strict":
                    raise

        else:  # pragma: no cover
            raise ValueError(f"Unsupported mode: {req.mode}")

        if self.run_state is not None:
            try:
                self.run_state.delete(run_id=run_id)
            except ReasoningStoreError:
                if self._cfg.DATASTORE_FAIL_MODE == "strict":
                    raise

        # 4) Save assistant message.
        assistant_msg = self.pg.insert_message(
            topic_id=req.topic_id,
            role="assistant",
            content=final_answer,
            agent="multiagent" if req.mode == ChatMode.multiagent else "default",
            meta={"run_id": run_id},
        )

        return RunChatResponseDTO(
            topic=topic,
            user_message=user_msg,
            assistant_message=assistant_msg,
            run_id=run_id,
            mode=req.mode,
        )

