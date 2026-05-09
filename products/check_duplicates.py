"""
Duplicate guard for products/top-1000.csv

Usage (standalone):
    python products/check_duplicates.py
    python products/check_duplicates.py --threshold 90   # stricter warn threshold

Usage (import):
    from products.check_duplicates import check_product, load_catalog, DuplicateError

    catalog = load_catalog()
    result = check_product("New Product Name", "Category", catalog)
    # raises DuplicateError if true duplicate (score >= 95)
    # returns warnings list for near-duplicates (score >= 75)

Exit codes:
    0 — no blocking duplicates found
    1 — one or more true duplicates detected
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

try:
    from rapidfuzz import fuzz
    from rapidfuzz.utils import default_process
except ImportError:
    sys.exit(
        "Missing dependency: pip install rapidfuzz\n"
        "Or: pip install -r requirements.txt"
    )

CSV_PATH = Path(__file__).parent / "top-1000.csv"

# Score thresholds (0-100)
BLOCK_THRESHOLD = 95   # treat as true duplicate — hard block
WARN_THRESHOLD = 75    # likely near-duplicate — warn but allow

# Known multi-word brand prefixes (checked before falling back to first word).
# Add entries here when a brand name contains a space.
_MULTI_WORD_BRANDS: tuple[str, ...] = (
    "amazon basics",
    "amazon echo",
    "amazon fire",
    "all clad",
    "all-clad",
    "alpha grillers",
    "ninja creami",
    "instant pot",
    "le creuset",
    "de'longhi",
    "delonghi",
    "beats by dre",
    "beats by dr",
    "google pixel",
    "google nest",
    "samsung galaxy",
    "apple airpods",
    "apple macbook",
    "apple ipad",
    "apple iphone",
    "apple watch",
    "microsoft surface",
    "lg gram",
    "asus rog",
    "asus zenbook",
    "asus vivobook",
    "acer predator",
    "acer swift",
    "acer aspire",
    "acer nitro",
    "acer chromebook",
)


_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")


def extract_asin(url_or_text: str) -> str:
    """Pull a 10-char Amazon ASIN out of a URL or free-text. Returns '' if none."""
    if not url_or_text:
        return ""
    m = _ASIN_RE.search(url_or_text)
    return m.group(1) if m else ""


def extract_brand(product_name: str) -> str:
    """
    Return a normalised brand token for *product_name*.

    Strategy:
    1. Check known multi-word brand prefixes (case-insensitive).
    2. Fall back to the first word (covers the vast majority of cases where
       the brand is a single token: Canon, Nikon, Sony, Dell, Apple, …).

    The returned string is lowercased and stripped so it can be compared
    directly with ==.
    """
    lower = product_name.lower().strip()
    for brand in _MULTI_WORD_BRANDS:
        if lower.startswith(brand):
            return brand
    # Default: first whitespace-separated token
    return lower.split()[0] if lower.split() else ""


class Match(NamedTuple):
    name: str
    category: str
    row: int
    token_sort_score: float
    partial_score: float

    @property
    def max_score(self) -> float:
        return max(self.token_sort_score, self.partial_score)


@dataclass(frozen=True)
class DuplicateError(Exception):
    new_name: str
    match: Match

    def __str__(self) -> str:
        return (
            f"BLOCKED: '{self.new_name}' is a true duplicate of "
            f"'{self.match.name}' (row {self.match.row}, "
            f"score={self.match.max_score:.1f})"
        )


def load_catalog(csv_path: Path = CSV_PATH) -> list[dict]:
    """Return all rows from the CSV as a list of dicts."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _score_pair(name_a: str, name_b: str) -> tuple[float, float]:
    """Return (token_sort_ratio, partial_ratio) for two product names."""
    a = default_process(name_a)
    b = default_process(name_b)
    token_sort = fuzz.token_sort_ratio(a, b)
    partial = fuzz.partial_ratio(a, b)
    return float(token_sort), float(partial)


def check_product(
    name: str,
    category: str,
    catalog: list[dict],
    asin: str | None = None,
    block_threshold: float = BLOCK_THRESHOLD,
    warn_threshold: float = WARN_THRESHOLD,
) -> list[Match]:
    """
    Check a single product against the existing catalog.

    - If *asin* is provided and an existing row has the same ASIN, raises
      DuplicateError immediately (zero false positives, defeats name-divergence).
    - Raises DuplicateError for the first true name duplicate found (score >= block_threshold).
    - Returns a list of Match objects for near-duplicates (score >= warn_threshold).
    """
    warnings: list[Match] = []

    # ── ASIN exact-match guard (catches cases the fuzzy name check misses) ──
    if asin:
        for i, row in enumerate(catalog, start=2):
            if extract_asin(row.get("Amazon URL", "")) == asin:
                match = Match(
                    name=row.get("Product Name", "").strip(),
                    category=row.get("Category", "").strip(),
                    row=i,
                    token_sort_score=100.0,
                    partial_score=100.0,
                )
                raise DuplicateError(new_name=name, match=match)

    new_brand = extract_brand(name)

    for i, row in enumerate(catalog, start=2):  # row 1 = header
        existing_name = row.get("Product Name", "").strip()
        existing_category = row.get("Category", "").strip()

        if not existing_name:
            continue

        # Different manufacturers → cannot be duplicates
        if extract_brand(existing_name) != new_brand:
            continue

        # Normalise: if names are identical after stripping, always block
        if existing_name.lower() == name.lower():
            match = Match(
                name=existing_name,
                category=existing_category,
                row=i,
                token_sort_score=100.0,
                partial_score=100.0,
            )
            raise DuplicateError(new_name=name, match=match)

        token_sort, partial = _score_pair(name, existing_name)

        if max(token_sort, partial) >= block_threshold:
            match = Match(
                name=existing_name,
                category=existing_category,
                row=i,
                token_sort_score=token_sort,
                partial_score=partial,
            )
            raise DuplicateError(new_name=name, match=match)

        if max(token_sort, partial) >= warn_threshold:
            warnings.append(
                Match(
                    name=existing_name,
                    category=existing_category,
                    row=i,
                    token_sort_score=token_sort,
                    partial_score=partial,
                )
            )

    return warnings


def scan_catalog(
    catalog: list[dict],
    block_threshold: float = BLOCK_THRESHOLD,
    warn_threshold: float = WARN_THRESHOLD,
) -> tuple[list[tuple[int, int, Match]], list[tuple[int, int, Match]]]:
    """
    Scan all pairs in the catalog.

    Returns:
        blocked  — list of (row_a, row_b, Match) pairs that exceed block_threshold
        warnings — list of (row_a, row_b, Match) pairs that exceed warn_threshold
    """
    blocked: list[tuple[int, int, Match]] = []
    warnings: list[tuple[int, int, Match]] = []
    n = len(catalog)

    # ── ASIN duplicate sweep (cheap, catches name-divergent dupes) ──
    asin_to_row: dict[str, int] = {}
    for i in range(n):
        asin = extract_asin(catalog[i].get("Amazon URL", ""))
        if not asin:
            continue
        if asin in asin_to_row:
            j = asin_to_row[asin]
            blocked.append((
                j + 2,
                i + 2,
                Match(
                    name=catalog[i].get("Product Name", "").strip(),
                    category=catalog[i].get("Category", "").strip(),
                    row=i + 2,
                    token_sort_score=100.0,
                    partial_score=100.0,
                ),
            ))
        else:
            asin_to_row[asin] = i

    for i in range(n):
        name_a = catalog[i].get("Product Name", "").strip()
        cat_a = catalog[i].get("Category", "").strip()
        if not name_a:
            continue
        brand_a = extract_brand(name_a)

        for j in range(i + 1, n):
            name_b = catalog[j].get("Product Name", "").strip()
            cat_b = catalog[j].get("Category", "").strip()
            if not name_b:
                continue

            # Different manufacturers → skip
            if extract_brand(name_b) != brand_a:
                continue

            if name_a.lower() == name_b.lower():
                match = Match(name_b, cat_b, j + 2, 100.0, 100.0)
                blocked.append((i + 2, j + 2, match))
                continue

            token_sort, partial = _score_pair(name_a, name_b)
            score = max(token_sort, partial)

            if score >= block_threshold:
                blocked.append(
                    (i + 2, j + 2, Match(name_b, cat_b, j + 2, token_sort, partial))
                )
            elif score >= warn_threshold:
                warnings.append(
                    (i + 2, j + 2, Match(name_b, cat_b, j + 2, token_sort, partial))
                )

    return blocked, warnings


def _print_section(
    label: str,
    symbol: str,
    pairs: list[tuple[int, int, Match]],
    catalog: list[dict],
) -> None:
    if not pairs:
        return
    print(f"\n{'='*70}")
    print(f"  {symbol}  {label} ({len(pairs)} pairs)")
    print(f"{'='*70}")
    for row_a, row_b, match in pairs:
        name_a = catalog[row_a - 2].get("Product Name", "")
        cat_a = catalog[row_a - 2].get("Category", "")
        print(
            f"\n  Row {row_a}: {name_a!r}  [{cat_a}]\n"
            f"  Row {row_b}: {match.name!r}  [{match.category}]\n"
            f"  token_sort={match.token_sort_score:.1f}  "
            f"partial={match.partial_score:.1f}  "
            f"max={match.max_score:.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan products/top-1000.csv for duplicate or near-duplicate entries."
    )
    parser.add_argument(
        "--csv", type=Path, default=CSV_PATH, help="Path to products CSV"
    )
    parser.add_argument(
        "--block-threshold",
        type=float,
        default=BLOCK_THRESHOLD,
        metavar="SCORE",
        help=f"Score >= this is a hard duplicate (default: {BLOCK_THRESHOLD})",
    )
    parser.add_argument(
        "--warn-threshold",
        type=float,
        default=WARN_THRESHOLD,
        metavar="SCORE",
        help=f"Score >= this triggers a warning (default: {WARN_THRESHOLD})",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Exit 0 even when blocking duplicates exist (report only)",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    print(f"Loading catalog from {args.csv} …")
    catalog = load_catalog(args.csv)
    print(f"  {len(catalog)} products loaded")
    print(
        f"  block threshold: {args.block_threshold}  |  "
        f"warn threshold:  {args.warn_threshold}"
    )
    print("Scanning all pairs …")

    blocked, warnings = scan_catalog(catalog, args.block_threshold, args.warn_threshold)

    _print_section("TRUE DUPLICATES (blocked)", "🚫", blocked, catalog)
    _print_section("NEAR-DUPLICATES (warning)", "⚠️ ", warnings, catalog)

    print(f"\n{'─'*70}")
    print(f"  Scan complete: {len(blocked)} blocked, {len(warnings)} warnings")

    if blocked and not args.warn_only:
        print("  Exit 1 — resolve blocking duplicates before publishing.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
