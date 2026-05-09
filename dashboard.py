#!/usr/bin/env python3
"""
Streamlit dashboard for AI-powered affiliate content tools.

Provides interactive interfaces for:
- Hook Writer: Generate scroll-stopping opening lines
- CTA Builder: Platform-specific call-to-action text
- Content Calendar: Plan N days of posts with products, hooks, and CTAs
- Bio Optimizer: Generate optimized Instagram/TikTok bios

Run with: streamlit run dashboard.py
"""

import json
import os
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Load environment
load_dotenv(override=True)

# ── Page config (must be the FIRST Streamlit call) ────────────────────────
st.set_page_config(
    page_title="HotProducts Affiliate Tools",
    page_icon="🛒",
    layout="wide",
)

# Try to import affiliate_tools, but don't fail if it's not available
_AFFILIATE_IMPORT_ERROR: str | None = None
try:
    from instagram import affiliate_tools
    _AFFILIATE_TOOLS_AVAILABLE = True
except Exception as e:
    _AFFILIATE_IMPORT_ERROR = str(e)
    _AFFILIATE_TOOLS_AVAILABLE = False
    affiliate_tools = None

# Try to import load_top_products, but don't fail if it's not available
try:
    from post_daily import load_top_products
    _PRODUCTS_AVAILABLE = True
except Exception as e:
    _PRODUCTS_AVAILABLE = False
    load_top_products = None

st.title("🛒 HotProducts Affiliate Content Tools")
st.markdown("AI-powered tools for Amazon affiliate marketing content creation")

if _AFFILIATE_IMPORT_ERROR:
    st.error(f"⚠️ Could not load affiliate_tools: {_AFFILIATE_IMPORT_ERROR}")


# ── Check API key ──────────────────────────────────────────────────────────
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.warning(
        "⚠️ **ANTHROPIC_API_KEY not set.** "
        "Add it to `.env` to enable AI features. Without it, you'll see fallback templates."
    )


# ── Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["🎣 Hook Writer", "📢 CTA Builder", "📅 Content Calendar", "✨ Bio Optimizer"]
)


# ────────────────────────────────────────────────────────────────────────────
# TAB 1: Hook Writer
# ────────────────────────────────────────────────────────────────────────────
with tab1:
    st.header("🎣 Hook Writer")
    st.markdown("Generate scroll-stopping opening lines for your product posts.")

    col1, col2 = st.columns(2)

    with col1:
        product_name = st.text_input("Product Name", value="Wireless Earbuds")
        category = st.text_input("Category", value="Electronics")

    with col2:
        rating = st.number_input("Rating (out of 5)", min_value=0.0, max_value=5.0, value=4.8, step=0.1)
        reviews = st.number_input("Number of Reviews", min_value=0, value=1200, step=100)
        price = st.text_input("Price", value="$49.99")

    if st.button("✨ Generate Hooks", key="hook_gen"):
        if not _AFFILIATE_TOOLS_AVAILABLE:
            st.error("affiliate_tools module is unavailable — cannot generate hooks.")
        elif not product_name or not category:
            st.error("Please fill in Product Name and Category")
        else:
            with st.spinner("Generating hooks..."):
                product = {
                    "name": product_name,
                    "category": category,
                    "rating": rating,
                    "reviews": str(reviews),
                    "price": price,
                }
                hooks = affiliate_tools.generate_hooks(product, count=5)

            st.success("✓ Hooks generated!")
            st.markdown("### Generated Hooks")
            for i, hook in enumerate(hooks, 1):
                st.markdown(f"{i}. **{hook}**")
                st.caption(f"Length: {len(hook)} chars")

            # Copy to clipboard hint
            st.markdown("💡 **Tip:** Click any hook to copy it for use in your posts")


# ────────────────────────────────────────────────────────────────────────────
# TAB 2: CTA Builder
# ────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("📢 CTA Builder")
    st.markdown("Generate platform-specific calls-to-action for higher conversion.")

    col1, col2 = st.columns([2, 1])

    with col1:
        product_name_cta = st.text_input("Product Name (CTA)", value="Wireless Earbuds")
        price_cta = st.text_input("Price (CTA)", value="$49.99")

    with col2:
        platform_cta = st.radio("Platform", ["Instagram", "TikTok"], horizontal=True)

    if st.button("✨ Generate CTA", key="cta_gen"):
        if not _AFFILIATE_TOOLS_AVAILABLE:
            st.error("affiliate_tools module is unavailable — cannot generate CTA.")
        elif not product_name_cta or not price_cta:
            st.error("Please fill in Product Name and Price")
        else:
            with st.spinner("Generating CTA..."):
                product_cta = {
                    "name": product_name_cta,
                    "price": price_cta,
                }
                cta = affiliate_tools.build_cta(product_cta, platform=platform_cta.lower())

            st.success("✓ CTA generated!")
            st.markdown("### Generated CTA")
            st.markdown(f"**{cta}**")
            st.caption(f"Length: {len(cta)} chars")

            # Show platform context
            if platform_cta == "Instagram":
                st.info("💡 Instagram CTAs emphasize 'Link in bio' and include price.")
            else:
                st.info("💡 TikTok CTAs use engagement-focused conventions like 'Comment LINK'.")


# ────────────────────────────────────────────────────────────────────────────
# TAB 3: Content Calendar
# ────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("📅 Content Calendar")
    st.markdown("Plan N days of product posts with AI-selected hooks and CTAs.")

    if not _PRODUCTS_AVAILABLE or not _AFFILIATE_TOOLS_AVAILABLE:
        st.warning(
            "⚠️ **Required module not available.** "
            "Make sure you're running this from the hotproductsdot-v2 project root directory "
            "and that `instagram/affiliate_tools.py` imports cleanly."
        )
    else:
        col1, col2 = st.columns(2)

        with col1:
            days_cal = st.slider("Number of Days to Plan", min_value=1, max_value=30, value=7)

        with col2:
            st.markdown("")  # spacing

        if st.button("✨ Generate Content Calendar", key="cal_gen"):
            with st.spinner(f"Generating {days_cal}-day calendar..."):
                try:
                    products = load_top_products()

                    if not products:
                        st.error("Could not load products from CSV.")
                    else:
                        calendar = affiliate_tools.generate_content_calendar(
                            products=products,
                            days=days_cal,
                        )

                        st.success(f"✓ {days_cal}-day calendar generated!")

                        # Display calendar as table
                        st.markdown("### Calendar Preview")
                        calendar_data = []
                        for entry in calendar["entries"]:
                            calendar_data.append({
                                "Day": entry["day"],
                                "Date": entry["date"],
                                "Platform": entry["platform"].upper(),
                                "Product": entry["product"]["name"][:30],
                                "Hook": entry["hook"][:25],
                                "CTA": entry["cta"][:25],
                            })

                        st.dataframe(
                            calendar_data,
                            use_container_width=True,
                            hide_index=True,
                        )

                        # Download JSON
                        calendar_json = json.dumps(calendar, indent=2)
                        st.download_button(
                            label="📥 Download Calendar as JSON",
                            data=calendar_json,
                            file_name=f"content_calendar_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json",
                        )

                        # Display generation timestamp
                        st.caption(f"Generated at: {calendar['generated_at']}")

                except Exception as exc:
                    st.error(f"Calendar generation failed: {exc}")


# ────────────────────────────────────────────────────────────────────────────
# TAB 4: Bio Optimizer
# ────────────────────────────────────────────────────────────────────────────
with tab4:
    st.header("✨ Bio Optimizer")
    st.markdown("Generate optimized bios for Instagram and TikTok affiliate accounts.")

    col1, col2 = st.columns([1, 1])

    with col1:
        platform_bio = st.radio("Platform", ["Instagram", "TikTok"], horizontal=True, key="bio_platform")

    with col2:
        niche_bio = st.text_input("Niche (optional)", value="Amazon trending products")

    if st.button("✨ Generate Bio", key="bio_gen"):
        if not _AFFILIATE_TOOLS_AVAILABLE:
            st.error("affiliate_tools module is unavailable — cannot generate bio.")
            st.stop()
        with st.spinner("Generating bio..."):
            bio = affiliate_tools.generate_bio(
                platform=platform_bio.lower(),
                niche=niche_bio or "Amazon affiliate",
            )

        st.success("✓ Bio generated!")
        st.markdown("### Generated Bio")
        st.markdown(f"**{bio}**")
        st.caption(f"Length: {len(bio)} chars")

        # Platform-specific notes
        if platform_bio == "Instagram":
            st.info(f"📱 Instagram max: 150 chars | Your bio: {len(bio)} chars")
        else:
            st.info(f"📱 TikTok max: 500 chars | Your bio: {len(bio)} chars")


# ── Footer ─────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    """
    ### 🛒 HotProducts Affiliate Tools

    Powered by Claude (Haiku) via Anthropic API.

    **Tips:**
    - All tools work best with your `ANTHROPIC_API_KEY` set in `.env`
    - Fallback templates are used if the API is unavailable
    - Save generated content for later use by copying or downloading
    - Content Calendar outputs ready-to-use JSON you can import into your posting system
    """
)
