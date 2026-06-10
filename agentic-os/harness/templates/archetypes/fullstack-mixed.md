### Stack notes

- **Site:** Next.js under `site/` (static export or Vercel)
- **Automation:** Python under `growth-engine/` or repo-root scripts
- **Control plane:** `agentic-os/` when present (Pantheon, bridge, Mission Control)

### Project-specific rules

- Run growth/automation with `--dry-run` unless the user explicitly approves publish/deploy
- Product images and CSVs are data assets — do not regenerate in bulk without approval
- Generated guides live in `site/content/guides-generated/` — match existing JSON schema
