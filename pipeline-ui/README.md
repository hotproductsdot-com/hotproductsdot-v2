# HotProducts Pipeline UI

A self-contained, locally-hosted **visual CI/CD dashboard** for every activity
in this repo: source products, fix images, validate, generate content, post to
Instagram/TikTok, build, and deploy to Hostinger.

No external Python deps — pure stdlib HTTP server with Server-Sent Events for
live log streaming.

## Quick start

```bash
# from the repo root
./pipeline-ui/start.sh
# or
python3 pipeline-ui/server.py
```

Then open http://127.0.0.1:7878 (it auto-launches your browser).

Flags:
- `--port 9000` — pick a different port (auto-selects if busy)
- `--no-browser` — don't auto-open
- `--host 0.0.0.0` — expose on the LAN

## What it shows

8 pipeline stages, each a row of clickable activity cards:

1. **Source Products** — find_bestsellers, scrape_top_affiliates, add_by_asin, …
2. **Images** — autofix-images, download-images, fix-mismatched, …
3. **Validate / QA** — check-links, check-images, validate_all, full QA suite
4. **Generate Content** — content calendar, IG ad creative, competitor ads
5. **Post** — `post_daily.py` (DRY/LIVE), TikTok pipeline, IG smoke test
6. **Build & Deploy** — `npm run build`, daily_post_and_deploy, rsync to Hostinger
7. **Auth / Refresh** — Oxylabs, TikTok refresh
8. **Tools / Git** — git status/diff/log, Streamlit dashboard, pytest

Cards marked **PROD** affect production (live posts, deploys). **LONG** = expect
slow runs. Click any card → form for CLI args → Run → live log streams in the
**Live Log** tab.

The **Job History** tab shows every run with status, exit code, and duration.
Click "view" to replay any past job's log (loaded from the buffered ring + the
on-disk log under `pipeline-ui/logs/`).

## How it works

- `server.py` — stdlib `ThreadingHTTPServer`. Routes:
  - `GET /api/stages` — pipeline definition
  - `GET /api/jobs` — recent jobs
  - `POST /api/run {activity_id, params}` — start a job
  - `GET /api/jobs/<id>/stream` — SSE live log
  - `POST /api/jobs/<id>/stop` — kill running job
- `jobs.py` — subprocess runner. One process per job, stdout+stderr captured
  line-by-line, broadcast to all SSE subscribers, and persisted to disk.
- `pipeline_config.py` — declarative stage/activity catalog. Add new ones here
  and they show up in the UI on next reload.
- `static/` — single-page frontend (vanilla JS, no build step).

The runner auto-activates the project's `venv/` if it exists, so Python scripts
that depend on the project's pinned packages just work.

## Adding a new activity

Edit `pipeline-ui/pipeline_config.py` and append an `Activity` to the matching
`Stage`. Refresh the page.

```python
Activity(
    id="my_new_thing",
    title="My New Thing",
    description="What it does",
    cmd=["python", "scripts/my_new_thing.py"],
    params=[Param(name="days", label="Days", flag="--days", default="7")],
    long_running=True,
)
```

## Files

```
pipeline-ui/
├── server.py            # HTTP + SSE server (entrypoint)
├── jobs.py              # subprocess job runner
├── pipeline_config.py   # stage/activity catalog
├── start.sh             # venv-aware launcher
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── logs/                # per-job log files (auto-created)
└── README.md
```

## Notes

- Runs locally only by default (binds 127.0.0.1).
- Jobs survive a browser refresh — reconnect from Job History to keep watching.
- `--platform`, `--category`, etc. on `post_daily.py` are exposed as form fields
  on the activity card. The DRY-RUN and LIVE variants are separate cards so you
  can never accidentally fire the live one.
