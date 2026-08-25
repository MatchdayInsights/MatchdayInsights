"""
generate_slug_registry.py

Builds slug_registry.json keyed by team_id (permanent, survives club renames).

Inputs:
  - club_metadata.json   {team_id: {name, country, league_code, season}}
  - rankings.json        {team_id: {...}}  (used only to flag currently-tracked)
  - slug_registry.json   OLD registry, keyed "Name||COUNTRY" -> slug
                          (reused verbatim wherever we can confidently match it
                          to a team_id, to preserve existing indexed URLs)

Output:
  - slug_registry.json (NEW structure)
      {
        "by_team_id": {
          "<team_id>": {
            "slug": "...",
            "name": "...",
            "country": "...",
            "source": "legacy" | "generated",
            "tracked": true|false
          },
          ...
        },
        "by_slug": {
          "<slug>": "<team_id>",
          ...
        }
      }

Design notes (see handoff doc for full context):
  - Slugs are assigned for EVERY club in club_metadata.json, not just
    currently-tracked ones, so a slug never has to change if a club drops out
    of / re-enters tracked status.
  - Old slugs are matched via normalized-name + country. Only UNIQUE matches
    are reused; ambiguous or missing matches get a freshly generated slug.
    This is deliberately conservative: a wrongly-preserved alias (pointing an
    old URL at the wrong club) is worse than a clean new URL.
  - New slugs use unidecode for accurate transliteration (the old registry's
    ad-hoc folding silently dropped some accented characters, e.g. Czech
    "ě" -> nothing instead of "e" -- see 'Prostějov' -> 'prost-jov' bug).
  - Collision resolution order: bare slug -> slug+country -> slug+team_id.
"""

import json
import re
from pathlib import Path
from unidecode import unidecode

DATA_DIR = Path("/mnt/user-data/uploads")
OUT_DIR = Path("/mnt/user-data/outputs")

# --- name normalization (for matching old registry entries to team_ids) ---

NOISE_PREFIXES = re.compile(
    r"^(1\.|fc|sk|sc|afc|cf|cd|ac|as|us|ss|ssd|ud|se|ec|acf|acr|acd|acsd|"
    r"asd|ssc|ogc|rc|rcd|cd|ca|club|de|deportivo)\s+",
    re.I,
)
YEAR_SUFFIX = re.compile(r"\s+(18|19|20)\d{2}$")
LEADING_NUMERIC_PREFIX = re.compile(r"^\d+\.\s*")


def normalize_for_matching(name: str) -> str:
    """Aggressively normalize a club name for fuzzy old-registry matching.
    NOT used for slug generation itself -- matching only."""
    n = name.strip()
    n = LEADING_NUMERIC_PREFIX.sub("", n)
    prev = None
    while prev != n:
        prev = n
        n = NOISE_PREFIXES.sub("", n)
    n = YEAR_SUFFIX.sub("", n)
    n = unidecode(n).lower()
    n = re.sub(r"[^a-z0-9]+", " ", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


# --- slug generation (for clubs with no usable old-registry match) ---

def slugify(name: str) -> str:
    n = unidecode(name).lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    n = re.sub(r"-{2,}", "-", n)
    return n


def main():
    with open(DATA_DIR / "club_metadata.json") as f:
        meta = json.load(f)
    with open(DATA_DIR / "rankings.json") as f:
        rankings = json.load(f)
    with open(DATA_DIR / "slug_registry.json") as f:
        old_registry = json.load(f)

    tracked_ids = set(rankings.keys())

    # Build normalized-name+country -> [team_ids] index from current metadata
    meta_norm_index = {}
    for tid, m in meta.items():
        key = (normalize_for_matching(m["name"]), m["country"])
        meta_norm_index.setdefault(key, []).append(tid)

    # Match old registry entries to team_ids; keep only unambiguous matches
    old_slug_for_team_id = {}
    ambiguous_old_entries = []
    unmatched_old_entries = []
    for old_key, old_slug in old_registry.items():
        old_name, old_country = old_key.split("||")
        nk = (normalize_for_matching(old_name), old_country)
        candidates = meta_norm_index.get(nk, [])
        if len(candidates) == 1:
            tid = candidates[0]
            # If two different old entries somehow map to the same team_id,
            # that's a real ambiguity -- don't silently overwrite.
            if tid in old_slug_for_team_id and old_slug_for_team_id[tid] != old_slug:
                ambiguous_old_entries.append((old_key, old_slug, "conflicts_with_other_old_entry"))
            else:
                old_slug_for_team_id[tid] = old_slug
        elif len(candidates) > 1:
            ambiguous_old_entries.append((old_key, old_slug, f"multiple_team_ids:{candidates}"))
        else:
            unmatched_old_entries.append((old_key, old_slug))

    # Assign a slug to every club in club_metadata.json
    by_team_id = {}
    claimed_slugs = {}  # slug -> team_id, for collision detection as we go

    # Process legacy-matched clubs first so they get first claim on their old slug
    all_team_ids = sorted(meta.keys(), key=lambda t: (t not in old_slug_for_team_id, t))

    for tid in all_team_ids:
        m = meta[tid]
        name, country = m["name"], m["country"]

        if tid in old_slug_for_team_id:
            slug = old_slug_for_team_id[tid]
            source = "legacy"
        else:
            base = slugify(name)
            slug = base
            source = "generated"

        # Collision resolution: bare -> +country -> +team_id
        if slug in claimed_slugs and claimed_slugs[slug] != tid:
            candidate = f"{slug}-{country.lower()}"
            if candidate in claimed_slugs and claimed_slugs[candidate] != tid:
                candidate = f"{slug}-{tid}"
            slug = candidate
            if source == "legacy":
                source = "legacy_disambiguated"

        claimed_slugs[slug] = tid
        by_team_id[tid] = {
            "slug": slug,
            "name": name,
            "country": country,
            "source": source,
            "tracked": tid in tracked_ids,
        }

    by_slug = {v["slug"]: tid for tid, v in by_team_id.items()}

    output = {"by_team_id": by_team_id, "by_slug": by_slug}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "slug_registry.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # --- report ---
    n_legacy = sum(1 for v in by_team_id.values() if v["source"].startswith("legacy"))
    n_generated = sum(1 for v in by_team_id.values() if v["source"] == "generated")
    print(f"Total clubs assigned slugs: {len(by_team_id)}")
    print(f"  Legacy slug reused:        {n_legacy}")
    print(f"  Freshly generated:         {n_generated}")
    print(f"Old registry entries:        {len(old_registry)}")
    print(f"  Matched -> reused:         {len(old_slug_for_team_id)}")
    print(f"  Ambiguous (skipped):       {len(ambiguous_old_entries)}")
    print(f"  Unmatched (skipped):       {len(unmatched_old_entries)}")
    print(f"by_slug entries (should equal total clubs, confirms bijection): {len(by_slug)}")

    if ambiguous_old_entries:
        print("\nAmbiguous old entries (not linked, needs manual review):")
        for k, s, reason in ambiguous_old_entries:
            print(f"  {k} -> {s}  ({reason})")

    # Save unmatched list for manual review
    with open(OUT_DIR / "slug_registry_unmatched_legacy.json", "w") as f:
        json.dump(
            {"unmatched_old_entries": unmatched_old_entries,
             "ambiguous_old_entries": ambiguous_old_entries},
            f, indent=2, ensure_ascii=False
        )


if __name__ == "__main__":
    main()
