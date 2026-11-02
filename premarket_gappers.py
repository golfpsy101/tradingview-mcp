#!/usr/bin/env python3
"""
Premarket Gappers Scanner
Data:    Yahoo Finance gainers API → Benzinga catalysts
Filters: gap > 5% | price > $3 | premarket_volume > 50k | top 10 by gap%
Output:  premarket_gappers_YYYY-MM-DD.json
Runtime: ~60-90s
"""

import json
import re
import sys
import time
from datetime import datetime, date
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(url, extra=None, timeout=30):
    headers = {**BASE_HEADERS, **(extra or {})}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        print(f"  HTTP {e.code}: {url}", file=sys.stderr)
    except URLError as e:
        print(f"  URLError {e.reason}: {url}", file=sys.stderr)
    except Exception as e:
        print(f"  Error {e}: {url}", file=sys.stderr)
    return None


# ── YAHOO FINANCE ─────────────────────────────────────────────────────────────

def fetch_gainers():
    json_accept = {"Accept": "application/json"}

    # Primary: v1 screener API (day_gainers, no crumb needed)
    for host in ("query1", "query2"):
        url = (
            f"https://{host}.finance.yahoo.com/v1/finance/screener/predefined/saved"
            "?formatted=false&lang=en-US&region=US&scrIds=day_gainers&count=50"
            "&corsDomain=finance.yahoo.com"
        )
        raw = _get(url, json_accept)
        if raw:
            try:
                data = json.loads(raw)
                quotes = data["finance"]["result"][0]["quotes"]
                if quotes:
                    print(f"  {len(quotes)} quotes via {host} API", file=sys.stderr)
                    return quotes
            except Exception:
                pass

    # Fallback: HTML page — extract embedded JSON blobs
    print("  API unavailable, scraping HTML...", file=sys.stderr)
    raw = _get(
        "https://finance.yahoo.com/markets/stocks/gainers/?count=50",
        {"Accept": "text/html,application/xhtml+xml"},
    )
    if raw:
        for pattern in (
            r'"quotes"\s*:\s*(\[[\s\S]{200,}\?])',   # long array
            r'"quotes"\s*:\s*(\[[^\]]{100,}\])',
        ):
            m = re.search(pattern, raw)
            if m:
                try:
                    q = json.loads(m.group(1))
                    if q:
                        print(f"  {len(q)} quotes from HTML fallback", file=sys.stderr)
                        return q
                except Exception:
                    pass

    return []


def filter_gappers(quotes):
    out = []
    for q in quotes:
        sym = q.get("symbol", "").strip()
        if not sym:
            continue

        # Prefer premarket fields; fall back to regular market
        price = q.get("preMarketPrice")           or q.get("regularMarketPrice", 0)
        pct   = q.get("preMarketChangePercent")   or q.get("regularMarketChangePercent", 0)
        vol   = q.get("preMarketVolume")          or q.get("regularMarketVolume", 0)

        try:
            price = float(price)
            pct   = float(pct)
            vol   = int(float(vol))
        except (TypeError, ValueError):
            continue

        if pct   <= 5.0:   continue  # gap filter
        if price <= 3.0:   continue  # penny filter
        if vol   <= 50_000: continue  # thin-volume filter

        out.append({
            "symbol":           sym,
            "price":            round(price, 2),
            "gap_pct":          round(pct, 2),
            "premarket_volume": vol,
        })

    out.sort(key=lambda x: x["gap_pct"], reverse=True)
    return out[:10]


# ── NEWS CATALYST (Yahoo Finance search API) ──────────────────────────────────
# Benzinga is fully JS-rendered; static HTML has no article content.
# Yahoo Finance /v1/finance/search returns actual article titles in JSON.

def fetch_catalyst(ticker):
    url = (
        f"https://query1.finance.yahoo.com/v1/finance/search"
        f"?q={ticker}&newsCount=5&quotesCount=0"
        f"&enableFuzzyQuery=false&enableCeLen=false"
        f"&corsDomain=finance.yahoo.com"
    )
    raw = _get(url, {"Accept": "application/json"}, timeout=20)
    if not raw:
        # fallback host
        raw = _get(
            url.replace("query1", "query2"),
            {"Accept": "application/json"}, timeout=20,
        )
    if not raw:
        return None, []

    try:
        data  = json.loads(raw)
        items = data.get("news", [])
    except Exception:
        return None, []

    seen, headlines = set(), []
    for item in items:
        title = item.get("title", "").strip()
        if not title or len(title) < 15:
            continue
        key = title[:60].lower()
        if key not in seen:
            seen.add(key)
            headlines.append(title)
        if len(headlines) == 2:
            break

    return (headlines[0] if headlines else None), headlines


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    today     = date.today().strftime("%Y-%m-%d")
    out_file  = f"premarket_gappers_{today}.json"
    scanned_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    print("Fetching Yahoo Finance gainers...", file=sys.stderr)
    quotes = fetch_gainers()
    if not quotes:
        print("ERROR: no quotes returned from Yahoo Finance.", file=sys.stderr)
        sys.exit(1)

    gappers = filter_gappers(quotes)
    print(
        f"{len(gappers)} gappers pass filters (gap>5%, price>$3, vol>50k)",
        file=sys.stderr,
    )

    if not gappers:
        payload = {"scanned_at": scanned_at, "gappers": []}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Premarket Gappers: 0 names. Saved → {out_file}")
        return

    print("Fetching Benzinga catalysts...", file=sys.stderr)
    results = []
    for i, g in enumerate(gappers):
        sym = g["symbol"]
        print(f"  [{i+1}/{len(gappers)}] {sym} (+{g['gap_pct']}%)...", file=sys.stderr)
        try:
            catalyst, headlines = fetch_catalyst(sym)
        except Exception as e:
            print(f"    catalyst failed: {e}", file=sys.stderr)
            catalyst, headlines = None, []

        results.append({
            "rank":             i + 1,
            "symbol":           sym,
            "price":            g["price"],
            "gap_pct":          g["gap_pct"],
            "premarket_volume": g["premarket_volume"],
            "catalyst":         catalyst,
            "headlines":        headlines,
        })

        if i < len(gappers) - 1:
            time.sleep(1.5)  # polite delay between Benzinga requests

    payload = {"scanned_at": scanned_at, "gappers": results}
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nSaved → {out_file}", file=sys.stderr)

    # One-line summary (top 3)
    parts = []
    for r in results[:3]:
        cat = (r["catalyst"] or "no catalyst found")
        if len(cat) > 55:
            cat = cat[:52] + "..."
        parts.append(f"{r['symbol']} ({r['gap_pct']}%) — {cat}")
    print(f"Premarket Gappers: {len(results)} names. Top: " + ", ".join(parts))


if __name__ == "__main__":
    main()
