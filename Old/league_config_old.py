"""
MATCHDAY INSIGHTS — League Configuration
=========================================
This is the ONLY file you need to edit between updates.

HOW TO USE:
- PROMOTIONS / RELEGATIONS: add or remove entries in MANUAL_NOTES
- NEW LEAGUES: add a block to LEAGUE_BLOCKS
- ZONE CHANGES: edit the relevant entry in ZONE_OVERRIDES
- Everything else stays the same

DO NOT edit update_site.py unless adding a brand new feature.
"""

# ── Season list (newest first) ────────────────────────────────────────────────
SEASON_LIST = ['2026-27', '2025-26', '2024-25', '2023-24', '2022-23', '2021-22']

# ── Tier thresholds (never change) ───────────────────────────────────────────
TIER_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

# ── League table block positions in the "League Tables" sheet ─────────────────
# Format: (note_col, club_col, rank_col)
# Stacked leagues are read automatically (script keeps reading until no more codes found)
LEAGUE_BLOCKS = [
    (1,   2,   3),    # ENG, ENG_2, ENG_3, ENG_4
    (15,  16,  17),   # ESP, ESP_2
    (29,  30,  31),   # GER, GER_2, GER_3
    (43,  44,  45),   # ITA, ITA_2
    (57,  58,  59),   # FRA
    (71,  72,  73),   # POR
    (85,  86,  87),   # NED
    (129, 130, 131),  # TUR
    (158, 159, 160),  # NOR
    # To add a new league, find its column position and add a new line here:
    # (col_note, col_club, col_rank),  # COUNTRY CODE
]

# ── Playoff-format leagues ────────────────────────────────────────────────────
# These leagues split into groups partway through the season.
# Format: code → list of (note_col, club_col, rank_col, data_start_row, group_name, zone_row)
PLAYOFF_LEAGUES = {
    'BEL': {
        'full_name': 'First Division A',
        'tiebreaker_row': 1,
        'tiebreaker_col': 99,
        'groups': [
            {'name': "Champions' Playoff",  'note_col': 100, 'club_col': 100, 'rank_col': 101, 'start_row': 0,  'zone_row': 2},
            {'name': 'Europe Playoff',       'note_col': 100, 'club_col': 100, 'rank_col': 101, 'start_row': 11, 'zone_row': 13},
            {'name': 'Relegation Playoff',   'note_col': 100, 'club_col': 100, 'rank_col': 101, 'start_row': 22, 'zone_row': 24},
        ],
        'group_keys': ['champions', 'europe', 'relegation'],
    },
    'GRE': {
        'full_name': 'Super League',
        'tiebreaker_row': 1,
        'tiebreaker_col': 114,
        'groups': [
            {'name': 'Championship Playoff', 'note_col': 115, 'club_col': 115, 'rank_col': 116, 'start_row': 0,  'zone_row': 2},
            {'name': 'Europe Playoff',        'note_col': 115, 'club_col': 115, 'rank_col': 116, 'start_row': 9,  'zone_row': 11},
            {'name': 'Relegation Playoff',    'note_col': 115, 'club_col': 115, 'rank_col': 116, 'start_row': 18, 'zone_row': 20},
        ],
        'group_keys': ['champions', 'europe', 'relegation'],
    },
    'CZE': {
        'full_name': '1. liga',
        'tiebreaker_row': 1,
        'tiebreaker_col': 143,
        'groups': [
            {'name': 'Champions Group',  'note_col': 144, 'club_col': 144, 'rank_col': 145, 'start_row': 0,  'zone_row': 2},
            {'name': 'Relegation Group', 'note_col': 144, 'club_col': 144, 'rank_col': 145, 'start_row': 11, 'zone_row': 13},
        ],
        'group_keys': ['champions', 'relegation'],
    },
}

# ── Zone overrides ────────────────────────────────────────────────────────────
# Use this to correct or supplement zones that the spreadsheet doesn't capture correctly.
# Format: league_code → {rank_string: (label, color)}
ZONE_OVERRIDES = {
    'ENG': {
        '6': ('Europa League',      '#833C00'),
        '7': ('Europa League',      '#833C00'),
        '8': ('Conference League',  '#375623'),
    },
    'FRA': {
        '5': ('Europa League',      '#833C00'),
        '6': ('Europa League',      '#833C00'),
        '7': ('Conference League',  '#375623'),
    },
    'TUR': {
        '3': ('Europa League',      '#833C00'),
        '4': ('Europa League',      '#833C00'),
        '5': ('Conference League',  '#375623'),
    },
    'NED': {
        '5': ('Conference League',  '#375623'),
    },
    # To override a zone in any league:
    # 'XXX': { 'N': ('Label', '#COLOR') },
}

# ── Manual notes ──────────────────────────────────────────────────────────────
# C = Champion, P = Promoted, R = Relegated
# Format: league_code → { club_name: note }
# Update this every cycle with that season's promotions/relegations/champions
MANUAL_NOTES = {
    'ENG':   {'Arsenal FC': 'C', 'West Ham United': 'R'},
    'ENG_2': {'Hull City': 'P'},
    'ENG_3': {'Bolton Wanderers': 'P'},
    'ENG_4': {'Notts County': 'P'},
    'ESP':   {'RCD Mallorca': 'R', 'Girona FC': 'R'},
    'ESP_2': {'RC Deportivo de La Coruña': 'P', 'SD Huesca': 'R', 'Real Zaragoza': 'R', 'Cultural Leonesa': 'R', 'Málaga CF': 'P'},
    'GER':   {'VfL Wolfsburg': 'R'},
    'GER_2': {'SV Elversberg': 'P', 'SC Paderborn 07': 'P'},
    'ITA':   {'US Cremonese': 'R'},
    'ITA_2': {'SSC Bari': 'R'},
    'NED':   {'FC Volendam': 'R'},
    'BEL':   {'Club Brugge KV': 'C', 'FCV Dender EH': 'R'},
    'CZE':   {'Slavia Praha': 'C', 'FK Dukla Praha': 'R'},
    # Belgium and Greece: notes also applied to group teams automatically
    # To add notes for a new season, just update the club names and letters above
}

# ── Luxembourg flag (was missing — added permanently) ─────────────────────────
# This gets injected automatically by update_site.py
LUX_FLAG_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#EF3340"/><rect y="4.67" width="20" height="4.67" fill="#fff"/><rect y="9.33" width="20" height="4.67" fill="#00A3E0"/></svg>'
