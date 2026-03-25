"""Price extraction for Makro promotional PDF pamphlets.

Strategy: use product size lines ("1 x 750 ml") as anchor points.
  - Look backward from the size for brand + description
  - Look forward from the size for SKU, savings, and price
"""

import re
import logging

logger = logging.getLogger(__name__)

SIZE_RE = re.compile(r"(\d+\s*x\s*[\d.]+\s*(?:ml|L|l))\b", re.IGNORECASE)
SKU_RE = re.compile(r"\([\d;,\s]+\)")
SAVE_RE = re.compile(r"Save\s+(\d[\d\s]*)", re.IGNORECASE)
BARE_PRICE_RE = re.compile(r"^(\d{2,6})$")
UNIT_RE = re.compile(r"^(each|per\s+(?:case|pack|6-pack|4-pack|12-pack))$", re.IGNORECASE)
PAGE_MARKER_RE = re.compile(r"^--\s*\d+\s+of\s+\d+\s*--$")

# Inline: "PRODUCT 1 x 750 ml (SKU) Save NN NNN each"
# Or: "PRODUCT 1 x 750 ml (SKU) NNN each"
INLINE_RE = re.compile(
    r"^(.+?)\s+(\d+\s*x\s*[\d.]+\s*(?:ml|L|l))\s*"
    r"(?:\([^)]+\)\s*)?"
    r"(?:Save\s+\d+\s+)?"
    r"(\d{2,6})\s+(each|per\s+(?:case|pack|6-pack|4-pack|12-pack))",
    re.IGNORECASE,
)

# Lines that clearly are NOT product names
BOUNDARY_RE = re.compile(
    r"^(NOW|FREE|OR|each|per\s+case|per\s+pack|per\s+\d+-pack|SAVE\s+\d|"
    r"Terms and conditions|Prices valid|For our full|DRINK RESPONSIBLY|"
    r"Shop online|Get in that|Now that|For store details|Massmart|"
    r"EXCLUSIVE|BUY$|AND$|--\s*\d+|SHOP|ONLINE|0800|Save\s+\d)"
    r"$",
    re.IGNORECASE,
)

# Section headers — not product names but useful context
SECTION_RE = re.compile(
    r"^(COGNAC|BRANDY|RUM|WHISK|TEQUILA|LIQUEUR|VODKA|GIN|BEER|COOLER|"
    r"BUBBLES|PREMIUM|BUY\s+5|BUY\s+A\s+CASE|BUY ALL)",
    re.IGNORECASE,
)

# Case pricing headers on wine pages
CASE_HEADER_RE = re.compile(r"^\d+\s*x\s*[\d.]+\s*(?:ml|L)\s+R\s*[\d\s]+$", re.IGNORECASE)
UNIT_CASE_RE = re.compile(r"^Unit\s+price\s+per\s+case$", re.IGNORECASE)
UNIT_CASE_PRICE_RE = re.compile(r"^R\s*([\d,.]+)$")


def _clean_price(s: str) -> int | None:
    s = s.strip().replace(" ", "").replace(",", "")
    if s.isdigit():
        return int(s)
    return None


def _is_noise(line: str) -> bool:
    """Return True for lines that should never be part of a product name."""
    if not line:
        return True
    if BOUNDARY_RE.match(line):
        return True
    if PAGE_MARKER_RE.match(line):
        return True
    if BARE_PRICE_RE.match(line):
        return True
    # Pure digit lines (variant numbers like "1", "2", "3")
    if re.match(r"^\d{1,2}$", line):
        return True
    # Lines that are just numbers with tabs
    if re.match(r"^[\d\s\t]+$", line):
        return True
    return False


def _is_brand_like(line: str) -> bool:
    """Heuristic: brand lines are mostly uppercase, at least 3 alpha chars."""
    alpha = re.sub(r"[^A-Za-z]", "", line)
    if len(alpha) < 3:
        return False
    upper = sum(1 for c in alpha if c.isupper())
    return upper / len(alpha) > 0.70


def _find_name_backward(lines: list[str], size_idx: int) -> str:
    """Look backward from the size line to build the product name.

    Stops at noise lines, other product end markers (NOW, each, per case),
    or when we've gone too far back.
    """
    parts = []
    max_back = 6
    start = max(0, size_idx - max_back)

    for i in range(size_idx - 1, start - 1, -1):
        line = lines[i].strip()

        if _is_noise(line):
            break
        if SECTION_RE.match(line):
            break
        if CASE_HEADER_RE.match(line):
            break
        if UNIT_CASE_RE.match(line):
            break
        if UNIT_CASE_PRICE_RE.match(line):
            break
        if re.search(r"Terms and conditions", line, re.IGNORECASE):
            break
        if re.search(r"Unit price per case", line, re.IGNORECASE):
            break
        # If this line contains a price pattern from a *previous* product, stop
        if re.search(r"\d{2,6}\s+each", line, re.IGNORECASE):
            break
        if re.search(r"\d{2,6}\s+per\s+(?:case|pack)", line, re.IGNORECASE):
            break

        # Skip SKUs
        if SKU_RE.match(line.strip("() ")):
            continue

        parts.insert(0, line)

    return " ".join(parts).strip()


def _find_price_forward(lines: list[str], size_idx: int) -> dict | None:
    """Look forward from the size line to find SKU, savings, price, and unit."""
    max_fwd = 8
    end = min(len(lines), size_idx + max_fwd + 1)

    savings = None
    price = None
    unit = "each"

    i = size_idx + 1
    while i < end:
        line = lines[i].strip()

        if not line or PAGE_MARKER_RE.match(line):
            break

        # SKU — skip it but check for inline price after it
        if SKU_RE.search(line):
            # Check if there's a price on the same line after the SKU
            after_sku = SKU_RE.sub("", line).strip()
            if after_sku:
                sm = SAVE_RE.search(after_sku)
                if sm:
                    savings = _clean_price(sm.group(1))
                    after_sku = SAVE_RE.sub("", after_sku).strip()
                pm = re.search(r"(\d{2,6})\s+(each|per\s+\w+)", after_sku, re.IGNORECASE)
                if pm:
                    price = _clean_price(pm.group(1))
                    unit = pm.group(2).lower()
                    return {"price": price, "unit": unit, "savings": savings}
            i += 1
            continue

        # Save line
        sm = SAVE_RE.match(line)
        if sm:
            savings = _clean_price(sm.group(1))
            rest = line[sm.end():].strip()
            if rest:
                pm = re.search(r"(\d{2,6})\s+(each|per\s+\w+)", rest, re.IGNORECASE)
                if pm:
                    price = _clean_price(pm.group(1))
                    unit = pm.group(2).lower()
                    return {"price": price, "unit": unit, "savings": savings}
            i += 1
            continue

        # Bare price
        bm = BARE_PRICE_RE.match(line)
        if bm:
            price = _clean_price(bm.group(1))
            i += 1
            # Look for unit on next line
            if i < end and UNIT_RE.match(lines[i].strip()):
                unit = lines[i].strip().lower()
            return {"price": price, "unit": unit, "savings": savings}

        # Unit line without preceding price — means we missed the price
        if UNIT_RE.match(line):
            break

        # If we hit a brand-like line, we've gone too far
        if _is_brand_like(line) and not SIZE_RE.search(line):
            break

        # NOW — means previous product ended
        if line.upper() == "NOW":
            break

        i += 1

    if price and price > 0:
        return {"price": price, "unit": unit, "savings": savings}
    return None


def _parse_inline(line: str, page: int) -> list[dict]:
    """Parse a line that contains one or more inline product+price entries.

    Format examples:
      "CÎROC Premium Imported Snapfrost Vodka 1 x 750 ml (107254) 499 each"
      "5 Year Old Brandy 1 x 750 ml (54539)) Save 14 195 each"
    """
    results = []
    # Find all "NNN each" or "NNN per case" occurrences
    for m in re.finditer(
        r"(.+?)\s+(\d+\s*x\s*[\d.]+\s*(?:ml|L|l))\s*"
        r"(?:\([^)]*\)\s*\)?\s*)?"
        r"(?:Save\s+\d+\s+)?"
        r"(\d{2,6})\s+(each|per\s+(?:case|pack|6-pack|4-pack|12-pack))",
        line, re.IGNORECASE,
    ):
        item_text = m.group(1).strip()
        size = m.group(2).strip()
        price = _clean_price(m.group(3))
        unit = m.group(4).strip().lower()

        # Clean leading prices/noise from previous product in same line
        item_text = re.sub(r"^\d{2,6}\s+each\s*", "", item_text, flags=re.IGNORECASE).strip()
        item_text = re.sub(r"^\d{2,6}\s+per\s+\w+\s*", "", item_text, flags=re.IGNORECASE).strip()

        save_m = SAVE_RE.search(m.group(0))
        savings = _clean_price(save_m.group(1)) if save_m else None

        if item_text and price and price > 0:
            results.append({
                "item": item_text,
                "price": float(price),
                "size": size,
                "unit": unit,
                "savings": float(savings) if savings else None,
                "page": page,
                "confidence": 0.85,
                "source": "makro",
            })
    return results


def extract_prices(rows: list[dict]) -> list[dict]:
    """Parse Makro PDF rows into structured item/price dicts."""
    lines = [r["raw"] for r in rows]
    pages = [r.get("page", 0) for r in rows]

    results = []
    used_indices = set()

    # Pass 1: find inline products (full product + price on one line)
    for i, line in enumerate(lines):
        if re.search(r"\d+\s*x\s*[\d.]+\s*(?:ml|L)\b.*\d{2,6}\s+(?:each|per\s)", line, re.IGNORECASE):
            inlines = _parse_inline(line, pages[i])
            if inlines:
                results.extend(inlines)
                used_indices.add(i)

    # Pass 2: anchor on size lines and build products
    for i, line in enumerate(lines):
        if i in used_indices:
            continue

        line_stripped = line.strip()
        size_m = SIZE_RE.search(line_stripped)
        if not size_m:
            continue

        # Skip if this is a case header like "6 x 750 ml R3594"
        if CASE_HEADER_RE.match(line_stripped):
            continue

        # Skip if this line is mostly a size and nothing else useful
        size_text = size_m.group(1)

        # Look backward for the product name
        name = _find_name_backward(lines, i)

        # Check if there's text before the size on the same line
        prefix = line_stripped[:size_m.start()].strip()
        if prefix and not re.match(r"^\d{1,2}$", prefix):
            # Prepend it to the name if it's descriptive
            if not _is_noise(prefix):
                if name:
                    name = name + " " + prefix
                else:
                    name = prefix

        if not name:
            continue

        # Look forward for price
        price_info = _find_price_forward(lines, i)
        if not price_info or not price_info["price"] or price_info["price"] <= 0:
            continue

        results.append({
            "item": name,
            "price": float(price_info["price"]),
            "size": size_text,
            "unit": price_info["unit"],
            "savings": float(price_info["savings"]) if price_info.get("savings") else None,
            "page": pages[i],
            "confidence": 0.80,
            "source": "makro",
        })

    # Post-process: clean up names that still have noise
    for rec in results:
        name = rec["item"]
        # Strip "Terms and conditions..." prefixes that leaked through
        name = re.sub(
            r"^.*?Terms and conditions.*?MKNLLQ\d+\s*",
            "", name, flags=re.IGNORECASE,
        ).strip()
        # Strip "Unit price per case RXXX.XX" prefixes
        name = re.sub(r"^Unit price per case R[\d,.]+\s*", "", name, flags=re.IGNORECASE).strip()
        # Strip leading size patterns like "1 x 750 ml (SKU)"
        name = re.sub(r"^\d+\s*x\s*[\d.]+\s*(?:ml|L|l)\s*(?:\([^)]*\)\s*)?", "", name, flags=re.IGNORECASE).strip()
        rec["item"] = name

    # Remove entries with empty names after cleanup
    results = [r for r in results if r["item"]]

    logger.info(f"Extracted {len(results)} products from Makro PDF")
    return results
