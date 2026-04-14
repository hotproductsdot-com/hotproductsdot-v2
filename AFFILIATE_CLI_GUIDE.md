# Affiliate CLI Tool

A command-line interface for generating Amazon affiliate marketing content without Streamlit.

## Installation

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

### Generate Hooks
```bash
python affiliate_cli.py hooks --product "Sony WH-1000XM5 Headphones" --category "Electronics" --count 5
```

### Generate CTA
```bash
python affiliate_cli.py cta --product "Sony WH-1000XM5 Headphones" --price "$399.99" --platform instagram
python affiliate_cli.py cta --product "Sony WH-1000XM5 Headphones" --price "$399.99" --platform tiktok
```

### Generate Content Calendar
```bash
python affiliate_cli.py calendar --days 7
python affiliate_cli.py calendar --days 7 --json  # Save as JSON file
```

### Generate Bio
```bash
python affiliate_cli.py bio --platform instagram --niche "Amazon gadgets"
python affiliate_cli.py bio --platform tiktok --niche "Amazon trending products"
```

### Interactive Mode
```bash
python affiliate_cli.py interactive
```

## Features

- **No Streamlit dependency** — Pure CLI tool aligned with post_daily.py
- **4 Content Generators**: Hooks, CTAs, Calendar, Bio
- **Interactive mode** — Walk through tools step-by-step
- **JSON output** — Export calendar and results as JSON
- **Fallback templates** — Works without ANTHROPIC_API_KEY (uses templates)
- **AI-powered** (when API key set) — Uses Claude Haiku for better content

## Environment Variables

Set in `.env`:
```
ANTHROPIC_API_KEY=sk-xxx  # Optional: enables AI generation
```

Without the API key, the tool uses built-in fallback templates.

## Logging

Add `-v` or `--verbose` for detailed output:
```bash
python affiliate_cli.py -v calendar --days 3
```

Add `-q` or `--quiet` to suppress info messages:
```bash
python affiliate_cli.py -q hooks --product "Test" --category "Electronics"
```
