# Agent Development Guide

For coding agents working in `recipe-agent-rpg`. This repository is the **RPG
gaming** recipe in the Agora Conversational AI recipes family. A voice RPG where
a managed keyless OpenAI **Dungeon Master** narrates and calls **MCP game tools**;
the FastMCP game server is mounted in-process inside the API server at `/mcp`
(served on :8000); `MCP_ENDPOINT` must be public via ngrok.

## System shape

- **`server/`** — Python FastAPI agent backend (:8000). Owns Agora token
  generation, the Dungeon Master agent session lifecycle, and the FastMCP game
  server (mounted at `/mcp`). SDK: `agora-agents>=2.3.0` (`import agora_agent`).
- **`server/src/mcp_server.py`** — FastMCP wrapper exposing 6 game tools.
  Mounted in-process; Agora cloud calls it at `<public-url>/mcp`.
- **`server/src/game.py`** — pure game engine (SQLite, no MCP dependency, fully
  unit-testable). All dice rolling, combat resolution, and inventory logic live here.
- **`web/`** — Next.js frontend (:3000), standard Agora quickstart with RPG
  branding. No character-sheet UI — game state is voice-only via `get_character`.
- Auth: Token007 from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`. OpenAI is
  Agora-managed (keyless). `OPENAI_API_KEY` is optional.

## Routing / ownership

- UI and RTC/RTM lifecycle live in `web/`.
- Browser-facing `/api/*` paths are Next rewrites (`web/next.config.ts`) to the
  agent backend; do not add `web/app/api/**/route.ts` for agent/token logic.
- Token generation and agent lifecycle live in `server/src/`.
- All 6 MCP game tools live in `server/src/mcp_server.py`; pure game engine in
  `server/src/game.py` (no MCP import, fully unit-testable).
- The FastMCP server is mounted at `/mcp` inside `server/src/server.py` via
  `app.mount("/", _mcp_asgi)` with a shared lifespan.

## The 6 tools

| Tool | Purpose |
| --- | --- |
| `create_character(char_class)` | Create/reset hero (warrior/mage/rogue/cleric) |
| `get_character()` | Read stats, HP, gold, inventory, current mode |
| `start_encounter()` | Spawn a random enemy, switch mode → combat |
| `attack()` | Resolve one attack round (dice + counterattack) |
| `cast_spell(name)` | Resolve a spell round (bonus die + counterattack) |
| `flee()` | Exit combat, clear enemy, switch mode → narration |

Each tool is **self-contained** — dice are rolled inside `game.py`, not by the
LLM. One player utterance maps to at most one tool call.

## Supported modes

- **Local:** `bun run dev` starts `server` (:8000, serving both token endpoints
  and `/mcp`) and `web` (:3000). The web app calls `/api/*`; Next rewrites to
  `AGENT_BACKEND_URL=http://localhost:8000`. The backend must be exposed publicly
  (ngrok) so Agora cloud can reach `/mcp`.
- **Deploy:** deploy `web` (Next) + `server` (a single publicly reachable FastAPI
  process that also serves `/mcp`). Set `AGENT_BACKEND_URL` in the web deployment.

## Key env vars

| Variable | Notes |
| --- | --- |
| `MCP_ENDPOINT` | Required, public ngrok URL ending in `/mcp` (e.g. `https://<tunnel>/mcp`) |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `RPG_DB_PATH` | Default `rpg.db` in `server/`; Docker uses `/tmp/rpg.db` |
| `RPG_SEED` | Optional integer — deterministic dice for tests |
| `OPENAI_API_KEY` | Optional — Agora manages it (keyless) |

## Patterns

- Keep the web client calling `/api/*`; hide backend placement behind Next rewrites.
- Keep token generation and the App Certificate in `server/`.
- Keep `server/src/game.py` free of MCP imports — it is a standalone game engine.
- `MCP_ENDPOINT` is required and must be public; there is no localhost default.
- `OPENAI_API_KEY` is optional — Agora manages it (keyless).
- Tools are self-contained — do not add tool-call chaining (the LLM resolves
  one utterance with at most one tool call).

## Anti-patterns

- Do not reintroduce Next Route Handlers for agent/token logic.
- Do not separate `mcp_server.py` and `game.py` into a standalone process.
- Do not default `MCP_ENDPOINT` to localhost.
- Do not put `PORT` in `server/.env.example` (it would clobber the random port
  that `verify:local:fastapi` injects via `load_dotenv(override=True)`).
- Do not change `server/src/game.py`, `server/src/mcp_server.py`, or
  `server/src/agent.py` without reading the full file first.

## Commands

```bash
bun run setup
bun run dev
bun run doctor
bun run doctor:local
bun run verify         # web-only, no creds
bun run verify:local   # full local gate
```

Narrower checks: `bun run verify:backend`, `bun run verify:local:fastapi`,
`bun run verify:web:proxy`.

## Done criteria

1. Run the narrowest relevant verification command.
2. Web-affecting changes: `bun run verify:web` passes.
3. Backend-affecting changes: `bun run verify:local` (or the narrower
   `verify:backend`) passes.
4. If you change required env vars or setup steps, update the root README, the
   relevant module README, and `server/.env.example` together.

## Git conventions

- Conventional Commits: `type: description` or `type(scope): description`
  (`feat`, `fix`, `chore`, `test`, `docs`). Lowercase after the prefix, present
  tense.
- No AI tool names in commit messages or PR descriptions. No `Co-Authored-By`
  trailers. No `--no-verify`. No git config changes.
- Branch names: `type/short-description` (e.g. `feat/add-spell-tool`).
