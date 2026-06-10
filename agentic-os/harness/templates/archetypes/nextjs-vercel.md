### Stack notes

- Next.js app — often deployed to Vercel
- Prefer Vercel env vars for secrets; never commit `.env` or use `NEXT_PUBLIC_*` for sensitive values
- Use `vercel env pull` when local parity with production env is needed

### Project-specific rules

- Run `npm run build` (or `cd site && npm run build` if app is in `site/`) before claiming deploy-ready
- Keep Server Components / App Router patterns consistent with existing pages
- Check `next.config.ts` for static export vs server features before adding APIs
