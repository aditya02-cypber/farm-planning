# 🌾 Farm Planning & Profit Estimator (AGR-02)

**Difficulty:** Intermediate
**Core idea:** Agent + Calculator Tool
**Suggested features:** Season/location-based crop recommendation, profit estimation
**Tech stack:** LangChain Agent, custom calculator tool, Streamlit, Gemini (`langchain-google-genai`)

## What it does

This app is a conversational farm-planning assistant built as a **LangChain tool-calling agent**.
Instead of a single RAG chain (like the PDF/PPT projects), the agent decides *which tool to call*
based on what the farmer asks:

1. **`crop_recommendation_tool`** – suggests suitable crops for a given cropping **season**
   (`kharif` / `rabi` / `zaid`) and **region** (`north` / `south` / `east` / `west`).
2. **`profit_calculator_tool`** – a custom calculator tool that estimates:
   - total expected yield
   - gross revenue
   - net profit
   - ROI %

   using land size (acres), total cost, and average yield/price data (with the option to override
   with the farmer's own numbers).

The agent can chain both tools in one conversation, e.g. *"What should I grow in kharif in the
north, and what's my expected profit on 3 acres with a ₹40,000 budget?"*

A **sidebar quick-calculator** also lets you call the profit tool directly without going through
the chat/agent, for a fast one-off estimate.

## How it works

```
User question
      │
      ▼
LangChain Tool-Calling Agent (Gemini)
      │
      ├── needs crop suggestion? → crop_recommendation_tool(season, region)
      │
      └── needs profit numbers? → profit_calculator_tool(crop, land_acres, total_cost_rs, ...)
      │
      ▼
Agent explains the tool output in plain language
```

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Enter your `GOOGLE_API_KEY` (Gemini) in the sidebar to activate the chat agent — the quick
calculator in the sidebar works without an API key since it calls the tool directly.

## Notes

- Crop/season/region data and average yield & price figures are simplified reference tables inside
  `app.py` for demo purposes — swap in a real agri-market API (e.g. Agmarknet, data.gov.in) for
  production accuracy.
- Built to follow the same project format as [`PDF`](https://github.com/aditya02-cypber/PDF),
  [`PPT`](https://github.com/aditya02-cypber/PPT), and
  [`fcml_collegeproject`](https://github.com/aditya02-cypber/fcml_collegeproject).
