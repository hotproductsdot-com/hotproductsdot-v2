#!/usr/bin/env python3
"""
web_ui.py — Simple web UI for manually posting deals to Facebook.

Usage:
    cd growth-engine
    pip install flask
    python web_ui.py
    # open http://localhost:5050
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import CONFIG
from lib.facebook import post_link

app = Flask(__name__)

_DEALS_FILE = Path(CONFIG["paths"]["data_dir"]) / "deals.json"

HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Deal Poster — hotproducts</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:system-ui,sans-serif;background:#f5f5f5;color:#222;padding:20px}
    h1{font-size:1.4rem;margin-bottom:4px}
    .meta{font-size:.8rem;color:#666;margin-bottom:20px}
    .flash{padding:10px 16px;border-radius:6px;margin-bottom:16px;font-size:.9rem}
    .flash.ok{background:#d1fae5;color:#065f46}
    .flash.err{background:#fee2e2;color:#991b1b}
    .toolbar{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;align-items:center}
    .btn{display:inline-block;padding:8px 16px;border-radius:6px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;text-decoration:none}
    .btn-primary{background:#1877f2;color:#fff}
    .btn-primary:hover{background:#1558b0}
    .btn-secondary{background:#e5e7eb;color:#374151}
    .btn-secondary:hover{background:#d1d5db}
    .btn-sm{padding:5px 10px;font-size:.78rem}
    table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}
    th{background:#f9fafb;padding:10px 12px;text-align:left;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;border-bottom:1px solid #e5e7eb}
    td{padding:10px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;vertical-align:middle}
    tr:last-child td{border-bottom:none}
    .badge{display:inline-block;padding:2px 7px;border-radius:999px;font-size:.72rem;font-weight:600}
    .badge-deal{background:#fef3c7;color:#92400e}
    .badge-catalog{background:#dbeafe;color:#1e40af}
    .pct{font-weight:700;color:#dc2626}
    .title-cell{max-width:320px}
    .title-text{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    .empty{text-align:center;padding:48px;color:#9ca3af}
    form{display:inline}
  </style>
</head>
<body>
  <h1>Deal Poster</h1>
  <p class="meta">
    {% if generated_at %}Last scan: {{ generated_at }} — {{ deals|length }} deal{{ 's' if deals|length != 1 }}{% else %}No deals loaded yet.{% endif %}
  </p>

  {% if flash %}
    <div class="flash {{ flash.type }}">{{ flash.msg }}</div>
  {% endif %}

  <div class="toolbar">
    {% if deals %}
    <form method="post" action="/post/top3">
      <button class="btn btn-primary" type="submit">🔥 Post Top 3 to Facebook</button>
    </form>
    {% endif %}
    <a class="btn btn-secondary" href="/">Refresh</a>
  </div>

  {% if deals %}
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th>Category</th>
        <th>Price</th>
        <th>Was</th>
        <th>Discount</th>
        <th>Badge</th>
        <th>Post</th>
      </tr>
    </thead>
    <tbody>
      {% for d in deals %}
      <tr>
        <td>{{ loop.index }}</td>
        <td class="title-cell">
          <span class="title-text"><a href="{{ d.affiliate_url }}" target="_blank" rel="noopener">{{ d.title }}</a></span>
          {% if d.in_catalog %}<span class="badge badge-catalog">catalog</span>{% endif %}
        </td>
        <td>{{ d.category }}</td>
        <td>{{ d.current_price }}</td>
        <td>{{ d.original_price or '—' }}</td>
        <td><span class="pct">{{ d.discount_pct }}%</span></td>
        <td>{% if d.deal_badge %}<span class="badge badge-deal">{{ d.deal_badge }}</span>{% endif %}</td>
        <td>
          <form method="post" action="/post/one">
            <input type="hidden" name="asin" value="{{ d.asin }}">
            <button class="btn btn-primary btn-sm" type="submit">Post</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty">No deals found. Run <code>python scripts/7_deal_finder.py</code> first.</div>
  {% endif %}
</body>
</html>"""


def _load_deals() -> tuple[list[dict], str]:
    if not _DEALS_FILE.exists():
        return [], ""
    data = json.loads(_DEALS_FILE.read_text(encoding="utf-8"))
    return data.get("deals", []), data.get("generatedAt", "")


def _format_message(deal: dict) -> str:
    lines = [f"🔥 Deal Alert: {deal['title']}", ""]
    lines.append(f"💰 Now: {deal['current_price']}")
    if deal.get("original_price"):
        lines.append(f"Was: {deal['original_price']}  ({deal['discount_pct']}% off)")
    if deal.get("deal_badge"):
        lines.append(f"🏷️  {deal['deal_badge']}")
    lines += ["", "👉 Shop now:"]
    return "\n".join(lines)


def _render(deals: list[dict], generated_at: str, flash: dict | None = None) -> str:
    from jinja2 import Environment
    env = Environment(autoescape=True)
    tmpl = env.from_string(HTML)
    return tmpl.render(deals=deals, generated_at=generated_at, flash=flash)


@app.get("/")
def index():
    deals, generated_at = _load_deals()
    return _render(deals, generated_at)


@app.post("/post/one")
def post_one():
    asin = request.form.get("asin", "").strip()
    deals, generated_at = _load_deals()
    deal = next((d for d in deals if d["asin"] == asin), None)
    if not deal:
        flash = {"type": "err", "msg": f"Deal {asin} not found in deals.json."}
        return _render(deals, generated_at, flash), 404

    try:
        result = post_link(message=_format_message(deal), link=deal["affiliate_url"])
        flash = {"type": "ok", "msg": f"Posted! Facebook post id: {result.get('id')}  —  {deal['title'][:80]}"}
    except Exception as exc:
        flash = {"type": "err", "msg": f"Facebook error: {exc}"}

    deals, generated_at = _load_deals()
    return _render(deals, generated_at, flash)


@app.post("/post/top3")
def post_top3():
    deals, generated_at = _load_deals()
    if not deals:
        flash = {"type": "err", "msg": "No deals loaded. Run the deal finder first."}
        return _render(deals, generated_at, flash)

    results = []
    for deal in deals[:3]:
        try:
            result = post_link(message=_format_message(deal), link=deal["affiliate_url"])
            results.append(f"✓ {deal['title'][:60]} (id: {result.get('id')})")
        except Exception as exc:
            results.append(f"✗ {deal['title'][:60]}: {exc}")

    flash = {"type": "ok" if all(r.startswith("✓") for r in results) else "err",
             "msg": " | ".join(results)}
    deals, generated_at = _load_deals()
    return _render(deals, generated_at, flash)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    print(f"Deal Poster running → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
