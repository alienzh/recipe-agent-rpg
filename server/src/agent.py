"""
Agent — RPG DM Recipe

High-level API for managing Agora Conversational AI Agents with managed OpenAI
and RPG game tool calling. Agora cloud orchestrates the MCP server — the managed
OpenAI LLM emits a tool call, Agora invokes the separate mcp/ server (public
MCP_ENDPOINT), returns the result, and the Dungeon Master speaks it.

OPENAI_API_KEY is optional — Agora manages the OpenAI key (keyless).
MCP_ENDPOINT must be PUBLIC — Agora cloud (not this server) calls it.
"""
import logging
import os
from typing import Any, Dict, Optional

from agora_agent import Area, AsyncAgora
from agora_agent.agentkit import Agent as AgoraAgent
from agora_agent.agentkit.vendors import OpenAI, DeepgramSTT, MiniMaxTTS
from mcp_config import build_mcp_servers

logger = logging.getLogger("uvicorn.error")

AGENT_GREETING = "Welcome, adventurer! I'm your Dungeon Master. Choose your class — warrior, mage, rogue, or cleric — and we begin."


class Agent:
    """
    High-level wrapper for Agora Conversational AI Agent with managed OpenAI
    and RPG game tool calling (Dungeon Master).

    The managed OpenAI vendor is keyless — Agora handles the API key. When the
    player takes an action, the DM LLM emits a tool call, Agora invokes the
    mcp/ server at MCP_ENDPOINT, and the game result is returned to the LLM so
    it can narrate the outcome.

    IMPORTANT: MCP_ENDPOINT must be publicly accessible for the Agora
    Conversational AI Engine (cloud) to reach the mcp/ server. For local
    development, use a tunnel (ngrok) — e.g. ngrok http 8001 — and paste
    the public URL here.
    """

    def __init__(self):
        self.app_id = os.getenv("AGORA_APP_ID")
        self.app_certificate = os.getenv("AGORA_APP_CERTIFICATE")
        self.greeting = os.getenv("AGENT_GREETING", AGENT_GREETING)

        # OpenAI is Agora-managed (keyless). OPENAI_API_KEY optional.
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # MCP_ENDPOINT must be PUBLIC — Agora cloud calls the mcp/ server directly.
        self.mcp_endpoint = os.getenv("MCP_ENDPOINT")
        if not self.mcp_endpoint:
            raise ValueError(
                "MCP_ENDPOINT is required (public URL of your mcp/ server, "
                "e.g. https://<tunnel>/mcp)"
            )

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")

        self.client = AsyncAgora(
            area=Area.US,
            app_id=self.app_id,
            app_certificate=self.app_certificate,
        )

        # Track active sessions by agent_id
        self._sessions: Dict[str, Any] = {}

    async def start(
        self,
        channel_name: str,
        agent_uid: int,
        user_uid: int,
        output_audio_codec: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start RPG DM agent with managed OpenAI + game tool calling."""
        if not channel_name or not str(channel_name).strip():
            raise ValueError("channel_name is required and cannot be empty")
        if agent_uid <= 0:
            raise ValueError("agent_uid is required and cannot be empty")
        if user_uid <= 0:
            raise ValueError("user_uid is required and cannot be empty")

        llm = OpenAI(
            api_key=self.openai_api_key,
            model=self.openai_model,
            system_messages=[{"role": "system", "content": (
                "You are a dramatic but concise voice Dungeon Master running a fantasy RPG. "
                "You narrate vividly in 1-3 sentences. CRITICAL: you MUST use the game tools to "
                "resolve every mechanic and NEVER invent dice rolls, damage, HP, gold, loot, or "
                "outcomes. Call create_character when the player picks a class; start_encounter to "
                "begin a fight; attack or cast_spell during combat; flee to escape; get_character "
                "for stats or inventory. After a tool returns, narrate ONLY what it reported. If the "
                "player has no character yet, ask them to choose warrior, mage, rogue, or cleric."
            )}],
            mcp_servers=build_mcp_servers(self.mcp_endpoint),
            greeting_message=self.greeting,
        )

        stt = DeepgramSTT(model="nova-3", language="en")
        tts = MiniMaxTTS(model="speech_2_6_turbo", voice_id="English_captivating_female1")

        parameters = {
            "audio_scenario": "chorus",  # web client — ultra-low-latency chorus profile
            "data_channel": "rtm",
            "enable_error_message": True,
            "enable_metrics": True,
        }
        if isinstance(output_audio_codec, str) and output_audio_codec.strip():
            parameters["output_audio_codec"] = output_audio_codec.strip()

        agora_agent = AgoraAgent(
            client=self.client,
            greeting=self.greeting,
            failure_message="Please wait a moment.",
            max_history=50,
            turn_detection={
                "config": {
                    "speech_threshold": 0.5,
                    "start_of_speech": {
                        "mode": "vad",
                        "vad_config": {
                            "interrupt_duration_ms": 160,
                            "prefix_padding_ms": 300,
                        },
                    },
                    "end_of_speech": {
                        "mode": "vad",
                        "vad_config": {
                            "silence_duration_ms": 480,
                        },
                    },
                },
            },
            advanced_features={"enable_rtm": True, "enable_tools": True},
            parameters=parameters,
        )

        agora_agent = (
            agora_agent
            .with_stt(stt)
            .with_llm(llm)
            .with_tts(tts)
        )

        session = agora_agent.create_async_session(
            channel=channel_name,
            agent_uid=str(agent_uid),
            remote_uids=[str(user_uid)],
            enable_string_uid=False,
            idle_timeout=30,
            expires_in=3600,
        )

        logger.info(
            "Starting RPG DM agent channel=%s agent_uid=%s user_uid=%s mcp_endpoint=%s",
            channel_name,
            agent_uid,
            user_uid,
            self.mcp_endpoint,
        )

        try:
            agent_id = await session.start()
        except Exception:
            logger.exception(
                "Failed to start RPG DM agent channel=%s agent_uid=%s user_uid=%s",
                channel_name,
                agent_uid,
                user_uid,
            )
            raise

        # Save session for later stop
        self._sessions[agent_id] = session

        logger.info(
            "Started RPG DM agent agent_id=%s channel=%s",
            agent_id,
            channel_name,
        )

        return {
            "agent_id": agent_id,
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id: str) -> None:
        """Stop a running agent. Falls back to the stateless client path."""
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id is required and cannot be empty")

        session = self._sessions.pop(agent_id, None)
        if session:
            try:
                await session.stop()
                logger.info("Stopped agent from active session agent_id=%s", agent_id)
                return
            except Exception:
                logger.warning(
                    "Failed to stop agent from active session; falling back agent_id=%s",
                    agent_id,
                    exc_info=True,
                )

        logger.info("Stopping agent through client.stop_agent agent_id=%s", agent_id)
        await self.client.stop_agent(agent_id)
