# site/

Next.js 16 app for hotproductsdot-v2. See the [root README](../README.md) for the full command reference.

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start local dev server at http://localhost:3000 |
| `npm run build` | Stable production build via webpack; skips rebuild if no inputs changed |
| `npm run build:fast` | Faster production build via Turbopack |
| `npm run start` | Serve production build locally |
| `npm run lint` | Run ESLint |

Set `BUILD_CPUS` to override build worker count (default: all CPU cores minus one).
Set `FORCE_BUILD=1` to bypass no-op detection and force a full rebuild.

## Stack

- **Next.js 16** — App Router, Server Components
- **TypeScript**
- **Tailwind CSS**
- **PapaParse** — CSV parsing for product data
