# Agora Agent Backend — RPG Gaming Recipe

FastAPI service that owns Agora token generation and the Dungeon Master agent
session lifecycle. It is the service the web client reaches through the Next.js
`/api/*` rewrite proxy (port 8000).

## What's different from the base quickstart

The LLM stage uses the SDK's managed `OpenAI` vendor (keyless — Agora manages
the OpenAI key) with `mcp_servers` pointing at the public `mcp/` game server and
`enable_tools: true`. When the Dungeon Master LLM emits a tool call, Agora cloud
POSTs to `MCP_ENDPOINT` (streamable-http transport), receives the game result,
and the DM narrates it. There is no `llm/` endpoint in this recipe. STT
(Deepgram) and TTS (MiniMax) remain Agora-managed.

## Run

Use the repo-root `README.md` for the full local flow (`bun run dev`). To work
on this module directly:

The root commands below select the correct virtualenv interpreter on macOS,
Linux, and Windows, so activation is not required:

```shell
bun run setup:server
bun run backend
```

## Environment

`server/.env.example` is the template. Required:

- `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE` — Agora project credentials.
- `MCP_ENDPOINT` — the **public** URL of your `mcp/` game server (e.g.
  `https://<tunnel>/mcp`). Agora cloud calls this directly, so it cannot be
  `localhost`. Expose the backend on port 8000 via ngrok first.

Optional:
- `OPENAI_MODEL` (default `gpt-4o-mini`) — model name for the managed Dungeon
  Master LLM.
- `OPENAI_API_KEY` — Agora manages the key by default; set this only if you
  want to supply your own.
- `AGENT_GREETING` — override the DM's opening line.
- `PORT` (default `8000`) — agent backend port.

## API

- `GET /get_config` — token + channel/UID config
- `POST /startAgent` — start a Dungeon Master agent session
- `POST /stopAgent` — stop an agent session

The repo-root `bun run verify:local:fastapi` exercises these routes through the Next
proxy using a fake agent (`scripts/run_fake_server.py`), so no live Agora
session is required.

## Key files

| File | Purpose |
| --- | --- |
| `src/server.py` | FastAPI app, routes |
| `src/agent.py` | Agent wrapper — Dungeon Master LLM (OpenAI vendor + mcp_servers) |
| `src/mcp_config.py` | Pure builder for the `mcp_servers` list (testable) |
