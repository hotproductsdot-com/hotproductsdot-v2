---
name: portfolio-harness
description: "Install, audit, and maintain the shared agent harness across all repos in the E:\\GITHUB portfolio."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [harness, portfolio, agents-md, cursor, mission-control]
    related_skills: [pantheon, claude-os-bridge]
---

# Portfolio Harness

Portable agent configuration for every repo under `E:\GITHUB` / `/mnt/e/GITHUB`.

## What it installs

| Artifact | Purpose |
|----------|---------|
| `AGENTS.md` | Project-specific agent instructions (archetype + commands) |
| `.cursor/rules/portfolio-core.mdc` | Always-on Cursor rules (secrets, delegation, git safety) |
| Mission Control registry | Registers project in `agentic-os/mission-control/data/projects.json` |

## Archetypes

| Archetype | Detected by |
|-----------|-------------|
| `fullstack-mixed` | `site/package.json` + `requirements.txt` |
| `nextjs-vercel` | `next.config.*` at root or in `site/` |
| `node-monorepo` | `pnpm-workspace.yaml` |
| `python-app` | `requirements.txt` or `pyproject.toml` |
| `node-app` | `package.json` |
| `generic` | fallback |

Override per project in `agentic-os/harness/portfolio.yaml` → `projects:`.

## Commands

```bash
# Single project (from repo root)
python3 agentic-os/harness/install.py

# Specific path
python3 agentic-os/harness/install.py --project /mnt/e/GITHUB/farm-website

# Entire portfolio
python3 agentic-os/harness/install.py --all

# Merge into existing AGENTS.md (keeps custom sections)
python3 agentic-os/harness/install.py --project /path/to/repo --merge

# Audit coverage
python3 agentic-os/harness/audit.py
python3 agentic-os/harness/audit.py --format json
```

Windows:

```powershell
.\agentic-os\harness\scripts\install-harness.ps1 -All
.\agentic-os\harness\scripts\install-harness.ps1 -Project E:\GITHUB\farm-website -Merge
```

## When to use

- New repo added to the portfolio → run `install.py` on it
- Morning brief (Mercury) reports low harness coverage → run `audit.py` then `--all`
- User asks to "sync agent rules across projects"
- Oracle needs to know project archetype → read `detect.py` output or Mission Control registry

## Skip list

Projects with `skip_harness: true` in `portfolio.yaml` (e.g. Obsidian vault, everything-claude-code) are never modified.
