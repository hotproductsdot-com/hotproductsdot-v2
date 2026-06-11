### Stack notes

- pnpm workspace monorepo — packages share types and build graph
- Contract changes must stay synchronized across packages

### Project-specific rules

- Prefer `pnpm` over npm/yarn — match workspace scripts in root `package.json`
- After schema/API changes, update all affected packages before hand-off
- Run `pnpm -r typecheck` and `pnpm build` when touching shared contracts
