"""
Pull full daily price history from Polymarket's CLOB API for all tracked markets.
Uses startTs to retrieve data from before our collection started (back to Nov 2025 or earlier).
Exports everything to an Excel file for manual inspection.

Run: python3 analysis/pull_clob_history.py
Output: analysis/output/clob_history.xlsx
"""

import json
import time
import datetime
import urllib.request
import urllib.error
from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
SEED_PATH   = Path(__file__).parent.parent / "seed_data" / "seed.xlsx"
OUTPUT_PATH = Path(__file__).parent / "output" / "clob_history.xlsx"
START_TS    = int(datetime.datetime(2025, 1, 1).timestamp())   # 2025-01-01 — captures everything
FIDELITY    = 1440   # daily (1440 minutes = 1 day)
DELAY       = 0.25   # seconds between requests (avoids rate limiting)

GAMMA_BASE  = "https://gamma-api.polymarket.com"
CLOB_BASE   = "https://clob.polymarket.com"


# ── Helpers ───────────────────────────────────────────────────────────────────
def norm_id(x):
    try:
        return str(int(float(x)))
    except Exception:
        return str(x)


def get(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"    rate limited — waiting 5s …")
                time.sleep(5)
            elif attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1)
    return None


# ── Load market list ──────────────────────────────────────────────────────────
print("Loading market list from seed.xlsx …")
mkts_df = pd.read_excel(SEED_PATH, sheet_name="markets")
mkts_df["market_id"] = mkts_df["market_id"].apply(norm_id)
market_ids = mkts_df["market_id"].tolist()
print(f"  {len(market_ids)} markets to process\n")


# ── Step 1: fetch clobTokenIds from Gamma API ─────────────────────────────────
# Gamma supports up to ~100 IDs per request via ?id=x&id=y...
print("Step 1 — Fetching token IDs from Gamma API …")

token_map   = {}   # market_id -> {yes_token, no_token, question, created}
failed_ids  = []

BATCH_SIZE = 80
batches = [market_ids[i:i+BATCH_SIZE] for i in range(0, len(market_ids), BATCH_SIZE)]

for b_idx, batch in enumerate(batches):
    id_params = "&".join(f"id={mid}" for mid in batch)
    url = f"{GAMMA_BASE}/markets?{id_params}&limit={BATCH_SIZE}"
    try:
        results = get(url)
        if not isinstance(results, list):
            results = [results] if isinstance(results, dict) else []
        for item in results:
            mid = norm_id(item.get("id", ""))
            try:
                token_ids = json.loads(item["clobTokenIds"])
                token_map[mid] = {
                    "yes_token":  token_ids[0],
                    "no_token":   token_ids[1] if len(token_ids) > 1 else None,
                    "question":   item.get("question", ""),
                    "created":    item.get("createdAt", "")[:10],
                    "closed":     item.get("closed", False),
                    "active":     item.get("active", True),
                }
            except Exception:
                failed_ids.append(mid)
        print(f"  Batch {b_idx+1}/{len(batches)} — got tokens for {len(results)} markets")
    except Exception as e:
        print(f"  Batch {b_idx+1} failed: {e}")
    time.sleep(DELAY)

print(f"\n  Token IDs found: {len(token_map)}")
print(f"  Failed / no token: {len(failed_ids)}")


# ── Step 2: fetch CLOB price history per market ───────────────────────────────
print("\nStep 2 — Fetching daily price history from CLOB API …")
print("  (This will take ~2-3 minutes for 280 markets)\n")

all_rows = []
index_rows = []
errors = []

total = len(token_map)
for i, (mid, info) in enumerate(token_map.items()):
    yes_token = info["yes_token"]
    url = (
        f"{CLOB_BASE}/prices-history"
        f"?market={yes_token}"
        f"&startTs={START_TS}"
        f"&fidelity={FIDELITY}"
    )
    try:
        data   = get(url)
        points = data.get("history", []) if data else []

        if points:
            first_dt = datetime.datetime.utcfromtimestamp(points[0]["t"]).date()
            last_dt  = datetime.datetime.utcfromtimestamp(points[-1]["t"]).date()
        else:
            first_dt = last_dt = None

        # Add to main dataset
        for pt in points:
            d   = datetime.datetime.utcfromtimestamp(pt["t"]).date()
            yes = round(float(pt["p"]), 4)
            all_rows.append({
                "date":        d,
                "market_id":   mid,
                "question":    info["question"],
                "yes_price":   yes,
                "no_price":    round(1 - yes, 4),
                "created":     info["created"],
                "active":      info["active"],
                "closed":      info["closed"],
            })

        # Index row
        index_rows.append({
            "market_id":   mid,
            "question":    info["question"],
            "created":     info["created"],
            "active":      info["active"],
            "closed":      info["closed"],
            "first_clob_date": first_dt,
            "last_clob_date":  last_dt,
            "total_days":  len(points),
            "days_before_jan26": max(0, (datetime.date(2026, 1, 26) - first_dt).days) if first_dt else 0,
        })

        status = f"{len(points):>4} pts  [{first_dt} → {last_dt}]" if points else "  0 pts"
        print(f"  [{i+1:>3}/{total}] {mid:<12}  {status}  {info['question'][:45]}")

    except Exception as e:
        errors.append({"market_id": mid, "error": str(e)})
        print(f"  [{i+1:>3}/{total}] {mid:<12}  ERROR: {e}")

    time.sleep(DELAY)


# ── Step 3: export to Excel ───────────────────────────────────────────────────
print(f"\nStep 3 — Exporting to Excel …")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

all_df   = pd.DataFrame(all_rows).sort_values(["market_id", "date"])
index_df = pd.DataFrame(index_rows).sort_values("first_clob_date")
error_df = pd.DataFrame(errors)

with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
    # Sheet 1: full daily price history
    all_df.to_excel(writer, sheet_name="Daily Prices", index=False)

    # Sheet 2: one row per market (summary)
    index_df.to_excel(writer, sheet_name="Market Index", index=False)

    # Sheet 3: errors
    if not error_df.empty:
        error_df.to_excel(writer, sheet_name="Errors", index=False)

    # Sheet 4: a comparison — CLOB data vs what we already collected
    our_snaps = pd.read_excel(SEED_PATH, sheet_name="snapshots_wide")
    our_snaps["market_id"] = our_snaps["market_id"].apply(norm_id)
    our_snaps["date"] = pd.to_datetime(our_snaps["timestamp_utc"], format="mixed", utc=True).dt.date
    our_snaps["source"] = "our_collection"
    our_cols = our_snaps[["date", "market_id", "yes_price", "no_price", "source"]].copy()
    our_cols["yes_price"] = pd.to_numeric(our_cols["yes_price"], errors="coerce").round(4)
    our_cols["no_price"]  = pd.to_numeric(our_cols["no_price"],  errors="coerce").round(4)

    clob_cols = all_df[["date", "market_id", "yes_price", "no_price"]].copy()
    clob_cols["source"] = "clob_api"

    comparison = (
        pd.concat([our_cols, clob_cols])
          .sort_values(["market_id", "date", "source"])
          .drop_duplicates(subset=["date", "market_id", "source"])
    )
    comparison.to_excel(writer, sheet_name="CLOB vs Our Collection", index=False)

print(f"\n{'='*60}")
print(f"  Done.")
print(f"  Total data rows    : {len(all_df):,}")
print(f"  Markets with data  : {all_df['market_id'].nunique()}")
print(f"  Markets with errors: {len(errors)}")
print(f"  Date range         : {all_df['date'].min()} → {all_df['date'].max()}")

pre_jan = index_df[index_df["days_before_jan26"] > 0]
print(f"\n  Markets with history BEFORE Jan 26, 2026 : {len(pre_jan)}")
if len(pre_jan) > 0:
    print(f"  Avg extra days available                 : {pre_jan['days_before_jan26'].mean():.0f}")
    print(f"  Max extra days available                 : {pre_jan['days_before_jan26'].max()}")
    print(f"  Earliest market goes back to             : {index_df['first_clob_date'].min()}")

print(f"\n  Saved to: {OUTPUT_PATH}")
print(f"{'='*60}")
