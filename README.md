# FBA Sourcer

An AI-powered Amazon FBA product sourcing tool that finds profitable leads automatically.

## Overview

FBA Sourcer uses Claude AI to scan major retailers and marketplaces, identifying products that meet your criteria:
- **50+ sales per month** (verified via Keepa)
- **20%+ ROI minimum**

The agent returns 5-7 qualified leads per search session for manual review with SellerAmp and Keepa.

## Tech Stack

- **Backend**: FastAPI + Python
- **Package Manager**: UV
- **Agent**: Claude API + Tool Use
- **APIs**: Keepa (product data), Claude Web Search
- **Frontend**: Vue.js (lightweight)
- **Deployment**: Local machine

## Quick Start

```bash
# Install dependencies
make install

# Run development server
make dev

# Access the UI
# Open browser to http://localhost:8000
```

## Project Structure

```
fba-sourcer/
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── agent/
│   │   ├── api/
│   │   └── utils/
│   └── tests/
├── frontend/           # Web UI
├── Makefile           # Build automation
└── pyproject.toml     # UV project config
```

## How It Works

1. **Submit a search** → Provide a product category (e.g., "kitchen gadgets")
2. **Agent orchestrates** → Claude decides which tools to use:
   - Web search to find candidates
   - Keepa queries to validate sales volume
   - ROI calculations to verify profitability
3. **Multi-turn loop** → Claude sees results and decides next steps until finding 5-7 leads
4. **Manual review** → User reviews results in SellerAmp and Keepa for final validation

The agent autonomously handles the research — you just provide the category and review the results.

## Environment Variables

Create a `.env` file:

```
CLAUDE_API_KEY=your-key-here
KEEPA_API_KEY=your-key-here
```