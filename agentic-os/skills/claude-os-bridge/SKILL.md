---
name: claude-os-bridge
description: "Read shared context from Cursor, Claude Code, and Claude Desktop sessions — the Jack Roberts memory bridge."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [bridge, cursor, claude-code, memory, agentic-os]
    related_skills: [pantheon]
---

# Claude OS Bridge

Bidirectional shared memory between Hermes and your desktop AI tools (Cursor, Claude Code, Claude Desktop).

## What it bridges

| Source | Path (WSL) | Contents |
|--------|------------|----------|
| Cursor agent transcripts | `/mnt/c/Users/cyber/.cursor/projects/*/agent-transcripts/*.jsonl` | Recent agent sessions |
| Claude Code projects | `~/.claude/projects/` | Per-project session metadata |
| Claude Desktop | `~/AppData/Roaming/Claude/` (via /mnt/c) | Local agent sessions |
| Obsidian vault | `/mnt/e/GITHUB/Claude-Code-OBVault` | PKM notes (already in Hermes config) |
| Bridge digest | `agentic-os/bridge/context/latest.json` | Pre-digested cross-tool summary |

## When to use

- User asks "what did I work on?", "what did my dream say?", "what's in Claude OS?"
- Before strategic advice (Oracle persona)
- Morning brief cron job (Mercury reads bridge + generates 2–3 suggestions)
- Any time Hermes needs desktop context it wasn't present for

## Workflow

1. **Refresh context** (if stale >4h or user asks):
   ```bash
   python3 agentic-os/bridge/collect_context.py
   ```
2. **Read** `agentic-os/bridge/context/latest.json`
3. **Synthesize** — don't dump raw logs; extract themes, open tasks, recent decisions
4. **Cross-reference** Obsidian vault for related notes when answering

## MCP bridge (Cursor ↔ Hermes)

Hermes exposes MCP server for Cursor:
```bash
hermes mcp serve --transport stdio --name hermes-orchestrator
```

Cursor `.cursor/mcp.json` points to WSL hermes. See `agentic-os/config/cursor-mcp.json`.

## Privacy

- Never include API keys or .env contents in bridge output
- Truncate long transcripts to last 50 messages per session
- Bridge files are gitignored except structure templates
