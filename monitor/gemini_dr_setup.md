# TASK-007 — Gemini Deep Research connector setup

Per Zee's 2026-06-04 brief: allow Claude to autonomously dispatch Gemini Deep
Research jobs overnight, retrieve results, integrate into memory + planning.

## State at 2026-06-04 ~01:40 PKT

- ✅ `uv` package manager installed at `C:\Users\zeesh\.local\bin\uv.exe`
- ✅ `google-generativeai` Python SDK available via uvx (downloads ~25MB on first use)
- ⏳ MCP server choice: `gemini-research-mcp` OR `deep-research-mcp` (community pkgs) — exact
  package names need PyPI verification before commit
- ❌ `GEMINI_API_KEY` not yet stored — Zee must generate one at
  https://aistudio.google.com/app/apikey and add to `monitor/.gemini_api_key`
- ❌ MCP server entry not yet added to `~/.claude/.mcp.json`

## To activate (one-time, ~10 min)

1. **Generate Gemini API key**:
   - Open https://aistudio.google.com/app/apikey in browser
   - Click "Create API key" → copy
   - Save to: `monitor/.gemini_api_key` (already in `.gitignore` via the
     `*.api_key` pattern)

2. **Add MCP server to Claude config** — append to `~/.claude/.mcp.json`:
   ```json
   {
     "mcpServers": {
       "tradingview": { ... existing ... },
       "gemini-research": {
         "command": "C:\\Users\\zeesh\\.local\\bin\\uvx.exe",
         "args": ["gemini-research-mcp"],
         "env": {
           "GEMINI_API_KEY": "<paste-key-here>"
         }
       }
     }
   }
   ```
   (If `gemini-research-mcp` PyPI package doesn't work, swap to
   `deep-research-mcp` or one of the custom-built alternatives.)

3. **Restart Claude Code session** — `.mcp.json` is read at session start.
   The next session should expose tools like `research_deep` and
   `resume_research`.

## Fallback: custom MCP wrapper (if community packages don't work)

If `uvx gemini-research-mcp` errors out, build a minimal MCP wrapper. Skeleton:

```python
# monitor/gemini_dr_mcp.py
import os, asyncio
from mcp.server.fastmcp import FastMCP
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
mcp = FastMCP("gemini-research")

@mcp.tool()
async def research_deep(query: str, max_minutes: int = 15) -> str:
    """Run Gemini Deep Research on `query`. Returns the synthesized report.
    Uses the Interactions API with background=True per Zee's 2026-06-04 brief."""
    # NOTE: as of mid-2026, the SDK route for this is:
    #   client = genai.Client()
    #   interaction = client.interactions.create(
    #       agent="deep-research-max-preview-04-2026",
    #       input=query, background=True)
    #   while not interaction.done: await asyncio.sleep(30); interaction.refresh()
    #   return interaction.output_text
    ...

if __name__ == "__main__":
    mcp.run()
```

Add to .mcp.json as a python script instead of uvx package.

## Use cases for Claude (once active)

Each night while Zee sleeps, Claude can dispatch deep-research jobs like:
  - "Latest 2026 XAUUSD intraday volatility regime changes"
  - "Atmos Global / prop firm rule changes in last 7 days"
  - "Analysis of EA trade patterns: do MQL5 broker SL/TP fills cluster at specific times?"

Results get appended to `daily_reports/` for next-day reading and feed into
`memory.md` as research-backed plan updates.

## Per Rule #10

TASK-007 stays OPEN until:
  - Zee generates API key
  - MCP server runs
  - First successful `research_deep` round-trip completes
  - Zee replies `close 007`
