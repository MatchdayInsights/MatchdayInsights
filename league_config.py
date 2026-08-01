"""
MATCHDAY INSIGHTS — League Configuration
=========================================
League tables have been removed from the site.
This file now only contains constants used by update_site.py.

DO NOT edit update_site.py unless adding a brand new feature.
"""

# ── Season list (newest first) ────────────────────────────────────────────────
SEASON_LIST = ['2026-27', '2025-26', '2024-25', '2023-24', '2022-23', '2021-22']

# ── Tier thresholds (never change) ───────────────────────────────────────────
TIER_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

# ── Luxembourg flag (injected automatically by update_site.py) ────────────────
LUX_FLAG_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#EF3340"/><rect y="4.67" width="20" height="4.67" fill="#fff"/><rect y="9.33" width="20" height="4.67" fill="#00A3E0"/></svg>'
