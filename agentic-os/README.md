# Agentic OS — Hermes + Jack Roberts Architecture

A Jack Roberts-style **Agentic Operating System** built around [Hermes Agent](https://hermes-agent.nousresearch.com/) for hotproductsdot-v2. Unifies Hermes (orchestrator), Cursor/Claude Code (coder), Obsidian (PKM), and the growth-engine into one shared intelligence layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mission Control (:9120)                       │
│         Pantheon · Bridge · Growth Engine · Hermes status        │
└────────────────────────────┬────────────────────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     │                       │                       │
     ▼                       ▼                       ▼
┌─────────┐           ┌─────────────┐         ┌──────────────┐
│ Hermes  │◄──MCP────►│ Cursor /    │         │ Obsidian     │
│ Agent   │  bridge   │ Claude Code │         │ Vault        │
│ (WSL)   │           │ (Windows)   │         │ (PKM)        │
└────┬────┘           └─────────────┘         └──────────────┘
     │
     ├── Pantheon (Mercury · Labyrinth · Philosopher · Oracle)
     ├── Claude OS Bridge (shared session digest)
     ├── Cron (morning brief · bridge refresh · backup)
     └── growth-engine (SEO · deals · Facebook · visibility)
```

## Quick start

**Prerequisites:** Hermes installed in WSL (`hermes --version`), Python 3.11+, PyYAML.

```powershell
# From repo root (Windows)
.\agentic-os\scripts\install.ps1
```

Or in WSL directly:

```bash
cd /mnt/e/GITHUB/hotproductsdot-v2
bash agentic-os/scripts/install.sh
```

### After install

| Service | Command | URL |
|---------|---------|-----|
| Mission Control | `python3 agentic-os/mission-control/server.py` | http://127.0.0.1:9120 |

**Mission Control sub-pages:** `/` · `/command` · `/projects` · `/hermes` · `/pantheon` · `/bridge` · `/memory` · `/growth` · `/cron` · `/skills`

**Hermes command box:** Use the bottom panel on any page, or open `/command` for the full chat UI. Messages run via `hermes chat` with session continuity and Pantheon delegation.
| Hermes Dashboard | `hermes dashboard --tui` | http://127.0.0.1:9119 |
| Hermes CLI | `hermes` | terminal |
| Telegram gateway | `hermes gateway start` | your phone |
| Pipeline UI | `python pipeline-ui/server.py` | http://127.0.0.1:7878 |

## Pantheon

Invoke personas in Hermes chat or Telegram:

| Persona | Say | Use for |
|---------|-----|---------|
| **Mercury** | "use Mercury for..." | Cron, briefs, status checks |
| **Labyrinth** | "use Labyrinth to research..." | Web research, SEO, competitors |
| **Philosopher** | "use Philosopher on..." | Strategy, trade-offs |
| **Oracle** | "use Oracle — what did I work on?" | Cross-tool synthesis |

Edit personas in `config/personalities.yaml`, then:

```bash
python3 agentic-os/scripts/sync-pantheon.py
```

## Claude OS Bridge

Fixes the "Hermes hears it, Claude knows it" gap. Collects Cursor agent transcripts + Claude Code project metadata into a shared digest:

```bash
python3 agentic-os/bridge/collect_context.py
# → agentic-os/bridge/context/latest.json
```

Auto-refreshes every 4 hours via Hermes cron after install.

### Cursor ↔ Hermes MCP

Copy MCP config to enable Cursor calling Hermes as a tool:

```powershell
Copy-Item agentic-os\config\cursor-mcp.json .cursor\mcp.json
```

## Cron jobs (installed by setup)

| Job | Schedule | Agent |
|-----|----------|-------|
| `morning-brief` | 8:00 AM daily | Mercury — growth status + 2–3 suggestions |
| `bridge-refresh` | Every 4 hours | Script only — refreshes bridge JSON |
| `github-backup` | 11:00 PM daily | Config backup reminder |

## Jack Roberts parity checklist

| Feature | Status |
|---------|--------|
| Hermes Agent (orchestrator) | ✅ Uses your WSL install |
| Pantheon personas | ✅ Mercury, Labyrinth, Philosopher, Oracle |
| Claude OS Bridge | ✅ Cursor + Claude session digest |
| Obsidian PKM | ✅ Already in your Hermes config |
| Mission Control dashboard | ✅ Custom UI at :9120 |
| Hermes built-in dashboard | ✅ `hermes dashboard --tui` |
| Telegram gateway | ⚙️ Run `hermes gateway setup` |
| MCP bidirectional bridge | ⚙️ Apply `config/cursor-mcp.json` |
| Overnight dream/suggestions | ✅ Morning brief cron |
| GitHub config backup | ✅ Nightly cron prompt |
| growth-engine integration | ✅ hotproducts-growth skill |

## Portfolio Harness

Portable agent rules for every repo under `E:\GITHUB`. Detects archetype (Next.js, Python, monorepo, etc.), writes `AGENTS.md`, installs Cursor rules, registers projects in Mission Control.

```bash
python3 agentic-os/harness/audit.py          # coverage scorecard
python3 agentic-os/harness/install.py --all  # install across portfolio
```

See [`harness/README.md`](harness/README.md).

## File layout

```
agentic-os/
├── harness/                  # Portfolio-wide agent harness (install + audit)
├── config/
│   ├── personalities.yaml    # Pantheon definitions
│   └── cursor-mcp.json       # Cursor MCP bridge template
├── skills/
│   ├── pantheon/SKILL.md
│   ├── claude-os-bridge/SKILL.md
│   ├── hotproducts-growth/SKILL.md
│   └── portfolio-harness/SKILL.md
├── bridge/
│   └── collect_context.py    # Claude OS bridge collector
├── mission-control/
│   └── server.py             # Visual dashboard
├── scripts/
│   ├── install.sh / install.ps1
│   └── sync-pantheon.py
└── SOUL.md                   # Hermes identity (synced to ~/.hermes/)
```

## Updating

After pulling changes:

```bash
bash agentic-os/scripts/install.sh
```

Or sync personas only:

```bash
python3 agentic-os/scripts/sync-pantheon.py
```
