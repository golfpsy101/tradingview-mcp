---
name: daily-brief
description: Generate a structured daily trading brief for the current chart — price, key levels, MTF signals, indicator readings, and bias. Use when the user types "daily_brief" or asks for a morning/daily overview.
---

# Daily Brief Workflow

You are generating a structured daily trading brief for the current TradingView chart.

## Step 1: Pull All Data in Parallel

Call all of these simultaneously (no dependencies between them):

1. `quote_get` — current price, OHLC, volume
2. `data_get_study_values` — all visible indicator readings (RSI, EMAs, etc.)
3. `data_get_pine_lines` — horizontal price levels from Pine indicators
4. `data_get_pine_labels` — labeled levels (ORH, ORL, targets, etc.)
5. `data_get_pine_tables` — MTF signal tables (Zero Lag, etc.)
6. `data_get_ohlcv` with `summary: true` — session OHLCV summary
7. `capture_screenshot` with `region: "chart"` — visual snapshot

## Step 2: Format the Brief

Output the brief in this exact structure:

```
## Daily Brief — [SYMBOL] | [TIMEFRAME]-min | [DATE]

### Price Snapshot
| | |
|---|---|
| Last | [price] |
| Session Open | [open] |
| Session High | [high] |
| Session Low | [low] |
| Change | [change] ([change_pct]) |
| Avg Volume | [avg_volume] / bar |

### Key Levels
| Level | Price | Type |
|---|---|---|
[List all Pine levels from labels + lines, sorted high → low. Include type: ORH, ORL, Target, Resistance, Support, etc.]

### Indicators
| Indicator | Value | Read |
|---|---|---|
[List all study values. Add a one-word read: Bullish / Bearish / Neutral / Oversold / Overbought]

### MTF Signal Table
| Timeframe | Signal |
|---|---|
[From data_get_pine_tables — list each timeframe and signal]

### Bias
**[BULLISH / BEARISH / NEUTRAL]**
[2-3 sentences max. State: (1) where price is relative to key levels, (2) what the MTF signals say, (3) what to watch.]

### Scenarios
**Bull case:** [one line — what needs to happen + target]
**Bear case:** [one line — what needs to happen + target]
```

## Step 3: Screenshot

Reference the screenshot file path at the end so the user knows it was captured.

## Rules

- Always call all 7 tools in parallel in Step 1 — never sequentially
- Keep the Bias section to 3 sentences max
- Sort Key Levels table high → low
- If Pine labels have the same price as Pine lines, merge them into one row
- If MTF table is unavailable, omit that section rather than leaving it empty
- Do not add commentary outside the brief format
