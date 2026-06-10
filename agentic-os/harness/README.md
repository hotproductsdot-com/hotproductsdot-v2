# Portfolio Harness

Shared agent harness for every repo under `E:\GITHUB`. One install script, six archetypes, consistent rules across Cursor, Claude Code, and Hermes.

## Why

Your portfolio mixes Next.js sites, Python pipelines, pnpm monorepos, and automation repos — but most lack `AGENTS.md` or Cursor rules. This harness:

1. **Detects** the project archetype automatically
2. **Generates** `AGENTS.md` with the right commands and verification steps
3. **Installs** `.cursor/rules/portfolio-core.mdc` for always-on safety rules
4. **Registers** projects in Mission Control
5. **Audits** coverage across the whole portfolio

## Quick start

```bash
# From hotproductsdot-v2 (WSL)
python3 agentic-os/harness/audit.py          # see current coverage
python3 agentic-os/harness/install.py --all  # install everywhere
```

```powershell
# From Windows
.\agentic-os\harness\scripts\install-harness.ps1 -All
```

Single project:

```bash
python3 agentic-os/harness/install.py --project /mnt/e/GITHUB/farm-website
```

Preserve existing `AGENTS.md` content (e.g. paperclip, farm-website):

```bash
python3 agentic-os/harness/install.py --project /mnt/e/GITHUB/paperclip --merge
```

## Layout

```
harness/
├── portfolio.yaml      # portfolio root, archetypes, per-project overrides
├── detect.py           # stack detection + command inference
├── install.py          # apply harness to one or all projects
├── audit.py            # coverage scorecard
├── templates/
│   ├── AGENTS.base.md
│   ├── archetypes/     # per-archetype overlays
│   └── cursor/         # portfolio-core.mdc
└── scripts/
    ├── install-harness.sh
    └── install-harness.ps1
```

## Customization

Edit `portfolio.yaml` to:

- Add `projects.<slug>.archetype` overrides
- Set `skip_harness: true` for non-code repos
- Adjust `global_rules` for portfolio-wide policy changes

Re-run `install.py` after editing templates or portfolio config.

## Integration

| System | How it connects |
|--------|-----------------|
| **Hermes** | `portfolio-harness` skill; Mercury can run audit in morning brief |
| **Mission Control** | Projects page shows registered repos + archetypes |
| **Claude OS Bridge** | Oracle cross-references harness-installed `AGENTS.md` files |
| **Pantheon** | Delegation rules are identical in every repo's harness |
