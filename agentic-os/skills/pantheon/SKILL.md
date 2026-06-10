---
name: pantheon
description: "Delegate tasks to Pantheon personas (Mercury, Labyrinth, Philosopher, Oracle) with model-aware routing."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pantheon, delegation, personas, agentic-os]
    related_skills: [claude-os-bridge]
---

# Pantheon — Multi-Agent Delegation

Jack Roberts-style persona routing. Each god has a role, model policy, and output format.

## Personas

| Persona | Role | Model policy | Trigger phrases |
|---------|------|--------------|-----------------|
| **Mercury** | Autopilot, cron, briefs, status | Cheap/fast | "use Mercury", morning brief, reminders |
| **Labyrinth** | Web research, SEO, competitive intel | Mid-tier + web tools | "use Labyrinth", research, analyze market |
| **Philosopher** | Strategy, trade-offs, architecture | Strong reasoning | "use Philosopher", should I, trade-off |
| **Oracle** | Cross-tool synthesis (Obsidian + bridge) | Context-heavy | "use Oracle", what did I work on |

## Workflow

1. **Classify** the request → pick persona (ask if ambiguous)
2. **Switch**: `/personality <name>` then adjust model if needed:
   - Mercury → `stepfun/step-3.7-flash:free` or haiku-class
   - Labyrinth → current default + web/x_search tools
   - Philosopher → stronger model (sonnet/opus) if available
   - Oracle → read `agentic-os/bridge/context/latest.json` first
3. **Execute** under persona system prompt rules
4. **Report** results tagged with persona name
5. **Reset** to orchestrator mode when task completes

## Parallel delegation

For independent subtasks, use `delegate_task()` to spawn subagents:
- Research + code review → Labyrinth subagent + Claude Code subagent in parallel
- Never delegate destructive ops without user confirmation

## Config source of truth

Persona definitions live in `agentic-os/config/personalities.yaml`.
After editing, run: `bash agentic-os/scripts/sync-pantheon.py`
