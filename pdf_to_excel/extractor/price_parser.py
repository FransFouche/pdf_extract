"""Price extraction tuned for the Ultra Liquors broadsheet PDF layout.

Each pdfplumber "table" represents one product block with a consistent structure:
  Row 0:  empty / decoration
  Row 1:  retail price digits split across cells  (e.g. ['', '359', '99'])
  Row 2:  bottle size  (e.g. [None, None, '750ml'])
  Row 3:  empty
  Row 4:  case info string  (e.g. '12 x 750ml R4 200.00  Unit Price p/case R350.00')
  Row 5:  product name      (e.g. 'JAMESON TRIPLE DISTILLED  IRISH WHISKEY')
"""

import re
import logging

logger = logging.getLogger(__name__)

CASE_RE = re.compile(
    r"(\d+\s*x\s*[\d.]+\s*(?:ml|L|lt))\s*R\s*([\d\s,]+\.\d{2})",
    re.IGNORECASE,
)
UNIT_RE = re.compile(r"Unit\s*Price\s*p/case\s*R\s*([\d\s,]+\.\d{2})", re.IGNORECASE)
TABLE_BOUNDARY = "__TABLE_BOUNDARY__"


def _parse_price_str(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


def _extract_retail_price(row: list[str]) -> float | None:
    digits = [c.strip() for c in row if c and c.strip().isdigit()]
    if len(digits) == 2:
        return float(f"{digits[0]}.{digits[1]}")
    if len(digits) == 1:
        d = digits[0]
        if len(d) >= 3:
            return float(f"{d[:-2]}.{d[-2:]}")
    return None


def _extract_product_name(cells: list[str]) -> str:
    parts = []
    for c in cells:
        if c:
            # Normalize unicode replacement chars and smart quotes
            cleaned = c.strip().replace("\n", " ")
            cleaned = cleaned.replace("\uf6ba", " ")  # private-use area char in this PDF
            parts.append(cleaned)
    return " ".join(parts).strip()


def _extract_bottle_size(cells: list[str]) -> str:
    for c in cells:
        if c and re.search(r"\d+\s*(?:ml|L|lt)", c, re.IGNORECASE):
            return c.strip()
    return ""


def _parse_case_info(cells: list[str]) -> dict:
    text = " ".join(c.strip().replace("\n", " ") for c in cells if c)
    info = {}
    m = CASE_RE.search(text)
    if m:
        info["pack_size"] = m.group(1).strip()
        info["case_price"] = _parse_price_str(m.group(2))
    m = UNIT_RE.search(text)
    if m:
        info["unit_price"] = _parse_price_str(m.group(1))
    return info


def _split_into_blocks(rows: list[dict]) -> list[list[dict]]:
    """Split rows at TABLE_BOUNDARY markers into per-product blocks."""
    blocks: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        if row.get("raw") == TABLE_BOUNDARY:
            if current:
                blocks.append(current)
            current = []
        elif row["source"] == "table":
            current.append(row)
    if current:
        blocks.append(current)
    return blocks


def _parse_product_block(block_rows: list[dict]) -> dict | None:
    cells_list = [r["cells"] for r in block_rows if r["cells"]]
    raws = [r["raw"] for r in block_rows]
    page = block_rows[0]["page"] if block_rows else 0

    if len(cells_list) < 2:
        return _parse_text_block(raws, page)

    # Product name: last row with meaningful alphabetic content
    product_name = ""
    for cells in reversed(cells_list):
        candidate = _extract_product_name(cells)
        if candidate and re.search(r"[A-Za-z]{2,}", candidate):
            # Skip rows that are clearly case-info, not product names
            if re.search(r"p/case|Unit\s*Price|SHOP|ONLINE|ultraliquors|0800|Quantities|Valid\s*from", candidate, re.IGNORECASE):
                continue
            product_name = candidate
            break

    if not product_name:
        return None

    # Retail price: first row with just digit cells
    retail_price = None
    for cells in cells_list:
        rp = _extract_retail_price(cells)
        if rp and rp > 1:
            retail_price = rp
            break

    # Bottle size
    bottle_size = ""
    for cells in cells_list:
        bs = _extract_bottle_size(cells)
        if bs:
            bottle_size = bs
            break

    # Case info
    case_info = {}
    for cells in cells_list:
        ci = _parse_case_info(cells)
        if ci:
            case_info = ci
            break
    if not case_info:
        for raw in raws:
            ci = _parse_case_info([raw])
            if ci:
                case_info = ci
                break

    if retail_price is None and not case_info:
        return None

    return {
        "item": product_name,
        "price": retail_price or case_info.get("unit_price", 0),
        "retail_price": retail_price,
        "case_price": case_info.get("case_price"),
        "unit_price": case_info.get("unit_price"),
        "pack_size": case_info.get("pack_size", ""),
        "bottle_size": bottle_size,
        "page": page,
        "confidence": 0.9 if (product_name and retail_price) else 0.7,
    }


def _parse_text_block(raws: list[str], page: int) -> dict | None:
    for raw in raws:
        m = re.search(r"(.+?)\s+R\s*([\d\s,]+\.\d{2})", raw)
        if m:
            item = m.group(1).strip()
            price = _parse_price_str(m.group(2))
            if item and price > 0:
                return {
                    "item": item,
                    "price": price,
                    "retail_price": price,
                    "case_price": None,
                    "unit_price": None,
                    "pack_size": "",
                    "bottle_size": "",
                    "page": page,
                    "confidence": 0.6,
                }
    return None


def extract_prices(rows: list[dict]) -> list[dict]:
    """Process raw PDF rows, returning structured item/price dicts."""
    blocks = _split_into_blocks(rows)
    logger.info(f"Found {len(blocks)} table blocks across all pages")

    results = []
    for block in blocks:
        product = _parse_product_block(block)
        if product:
            results.append(product)

    logger.info(f"Extracted {len(results)} products")
    return results
