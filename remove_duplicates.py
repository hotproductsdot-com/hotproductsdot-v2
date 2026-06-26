#!/usr/bin/env python3
"""
remove_duplicates.py - Remove same make/model duplicates from products/top-1000.csv

Uses fuzzy matching PLUS model-number-aware logic to distinguish true
duplicates (same product listed twice with different name lengths) from
different models (Razer Blade 14 vs 16, Tab S9 vs S10, etc.).

Usage:
    python3 remove_duplicates.py              # Preview duplicates (dry run)
    python3 remove_duplicates.py --apply      # Actually remove duplicates
    python3 remove_duplicates.py --threshold 90  # Lower matching threshold
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "products"))
from check_duplicates import extract_brand

try:
    from rapidfuzz import fuzz
    from rapidfuzz.utils import default_process
except ImportError:
    sys.exit("Missing dependency: pip install rapidfuzz")

CSV_PATH = Path("products/top-1000.csv")

FIELDNAMES = [
    "Product Name", "Category", "Price Range", "Review Count",
    "Rating", "BSR", "Affiliate Potential", "Amazon URL",
    "Refreshed Date", "Action Needed",
]

# ---------------------------------------------------------------------------
# Model differentiation — token-diff approach
# ---------------------------------------------------------------------------

# Words that are generic descriptors (don't distinguish models)
_GENERIC_WORDS: frozenset[str] = frozenset({
    "smart", "wireless", "bluetooth", "portable", "digital", "premium",
    "advanced", "professional", "indoor", "outdoor", "home", "camera",
    "speaker", "display", "headset", "headphones", "earbuds", "mouse",
    "keyboard", "monitor", "laptop", "desktop", "tablet", "phone",
    "watch", "ring", "drone", "vacuum", "robot", "cleaner", "true",
    "noise", "cancelling", "canceling", "active", "self", "emptying",
    "control", "panel", "hub", "device", "system", "kit", "set",
    "edition", "with", "and", "for", "the", "in", "of", "a", "an",
    "new", "latest", "best", "top", "rated", "selling", "2024", "2025",
    "2023", "2022", "2026", "electric", "cordless", "powered", "rechargeable",
    "waterproof", "bundle", "combo", "pack", "piece", "certified",
    "refurbished", "renewed", "updated", "improved", "enhanced",
    "gaming", "fitness", "exercise", "training", "running", "sport",
    "sports", "health", "wellness", "beauty", "care", "personal",
    "automatic", "auto", "full", "size", "compact", "slim", "mini",
    "standard", "classic", "original", "official", "genuine",
})


def _tokenize(name: str) -> list[str]:
    """Split a name into normalized tokens (lowercase, alphanumeric only)."""
    # Keep alphanumeric chars and +, collapse everything else to spaces
    cleaned = re.sub(r"[^a-zA-Z0-9+]+", " ", name.lower()).strip()
    return cleaned.split()


def _token_has_digit(token: str) -> bool:
    """Check if a token contains any digit."""
    return bool(re.search(r"\d", token))


def _is_same_product(name_a: str, name_b: str) -> bool:
    """
    Determine if two high-fuzzy-score names refer to the SAME product.

    Strategy: tokenize both names, find the words unique to each side.
    If the differing words are all generic descriptors (no model numbers),
    it's the same product with a longer/shorter name. If any differing
    word contains a digit or is a known model differentiator, they are
    different products.

    Examples:
      SAME:  'Fitbit Sense 2' vs 'Fitbit Sense 2 Advanced Smartwatch'
             diff = {advanced, smartwatch} → all generic → SAME
      DIFF:  'Razer Blade 14' vs 'Razer Blade 16'
             diff = {14} vs {16} → digits → DIFFERENT
      DIFF:  'Samsung Galaxy Book5 Pro 360' vs 'Samsung Galaxy Book3 Pro 360'
             diff = {book5} vs {book3} → digits → DIFFERENT
      SAME:  'Canon EOS R5 Mark II' vs 'Canon EOS R5 Mark II Mirrorless Camera'
             diff = {mirrorless, camera} → all generic → SAME
    """
    tokens_a = _tokenize(name_a)
    tokens_b = _tokenize(name_b)

    set_a = set(tokens_a)
    set_b = set(tokens_b)

    # Tokens unique to each side
    only_a = set_a - set_b
    only_b = set_b - set_a

    # If one is a perfect superset, it's the same product with more detail
    if not only_a or not only_b:
        # One side has no unique tokens → same product
        # Check that the extra words are just generic descriptors
        extra = only_a | only_b
        if all(w in _GENERIC_WORDS for w in extra):
            return True
        # Extra words contain something specific but only on one side
        # Still likely the same product with a longer description
        # UNLESS the extra words contain digits (model numbers)
        if not any(_token_has_digit(w) for w in extra):
            return True
        # Extra words have digits — could be a model variant added
        # e.g., "Sony FE 24-70mm f/2.8 GM" vs "Sony FE 24-70mm f/2.8 GM II Lens"
        # "II" and "Lens" are extra. "ii" has no digit. But "2" might appear.
        # Be conservative: if it's just ordinals/generations, still same product
        digit_extras = {w for w in extra if _token_has_digit(w)}
        # If the digit-containing extras are just years, it's fine
        if all(re.fullmatch(r"20\d{2}", w) for w in digit_extras):
            return True
        return False

    # Both sides have unique tokens. Check if any contain digits.
    a_has_model = any(_token_has_digit(w) for w in only_a)
    b_has_model = any(_token_has_digit(w) for w in only_b)

    if a_has_model and b_has_model:
        # Both sides have different model-like tokens → different products
        # e.g., {book5} vs {book3}, {14} vs {16}, {xm5} vs {xm6}
        return False

    if a_has_model or b_has_model:
        # One side has a model number the other doesn't
        # e.g., "Fire TV Stick 4K Max" vs "Fire TV Stick HD"
        # Check if the non-digit side has a variant word
        non_digit_side = only_b if a_has_model else only_a
        variant_words = {"hd", "sd", "uhd", "fhd", "qhd", "xl", "xs",
                         "lite", "light", "plus", "ultra", "fe", "se",
                         "max", "pro", "air", "mini", "nano", "mega"}
        if non_digit_side & variant_words:
            return False  # different variant

    # Remaining diffs are all non-numeric
    # Check if they're just generic descriptors
    all_diffs = only_a | only_b
    if all(w in _GENERIC_WORDS for w in all_diffs):
        return True

    # Some non-generic, non-numeric difference
    # Could be variant names like "Ultra" vs "Plus" or "MK2" vs "XL"
    variant_words = {"hd", "sd", "uhd", "fhd", "qhd", "xl", "xs",
                     "lite", "light", "plus", "ultra", "fe", "se",
                     "max", "pro", "air", "mini", "nano", "mega",
                     "standard", "basic", "essential"}
    a_variants = only_a & variant_words
    b_variants = only_b & variant_words
    if a_variants and b_variants and a_variants != b_variants:
        # Different variant labels → different products
        # e.g., "Stream Deck MK.2" vs "Stream Deck XL"
        return False

    # Default: if non-generic words differ but no clear model signal,
    # treat as same product (fuzzy score already confirmed high similarity)
    return True


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DupPair:
    row_a: int
    row_b: int
    name_a: str
    name_b: str
    category_a: str
    category_b: str
    score: float
    keep: int
    remove: int
    reason: str


def _normalize_name(name: str) -> str:
    """
    Strip noise that inflates/deflates fuzzy scores without changing
    which product is being described.

    Removes:
      - Parenthetical year suffixes: (2022), (2024), (3rd Gen, 2022)
      - Trailing year: "... 2024"
      - Edition/generation suffixes already captured elsewhere
    """
    # Remove parenthetical blocks that are just year or gen+year
    # e.g., "(2022)", "(3rd Gen, 2022)", "(2024 Edition)"
    out = re.sub(
        r"\s*\(\s*(?:\d+\w*\s+Gen(?:eration)?\s*,?\s*)?(?:20\d{2})(?:\s+Edition)?\s*\)",
        "",
        name,
        flags=re.I,
    )
    # Remove trailing bare year: "Foo Bar 2022" → "Foo Bar"
    out = re.sub(r"\s+20\d{2}\s*$", "", out)
    return out.strip()


def _score_pair(a: str, b: str) -> tuple[float, float]:
    """Return (token_sort_ratio, partial_ratio) after normalizing names."""
    na = _normalize_name(a)
    nb = _normalize_name(b)
    pa = default_process(na)
    pb = default_process(nb)
    return (
        fuzz.token_sort_ratio(pa, pb),
        fuzz.partial_ratio(pa, pb),
    )


def _row_quality(row: dict[str, str]) -> tuple[int, int, int, int]:
    """
    Score a row's data quality. Higher = better.
    (has_direct_url, review_count, name_length, filled_fields)
    """
    url = row.get("Amazon URL", "")
    has_direct = 1 if "/dp/" in url else 0

    review_str = row.get("Review Count", "0").strip().replace(",", "")
    try:
        reviews = int(review_str)
    except ValueError:
        reviews = 0

    name_len = len(row.get("Product Name", "").strip())
    filled = sum(1 for v in row.values() if v and v.strip())

    return (has_direct, reviews, name_len, filled)


def _pick_keeper(
    idx_a: int,
    idx_b: int,
    row_a: dict[str, str],
    row_b: dict[str, str],
) -> tuple[int, int, str]:
    """Decide which row to keep. Returns (keep_idx, remove_idx, reason)."""
    qa = _row_quality(row_a)
    qb = _row_quality(row_b)

    # 1. Prefer direct /dp/ URL
    if qa[0] != qb[0]:
        if qa[0] > qb[0]:
            return idx_a, idx_b, "has direct /dp/ URL"
        return idx_b, idx_a, "has direct /dp/ URL"

    # 2. Prefer higher review count
    if qa[1] != qb[1]:
        if qa[1] > qb[1]:
            return idx_a, idx_b, f"more reviews ({qa[1]:,} vs {qb[1]:,})"
        return idx_b, idx_a, f"more reviews ({qb[1]:,} vs {qa[1]:,})"

    # 3. Prefer more descriptive name
    if qa[2] != qb[2]:
        if qa[2] > qb[2]:
            return idx_a, idx_b, "more descriptive name"
        return idx_b, idx_a, "more descriptive name"

    # 4. More filled fields
    if qa[3] != qb[3]:
        if qa[3] > qb[3]:
            return idx_a, idx_b, "more data fields"
        return idx_b, idx_a, "more data fields"

    # 5. Tie: keep earlier row
    return idx_a, idx_b, "earlier entry (tie-breaker)"


def find_duplicates(
    catalog: list[dict[str, str]],
    threshold: float,
) -> tuple[list[DupPair], list[tuple[str, str, float, str]]]:
    """
    Find duplicate pairs. Returns (duplicates, skipped_as_different_model).
    """
    n = len(catalog)
    pairs: list[DupPair] = []
    skipped: list[tuple[str, str, float, str]] = []

    for i in range(n):
        name_a = catalog[i].get("Product Name", "").strip()
        if not name_a:
            continue
        brand_a = extract_brand(name_a)

        for j in range(i + 1, n):
            name_b = catalog[j].get("Product Name", "").strip()
            if not name_b:
                continue

            if extract_brand(name_b) != brand_a:
                continue

            # Exact match
            if name_a.lower() == name_b.lower():
                score = 100.0
            else:
                ts, pr = _score_pair(name_a, name_b)
                score = max(ts, pr)

            if score < threshold:
                continue

            # KEY CHECK: are these actually the same product?
            if not _is_same_product(name_a, name_b):
                skipped.append((name_a, name_b, score, "different model/variant"))
                continue

            keep_idx, remove_idx, reason = _pick_keeper(
                i, j, catalog[i], catalog[j],
            )

            pairs.append(DupPair(
                row_a=i + 2,
                row_b=j + 2,
                name_a=name_a,
                name_b=name_b,
                category_a=catalog[i].get("Category", ""),
                category_b=catalog[j].get("Category", ""),
                score=score,
                keep=keep_idx + 2,
                remove=remove_idx + 2,
                reason=reason,
            ))

    return pairs, skipped


def resolve_removals(pairs: list[DupPair]) -> set[int]:
    """
    Resolve transitive duplicates into a consistent set of 0-based
    indices to remove.
    """
    to_remove: set[int] = set()

    for pair in pairs:
        remove_idx = pair.remove - 2
        keep_idx = pair.keep - 2

        # If we already marked the "keep" row for removal, swap
        if keep_idx in to_remove:
            to_remove.discard(keep_idx)
            to_remove.add(remove_idx)
        else:
            to_remove.add(remove_idx)

    return to_remove


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find and remove same make/model duplicate products",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually remove duplicates (default: dry run)",
    )
    parser.add_argument(
        "--threshold", type=float, default=95.0,
        help="Fuzzy match score threshold (default: 95)",
    )
    parser.add_argument(
        "--csv", type=Path, default=CSV_PATH,
        help=f"Path to CSV (default: {CSV_PATH})",
    )
    parser.add_argument(
        "--show-skipped", action="store_true",
        help="Also show pairs skipped as different models",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    # utf-8-sig strips the BOM so DictReader's first key is "Product Name", not
    # "﻿Product Name" — the latter silently blanks every name on rewrite.
    with args.csv.open(newline="", encoding="utf-8-sig") as f:
        catalog = list(csv.DictReader(f))
    print(f"Loaded {len(catalog)} products from {args.csv}")
    print(f"Duplicate threshold: {args.threshold}")

    print("Scanning for same make/model duplicates...\n")
    pairs, skipped = find_duplicates(catalog, args.threshold)

    # Show skipped (different models that fuzzy matching would have caught)
    if args.show_skipped and skipped:
        print(f"Correctly skipped {len(skipped)} different-model pair(s):")
        for name_a, name_b, score, reason in skipped:
            print(f"  [{score:.0f}] {name_a[:50]} vs {name_b[:50]} ({reason})")
        print()

    if not pairs:
        print("No same-model duplicates found.")
        if skipped:
            print(f"({len(skipped)} different-model pairs correctly ignored)")
        return 0

    # Display duplicates
    print(f"Found {len(pairs)} same-model duplicate pair(s):\n")
    print(f"{'─'*72}")

    for i, p in enumerate(pairs, 1):
        keep_name = p.name_a if p.keep == p.row_a else p.name_b
        remove_name = p.name_b if p.keep == p.row_a else p.name_a
        keep_cat = p.category_a if p.keep == p.row_a else p.category_b
        remove_cat = p.category_b if p.keep == p.row_a else p.category_a

        print(f"\n  {i}. (score: {p.score:.1f})")
        print(f"     KEEP   (row {p.keep:3d}): {keep_name}")
        print(f"                        [{keep_cat}]")
        print(f"     REMOVE (row {p.remove:3d}): {remove_name}")
        print(f"                        [{remove_cat}]")
        print(f"     Reason: {p.reason}")

    print(f"\n{'─'*72}")

    to_remove = resolve_removals(pairs)
    print(f"\nTotal rows to remove: {len(to_remove)}")
    if skipped:
        print(f"Different-model pairs correctly skipped: {len(skipped)}")

    if not args.apply:
        print("\n  [DRY RUN] No changes made. Re-run with --apply to remove duplicates.")
        return 0

    # Apply
    cleaned = [row for i, row in enumerate(catalog) if i not in to_remove]
    print(f"\n  Removing {len(to_remove)} products: {len(catalog)} -> {len(cleaned)}")

    # Derive fieldnames from the live data so extra columns (e.g. sale columns)
    # are never dropped; fall back to FIELDNAMES only when there are no rows.
    fieldnames = list(cleaned[0].keys()) if cleaned else list(FIELDNAMES)
    for row in cleaned:
        for k in row:
            if k not in fieldnames:
                fieldnames.append(k)
    with args.csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in cleaned:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"  CSV updated: {args.csv}")
    print(f"  Final product count: {len(cleaned)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
