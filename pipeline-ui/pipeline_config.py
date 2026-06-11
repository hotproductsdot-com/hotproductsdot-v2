"""Declarative definition of pipeline stages and activities.

Each activity becomes a runnable card in the web UI. Stages are visual groupings
that mirror the lifecycle of an affiliate post: source -> images -> validate ->
generate -> post -> deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Param:
    name: str
    label: str
    kind: str = "text"  # text | bool | select | textarea
    default: Any = ""
    choices: list[str] = field(default_factory=list)
    placeholder: str = ""
    flag: str = ""  # CLI flag, e.g. "--platform"; if empty, value is appended positionally
    help: str = ""


@dataclass
class Activity:
    id: str
    title: str
    description: str
    cmd: list[str]
    cwd: str = ""           # relative to repo root; empty = repo root
    params: list[Param] = field(default_factory=list)
    icon: str = "*"
    danger: bool = False    # mark destructive / production-impacting tasks
    long_running: bool = False


@dataclass
class Stage:
    id: str
    title: str
    color: str
    icon: str
    activities: list[Activity]


STAGES: list[Stage] = [
    Stage(
        id="source",
        title="1. Source Products",
        color="#6366f1",
        icon="DB",
        activities=[
            Activity(
                id="find_bestsellers",
                title="Find Bestsellers",
                description="Scrape Amazon bestseller lists to find new product candidates.",
                cmd=["python", "find_bestsellers.py"],
                icon="*",
            ),
            Activity(
                id="scrape_top_affiliates",
                title="Scrape Top Affiliates",
                description="Mine competitor affiliate sites for trending products.",
                cmd=["python", "scrape_top_affiliates.py"],
            ),
            Activity(
                id="add_by_asin",
                title="Add Product by ASIN",
                description="Add a single product to the catalog by its Amazon ASIN.",
                cmd=["python", "add_product_by_asin.py"],
                params=[Param(name="asin", label="ASIN", placeholder="B0XXXXXXXX", help="Amazon ASIN (positional arg)")],
            ),
            Activity(
                id="add_new_products",
                title="Add New Products (batch)",
                description="Run the batch add-new-products workflow.",
                cmd=["python", "add_new_products.py"],
            ),
            Activity(
                id="generate_products",
                title="Generate Products",
                description="Generate product entries from the top-1000 CSV.",
                cmd=["python", "generate_products.py"],
            ),
            Activity(
                id="remove_duplicates",
                title="Remove Duplicates",
                description="De-duplicate the products CSV.",
                cmd=["python", "remove_duplicates.py"],
                danger=True,
            ),
            Activity(
                id="fix_amazon_urls",
                title="Fix Amazon URLs",
                description="Repair malformed Amazon product URLs in the catalog.",
                cmd=["python", "fix_amazon_urls.py"],
            ),
        ],
    ),
    Stage(
        id="images",
        title="2. Images",
        color="#06b6d4",
        icon="IMG",
        activities=[
            Activity(
                id="autofix_images",
                title="Autofix Images",
                description="Auto-download/repair product images. Run after adding products.",
                cmd=["node", "autofix-images.js"],
                long_running=True,
            ),
            Activity(
                id="download_images",
                title="Download Images",
                description="Download product images for the entire catalog.",
                cmd=["node", "download-images.js"],
                long_running=True,
            ),
            Activity(
                id="download_missing",
                title="Download Missing",
                description="Only download images that are currently missing.",
                cmd=["node", "download-missing.js"],
            ),
            Activity(
                id="fix_mismatched",
                title="Fix Mismatched Images",
                description="Detect and repair products with wrong/mismatched images.",
                cmd=["node", "fix-mismatched-images.js"],
            ),
            Activity(
                id="generate_placeholders",
                title="Generate Placeholders",
                description="Generate placeholder images for missing products.",
                cmd=["node", "generate-placeholders.js"],
            ),
        ],
    ),
    Stage(
        id="validate",
        title="3. Validate / QA",
        color="#10b981",
        icon="QA",
        activities=[
            Activity(
                id="check_links",
                title="Check Links",
                description="Verify all affiliate links resolve and tags are correct.",
                cmd=["node", "check-links.js"],
                long_running=True,
            ),
            Activity(
                id="check_duplicates",
                title="Check Duplicates",
                description="Find duplicate products in the catalog (read-only report).",
                cmd=["node", "check-duplicates.js"],
            ),
            Activity(
                id="check_images",
                title="Check Images",
                description="Audit image presence and integrity.",
                cmd=["node", "check-images.js"],
            ),
            Activity(
                id="validate_all",
                title="Validate All (Python)",
                description="Run the full Python validator across the catalog.",
                cmd=["python", "scripts/_validate_all.py"],
            ),
            Activity(
                id="qa_full",
                title="Full QA Suite",
                description="Run the full quality-assurance shell pipeline.",
                cmd=["bash", "perform_qualityassurance.sh"],
                long_running=True,
            ),
            Activity(
                id="fix_affiliate_tags",
                title="Fix Affiliate Tags",
                description="Repair Amazon Associates affiliate tags across the site.",
                cmd=["node", "fix-affiliate-tags.js"],
            ),
        ],
    ),
    Stage(
        id="generate",
        title="4. Generate Content",
        color="#f59e0b",
        icon="GEN",
        activities=[
            Activity(
                id="content_calendar",
                title="Generate Content Calendar",
                description="Plan N days of posts with hooks/CTAs.",
                cmd=["python", "generate_content_calendar.py"],
                params=[Param(name="days", label="Days", flag="--days", default="7", placeholder="7")],
            ),
            Activity(
                id="ad_creative",
                title="IG Ad Creative Generator",
                description="Generate Instagram ad creative banners.",
                cmd=["python", "instagram/ad_creative_gen.py"],
                long_running=True,
            ),
            Activity(
                id="competitor_ads",
                title="Scrape Competitor Ads",
                description="Pull competitor IG ads for inspiration.",
                cmd=["python", "instagram/competitor_ads.py"],
            ),
        ],
    ),
    Stage(
        id="post",
        title="5. Post",
        color="#ef4444",
        icon="POST",
        activities=[
            Activity(
                id="post_daily_dry",
                title="Post Daily (DRY RUN)",
                description="Run the daily post pipeline without actually posting.",
                cmd=["python", "post_daily.py", "--dry-run"],
                long_running=True,
                params=[
                    Param(name="platform", label="Platform", kind="select",
                          choices=["", "instagram", "tiktok"], flag="--platform"),
                    Param(name="category", label="Category", flag="--category", placeholder="kitchen"),
                    Param(name="local_flux", label="Use local FLUX", kind="bool", flag="--use-local-flux"),
                ],
            ),
            Activity(
                id="post_daily_live",
                title="Post Daily (LIVE)",
                description="Post for real to Instagram. PRODUCTION.",
                cmd=["python", "post_daily.py", "--platform", "instagram"],
                danger=True,
                long_running=True,
                params=[
                    Param(name="category", label="Category (optional)", flag="--category", placeholder="kitchen"),
                ],
            ),
            Activity(
                id="post_daily_show_posted",
                title="Show Previously Posted",
                description="List products already posted (no new post).",
                cmd=["python", "post_daily.py", "--show-posted"],
            ),
            Activity(
                id="test_ig_post",
                title="Test Instagram Post",
                description="Smoke test the Instagram posting path.",
                cmd=["python", "test_instagram_post.py"],
            ),
            Activity(
                id="tiktok_pipeline",
                title="TikTok Video Pipeline",
                description="Generate + post a TikTok video.",
                cmd=["python", "tiktok_video_pipeline.py"],
                long_running=True,
                danger=True,
            ),
        ],
    ),
    Stage(
        id="deploy",
        title="6. Build & Deploy",
        color="#8b5cf6",
        icon="DEPLOY",
        activities=[
            Activity(
                id="site_build",
                title="Build Site",
                description="Build the static site (cd site && npm install && npm run build).",
                cmd=["npm", "run", "build"],
                long_running=True,
            ),
            Activity(
                id="site_start",
                title="Start Site (dev)",
                description="Start the local site dev server.",
                cmd=["npm", "start"],
                long_running=True,
            ),
            Activity(
                id="daily_post_and_deploy",
                title="Daily Post + Deploy",
                description="Full daily routine: 4 IG posts, build, rsync to Hostinger.",
                cmd=["bash", "scripts/daily_post_and_deploy.sh"],
                danger=True,
                long_running=True,
            ),
            Activity(
                id="deploy_rsync",
                title="Deploy (rsync to Hostinger)",
                description="Build site and rsync to Hostinger production.",
                cmd=["npm", "run", "deploy:rsync"],
                cwd="site",
                danger=True,
                long_running=True,
            ),
        ],
    ),
    Stage(
        id="auth",
        title="7. Auth / Refresh",
        color="#0ea5e9",
        icon="KEY",
        activities=[
            Activity(
                id="oxylabs_refresh",
                title="Refresh Oxylabs",
                description="Refresh Oxylabs Amazon scraper credentials/cache.",
                cmd=["python", "oxylabs_refresh.py"],
            ),
            Activity(
                id="tiktok_refresh_test",
                title="Test TikTok Refresh",
                description="Test the TikTok token refresh flow.",
                cmd=["python", "test_tiktok_refresh.py"],
            ),
        ],
    ),
    Stage(
        id="tools",
        title="8. Tools / Git",
        color="#64748b",
        icon="GIT",
        activities=[
            Activity(
                id="git_status",
                title="Git Status",
                description="Show working tree status (short).",
                cmd=["git", "status", "--short"],
            ),
            Activity(
                id="git_diff",
                title="Git Diff",
                description="Show unstaged diff.",
                cmd=["git", "diff", "--stat"],
            ),
            Activity(
                id="git_log",
                title="Git Log (last 20)",
                description="Show recent commits.",
                cmd=["git", "log", "--oneline", "-n", "20"],
            ),
            Activity(
                id="streamlit_dashboard",
                title="Open Streamlit Dashboard",
                description="Launch the Streamlit dashboard on http://localhost:8501 (headless: opens in your browser tab).",
                cmd=[
                    "python", "-m", "streamlit", "run", "dashboard.py",
                    "--server.headless=true",
                    "--browser.gatherUsageStats=false",
                ],
                long_running=True,
            ),
            Activity(
                id="run_tests_py",
                title="Run Python Tests",
                description="Run all pytest tests under instagram/ and root.",
                cmd=["python", "-m", "pytest", "-x", "-q"],
                long_running=True,
            ),
            Activity(
                id="facebook_cookbook_demo",
                title="Build Facebook Cookbook (demo)",
                description=(
                    "Create a cookbook from Facebook saved recipes (sibling repo at ../facebook-cookbook). "
                    "For a real export: use --export path/to/facebook.zip."
                ),
                cmd=["python", "scripts/build_cookbook.py", "--demo"],
                cwd="../facebook-cookbook",
                params=[
                    Param(
                        name="dry_run",
                        label="Dry run (no Claude API)",
                        kind="bool",
                        default=True,
                        flag="--dry-run",
                    ),
                    Param(
                        name="export_path",
                        label="Facebook export .zip or folder (overrides demo)",
                        flag="--export",
                        placeholder="C:/Users/you/Downloads/facebook-export.zip",
                    ),
                    Param(
                        name="title",
                        label="Cookbook title",
                        flag="--title",
                        default="My Facebook Recipe Cookbook",
                    ),
                    Param(
                        name="limit",
                        label="Max recipes (0 = all)",
                        flag="--limit",
                        default="0",
                    ),
                ],
                long_running=True,
            ),
        ],
    ),
]


def to_dict() -> list[dict]:
    return [
        {
            "id": s.id,
            "title": s.title,
            "color": s.color,
            "icon": s.icon,
            "activities": [
                {
                    **{k: v for k, v in asdict(a).items() if k != "params"},
                    "params": [asdict(p) for p in a.params],
                }
                for a in s.activities
            ],
        }
        for s in STAGES
    ]


def find_activity(activity_id: str) -> Activity | None:
    for stage in STAGES:
        for a in stage.activities:
            if a.id == activity_id:
                return a
    return None
