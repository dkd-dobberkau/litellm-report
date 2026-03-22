# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python CLI tool that fetches and displays spend/cost data from a LiteLLM Proxy instance. Reports cover Virtual Keys, Teams, Tags (projects), and daily spend breakdowns. All output is in German.

## Running

```bash
# Install dependencies
uv pip install requests tabulate

# Required environment variables
export LITELLM_PROXY_URL=https://your-proxy-host  # default: http://localhost:4000
export LITELLM_MASTER_KEY=sk-...

# Run reports
python litellm_report.py --all                    # all four reports
python litellm_report.py --keys --teams           # specific reports
python litellm_report.py --tags --start 2026-03-01 --end 2026-03-31
```

## Architecture

Everything lives in `litellm_report.py`:
- `get()` — shared HTTP client for LiteLLM Proxy API calls (uses `/global/spend/*` endpoints)
- `report_keys()`, `report_teams()`, `report_tags()`, `report_global()` — each fetches from a different proxy endpoint and renders a `tabulate` table
- `main()` — argparse CLI with `--keys`, `--teams`, `--tags`, `--daily`, `--all`, `--start`, `--end`

## Key Details

- UI strings, help text, and error messages are all in **German**
- Cost formatting uses `$` prefix with 4 decimal places (`${cost:.4f}`)
- No tests, no packaging — standalone script
- LiteLLM Proxy API docs: https://docs.litellm.ai/docs/proxy/cost_tracking
