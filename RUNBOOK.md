# Project Run Book

Quick reference for frequently used command sequences in the hotproductsdot-v2 project. Run these to avoid searching history repeatedly.

**Last Updated:** 2026-04-16

---

## 🚀 Quick Start

### Activate Virtual Environment (FLUX)
```bash
source ~/.flux-env/bin/activate
```

### Activate Virtual Environment (Default)
```bash
source venv/bin/activate
```

### Navigate to Project Root
```bash
cd /mnt/e/GITHUB/hotproductsdot-v2
```

---

## 📝 Daily Content Posting Workflows

### Post Daily - Standard (All Categories, Instagram)
```bash
python3 post_daily.py --platform instagram
```

### Post Daily - Dry Run (Test without posting)
```bash
python3 post_daily.py --dry-run
```

### Post Daily - Specific Category
```bash
python3 post_daily.py --category "Audio" --platform instagram
python3 post_daily.py --category "Kitchen" --platform instagram
python3 post_daily.py --category "Robot Vacuums" --platform instagram
```

### Post Daily - Dry Run with Local FLUX
```bash
python3 post_daily.py --dry-run --use-local-flux
python3 post_daily.py --category "Kitchen" --dry-run --use-local-flux
```

### Post Daily - Show Previously Posted
```bash
python3 post_daily.py --show-posted all
python3 post_daily.py --show-posted Audio
```

### Post Daily - Dry Run with Grep Filter
```bash
python3 post_daily.py --category Audio --platform instagram --dry-run 2>&1 | grep -A 5 "Today's product"
```

### Post Daily - Random Categories (Multiple Items)
```bash
# Post 3 items, each from a random category
python3 post_daily.py --random 3 --platform instagram

# Dry run with 5 random items
python3 post_daily.py --random 5 --dry-run

# Random posting with local FLUX images
python3 post_daily.py --random 2 --use-local-flux --dry-run
```

---

## 🎵 TikTok token refresh

TikTok access tokens expire in 24 h. Refresh tokens last 365 d and rotate on each use —
persist the new one or the next refresh fails.

### One-time bootstrap (get the initial refresh token)

1. Register the app at <https://developers.tiktok.com/> with `video.publish` scope
   and a redirect URI you control (any HTTPS URL — the redirect just needs to
   capture the `code` query param).
2. Add the image host domain (e.g. `res.cloudinary.com`) to the app's
   "URL prefix properties". Without this, `PULL_FROM_URL` fails with
   `url_ownership_unverified`.
3. Put `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env`.
4. Open this URL in a browser (substitute your values):
   ```
   https://www.tiktok.com/v2/auth/authorize/?client_key=YOUR_KEY&scope=video.publish&redirect_uri=YOUR_REDIRECT&response_type=code&state=hp
   ```
5. After approval, TikTok redirects to `YOUR_REDIRECT?code=XXXX&state=hp`.
   Copy the `code` value.
6. Exchange it for initial tokens:
   ```bash
   python -m tiktok_api exchange-code --code XXXX --redirect-uri YOUR_REDIRECT
   ```
7. Save the printed `access_token` and `refresh_token` to `.env` as
   `TIKTOK_ACCESS_TOKEN` and `TIKTOK_REFRESH_TOKEN`.

### Daily refresh (manual)

```bash
python -m tiktok_api refresh
# Copy the printed tokens into .env (both access_token AND refresh_token — it rotated).
```

### Daily refresh (automated, GitHub Actions)

Wired up in `.github/workflows/tiktok_refresh.yml` — runs every 12 h at 00:00 and
12:00 UTC (2 h before the daily post at 14:00).

**One-time setup** to enable it:

1. Add these repo secrets (Settings → Secrets and variables → Actions):
   - `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`
   - `TIKTOK_ACCESS_TOKEN`, `TIKTOK_REFRESH_TOKEN` (from the bootstrap above)
2. Create a **fine-grained PAT** at <https://github.com/settings/personal-access-tokens/new>:
   - Resource owner: you (or the org)
   - Repository access: only this repo
   - Permissions → Repository → **Secrets: Read and write**
   - Copy the token, add it as a repo secret named `GH_PAT`.
3. (Optional) Trigger a test run via Actions → "Refresh TikTok token" → Run workflow.

To run manually from your terminal:

```bash
GH_REPO=OWNER/REPO GH_TOKEN=ghp_... python -m tiktok_api refresh --github
```

> The default `GITHUB_TOKEN` **cannot** write secrets — you must use a PAT with
> `Secrets: Read and write`.

### Troubleshooting

| Error | Cause |
|-------|-------|
| `invalid_grant: Refresh token is expired or revoked` | Re-run the bootstrap. This happens if nothing refreshed for 365 d, the user revoked access, or a rotation was lost. |
| `url_ownership_unverified` from `post_photo` | Add the image host to "URL prefix properties" in the TikTok Developer portal. |
| `access_token_invalid` | Run `python -m tiktok_api refresh` and update `TIKTOK_ACCESS_TOKEN`. |

---

## 🔗 Link & Content Checking

### Check Links (Node)
```bash
node check-links.js
```

### Extract Product Data
```bash
python3 extractor.py
```

### Run Tests
```bash
python3 test.py
```

### Mid-Day Checkpoint
```bash
python3 mid_day_checkpoint.py
```

---

## 📊 Dashboard & Monitoring

### Start Streamlit Dashboard
```bash
python -m streamlit run dashboard.py
```

### Start Python Dashboard (Flask)
```bash
python3 dashboard/app.py
```

### Kill Dashboard Process
```bash
pkill -f "python3 dashboard/app.py"
```

### Kill and Restart Dashboard
```bash
pkill -f "python3 dashboard/app.py" && python3 dashboard/app.py
```

---

## 🔧 Git Workflows

### Check Git Status (Short)
```bash
git status --short
```

### Check Git Status
```bash
git status
```

### Stage & View Changes
```bash
git add affiliate_cli.py AFFILIATE_CLI_GUIDE.md && git diff --cached --stat
```

### Commit with Message
```bash
git commit -m "feat: add affiliate_cli.py for CLI-based content generation"
```

### Commit and Check Log
```bash
git commit -m "your message here" && git log -1 --oneline
```

### Push to GitHub
```bash
git push origin main
```

### Pull with Rebase (Safe)
```bash
git pull origin main --rebase
```

### Full Sync (Pull, Push, Restore Stash)
```bash
git pull origin main --rebase && git push origin main && git stash pop
```

### Clean Sync (Stash, Pull, Push)
```bash
git stash && git pull --rebase origin main && git push origin main
```

### View Recent Commits
```bash
git log -3 --oneline
```

---

## 📋 Multi-Step Sequences

### Complete Development Cycle
```bash
# 1. Make changes
# 2. Check status
git status --short

# 3. Add changes
git add <files>

# 4. Commit
git commit -m "type: description"

# 5. Sync with remote
git pull origin main --rebase && git push origin main

# 6. Verify
git log -1 --oneline
echo "✓ Successfully pushed to GitHub"
```

### Test New Feature (Post Daily)
```bash
# 1. Dry run first
python3 post_daily.py --category "Category Name" --platform instagram --dry-run

# 2. Check output
# 3. If good, run for real
python3 post_daily.py --category "Category Name" --platform instagram

# 4. View posted items
python3 post_daily.py --show-posted all
```

### Dashboard Workflow
```bash
# 1. Kill any running dashboard
pkill -f "python3 dashboard/app.py"

# 2. Start fresh
python3 dashboard/app.py

# 3. View at http://localhost:5000
```

---

## 🔍 Troubleshooting

### Search History for Commands
```bash
history | grep topic
history | grep python
history | grep git
```

### Clear Terminal
```bash
clear
```

### Check API Key
```bash
echo $ANTHROPIC_API_KEY
```

### Load Environment Variables
```bash
source .env
```

### Python Interactive Mode
```bash
python3
python3 << 'EOF'
# your code here
EOF
```

---

## 📌 Key Files

- **Daily posting:** `post_daily.py`
- **Content extraction:** `extractor.py`
- **Dashboard:** `dashboard/app.py` or `dashboard.py`
- **Link checking:** `check-links.js`
- **Testing:** `test.py`
- **Configuration:** `.env`, `.flux-env`

---

## 🎯 Categories (for --category flag)
- Audio
- Kitchen
- Robot Vacuums
- [See CLAUDE.md or memory for full list]

---

## 💡 Tips

- **Always dry-run first** before posting to social media
- **Use `--show-posted`** to track what's been published
- **Check git status** before committing
- **Rebase before pushing** to keep history clean
- **Kill old processes** before restarting services

