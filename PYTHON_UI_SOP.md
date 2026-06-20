# SOP — Python Scripts with a UI

Of ~100 project `.py` files, **4 serve a user interface**. Everything else is
CLI/library code (run with `python <file>.py [args]`, no browser). This SOP
covers only the 4 UIs.

| Script | UI type | Default URL | Start command |
|--------|---------|-------------|---------------|
| `dashboard.py` | Streamlit | http://localhost:8501 | `streamlit run dashboard.py` |
| `pipeline-ui/server.py` | Web (stdlib HTTP + live logs) | http://localhost:7878 | `python pipeline-ui/server.py` |
| `growth-engine/web_ui.py` | Web (Flask) | http://localhost:5050 | `cd growth-engine && python web_ui.py` |
| `agentic-os/mission-control/server.py` | Web (stdlib HTTP) | http://127.0.0.1:9120 | `cd agentic-os/mission-control && python server.py` |

> Note: `instagram/image_gen_local_flux.py` is *not* a UI — it's a **client**
> that calls a remote Gradio image server. No browser interface of its own.

---

## 1. `dashboard.py` — Affiliate Content Tools (Streamlit)

AI content helpers in 4 tabs: **Hook Writer**, **CTA Builder**, **Content
Calendar**, **Bio Optimizer**.

```bash
pip install streamlit anthropic python-dotenv   # first time only
streamlit run dashboard.py                       # opens http://localhost:8501
```

- Requires `ANTHROPIC_API_KEY` in `.env` (loaded via python-dotenv). Without
  it the page loads but generation buttons error.
- Stop: `Ctrl+C` in the terminal.

## 2. `pipeline-ui/server.py` — Visual CI/CD Pipeline

Web dashboard to run/monitor the product pipeline with live streaming logs
(SSE) and a catalog view. **No external dependencies** (pure stdlib).

```bash
python pipeline-ui/server.py            # http://localhost:7878, auto-opens browser
python pipeline-ui/server.py --port 9000
```

- Run from the repo root so it finds `jobs.py` / `pipeline_config.py`.
- Stop: `Ctrl+C`.

## 3. `growth-engine/web_ui.py` — Deal Poster (Flask)

One-page UI to review found deals and post them to Facebook.

```bash
pip install flask
cd growth-engine
python web_ui.py            # http://localhost:5050
python web_ui.py 8080       # custom port (positional arg)
```

- **Run the deal finder first** or the page is empty:
  `python scripts/7_deal_finder.py`
- Needs Facebook config (`lib/config.py` + env) for posting to work.
- Runs with `debug=True` — fine locally, do not expose publicly.
- Stop: `Ctrl+C`.

## 4. `agentic-os/mission-control/server.py` — Mission Control

Multi-page ops dashboard (`/command /projects /pantheon /bridge /memory
/growth /cron /skills`). Stdlib HTTP server; serves `static/index.html`.

```bash
cd agentic-os/mission-control
python server.py            # http://127.0.0.1:9120
MISSION_CONTROL_PORT=9200 MISSION_CONTROL_HOST=0.0.0.0 python server.py
```

- Run from its own dir (imports sibling `projects.py` / `pantheon.py`).
- `pip install pyyaml` if persona/config features are used (optional import).
- Stop: `Ctrl+C`.

---

## General notes

- All 4 are local dev servers — bind to localhost by default; don't expose to
  the internet as-is (no auth, debug mode).
- Each holds the terminal; use a separate terminal per UI or run in the
  background. Conflicting "address in use" → another instance is running or
  pick a new port.
- API-key-backed features (`dashboard.py`, `mission-control`) need a populated
  `.env`.
