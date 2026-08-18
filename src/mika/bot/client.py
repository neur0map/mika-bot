"""Discord client bootstrap: intents, command registration, event wiring."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import discord
import uvicorn
from discord.ext import commands

from mika.ai.learning.reflection.relationship_job import RelationshipObservationJob
from mika.ai.llm.client import LLMClient
from mika.ai.llm.memory.store import LocalMemory
from mika.bot.events import register_events
from mika.bot.scheduler import SchedulerLifecycle, start_schedulers
from mika.conversation.actions import ActionPlanner
from mika.conversation.context import (
    AffinityRetriever,
    ContextSelector,
    MergedRetriever,
    TurnObserver,
)
from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.engine import ConversationEngine
from mika.conversation.participation import ParticipationPlanner
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import RelationshipConsolidator
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.extraction import (
    EvidenceProposal,
    extract_deterministic_evidence,
    is_sensitive_evidence_text,
)
from mika.conversation.relationships.relation import classify_relation
from mika.conversation.relationships.service import ObservationInput, RelationshipMemoryService
from mika.conversation.relationships.telemetry import (
    RelationshipOperationRecord,
    RelationshipTelemetry,
)
from mika.conversation.tools import ToolPlanner
from mika.core.config import get_settings
from mika.core.logging import configure_logging, get_logger
from mika.persistence.conversations.archive_reader import ArchiveReader
from mika.persistence.conversations.managed_relationship_memory import ManagedRelationshipMemory
from mika.persistence.conversations.managed_social_memory import ManagedSocialMemory
from mika.persistence.conversations.managed_traces import ManagedTurnTraceRepository
from mika.persistence.conversations.relationship_records import (
    RelationshipMemoryPolicyVersionRecord,
    RelationshipOperationWrite,
)
from mika.persistence.engine import init_db
from mika.web.app import create_app

logger = get_logger(__name__)


class _DeterministicExtractor:
    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        if is_sensitive_evidence_text(observation.text):
            return ()
        return extract_deterministic_evidence(
            observation.text,
            source_message_id=observation.message_id,
            source_timestamp=observation.created_at,
            relation=relation,
        )


class _DeterministicClassifier:
    def classify(self, observation: ObservationInput) -> RelationDecision:
        return classify_relation(observation.text)


class _ProviderExtractor:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        if is_sensitive_evidence_text(observation.text):
            return ()
        instruction = (
            "Extract relationship-memory evidence as a JSON array. Each item must have kind, key, "
            "value, evidence_class, confidence, and reason. Return [] for sensitive or uncertain "
            "content. Never add facts not explicit in the message."
        )
        raw = await self._client.summarize(instruction, observation.text)
        try:
            values = json.loads(raw)
            if not isinstance(values, list):
                raise ValueError("provider extraction must return a list")
            proposals = tuple(
                EvidenceProposal(
                    kind=str(item["kind"])[:40],
                    key=str(item["key"])[:64],
                    value=str(item["value"])[:120],
                    evidence_class="inference",
                    confidence=min(0.6, max(0.0, float(item["confidence"]))),
                    source_message_id=observation.message_id,
                    source_timestamp=observation.created_at,
                    reason=str(item["reason"])[:80],
                )
                for item in values
                if isinstance(item, dict)
                and item.get("evidence_class")
                in {"explicit", "correction", "repeated_behavior", "reaction", "inference"}
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            proposals = ()
        if proposals:
            return proposals
        deterministic = await _DeterministicExtractor().extract(observation, relation)
        return tuple(
            replace(proposal, reason=f"provider_fallback:invalid_output:{proposal.reason}")
            for proposal in deterministic
        )


class _ServiceRetriever:
    def __init__(self, service: RelationshipMemoryService) -> None:
        self._service = service

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        return await self._service.recall(envelope)


class _OperationSink:
    def __init__(self, repository: ManagedRelationshipMemory) -> None:
        self._repository = repository

    async def __call__(self, record: RelationshipOperationRecord) -> None:
        await self._repository.record_operation_write(
            RelationshipOperationWrite(
                record.operation,
                record.outcome,
                record.correlation_hash,
                record.duration_ms,
                record.candidate_count,
                record.selected_count,
                record.rejected_count,
                record.estimated_tokens,
                record.fallback_reason,
                record.profile_changed,
                record.policy_version_id,
                record.phase_durations_ms,
                record.created_at,
            )
        )


def _relationship_policy() -> RelationshipMemoryPolicyVersionRecord:
    memory = get_settings().memory
    return RelationshipMemoryPolicyVersionRecord(
        policy_version_id=f"policy-{uuid4()}",
        relationship_learning_enabled=memory.relationship_learning_enabled,
        semantic_retrieval_enabled=False,
        provider_extraction_enabled=memory.relationship_provider_extraction_enabled,
        local_relation_model_enabled=False,
        visibility_rules={
            "guild": True,
            "direct_message": memory.relationship_direct_message_enabled,
            "channel": True,
            "global_explicit": True,
            "shadow_mode": memory.relationship_shadow_mode,
        },
        change_reason="runtime_settings",
        created_at=datetime.now(UTC),
    )


class _QuietServer(uvicorn.Server):
    """A uvicorn server that lets the bot process own the shutdown signals."""

    def install_signal_handlers(self) -> None:
        return None


class BotApp(commands.Bot):
    """The bot application: a Discord client plus the LLM brain."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="\u200b", intents=intents, help_command=None)
        settings = get_settings()
        memory = LocalMemory()
        self.social_memory = ManagedSocialMemory()
        self.relationship_memory = ManagedRelationshipMemory()
        relationship_telemetry = RelationshipTelemetry(
            sink=_OperationSink(self.relationship_memory)
        )
        self.llm = LLMClient(memory)
        if settings.memory.relationship_semantic_scoring_enabled:
            logger.warning("relationship semantic scoring is unavailable; using lexical ranking")
        relationship_retriever = AffinityRetriever(
            self.social_memory,
            match_limit=0,
            relationship_source=self.relationship_memory,
            semantic_scorer=None,
        )
        self.relationship_service = RelationshipMemoryService(
            repository=self.relationship_memory,
            extractor=(
                _ProviderExtractor(self.llm)
                if settings.memory.relationship_provider_extraction_enabled
                else _DeterministicExtractor()
            ),
            activation_policy=ActivationPolicy(),
            classifier=_DeterministicClassifier(),
            retriever=relationship_retriever,
            consolidator=RelationshipConsolidator(),
            pending_source=(
                ArchiveReader(settings.shared_archive_path)
                if settings.shared_archive_path is not None
                and settings.shared_archive_path.is_file()
                else None
            ),
            batch_size=settings.memory.relationship_batch_size,
            telemetry=relationship_telemetry,
        )
        self.relationship_job = RelationshipObservationJob(
            self.relationship_service,
            max_queue_size=settings.memory.relationship_batch_size,
            enabled=settings.memory.relationship_learning_enabled,
            consolidation_interval_seconds=(
                settings.memory.relationship_consolidation_interval_seconds
            ),
            telemetry=self.relationship_service.telemetry,
            spool_path=settings.data_dir / "relationship-observations.sqlite3",
        )
        actions = ActionPlanner()
        self.conversation = ConversationEngine(
            ContextSelector(
                memory,
                retriever=MergedRetriever(
                    AffinityRetriever(self.social_memory),
                    _ServiceRetriever(self.relationship_service),
                ),
            ),
            ParticipationPlanner(),
            ToolPlanner(),
            self.llm,
            actions,
            TurnObserver(
                memory,
                assistant_name=settings.persona.name,
                facts=self.social_memory,
                relationships=self.relationship_job,
            ),
            ManagedTurnTraceRepository(),
        )
        self._web_task: asyncio.Task[None] | None = None
        self._schedulers: SchedulerLifecycle | None = None

    async def setup_hook(self) -> None:
        await init_db()
        await self.relationship_memory.ensure_policy_version(_relationship_policy())
        await self.llm.startup()
        self._schedulers = start_schedulers(self)
        self._start_web()

    def _start_web(self) -> None:
        """Serve the dashboard in the background so one service runs the bot + panel."""
        web = get_settings().web
        if not web.enabled:
            return
        config = uvicorn.Config(create_app(), host=web.host, port=web.port, log_level="warning")
        server = _QuietServer(config)
        self._web_task = asyncio.create_task(self._serve_web(server), name="dashboard")
        logger.info("dashboard on http://%s:%s", web.host, web.port)

    async def _serve_web(self, server: _QuietServer) -> None:
        try:
            await server.serve()
        except (SystemExit, OSError) as error:
            # port already in use, etc. - uvicorn calls sys.exit(1); keep the bot alive
            logger.warning(
                "dashboard could not start on port %s (%s); bot continues without it",
                get_settings().web.port,
                error,
            )
        except Exception as error:
            logger.warning("dashboard did not start (bot keeps running): %s", error)

    async def close(self) -> None:
        if self._schedulers is not None:
            await self._schedulers.close()
            self._schedulers = None
        if self._web_task is not None:
            self._web_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._web_task
        with contextlib.suppress(Exception):
            await self.llm.shutdown()
        await self.relationship_service.telemetry.flush()
        await super().close()


def run() -> None:
    """Start the bot. Entry point for `mika run`."""
    settings = get_settings()
    configure_logging(settings.log_level)
    token = settings.discord.token
    if not token or token == "CHANGEME":  # noqa: S105
        raise SystemExit("DISCORD_TOKEN is not set. Run `mika setup` first.")
    bot = BotApp()
    register_events(bot)
    try:
        bot.run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired as error:
        raise SystemExit(
            "Discord rejected the bot: a required intent is OFF.\n"
            "Fix: Developer Portal -> your app -> Bot -> Privileged Gateway Intents ->\n"
            "turn ON 'MESSAGE CONTENT INTENT', save, then run `mika run` again."
        ) from error
    except discord.LoginFailure as error:
        raise SystemExit("Discord rejected the token. Re-check it with `mika setup`.") from error
