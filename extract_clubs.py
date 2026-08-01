"""
MATCHDAY INSIGHTS — Extract clubs_data.json from index.html

Run this whenever you update your index.html to keep clubs_data.json in sync.

Usage:
    python3 extract_clubs.py
    python3 extract_clubs.py --index path/to/index.html   (custom path)

Output: clubs_data.json in the same folder as this script.
"""

import json, re, sys, os

# ── CONFIG ──────────────────────────────────────────
INDEX_PATH   = 'index.html'   # default — override with --index flag
OUTPUT_PATH  = 'clubs_data.json'
# ────────────────────────────────────────────────────

# Parse --index flag
args = sys.argv[1:]
if '--index' in args:
    idx = args.index('--index')
    INDEX_PATH = args[idx + 1]

if not os.path.exists(INDEX_PATH):
    print(f"ERROR: '{INDEX_PATH}' not found.")
    print("Usage: python3 extract_clubs.py --index path/to/index.html")
    sys.exit(1)

print(f"Reading {INDEX_PATH}...")
with open(INDEX_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Find CLUBS array
start_marker = 'const CLUBS='
idx = html.find(start_marker)
if idx == -1:
    print("ERROR: Could not find 'const CLUBS=' in index.html.")
    print("Make sure you're using the correct index.html from your GitHub repo.")
    sys.exit(1)

start = idx + len(start_marker)
depth = 0
i = start
while i < len(html):
    if html[i] == '[':   depth += 1
    elif html[i] == ']':
        depth -= 1
        if depth == 0:
            end = i + 1
            break
    i += 1

try:
    clubs = json.loads(html[start:end])
except json.JSONDecodeError as e:
    print(f"ERROR: Failed to parse CLUBS array: {e}")
    sys.exit(1)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(clubs, f)

# Summary
countries = sorted(set(c.get('country','?') for c in clubs))
print(f"✅ Extracted {len(clubs)} clubs across {len(countries)} countries")
print(f"   Saved to: {OUTPUT_PATH}")
print(f"   Countries: {', '.join(countries[:10])}{'...' if len(countries) > 10 else ''}")
